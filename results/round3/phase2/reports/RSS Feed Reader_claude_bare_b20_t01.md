# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-source Aggregation**: Processes multiple feed URLs organized by category from a JSON configuration file
3. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
4. **Time Localization**: Converts feed timestamps to a configured timezone (KST/UTC+9)
5. **Smart Date Formatting**: Shows time-only for today's entries, full date for older entries
6. **Data Persistence**: Saves parsed feeds as JSON files in `~/.rreader/` directory
7. **Configuration Management**: 
   - Copies bundled `feeds.json` if user has none
   - Merges new categories from bundled config into existing user config
8. **Flexible Author Display**: Supports per-category toggle for showing feed author vs. source name
9. **Selective Processing**: Can process a single category or all categories
10. **Basic Error Handling**: Try-catch blocks around feed parsing and time parsing

## Triage

### Critical Gaps
1. **No Error Recovery**: System exits entirely on RSS parse failure in log mode, no retry logic
2. **Missing Feed Validation**: No checks for malformed feeds, missing required fields, or network timeouts
3. **No Logging Infrastructure**: Only basic stdout writes; no proper logging levels, file logs, or error tracking
4. **Race Conditions**: No file locking when writing JSON files (concurrent runs could corrupt data)

### High Priority Gaps
5. **No Rate Limiting**: Could hammer RSS servers with requests; no delays between feeds
6. **Missing Caching Strategy**: No HTTP caching headers (ETag, Last-Modified) utilized; wasteful bandwidth
7. **No Feed Health Monitoring**: No tracking of feed failures, staleness, or quality metrics
8. **Hardcoded Timezone**: Timezone is fixed in config rather than configurable per-user
9. **No Entry Content**: Only saves title/link; no description, summary, or content body
10. **Missing Data Retention**: Old entries accumulate indefinitely; no pruning logic

### Medium Priority Gaps
11. **No Progress Indication**: For long-running multi-feed operations, no progress bar or status
12. **Limited Configuration Options**: No user-configurable settings for timeout, max entries, date formats
13. **No Incremental Updates**: Always rewrites entire feed file; no merging with existing entries
14. **Missing Export Functionality**: No way to export to OPML or other standard formats
15. **No Feed Discovery**: Cannot automatically find RSS feeds from website URLs

### Low Priority Gaps
16. **Basic CLI Interface**: No argument parsing for options like `--verbose`, `--force-refresh`
17. **No Read/Unread Tracking**: Cannot mark entries as read or filter by read status
18. **No Search Capability**: Cannot search across entries by keyword
19. **No Notification System**: No alerts for new entries matching criteria

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Replace `sys.exit()` in exception handler with proper error logging and continue
- Add retry logic with exponential backoff for network failures
- Create a `FailedFeed` data structure to track and report failures
```python
# Replace sys.exit with:
if log:
    print(f" - Failed: {str(e)}\n")
failed_feeds.append({'source': source, 'url': url, 'error': str(e)})
continue
```

### 2. Feed Validation (Critical)
**Changes needed:**
- Add `feedparser.bozo` check for malformed XML
- Set request timeout in feedparser (use `urllib` with timeout parameter)
- Validate required fields before processing
```python
d = feedparser.parse(url, timeout=30)
if d.bozo:
    log_error(f"Malformed feed: {url}, {d.bozo_exception}")
    continue
```

### 3. Proper Logging Infrastructure (Critical)
**Changes needed:**
- Add `import logging` and configure logger with file handler
- Replace `sys.stdout.write()` with `logging.info/error/debug()`
- Create log directory in `p['path_data']` with rotating file handler
```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p['path_data'], 'rreader.log')),
        logging.StreamHandler()
    ]
)
```

### 4. File Locking (Critical)
**Changes needed:**
- Import `fcntl` (Unix) or `msvcrt` (Windows) for file locking
- Wrap JSON writes in lock/unlock calls
- Alternative: use `filelock` library for cross-platform support
```python
import filelock
lock = filelock.FileLock(os.path.join(p["path_data"], f"rss_{category}.json.lock"))
with lock:
    with open(...) as f:
        f.write(json.dumps(rslt, ensure_ascii=False))
```

### 5. Rate Limiting (High Priority)
**Changes needed:**
- Add `time.sleep(1)` between feed fetches (configurable delay)
- Implement token bucket algorithm for more sophisticated limiting
- Add per-domain tracking to avoid hammering single servers
```python
FEED_FETCH_DELAY = 1.0  # seconds
for source, url in urls.items():
    # ... fetch feed ...
    time.sleep(FEED_FETCH_DELAY)
```

