# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **RSS Feed Parsing**: Downloads and parses RSS/Atom feeds using the `feedparser` library
2. **Multi-source Aggregation**: Supports multiple feed sources organized by categories
3. **Timestamp Normalization**: Converts feed publication times to a configurable timezone (currently KST/UTC+9)
4. **Deduplication**: Uses timestamps as unique IDs to prevent duplicate entries within a category
5. **Data Persistence**: Saves parsed feeds as JSON files in `~/.rreader/` directory
6. **Configuration Management**: 
   - Reads feed URLs from `feeds.json`
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled config into user config
7. **Flexible Date Display**: Shows time-only for today's items, full date for older items
8. **Author Attribution**: Configurable per-category author display (source name vs. feed author)
9. **Selective Updates**: Can refresh a single category or all categories
10. **Basic Logging**: Optional stdout logging of download progress

## Triage

### Critical (P0)
1. **No Error Handling**: Bare `except` clauses silently swallow all errors
2. **No Network Resilience**: No timeout, retry logic, or connection pooling
3. **No Duplicate ID Handling**: Timestamp collisions overwrite entries silently

### High Priority (P1)
4. **No Feed Validation**: Malformed feeds crash or produce corrupted data
5. **No Rate Limiting**: Could hammer feed servers or get rate-limited/banned
6. **No Stale Data Management**: Old feed data accumulates indefinitely
7. **No Incremental Updates**: Always fetches entire feeds, even if unchanged
8. **No Concurrency**: Fetches feeds serially, blocking on slow servers

### Medium Priority (P2)
9. **Poor Logging Infrastructure**: Mix of stdout prints and silent failures
10. **No Configuration Validation**: Invalid `feeds.json` causes crashes
11. **No User Feedback**: Long operations provide no progress indication (except optional log)
12. **Hardcoded Paths**: Limited flexibility for alternative deployments
13. **No Entry Content Storage**: Only saves title/link/metadata, not article content/summary

### Low Priority (P3)
14. **No Feed Discovery**: Cannot auto-detect RSS feeds from website URLs
15. **No OPML Import/Export**: Cannot bulk import/export feed subscriptions
16. **No Read/Unread Tracking**: Cannot mark items as read
17. **No Search Capability**: Cannot search across feed entries
18. **No Feed Metadata**: Doesn't store feed-level info (description, icon, etc.)

## Plan

### P0 Fixes

**1. Error Handling**
```python
# Replace bare excepts with specific exceptions and logging
try:
    d = feedparser.parse(url)
except (urllib.error.URLError, http.client.HTTPException) as e:
    logger.error(f"Network error fetching {url}: {e}")
    return {}
except feedparser.FeedParserError as e:
    logger.error(f"Parse error for {url}: {e}")
    return {}
```
- Import `logging` module and configure logger with file handler in `~/.rreader/logs/`
- Catch specific exceptions: network errors, parse errors, file I/O errors
- Add error counts to JSON output: `{"entries": [...], "errors": 3, "last_error": "..."}`

**2. Network Resilience**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# In get_feed_from_rss():
session = create_session()
response = session.get(url, timeout=30)
d = feedparser.parse(response.content)
```
- Add `requests` dependency for better control
- Configure 30-second timeout
- Implement exponential backoff retry (3 attempts)
- Add User-Agent header: `Mozilla/5.0 (compatible; RReader/1.0)`

**3. Duplicate ID Handling**
```python
# Change ID generation to include source and use hash for collisions
import hashlib

entry_key = f"{ts}_{source}_{feed.link}"
entry_id = hashlib.md5(entry_key.encode()).hexdigest()[:16]

entries = {
    "id": entry_id,
    "timestamp": ts,
    # ... rest of fields
}
```
- Use composite key (timestamp + source + URL) 
- Generate stable hash-based IDs
- Add collision detection: track if multiple entries map to same timestamp

### P1 Fixes

**4. Feed Validation**
```python
def validate_feed(parsed_feed):
    if parsed_feed.bozo:  # feedparser's error flag
        logger.warning(f"Malformed feed: {parsed_feed.bozo_exception}")
    
    if not hasattr(parsed_feed, 'entries') or len(parsed_feed.entries) == 0:
        raise ValueError("Feed has no entries")
    
    return True
