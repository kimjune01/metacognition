# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Source Aggregation**: Supports organizing feeds into categories, with each category containing multiple feed URLs.

3. **Feed Configuration Management**: 
   - Copies a bundled default `feeds.json` configuration file to user data directory on first run
   - Merges new categories from bundled config into existing user config without overwriting user data

4. **Entry Normalization**: Extracts and standardizes feed entries with fields including:
   - Unique ID (Unix timestamp)
   - Source name (with optional author display)
   - Publication date (formatted as "HH:MM" for today, "Mon DD, HH:MM" for other dates)
   - Timestamp, URL, and title

5. **Timezone Handling**: Converts UTC timestamps to a configured timezone (currently hardcoded to UTC+9/KST).

6. **Deduplication**: Uses timestamp-based dictionary keys to eliminate duplicate entries across sources.

7. **Sorted Output**: Entries are sorted by timestamp in reverse chronological order (newest first).

8. **JSON Persistence**: Saves aggregated feed data to category-specific JSON files in `~/.rreader/` directory.

9. **Selective Updates**: Can refresh either all categories or a single target category.

10. **Basic Logging**: Optional console output showing feed fetch progress.

## Triage

### Critical Gaps (P0)

1. **No Error Handling for Individual Feeds**: The bare `except:` clauses silently swallow errors. One malformed feed or network timeout will skip that source with no visibility.

2. **No Retry Logic**: Transient network failures result in missing data with no recovery mechanism.

3. **Missing Configuration Validation**: No verification that `feeds.json` has the expected structure or that URLs are valid.

### High Priority Gaps (P1)

4. **No Rate Limiting**: Rapid successive requests could hit rate limits or appear as abusive behavior.

5. **Timestamp Collision Handling**: Using Unix timestamp as ID causes data loss when multiple entries share the same second. Last entry wins silently.

6. **No HTTP Timeout Configuration**: Slow feeds can hang indefinitely.

7. **No Caching/Conditional Requests**: Every run fetches full feeds, wasting bandwidth. No support for ETags or Last-Modified headers.

8. **Hardcoded Timezone**: The UTC+9 timezone is hardcoded rather than configurable or system-detected.

### Medium Priority Gaps (P2)

9. **No Entry Age Limits**: Keeps all historical entries indefinitely, causing file bloat.

10. **No Feed Metadata**: Doesn't capture feed-level information (description, logo, last build date).

11. **Missing CLI Interface**: No command-line argument parsing for specifying categories, verbosity, or config paths.

12. **No Concurrency**: Sequential feed fetching is slow for many sources.

13. **Incomplete Import Handling**: The try/except import logic suggests package usage but isn't properly structured.

### Low Priority Gaps (P3)

14. **No Data Migration Strategy**: No version tracking for JSON schema changes.

15. **Limited Date Formatting**: The "today vs other" logic doesn't handle yesterday, this week, etc.

16. **No Feed Health Monitoring**: No tracking of fetch failures, staleness, or feed death.

17. **Missing Unit Tests**: No test coverage for parsing, deduplication, or date handling.

## Plan

### P0 Fixes

**1. Granular Error Handling**
```python
# Replace bare except clauses with specific handling:
except feedparser.FeedParserError as e:
    if log:
        sys.stderr.write(f" - Parse error: {e}\n")
    continue
except urllib.error.URLError as e:
    if log:
        sys.stderr.write(f" - Network error: {e}\n")
    continue
except Exception as e:
    if log:
        sys.stderr.write(f" - Unexpected error: {e}\n")
    continue

# Add error metrics to output JSON:
rslt = {
    "entries": rslt, 
    "created_at": int(time.time()),
    "errors": error_list  # List of {source, url, error} dicts
}
```

**2. Retry Logic with Exponential Backoff**
```python
import urllib.error
from time import sleep

def fetch_with_retry(url, max_retries=3, backoff_factor=2):
    for attempt in range(max_retries):
        try:
            return feedparser.parse(url)
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            sleep(backoff_factor ** attempt)
    return None
```

**3. Configuration Schema Validation**
```python
def validate_feeds_config(config):
    """Validate feeds.json structure."""
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a JSON object")
    
    for category, data in config.items():
        if not isinstance(data, dict):
            raise ValueError(f"Category '{category}' must be an object")
        if "feeds" not in data:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category '{category}' feeds must be an object")
        
        for source, url in data["feeds"].items():
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL for {source}: {url}")
```

### P1 Fixes

**4. Rate Limiting**
```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, min_interval=1.0):
        self.min_interval = min_interval
        self.last_request = defaultdict(float)
    
    def wait(self, domain):
        elapsed = time.time() - self.last_request[domain]
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request[domain] = time.time()

# Usage: Extract domain from URL and call limiter.wait(domain) before each fetch
```

**5. Collision-Resistant ID Generation**
```python
import hashlib

def generate_entry_id(feed, timestamp):
    """Generate unique ID combining timestamp and content hash."""
    content = f"{timestamp}:{feed.link}:{feed.title}".encode('utf-8')
    hash_suffix = hashlib.md5(content).hexdigest()[:8]
    return f"{timestamp}_{hash_suffix}"

# Usage: entries["id"] = generate_entry_id(feed, ts)
```

**6. HTTP Timeout Configuration**
```python
# Add to config.py:
HTTP_TIMEOUT = 30  # seconds

# Modify feedparser call:
d = feedparser.parse(url, timeout=HTTP_TIMEOUT)
```

