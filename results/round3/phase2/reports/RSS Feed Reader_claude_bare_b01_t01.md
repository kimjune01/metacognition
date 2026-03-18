# Diagnostic Report: RSS Feed Reader System

## Observations

This is a functional RSS feed aggregator that:

1. **Fetches and parses RSS feeds** from multiple sources using the `feedparser` library
2. **Organizes feeds by category** defined in a `feeds.json` configuration file
3. **Normalizes timestamps** to a configurable timezone (currently KST/UTC+9)
4. **Caches results** as JSON files in `~/.rreader/` directory (one file per category)
5. **Handles bundled defaults** by copying a bundled `feeds.json` if none exists, and merging new categories from updates
6. **Supports selective updates** via `target_category` parameter to refresh only one category
7. **Displays human-readable dates** (e.g., "14:30" for today, "Mar 15, 14:30" for older entries)
8. **Deduplicates entries** using timestamp as ID (though this may cause collisions)
9. **Supports optional author display** per category via `show_author` flag

## Triage

### Critical Gaps
1. **Error handling is nearly absent** - Single try/except with `sys.exit(0)` on feed fetch failure silently exits or continues
2. **ID collision vulnerability** - Using Unix timestamp as ID will overwrite entries published in the same second
3. **No validation** - Missing feed structure, URL format, and configuration schema validation

### High Priority
4. **No entry update detection** - Cannot detect when an existing entry has been modified
5. **Missing feed metadata** - No tracking of feed title, description, last-modified headers, or ETags for efficient polling
6. **No rate limiting or request management** - Could hammer servers or get blocked
7. **Silent data loss on parse errors** - Individual entries that fail to parse are skipped with no logging

### Medium Priority
8. **No CLI interface** - Function signature suggests one (`log` parameter) but no argparse implementation
9. **Incomplete relative imports** - Try/except import pattern suggests package structure but no `__init__.py` mentioned
10. **No configuration for cache TTL** - Always fetches, no smart refresh based on age
11. **Limited date formats** - Hardcoded format doesn't handle "Yesterday", relative times, or i18n

### Low Priority
12. **No feed health monitoring** - No tracking of consecutive failures, feed staleness warnings
13. **Missing entry content** - Only stores title/link, not summary or full content
14. **No search or filtering** - Cannot query cached entries

## Plan

### 1. Error Handling (Critical)
**Change:** Wrap feed parsing in granular try/except blocks
```python
# Per-feed error handling
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        if d.bozo:  # feedparser's malformed feed flag
            logging.warning(f"Malformed feed {source}: {d.bozo_exception}")
    except Exception as e:
        logging.error(f"Failed to fetch {source} ({url}): {e}")
        continue  # Don't exit, process other feeds

# Per-entry error handling
for feed in d.entries:
    try:
        # ... process entry ...
    except Exception as e:
        logging.warning(f"Skipped entry in {source}: {e}")
        continue
```
**Add:** Python `logging` module with configurable level, file handler to `~/.rreader/errors.log`

### 2. Fix ID Collision (Critical)
**Change:** Generate unique IDs combining timestamp and content hash
```python
import hashlib

entry_key = f"{ts}_{feed.link}"
entry_id = hashlib.sha256(entry_key.encode()).hexdigest()[:16]

entries = {
    "id": entry_id,
    "timestamp": ts,
    # ... rest of fields
}

rslt[entry_id] = entries  # Use hash instead of timestamp
```

### 3. Validation (Critical)
**Add:** Schema validation using `jsonschema` or `pydantic`
```python
from jsonschema import validate, ValidationError

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"}
            }
        }
    }
}

# Validate on load
try:
    validate(instance=RSS, schema=FEEDS_SCHEMA)
except ValidationError as e:
    sys.exit(f"Invalid feeds.json: {e.message}")
```

### 4. Entry Update Detection (High)
**Change:** Store entry hash in cache, compare on subsequent runs
```python
import hashlib

def entry_hash(feed):
    content = f"{feed.title}{feed.link}{getattr(feed, 'summary', '')}"
    return hashlib.md5(content.encode()).hexdigest()

entries = {
    # ... existing fields ...
    "content_hash": entry_hash(feed),
    "updated_at": ts,  # Track last modification
}

# When loading existing cache
existing = load_cache(category)
if entry_id in existing and existing[entry_id]["content_hash"] != new_hash:
    entries["updated_at"] = int(time.time())
```

### 5. Feed Metadata Tracking (High)
**Change:** Store feed-level metadata in separate file
```python
# Structure: ~/.rreader/metadata_{category}.json
{
    "source_name": {
        "url": "https://...",
        "title": "Feed Title",
        "last_fetched": 1234567890,
        "last_modified": "Wed, 15 Mar 2023 10:00:00 GMT",  # From HTTP header
        "etag": "\"abc123\"",  # From HTTP header
        "consecutive_failures": 0,
        "last_error": null
    }
}
```
**Add:** Use `requests` library instead of feedparser alone to access headers:
```python
import requests
response = requests.get(url, headers={
    "If-Modified-Since": last_modified,
    "If-None-Match": etag
})
if response.status_code == 304:
    # Not modified, use cache
    continue
```

### 6. Rate Limiting (High)
**Add:** Request throttling with exponential backoff
```python
import time
from functools import wraps

def rate_limit(min_interval=1.0):
    last_call = {}
    def decorator(func):
        @wraps(func)
        def wrapper(url, *args, **kwargs):
            now = time.time()
            if url in last_call:
                elapsed = now - last_call[url]
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
            last_call[url] = time.time()
            return func(url, *args, **kwargs)
        return wrapper
    return decorator

@rate_limit(min_interval=1.0)
def fetch_feed(url):
    return feedparser.parse(url)
```

### 7. CLI Interface (Medium)
**Add:** Proper argument parsing in `if __name__ == "__main__"`
```python
import argparse

parser = argparse.ArgumentParser(description="RSS feed aggregator")
parser.add_argument("-c", "--category", help="Update specific category")
parser.add_argument("-v", "--verbose", action="store_true", help="Enable logging")
parser.add_argument("--list-categories", action="store_true", help="List available categories")
args = parser.parse_args()

if args.list_categories:
    # Load and print categories
    pass
else:
    do(target_category=args.category, log=args.verbose)
```

### 8. Cache TTL Configuration (Medium)
**Add:** Check cache age before fetching
```python
# In feeds.json, add per-category TTL
{
    "tech": {
        "feeds": {...},
        "ttl_minutes": 30  # Don't refetch if cache < 30min old
    }
}

# In code
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(cache_file):
    cache_age = time.time() - os.path.getmtime(cache_file)
    ttl_seconds = RSS[category].get("ttl_minutes", 30) * 60
    if cache_age < ttl_seconds:
        return json.load(open(cache_file))
```

### 9. Store Entry Content (Medium)
**Change:** Add summary/content fields to entry storage
```python
entries = {
    # ... existing fields ...
    "summary": getattr(feed, 'summary', ''),
    "content": feed.get('content', [{}])[0].get('value', ''),  # Full content if available
    "tags": [tag.term for tag in getattr(feed, 'tags', [])],
}
```

### 10. Logging Infrastructure (Applies to #1, #7)
**Add:** Centralized logging configuration
```python
import logging

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
            logging.StreamHandler() if verbose else logging.NullHandler()
        ]
    )
    return logging.getLogger(__name__)
```