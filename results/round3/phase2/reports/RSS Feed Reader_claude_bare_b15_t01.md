# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, each with their own set of source URLs and configuration options.

3. **Feed Management**: 
   - Reads feed sources from a JSON configuration file (`feeds.json`)
   - Automatically copies bundled default feeds if user config doesn't exist
   - Merges new categories from bundled feeds into existing user configurations

4. **Entry Normalization**: Extracts and standardizes feed entries with:
   - Unique ID based on publication timestamp
   - Source name (with optional author display)
   - Publication date in human-readable format
   - Unix timestamp for sorting
   - URL and title

5. **Timezone Handling**: Converts all timestamps to KST (UTC+9) with smart date formatting (shows time-only for today, includes date otherwise).

6. **Duplicate Handling**: Uses timestamp as key to deduplicate entries from the same source.

7. **Data Persistence**: Saves parsed feeds to JSON files (`rss_{category}.json`) in `~/.rreader/` directory.

8. **Selective Updates**: Can update a specific category or all categories via the `target_category` parameter.

9. **Optional Logging**: Provides progress output during feed fetching when `log=True`.

## Triage

### Critical Gaps

1. **No Error Recovery**: Failed feed fetches call `sys.exit()`, terminating the entire program instead of continuing with other feeds.

2. **No Retry Logic**: Network failures or temporary unavailability immediately fail without retry attempts.

3. **Missing Feed Configuration**: The actual `feeds.json` structure is never defined in the code, making the system unusable without external documentation.

### High Priority Gaps

4. **No Caching/Rate Limiting**: Fetches all feeds every time without respecting HTTP caching headers (ETags, Last-Modified) or implementing reasonable rate limits.

5. **Silent Failures**: The try-except block around feed entry parsing silently skips malformed entries without logging what went wrong.

6. **No Data Validation**: Doesn't validate the structure of `feeds.json` or handle missing required fields gracefully.

7. **Duplicate ID Collisions**: Using only timestamp as ID means multiple entries published at the same second will overwrite each other.

### Medium Priority Gaps

8. **No Stale Data Management**: Old entries are never cleaned up, leading to unbounded file growth.

9. **No Feed Health Monitoring**: Doesn't track which feeds are consistently failing or haven't updated in a long time.

10. **Limited Date Handling**: Falls back to current time for feeds missing both `published_parsed` and `updated_parsed`, with no indication this happened.

11. **No Concurrency**: Fetches feeds sequentially, making updates slow for many feeds.

### Low Priority Gaps

12. **Hardcoded Timezone**: KST is hardcoded; should be user-configurable.

13. **No Content Extraction**: Only extracts title/link/date, missing description, content, and other potentially useful fields.

14. **No Feed Metadata**: Doesn't store feed-level information (last successful fetch, feed title, etc.).

## Plan

### 1. Error Recovery (Critical)

**Changes needed:**
- Replace `sys.exit()` in the exception handler with proper error logging
- Continue processing remaining feeds after individual failures
- Return or accumulate error information for user visibility

```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            d = feedparser.parse(url)
            if log:
                sys.stdout.write(" - Done\n")
        except Exception as e:
            error_msg = f"Failed to fetch {url}: {str(e)}"
            errors.append({"source": source, "url": url, "error": error_msg})
            if log:
                sys.stdout.write(f" - Failed: {str(e)}\n")
            continue  # Continue with next feed instead of exiting
```

### 2. Retry Logic (Critical)

**Changes needed:**
- Add retry decorator or loop with exponential backoff
- Make retry count configurable (default: 3 attempts)
- Add timeout parameter to feedparser.parse()

```python
import time
from functools import wraps

def retry_with_backoff(retries=3, backoff_in_seconds=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            x = 0
            while x < retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if x == retries - 1:
                        raise
                    sleep_time = backoff_in_seconds * (2 ** x)
                    time.sleep(sleep_time)
                    x += 1
        return wrapper
    return decorator

# Apply to feed fetching
@retry_with_backoff(retries=3)
def fetch_feed(url):
    return feedparser.parse(url, timeout=30)
```

### 3. Feed Configuration Template (Critical)

**Changes needed:**
- Create a `feeds.json` example file alongside the code
- Add JSON schema validation
- Document the expected structure in comments or README

