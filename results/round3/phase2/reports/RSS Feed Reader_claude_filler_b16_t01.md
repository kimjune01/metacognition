# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS/Atom feeds using the `feedparser` library
2. **Multi-source Aggregation**: Combines entries from multiple feed sources within categories
3. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
4. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
5. **Smart Date Formatting**: Displays "HH:MM" for today's entries, "Mon DD, HH:MM" for older entries
6. **Persistent Storage**: Saves parsed feeds as JSON files in `~/.rreader/` directory
7. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration
8. **Selective Updates**: Can update a specific category or all categories
9. **Timestamp Tracking**: Records when each feed was last updated
10. **Author Display**: Configurable per-category option to show feed authors vs source names

## Triage

### Critical Gaps (Production Blockers)

1. **No Error Recovery**: Silent failures leave stale data; users get no feedback about what broke
2. **No Feed Validation**: Malformed feeds crash the system; no schema validation for feeds.json
3. **No Caching Strategy**: Re-fetches everything on every run, wasting bandwidth and risking rate limits
4. **No Concurrency**: Sequential processing is extremely slow for many feeds
5. **No User Interface**: Terminal output only during updates; no way to read the fetched feeds

### High Priority (User Experience Issues)

6. **No Subscription Management**: Users must manually edit JSON to add/remove feeds
7. **No Update Scheduling**: Requires external cron/task scheduler setup
8. **No Read State Tracking**: Can't mark items as read or track what's been seen
9. **Limited Logging**: Only optional console output; no persistent logs for debugging
10. **No Content Extraction**: Only stores title/link; full article text not preserved

### Medium Priority (Quality of Life)

11. **No Feed Health Monitoring**: No tracking of which feeds consistently fail or go stale
12. **No Entry Filtering**: Can't filter by keywords, date range, or other criteria
13. **No Export Capability**: Data locked in proprietary JSON format
14. **Hardcoded Timezone**: Timezone setting requires code modification
15. **No Duplicate Detection Across Categories**: Same article in multiple feeds appears multiple times

### Low Priority (Nice to Have)

16. **No Feed Discovery**: Can't auto-detect RSS feeds from website URLs
17. **No OPML Import/Export**: Can't migrate from/to other RSS readers
18. **No Summary Generation**: Stores full titles but no excerpt/description
19. **No Media Handling**: Doesn't process enclosures (podcasts, images)
20. **No Analytics**: No statistics on reading habits or feed activity

## Plan

### 1. Error Recovery (Critical)

**Changes needed:**
- Wrap `feedparser.parse()` in try-except with specific exception types (URLError, HTTPError, timeout)
- Add per-feed timeout parameter (default 30s): `feedparser.parse(url, timeout=30)`
- Log failures to `~/.rreader/errors.log` with timestamp, URL, and exception details
- On failure, preserve previous feed data instead of leaving empty/corrupted JSON
- Add retry logic with exponential backoff: 3 attempts with 1s, 2s, 4s delays
- Return status dict: `{"success": bool, "error": str, "fetched_count": int}`

**Implementation:**
```python
def fetch_feed_safe(url, timeout=30, retries=3):
    for attempt in range(retries):
        try:
            return feedparser.parse(url, timeout=timeout), None
        except (URLError, HTTPError, TimeoutError) as e:
            if attempt == retries - 1:
                return None, str(e)
            time.sleep(2 ** attempt)
    return None, "Max retries exceeded"
```

### 2. Feed Validation (Critical)

**Changes needed:**
- Define JSON schema for feeds.json using `jsonschema` library
- Validate structure on load: categories must be dicts, feeds must be dict[str, str], show_author must be bool
- Validate URLs using `urllib.parse.urlparse()` - must have scheme and netloc
- Check feedparser response status: warn if `d.bozo == 1` (malformed feed)
- Validate required fields exist in entries before accessing: `published_parsed`, `link`, `title`
- Add `feeds_schema.json` file defining expected structure

**Implementation:**
```python
FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {"type": "object", "patternProperties": {".*": {"type": "string", "format": "uri"}}},
                "show_author": {"type": "boolean"}
            }
        }
    }
}

def validate_feeds_config(config):
    jsonschema.validate(instance=config, schema=FEEDS_SCHEMA)
    for category, data in config.items():
        for name, url in data["feeds"].items():
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid URL for {name}: {url}")
```

### 3. Caching Strategy (Critical)