```
- Check `feedparser.bozo` flag for well-formedness
- Validate required fields exist before accessing
- Set maximum entries per feed (e.g., 100) to prevent memory issues

**5. Rate Limiting**
```python
import time
from collections import defaultdict

last_fetch = defaultdict(float)
MIN_FETCH_INTERVAL = 300  # 5 minutes

def get_feed_from_rss(category, urls, ...):
    for source, url in urls.items():
        # Respect minimum fetch interval
        time_since_last = time.time() - last_fetch[url]
        if time_since_last < MIN_FETCH_INTERVAL:
            logger.info(f"Skipping {url}, fetched {time_since_last}s ago")
            continue
        
        time.sleep(1)  # 1 second between requests
        # ... fetch feed
        last_fetch[url] = time.time()
```
- Store last-fetch timestamps in `~/.rreader/fetch_log.json`
- Enforce minimum 5-minute interval per feed
- Add 1-second delay between consecutive requests
- Check feed's TTL/cache headers if present

**6. Stale Data Management**
```python
MAX_ENTRY_AGE_DAYS = 30

def cleanup_old_entries(entries):
    cutoff = time.time() - (MAX_ENTRY_AGE_DAYS * 86400)
    return [e for e in entries if e['timestamp'] > cutoff]

# In get_feed_from_rss(), before writing:
rslt["entries"] = cleanup_old_entries(rslt["entries"])
```
- Add configurable retention period to `feeds.json` (default 30 days)
- Prune entries older than retention period before saving
- Add `--cleanup` CLI flag to manually trigger deep cleanup

**7. Incremental Updates**
```python
def load_existing_entries(category):
    path = os.path.join(p["path_data"], f"rss_{category}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {"entries": [], "created_at": 0}

def get_feed_from_rss(category, urls, ...):
    existing = load_existing_entries(category)
    existing_ids = {e['id'] for e in existing['entries']}
    
    rslt = {}
    for entry in new_entries:
        if entry['id'] not in existing_ids:
            rslt[entry['id']] = entry
    
    # Merge with existing
    all_entries = existing['entries'] + list(rslt.values())
```
- Load existing entries before fetching
- Only add genuinely new entries
- Support HTTP ETags and Last-Modified headers to skip unchanged feeds

**8. Concurrency**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, show_author):
    # Move single-feed logic here
    pass

def get_feed_from_rss(category, urls, show_author=False, log=False):
    results = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(fetch_single_feed, src, url, show_author): (src, url)
            for src, url in urls.items()
        }
        
        for future in as_completed(future_to_url):
            src, url = future_to_url[future]
            try:
                entries = future.result(timeout=60)
                results.update(entries)
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
```
- Use `ThreadPoolExecutor` with 5 workers (configurable)
- Set per-feed timeout of 60 seconds
- Collect results as they complete for faster perceived performance

### P2 Fixes

**9. Logging Infrastructure**
```python
import logging

def setup_logging():
    log_dir = os.path.join(p["path_data"], "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "rreader.log")),
            logging.StreamHandler() if log else logging.NullHandler()
        ]
    )
    return logging.getLogger(__name__)
```
- Replace all `sys.stdout.write()` with `logger.info()`
- Add log rotation (keep last 7 days, max 10MB per file)
- Include request IDs for tracing multi-feed operations

**10. Configuration Validation**
```python
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {".*": {"type": "string", "format": "uri"}}
                },
                "show_author": {"type": "boolean"}
            }
        }
    }
}

def load_feeds():
    with open(FEEDS_FILE_NAME) as f:
        feeds = json.load(f)
    jsonschema.validate(feeds, FEEDS_SCHEMA)
    return feeds
```
- Define JSON schema for `feeds.json`
- Validate on load, provide helpful error messages
- Add `--validate-config` command to check configuration

**11. User Feedback**
```python
from tqdm import tqdm

def do(target_category=None, log=False):
    categories = [target_category] if target_category else RSS.keys()
    
    with tqdm(total=len(categories), desc="Updating feeds") as pbar:
        for category in categories:
            pbar.set_description(f"Updating {category}")
            get_feed_from_rss(...)
            pbar.update(1)
```
- Add `tqdm` dependency for progress bars
- Show "Updating feeds: 3/10" style progress
- Display per-feed progress when fetching multiple sources

**12. Configuration System**
```python
# In config.py
import os

class Config:
    DATA_PATH = os.getenv('RREADER_DATA_PATH', str(Path.home()) + "/.rreader/")
    TIMEZONE_OFFSET = int(os.getenv('RREADER_TZ_OFFSET', '9'))
    MAX_WORKERS = int(os.getenv('RREADER_MAX_WORKERS', '5'))
    FETCH_TIMEOUT = int(os.getenv('RREADER_TIMEOUT', '30'))
```
- Support environment variables for configuration
- Add `--config` CLI flag to specify alternative config file
- Document all configuration options in README

**13. Entry Content Storage**
```python
entries = {
    "id": entry_id,
    "title": feed.title,
    "summary": getattr(feed, 'summary', '')[:500],  # Truncate
    "content": getattr(feed, 'content', [{}])[0].get('value', '')[:2000],
    "author": author,
    # ... existing fields
}
```
- Add `summary` field (truncated to 500 chars)
- Add optional `content` field (truncated to 2000 chars)
- Make content storage configurable per-category: `"store_content": true`

### P3 Fixes

**14. Feed Discovery**
```python
import requests
from bs4 import BeautifulSoup

def discover_feeds(url):
    response = requests.get(url, timeout=10)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    feeds = []
    for link in soup.find_all('link', type=['application/rss+xml', 'application/atom+xml']):
        feeds.append({
            'url': link.get('href'),
            'title': link.get('title', 'Untitled Feed')
        })
    return feeds
```
- Add `--discover URL` CLI command
- Parse HTML for `<link>` tags with RSS/Atom MIME types
- Try common paths: `/feed`, `/rss`, `/atom.xml`

**15. OPML Support**
```python
import xml.etree.ElementTree as ET

def import_opml(filepath):
    tree = ET.parse(filepath)
    feeds = {}
    for outline in tree.findall('.//outline[@type="rss"]'):
        category = outline.get('category', 'Imported')
        if category not in feeds:
            feeds[category] = {'feeds': {}}
        feeds[category]['feeds'][outline.get('title')] = outline.get('xmlUrl')
    return feeds

def export_opml(feeds, filepath):
    # Generate OPML XML from feeds dict
    pass
```
- Add `--import-opml FILE` command
- Add `--export-opml FILE` command
- Support OPML 2.0 format

**16. Read/Unread Tracking**
```python
# Add read_status.json file
{
    "read_entries": ["entry_id_1", "entry_id_2", ...],
    "last_read_timestamp": 1234567890
}

# In entry dict:
entries = {
    # ... existing fields
    "read": entry_id in read_status['read_entries']
}
```
- Store read entry IDs in separate file
- Add `mark_as_read(entry_id)` function
- Auto-mark entries older than 7 days as read

**17. Search Capability**
```python
def search_entries(query, categories=None):
    results = []
    for category_file in glob.glob(os.path.join(p["path_data"], "rss_*.json")):
        with open(category_file) as f:
            data = json.load(f)
        for entry in data['entries']:
            if query.lower() in entry['title'].lower():
                results.append(entry)
    return sorted(results, key=lambda x: x['timestamp'], reverse=True)
```
- Add `--search QUERY` CLI command
- Search across title and summary fields
- Support regex patterns with `--regex` flag

**18. Feed Metadata**
```python
# Enhance category JSON structure:
{
    "entries": [...],
    "feed_info": {
        "title": "Example Feed",
        "description": "Feed description",
        "link": "https://example.com",
        "icon": "https://example.com/icon.png",
        "last_build_date": "2024-01-01T00:00:00Z"
    },
    "created_at": 1234567890
}
```
- Extract and store feed-level metadata from parsed feed
- Download and cache feed icons
- Display feed info in UI/CLI output