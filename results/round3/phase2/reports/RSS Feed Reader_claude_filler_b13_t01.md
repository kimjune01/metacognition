# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS feeds using the `feedparser` library from multiple sources defined in a JSON configuration file.

2. **Time Handling**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9) and formats them as human-readable strings (showing time-only for today's items, date+time for older items).

3. **Data Persistence**: Saves parsed feeds to individual JSON files per category in `~/.rreader/` directory, with structure containing entries array and creation timestamp.

4. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file with category-based feed organization
   - Automatically copies bundled default feeds if user configuration doesn't exist
   - Merges new categories from bundled config into existing user config

5. **Deduplication**: Uses timestamp as unique ID to prevent duplicate entries from the same feed source within a category.

6. **Flexible Attribution**: Supports configurable `show_author` flag per category to display either feed author or source name.

7. **Selective Updates**: Can update a single category via `target_category` parameter or all categories if none specified.

8. **Basic Logging**: Optional stdout logging shows feed URLs being processed and completion status.

## Triage

### Critical Gaps

1. **Error Handling** (Severity: HIGH)
   - Bare `except:` clauses swallow all exceptions without logging
   - Failed feed fetches exit entire program or silently continue
   - No handling of malformed JSON, network timeouts, or invalid URLs

2. **Data Integrity** (Severity: HIGH)
   - Timestamp collision handling is inadequate (multiple feeds at same second will overwrite)
   - No validation that required fields exist before writing
   - Corrupt JSON files would crash the reader

3. **Concurrency Issues** (Severity: MEDIUM-HIGH)
   - No file locking when reading/writing JSON files
   - Race conditions possible if multiple processes run simultaneously
   - Feed fetching is purely sequential (slow for many feeds)

### Important Gaps

4. **Resource Management** (Severity: MEDIUM)
   - No timeout configuration for HTTP requests
   - No maximum feed size limits
   - Memory usage unbounded for large feeds
   - No cleanup of old cached data

5. **Observability** (Severity: MEDIUM)
   - No proper logging framework (only optional stdout)
   - No metrics on fetch success/failure rates
   - No timing information for performance monitoring
   - No way to diagnose why specific feeds fail

6. **Configuration Validation** (Severity: MEDIUM)
   - No schema validation for feeds.json
   - Invalid category names or URLs not detected until runtime
   - No feedback when configuration merge happens

### Nice-to-Have Gaps

7. **User Experience** (Severity: LOW-MEDIUM)
   - No progress indication for long-running fetches
   - No way to force refresh vs. using cached data
   - No entry limit or pagination
   - No filtering capabilities (by date, source, keywords)

8. **Robustness Features** (Severity: LOW)
   - No retry logic for transient failures
   - No rate limiting to avoid hammering servers
   - No exponential backoff
   - No conditional GET (If-Modified-Since headers)

9. **Testing & Maintenance** (Severity: LOW)
   - No unit tests
   - No integration tests
   - No documentation beyond code
   - Hard-coded paths and magic numbers

## Plan

### 1. Error Handling Improvements

**Changes needed:**
- Replace all bare `except:` with specific exception types
- Import and use `logging` module instead of raw print statements
- Create error categories: `NetworkError`, `ParseError`, `ConfigError`
- Store failed feeds with error messages in output JSON under "errors" key

**Specific implementation:**
```python
import logging
from urllib.error import URLError
from socket import timeout

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser's error flag
        raise ParseError(f"Feed parsing error: {d.bozo_exception}")
except (URLError, timeout) as e:
    logger.error(f"Network error for {url}: {e}")
    # Store in errors dict, continue to next feed
except Exception as e:
    logger.error(f"Unexpected error for {url}: {e}", exc_info=True)
```

### 2. Data Integrity Fixes

**Changes needed:**
- Replace timestamp-only ID with compound key: `f"{source}_{ts}_{hash(title)[:8]}"`
- Add JSON schema validation using `jsonschema` library
- Implement atomic writes using temp file + rename pattern
- Add required field validation before JSON serialization

**Specific implementation:**
```python
import hashlib
import tempfile

def generate_entry_id(source, timestamp, title):
    title_hash = hashlib.md5(title.encode()).hexdigest()[:8]
    return f"{source}_{timestamp}_{title_hash}"

def atomic_write_json(filepath, data):
    with tempfile.NamedTemporaryFile(mode='w', delete=False, 
                                     dir=os.path.dirname(filepath)) as tf:
        json.dump(data, tf, ensure_ascii=False)
        temp_path = tf.name
    os.replace(temp_path, filepath)  # Atomic on POSIX systems
```

### 3. Concurrency Safety

**Changes needed:**
- Use `fcntl.flock()` on Unix or `msvcrt.locking()` on Windows for file locking
- Add thread pool executor for parallel feed fetching with configurable worker count
- Use threading locks around shared data structures

**Specific implementation:**
```python
import fcntl
from concurrent.futures import ThreadPoolExecutor, as_completed

def locked_file_operation(filepath, mode='r'):
    with open(filepath, mode) as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)

def fetch_feeds_parallel(feeds_dict, max_workers=5):
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_feed, url): source 
                   for source, url in feeds_dict.items()}
        for future in as_completed(futures):
            # Handle results
```

### 4. Resource Management

**Changes needed:**
- Add timeout parameter to feedparser calls (via custom urllib opener)
- Implement max entries per feed (default 100)
- Add cache expiry: delete JSON files older than configurable threshold
- Implement streaming JSON writer for very large result sets

**Specific implementation:**
```python
import urllib.request

def parse_feed_with_timeout(url, timeout=30, max_entries=100):
    opener = urllib.request.build_opener()
    opener.addheaders = [('User-Agent', 'rreader/1.0')]
    feedparser.USER_AGENT = 'rreader/1.0'
    
    d = feedparser.parse(url, request_headers={'timeout': timeout})
    d.entries = d.entries[:max_entries]
    return d

def cleanup_old_cache(max_age_days=7):
    cutoff = time.time() - (max_age_days * 86400)
    for f in os.listdir(p["path_data"]):
        if f.startswith("rss_") and f.endswith(".json"):
            fpath = os.path.join(p["path_data"], f)
            if os.path.getmtime(fpath) < cutoff:
                os.remove(fpath)
```

### 5. Observability Enhancement

**Changes needed:**
- Replace print/sys.stdout with proper logging at appropriate levels
- Add structured logging with context (category, source, URL)
- Create metrics dict with counts: `{successful: N, failed: N, total_time: T}`
- Write metrics to separate JSON file for monitoring

**Specific implementation:**
```python
import logging.handlers

def setup_logging(log_dir):
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, 'rreader.log'),
        maxBytes=10485760,  # 10MB
        backupCount=5
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

class FetchMetrics:
    def __init__(self):
        self.successful = 0
        self.failed = 0
        self.start_time = time.time()
        self.errors = []
    
    def to_dict(self):
        return {
            'successful': self.successful,
            'failed': self.failed,
            'duration': time.time() - self.start_time,
            'errors': self.errors
        }
```

### 6. Configuration Validation

**Changes needed:**
- Define JSON schema for feeds.json structure
- Validate on load with helpful error messages
- Add `--validate-config` CLI flag
- Warn user when auto-merging new categories

**Specific implementation:**
```python
from jsonschema import validate, ValidationError

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {".*": {"type": "string", "format": "uri"}}
                },
                "show_author": {"type": "boolean"}
            },
            "required": ["feeds"]
        }
    }
}

def validate_config(config):
    try:
        validate(instance=config, schema=FEEDS_SCHEMA)
    except ValidationError as e:
        logger.error(f"Invalid configuration: {e.message}")
        sys.exit(1)
```

### 7. User Experience Features

**Changes needed:**
- Add `--max-age` parameter to filter entries by date
- Implement `--force-refresh` flag to ignore cache timestamps
- Add `--limit` parameter for max entries per category
- Create progress bar using `tqdm` library

**Specific implementation:**
```python
from tqdm import tqdm
import argparse

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--category', help='Update specific category only')
    parser.add_argument('--max-age', type=int, help='Max age in hours')
    parser.add_argument('--force-refresh', action='store_true')
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument('--verbose', action='store_true')
    return parser.parse_args()

def should_refresh(cache_file, max_age_hours=1, force=False):
    if force or not os.path.exists(cache_file):
        return True
    age = time.time() - os.path.getmtime(cache_file)
    return age > (max_age_hours * 3600)

# Use tqdm for progress
for source, url in tqdm(urls.items(), desc="Fetching feeds"):
    # fetch logic
```

### 8. Robustness Features

**Changes needed:**
- Add retry decorator with exponential backoff using `tenacity` library
- Implement per-source rate limiting (min interval between requests)
- Add ETag and Last-Modified header support
- Store and reuse these headers for conditional requests

**Specific implementation:**
```python
from tenacity import retry, stop_after_attempt, wait_exponential
import time

class RateLimiter:
    def __init__(self, min_interval=1.0):
        self.min_interval = min_interval
        self.last_request = {}
    
    def wait_if_needed(self, key):
        if key in self.last_request:
            elapsed = time.time() - self.last_request[key]
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
        self.last_request[key] = time.time()

@retry(stop=stop_after_attempt(3), 
       wait=wait_exponential(multiplier=1, min=4, max=10))
def fetch_feed_with_retry(url):
    return feedparser.parse(url)
```

### 9. Testing & Documentation

**Changes needed:**
- Create `tests/` directory with pytest test suite
- Add docstrings to all functions using Google/NumPy style
- Create README.md with installation, configuration, usage examples
- Add type hints throughout codebase

**Specific implementation:**
```python
# tests/test_fetch.py
import pytest
from unittest.mock import Mock, patch

def test_fetch_feed_success():
    with patch('feedparser.parse') as mock_parse:
        mock_parse.return_value = Mock(entries=[...])
        result = get_feed_from_rss('test', {'src': 'http://example.com'})
        assert len(result['entries']) > 0

def test_fetch_feed_network_error():
    with patch('feedparser.parse', side_effect=URLError('timeout')):
        result = get_feed_from_rss('test', {'src': 'http://example.com'})
        assert 'errors' in result

# Type hints example
from typing import Dict, List, Optional

def get_feed_from_rss(
    category: str, 
    urls: Dict[str, str], 
    show_author: bool = False,
    log: bool = False
) -> Dict[str, any]:
    """
    Fetch and parse RSS feeds for a category.
    
    Args:
        category: Category name for organizing feeds
        urls: Mapping of source names to feed URLs
        show_author: Whether to show feed author instead of source name
        log: Enable verbose logging to stdout
    
    Returns:
        Dictionary with 'entries' list and 'created_at' timestamp
    """
```