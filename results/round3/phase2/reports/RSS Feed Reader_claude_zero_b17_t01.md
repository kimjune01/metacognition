# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, with each category maintaining its own set of feed URLs.

3. **Feed Configuration Management**: 
   - Bundles default feeds in `feeds.json` alongside the code
   - Creates user-editable feeds in `~/.rreader/feeds.json`
   - Merges new categories from bundled config into user config automatically

4. **Timestamp Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9) and formats them relative to today's date.

5. **Data Persistence**: Saves parsed feeds as JSON files (`rss_{category}.json`) with entries sorted by timestamp (newest first).

6. **Duplicate Handling**: Uses timestamp as ID to deduplicate entries from multiple sources within a category.

7. **Flexible Author Display**: Supports per-category configuration to show either source name or original author.

8. **Selective Updates**: Can refresh all categories or target a specific category via the `target_category` parameter.

9. **Optional Logging**: Provides progress output when `log=True`.

## Triage

### Critical Gaps

1. **No Error Recovery**: The bare `except:` clause calls `sys.exit()` on any feedparser failure, killing the entire process instead of continuing with other feeds.

2. **ID Collision Problem**: Using timestamp as ID causes entries published in the same second to overwrite each other in the `rslt` dictionary.

3. **Missing Configuration Validation**: No validation that `feeds.json` has the expected structure or that required keys exist.

### High Priority Gaps

4. **No Staleness Detection**: No mechanism to detect or handle feeds that haven't updated, are unreachable, or contain stale cached data.

5. **No Rate Limiting**: Requests all feeds simultaneously without delays, risking IP bans or server overload.

6. **Incomplete Logging**: Inconsistent error messages (writes to stdout then exits with status 0, losing the message).

7. **No Data Expiration**: Old entries accumulate indefinitely in JSON files with no cleanup mechanism.

8. **Hardcoded Timezone**: Timezone is in `config.py` but not easily reconfigurable per-user.

### Medium Priority Gaps

9. **No Feed Metadata Preservation**: Loses useful RSS metadata like descriptions, categories, images, or enclosures.

10. **No Update Scheduling**: No built-in mechanism for periodic updates (cron job or internal scheduler).

11. **No Progress Feedback**: When processing many feeds without logging, users have no indication the system is working.

12. **Limited Date Formatting**: "Today" detection uses `datetime.date.today()` without timezone awareness, creating edge cases.

### Low Priority Gaps

13. **No HTTP Caching**: Doesn't use ETags or Last-Modified headers to avoid re-downloading unchanged feeds.

14. **No User Agent**: HTTP requests don't identify the client, which some servers reject.

15. **No Content Sanitization**: Doesn't sanitize HTML in titles or check for malicious content.

16. **No Configuration for Feed Limits**: No way to limit number of entries per feed or per category.

## Plan

### 1. Error Recovery (Critical)

**Change**: Replace bare `except:` with specific exception handling and continue processing.

```python
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
    except Exception as e:
        if log:
            sys.stderr.write(f" - Failed: {str(e)}\n")
        continue  # Skip this feed but continue with others
```

Also wrap the inner feed processing loop:
```python
for feed in d.entries:
    try:
        # ... existing processing ...
    except Exception as e:
        if log:
            sys.stderr.write(f"  - Skipping entry: {str(e)}\n")
        continue
```

### 2. ID Collision Fix (Critical)

**Change**: Create unique IDs by combining timestamp with a hash of the URL.

```python
import hashlib

# Replace:
entries = {
    "id": ts,
    # ...
}

# With:
entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
entries = {
    "id": entry_id,
    "timestamp": ts,  # Keep separate for sorting
    # ...
}

# Update dictionary key:
rslt[entry_id] = entries

# Update sorting to use timestamp:
rslt = [val for key, val in sorted(rslt.items(), key=lambda x: x[1]['timestamp'], reverse=True)]
```

### 3. Configuration Validation (Critical)

