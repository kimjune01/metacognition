# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functioning RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-source Aggregation**: Handles multiple RSS URLs per category, combining entries from different sources
3. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries from the same feed
4. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9) with human-readable formatting
5. **Persistent Storage**: Saves aggregated feeds as JSON files (one per category) in `~/.rreader/`
6. **Configuration Management**: 
   - Stores feed URLs in `feeds.json` with category-based organization
   - Copies bundled default feeds on first run
   - Merges new categories from bundled feeds into existing user configuration
7. **Sorting**: Orders entries by timestamp (newest first)
8. **Metadata Extraction**: Captures title, URL, publication date, source name, and optional author information
9. **Selective Updates**: Can refresh a single category or all categories
10. **Basic Error Handling**: Catches exceptions during feed parsing without crashing

## Triage

### Critical Gaps (Must-Have for Production)

1. **Error Handling and Logging** - Currently swallows exceptions silently; production needs comprehensive error tracking
2. **Stale Data Management** - No cache expiration or data freshness validation
3. **Network Resilience** - No timeout configuration, retry logic, or connection pooling
4. **Data Validation** - Missing input sanitization and schema validation for feeds and configuration

### High Priority (Should-Have)

5. **Concurrency** - Sequential feed fetching; should parallelize for performance
6. **Rate Limiting** - No backoff or request throttling to respect server limits
7. **Feed Health Monitoring** - No tracking of which feeds consistently fail
8. **Configuration Validation** - Doesn't validate `feeds.json` structure or URL validity
9. **Update Scheduling** - No mechanism for periodic automatic updates

### Medium Priority (Nice-to-Have)

10. **Content Filtering** - No duplicate detection across different sources or content deduplication
11. **Storage Management** - No limits on data size or cleanup of old entries
12. **Performance Optimization** - No conditional GET (ETag/Last-Modified) support
13. **User Feedback** - Minimal progress indication; needs better UI/logging
14. **Extensibility** - Hard to add custom feed processors or output formats

### Low Priority (Future Enhancement)

15. **Analytics** - No metrics on feed performance, read rates, or usage patterns
16. **Search Capability** - No full-text search across cached entries
17. **Export Options** - Limited to JSON; could support other formats

## Plan

### 1. Error Handling and Logging

**Changes needed:**
```python
import logging
from typing import Dict, List, Optional

# Add at module level
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
        logging.StreamHandler()
    ]
)

# Replace try/except blocks:
try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser error flag
        logger.warning(f"Feed parsing warning for {url}: {d.bozo_exception}")
except Exception as e:
    logger.error(f"Failed to fetch {url}: {type(e).__name__}: {str(e)}")
    continue  # Don't exit, continue with other feeds
```

### 2. Stale Data Management

**Changes needed:**
```python
# Add configuration in config.py
CACHE_DURATION_SECONDS = 300  # 5 minutes default

# In do() function, check cache age:
def is_cache_fresh(category: str, max_age: int = CACHE_DURATION_SECONDS) -> bool:
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(cache_file):
        return False
    
    with open(cache_file, 'r') as f:
        data = json.load(f)
    
    created_at = data.get('created_at', 0)
    return (int(time.time()) - created_at) < max_age

# Before fetching, check:
if target_category and is_cache_fresh(target_category):
    with open(os.path.join(p["path_data"], f"rss_{target_category}.json"), 'r') as f:
        return json.load(f)
```

### 3. Network Resilience

**Changes needed:**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Create session with retry logic
def get_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Replace feedparser.parse(url):
session = get_session()
response = session.get(url, timeout=10)
response.raise_for_status()
d = feedparser.parse(response.content)
```

### 4. Data Validation

**Changes needed:**
```python
from jsonschema import validate, ValidationError

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"}
            },
            "required": ["feeds"]
        }
    }
}

# After loading feeds.json:
try:
    validate(instance=RSS, schema=FEEDS_SCHEMA)
except ValidationError as e:
    logger.error(f"Invalid feeds.json: {e.message}")
    sys.exit(1)

# Sanitize feed data:
import html

entries = {
    "title": html.escape(feed.title),
    "url": feed.link if feed.link.startswith(('http://', 'https://')) else '',
    # ... other fields
}
```

### 5. Concurrency

**Changes needed:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source: str, url: str, show_author: bool) -> Dict:
    """Fetch and parse a single feed."""
    try:
        d = feedparser.parse(url)
        entries = []
        # ... existing parsing logic
        return {source: entries}
    except Exception as e:
        logger.error(f"Error fetching {url}: {e}")
        return {source: []}

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(fetch_single_feed, source, url, show_author): source
            for source, url in urls.items()
        }
        
        for future in as_completed(futures):
            source = futures[future]
            try:
                feed_data = future.result()
                rslt.update(feed_data)
            except Exception as e:
                logger.error(f"Failed to process feed {source}: {e}")
    
    # ... rest of aggregation logic
```

