# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed reader with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-Category Support**: Organizes feeds into categories, each with multiple sources
3. **Data Persistence**: Stores parsed feed data as JSON files in a user directory (`~/.rreader/`)
4. **Timestamp Handling**: Converts feed publication times to a configured timezone (currently KST/UTC+9)
5. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries from the same feed
6. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Bundles default feeds with the package
   - Merges new bundled categories into user configuration without overwriting
7. **Date Formatting**: Displays relative dates (time-only for today, date+time for older entries)
8. **Selective Updates**: Can update a single category or all categories
9. **Author Display**: Configurable per-category to show source name or actual author
10. **Logging**: Optional verbose output during feed fetching

## Triage

### Critical Gaps (Must-Have for Production)

1. **Error Handling**: Minimal error recovery; silent failures lose data
2. **Network Reliability**: No retry logic, timeouts, or connection pooling
3. **Data Validation**: No schema validation for feeds or configuration files
4. **Concurrency Issues**: No file locking; concurrent runs could corrupt data
5. **Security**: No input sanitization, URL validation, or HTTPS enforcement

### High Priority (Should-Have)

6. **Performance**: Sequential feed fetching; no parallelization for multiple sources
7. **Rate Limiting**: No protection against hammering feed servers
8. **Stale Data Management**: Old entries never expire or get cleaned up
9. **Monitoring**: No metrics on feed health, fetch success rates, or latency
10. **User Feedback**: Minimal progress indication; no success/failure summary

### Medium Priority (Nice-to-Have)

11. **Configuration Validation**: No checks for malformed URLs or invalid JSON
12. **Duplicate Detection**: Uses only timestamp; doesn't handle same entry with different timestamps
13. **Content Extraction**: Stores only metadata; no feed content/description
14. **Incremental Updates**: Always fetches full feeds; no conditional requests (ETag/If-Modified-Since)
15. **Unicode Handling**: Some risk with filename encoding on non-UTF8 systems

### Low Priority (Future Enhancements)

16. **Feed Discovery**: No OPML import/export
17. **Search**: No indexing or search capability
18. **Read/Unread Tracking**: No state management for user interactions
19. **Testing**: No unit tests or integration tests present
20. **Documentation**: No inline documentation or user guide

## Plan

### 1. Error Handling (Critical)
```python
# Replace bare try/except with specific error handling:
import requests
from requests.exceptions import RequestException, Timeout

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    failed_feeds = []
    
    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            
            # Add timeout
            d = feedparser.parse(url, timeout=30)
            
            # Check for parsing errors
            if d.bozo and not isinstance(d.bozo_exception, feedparser.CharacterEncodingOverride):
                raise ValueError(f"Feed parse error: {d.bozo_exception}")
            
            if log:
                sys.stdout.write(" - Done\n")
                
        except (RequestException, Timeout) as e:
            failed_feeds.append((source, url, str(e)))
            if log:
                sys.stdout.write(f" - Failed: {e}\n")
            continue
        except Exception as e:
            failed_feeds.append((source, url, str(e)))
            if log:
                sys.stdout.write(f" - Unexpected error: {e}\n")
            continue
    
    # Return both results and failures
    return rslt, failed_feeds
```

### 2. Network Reliability (Critical)
```python
# Add retry decorator and session management:
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_session():
    """Create requests session with retry logic"""
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Use in feedparser:
session = get_session()
d = feedparser.parse(url, request_headers={'User-Agent': 'rreader/1.0'})
```

### 3. Data Validation (Critical)
```python
# Add JSON schema validation:
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {
                        ".*": {"type": "string", "format": "uri"}
                    }
                },
                "show_author": {"type": "boolean"}
            }
        }
    }
}

def load_feeds_config():
    with open(FEEDS_FILE_NAME, "r") as fp:
        data = json.load(fp)
    try:
        jsonschema.validate(data, FEEDS_SCHEMA)
    except jsonschema.ValidationError as e:
        sys.exit(f"Invalid feeds.json: {e.message}")
    return data
```

### 4. Concurrency Issues (Critical)
```python
# Add file locking:
import fcntl
from contextlib import contextmanager

@contextmanager
def locked_file(filepath, mode='r'):
    """Context manager for file locking"""
    with open(filepath, mode) as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

# Usage:
with locked_file(json_path, 'w') as f:
    f.write(json.dumps(rslt, ensure_ascii=False))
```

### 5. Security (Critical)
```python
# Add URL validation and sanitization:
from urllib.parse import urlparse

def validate_url(url):
    """Validate URL is well-formed and uses safe protocol"""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ['http', 'https']:
            raise ValueError(f"Invalid protocol: {parsed.scheme}")
        if not parsed.netloc:
            raise ValueError("Missing domain")
        return True
    except Exception as e:
        raise ValueError(f"Invalid URL {url}: {e}")

# Apply before parsing:
for source, url in urls.items():
    validate_url(url)
```

