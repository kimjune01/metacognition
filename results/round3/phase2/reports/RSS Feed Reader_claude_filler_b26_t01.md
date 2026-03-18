# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-Source Aggregation**: Supports organizing feeds into categories, with multiple feed URLs per category
3. **Data Persistence**: Stores parsed feed entries as JSON files in a user directory (`~/.rreader/`)
4. **Timestamp Normalization**: Converts feed publish times to a configurable timezone (currently KST/UTC+9)
5. **Entry Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
6. **Feed Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled feeds into existing user configuration
7. **Flexible Author Display**: Supports per-category option to show article authors vs. source names
8. **Sorted Output**: Presents entries in reverse chronological order (newest first)
9. **Selective Updates**: Can update a single category or all categories
10. **Basic Logging**: Optional stdout logging of fetch progress

## Triage

### Critical Gaps (P0)
1. **No Error Recovery**: Feed fetch failures cause silent data loss; partial failures abort processing
2. **No HTTP Timeout Configuration**: Network hangs can block indefinitely
3. **Missing Data Validation**: Malformed feed data can crash the process
4. **No Stale Data Management**: Old entries accumulate indefinitely; no TTL or pruning

### High Priority Gaps (P1)
5. **Inadequate Error Reporting**: Exceptions are caught but not logged meaningfully
6. **No Rate Limiting**: Simultaneous requests to many feeds could trigger rate limits or overwhelm networks
7. **No Caching Headers**: Ignores ETags and Last-Modified, causing unnecessary bandwidth usage
8. **Collision-Prone ID Generation**: Unix timestamps can collide for rapid publications from the same source
9. **No Feed Health Monitoring**: No tracking of which feeds are consistently failing or slow

### Medium Priority Gaps (P2)
10. **No Content Sanitization**: Feed titles/content could contain malicious HTML/JavaScript
11. **Hardcoded Timezone**: Timezone is not user-configurable outside code modification
12. **No Feed Validation on Add**: `feeds.json` can contain invalid URLs without detection
13. **No Concurrency**: Sequential processing makes updates slow with many feeds
14. **Limited Date Formatting**: Only supports "HH:MM" for today or "MMM DD, HH:MM" format
15. **No Incremental Updates**: Always fetches entire feeds, even when only new entries are needed

### Low Priority Gaps (P3)
16. **No User Feedback UI**: No progress indication for long operations
17. **No Feed Statistics**: No visibility into entry counts, update frequency, or data freshness
18. **Missing Configuration Options**: No control over entry limits per feed, retention periods, etc.
19. **No Import/Export**: Cannot backup or share feed configurations easily

## Plan

### P0 Fixes

**1. Error Recovery**
```python
# Change: Wrap individual feed processing in try-except
for source, url in urls.items():
    try:
        # existing code
    except Exception as e:
        if log:
            sys.stderr.write(f" - Failed: {str(e)}\n")
        # Log to error file: append to ~/.rreader/errors.log with timestamp
        continue  # Process remaining feeds instead of exiting
```

**2. HTTP Timeout Configuration**
```python
# Change: Add timeout parameter to feedparser
d = feedparser.parse(url, timeout=30)  # 30 second timeout

# Add to config.py:
HTTP_TIMEOUT = 30  # seconds
```

**3. Data Validation**
```python
# Change: Validate required fields before processing
required_fields = ['link', 'title']
if not all(hasattr(feed, field) for field in required_fields):
    continue

# Validate URL format
from urllib.parse import urlparse
parsed = urlparse(feed.link)
if not all([parsed.scheme, parsed.netloc]):
    continue
```

**4. Stale Data Management**
```python
# Add to config.py:
MAX_ENTRY_AGE_DAYS = 30
MAX_ENTRIES_PER_FEED = 100

# Change: Filter old entries before saving
cutoff_timestamp = int(time.time()) - (MAX_ENTRY_AGE_DAYS * 86400)
rslt = {k: v for k, v in rslt.items() if v['timestamp'] > cutoff_timestamp}

# Limit total entries
rslt = dict(sorted(rslt.items(), reverse=True)[:MAX_ENTRIES_PER_FEED])
```

### P1 Fixes

**5. Error Reporting**
```python
# Add structured logging
import logging

logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Change: Log all exceptions with context
except Exception as e:
    logging.error(f"Failed to fetch {url} from {source}: {type(e).__name__}: {str(e)}")
```

