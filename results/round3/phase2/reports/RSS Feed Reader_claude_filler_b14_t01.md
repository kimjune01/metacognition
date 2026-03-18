# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Successfully fetches and parses RSS/Atom feeds using the `feedparser` library
2. **Multi-source Aggregation**: Handles multiple feed sources per category from a JSON configuration file
3. **Time Zone Handling**: Converts feed timestamps to a configured timezone (KST/UTC+9) and formats them for display
4. **Data Persistence**: Saves parsed feed entries as JSON files in a user data directory (`~/.rreader/`)
5. **Deduplication**: Uses timestamp-based dictionary keys to eliminate duplicate entries within a single fetch
6. **Configuration Management**: 
   - Bundles default feeds with the application
   - Copies bundled feeds to user directory on first run
   - Merges new categories from bundled config into existing user config
7. **Sorted Output**: Returns entries sorted by timestamp (newest first)
8. **Flexible Execution**: Supports fetching either all categories or a specific target category
9. **Author Display**: Configurable per-category author/source attribution
10. **Date Formatting**: Smart date display (time-only for today, date+time for older entries)

## Triage

### Critical Gaps (P0)
1. **No Error Handling for Individual Feeds**: The try-except block exits the entire program on URL fetch failure, preventing other feeds from being processed
2. **No Caching/Rate Limiting**: Fetches all feeds on every run with no consideration for HTTP 304/ETags or politeness delays
3. **Silent Failures**: Failed feed parsing returns nothing without logging what went wrong
4. **No Feed Validation**: Doesn't verify feed structure or handle malformed feeds gracefully

### Important Gaps (P1)
5. **No Data Retention Strategy**: Old JSON files accumulate indefinitely; no cleanup mechanism
6. **No Network Timeout Configuration**: Can hang indefinitely on slow/unresponsive feeds
7. **Missing Duplicate Detection Across Fetches**: Only deduplicates within a single run, not against previously cached entries
8. **No User Feedback in Normal Mode**: Only logs when `log=True`, providing no progress indication by default
9. **No Feed Health Monitoring**: Doesn't track which feeds consistently fail or return no entries

### Enhancement Gaps (P2)
10. **No Concurrency**: Fetches feeds sequentially, making updates slow for many sources
11. **Limited Metadata Extraction**: Ignores descriptions, thumbnails, categories, and other useful feed metadata
12. **No Read/Unread Tracking**: No mechanism to mark or filter previously seen entries
13. **Hardcoded Timezone**: Timezone is configured in code rather than user configuration
14. **No Feed Discovery**: Can't add feeds from the UI; requires manual JSON editing
15. **Missing Entry Content**: Doesn't extract or store article summaries/descriptions
16. **No OPML Import/Export**: Can't import/export feed lists in standard format

## Plan

### P0 Fixes

#### 1. Error Handling for Individual Feeds
**Changes needed:**
- Replace `sys.exit()` in the except block with logging and continuation
- Accumulate errors in a list and return/log them at the end
- Add specific exception types (network errors, parse errors, timeout errors)

```python
failed_feeds = []
for source, url in urls.items():
    try:
        # existing code
    except requests.exceptions.Timeout:
        failed_feeds.append((source, url, "timeout"))
        if log:
            sys.stdout.write(" - Timeout\n")
        continue
    except Exception as e:
        failed_feeds.append((source, url, str(e)))
        if log:
            sys.stdout.write(f" - Failed: {e}\n")
        continue
```

#### 2. Caching and Rate Limiting
**Changes needed:**
- Add HTTP conditional GET support using ETags/Last-Modified headers
- Store last-fetch timestamps per feed in metadata file
- Implement minimum fetch interval (e.g., 15 minutes)
- Add configurable delay between feed requests (e.g., 1 second)

```python
# In get_feed_from_rss, before loop:
metadata = load_feed_metadata(category)
time.sleep(1)  # Between each feed fetch

# In feedparser.parse call:
etag = metadata.get(source, {}).get('etag')
modified = metadata.get(source, {}).get('modified')
d = feedparser.parse(url, etag=etag, modified=modified)
if d.status == 304:  # Not modified
    continue
```

#### 3. Comprehensive Logging
**Changes needed:**
- Add proper logging module instead of print statements
- Log all failures with context (timestamp, feed source, error type)
- Create rotating log files in the data directory
- Add verbosity levels (ERROR, WARNING, INFO, DEBUG)

```python
import logging
logger = logging.getLogger('rreader')
handler = logging.handlers.RotatingFileHandler(
    os.path.join(p["path_data"], 'rreader.log'),
    maxBytes=1048576, backupCount=3
)
logger.addHandler(handler)
```

#### 4. Feed Validation
**Changes needed:**
- Check for required feed attributes before accessing them
- Validate entry structure (has link, has title)
- Skip malformed entries rather than crashing
- Log validation failures with details

```python
if not hasattr(d, 'entries') or not d.entries:
    logger.warning(f"No entries found in {source}: {url}")
    continue

for feed in d.entries:
    if not hasattr(feed, 'link') or not hasattr(feed, 'title'):
        logger.debug(f"Skipping malformed entry in {source}")
        continue
```

