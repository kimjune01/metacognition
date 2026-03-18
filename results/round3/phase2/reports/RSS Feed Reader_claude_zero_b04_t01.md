# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS feeds using `feedparser` library from multiple sources
2. **Multi-category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Smart Date Formatting**: Shows "HH:MM" for today's entries, "Mon DD, HH:MM" for older ones
5. **Configuration Management**: 
   - Maintains user feeds in `~/.rreader/feeds.json`
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration
6. **Duplicate Handling**: Uses timestamps as IDs to deduplicate entries within a category
7. **JSON Output**: Writes sorted feed entries to `rss_{category}.json` files
8. **Author Display**: Configurable per-category author/source name display
9. **Selective Updates**: Can update a single category or all categories
10. **Optional Logging**: Progress indicators for feed fetching

## Triage

### Critical Gaps
1. **Error Handling is Dangerous** - `sys.exit()` on any parse failure kills the entire process
2. **No Data Validation** - Malformed JSON or missing keys will crash the system
3. **Collision-Prone IDs** - Using timestamp as ID means multiple entries at the same second collide

### High Priority
4. **No Rate Limiting** - Could hammer RSS servers or get IP-banned
5. **No Timeout Configuration** - Slow/hanging feeds block all others
6. **No Caching/Conditional Requests** - Wastes bandwidth, doesn't use ETags or Last-Modified
7. **Missing Logging Infrastructure** - Print statements instead of proper logging
8. **No Configuration Validation** - Invalid feeds.json structure fails silently or crashes

### Medium Priority
9. **No Retry Logic** - Temporary network failures lose all data from that source
10. **No Feed Health Monitoring** - Can't track which feeds are consistently failing
11. **No Entry Limits** - Memory unbounded for feeds with thousands of entries
12. **No Content Sanitization** - Feed titles/data written directly to JSON without escaping
13. **Date Comparison Bug** - Uses `datetime.date.today()` without timezone awareness
14. **No Concurrent Fetching** - Sequential processing is slow with many feeds

### Low Priority
15. **No CLI Interface** - Can't specify options like verbosity, output path, etc.
16. **No Incremental Updates** - Always refetches everything
17. **No Feed Discovery** - Can't auto-detect RSS feeds from URLs
18. **No OPML Import/Export** - Standard RSS reader format not supported

## Plan

### 1. Error Handling (Critical)
**Changes needed:**
- Replace `sys.exit()` with proper exception handling
- Wrap each feed fetch in try-except, log errors, continue processing others
- Return error summary from `do()` function
```python
failed_feeds = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
    except Exception as e:
        failed_feeds.append((source, url, str(e)))
        continue  # Don't kill entire process
```

### 2. Data Validation (Critical)
**Changes needed:**
- Add schema validation for feeds.json using `jsonschema` or manual checks
- Validate required keys exist: `feeds`, optional `show_author`
- Add graceful fallbacks for missing feed attributes
```python
def validate_feeds_config(config):
    assert isinstance(config, dict), "feeds.json must be object"
    for cat, data in config.items():
        assert "feeds" in data, f"Category {cat} missing 'feeds'"
        assert isinstance(data["feeds"], dict), f"Feeds must be dict"
```

### 3. ID Collision Fix (Critical)
**Changes needed:**
- Use compound key: `f"{ts}_{hash(feed.link)[:8]}"` or UUID
- Or append counter suffix when collision detected
```python
entry_id = ts
counter = 0
while entry_id in rslt:
    counter += 1
    entry_id = f"{ts}_{counter}"
```

### 4. Rate Limiting (High)
**Changes needed:**
- Add configurable delay between requests in config.py
- Implement per-domain rate limiting
```python
RATE_LIMIT_DELAY = 1.0  # seconds between requests
last_request = {}
domain = urlparse(url).netloc
if domain in last_request:
    elapsed = time.time() - last_request[domain]
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
last_request[domain] = time.time()
```

