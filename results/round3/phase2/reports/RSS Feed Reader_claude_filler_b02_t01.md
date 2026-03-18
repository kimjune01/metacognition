# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS/Atom feeds using `feedparser` library
2. **Multi-source Aggregation**: Processes multiple feed sources within categorized groups
3. **Timestamp Normalization**: Converts published/updated dates to a consistent timezone (KST/UTC+9)
4. **Deduplication by Timestamp**: Uses Unix timestamp as entry ID to prevent duplicates within a single fetch
5. **Time-based Sorting**: Orders entries by timestamp, newest first
6. **Human-readable Date Formatting**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older entries
7. **JSON Persistence**: Saves parsed feeds to `~/.rreader/rss_{category}.json` files
8. **Configuration Management**: 
   - Bundled default `feeds.json` shipped with the package
   - User-customizable feeds at `~/.rreader/feeds.json`
   - Automatic merge of new categories from bundled defaults
9. **Per-category Author Display**: Configurable `show_author` flag to show feed author vs. source name
10. **Selective Category Refresh**: Can update a single category or all categories
11. **Optional Logging**: Progress output during fetch operations

## Triage

### Critical Gaps (Would Break in Production)

1. **No Error Recovery** (Severity: HIGH)
   - Silent failures on network errors, malformed feeds, or missing fields
   - `sys.exit(0)` on fetch failure masks errors
   - No retry logic or backoff strategy

2. **No Concurrency Controls** (Severity: HIGH)
   - Sequential fetching is slow for many feeds (10+ feeds = 10+ seconds)
   - No connection pooling or timeout configuration
   - Blocks indefinitely on unresponsive servers

3. **No Cache Validation** (Severity: MEDIUM-HIGH)
   - Re-fetches all feeds on every run, wasting bandwidth
   - No ETags or Last-Modified header support
   - No minimum update interval enforcement

4. **Duplicate ID Collisions** (Severity: MEDIUM-HIGH)
   - Uses only timestamp as ID (`ts = int(time.mktime(parsed_time))`)
   - Multiple entries with same publish time overwrite each other
   - Cross-category uniqueness not guaranteed

### Important Missing Features (Reduce Usability)

5. **No Feed Health Monitoring** (Severity: MEDIUM)
   - No tracking of fetch failures, stale feeds, or dead sources
   - Users don't know which feeds are broken
   - No automatic removal or flagging of dead feeds

6. **Limited Metadata** (Severity: MEDIUM)
   - No entry summaries/descriptions stored
   - No content extraction or full-text storage
   - No feed-level metadata (icon, description, last-updated)

7. **No Feed Discovery** (Severity: MEDIUM)
   - No auto-detection of feed URLs from websites
   - No OPML import/export for migrating feeds
   - No suggested feeds or category presets

8. **Crude Date Handling** (Severity: LOW-MEDIUM)
   - Hardcoded timezone (KST) not suitable for international users
   - No relative time ("2 hours ago") display option
   - No date range filtering

### Polish & Maintenance (Nice to Have)

9. **No Logging Infrastructure** (Severity: LOW)
   - Uses `sys.stdout.write()` instead of proper logging
   - No log levels, rotation, or structured output
   - Debug mode relies on boolean flag

10. **No Tests** (Severity: LOW)
    - No unit tests for parsing, deduplication, or error cases
    - No fixtures or mock feeds for development

11. **No Rate Limiting** (Severity: LOW)
    - Could hammer servers with rapid successive fetches
    - No respect for `robots.txt` or feed-specific update intervals

12. **Configuration Fragility** (Severity: LOW)
    - JSON merge strategy only adds new categories, doesn't update existing
    - No schema validation for feeds.json
    - No migration path for config format changes

## Plan

### 1. Implement Robust Error Handling

**Changes needed:**
- Wrap `feedparser.parse()` in try-except for `URLError`, `HTTPError`, `Timeout`
- Add per-feed error tracking: store `{"last_error": "...", "error_count": N, "last_success": timestamp}`
- Replace `sys.exit(0)` with logging + continue to next feed
- Add `timeout` parameter to feedparser (requires requests session configuration)
- Return error summary to caller instead of silent failure

**Files to modify:**
- `rreader/fetch.py`: Add `FeedFetchError` exception class, wrap all parse calls
- `rreader/fetch.py`: Add `_handle_feed_error(source, error)` helper function
- Add `feed_health.json` to track error states per feed