```python
# Add to repository: feeds.json.example
{
    "tech": {
        "feeds": {
            "Hacker News": "https://news.ycombinator.com/rss",
            "TechCrunch": "https://techcrunch.com/feed/"
        },
        "show_author": false
    },
    "news": {
        "feeds": {
            "BBC": "http://feeds.bbci.co.uk/news/rss.xml"
        },
        "show_author": true
    }
}

# Add validation function
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("Feeds config must be a dictionary")
    for category, data in config.items():
        if "feeds" not in data or not isinstance(data["feeds"], dict):
            raise ValueError(f"Category '{category}' missing 'feeds' dict")
    return True
```

### 4. HTTP Caching (High Priority)

**Changes needed:**
- Store ETag and Last-Modified headers from previous fetches
- Send conditional requests with If-None-Match/If-Modified-Since
- Skip parsing when server returns 304 Not Modified

```python
def load_cache_metadata(category):
    cache_file = os.path.join(p["path_data"], f"rss_{category}_cache.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    return {}

def save_cache_metadata(category, metadata):
    cache_file = os.path.join(p["path_data"], f"rss_{category}_cache.json")
    with open(cache_file, 'w') as f:
        json.dump(metadata, f)

# Modify fetch to include headers
def fetch_feed_with_cache(url, etag=None, modified=None):
    headers = {}
    if etag:
        headers['If-None-Match'] = etag
    if modified:
        headers['If-Modified-Since'] = modified
    
    d = feedparser.parse(url, request_headers=headers)
    return d, d.get('etag'), d.get('modified')
```

### 5. Comprehensive Logging (High Priority)

**Changes needed:**
- Replace print statements with Python's `logging` module
- Add different log levels (DEBUG, INFO, WARNING, ERROR)
- Log skipped entries with reason
- Create log file in addition to console output

```python
import logging

def setup_logging(log_file=None):
    logger = logging.getLogger('rreader')
    logger.setLevel(logging.INFO)
    
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger

# Use throughout:
logger = setup_logging(os.path.join(p["path_data"], "rreader.log"))
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse entry: {e}")
logger.warning(f"Entry missing timestamp, skipping: {feed.get('title', 'Unknown')}")
```

### 6. Config Validation (High Priority)

**Changes needed:**
- Validate feeds.json structure on load
- Provide helpful error messages for malformed config
- Handle missing optional fields with defaults

```python
def load_and_validate_feeds():
    try:
        with open(FEEDS_FILE_NAME, "r") as fp:
            feeds = json.load(fp)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {FEEDS_FILE_NAME}: {e}")
    
    for category, config in feeds.items():
        if not isinstance(config, dict):
            raise ValueError(f"Category '{category}' must be a dictionary")
        if "feeds" not in config:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(config["feeds"], dict):
            raise ValueError(f"Category '{category}' feeds must be a dictionary")
        
        # Set defaults
        config.setdefault("show_author", False)
        config.setdefault("max_entries", 100)
    
    return feeds
```

### 7. Unique Entry IDs (High Priority)

**Changes needed:**
- Combine timestamp with URL hash or GUID from feed
- Use feed's GUID field if available
- Add sequence number for same-second collisions

```python
import hashlib

def generate_entry_id(feed, parsed_time):
    # Prefer feed's own ID/GUID
    if hasattr(feed, 'id') and feed.id:
        return hashlib.md5(feed.id.encode()).hexdigest()
    
    # Fallback to timestamp + URL hash
    ts = int(time.mktime(parsed_time))
    url_hash = hashlib.md5(feed.link.encode()).hexdigest()[:8]
    return f"{ts}_{url_hash}"
```

### 8. Data Cleanup (Medium Priority)

**Changes needed:**
- Add configurable retention period (e.g., 30 days)
- Remove entries older than retention period during save
- Add manual cleanup command

```python
def cleanup_old_entries(entries, max_age_days=30):
    cutoff_time = int(time.time()) - (max_age_days * 86400)
    return [e for e in entries if e.get("timestamp", 0) >= cutoff_time]

# In get_feed_from_rss before saving:
rslt["entries"] = cleanup_old_entries(rslt["entries"], max_age_days=30)
```

### 9. Feed Health Tracking (Medium Priority)

**Changes needed:**
- Store last successful fetch time per feed
- Track consecutive failure count
- Expose health status in separate file or API

