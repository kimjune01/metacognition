# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a basic RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-source Aggregation**: Processes feeds organized by categories, each containing multiple feed URLs
3. **Deduplication**: Uses timestamp-based IDs to deduplicate entries across sources
4. **Time Formatting**: Converts feed timestamps to local timezone (KST/UTC+9) with human-readable formatting
5. **Data Persistence**: Saves parsed feed data as JSON files (one per category) in `~/.rreader/`
6. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled config into user config
7. **Selective Processing**: Can process all categories or target a specific one
8. **Author Attribution**: Supports optional author display per category configuration
9. **Timestamp Tracking**: Records when each feed collection was created

## Triage

### Critical Gaps (Must Have)
1. **Error Handling**: Minimal error recovery; failed feeds abort silently
2. **HTTP Robustness**: No timeout configuration, retry logic, or rate limiting
3. **Feed Validation**: No validation that parsed feeds contain expected data structures
4. **Concurrency**: Sequential processing means slow feeds block everything

### High Priority (Should Have)
5. **Logging**: Uses print statements instead of proper logging infrastructure
6. **Stale Data Management**: No TTL or cleanup of old cached feeds
7. **Entry Uniqueness**: Uses only timestamp as ID, causing collisions for simultaneous posts
8. **Configuration Validation**: No schema validation for feeds.json structure
9. **Data Migration**: No versioning or migration path for breaking changes

### Medium Priority (Nice to Have)
10. **Performance Optimization**: No conditional GET (ETags/Last-Modified) support
11. **User Feedback**: No progress indication for long-running operations
12. **Content Sanitization**: No HTML cleaning or security filtering of feed content
13. **Incremental Updates**: Always fetches entire feeds instead of deltas
14. **Extensibility**: Hard-coded for RSS/Atom; no plugin architecture

### Low Priority (Enhancement)
15. **Testing**: No unit tests or integration tests
16. **Documentation**: Missing docstrings and usage examples
17. **CLI Interface**: No argument parsing for user-friendly invocation
18. **Monitoring**: No metrics on feed health or fetch success rates

## Plan

### 1. Error Handling
**Current Issue**: `try/except` blocks catch all exceptions without logging; `sys.exit()` kills entire process on single feed failure.

**Changes Needed**:
```python
import logging
from typing import Dict, List, Optional

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            if log:
                logging.info(f"Fetching {url}")
            d = feedparser.parse(url)
            
            # Validate feed has entries
            if not hasattr(d, 'entries'):
                errors.append(f"{source}: Invalid feed structure")
                continue
                
            if d.bozo and d.bozo_exception:
                logging.warning(f"{source}: Parse warning - {d.bozo_exception}")
                
        except Exception as e:
            logging.error(f"{source}: Failed to fetch - {str(e)}")
            errors.append(f"{source}: {str(e)}")
            continue  # Don't kill entire process
    
    # Store errors in output for monitoring
    rslt_metadata = {
        "entries": [...],
        "created_at": int(time.time()),
        "fetch_errors": errors,
        "feeds_attempted": len(urls),
        "feeds_successful": len(urls) - len(errors)
    }
```

### 2. HTTP Robustness
**Current Issue**: No timeout means hung connections block indefinitely; no retry logic for transient failures.

**Changes Needed**:
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Add at module level
def create_session():
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

SESSION = create_session()

# In get_feed_from_rss:
d = feedparser.parse(url, request_headers={
    'User-Agent': 'rreader/1.0',
    'Timeout': '10'  # 10 second timeout
})
```

### 3. Feed Validation
**Current Issue**: Silent failures when feeds lack required fields; `getattr` with defaults masks data issues.

**Changes Needed**:
```python
def validate_entry(feed_entry, source) -> Optional[Dict]:
    """Validate and extract required fields from feed entry."""
    
    # Required field: link
    if not hasattr(feed_entry, 'link') or not feed_entry.link:
        logging.warning(f"{source}: Entry missing link")
        return None
    
    # Required field: title
    if not hasattr(feed_entry, 'title') or not feed_entry.title:
        logging.warning(f"{source}: Entry missing title")
        return None
    
    # Required field: timestamp
    parsed_time = getattr(feed_entry, 'published_parsed', None) or \
                  getattr(feed_entry, 'updated_parsed', None)
    if not parsed_time:
        logging.warning(f"{source}: Entry missing timestamp")
        return None
    
    return {
        'link': feed_entry.link,
        'title': feed_entry.title,
        'parsed_time': parsed_time
    }

# Use in loop:
for feed in d.entries:
    validated = validate_entry(feed, source)
    if not validated:
        continue
    # Process validated data...
```

### 4. Concurrency
**Current Issue**: Sequential processing makes total runtime = sum of all feed fetch times.

**Changes Needed**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

def fetch_single_feed(source: str, url: str, show_author: bool) -> Tuple[str, List[Dict]]:
    """Fetch and parse a single feed. Returns (source, entries)."""
    try:
        d = feedparser.parse(url)
        entries = []
        for feed in d.entries:
            validated = validate_entry(feed, source)
            if validated:
                # ... process entry
                entries.append(entry_dict)
        return (source, entries)
    except Exception as e:
        logging.error(f"{source}: {e}")
        return (source, [])

def get_feed_from_rss(category, urls, show_author=False, log=False):
    all_entries = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_single_feed, source, url, show_author): source
            for source, url in urls.items()
        }
        
        for future in as_completed(futures):
            source, entries = future.result()
            for entry in entries:
                all_entries[entry['id']] = entry
    
    # Continue with deduplication and saving...
```

### 5. Logging
**Current Issue**: Mix of `print`, `sys.stdout.write`, and no structured logging.

