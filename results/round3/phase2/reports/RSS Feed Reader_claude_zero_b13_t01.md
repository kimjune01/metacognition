# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a basic RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS feeds from configured URLs using `feedparser`
2. **Multi-category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Timestamp Normalization**: Converts feed timestamps to a configured timezone (KST/UTC+9)
4. **Human-readable Dates**: Formats dates as "HH:MM" for today or "MMM DD, HH:MM" for older entries
5. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries within a single fetch
6. **Sorted Output**: Orders entries by timestamp (newest first)
7. **JSON Storage**: Saves parsed feeds to category-specific JSON files (`rss_{category}.json`)
8. **Configuration Management**: 
   - Creates a data directory (`~/.rreader/`) on first run
   - Copies bundled feeds configuration if none exists
   - Merges new bundled categories into existing user configuration
9. **Optional Author Display**: Can show individual authors or just source names per category
10. **Selective Updates**: Can update a single category or all categories
11. **Logging**: Optional stdout logging of fetch progress

## Triage

### Critical Gaps
1. **No Error Handling** - `sys.exit()` on any exception kills the entire process
2. **No Feed Validation** - Missing or malformed bundled `feeds.json` will crash
3. **Duplicate ID Collisions** - Multiple entries with same timestamp overwrite each other
4. **No Data Directory Validation** - Race conditions and permission errors not handled

### High Priority Gaps
5. **No Rate Limiting** - Can hammer servers, risking IP bans
6. **No Timeout Configuration** - Slow feeds can hang indefinitely
7. **No Caching/Conditional Requests** - Re-downloads entire feeds every time (wastes bandwidth)
8. **No Entry Limit** - Unbounded memory usage for large feeds
9. **No Stale Data Detection** - Old cached files persist indefinitely

### Medium Priority Gaps
10. **Poor Observability** - No structured logging, metrics, or error counts
11. **No Content Sanitization** - Feed titles/URLs not validated or escaped
12. **Timezone Hardcoded** - Should be configurable per-user
13. **No Concurrent Fetching** - Sequential processing is slow for many feeds
14. **No Feed Health Monitoring** - Dead feeds not tracked or reported

### Low Priority Gaps
15. **No Entry Content** - Only captures title/link, not descriptions or full content
16. **No Read/Unread Tracking** - No way to mark entries as seen
17. **No Search/Filter** - Cannot search across entries
18. **No OPML Import/Export** - No standard feed list portability

## Plan

### 1. Error Handling (Critical)
**Changes needed:**
- Replace bare `except:` with specific exception handling for `feedparser.parse()`, file I/O, and JSON operations
- Remove `sys.exit()` calls; instead log errors and continue to next feed
- Add a summary report at the end listing failed feeds
- Wrap the entire feed processing loop in try-except to ensure partial results are saved

```python
failed_feeds = []
for source, url in urls.items():
    try:
        # existing code
    except (URLError, HTTPError, TimeoutError) as e:
        failed_feeds.append((source, url, str(e)))
        if log:
            sys.stderr.write(f" - Failed: {e}\n")
        continue
    except Exception as e:
        failed_feeds.append((source, url, f"Unexpected: {e}"))
        continue
```

### 2. Feed Validation (Critical)
**Changes needed:**
- Add JSON schema validation for `feeds.json` structure
- Validate that categories contain "feeds" dict and optional "show_author" bool
- Provide helpful error messages for malformed configurations
- Add a `--validate-config` CLI flag for testing

```python
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dict")
    for cat, settings in config.items():
        if "feeds" not in settings:
            raise ValueError(f"Category '{cat}' missing 'feeds' key")
        if not isinstance(settings["feeds"], dict):
            raise ValueError(f"Category '{cat}' feeds must be a dict")
```

### 3. Duplicate ID Handling (Critical)
**Changes needed:**
- Change ID generation to include source name: `f"{source}_{ts}"`
- Add a counter suffix for true collisions: `f"{source}_{ts}_{counter}"`
- Track seen IDs in a set during processing

```python
seen_ids = set()
counter = 0
base_id = f"{source}_{ts}"
entry_id = base_id
while entry_id in seen_ids:
    counter += 1
    entry_id = f"{base_id}_{counter}"
seen_ids.add(entry_id)
entries["id"] = entry_id
```

### 4. Data Directory Safety (Critical)
**Changes needed:**
- Use `os.makedirs(exist_ok=True)` with try-except for permission errors
- Add file locking for concurrent access to JSON files
- Validate write permissions before processing feeds
- Use atomic writes (write to temp file, then rename)

```python
import tempfile
temp_fd, temp_path = tempfile.mkstemp(dir=p["path_data"], suffix='.json')
try:
    with os.fdopen(temp_fd, 'w', encoding='utf-8') as f:
        f.write(json.dumps(rslt, ensure_ascii=False))
    os.replace(temp_path, final_path)
except:
    os.unlink(temp_path)
    raise
```