**Changes needed:**
- Check `created_at` timestamp in existing JSON before fetching
- Add configurable TTL per category (default 1 hour): `"cache_ttl": 3600`
- Skip fetch if `time.time() - existing["created_at"] < TTL`
- Implement HTTP conditional requests using `If-Modified-Since` and `ETag` headers
- Store etags/last-modified in separate `cache_metadata.json`
- Add `--force` flag to bypass cache

**Implementation:**
```python
def should_update(category, ttl=3600):
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(cache_file):
        return True
    with open(cache_file) as f:
        data = json.load(f)
    return time.time() - data.get("created_at", 0) > ttl

def fetch_with_conditional(url, etag=None, modified=None):
    headers = {}
    if etag:
        headers["If-None-Match"] = etag
    if modified:
        headers["If-Modified-Since"] = modified
    # Use requests library with headers support
    return feedparser.parse(url, request_headers=headers)
```

### 4. Concurrency (Critical)

**Changes needed:**
- Replace sequential loop with `concurrent.futures.ThreadPoolExecutor`
- Set max workers to 10 (configurable): `ThreadPoolExecutor(max_workers=10)`
- Pass each (source, url) pair to worker threads
- Collect results and merge into category dict
- Add progress indicator: `tqdm` library or simple counter
- Ensure thread-safe file writing with locks

**Implementation:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_source(source, url):
    try:
        d = feedparser.parse(url, timeout=30)
        return source, d, None
    except Exception as e:
        return source, None, str(e)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_single_source, src, url): src 
                   for src, url in urls.items()}
        
        for future in as_completed(futures):
            source, d, error = future.result()
            if error:
                if log:
                    sys.stderr.write(f"Failed {source}: {error}\n")
                continue
            # Process d.entries as before
```

### 5. User Interface (Critical)

**Changes needed:**
- Create `reader.py` with TUI using `curses` or `rich` library
- Display feed list with unread counts
- Arrow key navigation between categories and entries
- Enter key to open URLs in browser using `webbrowser.open()`
- Keyboard shortcuts: 'r' refresh, 'q' quit, 'm' mark read, 'a' mark all read
- Show entry details: title, source, date, summary in preview pane
- Persist UI state (selected category, scroll position) to JSON

**Implementation:**
```python
from rich.console import Console
from rich.table import Table
from rich.live import Live

def display_feeds(category):
    console = Console()
    with open(os.path.join(p["path_data"], f"rss_{category}.json")) as f:
        data = json.load(f)
    
    table = Table(title=f"{category.title()} Feeds")
    table.add_column("Time", style="cyan")
    table.add_column("Source", style="magenta")
    table.add_column("Title")
    
    for entry in data["entries"]:
        table.add_row(entry["pubDate"], entry["sourceName"], entry["title"])
    
    console.print(table)
```

### 6. Subscription Management (High Priority)

**Changes needed:**
- Add `manage.py` with commands: `add`, `remove`, `list`, `edit`
- `add` command: `python -m rreader.manage add <category> <name> <url>`
- Validate URL is actually a feed before adding
- Interactive mode with prompts if no arguments provided
- Pretty-print feeds.json with proper indentation on save
- Backup feeds.json before modifications to `feeds.json.bak`

**Implementation:**
```python
def add_feed(category, name, url):
    # Validate feed
    d = feedparser.parse(url)
    if not d.entries:
        raise ValueError(f"No entries found at {url}")
    
    with open(FEEDS_FILE_NAME) as f:
        feeds = json.load(f)
    
    if category not in feeds:
        feeds[category] = {"feeds": {}, "show_author": False}
    
    feeds[category]["feeds"][name] = url
    
    # Backup
    shutil.copy(FEEDS_FILE_NAME, FEEDS_FILE_NAME + ".bak")
    
    with open(FEEDS_FILE_NAME, "w") as f:
        json.dump(feeds, f, indent=4, ensure_ascii=False)
```

### 7. Update Scheduling (High Priority)

**Changes needed:**
- Add `scheduler.py` using `schedule` library or `APScheduler`
- Run as daemon process with `python -m rreader.scheduler start`
- Read update intervals from feeds.json: `"update_interval": "1h"`
- Parse intervals: support "30m", "1h", "6h", "1d" formats
- PID file in `~/.rreader/scheduler.pid` to prevent multiple instances
- Log updates to `~/.rreader/scheduler.log`
- Stop command: `python -m rreader.scheduler stop`

**Implementation:**
```python
import schedule
import daemon

