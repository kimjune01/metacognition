# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Aggregation**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, with each category containing multiple feed sources defined in a `feeds.json` configuration file.

3. **Feed Management**: 
   - Copies a bundled default `feeds.json` if user doesn't have one
   - Merges new categories from bundled feeds into existing user configuration
   - Preserves user customizations while adding new default categories

4. **Data Extraction**: Extracts key metadata from feeds including:
   - Publication/update timestamps
   - Article titles and URLs
   - Source/author names
   - Formatted publication dates

5. **Timezone Handling**: Converts UTC timestamps to a configured timezone (KST/UTC+9) with smart date formatting (shows time only for today's items, full date otherwise).

6. **Deduplication**: Uses timestamp as ID to prevent duplicate entries when multiple feeds contain the same item.

7. **Chronological Sorting**: Sorts entries by timestamp in reverse chronological order (newest first).

8. **JSON Output**: Writes aggregated feed data to category-specific JSON files in `~/.rreader/` directory.

9. **Selective Updates**: Can update a single category or all categories via the `target_category` parameter.

## Triage

### Critical Gaps (P0)
1. **No Error Handling for Individual Feeds**: `sys.exit()` on feed failure kills the entire process rather than continuing with other feeds
2. **Missing Configuration Validation**: No validation of `feeds.json` structure or URL formats
3. **No Stale Data Handling**: Old cached data never expires or gets flagged as outdated

### High Priority Gaps (P1)
4. **Bare Exception Clauses**: Multiple `except:` blocks catch all exceptions, hiding bugs and making debugging impossible
5. **No HTTP Timeout Configuration**: Feed fetches could hang indefinitely
6. **Missing Logging Infrastructure**: `log` parameter only prints to stdout; no proper logging levels or file output
7. **No Rate Limiting**: Could overwhelm feed servers or trigger rate limiting
8. **Duplicate ID Collision Risk**: Using only timestamp as ID means items published in the same second will overwrite each other

### Medium Priority Gaps (P2)
9. **No Feed Content Storage**: Only metadata is saved; article descriptions/summaries are discarded
10. **No User Agent String**: Polite HTTP clients should identify themselves
11. **Missing Network Error Retry Logic**: Transient network failures cause permanent data loss for that update cycle
12. **No Performance Metrics**: No tracking of fetch times or success rates per feed
13. **No Concurrency**: Sequential fetching is slow for many feeds

### Low Priority Gaps (P3)
14. **No Data Migration Strategy**: Schema changes to JSON format could break existing installations
15. **No Feed Discovery**: Users must manually edit JSON; no UI or command to add feeds
16. **Limited Date Formatting**: Hardcoded format doesn't respect user locale preferences
17. **No Data Cleanup**: Old JSON files never get pruned or archived

## Plan

### P0 Fixes

**1. Graceful Feed Failure Handling**
```python
# Replace sys.exit() with logging and continue
failed_feeds = []
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
    except Exception as e:
        failed_feeds.append((source, url, str(e)))
        if log:
            sys.stdout.write(f" - Failed: {e}\n")
        continue  # Continue processing other feeds
```

**2. Configuration Validation**
```python
# Add validation function at start of do()
def validate_feeds_config(config):
    required_keys = ['feeds']
    for category, data in config.items():
        if not isinstance(data, dict):
            raise ValueError(f"Category {category} must be a dict")
        if 'feeds' not in data:
            raise ValueError(f"Category {category} missing 'feeds' key")
        if not isinstance(data['feeds'], dict):
            raise ValueError(f"Category {category} 'feeds' must be a dict")
        for source, url in data['feeds'].items():
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL for {source}: {url}")
    return True

# Call before processing
validate_feeds_config(RSS)
```

**3. Stale Data Detection**
```python
# Add to JSON output
rslt = {
    "entries": rslt, 
    "created_at": int(time.time()),
    "stale_threshold_seconds": 3600,  # configurable
}

# Add function to check staleness on read
def is_data_stale(data, threshold_seconds=3600):
    age = int(time.time()) - data.get('created_at', 0)
    return age > threshold_seconds
```

### P1 Fixes

**4. Specific Exception Handling**
```python
# Replace all `except:` with specific exceptions
try:
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        continue
    at = (datetime.datetime(*parsed_time[:6])
          .replace(tzinfo=datetime.timezone.utc)
          .astimezone(TIMEZONE))
except (TypeError, ValueError, AttributeError) as e:
    if log:
        sys.stdout.write(f"  Skipping entry due to date parse error: {e}\n")
    continue
```

**5. HTTP Timeout Configuration**
```python
# Add to config.py
REQUEST_TIMEOUT = 30  # seconds

# Modify feedparser call
import socket
socket.setdefaulttimeout(REQUEST_TIMEOUT)
d = feedparser.parse(url)
```

**6. Proper Logging Infrastructure**
```python
# Replace stdout writes with logging module
import logging

logger = logging.getLogger('rreader')

def setup_logging(log_file=None, level=logging.INFO):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    if log_file:
        handler = logging.FileHandler(os.path.join(p["path_data"], 'rreader.log'))
    else:
        handler = logging.StreamHandler()
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(level)

# Replace: sys.stdout.write(f"- {url}")
# With: logger.info(f"Fetching {url} from {source}")
```

**7. Rate Limiting**
```python
# Add to config.py
RATE_LIMIT_DELAY = 0.5  # seconds between requests

# Add to feed fetching loop
import time
for source, url in urls.items():
    time.sleep(RATE_LIMIT_DELAY)
    # ... fetch feed
```

**8. Better ID Generation**
```python
# Replace timestamp-only ID with composite key
import hashlib

entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
entries = {
    "id": entry_id,
    # ... rest of fields
}
rslt[entry_id] = entries
```

### P2 Fixes

**9. Store Feed Content**
```python
# Add to entries dict
entries = {
    "id": entry_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', ''),
    "content": getattr(feed, 'content', [{}])[0].get('value', '') if hasattr(feed, 'content') else '',
}
```

**10. User Agent String**
```python
# Add to config.py
USER_AGENT = 'RReader/1.0 (RSS Feed Aggregator; +https://github.com/yourrepo)'

# Configure feedparser
feedparser.USER_AGENT = USER_AGENT
```

**11. Retry Logic**
```python
# Add retry decorator
from functools import wraps
import time

def retry(max_attempts=3, delay=2, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    logger.warning(f"Attempt {attempt} failed: {e}. Retrying in {current_delay}s")
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator

@retry(max_attempts=3)
def fetch_feed(url):
    return feedparser.parse(url)
```

**12. Performance Metrics**
```python
# Add metrics collection
metrics = {
    'total_feeds': 0,
    'successful_feeds': 0,
    'failed_feeds': 0,
    'total_entries': 0,
    'fetch_times': {},
}

# Wrap fetch with timing
start = time.time()
d = feedparser.parse(url)
fetch_time = time.time() - start
metrics['fetch_times'][source] = fetch_time

# Save metrics with results
rslt["metrics"] = metrics
```

**13. Concurrent Fetching**
```python
# Add concurrent processing
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    # Extract single feed logic
    pass

# Replace loop with concurrent execution
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, source, url, log): source 
               for source, url in urls.items()}
    
    for future in as_completed(futures):
        source = futures[future]
        try:
            result = future.result()
            rslt.update(result)
        except Exception as e:
            logger.error(f"Feed {source} failed: {e}")
```

### P3 Fixes

**14. Data Migration**
```python
# Add version to JSON and migration function
SCHEMA_VERSION = 2

def migrate_data(data):
    version = data.get('schema_version', 1)
    if version < 2:
        # Apply v1 to v2 migration
        data['schema_version'] = 2
    return data

# Apply on read
with open(file_path, 'r') as f:
    data = json.load(f)
    data = migrate_data(data)
```

**15. Feed Discovery CLI**
```python
# Add command-line interface
import argparse

def add_feed_command(category, source_name, url):
    """Add a new feed via command line"""
    with open(FEEDS_FILE_NAME, 'r') as f:
        feeds = json.load(f)
    
    if category not in feeds:
        feeds[category] = {"feeds": {}, "show_author": False}
    
    feeds[category]["feeds"][source_name] = url
    
    with open(FEEDS_FILE_NAME, 'w') as f:
        json.dump(feeds, f, indent=4, ensure_ascii=False)
```

**16. Locale-Aware Formatting**
```python
# Add to config.py
import locale
DATE_FORMAT = "%b %d, %H:%M"  # User configurable
TIME_FORMAT = "%H:%M"

# Use in formatting
pubDate = at.strftime(TIME_FORMAT if at.date() == datetime.date.today() else DATE_FORMAT)
```

**17. Data Cleanup**
```python
# Add cleanup function
def cleanup_old_data(days_to_keep=30):
    """Remove entries older than specified days"""
    cutoff = int(time.time()) - (days_to_keep * 86400)
    
    for file in os.listdir(p["path_data"]):
        if file.startswith("rss_") and file.endswith(".json"):
            path = os.path.join(p["path_data"], file)
            with open(path, 'r') as f:
                data = json.load(f)
            
            data['entries'] = [e for e in data['entries'] if e['timestamp'] > cutoff]
            
            with open(path, 'w') as f:
                json.dump(data, f, ensure_ascii=False)
```