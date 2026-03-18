# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-Source Aggregation**: Supports organizing feeds into categories, with multiple sources per category
3. **Data Persistence**: Stores parsed feed data as JSON files in a user directory (`~/.rreader/`)
4. **Time Handling**: Converts feed timestamps to a configured timezone (currently KST/UTC+9)
5. **Deduplication**: Uses timestamp-based keys to prevent duplicate entries from the same feed
6. **Feed Configuration Management**: 
   - Stores feed URLs in a `feeds.json` configuration file
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled feeds into existing user configuration
7. **Flexible Author Display**: Supports per-category toggle for showing feed author vs. source name
8. **Sorting**: Chronologically sorts entries (newest first) across all sources in a category
9. **Date Formatting**: Displays relative dates (time-only for today, month/day/time for older)
10. **Selective Updates**: Can update a single category or all categories

## Triage

### Critical Gaps (Production Blockers)

1. **No Error Recovery** - Single feed failure crashes entire category update
2. **No Concurrent Fetching** - Sequential fetches are slow for many feeds
3. **No Rate Limiting** - Risk of being blocked by feed providers
4. **No Data Validation** - Malformed feeds or JSON can crash the system
5. **No Logging Infrastructure** - Optional stdout logging is insufficient for debugging

### High Priority (User Experience)

6. **No Caching/Conditional Requests** - Downloads full feeds every time (wasteful)
7. **No Feed Health Monitoring** - Silent failures leave stale data
8. **No Retry Logic** - Transient network errors cause permanent failures
9. **No User Feedback** - No progress indication for long-running operations
10. **No Content Storage** - Only stores metadata, not article content/summaries

### Medium Priority (Robustness)

11. **Hardcoded Timezone** - Should be configurable per-user
12. **No Feed Validation** - Accepts any URL without checking if it's valid RSS
13. **No Entry Limits** - Unbounded growth of JSON files
14. **Collision-Prone IDs** - Unix timestamp allows collisions for rapid posts
15. **No Backup/Migration** - Data loss risk during updates

### Low Priority (Polish)

16. **No Feed Metadata** - Doesn't store feed title, description, icon
17. **No Entry Content** - Loses summary/description from feeds
18. **No Read/Unread Tracking** - Can't mark entries as read
19. **No Search/Filter** - No way to query historical data
20. **No CLI Interface** - Must be imported as module

## Plan

### 1. Error Recovery (Critical)
**Change**: Wrap individual feed fetches in try-except blocks within the loop.
```python
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        # ... process entries ...
    except Exception as e:
        print(f"Failed to fetch {source}: {e}")
        continue  # Don't crash, move to next feed
```
Store failed feeds in the output JSON with error details so the UI can display warnings.

### 2. Concurrent Fetching (Critical)
**Change**: Use `concurrent.futures.ThreadPoolExecutor` to fetch feeds in parallel.
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    return source, feedparser.parse(url)

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source, parsed = future.result()
        # ... process entries ...
```

### 3. Rate Limiting (Critical)
**Change**: Add delays between requests to the same domain.
```python
from urllib.parse import urlparse
import time

last_request_time = {}
MIN_DELAY = 1.0  # seconds between requests to same domain

def rate_limited_fetch(url):
    domain = urlparse(url).netloc
    if domain in last_request_time:
        elapsed = time.time() - last_request_time[domain]
        if elapsed < MIN_DELAY:
            time.sleep(MIN_DELAY - elapsed)
    
    result = feedparser.parse(url)
    last_request_time[domain] = time.time()
    return result
```

### 4. Data Validation (Critical)
**Change**: Validate feed structure and handle missing fields gracefully.
```python
def safe_get_entries(parsed_feed):
    if not hasattr(parsed_feed, 'entries'):
        raise ValueError("Invalid feed: no entries")
    if parsed_feed.bozo and parsed_feed.bozo_exception:
        # Log warning but try to continue
        pass
    return parsed_feed.entries

def safe_get_time(entry):
    for attr in ['published_parsed', 'updated_parsed', 'created_parsed']:
        if hasattr(entry, attr):
            parsed = getattr(entry, attr)
            if parsed and len(parsed) >= 6:
                return parsed
    return None
```

### 5. Logging Infrastructure (Critical)
**Change**: Replace print statements with proper logging.
```python
import logging

