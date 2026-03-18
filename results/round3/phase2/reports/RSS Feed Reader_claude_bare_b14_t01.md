# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds from multiple sources using the `feedparser` library.

2. **Feed Aggregation**: Combines entries from multiple feed URLs within categories, deduplicating by timestamp-based ID.

3. **Time Normalization**: Converts feed timestamps to a configured timezone (currently KST/UTC+9) and formats them as either "HH:MM" (for today) or "Mon DD, HH:MM" (for other dates).

4. **JSON Storage**: Persists parsed feeds to JSON files named `rss_{category}.json` in a data directory (`~/.rreader/`).

5. **Feed Configuration Management**: 
   - Copies a bundled `feeds.json` template if user config doesn't exist
   - Merges new categories from bundled config into existing user config
   - Supports per-category `show_author` flag to toggle between source name and feed author

6. **Entry Structure**: Standardizes feed entries with: id, sourceName, pubDate, timestamp, url, and title fields.

7. **Selective Processing**: Can process either a single category or all categories via the `target_category` parameter.

8. **Directory Initialization**: Automatically creates the data directory if it doesn't exist.

## Triage

### Critical Gaps
1. **No Error Handling**: The try-except blocks either exit the program or silently skip errors with no logging.
2. **Feed Configuration Validation**: No validation that `feeds.json` exists or is properly formatted.
3. **Network Timeout Configuration**: No timeout settings for RSS fetching, risking indefinite hangs.

### High Priority Gaps
4. **No Caching/Conditional Requests**: Refetches entire feeds every time, wasting bandwidth and potentially hitting rate limits.
5. **Duplicate ID Collisions**: Using only timestamp as ID means feeds published in the same second will overwrite each other.
6. **No Logging Framework**: Uses print statements and has inconsistent logging behavior (log parameter barely used).
7. **No Feed Validation**: Doesn't verify that parsed feeds have required fields before accessing them.

### Medium Priority Gaps
8. **No Concurrency**: Processes feeds sequentially, making it slow with many feeds.
9. **No Data Retention Policy**: Old JSON files accumulate indefinitely with no cleanup mechanism.
10. **Configuration Hardcoded**: Timezone and paths have no runtime configuration mechanism.
11. **No User Feedback**: When running without `log=True`, operations are completely silent.

### Low Priority Gaps
12. **No Feed Metadata**: Doesn't store feed-level information (description, icon, last-modified headers).
13. **No Entry Content**: Only stores title/url, not the actual content/summary.
14. **Incomplete Import Handling**: The try-except import suggests package/module usage but isn't fully implemented.
15. **No Testing Infrastructure**: No unit tests or test fixtures.

## Plan

### 1. Error Handling (Critical)
**Changes needed:**
- Replace bare `except:` clauses with specific exception types (`feedparser.FeedParserError`, `requests.exceptions.RequestException`, etc.)
- Add proper logging using Python's `logging` module instead of `sys.stdout.write`
- Create an error accumulation structure to report all failures at the end rather than exiting immediately
- Add validation for dictionary key access (e.g., check if `d.entries` exists before iterating)

```python
import logging
logger = logging.getLogger(__name__)

# In get_feed_from_rss:
failed_feeds = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        if d.bozo:  # feedparser's error flag
            logger.warning(f"Feed {url} has errors: {d.bozo_exception}")
    except (urllib.error.URLError, socket.timeout) as e:
        logger.error(f"Failed to fetch {url}: {e}")
        failed_feeds.append((source, url, str(e)))
        continue
```

### 2. Feed Configuration Validation (Critical)
**Changes needed:**
- Add JSON schema validation for `feeds.json` structure
- Verify required keys exist (`feeds`, optionally `show_author`)
- Validate URLs are well-formed before attempting to fetch
- Provide clear error messages indicating which part of config is malformed

```python
def validate_feeds_config(config):
    """Validate feeds.json structure."""
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a JSON object")
    
    for category, data in config.items():
        if "feeds" not in data:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category '{category}' feeds must be a dictionary")
        for source, url in data["feeds"].items():
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL for {source}: {url}")
```

### 3. Network Timeout Configuration (Critical)
**Changes needed:**
- Add timeout parameter to `feedparser.parse()` calls
- Make timeout configurable via config.py
- Add retry logic with exponential backoff for transient failures

```python
# In config.py:
FEED_TIMEOUT = 30  # seconds

# In get_feed_from_rss:
d = feedparser.parse(url, timeout=FEED_TIMEOUT)
```

### 4. Caching/Conditional Requests (High Priority)
**Changes needed:**
- Store `ETag` and `Last-Modified` headers from feed responses
- Send these headers in subsequent requests
- Only reprocess feeds if content has changed (304 Not Modified)
- Add cache metadata to JSON output files

