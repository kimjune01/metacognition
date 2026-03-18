# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Timestamp Handling**: Converts feed publication times to a configurable timezone (currently KST/UTC+9)
4. **Data Persistence**: Stores parsed feed entries as JSON files (one per category) in `~/.rreader/`
5. **Configuration Management**: 
   - Maintains user feed configuration in `feeds.json`
   - Auto-copies bundled default feeds if user config doesn't exist
   - Merges new categories from bundled config into existing user config
6. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries within a single fetch
7. **Flexible Author Display**: Supports per-category `show_author` flag to display feed authors vs. source names
8. **Date Formatting**: Shows today's entries with time only, older entries with date and time
9. **Selective Updates**: Can target a single category or update all categories

## Triage

### Critical Gaps
1. **No error handling for individual feeds** - One failing feed crashes the entire category
2. **No feed timeout configuration** - Slow feeds can hang indefinitely
3. **No data directory validation** - Silent failures if directory creation fails

### High Priority Gaps
4. **Duplicate ID collision** - Multiple entries published at the same second overwrite each other
5. **No logging framework** - Binary log flag with print statements instead of proper logging
6. **No rate limiting** - Could hammer feed servers or get IP-banned
7. **No stale data handling** - Old cached data persists forever with no expiration

### Medium Priority Gaps
8. **No network retry logic** - Transient failures aren't retried
9. **No feed validation** - Malformed feed URLs accepted silently
10. **No concurrency** - Sequential processing is slow for many feeds
11. **Hardcoded timezone** - Not configurable per-user
12. **No entry limit** - Could create massive JSON files over time

### Low Priority Gaps
13. **No CLI argument parsing** - Limited command-line interface
14. **No performance metrics** - Can't measure fetch times or success rates
15. **No user-agent header** - Some feeds block requests without proper identification

## Plan

### 1. Error Handling for Individual Feeds
**Change**: Wrap each feed fetch in try-except, continue on failure
```python
for source, url in urls.items():
    try:
        # existing fetch logic
    except Exception as e:
        if log:
            sys.stderr.write(f"Failed to fetch {source} ({url}): {e}\n")
        continue  # Don't crash, skip to next feed
```
Add a summary dict tracking successes/failures to return alongside results.

### 2. Feed Timeout Configuration
**Change**: Add timeout parameter to feedparser and config file
```python
# In feeds.json schema
{"timeout": 30}  # seconds, per-category

# In code
d = feedparser.parse(url, timeout=d.get("timeout", 30))
```

### 3. Data Directory Validation
**Change**: Add explicit error handling in directory creation
```python
for d in p["pathkeys"]:
    try:
        os.makedirs(p[d], exist_ok=True)
    except OSError as e:
        sys.stderr.write(f"Failed to create directory {p[d]}: {e}\n")
        sys.exit(1)
```

### 4. Duplicate ID Collision
**Change**: Create composite unique ID using timestamp + hash of URL
```python
import hashlib

entry_hash = hashlib.md5(feed.link.encode()).hexdigest()[:8]
unique_id = f"{ts}_{entry_hash}"
entries = {
    "id": unique_id,
    # ... rest of fields
}
rslt[entries["id"]] = entries
```

### 5. Logging Framework
**Change**: Replace print statements with Python logging module
```python
import logging

logger = logging.getLogger(__name__)

# Replace sys.stdout.write calls
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}")

# Add log level configuration
logging.basicConfig(level=logging.INFO if log else logging.WARNING)
```

### 6. Rate Limiting
**Change**: Add configurable delay between requests
```python
import time

# In feeds.json schema
{"rate_limit_delay": 1.0}  # seconds between feeds

# In code
for source, url in urls.items():
    # ... fetch logic ...
    time.sleep(d.get("rate_limit_delay", 1.0))
```

### 7. Stale Data Handling
**Change**: Add max_age check when reading cached data
```python
# Add to each category in feeds.json
{"max_age_hours": 24}

# In reading code (separate module needed)
with open(cache_file, "r") as f:
    data = json.load(f)
    age_hours = (time.time() - data["created_at"]) / 3600
    if age_hours > max_age:
        return None  # Trigger refresh
```

### 8. Network Retry Logic
**Change**: Add retry decorator or loop
```python
from time import sleep

def fetch_with_retry(url, max_retries=3, backoff=2):
    for attempt in range(max_retries):
        try:
            return feedparser.parse(url)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            sleep(backoff ** attempt)
```

### 9. Feed URL Validation
**Change**: Validate URLs before fetching
```python
from urllib.parse import urlparse

def validate_feed_url(url):
    parsed = urlparse(url)
    if not all([parsed.scheme in ['http', 'https'], parsed.netloc]):
        raise ValueError(f"Invalid feed URL: {url}")
    return True

# Call before feedparser.parse()
```

### 10. Concurrency
**Change**: Use ThreadPoolExecutor for parallel fetching
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # Extract per-feed logic
    return source, feedparser.parse(url)

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source, result = future.result()
        # Process result
```

### 11. Configurable Timezone
**Change**: Move timezone to feeds.json, read at runtime
```python
# In feeds.json root
{"timezone_offset_hours": 9}

# In config.py
def get_timezone():
    with open(FEEDS_FILE_NAME, "r") as f:
        config = json.load(f)
    offset = config.get("timezone_offset_hours", 0)
    return datetime.timezone(datetime.timedelta(hours=offset))
```

### 12. Entry Limit
**Change**: Add max_entries configuration
```python
# In feeds.json per category
{"max_entries": 100}

# Before writing
rslt = rslt[:d.get("max_entries", 100)]
```

### 13. CLI Argument Parsing
**Change**: Add argparse module
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description="RSS feed aggregator")
    parser.add_argument("--category", help="Update specific category")
    parser.add_argument("--verbose", action="store_true", help="Enable logging")
    args = parser.parse_args()
    
    do(target_category=args.category, log=args.verbose)

if __name__ == "__main__":
    main()
```