### 5. Timeout Configuration (High)
**Changes needed:**
- Add timeout parameter to feedparser calls
- Make configurable in config.py
```python
FEED_TIMEOUT = 30  # seconds
d = feedparser.parse(url, timeout=FEED_TIMEOUT)
```

### 6. HTTP Caching (High)
**Changes needed:**
- Store ETags and Last-Modified headers per feed
- Pass them to feedparser for conditional requests
```python
# Store in cache file: {url: {"etag": "...", "modified": "..."}}
cache = load_http_cache()
d = feedparser.parse(url, 
                     etag=cache.get(url, {}).get('etag'),
                     modified=cache.get(url, {}).get('modified'))
if d.status == 304:  # Not modified
    return cached_entries
save_http_cache(url, d.get('etag'), d.get('modified'))
```

### 7. Logging Infrastructure (High)
**Changes needed:**
- Replace print/sys.stdout with Python logging module
- Add log levels (DEBUG, INFO, WARNING, ERROR)
- Write logs to file in ~/.rreader/
```python
import logging
logger = logging.getLogger('rreader')
logger.setLevel(logging.INFO)
handler = logging.FileHandler(os.path.join(p["path_data"], "rreader.log"))
logger.addHandler(handler)
# Then use: logger.info(f"Fetching {url}")
```

### 8. Configuration Validation (High)
**Changes needed:**
- Validate feeds.json structure on load
- Provide clear error messages for malformed config
- Add example in documentation
```python
try:
    with open(FEEDS_FILE_NAME, "r") as fp:
        RSS = json.load(fp)
    validate_feeds_config(RSS)
except json.JSONDecodeError as e:
    logger.error(f"Invalid JSON in {FEEDS_FILE_NAME}: {e}")
    sys.exit(1)
```

### 9. Retry Logic (Medium)
**Changes needed:**
- Add retry decorator or manual retry loop
- Exponential backoff for transient failures
```python
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        d = feedparser.parse(url)
        break
    except Exception as e:
        if attempt == MAX_RETRIES - 1:
            raise
        time.sleep(2 ** attempt)  # 1s, 2s, 4s
```

### 10. Feed Health Monitoring (Medium)
**Changes needed:**
- Track success/failure counts per feed
- Store last successful fetch timestamp
- Add command to show feed health status
```python
# Add to output JSON:
"feed_health": {
    "source_name": {
        "last_success": timestamp,
        "consecutive_failures": 0,
        "total_failures": 0
    }
}
```

### 11. Entry Limits (Medium)
**Changes needed:**
- Add MAX_ENTRIES_PER_FEED to config.py
- Slice results before writing
```python
MAX_ENTRIES_PER_FEED = 100
rslt["entries"] = rslt["entries"][:MAX_ENTRIES_PER_FEED]
```

### 12. Content Sanitization (Medium)
**Changes needed:**
- HTML-escape feed titles and content
- Strip potentially dangerous characters
```python
import html
entries["title"] = html.escape(feed.title.strip())
```

### 13. Date Comparison Fix (Medium)
**Changes needed:**
- Make `today()` timezone-aware
```python
today = datetime.datetime.now(TIMEZONE).date()
pubDate = at.strftime("%H:%M" if at.date() == today else "%b %d, %H:%M")
```

### 14. Concurrent Fetching (Medium)
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetching
- Make worker count configurable
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_feed, src, url): src 
               for src, url in urls.items()}
    for future in as_completed(futures):
        results.update(future.result())
```

### 15. CLI Interface (Low)
**Changes needed:**
- Add argparse for command-line options
- Support: --category, --verbose, --config-file, --output-dir
```python
import argparse
parser = argparse.ArgumentParser(description='RSS Feed Reader')
parser.add_argument('--category', help='Update specific category')
parser.add_argument('--verbose', action='store_true')
args = parser.parse_args()
do(target_category=args.category, log=args.verbose)
```