# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Feed Configuration Management**: 
   - Loads feed configurations from a JSON file (`feeds.json`)
   - Copies bundled default feeds if user configuration doesn't exist
   - Merges new categories from bundled feeds into existing user configurations

3. **Data Extraction**: Extracts key information from feed entries:
   - Publication/update timestamps
   - Article titles and URLs
   - Source/author names
   - Formatted publication dates

4. **Time Handling**:
   - Converts UTC timestamps to configured timezone (KST/UTC+9)
   - Formats dates contextually (time-only for today, date+time for older items)

5. **Data Storage**: 
   - Saves parsed feeds as JSON files (`rss_{category}.json`)
   - Deduplicates entries by timestamp
   - Sorts entries reverse-chronologically
   - Stores creation timestamp with each feed

6. **Directory Management**: Creates necessary data directories on first run

7. **Category Filtering**: Can process either all feeds or a specific category via `target_category` parameter

## Triage

### Critical Gaps

1. **Error Handling** (Severity: HIGH)
   - Bare `except` clauses that silently swallow errors
   - `sys.exit()` called on feed parsing failure, terminating entire process
   - No retry mechanism for transient network failures
   - Missing validation of parsed feed data

2. **Feed Configuration Schema** (Severity: HIGH)
   - No validation of `feeds.json` structure
   - Missing example or documentation of expected format
   - No error messages for malformed configuration

3. **Collision Handling** (Severity: MEDIUM-HIGH)
   - Uses timestamp as unique ID, which can collide if multiple articles published simultaneously
   - No handling for duplicate URLs or titles

### Important Gaps

4. **Logging Infrastructure** (Severity: MEDIUM)
   - Optional `log` parameter only prints to stdout
   - No structured logging (levels, timestamps, context)
   - No log file output
   - No differentiation between info/warning/error

5. **Resource Management** (Severity: MEDIUM)
   - No timeout configuration for HTTP requests
   - No connection pooling or rate limiting
   - Sequential processing could be slow with many feeds
   - No caching of feed data to reduce redundant requests

6. **Data Integrity** (Severity: MEDIUM)
   - No atomic file writes (could corrupt data on crash)
   - No backup mechanism for existing feed data
   - Missing file locking for concurrent access

### Nice-to-Have Gaps

7. **Monitoring & Observability** (Severity: LOW-MEDIUM)
   - No metrics on feed fetch success/failure rates
   - No tracking of feed update frequency
   - No alerts for stale or broken feeds

8. **User Experience** (Severity: LOW)
   - No progress indication for long-running operations
   - No summary output (e.g., "Fetched 45 new articles from 12 feeds")
   - Missing command-line argument parsing for category selection

9. **Testing & Validation** (Severity: LOW)
   - No unit tests
   - No mock feeds for testing
   - No validation that saved JSON is readable

## Plan

### 1. Error Handling Improvements

**Changes needed:**
```python
# Replace bare except clauses with specific exceptions
try:
    d = feedparser.parse(url)
except (urllib.error.URLError, socket.timeout) as e:
    logger.error(f"Network error fetching {url}: {e}")
    continue  # Don't exit, skip to next feed
except Exception as e:
    logger.error(f"Unexpected error parsing {url}: {e}")
    continue

# Add retry logic with exponential backoff
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# Add data validation
def validate_entry(feed):
    required = ['link', 'title']
    return all(hasattr(feed, attr) for attr in required)
```

### 2. Feed Configuration Schema

**Changes needed:**
```python
# Create feeds.json.example with documentation
FEED_SCHEMA = {
    "category_name": {
        "feeds": {
            "Source Name": "https://example.com/rss"
        },
        "show_author": False  # Optional, defaults to False
    }
}

# Add validation function
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a JSON object")
    
    for category, data in config.items():
        if "feeds" not in data:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category '{category}' feeds must be object")
        # Validate URLs
        for source, url in data["feeds"].items():
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL for {source}: {url}")

# Call before processing
with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
    validate_feeds_config(RSS)
```

### 3. Collision Handling

**Changes needed:**
```python
# Generate unique IDs combining timestamp and URL hash
import hashlib

def generate_entry_id(feed, parsed_time):
    ts = int(time.mktime(parsed_time))
    url_hash = hashlib.md5(feed.link.encode()).hexdigest()[:8]
    return f"{ts}_{url_hash}"

# Use in entry creation
entries = {
    "id": generate_entry_id(feed, parsed_time),
    # ... rest of fields
}

# Change rslt to use URL as deduplication key
if feed.link not in seen_urls:
    seen_urls.add(feed.link)
    rslt[entries["id"]] = entries
```

### 4. Logging Infrastructure

