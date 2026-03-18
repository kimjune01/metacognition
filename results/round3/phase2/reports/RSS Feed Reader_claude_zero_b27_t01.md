# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS feeds from multiple sources using `feedparser`
2. **Multi-category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Data Storage**: Saves parsed feed entries as JSON files (one per category) in `~/.rreader/`
4. **Timezone Handling**: Converts feed timestamps to a configured timezone (currently KST/UTC+9)
5. **Smart Date Formatting**: Shows "HH:MM" for today's entries, "Mon DD, HH:MM" for older entries
6. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries (though collision-prone)
7. **Configuration Management**: 
   - Copies bundled `feeds.json` on first run
   - Merges new categories from bundled config into user config on updates
8. **Flexible Execution**: Can refresh all feeds or a single target category
9. **Author Display**: Configurable per-category author attribution (source name vs. feed author)
10. **Sorting**: Entries sorted by timestamp (newest first)

## Triage

### Critical Gaps
1. **No Error Recovery**: Single feed failure kills entire category update
2. **No Logging Infrastructure**: Only basic stdout messages, no persistent logs
3. **No Rate Limiting**: Could hammer RSS servers or get blocked
4. **ID Collision Risk**: Using timestamp as ID means multiple posts at same second collide

### High Priority
5. **No Validation**: Malformed feeds.json causes crashes
6. **No HTTP Timeout**: Network hangs will freeze indefinitely
7. **No Caching Headers**: Ignores ETags/Last-Modified, wastes bandwidth
8. **No Concurrency**: Sequential processing is slow for many feeds
9. **Missing CLI Interface**: No argument parsing for command-line usage

### Medium Priority
10. **No Monitoring/Metrics**: Can't track feed health, fetch times, error rates
11. **Poor Exception Handling**: Bare `except:` clauses hide real issues
12. **No Content Sanitization**: HTML/script injection risks in titles
13. **No Database**: JSON files don't scale and have race conditions
14. **Missing Tests**: No unit or integration tests

### Low Priority
15. **Hardcoded Timezone**: Should be user-configurable
16. **No Feed Discovery**: Can't auto-detect RSS URLs from websites
17. **No OPML Import/Export**: Industry standard for feed list portability

## Plan

### 1. Error Recovery (Critical)
**Change**: Wrap individual feed fetching in try-except, continue on failure
```python
for source, url in urls.items():
    try:
        # existing parse logic
    except Exception as e:
        errors.append({"source": source, "url": url, "error": str(e)})
        if log:
            sys.stderr.write(f"ERROR: {source} failed: {e}\n")
        continue  # Don't exit, process remaining feeds
```
**Add**: Return error summary in result dict for monitoring

### 2. Logging Infrastructure (Critical)
**Change**: Replace print statements with proper logging
```python
import logging

logger = logging.getLogger('rreader')
handler = logging.FileHandler(os.path.join(p["path_data"], "rreader.log"))
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)
```
**Add**: Log levels for different events (INFO for success, WARNING for recoverable errors, ERROR for failures)

### 3. Rate Limiting (Critical)
**Change**: Add delay between requests
```python
import time
RATE_LIMIT_DELAY = 1  # seconds between feeds

for source, url in urls.items():
    time.sleep(RATE_LIMIT_DELAY)
    # existing logic
```
**Add**: Configurable per-feed rate limits in feeds.json

### 4. Fix ID Collision (Critical)
**Change**: Generate unique IDs combining timestamp and URL hash
```python
import hashlib

entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
entries = {
    "id": entry_id,
    # ... rest of fields
}
rslt[entry_id] = entries  # Use string key instead of int
```

### 5. Configuration Validation (High Priority)
**Change**: Add schema validation at startup
```python
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"}
            }
        }
    }
}

with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
    jsonschema.validate(RSS, FEEDS_SCHEMA)
```