logger = logging.getLogger('rreader')
handler = logging.FileHandler(os.path.join(p['path_data'], 'rreader.log'))
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage:
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse feed {source}: {e}")
```

### 6. Caching/Conditional Requests (High)
**Change**: Store and use ETag/Last-Modified headers.
```python
# Store in a separate cache file per category
cache = {
    'source_name': {
        'etag': 'abc123',
        'modified': 'Thu, 01 Jan 2024 00:00:00 GMT',
        'last_fetch': 1234567890
    }
}

d = feedparser.parse(url, 
                     etag=cache.get(source, {}).get('etag'),
                     modified=cache.get(source, {}).get('modified'))

if d.status == 304:  # Not modified
    # Use cached data
    continue

# Update cache with new etag/modified
cache[source] = {
    'etag': d.get('etag'),
    'modified': d.get('modified'),
    'last_fetch': int(time.time())
}
```

### 7. Feed Health Monitoring (High)
**Change**: Track fetch success/failure history.
```python
# Add to output JSON:
{
    "entries": [...],
    "created_at": 1234567890,
    "feed_status": {
        "source_name": {
            "last_success": 1234567890,
            "last_failure": null,
            "consecutive_failures": 0,
            "last_error": null
        }
    }
}
```

### 8. Retry Logic (High)
**Change**: Implement exponential backoff for failed requests.
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), 
       wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_with_retry(url):
    return feedparser.parse(url)
```

### 9. User Feedback (High)
**Change**: Add progress callback mechanism.
```python
def get_feed_from_rss(category, urls, show_author=False, 
                      progress_callback=None):
    total = len(urls)
    for i, (source, url) in enumerate(urls.items(), 1):
        if progress_callback:
            progress_callback(i, total, source)
        # ... fetch and process ...
```

### 10. Content Storage (High)
**Change**: Store entry summary/content in the JSON output.
```python
entries = {
    # ... existing fields ...
    "summary": getattr(feed, 'summary', '')[:500],  # Truncate
    "content": getattr(feed, 'content', [{}])[0].get('value', '')[:1000]
}
```

### 11. Configurable Timezone (Medium)
**Change**: Move timezone to user-editable config file.
```python
# In config.py, load from JSON:
config_file = os.path.join(p['path_data'], 'config.json')
if os.path.exists(config_file):
    with open(config_file) as f:
        config = json.load(f)
        tz_offset = config.get('timezone_offset', 9)
else:
    tz_offset = 9

TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```

### 12. Feed Validation (Medium)
**Change**: Validate feeds before adding to configuration.
```python
def validate_feed(url):
    try:
        d = feedparser.parse(url)
        if not d.entries:
            return False, "No entries found"
        if d.bozo and isinstance(d.bozo_exception, 
                                xml.sax.SAXParseException):
            return False, f"Invalid XML: {d.bozo_exception}"
        return True, None
    except Exception as e:
        return False, str(e)
```

### 13. Entry Limits (Medium)
**Change**: Implement rolling window of entries.
```python
MAX_ENTRIES_PER_CATEGORY = 1000
MAX_AGE_DAYS = 30

# After sorting:
cutoff_time = int(time.time()) - (MAX_AGE_DAYS * 86400)
rslt = [e for e in rslt if e['timestamp'] > cutoff_time]
rslt = rslt[:MAX_ENTRIES_PER_CATEGORY]
```

### 14. Better Entry IDs (Medium)
**Change**: Generate unique IDs combining timestamp and hash.
```python
import hashlib

entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
```

### 15. Backup/Migration (Medium)
**Change**: Implement atomic writes and backups.
```python
def safe_write_json(filepath, data):
    temp_file = filepath + '.tmp'
    backup_file = filepath + '.bak'
    
    # Write to temp file
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)
    
    # Backup existing file
    if os.path.exists(filepath):
        shutil.copy2(filepath, backup_file)
    
    # Atomic rename
    os.replace(temp_file, filepath)
```

### 16-20. Lower Priority Items
These would follow similar patterns:
- **Metadata**: Extend entries dict with feed-level fields
- **Content**: Already covered in #10
- **Read tracking**: Add `read: false` field and persistence mechanism
- **Search**: Create inverted index in separate JSON file
- **CLI**: Add `if __name__ == '__main__'` argparse interface