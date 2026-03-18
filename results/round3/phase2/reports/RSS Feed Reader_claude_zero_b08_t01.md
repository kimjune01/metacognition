# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS/Atom feeds using `feedparser` library
2. **Multi-category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Data Persistence**: Saves parsed feed entries to JSON files (one per category) in `~/.rreader/`
4. **Timestamp Management**: Converts feed publication times to a configurable timezone (currently KST/UTC+9)
5. **Deduplication**: Uses timestamp as ID to prevent duplicate entries within a category
6. **Configuration Management**: 
   - Copies bundled `feeds.json` template if user config doesn't exist
   - Merges new categories from bundled config into existing user config
7. **Flexible Execution**: Can process all categories or a single target category
8. **Author Attribution**: Supports per-category configuration for showing feed author vs. source name
9. **Time Formatting**: Displays times as "HH:MM" for today's items, "Mon DD, HH:MM" for older items

## Triage

### Critical Gaps
1. **No Error Recovery** - Single feed failure crashes entire category update
2. **No HTTP Timeout Configuration** - Can hang indefinitely on network issues
3. **Missing Configuration Validation** - Invalid JSON or malformed URLs cause cryptic failures

### High Priority Gaps
4. **No Logging Framework** - Uses print statements; no log levels, rotation, or file output
5. **ID Collision Vulnerability** - Using only timestamp (second precision) as ID allows duplicates
6. **No Rate Limiting** - Could overwhelm feed sources or trigger rate limits
7. **Missing Data Directory Creation Check** - Assumes `~/.rreader/` exists before writing files

### Medium Priority Gaps
8. **No Feed Metadata Persistence** - Loses feed info (descriptions, images, ETags) between runs
9. **No Conditional GET Support** - Downloads full feeds every time (inefficient)
10. **Timezone Hardcoded** - TIMEZONE in config.py but no user-facing configuration mechanism
11. **No Entry Expiration** - JSON files grow indefinitely

### Low Priority Gaps
12. **No CLI Interface** - No argument parsing for selecting categories or options
13. **No Status Reporting** - No summary of entries fetched, errors encountered
14. **No Tests** - No unit or integration tests

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Wrap `feedparser.parse()` in try-except to catch network errors, timeouts
- Continue processing remaining feeds if one fails
- Collect errors and report at end
```python
failed_feeds = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        if d.bozo:  # feedparser's error flag
            failed_feeds.append((source, url, d.bozo_exception))
            continue
    except Exception as e:
        failed_feeds.append((source, url, e))
        continue
```

### 2. HTTP Timeout Configuration (Critical)
**Changes needed:**
- Add timeout parameter to `feedparser.parse()` call
- Add timeout setting to config.py (default 30 seconds)
```python
# In config.py
FEED_TIMEOUT = 30

# In do()
d = feedparser.parse(url, timeout=FEED_TIMEOUT)
```

### 3. Configuration Validation (Critical)
**Changes needed:**
- Validate `feeds.json` structure on load
- Check URLs are well-formed
- Provide helpful error messages
```python
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    for category, data in config.items():
        if 'feeds' not in data:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(data['feeds'], dict):
            raise ValueError(f"Category '{category}' feeds must be a dictionary")
```

### 4. Logging Framework (High Priority)
**Changes needed:**
- Replace print/sys.stdout.write with Python's `logging` module
- Add configurable log levels and file output
- Create logger in `common.py`
```python
import logging
logger = logging.getLogger('rreader')
handler = logging.FileHandler(os.path.join(p["path_data"], "rreader.log"))
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Replace sys.stdout.write calls
logger.info(f"Fetching {url}")
```

### 5. Fix ID Collision Vulnerability (High Priority)
**Changes needed:**
- Change ID strategy to combine timestamp with URL hash or use UUID
- Update deduplication logic
```python
import hashlib

def generate_entry_id(feed, parsed_time):
    ts = int(time.mktime(parsed_time))
    url_hash = hashlib.md5(feed.link.encode()).hexdigest()[:8]
    return f"{ts}_{url_hash}"

entries = {
    "id": generate_entry_id(feed, parsed_time),
    # ... rest of fields
}
```

