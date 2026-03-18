# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-category support**: Organizes feeds into categories defined in a JSON configuration file
3. **Timestamp normalization**: Converts feed publication dates to a configurable timezone (currently KST/UTC+9)
4. **Deduplication by timestamp**: Uses Unix timestamp as unique ID to prevent duplicate entries
5. **Data persistence**: Saves parsed feeds as JSON files per category (`rss_{category}.json`)
6. **Configuration management**: 
   - Bundles default feeds in `feeds.json` alongside the code
   - Copies to user directory (`~/.rreader/`) on first run
   - Merges new categories from bundled config into user config
7. **Flexible author display**: Supports per-category toggle for showing feed-level vs. entry-level author
8. **Sorted output**: Returns entries in reverse chronological order
9. **Relative date formatting**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones

## Triage

### Critical (blocks production deployment)

1. **No error recovery**: Single feed failure terminates entire category update with `sys.exit(0)`
2. **Timestamp collision vulnerability**: Multiple entries published in the same second overwrite each other
3. **No retry logic**: Transient network failures permanently fail updates
4. **Silent data loss**: Overwriting JSON files provides no backup or rollback capability

### High (impacts reliability)

5. **No rate limiting**: Simultaneous requests to same host can trigger 429/503 errors
6. **Missing HTTP timeouts**: Hanging requests block indefinitely
7. **No stale data detection**: Can't distinguish between "no new entries" and "feed broken"
8. **Unconstrained memory growth**: Loading all historical entries for deduplication scales O(n)

### Medium (impacts usability)

9. **No incremental updates**: Always fetches full feed even when only newest entries needed
10. **Lossy metadata**: Discards content, summary, tags, enclosures (podcast URLs, etc.)
11. **No entry expiration**: Old entries accumulate forever
12. **Hardcoded timezone**: Requires code change to support different locales

### Low (nice-to-have)

13. **No feed health monitoring**: Can't identify consistently failing feeds
14. **Missing validation**: Accepts malformed `feeds.json` without schema check
15. **No concurrency**: Sequential processing slow for 50+ feeds
16. **Primitive logging**: `sys.stdout.write` instead of proper logging framework

## Plan

### 1. Error Recovery (Critical)
**Change**: Wrap each feed fetch in try-except, collect failures, continue processing
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    failures = []
    
    for source, url in urls.items():
        try:
            # existing parsing logic
        except Exception as e:
            failures.append((source, url, str(e)))
            if log:
                sys.stderr.write(f"  Failed: {e}\n")
            continue  # Don't exit, process remaining feeds
    
    # Save both results and failures
    output = {
        "entries": rslt,
        "created_at": int(time.time()),
        "errors": failures
    }
```

### 2. Unique ID Generation (Critical)
**Change**: Replace timestamp-as-ID with composite key or hash
```python
import hashlib

def generate_entry_id(feed):
    # Use feed link + title for uniqueness
    content = f"{feed.link}::{feed.title}".encode('utf-8')
    return hashlib.sha256(content).hexdigest()[:16]

entries = {
    "id": generate_entry_id(feed),  # Guaranteed unique
    "timestamp": ts,  # Keep for sorting
    # ... rest of fields
}
```

### 3. Retry Logic (Critical)
**Change**: Add exponential backoff wrapper
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,  # 1s, 2s, 4s delays
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# In get_feed_from_rss:
session = create_session()
response = session.get(url, timeout=10)
d = feedparser.parse(response.content)
```

### 4. Atomic Writes with Backup (Critical)
**Change**: Write to temp file, then atomic rename
```python
import tempfile

def save_feed_data(category, data):
    filepath = os.path.join(p["path_data"], f"rss_{category}.json")
    backup = filepath + ".bak"
    
    # Keep one backup generation
    if os.path.exists(filepath):
        shutil.copy2(filepath, backup)
    
    # Write to temp file in same directory (ensures same filesystem)
    fd, temppath = tempfile.mkstemp(
        dir=p["path_data"], 
        prefix=f"rss_{category}_", 
        suffix=".tmp"
    )
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False)
        os.replace(temppath, filepath)  # Atomic on POSIX
    except:
        os.unlink(temppath)
        raise
```

### 5. Rate Limiting (High)
**Change**: Add per-host delay tracking
```python
from collections import defaultdict
from urllib.parse import urlparse

class RateLimiter:
    def __init__(self, delay_seconds=1.0):
        self.last_request = defaultdict(float)
        self.delay = delay_seconds
    
    def wait(self, url):
        host = urlparse(url).netloc
        elapsed = time.time() - self.last_request[host]
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request[host] = time.time()

# In get_feed_from_rss:
limiter = RateLimiter(delay_seconds=1.0)
for source, url in urls.items():
    limiter.wait(url)
    # ... fetch feed
```