### 6. HTTP Caching (High Priority)
**Changes needed:**
- Store ETag and Last-Modified headers from previous fetch
- Add conditional request headers on subsequent fetches
- Check HTTP 304 Not Modified responses
```python
# Store in metadata:
cache_headers = {'etag': d.etag, 'last_modified': d.modified}
# On next fetch:
d = feedparser.parse(url, etag=cached_etag, modified=cached_modified)
if d.status == 304:
    continue  # No new content
```

### 7. Feed Health Monitoring (High Priority)
**Changes needed:**
- Create `feed_stats.json` to track per-feed metrics
- Record: last successful fetch, consecutive failures, average entry count
- Add function to report unhealthy feeds
```python
stats = {
    'last_success': timestamp,
    'failure_count': 0,
    'total_fetches': count,
    'avg_entries': avg
}
```

### 8. Configurable Timezone (High Priority)
**Changes needed:**
- Move TIMEZONE to feeds.json or separate user config
- Add timezone selection in configuration
- Fallback to system timezone if not specified
```python
# In feeds.json:
{"settings": {"timezone": "Asia/Seoul"}}
# Parse with:
import pytz
TIMEZONE = pytz.timezone(config.get('timezone', 'UTC'))
```

### 9. Entry Content Storage (High Priority)
**Changes needed:**
- Add `description`, `summary`, and `content` fields to entries dict
- Handle multiple content types (HTML, plain text)
- Optionally sanitize HTML content
```python
entries.update({
    "description": getattr(feed, 'description', ''),
    "summary": getattr(feed, 'summary', ''),
    "content": feed.content[0].value if hasattr(feed, 'content') else ''
})
```

### 10. Data Retention Policy (High Priority)
**Changes needed:**
- Add `max_age_days` configuration parameter
- Before writing, filter out entries older than threshold
- Optionally archive old entries to separate file
```python
MAX_AGE_DAYS = config.get('max_age_days', 30)
cutoff = time.time() - (MAX_AGE_DAYS * 86400)
rslt = [e for e in rslt if e['timestamp'] > cutoff]
```

### 11. Progress Indication (Medium Priority)
**Changes needed:**
- Import `tqdm` library for progress bars
- Wrap feed iteration with progress bar
```python
from tqdm import tqdm
for source, url in tqdm(urls.items(), desc=f"Fetching {category}"):
    # ... process feed ...
```

### 12. User Configuration (Medium Priority)
**Changes needed:**
- Create `config.json` separate from `feeds.json`
- Support settings: timeout, max_entries, date_format, timezone
- Load config early in `do()` function
```python
CONFIG_FILE = os.path.join(p['path_data'], 'config.json')
default_config = {
    'timeout': 30,
    'max_entries_per_feed': 100,
    'date_format': '%b %d, %H:%M'
}
```

### 13. Incremental Updates (Medium Priority)
**Changes needed:**
- Load existing entries before fetching new ones
- Merge by ID, keeping existing entries
- Only fetch feeds if cache is older than refresh interval
```python
existing = load_existing_entries(category)
new_entries = {e['id']: e for e in fetch_new_entries()}
existing.update(new_entries)
```

### 14. OPML Export (Medium Priority)
**Changes needed:**
- Add `export_opml()` function
- Generate XML with all feed URLs organized by category
```python
def export_opml(output_file):
    # Create XML structure with all feeds
    # Write to output_file
```

### 15. Feed Discovery (Medium Priority)
**Changes needed:**
- Add function to parse HTML for `<link rel="alternate">` tags
- Use `BeautifulSoup` to find RSS/Atom feed URLs
```python
def discover_feeds(url):
    # Parse HTML, find feed links
    return list_of_feed_urls
```

### 16. CLI Argument Parsing (Low Priority)
**Changes needed:**
- Import `argparse`
- Add arguments: `--category`, `--verbose`, `--force`, `--config`
```python
parser = argparse.ArgumentParser()
parser.add_argument('--category', help='Process single category')
parser.add_argument('--verbose', action='store_true')
args = parser.parse_args()
```

### 17. Read/Unread Tracking (Low Priority)
**Changes needed:**
- Add `read: false` boolean to each entry
- Create function to mark entries as read by ID
- Store read state in separate file or database
```python
def mark_read(entry_ids):
    read_state[entry_id] = {'read': True, 'read_at': time.time()}
```

### 18. Search Capability (Low Priority)
**Changes needed:**
- Add `search()` function taking query string
- Search across title, description, content fields
- Return matching entries sorted by relevance
```python
def search(query, category=None):
    # Load all entries, filter by query match
    return matching_entries
```

### 19. Notification System (Low Priority)
**Changes needed:**
- Add notification rules to config (keywords, sources)
- Integrate with system notifications (notify-send, toast)
- Optional: email or webhook notifications
```python
if matches_notification_rule(entry):
    send_notification(entry['title'], entry['url'])
```