**Change**: Add validation function called after loading feeds.json.

```python
def validate_feeds_config(rss_dict):
    """Validate feeds.json structure."""
    if not isinstance(rss_dict, dict):
        raise ValueError("feeds.json must contain a JSON object")
    
    for category, content in rss_dict.items():
        if not isinstance(content, dict):
            raise ValueError(f"Category '{category}' must be an object")
        if "feeds" not in content:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(content["feeds"], dict):
            raise ValueError(f"Category '{category}' feeds must be an object")
        # Validate each URL
        for source, url in content["feeds"].items():
            if not isinstance(url, str) or not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL for {category}/{source}: {url}")

# Call after loading:
with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
validate_feeds_config(RSS)
```

### 4. Staleness Detection (High Priority)

**Change**: Add timestamp checking and feed health tracking.

```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    feed_health = {}  # Track feed status
    
    for source, url in urls.items():
        try:
            d = feedparser.parse(url)
            
            # Check for feed errors
            if hasattr(d, 'bozo') and d.bozo:
                feed_health[source] = {"status": "error", "message": str(d.bozo_exception)}
                if log:
                    sys.stderr.write(f" - Warning: {d.bozo_exception}\n")
            
            # Check if feed has entries
            if not d.entries:
                feed_health[source] = {"status": "empty", "message": "No entries"}
                if log:
                    sys.stderr.write(f" - Warning: No entries found\n")
                continue
                
            feed_health[source] = {"status": "ok", "entry_count": len(d.entries)}
            # ... rest of processing ...
```

Save health data:
```python
rslt = {
    "entries": rslt,
    "created_at": int(time.time()),
    "feed_health": feed_health
}
```

### 5. Rate Limiting (High Priority)

**Change**: Add configurable delay between feed requests.

```python
import time

def get_feed_from_rss(category, urls, show_author=False, log=False, delay=1.0):
    # Add delay parameter with 1 second default
    
    for idx, (source, url) in enumerate(urls.items()):
        if idx > 0:  # Don't delay before first request
            time.sleep(delay)
        
        # ... existing code ...
```

Add to config.py:
```python
FEED_REQUEST_DELAY = 1.0  # seconds between requests
```

### 6. Complete Logging (High Priority)

**Change**: Use proper logging module instead of print statements.

```python
import logging

def setup_logging(log_enabled):
    """Configure logging for feed updates."""
    logger = logging.getLogger('rreader')
    logger.setLevel(logging.INFO if log_enabled else logging.WARNING)
    
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logger.addHandler(handler)
    
    return logger

def do(target_category=None, log=False):
    logger = setup_logging(log)
    
    def get_feed_from_rss(category, urls, show_author=False):
        # Replace sys.stdout.write with:
        logger.info(f"Fetching {url}")
        logger.info(f"Successfully fetched {len(d.entries)} entries")
        # For errors:
        logger.error(f"Failed to fetch {url}: {str(e)}")
```

### 7. Data Expiration (High Priority)

**Change**: Add entry age limit and cleanup.

```python
# In config.py:
MAX_ENTRY_AGE_DAYS = 30  # Keep entries for 30 days

# In get_feed_from_rss, before saving:
def cleanup_old_entries(entries, max_age_days):
    """Remove entries older than max_age_days."""
    cutoff = int(time.time()) - (max_age_days * 86400)
    return [e for e in entries if e['timestamp'] >= cutoff]

rslt_list = [val for key, val in sorted(rslt.items(), key=lambda x: x[1]['timestamp'], reverse=True)]
rslt_list = cleanup_old_entries(rslt_list, MAX_ENTRY_AGE_DAYS)
```

### 8. Configurable Timezone (High Priority)

**Change**: Move timezone to user feeds.json with fallback.

```python
# In feeds.json structure, add root-level config:
{
    "_config": {
        "timezone_offset_hours": 9,
        "max_entry_age_days": 30
    },
    "category1": { ... }
}

# In do():
config = RSS.get("_config", {})
tz_offset = config.get("timezone_offset_hours", 9)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```