### 6. HTTP Timeouts (High)
**Change**: Already shown in #3 retry logic with `timeout=10`

### 7. Staleness Detection (High)
**Change**: Track last successful update per feed
```python
output = {
    "entries": rslt,
    "created_at": int(time.time()),
    "last_modified": d.get('modified', None),  # ETag for conditional requests
    "etag": d.get('etag', None),
    "errors": failures
}

# On next fetch:
headers = {}
if prev_data.get('etag'):
    headers['If-None-Match'] = prev_data['etag']
if prev_data.get('last_modified'):
    headers['If-Modified-Since'] = prev_data['last_modified']
response = session.get(url, headers=headers, timeout=10)
if response.status_code == 304:
    # Not modified, reuse cached data
```

### 8. Memory-Efficient Deduplication (High)
**Change**: Load only recent IDs for deduplication check
```python
def load_recent_ids(category, days=7):
    """Load only IDs from last N days for deduplication"""
    filepath = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(filepath):
        return set()
    
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    cutoff = int(time.time()) - (days * 86400)
    return {
        entry['id'] 
        for entry in data.get('entries', []) 
        if entry.get('timestamp', 0) > cutoff
    }
```

### 9. Incremental Updates (Medium)
**Change**: Merge new entries with existing, keep max N
```python
def merge_entries(old_entries, new_entries, max_entries=1000):
    """Merge, deduplicate, sort, and limit entries"""
    combined = {e['id']: e for e in old_entries}
    combined.update({e['id']: e for e in new_entries})
    
    sorted_entries = sorted(
        combined.values(), 
        key=lambda x: x['timestamp'], 
        reverse=True
    )
    return sorted_entries[:max_entries]
```

### 10. Extended Metadata (Medium)
**Change**: Capture additional fields
```python
entries = {
    "id": generate_entry_id(feed),
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', '')[:500],  # Truncate to 500 chars
    "content": getattr(feed, 'content', [{}])[0].get('value', '')[:2000],
    "tags": [tag.term for tag in getattr(feed, 'tags', [])],
    "enclosures": [
        {"url": enc.href, "type": enc.get('type', 'unknown')}
        for enc in getattr(feed, 'enclosures', [])
    ]
}
```

### 11. Entry Expiration (Medium)
**Change**: Implement in merge_entries (see #9), or add separate cleanup:
```python
def cleanup_old_entries(category, days=30):
    filepath = os.path.join(p["path_data"], f"rss_{category}.json")
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    cutoff = int(time.time()) - (days * 86400)
    data['entries'] = [
        e for e in data['entries'] 
        if e.get('timestamp', 0) > cutoff
    ]
    
    save_feed_data(category, data)
```

### 12. Configurable Timezone (Medium)
**Change**: Move to `feeds.json` config
```python
# In feeds.json:
{
    "settings": {
        "timezone_offset_hours": 9,
        "max_entries_per_category": 1000
    },
    "tech": { "feeds": {...} }
}

# In code:
with open(FEEDS_FILE_NAME, 'r') as fp:
    config = json.load(fp)
    
tz_hours = config.get('settings', {}).get('timezone_offset_hours', 0)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_hours))
```

### 13. Feed Health Monitoring (Low)
**Change**: Track failure counts per feed
```python
# Add to output JSON:
"feed_health": {
    url: {
        "consecutive_failures": 0,
        "last_success": timestamp,
        "last_error": error_msg
    }
}
```

### 14. Config Validation (Low)
**Change**: Use `jsonschema` library
```python
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        "^[a-z_]+$": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {
                        "^.+$": {"type": "string", "format": "uri"}
                    }
                },
                "show_author": {"type": "boolean"}
            }
        }
    }
}

jsonschema.validate(user_config, FEEDS_SCHEMA)
```

### 15. Concurrent Processing (Low)
**Change**: Use `concurrent.futures`
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def do(target_category=None, log=False, max_workers=5):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                get_feed_from_rss, cat, d["feeds"], 
                d.get("show_author", False), log
            ): cat
            for cat, d in RSS.items()
        }
        
        for future in as_completed(futures):
            category = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"Category {category} failed: {e}")
```

### 16. Proper Logging (Low)
**Change**: Replace print statements
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Replace sys.stdout.write with:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}: {e}")
```