### 6. Rate Limiting (High Priority)
**Changes needed:**
- Add configurable delay between feed fetches
- Add to config.py and implement in loop
```python
# In config.py
FEED_FETCH_DELAY = 1.0  # seconds

# In get_feed_from_rss()
for source, url in urls.items():
    if source != list(urls.keys())[0]:  # Skip delay for first feed
        time.sleep(FEED_FETCH_DELAY)
    # ... fetch logic
```

### 7. Data Directory Safety (High Priority)
**Changes needed:**
- Ensure directory exists before writing files (already partially done but incomplete)
- Add explicit check before JSON write operations
```python
# Already exists in common.py but should add error handling
for d in p["pathkeys"]:
    try:
        os.makedirs(p[d], exist_ok=True)
    except OSError as e:
        sys.exit(f"Cannot create directory {p[d]}: {e}")
```

### 8. Feed Metadata Persistence (Medium Priority)
**Changes needed:**
- Store ETags and Last-Modified headers in metadata file
- Pass to feedparser for conditional requests
```python
# Save metadata
metadata_file = os.path.join(p["path_data"], f"metadata_{category}.json")
metadata = {}
if os.path.exists(metadata_file):
    with open(metadata_file) as f:
        metadata = json.load(f)

# Use in request
etag = metadata.get(url, {}).get('etag')
modified = metadata.get(url, {}).get('modified')
d = feedparser.parse(url, etag=etag, modified=modified)

# Update metadata after fetch
metadata[url] = {
    'etag': d.get('etag'),
    'modified': d.get('modified')
}
```

### 9. Conditional GET Support (Medium Priority)
**Changes needed:**
- Implement in conjunction with #8 above
- Check `d.status` for 304 Not Modified and skip processing

### 10. User-Configurable Timezone (Medium Priority)
**Changes needed:**
- Move timezone to user `feeds.json` or separate config file
- Parse timezone string to timezone object
```python
# In feeds.json
{
    "settings": {
        "timezone": "+09:00"
    },
    "categories": { ... }
}

# Parse timezone
from datetime import timezone, timedelta
def parse_timezone(tz_string):
    # Parse "+09:00" format
    sign = 1 if tz_string[0] == '+' else -1
    hours, minutes = map(int, tz_string[1:].split(':'))
    return timezone(timedelta(hours=sign*hours, minutes=sign*minutes))
```

### 11. Entry Expiration (Medium Priority)
**Changes needed:**
- Add max_age configuration per category
- Filter old entries before saving
```python
# In feeds.json per category
"max_age_days": 30

# In get_feed_from_rss()
max_age = d.get("max_age_days", 30)
cutoff_ts = int(time.time()) - (max_age * 86400)
rslt = {k: v for k, v in rslt.items() if v["timestamp"] >= cutoff_ts}
```

### 12. CLI Interface (Low Priority)
**Changes needed:**
- Add argparse for command-line options
```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('--category', help='Update specific category')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    args = parser.parse_args()
    do(target_category=args.category, log=args.verbose)
```

### 13. Status Reporting (Low Priority)
**Changes needed:**
- Return statistics from `get_feed_from_rss()`
- Print summary after execution
```python
stats = {
    'feeds_fetched': len(urls),
    'entries_found': len(rslt['entries']),
    'errors': len(failed_feeds)
}
return rslt, stats
```

### 14. Tests (Low Priority)
**Changes needed:**
- Create `tests/` directory
- Add unit tests for feed parsing, timezone conversion, ID generation
- Add integration tests with mock RSS feeds
```python
# tests/test_feed_parsing.py
import unittest
from unittest.mock import patch, MagicMock

class TestFeedParsing(unittest.TestCase):
    @patch('feedparser.parse')
    def test_feed_parsing_success(self, mock_parse):
        # Mock feedparser response
        # Test get_feed_from_rss()
        pass
```