**7. Conditional Request Support**
```python
def load_feed_metadata(category):
    """Load ETags and Last-Modified from previous fetch."""
    meta_file = os.path.join(p["path_data"], f"rss_{category}_meta.json")
    if os.path.exists(meta_file):
        with open(meta_file) as f:
            return json.load(f)
    return {}

def save_feed_metadata(category, metadata):
    """Save ETags and Last-Modified for next fetch."""
    meta_file = os.path.join(p["path_data"], f"rss_{category}_meta.json")
    with open(meta_file, 'w') as f:
        json.dump(metadata, f)

# In fetch logic:
metadata = load_feed_metadata(category)
d = feedparser.parse(url, 
                     etag=metadata.get(url, {}).get('etag'),
                     modified=metadata.get(url, {}).get('modified'))
if d.status == 304:  # Not modified
    continue
metadata[url] = {'etag': d.get('etag'), 'modified': d.get('modified')}
save_feed_metadata(category, metadata)
```

**8. Configurable Timezone**
```python
# In config.py, replace hardcoded timezone:
import os
from zoneinfo import ZoneInfo  # Python 3.9+

# Try to use system timezone, fallback to UTC+9
try:
    TIMEZONE = ZoneInfo(os.environ.get('TZ', 'Asia/Seoul'))
except:
    TIMEZONE = datetime.timezone(datetime.timedelta(hours=9))

# Or read from feeds.json:
# "settings": {"timezone": "America/New_York"}
```

### P2 Fixes

**9. Entry Age Filtering**
```python
# Add to config.py:
MAX_ENTRY_AGE_DAYS = 30

# In get_feed_from_rss, after collecting entries:
cutoff_timestamp = int(time.time()) - (MAX_ENTRY_AGE_DAYS * 86400)
rslt = {k: v for k, v in rslt.items() if v["timestamp"] > cutoff_timestamp}
```

**10. Feed-Level Metadata Capture**
```python
# Add to JSON output:
feed_metadata = {
    "title": d.feed.get('title', ''),
    "description": d.feed.get('description', ''),
    "link": d.feed.get('link', ''),
    "image": d.feed.get('image', {}).get('href', ''),
}

rslt = {
    "entries": rslt, 
    "created_at": int(time.time()),
    "feed_metadata": feed_metadata
}
```

**11. CLI Argument Parsing**
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('--category', help='Update specific category only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable logging')
    parser.add_argument('--config', help='Path to feeds.json', 
                       default=FEEDS_FILE_NAME)
    args = parser.parse_args()
    
    do(target_category=args.category, log=args.verbose)

if __name__ == "__main__":
    main()
```

**12. Concurrent Feed Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    """Fetch and parse a single feed."""
    try:
        if log:
            sys.stdout.write(f"- {url}\n")
        return source, feedparser.parse(url), None
    except Exception as e:
        return source, None, str(e)

# In get_feed_from_rss:
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, source, url, log): source 
               for source, url in urls.items()}
    
    for future in as_completed(futures):
        source, parsed_data, error = future.result()
        if error:
            # Handle error
            continue
        # Process parsed_data
```

**13. Proper Package Structure**
```python
# Remove the try/except import hack, structure as proper package:
# rreader/
#   __init__.py
#   cli.py        (main entry point)
#   fetcher.py    (RSS fetching logic)
#   common.py     (shared utilities)
#   config.py     (configuration)

# In __init__.py:
from .fetcher import fetch_feeds
from .common import setup_directories

__all__ = ['fetch_feeds', 'setup_directories']
```

### P3 Fixes

**14. Data Migration Framework**
```python
SCHEMA_VERSION = 1

def migrate_data(old_version, new_version):
    """Migrate data between schema versions."""
    migrations = {
        (0, 1): migrate_v0_to_v1,
        # Add more migrations as needed
    }
    # Apply migrations sequentially
    
# Add version to JSON files:
rslt = {
    "schema_version": SCHEMA_VERSION,
    "entries": rslt,
    "created_at": int(time.time())
}
```

**15. Enhanced Date Formatting**
```python
def format_relative_date(dt, now):
    """Format date relative to now."""
    delta = now.date() - dt.date()
    if delta.days == 0:
        return dt.strftime("%H:%M")
    elif delta.days == 1:
        return f"Yesterday, {dt.strftime('%H:%M')}"
    elif delta.days < 7:
        return dt.strftime("%a, %H:%M")
    else:
        return dt.strftime("%b %d, %H:%M")
```

**16. Feed Health Monitoring**
```python
# Track in metadata:
feed_health = {
    url: {
        "last_success": timestamp,
        "last_failure": timestamp,
        "consecutive_failures": count,
        "total_entries_seen": count,
        "is_stale": bool  # No updates in X days
    }
}

# Alert on persistent failures or staleness
```

**17. Unit Test Framework**
```python
# tests/test_fetcher.py
import unittest
from unittest.mock import Mock, patch
from rreader.fetcher import get_feed_from_rss, generate_entry_id

class TestFeedFetcher(unittest.TestCase):
    def test_entry_deduplication(self):
        # Test that duplicate entries are handled correctly
        pass
    
    def test_date_parsing(self):
        # Test various date formats
        pass
    
    @patch('feedparser.parse')
    def test_network_error_handling(self, mock_parse):
        mock_parse.side_effect = URLError("Network error")
        # Verify graceful handling
        pass
```