**6. Rate Limiting**
```python
# Add to config.py:
REQUEST_DELAY_SECONDS = 0.5

# Change: Add delay between requests
import time
for source, url in urls.items():
    # existing fetch code
    time.sleep(REQUEST_DELAY_SECONDS)
```

**7. Caching Headers**
```python
# Add cache storage to track ETags/Last-Modified per feed
# Create ~/.rreader/cache_metadata.json:
# {"feed_url": {"etag": "...", "last_modified": "...", "last_fetched": timestamp}}

# Change: Pass cached values to feedparser
cache_meta = load_cache_metadata()
etag = cache_meta.get(url, {}).get('etag')
modified = cache_meta.get(url, {}).get('last_modified')
d = feedparser.parse(url, etag=etag, modified=modified)

if d.status == 304:  # Not modified
    continue  # Use existing data

# Save new etag/modified from d.etag and d.modified
```

**8. Unique ID Generation**
```python
# Change: Use composite key for ID
import hashlib
unique_str = f"{feed.link}|{ts}|{source}"
entry_id = hashlib.sha256(unique_str.encode()).hexdigest()[:16]

entries = {
    "id": entry_id,
    # rest of fields
}
```

**9. Feed Health Monitoring**
```python
# Create ~/.rreader/feed_health.json tracking:
# {"feed_url": {"success_count": N, "fail_count": M, "last_success": timestamp, 
#               "last_error": "error message", "avg_fetch_time_ms": X}}

# Change: Update health metrics after each fetch
start = time.time()
# ... fetch code ...
elapsed_ms = (time.time() - start) * 1000
update_feed_health(url, success=True, fetch_time_ms=elapsed_ms)
```

### P2 Fixes

**10. Content Sanitization**
```python
# Add dependency: pip install bleach
import bleach

# Change: Sanitize text fields
safe_title = bleach.clean(feed.title, tags=[], strip=True)
entries = {
    "title": safe_title,
    # ...
}
```

**11. User-Configurable Timezone**
```python
# Add to feeds.json schema:
# {"timezone": "Asia/Seoul", "categories": {...}}

# Change config.py:
import pytz
def get_timezone():
    with open(FEEDS_FILE_NAME, 'r') as f:
        config = json.load(f)
    tz_name = config.get('timezone', 'Asia/Seoul')
    return pytz.timezone(tz_name)
```

**12. Feed URL Validation**
```python
# Add validation function
def validate_feed_config(config):
    for category, data in config.items():
        for source, url in data.get('feeds', {}).items():
            parsed = urlparse(url)
            if parsed.scheme not in ['http', 'https']:
                raise ValueError(f"Invalid URL scheme for {source}: {url}")
    return True

# Call after loading feeds.json
```

**13. Concurrent Processing**
```python
# Add concurrent.futures for parallel fetches
from concurrent.futures import ThreadPoolExecutor, as_completed

# Change: Process feeds in parallel
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, source, url): source 
               for source, url in urls.items()}
    for future in as_completed(futures):
        source = futures[future]
        try:
            result = future.result()
            # merge result into rslt
        except Exception as e:
            logging.error(f"Failed {source}: {e}")
```

**14. Flexible Date Formatting**
```python
# Add to config.py or feeds.json:
DATE_FORMAT_TODAY = "%H:%M"
DATE_FORMAT_OTHER = "%b %d, %H:%M"
DATE_FORMAT_OLD = "%Y-%m-%d"  # for entries > 1 year old

# Change: Format based on age
if at.date() == datetime.date.today():
    pubDate = at.strftime(DATE_FORMAT_TODAY)
elif (datetime.date.today() - at.date()).days < 365:
    pubDate = at.strftime(DATE_FORMAT_OTHER)
else:
    pubDate = at.strftime(DATE_FORMAT_OLD)
```

**15. Incremental Updates**
```python
# Change: Load existing entries and merge new ones
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(existing_file):
    with open(existing_file, 'r') as f:
        existing = json.load(f)
    existing_entries = {e['id']: e for e in existing.get('entries', [])}
    # Merge: new entries take precedence
    rslt.update(existing_entries)
```

### P3 Fixes

**16-19: Implementation Patterns**

**User Feedback**: Add progress bar using `tqdm` library, showing "Fetching X/N feeds"

**Statistics**: Create `~/.rreader/stats.json` with per-category counts, timestamps, avg entries per update

**Configuration Options**: Extend feeds.json schema with `"settings": {"max_entries": 100, "retention_days": 30}`

**Import/Export**: Add CLI commands `--export feeds.json` and `--import feeds.json` with validation