```python
def update_feed_health(category, source, success, error=None):
    health_file = os.path.join(p["path_data"], "feed_health.json")
    
    if os.path.exists(health_file):
        with open(health_file, 'r') as f:
            health = json.load(f)
    else:
        health = {}
    
    if category not in health:
        health[category] = {}
    
    if source not in health[category]:
        health[category][source] = {
            "consecutive_failures": 0,
            "last_success": None,
            "last_failure": None
        }
    
    if success:
        health[category][source]["consecutive_failures"] = 0
        health[category][source]["last_success"] = int(time.time())
    else:
        health[category][source]["consecutive_failures"] += 1
        health[category][source]["last_failure"] = int(time.time())
        health[category][source]["last_error"] = error
    
    with open(health_file, 'w') as f:
        json.dump(health, f, indent=2)
```

### 10. Graceful Time Handling (Medium Priority)

**Changes needed:**
- Never silently use current time
- Mark entries with missing/invalid timestamps
- Log timestamp parsing failures

```python
try:
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        logger.warning(f"Entry missing timestamp: {feed.get('title', feed.link)}")
        # Use current time but mark it
        parsed_time = time.gmtime()
        is_estimated_time = True
    else:
        is_estimated_time = False
    # ... rest of processing
    entries["estimated_time"] = is_estimated_time
except Exception as e:
    logger.error(f"Failed to parse time for entry {feed.get('title')}: {e}")
    continue
```

### 11. Concurrent Fetching (Medium Priority)

**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetching
- Make worker count configurable
- Preserve error handling per feed

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url, timeout=30)
        if log:
            sys.stdout.write(" - Done\n")
        return source, d, None
    except Exception as e:
        return source, None, str(e)

def get_feed_from_rss(category, urls, show_author=False, log=False, max_workers=5):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_single_feed, src, url, log): src 
                   for src, url in urls.items()}
        
        for future in as_completed(futures):
            source, parsed, error = future.result()
            if error:
                logger.error(f"Failed to fetch {source}: {error}")
                continue
            # Process parsed feed entries...
```

### 12. Configurable Timezone (Low Priority)

**Changes needed:**
- Add timezone setting to config file
- Parse timezone string or offset
- Apply per-category or globally

```python
# In config or feeds.json
"timezone": "America/New_York"  # or "UTC+9" or "+09:00"

# Parse in config.py
import datetime
import re

def parse_timezone(tz_string):
    # Handle pytz timezone names
    try:
        import pytz
        return pytz.timezone(tz_string)
    except:
        pass
    
    # Handle UTC offsets like "UTC+9" or "+09:00"
    match = re.match(r'UTC?([+-]\d{1,2})(?::?(\d{2}))?', tz_string)
    if match:
        hours = int(match.group(1))
        minutes = int(match.group(2) or 0)
        return datetime.timezone(datetime.timedelta(hours=hours, minutes=minutes))
    
    raise ValueError(f"Invalid timezone: {tz_string}")
```

### 13. Enhanced Content Extraction (Low Priority)

**Changes needed:**
- Extract description/summary field
- Extract full content if available
- Store media attachments (enclosures)
- Add categories/tags

```python
entries = {
    "id": entry_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "description": getattr(feed, 'description', '') or getattr(feed, 'summary', ''),
    "content": getattr(feed, 'content', [{}])[0].get('value', '') if hasattr(feed, 'content') else '',
    "author": getattr(feed, 'author', ''),
    "categories": [tag.term for tag in getattr(feed, 'tags', [])],
    "enclosures": [{"url": e.href, "type": e.type} for e in getattr(feed, 'enclosures', [])]
}
```

### 14. Feed Metadata Storage (Low Priority)

**Changes needed:**
- Store feed-level information separate from entries
- Track feed title, description, update frequency
- Use for display and diagnostics

```python
def save_feed_metadata(category, feeds_data):
    metadata = {
        "category": category,
        "feeds": {}
    }
    
    for source, parsed_feed in feeds_data.items():
        if hasattr(parsed_feed, 'feed'):
            metadata["feeds"][source] = {
                "title": getattr(parsed_feed.feed, 'title', source),
                "description": getattr(parsed_feed.feed, 'subtitle', ''),
                "link": getattr(parsed_feed.feed, 'link', ''),
                "last_updated": int(time.time())
            }
    
    metadata_file = os.path.join(p["path_data"], f"rss_{category}_metadata.json")
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)
```