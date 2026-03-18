# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-Category Support**: Organizes feeds into categories, each with multiple feed sources
3. **Feed Configuration Management**: 
   - Maintains a `feeds.json` configuration file in `~/.rreader/`
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration
4. **Data Persistence**: Saves parsed feed entries as JSON files (`rss_{category}.json`) in the data directory
5. **Timezone Handling**: Converts feed timestamps to a configured timezone (KST/UTC+9)
6. **Smart Date Formatting**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
7. **Deduplication**: Uses timestamp as ID to prevent duplicate entries within a category
8. **Sorted Output**: Orders entries by timestamp (newest first)
9. **Optional Logging**: Can display progress messages during feed fetching
10. **Flexible Author Display**: Supports per-category configuration for showing feed authors vs source names

## Triage

### Critical Gaps (P0)
1. **No Error Handling**: The bare `except:` clauses silently swallow all errors, making debugging impossible
2. **Timestamp Collision Vulnerability**: Using timestamp as ID will cause data loss when multiple entries share the same second
3. **No Rate Limiting**: Will hammer feed servers if called repeatedly, risking IP bans

### High Priority Gaps (P1)
4. **No Retry Logic**: Network failures immediately fail the entire feed source
5. **Missing Input Validation**: No validation that `feeds.json` has correct structure
6. **No Concurrency**: Fetches feeds sequentially, making updates very slow
7. **No Caching Strategy**: No HTTP conditional requests (ETag/Last-Modified), wastes bandwidth
8. **Silent Data Loss**: When a single entry fails parsing, it's silently skipped with no notification

### Medium Priority Gaps (P2)
9. **No Feed Health Monitoring**: No tracking of which feeds consistently fail
10. **Missing Content Sanitization**: Feed titles/content aren't sanitized, could contain malicious data
11. **No Update Frequency Control**: No way to specify different update intervals per feed
12. **Incomplete Logging**: Log flag only affects network requests, not parsing or file operations
13. **No User Feedback**: When used as a library, no progress indication for long operations
14. **Missing Metadata**: Doesn't store feed descriptions, images, or other useful metadata

### Low Priority Gaps (P3)
15. **Hardcoded Timezone**: Configuration should be in a user-editable file
16. **No Feed Discovery**: Can't automatically find RSS feeds from a website URL
17. **No Export Functionality**: Can't export/backup feed configuration
18. **Limited Date Parsing**: Assumes feeds use standard datetime formats

## Plan

### P0 Fixes

**1. Error Handling**
```python
# Replace bare except clauses with specific exceptions and logging
import logging

logger = logging.getLogger(__name__)

try:
    d = feedparser.parse(url)
except (ConnectionError, TimeoutError) as e:
    logger.error(f"Network error fetching {url}: {e}")
    continue
except Exception as e:
    logger.error(f"Unexpected error parsing {url}: {e}", exc_info=True)
    continue

# For feed parsing, collect errors and return them
for feed in d.entries:
    try:
        # ... parsing logic ...
    except (AttributeError, KeyError) as e:
        logger.warning(f"Malformed entry in {source}: {e}")
        continue
```

**2. Timestamp Collision Fix**
```python
# Use compound key: timestamp + hash of URL
import hashlib

def generate_entry_id(timestamp, url):
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{timestamp}_{url_hash}"

entries = {
    "id": generate_entry_id(ts, feed.link),
    # ... rest of fields ...
}
```

**3. Rate Limiting**
```python
import threading
from collections import defaultdict

class RateLimiter:
    def __init__(self, min_interval=1.0):
        self.last_request = defaultdict(float)
        self.min_interval = min_interval
        self.lock = threading.Lock()
    
    def wait(self, domain):
        with self.lock:
            elapsed = time.time() - self.last_request[domain]
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request[domain] = time.time()

# Usage:
from urllib.parse import urlparse
limiter = RateLimiter(min_interval=2.0)
domain = urlparse(url).netloc
limiter.wait(domain)
d = feedparser.parse(url)
```