### 5. Rate Limiting (High Priority)
**Changes needed:**
- Add configurable delay between feed fetches (default 1 second)
- Implement per-domain rate limiting (track last fetch time per domain)
- Add to `config.py`: `RATE_LIMIT_DELAY = 1.0`

```python
import urllib.parse
from collections import defaultdict

last_fetch = defaultdict(float)
for source, url in urls.items():
    domain = urllib.parse.urlparse(url).netloc
    elapsed = time.time() - last_fetch[domain]
    if elapsed < RATE_LIMIT_DELAY:
        time.sleep(RATE_LIMIT_DELAY - elapsed)
    # fetch feed
    last_fetch[domain] = time.time()
```

### 6. Timeout Configuration (High Priority)
**Changes needed:**
- Add timeout parameter to feedparser (it uses underlying HTTP library)
- Set default to 30 seconds, make configurable
- Add to `config.py`: `FEED_TIMEOUT = 30`

```python
import socket
socket.setdefaulttimeout(FEED_TIMEOUT)
d = feedparser.parse(url)
```

### 7. Conditional Requests (High Priority)
**Changes needed:**
- Store `etag` and `modified` headers from previous fetch
- Pass them to `feedparser.parse()` for conditional requests
- Only update JSON if feed actually changed (check `d.status`)

```python
# Store in metadata file
metadata = {"etag": d.get("etag"), "modified": d.get("modified")}
# Next fetch
d = feedparser.parse(url, etag=old_etag, modified=old_modified)
if d.status == 304:  # Not modified
    continue
```

### 8. Entry Limits (High Priority)
**Changes needed:**
- Add `MAX_ENTRIES_PER_CATEGORY` config (default 100)
- Truncate sorted results before saving: `rslt[:MAX_ENTRIES_PER_CATEGORY]`
- Add per-feed entry limit to prevent one feed dominating

```python
MAX_ENTRIES_PER_FEED = 50
MAX_ENTRIES_PER_CATEGORY = 100

feed_entries = []
for feed in d.entries[:MAX_ENTRIES_PER_FEED]:
    # process
rslt = sorted(all_entries, reverse=True)[:MAX_ENTRIES_PER_CATEGORY]
```

### 9. Stale Data Detection (High Priority)
**Changes needed:**
- Add `MAX_AGE` config (e.g., 7 days)
- Filter out entries older than threshold
- Add warning if no new entries found

```python
MAX_AGE_SECONDS = 7 * 24 * 3600
now = int(time.time())
if (now - ts) > MAX_AGE_SECONDS:
    continue  # Skip old entry
```

### 10. Structured Logging (Medium Priority)
**Changes needed:**
- Replace print statements with Python `logging` module
- Add log levels (INFO, WARNING, ERROR)
- Include timestamps, categories, and feed counts
- Optionally log to file

```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)
logger.info(f"Fetching {len(urls)} feeds for category '{category}'")
```

### 11. Content Sanitization (Medium Priority)
**Changes needed:**
- HTML-escape titles and URLs before storing
- Validate URLs are http/https schemes
- Truncate excessively long titles (e.g., 500 chars)

```python
import html
from urllib.parse import urlparse

title = html.escape(feed.title[:500])
parsed = urlparse(feed.link)
if parsed.scheme not in ('http', 'https'):
    continue  # Skip invalid URL
```

### 12. Configurable Timezone (Medium Priority)
**Changes needed:**
- Move TIMEZONE to `feeds.json` as optional top-level key
- Default to UTC if not specified
- Parse timezone string (e.g., "UTC+9", "America/New_York")

```python
from zoneinfo import ZoneInfo  # Python 3.9+
tz_str = RSS.get("timezone", "UTC")
TIMEZONE = ZoneInfo(tz_str)
```

### 13. Concurrent Fetching (Medium Priority)
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetches
- Limit to 5-10 concurrent connections
- Maintain rate limiting per domain

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # existing fetch logic
    return source, result

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source, result = future.result()
        # aggregate results
```

### 14. Feed Health Monitoring (Medium Priority)
**Changes needed:**
- Track consecutive failures per feed in metadata file
- Mark feeds as "dead" after 5 consecutive failures
- Add `--health-check` command to report feed status

```python
health = {"url": url, "last_success": timestamp, 
          "consecutive_failures": 0, "status": "active"}
# Update after each fetch
if success:
    health["consecutive_failures"] = 0
else:
    health["consecutive_failures"] += 1
    if health["consecutive_failures"] >= 5:
        health["status"] = "dead"
```

### 15-18. Lower Priority Features
These would be implemented as separate enhancement projects after stabilizing core functionality. Each would require significant new modules (content storage, user preferences DB, search indexing, OPML parser/generator).