### 2. Add Concurrent Fetching

**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` with `max_workers=5` (configurable)
- Batch feed fetches with `executor.map()` or individual `submit()` calls
- Add connection timeout (10s) and read timeout (30s) parameters
- Implement connection pooling via `requests.Session()` with `HTTPAdapter`

**Implementation approach:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
session.mount('http://', adapter)
session.mount('https://', adapter)

def fetch_single_feed(source, url):
    # feedparser can use session via requests
    return feedparser.parse(url, request_headers={'User-Agent': '...'})

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s for s, u in urls.items()}
    for future in as_completed(futures):
        # handle result
```

**Files to modify:**
- `rreader/fetch.py`: Refactor `get_feed_from_rss()` to use executor
- `rreader/config.py`: Add `FETCH_TIMEOUT`, `MAX_WORKERS` constants

### 3. Implement Cache Validation

**Changes needed:**
- Store ETag and Last-Modified headers from responses in `rss_{category}.json`
- Send `If-None-Match` / `If-Modified-Since` headers on subsequent fetches
- Handle 304 Not Modified responses by returning cached data
- Add minimum update interval (e.g., don't fetch more than once per 15 minutes)

**Storage schema addition:**
```json
{
  "entries": [...],
  "created_at": 1234567890,
  "cache_metadata": {
    "source_name": {
      "etag": "...",
      "last_modified": "...",
      "last_fetch": 1234567890
    }
  }
}
```

**Files to modify:**
- `rreader/fetch.py`: Add `_load_cache_metadata()` and `_save_cache_metadata()`
- `rreader/fetch.py`: Modify parse call to include conditional request headers
- `rreader/fetch.py`: Check `created_at` timestamp before fetching

### 4. Fix Duplicate ID Collisions

**Changes needed:**
- Change ID generation to: `hash(f"{ts}:{feed.link}")` or use feed GUID if available
- Prefer `feed.id` (GUID) if present, fallback to hash of link + timestamp
- Add cross-category duplicate detection by maintaining global seen set

**Implementation:**
```python
import hashlib

def generate_entry_id(feed, ts):
    # Prefer feed's own ID
    if hasattr(feed, 'id'):
        return hashlib.sha256(feed.id.encode()).hexdigest()[:16]
    # Fallback: hash of link + timestamp
    unique_key = f"{ts}:{feed.link}"
    return hashlib.sha256(unique_key.encode()).hexdigest()[:16]
```

**Files to modify:**
- `rreader/fetch.py`: Replace `"id": ts` with `"id": generate_entry_id(feed, ts)`

### 5. Add Feed Health Monitoring

**Changes needed:**
- Create `feed_health.json` with schema:
  ```json
  {
    "category/source": {
      "last_success": 1234567890,
      "last_error": "Connection timeout",
      "error_count": 3,
      "success_count": 47,
      "avg_fetch_time": 1.2
    }
  }
  ```
- Update health metrics on every fetch attempt
- Add `rreader status` command to show feed health dashboard
- Flag feeds with >5 consecutive errors or >7 days stale

**Files to modify:**
- Add `rreader/health.py` with `FeedHealthTracker` class
- `rreader/fetch.py`: Call `health.record_fetch(source, success, duration, error)`
- Add `rreader/cli.py` (if doesn't exist) for status command

### 6. Expand Entry Metadata

**Changes needed:**
- Store `summary` field: `feed.summary` or `feed.description`
- Store `content` if available: `feed.content[0].value` (may be HTML)
- Add feed-level metadata: `feed.feed.title`, `feed.feed.subtitle`, `feed.feed.image.href`
- Truncate summaries to 500 chars to limit file size

**Schema changes:**
```python
entries = {
    "id": entry_id,
    "sourceName": author,
    "feedTitle": d.feed.title,  # NEW
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": feed.summary[:500],  # NEW
    "contentSnippet": strip_html(feed.content[0].value)[:500] if hasattr(feed, 'content') else None  # NEW
}
```

**Files to modify:**
- `rreader/fetch.py`: Expand entry dictionary
- Add `rreader/utils.py` with `strip_html()` function

### 7. Add Feed Discovery & OPML

**Changes needed:**
- Add `rreader discover <url>` command that scrapes HTML for `<link rel="alternate" type="application/rss+xml">`
- Add `rreader import <opml_file>` to parse OPML and merge into feeds.json
- Add `rreader export <opml_file>` to write feeds.json as OPML

**Implementation:**
```python
# In rreader/discover.py
import requests
from bs4 import BeautifulSoup

def discover_feeds(url):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'html.parser')
    links = soup.find_all('link', type='application/rss+xml')
    return [link.get('href') for link in links]
```

**Files to add:**
- `rreader/discover.py`
- `rreader/opml.py` with `import_opml()` and `export_opml()`

### 8. Make Timezone Configurable

**Changes needed:**
- Move timezone to user config: add `timezone` field to feeds.json or separate settings.json
- Default to system timezone via `datetime.datetime.now().astimezone().tzinfo`
- Add validation for timezone strings (use `pytz` or `zoneinfo`)

**Config schema:**
```json
{
  "settings": {
    "timezone": "America/New_York",
    "date_format": "relative"  // "relative" | "absolute"
  },
  "categories": { ... }
}
```

**Files to modify:**
- `rreader/config.py`: Load timezone from config, provide default
- `rreader/fetch.py`: Use config timezone instead of hardcoded KST

### 9. Add Proper Logging

**Changes needed:**
- Replace `sys.stdout.write()` with `logging` module
- Add log levels: DEBUG, INFO, WARNING, ERROR
- Write logs to `~/.rreader/rreader.log` with rotation (using `RotatingFileHandler`)
- Add `--verbose` / `--quiet` CLI flags to control console output

**Implementation:**
```python
import logging
from logging.handlers import RotatingFileHandler

logger = logging.getLogger('rreader')
logger.setLevel(logging.DEBUG)

file_handler = RotatingFileHandler(
    os.path.join(p['path_data'], 'rreader.log'),
    maxBytes=1024*1024,  # 1MB
    backupCount=3
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Usage:
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse {url}: {error}")
```

**Files to modify:**
- `rreader/fetch.py`: Replace print statements with `logger` calls
- Add `rreader/logging_config.py` for centralized setup

### 10. Add Minimal Test Coverage

**Changes needed:**
- Add `tests/` directory with pytest structure
- Create `tests/fixtures/sample_feed.xml` with known RSS content
- Write tests for:
  - Parse valid feed → correct entry count
  - Parse feed with missing timestamps → skip entry
  - Generate unique IDs → no collisions
  - Handle network errors → graceful failure

**Sample test:**
```python
# tests/test_fetch.py
import pytest
from rreader.fetch import get_feed_from_rss

def test_parse_valid_feed(tmp_path, monkeypatch):
    # Mock feedparser.parse to return fixture
    def mock_parse(url):
        # Return parsed fixture
        pass
    monkeypatch.setattr('feedparser.parse', mock_parse)
    
    result = get_feed_from_rss('test', {'source': 'http://example.com/feed'})
    assert len(result['entries']) > 0
    assert 'timestamp' in result['entries'][0]
```

**Files to add:**
- `tests/test_fetch.py`
- `tests/test_config.py`
- `tests/fixtures/` directory with sample feeds

### 11. Add Rate Limiting

**Changes needed:**
- Store `last_fetch_time` per feed in feed_health.json
- Enforce minimum interval between fetches (default: 900 seconds / 15 minutes)
- Add per-feed `update_interval` override in feeds.json
- Skip fetch if `time.time() - last_fetch_time < interval`

**Config schema addition:**
```json
{
  "Tech": {
    "feeds": {
      "HackerNews": "https://...",
    },
    "update_interval": 1800  // seconds
  }
}
```

**Files to modify:**
- `rreader/fetch.py`: Check interval before fetching, skip if too soon
- `rreader/health.py`: Track `last_fetch_time`

### 12. Add Config Validation

**Changes needed:**
- Define JSON schema for feeds.json using `jsonschema` library
- Validate on load, provide helpful error messages for malformed config
- Add `rreader validate` command to check feeds.json without fetching
- Handle schema migrations (e.g., v1 → v2 format) with conversion scripts

**Implementation:**
```python
from jsonschema import validate, ValidationError

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"},
                "update_interval": {"type": "integer", "minimum": 60}
            },
            "required": ["feeds"]
        }
    }
}

def validate_feeds_config(config):
    try:
        validate(instance=config, schema=FEEDS_SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Invalid feeds.json: {e.message}")
```

**Files to modify:**
- Add `rreader/validation.py`
- `rreader/fetch.py`: Call validation after loading feeds.json