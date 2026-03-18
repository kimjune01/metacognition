# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed reader with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS feeds from multiple sources using `feedparser`
2. **Multi-Category Support**: Organizes feeds into categories, processing each separately
3. **Data Persistence**: Stores parsed feed entries as JSON files (`rss_{category}.json`)
4. **Configuration Management**: 
   - Maintains user feed configuration in `~/.rreader/feeds.json`
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled config into user config
5. **Timezone Handling**: Converts feed timestamps to a configured timezone (KST/UTC+9)
6. **Smart Date Formatting**: Shows time-only for today's posts, full date for older posts
7. **Deduplication**: Uses timestamp as unique ID to prevent duplicate entries
8. **Flexible Author Display**: Can toggle between source name or actual author per category
9. **Selective Updates**: Can update single category or all categories
10. **Optional Logging**: Provides progress output when enabled

## Triage

### Critical (P0) - System Fails Without These
1. **Fatal Exception Handling**: Bare `except:` with `sys.exit()` kills entire process on single feed failure
2. **Duplicate ID Collisions**: Multiple entries with same timestamp overwrite each other
3. **Missing Error Recovery**: No retry logic or graceful degradation

### High Priority (P1) - Production Blockers
4. **No Error Reporting**: Failed feeds silently disappear from output
5. **Timezone Assumption**: Hardcoded to KST; not configurable per-deployment
6. **No Feed Validation**: Doesn't verify feed quality or handle malformed feeds
7. **Missing Tests**: No unit tests, integration tests, or validation
8. **No Rate Limiting**: Could hammer feed servers or get blocked

### Medium Priority (P2) - Quality & Maintainability
9. **No Caching Strategy**: Re-downloads all feeds every run, even if unchanged
10. **Limited Observability**: No structured logging, metrics, or monitoring hooks
11. **No Incremental Updates**: Always processes all entries, not just new ones
12. **Configuration Schema**: No validation of `feeds.json` structure
13. **Date Edge Cases**: `datetime.date.today()` doesn't use TIMEZONE for comparison

### Low Priority (P3) - Nice to Have
14. **No Feed Metadata**: Missing feed description, image, update frequency
15. **Memory Efficiency**: Loads all entries into memory before sorting
16. **No User Feedback**: Doesn't show count of new entries or update summary

## Plan

### P0 Fixes

**1. Fatal Exception Handling**
```python
# Current problematic code:
except:
    sys.exit(" - Failed\n" if log else 0)

# Change to:
except Exception as e:
    if log:
        sys.stderr.write(f" - Failed: {e}\n")
    continue  # Skip this feed, continue with others
```
Add feed-level error collection and report at end rather than killing process.

**2. Duplicate ID Collisions**
```python
# Current: entries["id"] = ts  # timestamp collision loses data

# Change to unique ID generation:
import hashlib
unique_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"

# Or append collision counter:
base_id = ts
counter = 0
while base_id in rslt:
    counter += 1
    base_id = f"{ts}_{counter}"
```

**3. Missing Error Recovery**
```python
# Add at function level:
from functools import wraps
import time

def retry_on_failure(max_attempts=3, delay=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay * (attempt + 1))
            return wrapper
    return decorator

# Apply to feedparser.parse() call
```

### P1 Fixes

**4. No Error Reporting**
```python
# Add error tracking structure:
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    # In exception handler:
    except Exception as e:
        errors.append({"source": source, "url": url, "error": str(e)})
    
    # Include in output:
    result_data = {
        "entries": rslt,
        "created_at": int(time.time()),
        "errors": errors
    }
```

**5. Timezone Assumption**
```python
# In config.py, make configurable:
TIMEZONE = datetime.timezone(
    datetime.timedelta(hours=int(os.getenv('RREADER_TZ_OFFSET', '9')))
)

# Or use system timezone:
import zoneinfo
TIMEZONE = zoneinfo.ZoneInfo(os.getenv('RREADER_TZ', 'Asia/Seoul'))
```

**6. No Feed Validation**
```python
# Add after feedparser.parse():
if not hasattr(d, 'entries') or d.bozo:
    if log:
        sys.stderr.write(f" - Invalid feed: {d.bozo_exception}\n")
    continue

# Validate required fields:
required_fields = ['title', 'link']
if not all(hasattr(feed, field) for field in required_fields):
    continue  # Skip malformed entry
```

**7. Missing Tests**
```python
# Create tests/test_feed_parser.py:
import unittest
from unittest.mock import patch, Mock

class TestFeedParser(unittest.TestCase):
    def test_parse_valid_feed(self):
        # Mock feedparser.parse response
        pass
    
    def test_handle_missing_timestamp(self):
        # Verify graceful handling
        pass
    
    def test_duplicate_timestamps(self):
        # Verify no data loss
        pass
```

**8. No Rate Limiting**
```python
import time

# Add before loop:
RATE_LIMIT_DELAY = 1  # seconds between requests

# In loop:
for i, (source, url) in enumerate(urls.items()):
    if i > 0:  # Don't delay first request
        time.sleep(RATE_LIMIT_DELAY)
    
    # Or use library like ratelimit:
    # from ratelimit import limits, sleep_and_retry
```

### P2 Fixes

**9. No Caching Strategy**
```python
# Add ETag/Last-Modified support:
import pickle

def parse_with_cache(url, cache_file):
    etag = None
    modified = None
    
    if os.path.exists(cache_file):
        with open(cache_file, 'rb') as f:
            cached = pickle.load(f)
            etag = cached.get('etag')
            modified = cached.get('modified')
    
    d = feedparser.parse(url, etag=etag, modified=modified)
    
    if d.status == 304:  # Not modified
        return cached['data']
    
    # Save new cache
    with open(cache_file, 'wb') as f:
        pickle.dump({
            'etag': d.get('etag'),
            'modified': d.get('modified'),
            'data': d
        }, f)
    
    return d
```

**10. Limited Observability**
```python
import logging

# Replace print statements with:
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Use structured logging:
logger.info("Fetching feed", extra={
    "category": category,
    "source": source,
    "url": url
})
```

**11. No Incremental Updates**
```python
# Load existing data:
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
existing_ids = set()

if os.path.exists(existing_file):
    with open(existing_file, 'r') as f:
        existing_data = json.load(f)
        existing_ids = {e['id'] for e in existing_data.get('entries', [])}

# Only add new entries:
if entries["id"] not in existing_ids:
    rslt[entries["id"]] = entries
```

**12. Configuration Schema**
```python
from jsonschema import validate, ValidationError

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"}
            },
            "required": ["feeds"]
        }
    }
}

# Validate on load:
try:
    validate(instance=RSS, schema=FEEDS_SCHEMA)
except ValidationError as e:
    sys.stderr.write(f"Invalid feeds.json: {e.message}\n")
    sys.exit(1)
```

**13. Date Edge Cases**
```python
# Replace:
at.date() == datetime.date.today()

# With timezone-aware comparison:
today = datetime.datetime.now(TIMEZONE).date()
pubDate = at.strftime(
    "%H:%M" if at.date() == today else "%b %d, %H:%M"
)
```