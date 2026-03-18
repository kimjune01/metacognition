# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` library to fetch and parse RSS/Atom feeds from multiple sources
2. **Multi-source Aggregation**: Processes multiple feed URLs organized by category
3. **Deduplication**: Uses timestamp as unique ID to prevent duplicate entries within a category
4. **Time Normalization**: Converts feed timestamps to a configured timezone (currently KST/UTC+9)
5. **Smart Date Formatting**: Shows time-only for today's entries, full date for older entries
6. **JSON Persistence**: Saves aggregated feeds to category-specific JSON files in `~/.rreader/`
7. **Configuration Management**: 
   - Copies bundled default `feeds.json` if user config doesn't exist
   - Merges new categories from bundled config into existing user config
8. **Flexible Execution**: Can process all categories or target a specific one
9. **Author Attribution**: Supports per-category flag to show feed author vs source name
10. **Sorted Output**: Orders entries by timestamp (newest first)

## Triage

### Critical Gaps (Production Blockers)
1. **Error Handling**: Bare `except` clauses swallow all errors; network failures exit entire program
2. **Security**: No SSL verification control, timeout settings, or URL validation
3. **Logging**: Only basic stdout messages; no proper logging framework

### High Priority (Reliability Issues)
4. **Duplicate ID Collisions**: Using only timestamp as ID causes collisions for simultaneous posts
5. **Feed Validation**: No validation of feed structure or required fields before processing
6. **Rate Limiting**: No delays between requests; could trigger rate limits or bans
7. **Stale Data Handling**: No expiration policy for old entries
8. **Configuration Validation**: feeds.json structure not validated; malformed config crashes system

### Medium Priority (Usability)
9. **Progress Indication**: Limited feedback during long operations
10. **Partial Failure Recovery**: One failed feed aborts entire category processing
11. **Caching**: Re-fetches all feeds every run; no ETag or Last-Modified support
12. **Timezone Configuration**: Hardcoded KST; should be configurable per user

### Low Priority (Nice-to-Have)
13. **Content Extraction**: Only saves title/link; no description or content preview
14. **Feed Health Monitoring**: No tracking of consistently failing feeds
15. **Concurrent Fetching**: Sequential processing; slow for many feeds
16. **CLI Interface**: No command-line arguments for filtering, limiting results, etc.

## Plan

### 1. Error Handling
**Changes needed:**
```python
# Replace bare except with specific exceptions
import requests.exceptions

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    failed_feeds = []
    
    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            d = feedparser.parse(url)
            
            # Check for parsing errors
            if d.bozo:
                raise feedparser.NonXMLContentType(f"Feed parsing error: {d.bozo_exception}")
                
            if log:
                sys.stdout.write(" - Done\n")
                
        except (requests.exceptions.RequestException, 
                feedparser.NonXMLContentType, 
                Exception) as e:
            error_msg = f"Failed to fetch {url}: {type(e).__name__}: {str(e)}"
            if log:
                sys.stdout.write(f" - {error_msg}\n")
            failed_feeds.append({'source': source, 'url': url, 'error': str(e)})
            continue  # Don't exit, process remaining feeds
            
    # Store failed feeds in result for monitoring
    if failed_feeds:
        rslt['_errors'] = failed_feeds
```

### 2. Security Enhancements
**Changes needed:**
```python
# Add at top of get_feed_from_rss
import urllib.parse

TIMEOUT = 30  # seconds
MAX_FEED_SIZE = 10 * 1024 * 1024  # 10MB

def validate_url(url):
    """Ensure URL is HTTP/HTTPS and properly formed"""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f"Invalid URL scheme: {parsed.scheme}")
    return url

# In parsing loop
url = validate_url(url)
d = feedparser.parse(url, timeout=TIMEOUT)
```

### 3. Logging Framework
**Changes needed:**
```python
import logging

# Setup at module level
logger = logging.getLogger('rreader')
handler = logging.FileHandler(os.path.join(p["path_data"], "rreader.log"))
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Replace all sys.stdout.write and log parameter usage
logger.info(f"Fetching feed: {url}")
logger.error(f"Failed to fetch {url}: {e}")
```

### 4. Duplicate ID Prevention
**Changes needed:**
```python
import hashlib

def generate_entry_id(feed, ts):
    """Generate unique ID from timestamp + URL + title"""
    unique_string = f"{ts}:{feed.link}:{feed.title}"
    return hashlib.md5(unique_string.encode()).hexdigest()

# In entry processing
entries = {
    "id": generate_entry_id(feed, ts),
    "timestamp": ts,
    # ... rest of fields
}
```

### 5. Feed Validation
**Changes needed:**
```python
def validate_feed_entry(feed):
    """Check required fields exist"""
    if not hasattr(feed, 'link') or not feed.link:
        raise ValueError("Feed entry missing 'link'")
    if not hasattr(feed, 'title') or not feed.title:
        raise ValueError("Feed entry missing 'title'")
    return True

# In feed processing loop
for feed in d.entries:
    try:
        validate_feed_entry(feed)
        # ... continue processing
    except ValueError as e:
        logger.warning(f"Skipping invalid entry from {source}: {e}")
        continue
```

### 6. Rate Limiting
**Changes needed:**
```python
import time

REQUEST_DELAY = 1  # seconds between requests

# In fetching loop, after successful parse
time.sleep(REQUEST_DELAY)
```

### 7. Stale Data Management
**Changes needed:**
```python
MAX_ENTRY_AGE_DAYS = 30

def filter_old_entries(entries):
    """Remove entries older than MAX_ENTRY_AGE_DAYS"""
    cutoff = int(time.time()) - (MAX_ENTRY_AGE_DAYS * 86400)
    return [e for e in entries if e.get('timestamp', 0) >= cutoff]

# Before saving
rslt["entries"] = filter_old_entries(rslt["entries"])
```

### 8. Configuration Validation
**Changes needed:**
```python
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

def load_and_validate_config(filepath):
    with open(filepath, "r") as fp:
        config = json.load(fp)
    jsonschema.validate(config, FEEDS_SCHEMA)
    return config

# Replace direct json.load calls
RSS = load_and_validate_config(FEEDS_FILE_NAME)
```

### 9-16. Additional Improvements
For the remaining items, similar patterns apply:
- **Progress**: Use `tqdm` library or logging with counters
- **Caching**: Store ETags in metadata file, pass to feedparser
- **Timezone**: Add TIMEZONE to config.py user settings
- **Content**: Add `feed.summary` or `feed.content` to entries dict
- **Monitoring**: Track consecutive failures in separate JSON file
- **Concurrency**: Use `concurrent.futures.ThreadPoolExecutor`
- **CLI**: Add `argparse` with options for category, limit, date range
- **Health tracking**: Maintain `feed_stats.json` with success/failure counts