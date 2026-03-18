# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Organization**: Supports organizing feeds into categories, with each category containing multiple feed sources.

3. **Feed Configuration Management**: 
   - Stores feed configurations in a JSON file (`feeds.json`)
   - Copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration without overwriting existing customizations

4. **Data Extraction**: Extracts key metadata from feed entries:
   - Publication/update timestamps
   - Article titles and URLs
   - Source/author names
   - Formatted publication dates

5. **Timezone Localization**: Converts UTC timestamps to a configured timezone (currently KST/UTC+9).

6. **Date Formatting**: Shows time-only for today's articles, full date+time for older ones.

7. **Deduplication**: Uses timestamp as unique ID to prevent duplicate entries within a category.

8. **Persistent Storage**: Saves parsed feeds as JSON files (one per category) in `~/.rreader/`.

9. **Selective Updates**: Can update a single category or all categories.

10. **Basic Logging**: Optional progress logging to stdout.

## Triage

### Critical Gaps (Production Blockers)

1. **No Error Handling**: System exits on any feed failure rather than continuing with remaining feeds
2. **Missing Configuration Validation**: No validation of feeds.json structure or URL formats
3. **No Rate Limiting**: Could overwhelm feed servers or get rate-limited/banned
4. **Hardcoded Timezone**: Configuration isn't user-configurable at runtime

### High Priority (Reliability Issues)

5. **No Retry Logic**: Transient network failures cause permanent data loss for that update cycle
6. **No Timeout Configuration**: Network requests could hang indefinitely
7. **Collision Risk**: Using timestamp as ID causes collisions when feeds publish multiple articles at once
8. **No Cache Headers**: Doesn't respect ETags or Last-Modified headers, wasting bandwidth
9. **Silent Failures**: Exception handling swallows errors without recording what went wrong

### Medium Priority (Usability/Maintenance)

10. **No Feed Health Monitoring**: No way to know which feeds are consistently failing
11. **Missing User Agent**: Doesn't identify itself properly to feed servers
12. **No Encoding Handling**: Assumes UTF-8 everywhere without fallbacks
13. **No Data Migration**: Version updates to data format would break existing installations
14. **Limited Date Parsing**: Relies on feedparser exclusively, no fallback for malformed dates
15. **No Concurrency**: Sequential processing is slow with many feeds

### Low Priority (Nice-to-Have)

16. **No Feed Discovery**: Can't auto-detect feeds from website URLs
17. **No OPML Import/Export**: Standard RSS format not supported
18. **Limited Logging**: No log levels, rotation, or file-based logging
19. **No Statistics**: No tracking of update frequency, article counts, etc.

## Plan

### 1. Error Handling (Critical)

**Change Required**: Replace `sys.exit()` with proper exception handling and continuation logic.

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
        except Exception as e:
            error_msg = f"Failed to fetch {url}: {str(e)}"
            errors.append(error_msg)
            if log:
                sys.stderr.write(f" - {error_msg}\n")
            continue  # Continue with next feed
        
        # Process entries with individual try-catch blocks
        for feed in d.entries:
            try:
                # existing processing logic
                pass
            except Exception as e:
                if log:
                    sys.stderr.write(f"Error processing entry from {source}: {str(e)}\n")
                continue
    
    # Save errors to metadata
    rslt["errors"] = errors
    rslt["success_count"] = len([v for v in rslt.values() if isinstance(v, dict)])
```

### 2. Configuration Validation (Critical)

**Change Required**: Add JSON schema validation at load time.

```python
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {
                        ".*": {"type": "string", "format": "uri"}
                    }
                },
                "show_author": {"type": "boolean"}
            }
        }
    }
}

def load_feeds():
    with open(FEEDS_FILE_NAME, "r") as fp:
        feeds = json.load(fp)
    
    try:
        jsonschema.validate(feeds, FEEDS_SCHEMA)
    except jsonschema.ValidationError as e:
        sys.stderr.write(f"Invalid feeds.json: {e.message}\n")
        sys.exit(1)
    
    return feeds
```

### 3. Rate Limiting (Critical)

**Change Required**: Add delays between requests and respect robots.txt.

```python
import time
from urllib.robotparser import RobotFileParser

# At module level
REQUEST_DELAY = 1.0  # seconds between requests
last_request_time = {}

def rate_limited_parse(url):
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    
    # Wait if we've recently hit this domain
    if domain in last_request_time:
        elapsed = time.time() - last_request_time[domain]
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)
    
    result = feedparser.parse(url)
    last_request_time[domain] = time.time()
    return result
```

### 4. Configurable Timezone (Critical)

**Change Required**: Move timezone to feeds.json and provide fallback.

```python
# In do() function
def load_timezone():
    try:
        with open(FEEDS_FILE_NAME, "r") as fp:
            config = json.load(fp)
        tz_offset = config.get("_settings", {}).get("timezone_offset", 9)
        return datetime.timezone(datetime.timedelta(hours=tz_offset))
    except:
        return datetime.timezone(datetime.timedelta(hours=9))  # Default KST

TIMEZONE = load_timezone()
```

### 5. Retry Logic (High Priority)

**Change Required**: Add exponential backoff for transient failures.

```python
from urllib.error import URLError
import socket