### 6. Rate Limiting

**Changes needed:**
```python
import time
from threading import Lock

class RateLimiter:
    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request = 0
        self.lock = Lock()
    
    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_request
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request = time.time()

# Use in fetch_single_feed:
rate_limiter = RateLimiter(requests_per_second=2.0)

def fetch_single_feed(source, url, show_author):
    rate_limiter.wait()
    # ... rest of function
```

### 7. Feed Health Monitoring

**Changes needed:**
```python
# Add health tracking file
HEALTH_FILE = os.path.join(p["path_data"], "feed_health.json")

def update_feed_health(url: str, success: bool):
    health = {}
    if os.path.exists(HEALTH_FILE):
        with open(HEALTH_FILE, 'r') as f:
            health = json.load(f)
    
    if url not in health:
        health[url] = {"success": 0, "failure": 0, "last_check": None}
    
    if success:
        health[url]["success"] += 1
    else:
        health[url]["failure"] += 1
    
    health[url]["last_check"] = int(time.time())
    
    with open(HEALTH_FILE, 'w') as f:
        json.dump(health, f, indent=2)

# Call after each feed attempt:
update_feed_health(url, success=d.status == 200 if hasattr(d, 'status') else True)

# Add health report function:
def get_failing_feeds(threshold: float = 0.5) -> List[str]:
    """Return feeds with failure rate above threshold."""
    if not os.path.exists(HEALTH_FILE):
        return []
    
    with open(HEALTH_FILE, 'r') as f:
        health = json.load(f)
    
    failing = []
    for url, stats in health.items():
        total = stats["success"] + stats["failure"]
        if total > 0 and stats["failure"] / total > threshold:
            failing.append(url)
    
    return failing
```

### 8. Configuration Validation

**Changes needed:**
```python
from urllib.parse import urlparse

def validate_feeds_config(config: Dict) -> List[str]:
    """Validate feeds configuration, return list of errors."""
    errors = []
    
    for category, data in config.items():
        if not isinstance(data, dict):
            errors.append(f"Category '{category}' must be an object")
            continue
        
        if "feeds" not in data:
            errors.append(f"Category '{category}' missing 'feeds' field")
            continue
        
        for source, url in data["feeds"].items():
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                errors.append(f"Invalid URL for {category}/{source}: {url}")
    
    return errors

# After loading feeds.json:
errors = validate_feeds_config(RSS)
if errors:
    for error in errors:
        logger.error(error)
    sys.exit(1)
```

### 9. Update Scheduling

**Changes needed:**
```python
# Create new scheduler module
import schedule
import threading

def run_continuously(interval=1):
    """Run scheduler in background thread."""
    cease_continuous_run = threading.Event()
    
    class ScheduleThread(threading.Thread):
        @classmethod
        def run(cls):
            while not cease_continuous_run.is_set():
                schedule.run_pending()
                time.sleep(interval)
    
    continuous_thread = ScheduleThread()
    continuous_thread.daemon = True
    continuous_thread.start()
    return cease_continuous_run

# Add scheduling configuration:
def start_scheduler(update_interval_minutes: int = 15):
    """Schedule periodic feed updates."""
    schedule.every(update_interval_minutes).minutes.do(lambda: do(log=True))
    return run_continuously()

# Usage:
if __name__ == "__main__":
    # Initial update
    do(log=True)
    # Start scheduler
    stop_scheduler = start_scheduler(update_interval_minutes=15)
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_scheduler.set()
```

### 10. Content Filtering

**Changes needed:**
```python
import hashlib

def content_hash(entry: Dict) -> str:
    """Generate hash for duplicate detection."""
    content = f"{entry['title']}|{entry.get('summary', '')}"
    return hashlib.md5(content.encode()).hexdigest()

def deduplicate_entries(entries: List[Dict]) -> List[Dict]:
    """Remove duplicate entries across sources."""
    seen_hashes = set()
    unique_entries = []
    
    for entry in entries:
        h = content_hash(entry)
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique_entries.append(entry)
    
    return unique_entries

# Apply before writing to file:
rslt["entries"] = deduplicate_entries(rslt["entries"])
```

### 11. Storage Management

