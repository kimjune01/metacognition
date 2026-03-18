# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from URLs using the `feedparser` library
2. **Multi-Category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Data Persistence**: Saves parsed feed entries as JSON files in `~/.rreader/` directory
5. **Deduplication**: Uses timestamp as unique ID to prevent duplicate entries within a single fetch
6. **Feed Merging**: Combines multiple feed sources within a category into a single sorted list
7. **Configuration Management**: Automatically copies bundled feeds.json on first run and merges new categories from updates
8. **Flexible Author Display**: Supports per-category toggle for showing feed source vs. individual author names
9. **Graceful Time Handling**: Falls back from published_parsed to updated_parsed if needed
10. **Human-Readable Timestamps**: Formats dates as "HH:MM" for today, "MMM DD, HH:MM" for older entries
11. **Sorted Output**: Returns entries in reverse chronological order (newest first)

## Triage

### Critical (Production Blockers)

1. **No Error Recovery**: Silent failures when individual feeds timeout or return malformed data
2. **Missing Logging Infrastructure**: Debug mode exists but doesn't integrate with standard logging
3. **No Stale Data Detection**: System doesn't track or expire old cached data
4. **Collision-Prone ID Strategy**: Using timestamp as ID will cause overwrites when multiple entries share the same second

### High Priority (Reliability Issues)

5. **No Request Timeout**: Feed fetches can hang indefinitely
6. **Missing Rate Limiting**: No protection against hammering feed sources
7. **No Retry Logic**: Transient network failures cause permanent data loss
8. **Bare Exception Handling**: `except:` clauses catch and hide all errors including KeyboardInterrupt
9. **No Validation**: Doesn't verify feed schema or detect malicious/malformed data
10. **Synchronous Blocking**: Fetching multiple feeds happens serially, not concurrently

### Medium Priority (UX/Maintenance)

11. **No Incremental Updates**: Always refetches entire feeds instead of just new entries
12. **Missing Feed Health Monitoring**: No tracking of which feeds consistently fail
13. **No User Feedback**: Progress indication only available in log mode
14. **Hard-Coded Paths**: Data directory location not configurable via environment variables
15. **No Migration System**: Feed schema changes would break existing data files

### Low Priority (Nice-to-Have)

16. **No Content Filtering**: Can't filter entries by keyword, date range, or read status
17. **Missing Analytics**: No tracking of feed update frequency or entry volume
18. **No Export Functionality**: Data locked in proprietary JSON format
19. **Limited Timezone Support**: Single global timezone instead of per-feed configuration

## Plan

### Critical Fixes

**1. Error Recovery**
```python
# In get_feed_from_rss, wrap feed processing:
for feed in d.entries:
    try:
        # existing parsing logic
    except Exception as e:
        # Log the error with feed URL and entry details
        # Continue to next entry
        continue
```
Add a summary at the end: `return {"entries": rslt, "errors": error_list, "created_at": ts}`

**2. Logging Infrastructure**
```python
import logging

logger = logging.getLogger('rreader')
# Replace all sys.stdout.write and print statements with:
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse {url}: {e}")
```
Add configuration in `config.py` for log level and output destination.

**3. Stale Data Detection**
```python
# In the JSON output, add:
"expires_at": int(time.time()) + 3600  # 1 hour TTL

# Before returning cached data, check:
if cached_data.get("expires_at", 0) < time.time():
    # Refetch
```

**4. Collision-Resistant IDs**
```python
# Replace:
entries = {"id": ts, ...}
# With:
import hashlib
entry_id = hashlib.sha256(
    f"{ts}:{feed.link}:{feed.title}".encode()
).hexdigest()[:16]
entries = {"id": entry_id, "timestamp": ts, ...}
```

### High Priority

**5. Request Timeout**
```python
# Add to config.py:
FETCH_TIMEOUT = 30  # seconds

# In get_feed_from_rss:
import socket
socket.setdefaulttimeout(FETCH_TIMEOUT)
# Or use requests library with timeout parameter
```

**6. Rate Limiting**
```python
# Add throttling between requests:
import time
REQUEST_DELAY = 1.0  # seconds between feeds

for source, url in urls.items():
    time.sleep(REQUEST_DELAY)
    # fetch logic
```

**7. Retry Logic**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), 
       wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_feed(url):
    return feedparser.parse(url)
```

**8. Specific Exception Handling**
```python
# Replace all bare except: with:
except (feedparser.ParseError, KeyError, AttributeError) as e:
    logger.error(f"Parse error for {url}: {e}")
except (requests.Timeout, requests.ConnectionError) as e:
    logger.error(f"Network error for {url}: {e}")
```

**9. Input Validation**
```python
def validate_feed_entry(feed):
    required = ['link', 'title']
    if not all(hasattr(feed, attr) for attr in required):
        raise ValueError("Missing required fields")
    
    # Sanitize HTML in title
    from html import escape
    return escape(feed.title)
```

**10. Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=5) as executor:
    future_to_url = {
        executor.submit(fetch_feed, url): (source, url)
        for source, url in urls.items()
    }
    for future in as_completed(future_to_url):
        source, url = future_to_url[future]
        try:
            d = future.result()
            # process d
        except Exception as e:
            logger.error(f"Failed {url}: {e}")
```

### Medium Priority

**11. Incremental Updates**
```python
# Track last fetch per feed:
"last_entry_id": "abc123",
"last_fetch_timestamp": 1234567890

# On next fetch, filter entries:
if entry_id <= last_seen_id:
    break  # feedparser returns newest first
```

**12. Feed Health Monitoring**
```python
# Add to each feed's metadata:
"health": {
    "consecutive_failures": 0,
    "last_success": timestamp,
    "average_latency_ms": 450
}

# Skip feeds with consecutive_failures > 10
```

**13. Progress Feedback**
```python
# Add progress bar using tqdm:
from tqdm import tqdm

for source, url in tqdm(urls.items(), desc="Fetching feeds"):
    # fetch logic
```

**14. Configurable Paths**
```python
# In config.py:
DATA_DIR = os.environ.get('RREADER_DATA_DIR', 
                          str(Path.home()) + "/.rreader/")

# Use throughout instead of hard-coded p["path_data"]
```

**15. Migration System**
```python
# Add version field to JSON:
{"version": 2, "entries": [...]}

# Create migrations/ directory with:
# 001_add_entry_ids.py
# 002_add_expiry.py

def migrate():
    current_version = get_schema_version()
    for migration in get_pending_migrations(current_version):
        migration.apply()
        update_schema_version()
```

### Low Priority

**16. Content Filtering**
```python
def filter_entries(entries, after_date=None, keywords=None):
    filtered = entries
    if after_date:
        filtered = [e for e in filtered 
                   if e['timestamp'] >= after_date]
    if keywords:
        filtered = [e for e in filtered 
                   if any(kw in e['title'].lower() 
                         for kw in keywords)]
    return filtered
```

**17. Analytics**
```python
# Add metrics collection:
"stats": {
    "total_entries": 150,
    "entries_per_hour": 12.5,
    "avg_time_between_posts": 300
}
```

**18. Export Functionality**
```python
def export_opml(feeds):
    # Generate OPML XML from feeds.json
    pass

def export_atom(entries):
    # Convert to Atom feed format
    pass
```

**19. Per-Feed Timezones**
```python
# In feeds.json:
"feeds": {
    "TechCrunch": {
        "url": "...",
        "timezone": "America/Los_Angeles"
    }
}

# Parse with feed-specific timezone
```