MAX_RETRIES = 3
BACKOFF_FACTOR = 2

def fetch_with_retry(url, retries=MAX_RETRIES):
    for attempt in range(retries):
        try:
            return feedparser.parse(url)
        except (URLError, socket.timeout, ConnectionError) as e:
            if attempt == retries - 1:
                raise
            wait_time = BACKOFF_FACTOR ** attempt
            time.sleep(wait_time)
    return None
```

### 6. Timeout Configuration (High Priority)

**Change Required**: Set socket timeout for all HTTP requests.

```python
import socket

# At module level
DEFAULT_TIMEOUT = 30  # seconds

# Before any feedparser.parse() call
socket.setdefaulttimeout(DEFAULT_TIMEOUT)

# Or pass to feedparser if supported
d = feedparser.parse(url, timeout=DEFAULT_TIMEOUT)
```

### 7. Unique ID Generation (High Priority)

**Change Required**: Use content-based hashing instead of timestamp.

```python
import hashlib

def generate_entry_id(feed, source):
    # Combine multiple fields to create unique ID
    unique_string = f"{feed.link}|{feed.title}|{source}"
    return hashlib.sha256(unique_string.encode()).hexdigest()[:16]

# In processing loop
entries = {
    "id": generate_entry_id(feed, source),
    "timestamp": ts,
    # ... rest of fields
}

rslt[entries["id"]] = entries
```

### 8. Cache Headers Support (High Priority)

**Change Required**: Store and use ETags/Last-Modified headers.

```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    # Load previous cache metadata
    cache_file = os.path.join(p["path_data"], f"cache_{category}.json")
    cache_data = {}
    if os.path.exists(cache_file):
        with open(cache_file, "r") as f:
            cache_data = json.load(f)
    
    for source, url in urls.items():
        # Pass etag and modified to feedparser
        etag = cache_data.get(url, {}).get("etag")
        modified = cache_data.get(url, {}).get("modified")
        
        d = feedparser.parse(url, etag=etag, modified=modified)
        
        # Update cache
        if hasattr(d, 'etag'):
            cache_data.setdefault(url, {})["etag"] = d.etag
        if hasattr(d, 'modified'):
            cache_data.setdefault(url, {})["modified"] = d.modified
    
    # Save cache
    with open(cache_file, "w") as f:
        json.dump(cache_data, f)
```

### 9. Error Logging (High Priority)

**Change Required**: Maintain error log with timestamps.

```python
def log_error(category, source, error, error_type="fetch"):
    error_log_file = os.path.join(p["path_data"], "errors.log")
    timestamp = datetime.datetime.now().isoformat()
    log_entry = f"{timestamp}|{category}|{source}|{error_type}|{error}\n"
    
    with open(error_log_file, "a", encoding="utf-8") as f:
        f.write(log_entry)
```

### 10. Feed Health Monitoring (Medium Priority)

**Change Required**: Track success/failure rates per feed.

```python
def update_feed_health(url, success):
    health_file = os.path.join(p["path_data"], "feed_health.json")
    health_data = {}
    
    if os.path.exists(health_file):
        with open(health_file, "r") as f:
            health_data = json.load(f)
    
    if url not in health_data:
        health_data[url] = {"attempts": 0, "successes": 0, "last_success": None}
    
    health_data[url]["attempts"] += 1
    if success:
        health_data[url]["successes"] += 1
        health_data[url]["last_success"] = int(time.time())
    
    with open(health_file, "w") as f:
        json.dump(health_data, f)
```

### 11. User Agent (Medium Priority)

**Change Required**: Set proper User-Agent header.

```python
# Feedparser respects this
feedparser.USER_AGENT = "RReader/1.0 (+https://github.com/yourusername/rreader)"
```

### 12. Encoding Handling (Medium Priority)

**Change Required**: Add encoding detection and fallback.

```python
import chardet

def safe_json_dump(data, filepath):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False))
    except UnicodeEncodeError:
        # Fallback to ASCII-safe
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=True))
```

### 13. Data Migration (Medium Priority)

**Change Required**: Version data files and provide migration path.

```python
DATA_VERSION = 2

def migrate_data():
    version_file = os.path.join(p["path_data"], "version.txt")
    current_version = 1
    
    if os.path.exists(version_file):
        with open(version_file, "r") as f:
            current_version = int(f.read().strip())
    
    if current_version < DATA_VERSION:
        # Run migrations
        if current_version < 2:
            migrate_v1_to_v2()
        
        with open(version_file, "w") as f:
            f.write(str(DATA_VERSION))

def migrate_v1_to_v2():
    # Example: convert timestamp IDs to hash IDs
    pass
```

### 14-19. Lower Priority Items

These can be addressed incrementally:

- **Feed Discovery**: Add `discover_feed(url)` function using feedfinder2 library
- **OPML Support**: Add `import_opml()` and `export_opml()` functions
- **Advanced Logging**: Integrate Python's logging module with file rotation
- **Statistics**: Add `get_stats(category)` function to calculate metrics
- **Date Parsing Fallback**: Add dateutil.parser as backup
- **Concurrency**: Use `concurrent.futures.ThreadPoolExecutor` for parallel fetching