### 6. HTTP Timeouts (High Priority)
**Change**: Configure feedparser with timeout
```python
d = feedparser.parse(url, timeout=30)
```
**Note**: May require setting socket default timeout as feedparser doesn't always respect timeout parameter:
```python
import socket
socket.setdefaulttimeout(30)
```

### 7. HTTP Caching (High Priority)
**Change**: Store and use ETags/Last-Modified headers
```python
# Store in cache file per feed
cache_file = os.path.join(p["path_data"], "cache", f"{hashlib.md5(url.encode()).hexdigest()}.json")
# Load previous etag/modified
d = feedparser.parse(url, etag=cached_etag, modified=cached_modified)
if d.status == 304:  # Not Modified
    continue
# Save new etag/modified for next run
```

### 8. Concurrent Fetching (High Priority)
**Change**: Use ThreadPoolExecutor for parallel downloads
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # Extract single feed logic here
    return source, result

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s for s, u in urls.items()}
    for future in as_completed(futures):
        source, result = future.result()
        rslt.update(result)
```

### 9. CLI Interface (High Priority)
**Change**: Add argparse for proper command-line handling
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS feed reader')
    parser.add_argument('--category', '-c', help='Update specific category')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    parser.add_argument('--list', '-l', action='store_true', help='List categories')
    args = parser.parse_args()
    
    if args.list:
        # show categories
    else:
        do(target_category=args.category, log=args.verbose)

if __name__ == "__main__":
    main()
```

### 10. Monitoring/Metrics (Medium Priority)
**Change**: Track and persist metrics
```python
metrics = {
    "last_run": int(time.time()),
    "feeds_processed": 0,
    "feeds_failed": 0,
    "entries_added": 0,
    "average_fetch_time": 0
}
# Write to metrics.json after each run
```

### 11. Proper Exception Handling (Medium Priority)
**Change**: Replace bare `except:` with specific exceptions
```python
except (AttributeError, KeyError, ValueError) as e:
    logger.warning(f"Skipping malformed entry: {e}")
    continue
except (feedparser.exceptions.FeedParserException, ConnectionError, TimeoutError) as e:
    logger.error(f"Feed fetch failed for {url}: {e}")
    continue
```

### 12. Content Sanitization (Medium Priority)
**Change**: Sanitize HTML in titles
```python
import html
from html.parser import HTMLParser

class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.strict = False
        self.convert_charrefs= True
        self.text = []
    def handle_data(self, d):
        self.text.append(d)
    def get_data(self):
        return ''.join(self.text)

def strip_tags(html_string):
    s = MLStripper()
    s.feed(html_string)
    return s.get_data()

entries = {
    # ...
    "title": strip_tags(html.unescape(feed.title)),
}
```

### 13. Database Backend (Medium Priority)
**Change**: Replace JSON files with SQLite
```python
import sqlite3

# Create schema
conn = sqlite3.connect(os.path.join(p["path_data"], "feeds.db"))
conn.execute('''CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    category TEXT,
    source_name TEXT,
    pub_date TEXT,
    timestamp INTEGER,
    url TEXT UNIQUE,
    title TEXT,
    created_at INTEGER
)''')
# Replace file writes with INSERT OR REPLACE statements
```

### 14. Test Suite (Medium Priority)
**Add**: Unit tests for core functions
```python
# tests/test_feed_parsing.py
import unittest
from unittest.mock import patch, Mock

class TestFeedParsing(unittest.TestCase):
    def test_timestamp_conversion(self):
        # Test timezone conversion logic
        pass
    
    @patch('feedparser.parse')
    def test_feed_fetch_error_handling(self, mock_parse):
        mock_parse.side_effect = Exception("Network error")
        # Verify error is caught and logged
        pass
```

### 15. Configurable Timezone (Low Priority)
**Change**: Move timezone to feeds.json or separate config
```python
# In feeds.json add:
{
    "config": {
        "timezone_offset_hours": 9
    },
    "categories": { ... }
}

# In code:
TIMEZONE = datetime.timezone(datetime.timedelta(hours=RSS.get("config", {}).get("timezone_offset_hours", 0)))
```