**Changes needed:**
```python
import logging
from logging.handlers import RotatingFileHandler

# Set up logger at module level
def setup_logger():
    logger = logging.getLogger('rreader')
    logger.setLevel(logging.INFO)
    
    # File handler
    fh = RotatingFileHandler(
        os.path.join(p["path_data"], 'rreader.log'),
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    fh.setLevel(logging.DEBUG)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

logger = setup_logger()

# Replace print statements
logger.info(f"Fetching feed: {url}")
logger.debug(f"Parsed {len(d.entries)} entries")
logger.error(f"Failed to fetch {url}: {e}")
```

### 5. Resource Management

**Changes needed:**
```python
# Add timeout configuration at top of file
FEED_TIMEOUT = 30  # seconds
MAX_WORKERS = 5  # concurrent feed fetches

# Use requests instead of feedparser's built-in fetching
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, timeout=FEED_TIMEOUT):
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except requests.RequestException as e:
        logger.error(f"Error fetching {source}: {e}")
        return None

# Parallel processing
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_source = {
            executor.submit(fetch_single_feed, source, url): (source, url)
            for source, url in urls.items()
        }
        
        for future in as_completed(future_to_source):
            source, url = future_to_source[future]
            d = future.result()
            if d:
                # Process entries...
```

### 6. Data Integrity

**Changes needed:**
```python
import tempfile
import shutil

# Atomic file writes
def atomic_write_json(filepath, data):
    """Write JSON atomically using temp file and rename"""
    dir_name = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile(
        mode='w', 
        dir=dir_name, 
        delete=False,
        encoding='utf-8'
    ) as tf:
        json.dump(data, tf, ensure_ascii=False, indent=2)
        temp_name = tf.name
    
    # Atomic rename
    shutil.move(temp_name, filepath)

# Create backup before overwriting
def backup_if_exists(filepath):
    if os.path.exists(filepath):
        backup = f"{filepath}.backup"
        shutil.copy2(filepath, backup)

# Use in save operation
backup_if_exists(output_path)
atomic_write_json(output_path, rslt)
```

### 7. Monitoring & Observability

**Changes needed:**
```python
from dataclasses import dataclass
from typing import Dict, List

@dataclass
class FetchMetrics:
    total_feeds: int = 0
    successful_feeds: int = 0
    failed_feeds: int = 0
    total_entries: int = 0
    new_entries: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = None
    
    def __post_init__(self):
        if self.errors is None:
            self.errors = []

# Track metrics during fetch
def get_feed_from_rss(category, urls, show_author=False, log=False):
    metrics = FetchMetrics(total_feeds=len(urls))
    start_time = time.time()
    
    # ... during processing ...
    metrics.successful_feeds += 1
    metrics.total_entries += len(d.entries)
    
    # Save metrics
    metrics.duration_seconds = time.time() - start_time
    metrics_path = os.path.join(p["path_data"], f"metrics_{category}.json")
    atomic_write_json(metrics_path, metrics.__dict__)
    
    return rslt, metrics
```

### 8. User Experience

**Changes needed:**
```python
import argparse
from tqdm import tqdm  # Progress bars

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('-c', '--category', help='Specific category to fetch')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--list', action='store_true', help='List available categories')
    args = parser.parse_args()
    
    if args.list:
        with open(FEEDS_FILE_NAME, "r") as fp:
            RSS = json.load(fp)
        print("Available categories:")
        for cat in RSS.keys():
            print(f"  - {cat}")
        return
    
    results = do(target_category=args.category, log=args.verbose)
    
    # Print summary
    if results:
        print(f"\nFetched {len(results['entries'])} articles")
        print(f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()
```

### 9. Testing & Validation

**Changes needed:**
```python
# Create tests/test_rss.py
import unittest
from unittest.mock import Mock, patch
import tempfile

class TestRSSFetcher(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        
    def test_parse_valid_feed(self):
        mock_feed = Mock()
        mock_feed.entries = [
            Mock(
                title="Test Article",
                link="https://example.com/article",
                published_parsed=time.gmtime()
            )
        ]
        
        with patch('feedparser.parse', return_value=mock_feed):
            result = get_feed_from_rss('test', {'Source': 'http://example.com'})
            self.assertEqual(len(result['entries']), 1)
    
    def test_handles_missing_timestamp(self):
        # Test entry without published_parsed or updated_parsed
        pass
    
    def test_atomic_write_preserves_data(self):
        # Test atomic writes don't corrupt on failure
        pass

# Add validation after write
def validate_saved_json(filepath):
    try:
        with open(filepath, 'r') as f:
            data = json.load(f)
        assert 'entries' in data
        assert 'created_at' in data
        return True
    except Exception as e:
        logger.error(f"Validation failed for {filepath}: {e}")
        return False
```