### P1 Fixes

#### 5. Data Retention Strategy
**Changes needed:**
- Add configurable max age for entries (e.g., 30 days)
- Implement cleanup function that runs on startup
- Add max entries per category limit
- Archive old entries to separate files rather than deleting

```python
def cleanup_old_entries(category, max_age_days=30):
    cutoff = time.time() - (max_age_days * 86400)
    # Filter entries, move old ones to archive
```

#### 6. Network Timeout Configuration
**Changes needed:**
- Add timeout parameter to feedparser.parse() (requires custom HTTP headers)
- Add timeout configuration to feeds.json
- Set reasonable defaults (connect: 10s, read: 30s)

```python
# Add to config.py:
DEFAULT_TIMEOUT = (10, 30)  # connect, read

# Modify feedparser call:
import requests
response = requests.get(url, timeout=DEFAULT_TIMEOUT)
d = feedparser.parse(response.content)
```

#### 7. Cross-Fetch Duplicate Detection
**Changes needed:**
- Load existing entries from JSON before fetching
- Compare new entries against existing by URL or GUID
- Merge new entries with existing, preserving metadata
- Track "first seen" timestamp separately from published timestamp

```python
existing_data = load_existing_entries(category)
existing_urls = {e['url'] for e in existing_data.get('entries', [])}
# In loop:
if entries['url'] in existing_urls:
    continue
```

#### 8. User Feedback System
**Changes needed:**
- Add progress bar library (tqdm) or simple counter
- Show "Fetching X of Y feeds..." messages
- Display summary statistics after completion
- Add `--quiet` flag to suppress all output

```python
from tqdm import tqdm
for source, url in tqdm(urls.items(), desc=f"Fetching {category}"):
    # existing code
```

#### 9. Feed Health Monitoring
**Changes needed:**
- Track success/failure count per feed in metadata
- Record last successful fetch timestamp
- Flag feeds with >80% failure rate
- Add health report command to show feed statistics

```python
metadata[source] = {
    'last_success': timestamp if success else metadata.get('last_success'),
    'failures': metadata.get('failures', 0) + (0 if success else 1),
    'attempts': metadata.get('attempts', 0) + 1
}
```

### P2 Enhancements

#### 10. Concurrent Fetching
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetches
- Add configurable worker pool size (default: 5)
- Maintain rate limiting across threads
- Add timeout for entire fetch operation

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # Move inner logic here
    
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        # Process results
```

#### 11. Extended Metadata Extraction
**Changes needed:**
- Extract summary/description field
- Extract media enclosures (podcasts, images)
- Extract categories/tags
- Store all in JSON output
- Add schema version to output for migrations

```python
entries = {
    # existing fields...
    "description": getattr(feed, 'summary', ''),
    "content": getattr(feed, 'content', [{}])[0].get('value', ''),
    "thumbnail": extract_thumbnail(feed),
    "tags": getattr(feed, 'tags', []),
}
```

#### 12. Read/Unread Tracking
**Changes needed:**
- Add "read" boolean to each entry
- Create separate index file mapping entry IDs to read status
- Add mark-as-read API function
- Filter entries by read status in output

```python
def mark_as_read(category, entry_id):
    read_status = load_read_status(category)
    read_status[entry_id] = True
    save_read_status(category, read_status)
```

#### 13. User-Configurable Timezone
**Changes needed:**
- Move TIMEZONE from config.py to feeds.json or separate settings file
- Add timezone validation
- Provide timezone selector or UTC offset configuration
- Default to system timezone if not specified

```python
# In feeds.json:
{"settings": {"timezone": "Asia/Seoul"}}

# In code:
import pytz
tz = pytz.timezone(settings.get('timezone', 'UTC'))
```

#### 14. Feed Management UI/API
**Changes needed:**
- Add `add_feed(category, name, url)` function
- Add `remove_feed(category, name)` function
- Add feed validation before adding
- Auto-detect feed URL from website URL
- Support folder/category creation

```python
def add_feed(category, name, url):
    # Validate URL returns valid feed
    test = feedparser.parse(url)
    if not test.entries:
        raise ValueError("Not a valid feed")
    # Add to feeds.json
```

#### 15. Entry Content Storage
**Changes needed:**
- Extract full content/summary from feeds
- Handle multiple content types (HTML, text)
- Sanitize HTML to prevent XSS
- Add content length limits to prevent bloat

```python
from bleach import clean
content = clean(feed.summary, tags=['p', 'br', 'a'], strip=True)
entries['content'] = content[:5000]  # Limit length
```

#### 16. OPML Support
**Changes needed:**
- Add `export_opml()` function that generates OPML XML
- Add `import_opml(file)` function that parses and adds feeds
- Map OPML categories to internal categories
- Handle duplicate detection on import

```python
import xml.etree.ElementTree as ET

def export_opml():
    opml = ET.Element('opml', version='2.0')
    body = ET.SubElement(opml, 'body')
    # Generate XML from feeds.json
    return ET.tostring(opml)
```