**Changes needed:**
```python
MAX_ENTRIES_PER_CATEGORY = 1000
MAX_AGE_DAYS = 30

def prune_old_entries(entries: List[Dict], max_entries: int = MAX_ENTRIES_PER_CATEGORY, 
                      max_age_days: int = MAX_AGE_DAYS) -> List[Dict]:
    """Remove old or excess entries."""
    cutoff_timestamp = int(time.time()) - (max_age_days * 86400)
    
    # Filter by age
    recent = [e for e in entries if e.get("timestamp", 0) > cutoff_timestamp]
    
    # Limit total count
    return recent[:max_entries]

# Apply before writing:
rslt["entries"] = prune_old_entries(rslt["entries"])
```

### 12. Performance Optimization

**Changes needed:**
```python
def fetch_with_etag(url: str, category: str) -> Optional[feedparser.FeedParserDict]:
    """Fetch feed using conditional GET."""
    etag_file = os.path.join(p["path_data"], f"{category}_etags.json")
    etags = {}
    
    if os.path.exists(etag_file):
        with open(etag_file, 'r') as f:
            etags = json.load(f)
    
    etag = etags.get(url, {}).get('etag')
    modified = etags.get(url, {}).get('modified')
    
    d = feedparser.parse(url, etag=etag, modified=modified)
    
    # Update stored etags
    if hasattr(d, 'etag') or hasattr(d, 'modified'):
        etags[url] = {
            'etag': getattr(d, 'etag', None),
            'modified': getattr(d, 'modified', None)
        }
        with open(etag_file, 'w') as f:
            json.dump(etags, f)
    
    # Return None if not modified
    if d.status == 304:
        return None
    
    return d
```

### 13. User Feedback

**Changes needed:**
```python
from tqdm import tqdm

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    progress = tqdm(urls.items(), desc=f"Fetching {category}", disable=not log)
    
    for source, url in progress:
        progress.set_postfix_str(source)
        try:
            d = feedparser.parse(url)
            # ... processing
        except Exception as e:
            progress.write(f"✗ {source}: {str(e)}")
            continue
    
    return rslt
```

### 14. Extensibility

**Changes needed:**
```python
from abc import ABC, abstractmethod
from typing import Protocol

class FeedProcessor(Protocol):
    """Protocol for custom feed processors."""
    
    def process_entry(self, entry: Dict, source: str) -> Dict:
        """Transform a feed entry."""
        ...
    
    def filter_entry(self, entry: Dict) -> bool:
        """Return True if entry should be included."""
        ...

class DefaultProcessor:
    def process_entry(self, entry, source):
        return entry
    
    def filter_entry(self, entry):
        return True

# Allow custom processors per category in feeds.json:
# {
#   "tech": {
#     "feeds": {...},
#     "processor": "custom_processors.TechProcessor"
#   }
# }

def load_processor(processor_path: str) -> FeedProcessor:
    """Dynamically load custom processor."""
    module_name, class_name = processor_path.rsplit('.', 1)
    module = __import__(module_name, fromlist=[class_name])
    return getattr(module, class_name)()
```

### 15. Analytics

**Changes needed:**
```python
# Add analytics module
class FeedAnalytics:
    def __init__(self, analytics_file: str):
        self.analytics_file = analytics_file
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.analytics_file):
            with open(self.analytics_file, 'r') as f:
                return json.load(f)
        return {"fetch_times": {}, "entry_counts": {}, "error_counts": {}}
    
    def record_fetch(self, category: str, duration: float, entry_count: int, errors: int):
        if category not in self.data["fetch_times"]:
            self.data["fetch_times"][category] = []
            self.data["entry_counts"][category] = []
            self.data["error_counts"][category] = []
        
        self.data["fetch_times"][category].append({
            "timestamp": int(time.time()),
            "duration": duration
        })
        self.data["entry_counts"][category].append(entry_count)
        self.data["error_counts"][category].append(errors)
        
        self._save()
    
    def _save(self):
        with open(self.analytics_file, 'w') as f:
            json.dump(self.data, f)
    
    def get_summary(self, category: str) -> Dict:
        """Get analytics summary for category."""
        if category not in self.data["fetch_times"]:
            return {}
        
        fetch_times = [f["duration"] for f in self.data["fetch_times"][category][-100:]]
        return {
            "avg_fetch_time": sum(fetch_times) / len(fetch_times) if fetch_times else 0,
            "avg_entries": sum(self.data["entry_counts"][category][-100:]) / min(100, len(self.data["entry_counts"][category])),
            "total_errors": sum(self.data["error_counts"][category])
        }
```