# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS/Atom feeds using the `feedparser` library
2. **Multi-source Aggregation**: Supports multiple feed sources organized by categories
3. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a single fetch
5. **Data Persistence**: Saves parsed feeds as JSON files in `~/.rreader/` directory
6. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user config without overwriting existing ones
7. **Selective Updates**: Can update a single category or all categories
8. **Flexible Author Display**: Supports per-category toggle for showing feed author vs. source name
9. **Human-readable Timestamps**: Formats dates as "HH:MM" for today, "Mon DD, HH:MM" for older items
10. **Basic Error Handling**: Continues processing other feeds if one fails

## Triage

### Critical Gaps (P0 - System Reliability)

1. **Silent Error Handling**: Failed feed fetches use `sys.exit(0)` or continue silently, masking failures
2. **No Logging Framework**: Uses ad-hoc `sys.stdout.write()` with a boolean flag
3. **Missing Input Validation**: No validation of feed URLs, category names, or JSON structure
4. **Race Conditions**: No file locking when reading/writing JSON files
5. **No Network Timeout Configuration**: Feed fetches could hang indefinitely

### High Priority Gaps (P1 - Production Readiness)

6. **No Retry Logic**: Network failures immediately abort without retry attempts
7. **Missing Metrics**: No tracking of fetch success/failure rates, latency, or feed health
8. **No Rate Limiting**: Could overwhelm feed sources or trigger rate limits
9. **Incomplete Error Context**: Exception handling loses stack traces and error details
10. **No Data Validation**: Doesn't verify JSON structure after loading from disk
11. **Missing Feed Metadata**: Doesn't track feed last-modified headers or ETags for conditional requests
12. **No Incremental Updates**: Re-fetches entire feeds even if unchanged

### Medium Priority Gaps (P2 - User Experience)

13. **No CLI Interface**: Requires programmatic invocation; no command-line arguments beyond hardcoded behavior
14. **Missing Progress Indicators**: No feedback during long multi-feed operations
15. **No Feed Health Monitoring**: Doesn't track which feeds consistently fail
16. **Hardcoded Timezone**: Timezone is configured but not easily changeable by users
17. **No Entry Limit**: Could create unbounded JSON files with very active feeds
18. **Missing Timestamp Fallback Chain**: Only tries two timestamp fields before giving up
19. **No Character Encoding Handling**: Relies on feedparser defaults without explicit encoding management

### Lower Priority Gaps (P3 - Nice to Have)

20. **No Database Backend**: JSON files don't scale well for historical data
21. **Missing Search/Filter**: No way to query across feeds
22. **No OPML Import/Export**: Standard feed list format not supported
23. **No Notification System**: No alerts for new items matching criteria
24. **Missing Feed Discovery**: No ability to search/add feeds from within the system

## Plan

### P0 Fixes

**1. Implement Proper Exception Handling**
```python
# Replace current try/except blocks with:
import logging

logger = logging.getLogger(__name__)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            logger.info(f"Fetching {url}")
            d = feedparser.parse(url)
            
            # Check for parse errors
            if hasattr(d, 'bozo') and d.bozo:
                logger.warning(f"Feed parse warning for {url}: {d.bozo_exception}")
                
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}", exc_info=True)
            errors.append({"source": source, "url": url, "error": str(e)})
            continue
    
    # Store errors in metadata
    rslt["fetch_errors"] = errors
    return rslt
```

**2. Add Structured Logging**
```python
# In do() function, initialize logging:
def do(target_category=None, log_level=logging.INFO):
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
            logging.StreamHandler()
        ]
    )
```

**3. Add Input Validation**
```python
def validate_feeds_config(config):
    """Validate feeds.json structure."""
    if not isinstance(config, dict):
        raise ValueError("Feeds config must be a dictionary")
    
    for category, data in config.items():
        if not isinstance(data, dict):
            raise ValueError(f"Category {category} must be a dictionary")
        if "feeds" not in data:
            raise ValueError(f"Category {category} missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category {category} 'feeds' must be a dictionary")
        
        for source, url in data["feeds"].items():
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL for {source}: {url}")
    
    return True

# Call before processing:
with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
    validate_feeds_config(RSS)
```

**4. Implement File Locking**
```python
import fcntl  # Unix
# or use portalocker library for cross-platform support

def atomic_write_json(filepath, data):
    """Write JSON with file locking."""
    temp_path = filepath + ".tmp"
    with open(temp_path, 'w', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    os.replace(temp_path, filepath)  # Atomic on POSIX systems
```

**5. Add Network Timeouts**
```python
# Modify feedparser calls:
import socket

# Set default timeout
socket.setdefaulttimeout(30)  # 30 seconds

# Or use requests with feedparser for better control:
import requests
from io import BytesIO

def fetch_with_timeout(url, timeout=30):
    response = requests.get(url, timeout=timeout, headers={
        'User-Agent': 'RReader/1.0 (RSS Aggregator)'
    })
    return feedparser.parse(BytesIO(response.content))
```