### 6. Performance (High Priority)
```python
# Add parallel feed fetching:
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    """Fetch a single feed (for parallelization)"""
    try:
        d = feedparser.parse(url)
        return source, d, None
    except Exception as e:
        return source, None, e

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(fetch_single_feed, source, url, log): source 
            for source, url in urls.items()
        }
        
        for future in as_completed(futures):
            source, data, error = future.result()
            if error:
                if log:
                    print(f"Failed {source}: {error}")
                continue
            # Process data...
```

### 7. Rate Limiting (High Priority)
```python
# Add rate limiting per domain:
from collections import defaultdict
import time
from urllib.parse import urlparse

class RateLimiter:
    def __init__(self, min_interval=1.0):
        self.min_interval = min_interval
        self.last_request = defaultdict(float)
    
    def wait(self, url):
        domain = urlparse(url).netloc
        elapsed = time.time() - self.last_request[domain]
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request[domain] = time.time()

# Use before each request:
rate_limiter = RateLimiter(min_interval=1.0)
rate_limiter.wait(url)
```

### 8. Stale Data Management (High Priority)
```python
# Add cleanup of old entries:
def cleanup_old_entries(category, max_age_days=30):
    """Remove entries older than max_age_days"""
    json_path = os.path.join(p["path_data"], f"rss_{category}.json")
    
    with locked_file(json_path, 'r+') as f:
        data = json.load(f)
        cutoff = int(time.time()) - (max_age_days * 86400)
        
        original_count = len(data['entries'])
        data['entries'] = [
            e for e in data['entries'] 
            if e['timestamp'] > cutoff
        ]
        
        if len(data['entries']) < original_count:
            f.seek(0)
            f.truncate()
            json.dump(data, f, ensure_ascii=False)
            return original_count - len(data['entries'])
    return 0
```

### 9. Monitoring (High Priority)
```python
# Add metrics collection:
import logging

class FeedMetrics:
    def __init__(self):
        self.success_count = 0
        self.failure_count = 0
        self.total_entries = 0
        self.start_time = time.time()
    
    def record_success(self, entry_count):
        self.success_count += 1
        self.total_entries += entry_count
    
    def record_failure(self):
        self.failure_count += 1
    
    def report(self):
        duration = time.time() - self.start_time
        return {
            'success': self.success_count,
            'failures': self.failure_count,
            'total_entries': self.total_entries,
            'duration_seconds': duration
        }

# Log to file:
logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```

### 10. User Feedback (High Priority)
```python
# Add summary reporting:
def do(target_category=None, log=False):
    metrics = FeedMetrics()
    
    # ... existing code ...
    
    # At end:
    report = metrics.report()
    if log:
        print(f"\n=== Summary ===")
        print(f"Feeds fetched: {report['success']}/{report['success']+report['failures']}")
        print(f"Total entries: {report['total_entries']}")
        print(f"Duration: {report['duration_seconds']:.2f}s")
    
    return report
```

### 11. Configuration Validation (Medium Priority)
```python
# Add startup validation:
def validate_feeds_file():
    """Validate feeds.json on startup"""
    try:
        with open(FEEDS_FILE_NAME, 'r') as fp:
            data = json.load(fp)
        
        for category, config in data.items():
            if 'feeds' not in config:
                raise ValueError(f"Category '{category}' missing 'feeds'")
            
            for source, url in config['feeds'].items():
                validate_url(url)
        
        return data
    except json.JSONDecodeError as e:
        sys.exit(f"Malformed feeds.json: {e}")
    except ValueError as e:
        sys.exit(f"Invalid feeds.json: {e}")
```

### 12. Duplicate Detection (Medium Priority)
```python
# Use content hash instead of just timestamp:
import hashlib

def get_entry_id(feed):
    """Generate unique ID from feed content"""
    content = f"{feed.link}{feed.title}".encode('utf-8')
    return hashlib.md5(content).hexdigest()

# Replace in get_feed_from_rss:
entry_id = get_entry_id(feed)
if entry_id in rslt:
    continue  # Skip duplicate
rslt[entry_id] = entries
```

### 14. Incremental Updates (Medium Priority)
```python
# Add ETag/Last-Modified support:
def save_feed_metadata(category, source, etag, last_modified):
    """Store feed metadata for conditional requests"""
    meta_file = os.path.join(p["path_data"], f"meta_{category}.json")
    
    meta = {}
    if os.path.exists(meta_file):
        with open(meta_file, 'r') as f:
            meta = json.load(f)
    
    meta[source] = {
        'etag': etag,
        'last_modified': last_modified,
        'last_checked': int(time.time())
    }
    
    with open(meta_file, 'w') as f:
        json.dump(meta, f)

# Use in requests:
meta = load_feed_metadata(category, source)
headers = {}
if meta.get('etag'):
    headers['If-None-Match'] = meta['etag']
if meta.get('last_modified'):
    headers['If-Modified-Since'] = meta['last_modified']

d = feedparser.parse(url, request_headers=headers)
if d.status == 304:  # Not Modified
    # Use cached data
    pass
```