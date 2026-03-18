# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, with each category containing multiple feed sources defined in a `feeds.json` configuration file.

3. **Feed Aggregation**: Combines entries from multiple sources within a category, deduplicates by timestamp, and sorts in reverse chronological order (newest first).

4. **Data Persistence**: Saves parsed feed data as JSON files (`rss_{category}.json`) in a designated data directory (`~/.rreader/`).

5. **Timestamp Handling**: Converts feed publication times to a configured timezone (hardcoded to KST/UTC+9) and formats them for display (shows time for today's posts, date+time for older posts).

6. **Configuration Management**: 
   - Creates data directory if it doesn't exist
   - Copies bundled `feeds.json` if user doesn't have one
   - Merges new categories from bundled feeds into existing user configuration

7. **Optional Author Display**: Supports a `show_author` flag per category to display original author names instead of source names.

8. **Selective Updates**: Can update a single category via `target_category` parameter or all categories if none specified.

9. **Optional Logging**: Basic progress logging to stdout when `log=True`.

## Triage

### Critical Gaps (Must Have)

1. **No Error Handling for Individual Feeds**: A single failed feed takes down the entire category update with `sys.exit()`, preventing other feeds in that category from being processed.

2. **Missing feeds.json Configuration**: The system references `feeds.json` but doesn't include it or document its expected structure.

3. **Silent Failures**: When `log=False`, errors result in `sys.exit(0)`, hiding problems from users and automated systems.

4. **No Data Validation**: No validation of parsed feed data before accessing attributes, leading to potential crashes.

### Important Gaps (Should Have)

5. **No Caching/Conditional Requests**: Fetches entire feeds every time, wasting bandwidth and being a poor RSS citizen (no ETags, Last-Modified headers).

6. **No Rate Limiting**: Could hammer feed servers if run too frequently or with many feeds.

7. **No Timeout Configuration**: Network requests could hang indefinitely.

8. **Duplicate Entry Detection Flaw**: Uses only timestamp as ID, causing collisions when multiple articles are published at the same second.

9. **No Stale Data Handling**: Old cached JSON files persist indefinitely; no indication if data is outdated.

10. **Hardcoded Timezone**: TIMEZONE is hardcoded to KST instead of being user-configurable.

### Nice to Have

11. **No Incremental Updates**: Always rewrites entire category files even when only one feed has new content.

12. **No Feed Health Monitoring**: No tracking of which feeds consistently fail or are slow.

13. **No Concurrent Fetching**: Fetches feeds sequentially, making updates slow for categories with many sources.

14. **Missing CLI Interface**: No argument parsing for command-line usage beyond programmatic calls.

15. **No Feed Metadata**: Doesn't store feed description, icon, or other useful metadata.

## Plan

### 1. Error Handling for Individual Feeds

**Current Problem**: `sys.exit()` terminates the entire program on feed failure.

**Changes Needed**:
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            d = feedparser.parse(url)
            if log:
                sys.stdout.write(" - Done\n")
                
            # Process entries here...
            
        except Exception as e:
            error_msg = f"Failed to fetch {source} ({url}): {str(e)}"
            errors.append(error_msg)
            if log:
                sys.stderr.write(f" - Failed: {str(e)}\n")
            continue  # Continue to next feed instead of exiting
    
    # Add error tracking to saved JSON
    rslt = {
        "entries": [val for key, val in sorted(rslt.items(), reverse=True)],
        "created_at": int(time.time()),
        "errors": errors
    }
```

### 2. Include Sample feeds.json Configuration

**Current Problem**: System depends on undefined configuration file structure.

**Changes Needed**:
- Create `feeds.json.example` in the package:
```json
{
    "tech": {
        "feeds": {
            "Hacker News": "https://news.ycombinator.com/rss",
            "TechCrunch": "https://techcrunch.com/feed/"
        },
        "show_author": false
    },
    "blogs": {
        "feeds": {
            "Example Blog": "https://example.com/feed.xml"
        },
        "show_author": true
    }
}
```
- Add documentation explaining the structure
- Update `bundled_feeds_file` to point to this example

### 3. Proper Exception Handling and Logging

**Current Problem**: Silent failures hide issues; no structured logging.

**Changes Needed**:
```python
import logging

# At module level
logger = logging.getLogger(__name__)

def do(target_category=None, log=False):
    # Configure logging
    if log:
        logging.basicConfig(level=logging.INFO, 
                          format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Replace sys.stdout.write with logger.info()
    # Replace sys.stderr.write with logger.error()
    # Remove all sys.exit() calls
```

### 4. Data Validation

**Current Problem**: Direct attribute access without checking existence.

**Changes Needed**:
```python
for feed in d.entries:
    # Validate required fields
    if not hasattr(feed, 'link') or not hasattr(feed, 'title'):
        logger.warning(f"Skipping malformed entry from {source}")
        continue
    
    try:
        parsed_time = getattr(feed, 'published_parsed', None) or \
                     getattr(feed, 'updated_parsed', None)
        if not parsed_time or len(parsed_time) < 6:
            logger.warning(f"Skipping entry without valid timestamp: {feed.title}")
            continue
        # Continue processing...
    except (TypeError, ValueError) as e:
        logger.warning(f"Invalid data in entry from {source}: {e}")
        continue
```

### 5. Implement HTTP Caching

**Current Problem**: No conditional requests waste bandwidth.

**Changes Needed**:
```python
# Add cache storage to saved JSON
cache_data = {
    "entries": rslt,
    "created_at": int(time.time()),
    "etag": {},  # Store per-feed ETags
    "last_modified": {}  # Store per-feed Last-Modified
}

# Modify fetch logic
import urllib.request

def fetch_with_cache(url, etag=None, last_modified=None):
    request = urllib.request.Request(url)
    if etag:
        request.add_header('If-None-Match', etag)
    if last_modified:
        request.add_header('If-Modified-Since', last_modified)
    
    # Use feedparser with prepared request
    d = feedparser.parse(url, etag=etag, modified=last_modified)
    
    return d, d.get('etag'), d.get('modified')
```

### 6. Add Rate Limiting

**Current Problem**: No protection against hammering feed servers.

**Changes Needed**:
```python
import time

# Add to config.py
RATE_LIMIT_DELAY = 1.0  # seconds between requests

# In get_feed_from_rss()
for i, (source, url) in enumerate(urls.items()):
    if i > 0:  # Don't delay before first request
        time.sleep(RATE_LIMIT_DELAY)
    # ... fetch feed
```

### 7. Add Network Timeout Configuration

**Current Problem**: Requests can hang indefinitely.

**Changes Needed**:
```python
# In config.py
FEED_TIMEOUT = 30  # seconds

# Modify feedparser calls
d = feedparser.parse(url, timeout=FEED_TIMEOUT)
```

### 8. Fix Duplicate Entry Detection

**Current Problem**: Timestamp-only IDs cause collisions.

**Changes Needed**:
```python
import hashlib

# Generate unique ID combining timestamp and URL
entry_id = hashlib.md5(f"{ts}:{feed.link}".encode()).hexdigest()

entries = {
    "id": entry_id,
    "timestamp": ts,  # Keep timestamp for sorting
    # ... rest of fields
}

rslt[entries["id"]] = entries
```

### 9. Implement Stale Data Detection

**Current Problem**: No indication when cached data is old.

**Changes Needed**:
```python
# In config.py
MAX_CACHE_AGE = 3600  # seconds (1 hour)

# When reading cached data
def is_cache_stale(cache_file):
    if not os.path.exists(cache_file):
        return True
    
    mtime = os.path.getmtime(cache_file)
    age = time.time() - mtime
    return age > MAX_CACHE_AGE

# Add cache_age to returned data
rslt = {
    "entries": entries,
    "created_at": created_at,
    "cache_age": int(time.time() - created_at),
    "is_stale": (time.time() - created_at) > MAX_CACHE_AGE
}
```

### 10. Make Timezone Configurable

**Current Problem**: Hardcoded KST timezone.

**Changes Needed**:
```python
# In config.py
import os

# Allow environment variable override
TIMEZONE_OFFSET = int(os.getenv('RREADER_TZ_OFFSET', '9'))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET))