**Changes Needed**:
```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(log_dir: str):
    """Configure logging to file and console."""
    log_file = os.path.join(log_dir, 'rreader.log')
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

# Call in do():
setup_logging(p["path_data"])

# Replace all print/write:
logging.info(f"Fetching {url}")
logging.error(f"Failed to fetch {url}")
```

### 6. Stale Data Management
**Current Issue**: JSON files grow indefinitely; no cleanup of old entries.

**Changes Needed**:
```python
MAX_ENTRIES_PER_FEED = 100
MAX_AGE_DAYS = 30

def prune_old_entries(entries: List[Dict]) -> List[Dict]:
    """Remove entries older than MAX_AGE_DAYS and limit total count."""
    cutoff_timestamp = int(time.time()) - (MAX_AGE_DAYS * 86400)
    
    # Filter by age
    recent = [e for e in entries if e['timestamp'] > cutoff_timestamp]
    
    # Limit count
    return recent[:MAX_ENTRIES_PER_FEED]

# Before saving:
rslt = {
    "entries": prune_old_entries(sorted_entries),
    "created_at": int(time.time())
}
```

### 7. Entry Uniqueness
**Current Issue**: Timestamp-only ID causes collisions for feeds posted at same second.

**Changes Needed**:
```python
import hashlib

def generate_entry_id(url: str, timestamp: int, title: str) -> str:
    """Generate unique ID from URL, timestamp, and title."""
    content = f"{url}|{timestamp}|{title}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

# In entry creation:
entries = {
    "id": generate_entry_id(feed.link, ts, feed.title),
    "sourceName": author,
    # ... rest of fields
}
```

### 8. Configuration Validation
**Current Issue**: No validation of feeds.json structure; malformed config causes cryptic errors.

**Changes Needed**:
```python
from typing import Dict, Any
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

def load_and_validate_config(config_path: str) -> Dict[str, Any]:
    """Load feeds.json and validate against schema."""
    try:
        with open(config_path, "r") as fp:
            config = json.load(fp)
        jsonschema.validate(config, FEEDS_SCHEMA)
        return config
    except jsonschema.ValidationError as e:
        logging.error(f"Invalid feeds.json: {e.message}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logging.error(f"Malformed JSON in feeds.json: {e}")
        sys.exit(1)

# Use instead of direct json.load:
RSS = load_and_validate_config(FEEDS_FILE_NAME)
```

### 9. Data Migration
**Current Issue**: No version field; breaking changes to JSON format have no migration path.

**Changes Needed**:
```python
CURRENT_DATA_VERSION = 2

def migrate_feed_data(data: Dict, from_version: int) -> Dict:
    """Migrate feed data to current version."""
    if from_version == 1:
        # v1 -> v2: Add entry IDs based on hash instead of timestamp
        for entry in data.get('entries', []):
            if 'id' in entry and isinstance(entry['id'], int):
                entry['id'] = generate_entry_id(
                    entry['url'], entry['timestamp'], entry['title']
                )
        data['version'] = 2
    return data

def load_feed_data(category: str) -> Dict:
    """Load and migrate feed data if needed."""
    path = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(path):
        return {"entries": [], "created_at": int(time.time()), "version": CURRENT_DATA_VERSION}
    
    with open(path, "r") as f:
        data = json.load(f)
    
    version = data.get('version', 1)
    if version < CURRENT_DATA_VERSION:
        data = migrate_feed_data(data, version)
    
    return data
```

### 10. Performance Optimization
**Current Issue**: Always fetches full feeds even when unchanged; wastes bandwidth and time.

**Changes Needed**:
```python
import pickle

ETAG_CACHE_FILE = os.path.join(p["path_data"], "etag_cache.pkl")

def load_etag_cache() -> Dict[str, Dict]:
    """Load cached ETags and Last-Modified headers."""
    if os.path.exists(ETAG_CACHE_FILE):
        with open(ETAG_CACHE_FILE, 'rb') as f:
            return pickle.load(f)
    return {}

def save_etag_cache(cache: Dict):
    """Save ETag cache."""
    with open(ETAG_CACHE_FILE, 'wb') as f:
        pickle.dump(cache, f)

def fetch_with_cache(url: str, cache: Dict) -> Optional[feedparser.FeedParserDict]:
    """Fetch feed with conditional GET if cached."""
    headers = {}
    cache_entry = cache.get(url, {})
    
    if 'etag' in cache_entry:
        headers['If-None-Match'] = cache_entry['etag']
    if 'modified' in cache_entry:
        headers['If-Modified-Since'] = cache_entry['modified']
    
    d = feedparser.parse(url, request_headers=headers)
    
    # 304 Not Modified
    if d.status == 304:
        logging.info(f"Feed unchanged: {url}")
        return None
    
    # Update cache
    cache[url] = {}
    if hasattr(d, 'etag'):
        cache[url]['etag'] = d.etag
    if hasattr(d, 'modified'):
        cache[url]['modified'] = d.modified
    
    return d
```

### 11-17. Additional Improvements

For completeness, here are brief outlines for remaining items:

**11. User Feedback**: Add `tqdm` progress bars for multi-feed operations
**12. Content Sanitization**: Use `bleach` library to sanitize HTML in titles/descriptions
**13. Incremental Updates**: Merge new entries with existing JSON instead of replacing
**14. Extensibility**: Create abstract `FeedSource` class with RSS/Atom/JSON implementations
**15. Testing**: Add `pytest` tests for validation, parsing, deduplication logic
**16. Documentation**: Add module/function docstrings and README with usage examples
**17. CLI Interface**: Use `argparse` for `--category`, `--verbose`, `--force-refresh` flags