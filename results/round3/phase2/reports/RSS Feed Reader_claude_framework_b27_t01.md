# Diagnostic Report: RSS Feed Reader System

## Observations

This system implements a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Uses `feedparser` to fetch and parse RSS/Atom feeds from URLs defined in a JSON configuration file.

2. **Configuration management**: 
   - Stores feed sources in `~/.rreader/feeds.json`
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled config into user config on subsequent runs

3. **Data normalization**: Converts feed entries into a consistent format with:
   - Timestamp-based IDs
   - Source attribution
   - Human-readable publication dates (relative for today, absolute otherwise)
   - URLs and titles

4. **Time zone handling**: Converts UTC timestamps to configured timezone (currently KST/UTC+9)

5. **Output persistence**: Writes processed feeds to JSON files (`rss_{category}.json`) with timestamp metadata

6. **Deduplication**: Uses timestamp as ID to prevent duplicate entries within a category

7. **Category isolation**: Processes feeds by category, allowing targeted or batch updates

8. **Sorting**: Returns entries in reverse chronological order

## Triage

### Critical (blocks production use)

1. **No error recovery**: Single feed failure crashes entire category processing
2. **No rate limiting**: Risks being blocked by feed providers
3. **No staleness detection**: Cannot determine if cached data is outdated
4. **Silent data loss**: Overwrites existing data without merging; no history preserved

### High (degrades reliability)

5. **No retry logic**: Network hiccups cause permanent failures until next run
6. **No timeout configuration**: Hung requests block indefinitely
7. **No feed validation**: Accepts malformed URLs or invalid JSON without sanitization
8. **No logging framework**: Debug information only available via boolean flag to stdout

### Medium (limits functionality)

9. **No incremental updates**: Re-fetches entire feeds even for unchanged content
10. **No entry limit**: Unbounded memory usage for feeds with thousands of items
11. **No content extraction**: Only captures title/link, ignoring summary/description
12. **No read/unread tracking**: No way to mark entries as consumed

### Low (quality-of-life)

13. **Hard-coded timezone**: Configuration exists but no CLI/config override
14. **No feed health monitoring**: Cannot detect broken or abandoned feeds
15. **No OPML import/export**: Manual JSON editing required for feed management

## Plan

### 1. Error recovery (Critical)
**Change**: Wrap individual feed processing in try-except blocks
```python
for source, url in urls.items():
    try:
        # existing parse logic
    except Exception as e:
        if log:
            sys.stderr.write(f"Failed to fetch {url}: {e}\n")
        continue  # process remaining feeds
```
**Impact**: System continues working even if some feeds fail

### 2. Rate limiting (Critical)
**Change**: Add delay between requests and respect robots.txt
```python
import time
from urllib.robotparser import RobotFileParser

# At module level
RATE_LIMIT_SECONDS = 1.0

# In loop
time.sleep(RATE_LIMIT_SECONDS)
```
**Impact**: Prevents IP bans from aggressive crawling

### 3. Staleness detection (Critical)
**Change**: Store `last_fetched` timestamp and compare against current data age
```python
# Before writing
rslt["last_fetched"] = int(time.time())

# On read
if time.time() - cached_data["last_fetched"] > MAX_AGE_SECONDS:
    # trigger refresh
```
**Impact**: Enables conditional updates and cache expiry

### 4. Data merging (Critical)
**Change**: Load existing data and merge with new entries by ID
```python
existing = {}
if os.path.exists(output_path):
    with open(output_path) as f:
        existing = {e["id"]: e for e in json.load(f)["entries"]}

# After parsing new entries
existing.update(rslt)  # newer entries overwrite
rslt = list(existing.values())
```
**Impact**: Preserves history and enables incremental updates

### 5. Retry logic (High)
**Change**: Use exponential backoff for transient failures
```python
from urllib.error import URLError

MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        d = feedparser.parse(url)
        break
    except URLError as e:
        if attempt == MAX_RETRIES - 1:
            raise
        time.sleep(2 ** attempt)
```
**Impact**: Handles temporary network issues gracefully

### 6. Timeout configuration (High)
**Change**: Add timeout to feedparser via socket default timeout
```python
import socket
socket.setdefaulttimeout(30)  # seconds
```
**Impact**: Prevents hung processes on slow/dead endpoints

### 7. Input validation (High)
**Change**: Validate URLs and sanitize JSON at load time
```python
from urllib.parse import urlparse

def validate_url(url):
    parsed = urlparse(url)
    return all([parsed.scheme in ('http', 'https'), parsed.netloc])

# Before parsing
if not validate_url(url):
    sys.stderr.write(f"Invalid URL: {url}\n")
    continue
```
**Impact**: Fails fast on configuration errors

### 8. Structured logging (High)
**Change**: Replace print statements with logging module
```python
import logging
logger = logging.getLogger(__name__)

# Replace sys.stdout.write
logger.info(f"Fetching {url}")
logger.error(f"Failed: {e}")
```
**Impact**: Enables log levels, file output, structured formatting

### 9. ETag/Last-Modified support (Medium)
**Change**: Store HTTP headers and send conditional requests
```python
# feedparser automatically handles this if you pass previous result
d = feedparser.parse(url, etag=cached_etag, modified=cached_modified)
if d.status == 304:  # Not Modified
    continue
```
**Impact**: Reduces bandwidth by 90%+ for unchanged feeds

### 10. Entry limiting (Medium)
**Change**: Add configurable max entries per feed
```python
MAX_ENTRIES_PER_FEED = 100
rslt = sorted(rslt.items(), reverse=True)[:MAX_ENTRIES_PER_FEED]
```
**Impact**: Bounds memory usage and JSON file size

### 11. Content extraction (Medium)
**Change**: Add summary field to entry schema
```python
entries["summary"] = getattr(feed, "summary", "")[:500]  # truncate
```
**Impact**: Enables preview without clicking through

### 12. Read tracking (Medium)
**Change**: Add `read` boolean field and update mechanism
```python
entries["read"] = False

# New function
def mark_read(category, entry_id):
    data = load_category(category)
    for entry in data["entries"]:
        if entry["id"] == entry_id:
            entry["read"] = True
    save_category(category, data)
```
**Impact**: Enables filtering for unread items only

### 13. Timezone configuration (Low)
**Change**: Accept timezone as CLI argument or env var
```python
import os
tz_offset = int(os.getenv("RSS_TZ_OFFSET", "9"))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```
**Impact**: Makes tool usable across time zones

### 14. Feed health monitoring (Low)
**Change**: Track consecutive failures and last success time
```python
# In feeds.json per-feed
"meta": {
    "consecutive_failures": 0,
    "last_success": timestamp,
    "last_error": "message"
}
```
**Impact**: Enables automated cleanup of dead feeds

### 15. OPML support (Low)
**Change**: Add import/export functions using xml.etree
```python
def import_opml(filepath):
    tree = ET.parse(filepath)
    for outline in tree.findall(".//outline[@xmlUrl]"):
        # extract title, xmlUrl, category
        # add to feeds.json
```
**Impact**: Compatibility with standard feed readers