# Or use system timezone
# import tzlocal
# TIMEZONE = tzlocal.get_localzone()
```

### 11. Add Concurrent Fetching

**Current Problem**: Sequential fetching is slow.

**Changes Needed**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    def fetch_single_feed(source, url):
        # Move feed fetching logic here
        # Return (source, entries_dict) or (source, None) on error
        pass
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_source = {
            executor.submit(fetch_single_feed, source, url): source 
            for source, url in urls.items()
        }
        
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                source, entries = future.result()
                if entries:
                    rslt.update(entries)
            except Exception as e:
                logger.error(f"Feed {source} failed: {e}")
```

### 12. Add CLI Interface

**Current Problem**: No user-friendly command-line interface.

**Changes Needed**:
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('-c', '--category', help='Update specific category')
    parser.add_argument('-v', '--verbose', action='store_true', 
                       help='Enable verbose logging')
    parser.add_argument('-l', '--list', action='store_true',
                       help='List available categories')
    
    args = parser.parse_args()
    
    if args.list:
        # List categories from feeds.json
        pass
    else:
        do(target_category=args.category, log=args.verbose)

if __name__ == "__main__":
    main()
```

### 13. Add Feed Health Monitoring

**Current Problem**: No visibility into feed reliability.

**Changes Needed**:
```python
# Create separate health tracking file
health_file = os.path.join(p["path_data"], "feed_health.json")

def update_feed_health(source, url, success, response_time):
    # Load existing health data
    # Update statistics: success_rate, avg_response_time, last_success, last_failure
    # Save back to file
    pass

# Add health tracking to each feed fetch
start_time = time.time()
try:
    d = feedparser.parse(url)
    response_time = time.time() - start_time
    update_feed_health(source, url, True, response_time)
except Exception as e:
    response_time = time.time() - start_time
    update_feed_health(source, url, False, response_time)
```