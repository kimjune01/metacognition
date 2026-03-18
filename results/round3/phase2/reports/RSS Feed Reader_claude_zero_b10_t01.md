# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-Category Support**: Organizes feeds into categories, with each category containing multiple feed sources
3. **Feed Configuration Management**: 
   - Maintains a `feeds.json` configuration file in `~/.rreader/`
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration
4. **Time Localization**: Converts feed timestamps from UTC to a configured timezone (KST/UTC+9)
5. **Flexible Date Display**: Shows time-only format for today's posts, date+time for older posts
6. **Data Persistence**: Saves parsed feed data as JSON files (`rss_{category}.json`) in the data directory
7. **Duplicate Handling**: Uses timestamp as ID to prevent duplicate entries in a single fetch
8. **Author Display**: Configurable per-category option to show feed author vs source name
9. **Selective Updates**: Can refresh a single category or all categories
10. **Optional Logging**: Progress output to stdout when `log=True`

## Triage

### Critical Gaps
1. **No Error Recovery** - Single feed failure terminates entire application with `sys.exit(0)`
2. **Missing Input Validation** - No validation of feed URLs, category names, or JSON structure
3. **No Concurrent Fetching** - Sequential processing makes updates slow with many feeds

### High Priority Gaps
4. **ID Collision Risk** - Using second-precision timestamps as IDs causes overwriting of simultaneous posts
5. **No Retry Logic** - Network failures result in immediate exit with no retry attempts
6. **Missing Feed Validation** - No checks for malformed RSS/Atom feeds or empty entries
7. **No Rate Limiting** - Could overwhelm feed servers or trigger rate limits
8. **Silent Data Directory Creation** - Creates `.rreader/` without user notification or error handling

### Medium Priority Gaps
9. **No User Feedback** - Non-log mode provides no progress indication for long-running operations
10. **Hard-coded Timezone** - Timezone is fixed in config rather than user-configurable
11. **No Data Expiration** - Old feed entries accumulate indefinitely
12. **Missing Command-line Interface** - No argument parsing for category selection or options
13. **No Configuration Validation** - Invalid `feeds.json` will cause runtime crashes

### Low Priority Gaps
14. **No Tests** - No unit or integration tests present
15. **Limited Metadata** - Doesn't capture/store description, tags, images, or other RSS fields
16. **No Feed Discovery** - Users must manually add feed URLs
17. **No OPML Import/Export** - Can't import/export feed lists in standard format

## Plan

### 1. Error Recovery (Critical)
**Change**: Wrap feed fetching in try-except per source, not per category
```python
for source, url in urls.items():
    try:
        # ... fetch and parse ...
    except Exception as e:
        if log:
            sys.stderr.write(f" - Failed: {e}\n")
        continue  # Process remaining feeds
```
**Remove**: The `sys.exit()` call on line 30
**Add**: Error collection and summary reporting at end of function

### 2. Input Validation (Critical)
**Add**: Validation function before processing:
```python
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    for category, data in config.items():
        if "feeds" not in data or not isinstance(data["feeds"], dict):
            raise ValueError(f"Category {category} missing 'feeds' dict")
        for source, url in data["feeds"].items():
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL for {source}: {url}")
```
**Location**: Call after loading RSS from JSON (line 77)

### 3. Concurrent Fetching (Critical)
**Add**: Import `concurrent.futures.ThreadPoolExecutor` at top
**Replace**: Sequential loop (lines 82-87) with:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {
        executor.submit(get_feed_from_rss, cat, d["feeds"], 
                       d.get("show_author", False), log): cat 
        for cat, d in RSS.items()
    }
    for future in as_completed(futures):
        try:
            future.result()
        except Exception as e:
            if log:
                sys.stderr.write(f"Category {futures[future]} failed: {e}\n")
```

### 4. ID Collision Fix (High)
**Replace**: Line 56 `"id": ts` with:
```python
"id": f"{ts}_{hash(feed.link) % 10000}"  # Combine timestamp + URL hash
```
**Update**: Line 70 sorting to handle string IDs properly

### 5. Retry Logic (High)
**Add**: Decorator or wrapper function:
```python
def fetch_with_retry(url, max_attempts=3, backoff=2):
    for attempt in range(max_attempts):
        try:
            return feedparser.parse(url)
        except Exception as e:
            if attempt == max_attempts - 1:
                raise
            time.sleep(backoff ** attempt)
```
**Replace**: Line 26 `d = feedparser.parse(url)` with retry call

### 6. Feed Validation (High)
**Add**: After parsing (line 29):
```python
if d.bozo and not d.entries:  # feedparser sets bozo flag for errors
    raise ValueError(f"Invalid feed: {d.bozo_exception}")
if not hasattr(d, 'entries'):
    raise ValueError("Feed has no entries attribute")
```

### 7. Rate Limiting (High)
**Add**: Per-domain rate limiting:
```python
from urllib.parse import urlparse
from collections import defaultdict

last_fetch_time = defaultdict(float)
MIN_INTERVAL = 1.0  # seconds between requests to same domain

def rate_limited_fetch(url):
    domain = urlparse(url).netloc
    elapsed = time.time() - last_fetch_time[domain]
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    result = feedparser.parse(url)
    last_fetch_time[domain] = time.time()
    return result
```

### 8. Data Directory Error Handling (High)
**Replace**: Lines in common.py section:
```python
for d in p["pathkeys"]:
    try:
        os.makedirs(p[d], exist_ok=True)
    except OSError as e:
        sys.stderr.write(f"Cannot create directory {p[d]}: {e}\n")
        sys.exit(1)
```

### 9. Progress Feedback (Medium)
**Add**: Progress bar or percentage for non-log mode:
```python
if not log:
    total = len(urls)
    for idx, (source, url) in enumerate(urls.items(), 1):
        print(f"\rFetching {category}: {idx}/{total}", end="", file=sys.stderr)
```

### 10. Configurable Timezone (Medium)
**Modify**: config.py to load from environment or config file:
```python
TIMEZONE_OFFSET = int(os.getenv('RSS_TIMEZONE_OFFSET', '9'))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET))
```

### 11. Data Expiration (Medium)
**Add**: Before saving (line 72):
```python
MAX_AGE_DAYS = 30
cutoff_ts = int(time.time()) - (MAX_AGE_DAYS * 86400)
rslt = [val for val in rslt if val["timestamp"] > cutoff_ts]
```

### 12. Command-line Interface (Medium)
**Add**: Argument parsing at bottom:
```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='RSS Feed Fetcher')
    parser.add_argument('category', nargs='?', help='Specific category to update')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable logging')
    args = parser.parse_args()
    do(target_category=args.category, log=args.verbose)
```

### 13. Configuration Validation (Medium)
**Add**: JSON schema validation using `jsonschema` library or manual checks:
```python
try:
    with open(FEEDS_FILE_NAME, "r") as fp:
        RSS = json.load(fp)
    validate_feeds_config(RSS)
except (json.JSONDecodeError, ValueError) as e:
    sys.stderr.write(f"Invalid feeds.json: {e}\n")
    sys.exit(1)
```

### 14. Testing (Low)
**Add**: New file `test_rreader.py`:
```python
import unittest
from unittest.mock import patch, Mock
# Test feed parsing, error handling, ID generation, etc.
```

### 15. Enhanced Metadata (Low)
**Expand**: entries dict (line 57) to include:
```python
"description": getattr(feed, 'summary', '')[:200],
"image": getattr(feed, 'media_thumbnail', [{}])[0].get('url'),
"tags": [tag.term for tag in getattr(feed, 'tags', [])]
```