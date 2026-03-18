# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-category Support**: Organizes feeds into categories, each with multiple sources
3. **Feed Configuration Management**: 
   - Maintains a `feeds.json` configuration file in `~/.rreader/`
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled feeds into existing user configuration
4. **Data Persistence**: Saves parsed feed entries as JSON files (`rss_{category}.json`) in the data directory
5. **Timezone Handling**: Converts UTC timestamps to KST (UTC+9) timezone
6. **Smart Date Formatting**: Shows time-only for today's entries, full date for older entries
7. **Deduplication**: Uses timestamp as ID to avoid duplicate entries from the same time
8. **Author/Source Display**: Configurable per-category author display (source name vs. feed author)
9. **Sorting**: Entries sorted by timestamp in reverse chronological order
10. **Selective Updates**: Can update a single category or all categories
11. **Optional Logging**: Progress output controlled by `log` parameter

## Triage

### Critical Gaps
1. **No Error Recovery** - Single feed failure kills entire category processing
2. **Missing Input Validation** - No validation of feed configuration structure or URL formats
3. **ID Collision Risk** - Using timestamp as ID causes overwrites when multiple entries share the same second

### High Priority
4. **No Rate Limiting** - Could hammer servers or get blocked when updating many feeds
5. **No Cache/Conditional Requests** - Refetches entire feeds every time (bandwidth waste, server burden)
6. **Silent Failures** - Bare `except:` blocks mask all errors
7. **No Timeout Configuration** - Feed requests can hang indefinitely
8. **Missing Logging Infrastructure** - Only has print statements, no proper logging levels

### Medium Priority
9. **No Content Sanitization** - Feed titles/content not sanitized (potential XSS if displayed in web UI)
10. **No Feed Validation** - Doesn't verify feeds are actually valid RSS/Atom before processing
11. **Hardcoded Timezone** - KST is hardcoded, not user-configurable
12. **No Entry Limit** - Could create massive JSON files from high-volume feeds
13. **No Stale Data Handling** - Old cached feeds never expire or get flagged as stale

### Low Priority
14. **No Concurrent Fetching** - Sequential processing is slow for many feeds
15. **No Feed Metadata** - Doesn't store feed description, icon, or update frequency
16. **No Statistics** - No tracking of update success rates or fetch times
17. **No CLI Interface** - Can't easily update specific categories from command line

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Wrap individual feed fetches in try-except blocks
- Continue processing remaining feeds if one fails
- Collect and report errors at the end
```python
failed_feeds = []
for source, url in urls.items():
    try:
        # ... fetch and parse ...
    except Exception as e:
        failed_feeds.append((source, url, str(e)))
        continue  # Don't exit, continue to next feed
```

### 2. Input Validation (Critical)
**Changes needed:**
- Add JSON schema validation for `feeds.json` structure
- Validate URLs before attempting to fetch
- Add function at startup:
```python
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    for category, data in config.items():
        if 'feeds' not in data or not isinstance(data['feeds'], dict):
            raise ValueError(f"Category {category} missing 'feeds' dict")
        for source, url in data['feeds'].items():
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL for {source}: {url}")
```

### 3. Fix ID Collision (Critical)
**Changes needed:**
- Use composite key: timestamp + hash of URL or title
- Modify entry creation:
```python
import hashlib
unique_str = f"{ts}_{feed.link}_{feed.title}"
entry_id = f"{ts}_{hashlib.md5(unique_str.encode()).hexdigest()[:8]}"
entries["id"] = entry_id
```

### 4. Rate Limiting (High Priority)
**Changes needed:**
- Add delays between requests
- Make configurable per-category:
```python
import time
# In feeds.json: "request_delay": 1.0
delay = d.get("request_delay", 0.5)
for source, url in urls.items():
    # ... fetch feed ...
    time.sleep(delay)
```

### 5. Implement HTTP Caching (High Priority)
**Changes needed:**
- Store ETag and Last-Modified headers
- Send conditional requests:
```python
# Store in rss_{category}_meta.json
cache_meta = load_cache_meta(category, source)
headers = {}
if cache_meta.get('etag'):
    headers['If-None-Match'] = cache_meta['etag']
if cache_meta.get('last_modified'):
    headers['If-Modified-Since'] = cache_meta['last_modified']
    
d = feedparser.parse(url, request_headers=headers)
if d.status == 304:  # Not Modified
    continue  # Use cached data
```

