# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds using the `feedparser` library from multiple sources organized by category.

2. **Feed Management**: 
   - Loads feed configurations from a JSON file (`feeds.json`)
   - Copies a bundled default feeds file if user's file doesn't exist
   - Merges new categories from bundled feeds into existing user configurations

3. **Data Extraction**: Extracts key feed entry data including:
   - Publication/update timestamps
   - Article titles and URLs
   - Source/author names
   - Converts timestamps to local timezone (KST/UTC+9)

4. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries from the same feed.

5. **Output Formatting**:
   - Formats dates as "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
   - Sorts entries by timestamp (newest first)
   - Saves processed feeds as JSON files (`rss_{category}.json`)

6. **Flexible Execution**: Can process all categories or a single target category with optional logging.

7. **Directory Management**: Automatically creates data directory (`~/.rreader/`) if it doesn't exist.

## Triage

### Critical Gaps

1. **No Error Recovery**: The system exits on first feed failure, leaving remaining feeds unprocessed
2. **No Configuration Validation**: Missing validation for feeds.json structure and required fields
3. **Duplicate ID Collision**: Using timestamp as ID causes collisions when multiple articles publish simultaneously

### High Priority Gaps

4. **No Rate Limiting**: Could overwhelm servers or get IP-banned when fetching many feeds
5. **No Caching/Conditional Requests**: Re-downloads entire feeds every time, wasting bandwidth
6. **No Network Timeout Configuration**: Feeds can hang indefinitely on slow/broken servers
7. **No Logging Infrastructure**: Uses bare print statements instead of proper logging framework

### Medium Priority Gaps

8. **No Feed Health Monitoring**: Doesn't track which feeds consistently fail or are stale
9. **No Data Retention Policy**: JSON files grow unbounded, no pruning of old entries
10. **No Concurrency**: Processes feeds sequentially, making it slow for many feeds
11. **Hard-coded Timezone**: TIMEZONE is fixed to KST instead of being configurable
12. **No Content Sanitization**: Feed titles/content not sanitized for malicious HTML/scripts

### Low Priority Gaps

13. **No CLI Interface**: Limited command-line options for users
14. **No Progress Indicators**: Users don't know how many feeds remain when logging is disabled
15. **No Feed Metadata**: Doesn't store feed-level info (description, update frequency, last-modified headers)
16. **Minimal Documentation**: No docstrings or inline comments explaining logic

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Wrap individual feed parsing in try-except blocks
- Continue processing remaining feeds after failures
- Collect and report all errors at the end
```python
failed_feeds = []
for source, url in urls.items():
    try:
        # existing parsing code
    except Exception as e:
        failed_feeds.append((source, url, str(e)))
        continue  # Don't exit, process next feed
# After loop, log all failures
```

### 2. Configuration Validation (Critical)
**Changes needed:**
- Add validation function at startup
- Check feeds.json has expected structure: `{category: {feeds: {name: url}, show_author: bool}}`
- Validate URLs are well-formed
- Provide clear error messages
```python
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    for cat, data in config.items():
        if "feeds" not in data or not isinstance(data["feeds"], dict):
            raise ValueError(f"Category {cat} missing 'feeds' dict")
        # validate URLs, etc.
```

### 3. Fix Duplicate ID Collision (Critical)
**Changes needed:**
- Use compound key: `f"{ts}_{source}_{hash(feed.link)[:8]}"`
- Or use feed.id if available, fallback to compound key
```python
feed_id = getattr(feed, 'id', None) or f"{ts}_{source}_{hash(feed.link) % 1000000}"
entries["id"] = feed_id
rslt[feed_id] = entries  # Now truly unique
```

### 4. Rate Limiting (High)
**Changes needed:**
- Add configurable delay between feed requests
- Use `time.sleep()` between fetches
```python
import time
FETCH_DELAY = 0.5  # seconds, make configurable
for source, url in urls.items():
    # fetch and parse
    time.sleep(FETCH_DELAY)
```