### P1 Fixes

**6. Add Retry Logic with Exponential Backoff**
```python
from time import sleep

def fetch_feed_with_retry(url, max_retries=3, base_delay=1):
    """Fetch feed with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            return feedparser.parse(url)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed for {url}, retrying in {delay}s")
            sleep(delay)
```

**7. Implement Metrics Collection**
```python
class FeedMetrics:
    def __init__(self):
        self.metrics = {
            "fetches_total": 0,
            "fetches_success": 0,
            "fetches_failed": 0,
            "total_entries": 0,
            "fetch_duration_ms": [],
        }
    
    def record_fetch(self, success, duration_ms, entry_count=0):
        self.metrics["fetches_total"] += 1
        if success:
            self.metrics["fetches_success"] += 1
            self.metrics["total_entries"] += entry_count
        else:
            self.metrics["fetches_failed"] += 1
        self.metrics["fetch_duration_ms"].append(duration_ms)
    
    def save(self, category):
        path = os.path.join(p["path_data"], f"metrics_{category}.json")
        with open(path, 'w') as f:
            json.dump(self.metrics, f, indent=2)

# Use in get_feed_from_rss:
metrics = FeedMetrics()
start = time.time()
try:
    d = feedparser.parse(url)
    metrics.record_fetch(True, (time.time() - start) * 1000, len(d.entries))
except:
    metrics.record_fetch(False, (time.time() - start) * 1000)
```

**8. Add Rate Limiting**
```python
from time import sleep
from collections import defaultdict

class RateLimiter:
    def __init__(self, requests_per_minute=30):
        self.delay = 60.0 / requests_per_minute
        self.last_request = defaultdict(float)
    
    def wait(self, domain):
        """Wait if necessary before making request to domain."""
        elapsed = time.time() - self.last_request[domain]
        if elapsed < self.delay:
            sleep(self.delay - elapsed)
        self.last_request[domain] = time.time()

# Use before fetching:
rate_limiter = RateLimiter(requests_per_minute=30)
from urllib.parse import urlparse
domain = urlparse(url).netloc
rate_limiter.wait(domain)
```

**9. Preserve Error Context**
```python
# Replace bare except: with explicit exception types
try:
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        raise ValueError("No timestamp found")
    at = datetime.datetime(*parsed_time[:6]).replace(tzinfo=datetime.timezone.utc).astimezone(TIMEZONE)
except (AttributeError, ValueError, TypeError, OverflowError) as e:
    logger.debug(f"Skipping entry '{feed.get('title', 'unknown')}' due to timestamp error: {e}")
    continue
```

**10. Validate Loaded Data**
```python
def validate_feed_json(data):
    """Validate structure of loaded feed JSON."""
    required_keys = ["entries", "created_at"]
    if not all(key in data for key in required_keys):
        raise ValueError(f"Feed JSON missing required keys: {required_keys}")
    
    if not isinstance(data["entries"], list):
        raise ValueError("'entries' must be a list")
    
    for entry in data["entries"]:
        required_entry_keys = ["id", "sourceName", "pubDate", "timestamp", "url", "title"]
        if not all(key in entry for key in required_entry_keys):
            raise ValueError(f"Entry missing required keys: {required_entry_keys}")
    
    return True

# Use when loading:
try:
    with open(feed_path, 'r') as f:
        data = json.load(f)
        validate_feed_json(data)
except (json.JSONDecodeError, ValueError) as e:
    logger.error(f"Invalid feed JSON at {feed_path}: {e}")
    # Fall back to empty feed or re-fetch
```

**11. Add Conditional Request Support**
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    # Load previous metadata
    metadata_path = os.path.join(p["path_data"], f"metadata_{category}.json")
    metadata = {}
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
    
    for source, url in urls.items():
        headers = {}
        if source in metadata:
            if 'etag' in metadata[source]:
                headers['If-None-Match'] = metadata[source]['etag']
            if 'last_modified' in metadata[source]:
                headers['If-Modified-Since'] = metadata[source]['last_modified']
        
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 304:
            logger.info(f"Feed {url} not modified, skipping")
            continue
        
        # Store new metadata
        metadata[source] = {
            'etag': response.headers.get('ETag'),
            'last_modified': response.headers.get('Last-Modified'),
            'fetched_at': int(time.time())
        }
        
        d = feedparser.parse(BytesIO(response.content))
    
    # Save metadata
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
```

**12. Implement Incremental Updates**
```python
def merge_feed_entries(existing_path, new_entries, max_entries=1000):
    """Merge new entries with existing, maintaining order and limit."""
    existing = []
    if os.path.exists(existing_path):
        with open(existing_path, 'r') as f:
            data = json.load(f)
            existing = data.get("entries", [])
    
    # Create dict keyed by ID for deduplication
    all_entries = {e["id"]: e for e in existing}
    all_entries.update({e["id"]: e for e in new_entries})
    
    # Sort by timestamp descending and limit
    merged = sorted(all_entries.values(), key=lambda x: x["timestamp"], reverse=True)
    return merged[:max_entries]
