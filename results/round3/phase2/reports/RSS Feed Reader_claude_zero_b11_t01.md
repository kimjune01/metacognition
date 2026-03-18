# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed aggregator with the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using `feedparser`
2. **Multi-category Support**: Organizes feeds into categories, each with multiple source URLs
3. **Configuration Management**: 
   - Initializes user data directory (`~/.rreader/`)
   - Copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user's feeds.json
4. **Data Processing**:
   - Extracts entry metadata (title, link, author, publication date)
   - Handles timezone conversion (UTC to configured timezone, default KST)
   - Generates human-readable timestamps ("HH:MM" for today, "Mon DD, HH:MM" for older)
   - Uses Unix timestamps as unique IDs
5. **Deduplication**: Uses timestamp-based dictionary to prevent duplicate entries
6. **Output**: Writes sorted JSON files per category (`rss_{category}.json`) with entries and creation timestamp
7. **Selective Updates**: Can update a single category or all categories
8. **Logging**: Optional progress logging to stdout

## Triage

### Critical Gaps (Blockers for Production)

1. **Silent Failure on Feed Fetch**: `sys.exit(0)` silently exits on parse errors without logging
2. **ID Collision**: Using Unix timestamps as IDs causes duplicates when multiple entries share the same second
3. **No Error Recovery**: One failed feed aborts the entire category update
4. **Missing User Configuration**: Timezone is hardcoded, no user preferences file

### High Priority (Data Integrity & Reliability)

5. **Naive Timezone Handling**: Assumes all feeds publish in UTC without verification
6. **No Validation**: Missing validation for feeds.json structure, URL formats, required fields
7. **No Rate Limiting**: Could hammer feed servers or get blocked
8. **Race Conditions**: No file locking when writing JSON files
9. **Missing Retry Logic**: Network transients cause permanent failures

### Medium Priority (Usability & Maintenance)

10. **No Error Logging**: No persistent error logs for debugging
11. **No Feed Health Monitoring**: Can't detect consistently failing feeds
12. **Memory Inefficiency**: Loads entire feed history into memory before writing
13. **No Content Sanitization**: Titles/links stored raw without HTML entity handling
14. **Missing CLI Interface**: No argument parsing for user control
15. **No Tests**: Zero test coverage

### Low Priority (Polish & Features)

16. **No Update Scheduling**: Users must manually trigger updates
17. **No Feed Discovery**: Can't add feeds from OPML or by URL probing
18. **Limited Metadata**: Doesn't preserve descriptions, tags, or enclosures
19. **No Read/Unread Tracking**: Can't mark entries as consumed

## Plan

### Critical Fixes

**1. Silent Failure on Feed Fetch**
```python
# Replace the bare except with proper error handling:
except Exception as e:
    error_msg = f" - Failed: {str(e)}\n"
    if log:
        sys.stderr.write(error_msg)
    # Log to error file
    with open(os.path.join(p["path_data"], "errors.log"), "a") as f:
        f.write(f"{datetime.datetime.now()}: {source} - {url} - {str(e)}\n")
    continue  # Don't exit, process remaining feeds
```

**2. ID Collision**
```python
# Change ID generation to include URL hash:
import hashlib
entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"

# Or use incrementing counter for same-second collisions:
if entries["id"] in rslt:
    entries["id"] = f"{ts}_{len([k for k in rslt if str(k).startswith(str(ts))])}"
```

**3. Error Recovery**
- Already addressed in fix #1 by changing `sys.exit()` to `continue`

**4. User Configuration File**
```python
# In config.py, add:
CONFIG_FILE = os.path.join(p["path_data"], "config.json")
DEFAULT_CONFIG = {
    "timezone_offset_hours": 9,
    "update_interval_minutes": 60,
    "max_entries_per_feed": 100
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

config = load_config()
TIMEZONE = datetime.timezone(datetime.timedelta(hours=config["timezone_offset_hours"]))
```

### High Priority Improvements

**5. Timezone Handling**
```python
# In the time parsing section, handle existing timezone info:
if parsed_time:
    at = datetime.datetime(*parsed_time[:6])
    # Check if feed provides timezone (feedparser sets this)
    if hasattr(feed, 'published_parsed') and time.daylight:
        # Use feed's timezone if available
        at = at.replace(tzinfo=datetime.timezone.utc)
    else:
        # Assume UTC if unspecified
        at = at.replace(tzinfo=datetime.timezone.utc)
    at = at.astimezone(TIMEZONE)
```

**6. Validation**
```python
# Add validation function:
def validate_feeds_json(data):
    if not isinstance(data, dict):
        raise ValueError("feeds.json must be a dictionary")
    for category, content in data.items():
        if "feeds" not in content:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(content["feeds"], dict):
            raise ValueError(f"Category '{category}' feeds must be a dictionary")
        for source, url in content["feeds"].items():
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL for {source}: {url}")
    return True

# Use after loading:
with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
    validate_feeds_json(RSS)
```

**7. Rate Limiting**
```python
# Add at top of get_feed_from_rss:
import time
REQUEST_DELAY = 1  # seconds between requests

for source, url in urls.items():
    time.sleep(REQUEST_DELAY)  # Respect server resources
    # ... existing code
```

**8. File Locking**
```python
# Add import: import fcntl (Unix) or msvcrt (Windows)
# Or use portable library:
import portalocker

# Replace file write with:
output_file = os.path.join(p["path_data"], f"rss_{category}.json")
with portalocker.Lock(output_file, mode="w", encoding="utf-8", timeout=5) as f:
    f.write(json.dumps(rslt, ensure_ascii=False))
```

**9. Retry Logic**
```python
# Add retry decorator or manual implementation:
from urllib.error import URLError
import socket

MAX_RETRIES = 3
RETRY_DELAY = 2

for retry in range(MAX_RETRIES):
    try:
        d = feedparser.parse(url)
        break
    except (URLError, socket.timeout) as e:
        if retry < MAX_RETRIES - 1:
            time.sleep(RETRY_DELAY * (retry + 1))
        else:
            # Log and continue to next feed
            sys.stderr.write(f"Failed after {MAX_RETRIES} retries\n")
```

### Medium Priority Enhancements

**10. Error Logging**
```python
# Create logging module:
import logging

logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Replace print statements with logging calls
```

**14. CLI Interface**
```python
# Add argparse:
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RSS Feed Reader")
    parser.add_argument("-c", "--category", help="Update specific category")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--list", action="store_true", help="List all categories")
    args = parser.parse_args()
    
    if args.list:
        with open(FEEDS_FILE_NAME, "r") as fp:
            RSS = json.load(fp)
        for cat in RSS.keys():
            print(cat)
    else:
        do(target_category=args.category, log=args.verbose)
```

**15. Testing Framework**
```python
# Create tests/test_rreader.py:
import unittest
from unittest.mock import patch, mock_open
import rreader

class TestFeedParsing(unittest.TestCase):
    def test_timestamp_conversion(self):
        # Test timezone handling
        pass
    
    def test_duplicate_handling(self):
        # Test ID collision resolution
        pass
    
    @patch('feedparser.parse')
    def test_feed_fetch_failure(self, mock_parse):
        mock_parse.side_effect = Exception("Network error")
        # Verify graceful handling
        pass
```

This plan provides concrete, actionable steps prioritized by impact. Start with Critical fixes to ensure data integrity, then proceed through High/Medium priorities based on user needs.