### 9. Preserve Feed Metadata (Medium Priority)

**Change**: Extend entries dictionary to include optional metadata.

```python
entries = {
    "id": entry_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "description": getattr(feed, 'summary', '')[:500],  # Truncate long descriptions
    "categories": getattr(feed, 'tags', []),
    "image": getattr(feed, 'media_thumbnail', [{}])[0].get('url') if hasattr(feed, 'media_thumbnail') else None,
}
```

### 10. Update Scheduling (Medium Priority)

**Change**: Add a scheduler module using `schedule` library or APScheduler.

```python
# New file: scheduler.py
import schedule
import time
from . import fetch

def run_scheduled_updates(interval_minutes=60):
    """Run feed updates on a schedule."""
    schedule.every(interval_minutes).minutes.do(fetch.do, log=True)
    
    print(f"Scheduler started. Updates every {interval_minutes} minutes.")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    run_scheduled_updates()
```

### 11. Progress Feedback (Medium Priority)

**Change**: Add progress bar for non-logged mode using `tqdm`.

```python
from tqdm import tqdm

def do(target_category=None, log=False):
    # ...
    categories_to_process = [target_category] if target_category else RSS.keys()
    
    for category in tqdm(categories_to_process, desc="Processing categories", disable=log):
        feeds = RSS[category]["feeds"]
        with tqdm(total=len(feeds), desc=f"  {category}", disable=log, leave=False) as pbar:
            # Pass pbar to get_feed_from_rss to update
```

### 12. Timezone-Aware Date Comparison (Medium Priority)

**Change**: Fix today detection to use timezone-aware comparison.

```python
# Replace:
pubDate = at.strftime(
    "%H:%M" if at.date() == datetime.date.today() else "%b %d, %H:%M"
)

# With:
now_in_tz = datetime.datetime.now(TIMEZONE)
is_today = at.date() == now_in_tz.date()
pubDate = at.strftime("%H:%M" if is_today else "%b %d, %H:%M")
```

### 13. HTTP Caching (Low Priority)

**Change**: Use feedparser's built-in ETag/Modified support.

```python
# Create cache directory
CACHE_DIR = os.path.join(p["path_data"], "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def get_feed_with_cache(url, source):
    """Fetch feed with HTTP caching support."""
    cache_file = os.path.join(CACHE_DIR, f"{hashlib.md5(url.encode()).hexdigest()}.json")
    
    cache_data = {}
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
    
    d = feedparser.parse(url, 
                        etag=cache_data.get('etag'),
                        modified=cache_data.get('modified'))
    
    # Save cache headers
    if hasattr(d, 'etag') or hasattr(d, 'modified'):
        with open(cache_file, 'w') as f:
            json.dump({
                'etag': getattr(d, 'etag', None),
                'modified': getattr(d, 'modified', None)
            }, f)
    
    return d
```

### 14. User Agent (Low Priority)

**Change**: Configure feedparser to send proper User-Agent header.

```python
# In config.py:
USER_AGENT = "rreader/1.0 (+https://github.com/yourproject/rreader)"

# In fetch.py:
import feedparser
feedparser.USER_AGENT = USER_AGENT
```

### 15. Content Sanitization (Low Priority)

**Change**: Use `bleach` or `html` library to sanitize titles.

```python
import html

# When processing feed:
entries = {
    # ...
    "title": html.unescape(feed.title).strip(),
    "description": html.unescape(getattr(feed, 'summary', '')[:500]).strip(),
}
```

### 16. Entry Limits (Low Priority)

**Change**: Add configuration for maximum entries per category.

```python
# In feeds.json per-category:
{
    "category1": {
        "feeds": { ... },
        "max_entries": 100,  # New option
        "show_author": false
    }
}

# Before saving:
max_entries = d.get("max_entries", 1000)  # Default 1000
rslt_list = rslt_list[:max_entries]
```