```python
# Store in cache file:
cache = {
    "url": url,
    "etag": d.get("etag"),
    "modified": d.get("modified"),
    "last_fetch": time.time()
}

# Use in requests:
d = feedparser.parse(url, etag=cache.get("etag"), modified=cache.get("modified"))
if d.status == 304:
    # Use cached data
    continue
```

### 5. Duplicate ID Collision Prevention (High Priority)
**Changes needed:**
- Generate IDs using hash of (timestamp + url + title) instead of just timestamp
- Add collision detection and append suffix if ID exists
- Consider using UUID or content hash for truly unique IDs

```python
import hashlib

def generate_entry_id(timestamp, url, title):
    """Generate unique ID from entry attributes."""
    content = f"{timestamp}:{url}:{title}"
    hash_suffix = hashlib.md5(content.encode()).hexdigest()[:8]
    return f"{timestamp}_{hash_suffix}"
```

### 6. Logging Framework (High Priority)
**Changes needed:**
- Replace all `sys.stdout.write` and print statements with `logging` calls
- Add log levels (DEBUG, INFO, WARNING, ERROR)
- Configure log output to both file and console
- Remove the `log` parameter in favor of logger configuration

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Usage:
logger.info(f"Fetching feed: {url}")
logger.debug(f"Parsed {len(d.entries)} entries")
logger.error(f"Failed to parse feed: {e}")
```

### 7. Feed Validation (High Priority)
**Changes needed:**
- Check that required fields exist before accessing them
- Provide defaults for missing optional fields
- Validate that timestamps are parseable before using them

```python
def extract_entry_data(feed, source, show_author):
    """Safely extract entry data with validation."""
    # Validate required fields
    if not hasattr(feed, 'link') or not hasattr(feed, 'title'):
        logger.debug(f"Skipping entry missing required fields from {source}")
        return None
    
    # Extract timestamp with fallback
    parsed_time = getattr(feed, 'published_parsed', None) or \
                  getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        logger.debug(f"Skipping entry without timestamp: {feed.title}")
        return None
    
    # ... rest of extraction logic
```

### 8. Concurrency (Medium Priority)
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` to fetch multiple feeds simultaneously
- Add configurable max_workers parameter
- Maintain thread-safe data structures for results

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, show_author):
    """Fetch and parse a single feed."""
    # Move feed parsing logic here
    pass

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_source = {
            executor.submit(fetch_single_feed, source, url, show_author): source
            for source, url in urls.items()
        }
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                entries = future.result()
                rslt.update(entries)
            except Exception as e:
                logger.error(f"Failed to fetch {source}: {e}")
```

### 9. Data Retention Policy (Medium Priority)
**Changes needed:**
- Add configuration for max age of entries to keep
- Implement cleanup function to remove old entries from JSON files
- Add option to archive rather than delete old data

```python
# In config.py:
MAX_ENTRY_AGE_DAYS = 30

# In do():
def clean_old_entries(entries, max_age_days):
    """Remove entries older than max_age_days."""
    cutoff = time.time() - (max_age_days * 86400)
    return [e for e in entries if e["timestamp"] > cutoff]
```

### 10. Runtime Configuration (Medium Priority)
**Changes needed:**
- Accept timezone as parameter or environment variable
- Make data path configurable via environment variable
- Add command-line argument parsing for common options

```python
import argparse

def get_config():
    """Load configuration from environment and defaults."""
    return {
        "data_path": os.getenv("RREADER_DATA_PATH", str(Path.home()) + "/.rreader/"),
        "timezone_offset": int(os.getenv("RREADER_TZ_OFFSET", "9")),
        "timeout": int(os.getenv("RREADER_TIMEOUT", "30"))
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RSS Feed Reader")
    parser.add_argument("--category", help="Process specific category")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
```

### 11. User Feedback (Medium Priority)
**Changes needed:**
- Always provide minimal output (summary statistics)
- Add progress indicators for long operations
- Report success/failure counts at completion

```python
logger.info(f"Processing {len(urls)} feeds in category '{category}'")
# ... processing ...
logger.info(f"Completed: {success_count} succeeded, {failed_count} failed, {total_entries} entries")
```

### 12-15. Lower Priority Improvements
These can be addressed iteratively:
- **Feed Metadata**: Add `feed_info` dict to JSON with title, description, icon URL
- **Entry Content**: Add `summary` and `content` fields to entry structure
- **Import Handling**: Properly package with `__init__.py` and explicit relative imports
- **Testing**: Add `tests/` directory with pytest fixtures for sample feeds