```

### P2 Fixes

**13. Add CLI Interface**
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('--category', '-c', help='Update specific category')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])
    parser.add_argument('--config', help='Path to feeds.json', default=FEEDS_FILE_NAME)
    
    args = parser.parse_args()
    
    log_level = getattr(logging, args.log_level)
    logging.basicConfig(level=log_level)
    
    do(target_category=args.category, log=args.verbose)

if __name__ == "__main__":
    main()
```

**14. Add Progress Indicators**
```python
from tqdm import tqdm  # or implement simple progress bar

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with tqdm(total=len(urls), desc=f"Fetching {category}", disable=not log) as pbar:
        for source, url in urls.items():
            pbar.set_description(f"Fetching {source}")
            # ... fetch logic ...
            pbar.update(1)
```

**15. Implement Feed Health Tracking**
```python
class FeedHealthTracker:
    def __init__(self, history_path):
        self.history_path = history_path
        self.load_history()
    
    def load_history(self):
        if os.path.exists(self.history_path):
            with open(self.history_path, 'r') as f:
                self.history = json.load(f)
        else:
            self.history = {}
    
    def record_result(self, source, success, error=None):
        if source not in self.history:
            self.history[source] = {
                "total_fetches": 0,
                "failed_fetches": 0,
                "last_success": None,
                "last_error": None,
                "consecutive_failures": 0
            }
        
        self.history[source]["total_fetches"] += 1
        
        if success:
            self.history[source]["last_success"] = int(time.time())
            self.history[source]["consecutive_failures"] = 0
        else:
            self.history[source]["failed_fetches"] += 1
            self.history[source]["last_error"] = error
            self.history[source]["consecutive_failures"] += 1
        
        self.save_history()
    
    def save_history(self):
        with open(self.history_path, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def get_unhealthy_feeds(self, threshold=5):
        """Return feeds with consecutive failures above threshold."""
        return {
            source: data 
            for source, data in self.history.items() 
            if data.get("consecutive_failures", 0) >= threshold
        }
```

**16. Make Timezone Configurable**
```python
# In config.py, add:
def get_timezone_from_config():
    config_path = os.path.join(p["path_data"], "config.json")
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
            tz_offset = config.get("timezone_offset_hours", 9)
    else:
        tz_offset = 9  # Default to KST
    
    return datetime.timezone(datetime.timedelta(hours=tz_offset))

TIMEZONE = get_timezone_from_config()
```

**17. Add Entry Limits**
```python
# In get_feed_from_rss, add parameter:
def get_feed_from_rss(category, urls, show_author=False, log=False, max_entries_per_feed=100):
    # ...
    for feed in d.entries[:max_entries_per_feed]:  # Limit entries per feed
        # ... process entry ...
```

**18. Expand Timestamp Fallback Chain**
```python
def extract_timestamp(feed_entry):
    """Try multiple timestamp fields with fallbacks."""
    timestamp_fields = [
        'published_parsed',
        'updated_parsed',
        'created_parsed',
        'modified_parsed'
    ]
    
    for field in timestamp_fields:
        parsed_time = getattr(feed_entry, field, None)
        if parsed_time:
            try:
                return datetime.datetime(*parsed_time[:6]).replace(
                    tzinfo=datetime.timezone.utc
                ).astimezone(TIMEZONE)
            except (ValueError, OverflowError):
                continue
    
    # If all else fails, use current time
    logger.warning(f"No valid timestamp for entry: {feed_entry.get('title', 'unknown')}")
    return datetime.datetime.now(TIMEZONE)
```

**19. Handle Character Encoding Explicitly**
```python
def fetch_feed_with_encoding(url):
    """Fetch feed with explicit encoding handling."""
    response = requests.get(url, timeout=30)
    
    # Try to detect encoding
    if response.encoding is None:
        response.encoding = 'utf-8'
    
    content = response.content
    
    # Try parsing with explicit encodings if feedparser fails
    d = feedparser.parse(content)
    
    if hasattr(d, 'bozo') and d.bozo and 'encoding' in str(d.bozo_exception):
        for encoding in ['utf-8', 'iso-8859-1', 'windows-1252']:
            try:
                d = feedparser.parse(content.decode(encoding))
                if not (hasattr(d, 'bozo') and d.bozo):
                    break
            except UnicodeDecodeError:
                continue
    
    return d
```

This diagnostic provides concrete, actionable improvements prioritized by impact on system reliability and user experience.