### 6. Proper Error Handling (High Priority)
**Changes needed:**
- Replace bare `except:` with specific exceptions
- Log errors with context:
```python
import logging
try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser error flag
        logging.warning(f"Feed {url} has issues: {d.bozo_exception}")
except (urllib.error.URLError, socket.timeout) as e:
    logging.error(f"Network error fetching {url}: {e}")
except Exception as e:
    logging.error(f"Unexpected error processing {url}: {e}", exc_info=True)
```

### 7. Add Timeout Configuration (High Priority)
**Changes needed:**
- Configure feedparser timeout:
```python
# Add to config.py
FEED_TIMEOUT = 30  # seconds

# In do():
import socket
socket.setdefaulttimeout(FEED_TIMEOUT)
```

### 8. Implement Proper Logging (High Priority)
**Changes needed:**
- Replace print statements with logging module:
```python
import logging
logging.basicConfig(
    level=logging.INFO if log else logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Replace sys.stdout.write with:
logger.info(f"Fetching {url}")
```

### 9. Content Sanitization (Medium Priority)
**Changes needed:**
- Add HTML sanitization library (bleach)
- Clean titles before storing:
```python
import bleach
entries["title"] = bleach.clean(
    feed.title, 
    tags=[], 
    strip=True
)
```

### 10. Feed Validation (Medium Priority)
**Changes needed:**
- Check feedparser's bozo flag and feed type:
```python
d = feedparser.parse(url)
if d.bozo and isinstance(d.bozo_exception, feedparser.NonXMLContentType):
    logger.error(f"{url} is not a valid feed")
    continue
if not d.entries:
    logger.warning(f"{url} has no entries")
```

### 11. Configurable Timezone (Medium Priority)
**Changes needed:**
- Move timezone to feeds.json:
```python
# In feeds.json root: "timezone_offset": 9
# In config.py:
def get_timezone():
    with open(FEEDS_FILE_NAME) as f:
        config = json.load(f)
    offset = config.get('timezone_offset', 0)
    return datetime.timezone(datetime.timedelta(hours=offset))
```

### 12. Entry Limits (Medium Priority)
**Changes needed:**
- Add max_entries configuration:
```python
# In feeds.json: "max_entries": 100
max_entries = d.get("max_entries", 100)
rslt = [val for key, val in sorted(rslt.items(), reverse=True)][:max_entries]
```

### 13. Stale Data Handling (Medium Priority)
**Changes needed:**
- Add metadata to JSON output with update time
- Check age on read and warn if stale:
```python
MAX_AGE = 3600  # 1 hour
if rslt.get("created_at", 0) < time.time() - MAX_AGE:
    rslt["stale"] = True
```

### 14. Concurrent Fetching (Low Priority)
**Changes needed:**
- Use ThreadPoolExecutor for parallel fetches:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # ... existing fetch logic ...
    return source, result

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source, result = future.result()
        # ... process result ...
```

### 15. Feed Metadata Storage (Low Priority)
**Changes needed:**
- Extract and store feed-level info:
```python
feed_meta = {
    "title": d.feed.get("title", source),
    "description": d.feed.get("description", ""),
    "link": d.feed.get("link", ""),
    "icon": d.feed.get("icon", "")
}
# Store in separate metadata file
```

### 16. Statistics Tracking (Low Priority)
**Changes needed:**
- Create stats.json with per-feed metrics:
```python
stats = {
    "last_success": timestamp,
    "last_failure": timestamp,
    "fetch_time_ms": duration,
    "entry_count": len(entries),
    "consecutive_failures": 0
}
```

### 17. CLI Interface (Low Priority)
**Changes needed:**
- Add argparse for command-line options:
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--category', help='Update specific category')
parser.add_argument('--verbose', '-v', action='store_true')
parser.add_argument('--list', action='store_true', help='List categories')
args = parser.parse_args()
```