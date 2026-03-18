# Diagnostic Report: RSS Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, each with multiple source URLs defined in a `feeds.json` configuration file.

3. **Feed Data Extraction**: Extracts key metadata from each feed entry:
   - Publication/update timestamps
   - Article titles and URLs
   - Source/author names
   - Formatted publication dates

4. **Timezone Handling**: Converts UTC timestamps to a configured timezone (hardcoded to KST/UTC+9) and formats display times intelligently (showing "HH:MM" for today's items, "MMM DD, HH:MM" for older items).

5. **Data Persistence**: Saves parsed feed data as JSON files in a data directory (`~/.rreader/`), one file per category (`rss_{category}.json`).

6. **Configuration Management**: 
   - Copies bundled default feeds if none exist
   - Merges new categories from bundled feeds into existing user configuration
   - Preserves user customizations

7. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries within a single fetch operation.

8. **Sorted Output**: Returns entries sorted by timestamp in reverse chronological order (newest first).

## Triage

### Critical Gaps
1. **No Error Recovery**: Failed feeds cause complete program termination (`sys.exit(0)`), preventing other feeds from being processed.
2. **No Feed Validation**: Missing required fields cause silent failures or exceptions that aren't handled.
3. **No Rate Limiting**: Could trigger rate limits or bans from feed providers when fetching many feeds.

### High Priority Gaps
4. **No Stale Data Handling**: No cache expiration or refresh logic; old data persists indefinitely.
5. **No Logging Framework**: Uses print statements; no structured logging for debugging production issues.
6. **Hardcoded Timezone**: Configuration is in code rather than user-configurable settings.
7. **No Feed Health Monitoring**: No tracking of which feeds consistently fail or return no data.

### Medium Priority Gaps
8. **No Concurrency**: Feeds are fetched sequentially, causing slow updates with many sources.
9. **No User Feedback**: No progress indicators or summaries (e.g., "fetched 42 articles from 5 sources").
10. **No Data Validation**: Malformed URLs or corrupted JSON files could crash the system.
11. **Duplicate ID Collisions**: Using Unix timestamp as ID means articles published in the same second collide.

### Low Priority Gaps
12. **No Content Preview**: Doesn't extract article summaries/descriptions that RSS feeds often provide.
13. **No Read/Unread Tracking**: No way to mark articles as read or filter them.
14. **No Search/Filter Capability**: Cannot search articles by keyword or filter by date range.
15. **No Feed Discovery**: No mechanism to suggest or auto-discover related feeds.

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Replace `sys.exit(0)` with logging and continuation logic
- Wrap `feedparser.parse()` in try-except that logs errors but continues
- Add a summary section tracking successful/failed feeds
```python
failed_feeds = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        if d.bozo:  # feedparser's error flag
            failed_feeds.append((source, d.bozo_exception))
            continue
    except Exception as e:
        failed_feeds.append((source, str(e)))
        continue
```

### 2. Feed Entry Validation (Critical)
**Changes needed:**
- Add validation function for required fields before processing
- Provide default values for missing optional fields
- Log entries that fail validation
```python
def validate_entry(feed, source):
    if not hasattr(feed, 'link') or not feed.link:
        return None
    if not hasattr(feed, 'title') or not feed.title:
        return None
    return {
        'parsed_time': getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None),
        'author': getattr(feed, 'author', source),
        # ... other fields
    }
```

### 3. Rate Limiting (Critical)
**Changes needed:**
- Add configurable delays between feed fetches
- Implement exponential backoff for failed requests
- Add a `time.sleep()` between iterations
```python
import time
from config import FETCH_DELAY_SECONDS  # default: 1

for source, url in urls.items():
    # ... fetch logic ...
    time.sleep(FETCH_DELAY_SECONDS)
```

### 4. Stale Data Handling (High Priority)
**Changes needed:**
- Add `max_age` parameter to configuration
- Check `created_at` timestamp before returning cached data
- Re-fetch if data exceeds max age
```python
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        cached = json.load(f)
        if time.time() - cached.get('created_at', 0) < MAX_CACHE_AGE:
            return cached
```

### 5. Structured Logging (High Priority)
**Changes needed:**
- Replace print statements with `logging` module
- Add configurable log levels and file output
- Include contextual information (category, source, URL)
```python
import logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                   handlers=[logging.FileHandler('rreader.log'), logging.StreamHandler()])
logger = logging.getLogger(__name__)
logger.info(f"Fetching {url} for category {category}")
```

### 6. Configurable Timezone (High Priority)
**Changes needed:**
- Move TIMEZONE to `feeds.json` or separate config file
- Add timezone validation and fallback to UTC
```python
# In config.py
import pytz
def get_timezone():
    config_tz = os.getenv('RREADER_TIMEZONE', 'UTC')
    return pytz.timezone(config_tz)
```

### 7. Feed Health Monitoring (High Priority)
**Changes needed:**
- Track fetch attempts, successes, failures per feed
- Store metrics in separate JSON file
- Expose API to query unhealthy feeds
```python
# Store in feed_health.json
{
    "https://example.com/feed": {
        "last_success": 1234567890,
        "last_failure": null,
        "failure_count": 0,
        "total_fetches": 42
    }
}
```

### 8. Concurrent Fetching (Medium Priority)
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetches
- Add configurable worker pool size
- Maintain thread-safe result collection
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # ... existing logic per feed ...
    
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        result = future.result()
```

### 9. User Feedback (Medium Priority)
**Changes needed:**
- Return fetch statistics from `get_feed_from_rss()`
- Print summary after completion
```python
stats = {"total_sources": len(urls), "successful": 0, "failed": 0, "articles": 0}
# ... after processing ...
print(f"Fetched {stats['articles']} articles from {stats['successful']}/{stats['total_sources']} sources")
```

### 10. Data Validation (Medium Priority)
**Changes needed:**
- Validate URLs before fetching (regex or urllib.parse)
- Add JSON schema validation for config files
- Handle file I/O errors gracefully
```python
from urllib.parse import urlparse

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False
```

### 11. Fix Duplicate ID Collisions (Medium Priority)
**Changes needed:**
- Change ID from timestamp to hash of (timestamp + URL)
- Or use UUID generation
```python
import hashlib
entry_id = hashlib.md5(f"{ts}{feed.link}".encode()).hexdigest()
```

### 12-15. Feature Additions (Low Priority)
**Changes needed for each:**
- **Content Preview**: Extract `feed.summary` or `feed.description` in entry data
- **Read/Unread Tracking**: Add `read_articles.json` with article IDs and timestamps
- **Search/Filter**: Add query functions that filter the JSON data by criteria
- **Feed Discovery**: Integrate with OPML import or feed suggestion APIs