### 5. Caching/Conditional Requests (High)
**Changes needed:**
- Store ETag and Last-Modified headers from responses
- Pass them in subsequent requests via feedparser's `etag` and `modified` parameters
```python
# Load cached headers
cache = load_feed_cache(category, source)
d = feedparser.parse(url, etag=cache.get('etag'), modified=cache.get('modified'))
if d.status == 304:  # Not modified
    continue
# Save new headers
save_feed_cache(category, source, {'etag': d.etag, 'modified': d.modified})
```

### 6. Network Timeout Configuration (High)
**Changes needed:**
- Set socket timeout globally or per-request
```python
import socket
socket.setdefaulttimeout(30)  # 30 second timeout
# Or configure feedparser's timeout if supported
```

### 7. Proper Logging (High)
**Changes needed:**
- Replace print statements with logging module
- Add configurable log levels
```python
import logging
logger = logging.getLogger(__name__)

def do(target_category=None, log_level=logging.INFO):
    logging.basicConfig(level=log_level)
    logger.info(f"Fetching {url}")
    logger.error(f"Failed to fetch {url}: {e}")
```

### 8. Feed Health Monitoring (Medium)
**Changes needed:**
- Track consecutive failures per feed in metadata file
- Flag feeds with >N consecutive failures
- Report health stats
```python
# In metadata file: {source: {consecutive_failures: 0, last_success: timestamp}}
if fetch_failed:
    health[source]['consecutive_failures'] += 1
else:
    health[source] = {'consecutive_failures': 0, 'last_success': time.time()}
```

### 9. Data Retention Policy (Medium)
**Changes needed:**
- Add MAX_ENTRIES or MAX_AGE configuration
- Prune old entries before saving
```python
MAX_ENTRY_AGE_DAYS = 30
cutoff = time.time() - (MAX_ENTRY_AGE_DAYS * 86400)
rslt = [val for val in rslt if val['timestamp'] > cutoff]
```

### 10. Concurrency (Medium)
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetching
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_feed, src, url): src for src, url in urls.items()}
    for future in as_completed(futures):
        # process results
```

### 11. Configurable Timezone (Medium)
**Changes needed:**
- Move TIMEZONE to user configuration
- Detect system timezone as default
```python
# In config.py
import datetime
try:
    from zoneinfo import ZoneInfo
    TIMEZONE = ZoneInfo("Asia/Seoul")  # or from config file
except ImportError:
    TIMEZONE = datetime.timezone(datetime.timedelta(hours=9))
```

### 12. Content Sanitization (Medium)
**Changes needed:**
- Use `html.escape()` or `bleach` library to sanitize titles
```python
import html
entries["title"] = html.escape(feed.title)
```

### 13. CLI Interface (Low)
**Changes needed:**
- Add argparse for command-line options
```python
import argparse
parser = argparse.ArgumentParser(description="RSS Feed Reader")
parser.add_argument('--category', help='Specific category to fetch')
parser.add_argument('--verbose', action='store_true')
args = parser.parse_args()
do(target_category=args.category, log=args.verbose)
```

### 14. Progress Indicators (Low)
**Changes needed:**
- Add progress counter or use tqdm library
```python
from tqdm import tqdm
for source, url in tqdm(urls.items(), desc=f"Fetching {category}"):
    # fetch code
```

### 15. Feed Metadata Storage (Low)
**Changes needed:**
- Store feed-level info in separate metadata file
- Include feed description, website, icon URL
```python
feed_metadata = {
    'title': d.feed.get('title'),
    'description': d.feed.get('description'),
    'link': d.feed.get('link'),
    'last_fetched': time.time()
}
```

### 16. Documentation (Low)
**Changes needed:**
- Add module, class, and function docstrings
- Add inline comments for complex logic
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    """
    Fetch and parse RSS feeds for a category.
    
    Args:
        category: Category name for organizing feeds
        urls: Dict mapping source names to feed URLs
        show_author: Use feed author instead of source name
        log: Print progress messages
        
    Returns:
        Dict with 'entries' list and 'created_at' timestamp
    """
```