def schedule_updates():
    with open(FEEDS_FILE_NAME) as f:
        feeds = json.load(f)
    
    for category, config in feeds.items():
        interval = config.get("update_interval", "1h")
        minutes = parse_interval(interval)
        schedule.every(minutes).minutes.do(do, category)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def parse_interval(s):
    # "30m" -> 30, "1h" -> 60, "1d" -> 1440
    units = {"m": 1, "h": 60, "d": 1440}
    return int(s[:-1]) * units[s[-1]]
```

### 8. Read State Tracking (High Priority)

**Changes needed:**
- Create `read_state.json` mapping entry IDs to read timestamps
- Structure: `{category: {entry_id: unix_timestamp}}`
- Add `mark_read(category, entry_id)` and `is_read(category, entry_id)` functions
- Include read state in UI (dim read entries, bold unread)
- Add unread count to category display
- Periodically prune old read states (entries >30 days old)

**Implementation:**
```python
READ_STATE_FILE = os.path.join(p["path_data"], "read_state.json")

def mark_read(category, entry_id):
    if os.path.exists(READ_STATE_FILE):
        with open(READ_STATE_FILE) as f:
            state = json.load(f)
    else:
        state = {}
    
    if category not in state:
        state[category] = {}
    
    state[category][str(entry_id)] = int(time.time())
    
    with open(READ_STATE_FILE, "w") as f:
        json.dump(state, f)

def get_unread_count(category):
    with open(os.path.join(p["path_data"], f"rss_{category}.json")) as f:
        entries = json.load(f)["entries"]
    
    if not os.path.exists(READ_STATE_FILE):
        return len(entries)
    
    with open(READ_STATE_FILE) as f:
        state = json.load(f)
    
    read_ids = set(state.get(category, {}).keys())
    return sum(1 for e in entries if str(e["id"]) not in read_ids)
```

### 9. Logging (High Priority)

**Changes needed:**
- Replace print statements with `logging` module
- Configure rotating file handler: max 10MB, 5 backup files
- Log levels: DEBUG for feed parsing details, INFO for updates, WARNING for retries, ERROR for failures
- Separate log files: `fetcher.log`, `scheduler.log`, `ui.log`
- Add `--verbose` and `--quiet` flags to control console output
- Include structured logging with JSON format option for parsing

**Implementation:**
```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(name, log_file, level=logging.INFO):
    handler = RotatingFileHandler(
        os.path.join(p["path_data"], log_file),
        maxBytes=10*1024*1024,
        backupCount=5
    )
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.addHandler(handler)
    
    return logger

# Usage
logger = setup_logging("rreader.fetcher", "fetcher.log")
logger.info(f"Fetching {len(urls)} feeds for {category}")
```

### 10. Content Extraction (High Priority)

**Changes needed:**
- Store `summary` field from feedparser entries
- Add `content` field extraction from `entry.content[0].value`
- Strip HTML tags for plain text version using `html2text` or `BeautifulSoup`
- Store both HTML and plain text versions
- Add character limit (default 500 chars) for summaries in UI
- Download and cache full article text using `newspaper3k` or `readability-lxml`

**Implementation:**
```python
from bs4 import BeautifulSoup

def extract_content(entry):
    summary = getattr(entry, "summary", "")
    content_html = ""
    
    if hasattr(entry, "content"):
        content_html = entry.content[0].value
    elif summary:
        content_html = summary
    
    # Plain text version
    soup = BeautifulSoup(content_html, "html.parser")
    content_text = soup.get_text(separator=" ", strip=True)
    
    return {
        "summary": content_text[:500],
        "content_html": content_html,
        "content_text": content_text
    }

# Add to entries dict
entries.update(extract_content(feed))
```

### Remaining Gaps (11-20)

For medium and low priority items, the implementation approach follows similar patterns:

- **Feed Health Monitoring**: Track success/fail rates in `feed_health.json`, display warnings for consistently failing feeds
- **Entry Filtering**: Add filter syntax to feeds.json: `"filters": {"exclude": ["regex"], "include": ["regex"]}`
- **Export**: Add `export` command supporting JSON, CSV, Markdown formats
- **Configurable Timezone**: Move TIMEZONE to feeds.json or separate config.json
- **Cross-category Deduplication**: Hash URLs and track in global set
- **Feed Discovery**: Use `feedfinder2` library to auto-detect feeds from homepage URLs
- **OPML Support**: Use `listparser` library for import, generate XML for export
- **Description Storage**: Add `entry.description` to stored fields
- **Media Handling**: Store `entry.enclosures` list with URL, type, length
- **Analytics**: Track read/unread rates, popular sources, reading times in `analytics.json`

Each of these follows the established pattern: add JSON storage, implement helper functions, integrate into UI where applicable.