### P1 Fixes

**4. Retry Logic**
```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True
)
def fetch_feed(url, timeout=30):
    return feedparser.parse(url, timeout=timeout)
```

**5. Input Validation**
```python
from jsonschema import validate, ValidationError

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {".*": {"type": "string", "format": "uri"}}
                },
                "show_author": {"type": "boolean"}
            }
        }
    }
}

try:
    validate(instance=RSS, schema=FEEDS_SCHEMA)
except ValidationError as e:
    logger.error(f"Invalid feeds.json: {e.message}")
    sys.exit(1)
```

**6. Concurrency**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    try:
        return source, feedparser.parse(url), None
    except Exception as e:
        return source, None, e

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_single_feed, src, url): (src, url) 
                   for src, url in urls.items()}
        
        for future in as_completed(futures):
            source, data, error = future.result()
            if error:
                logger.error(f"Failed to fetch {source}: {error}")
                continue
            # Process data...
```

**7. HTTP Caching**
```python
# Store ETags and Last-Modified headers
cache_file = os.path.join(p["path_data"], f"cache_{category}.json")

def load_cache():
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)
    return {}

def fetch_with_cache(url, cache_data):
    headers = {}
    if url in cache_data:
        if 'etag' in cache_data[url]:
            headers['If-None-Match'] = cache_data[url]['etag']
        if 'modified' in cache_data[url]:
            headers['If-Modified-Since'] = cache_data[url]['modified']
    
    # feedparser supports etag and modified arguments
    d = feedparser.parse(url, etag=cache_data.get(url, {}).get('etag'),
                        modified=cache_data.get(url, {}).get('modified'))
    
    if d.status == 304:  # Not modified
        return None
    
    # Update cache
    cache_data[url] = {
        'etag': d.get('etag'),
        'modified': d.get('modified')
    }
    return d
```

**8. Error Reporting**
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            # ... fetch logic ...
            for feed in d.entries:
                try:
                    # ... parse logic ...
                except Exception as e:
                    errors.append(f"{source}: Failed to parse entry - {e}")
        except Exception as e:
            errors.append(f"{source}: Failed to fetch - {e}")
    
    # Include errors in output
    return {
        "entries": rslt,
        "created_at": int(time.time()),
        "errors": errors
    }
```

### P2 Fixes

**9. Feed Health Monitoring**
```python
# Add stats tracking
stats_file = os.path.join(p["path_data"], "feed_stats.json")

def update_feed_stats(source, success, error_msg=None):
    stats = load_stats()
    if source not in stats:
        stats[source] = {"success": 0, "failure": 0, "last_success": None, "last_error": None}
    
    if success:
        stats[source]["success"] += 1
        stats[source]["last_success"] = int(time.time())
    else:
        stats[source]["failure"] += 1
        stats[source]["last_error"] = {"time": int(time.time()), "msg": error_msg}
    
    save_stats(stats)
```

**10. Content Sanitization**
```python
import bleach

def sanitize_text(text):
    # Remove HTML tags, keep only plain text
    return bleach.clean(text, tags=[], strip=True)

entries = {
    "id": entry_id,
    "title": sanitize_text(feed.title),
    "url": feed.link,  # URLs should be validated
    # ...
}
```

**11. Update Frequency Control**
```python
# Add to feeds.json schema:
# "update_interval": 3600  (seconds)

def should_update(category, config):
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(cache_file):
        return True
    
    interval = config.get("update_interval", 3600)
    mtime = os.path.getmtime(cache_file)
    return (time.time() - mtime) > interval
```

**12. Comprehensive Logging**
```python
def setup_logging(log_level=logging.INFO):
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
            logging.StreamHandler(sys.stdout)
        ]
    )

# Use throughout:
logger.info(f"Starting update for category: {category}")
logger.debug(f"Fetching {url}")
logger.info(f"Saved {len(rslt)} entries to {output_file}")
```

This plan prioritizes stability and data integrity first, then performance, then user experience enhancements.