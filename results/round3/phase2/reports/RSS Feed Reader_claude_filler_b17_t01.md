# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed reader with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS/Atom feeds using the `feedparser` library
2. **Multi-source Aggregation**: Handles multiple feed sources organized by category
3. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
5. **Persistence**: Stores parsed feeds as JSON files in `~/.rreader/` directory
6. **Configuration Management**: Maintains a `feeds.json` configuration file with automatic initialization from bundled defaults
7. **Incremental Updates**: Can refresh specific categories or all feeds
8. **Display Formatting**: Provides human-readable timestamps ("HH:MM" for today, "Mon DD, HH:MM" for older entries)
9. **Author Attribution**: Supports configurable author display (source name vs. actual author)
10. **Sorted Output**: Entries are sorted by timestamp in reverse chronological order

## Triage

### Critical Gaps (P0)
1. **No Error Recovery**: Single feed failure causes entire operation to exit with `sys.exit(0)`
2. **No Rate Limiting**: Could hammer servers with rapid successive requests
3. **No Caching Strategy**: Re-fetches all feeds even if recently updated
4. **Silent Failures**: The try/except around feed parsing swallows all errors without logging

### High Priority Gaps (P1)
5. **No HTTP Timeout**: Requests can hang indefinitely on unresponsive servers
6. **No User-Agent Header**: Many servers block or throttle requests without proper identification
7. **No Concurrent Fetching**: Sequential processing makes multi-feed updates slow
8. **Missing Feed Metadata**: No storage of feed-level info (title, description, last-modified headers)
9. **No Entry Content Storage**: Only stores title/link, not description or full content
10. **Hardcoded Paths**: Directory structure and timezone not configurable via environment/CLI

### Medium Priority Gaps (P2)
11. **No Feed Validation**: No check for malformed URLs or invalid feed formats before fetching
12. **No Stale Data Detection**: Old cached files remain valid indefinitely
13. **No Read/Unread Tracking**: No mechanism to mark entries as read
14. **No Entry Limits**: Unlimited entries per feed could cause memory/storage issues
15. **No Logging Framework**: Uses ad-hoc print statements instead of structured logging
16. **Missing CLI Interface**: No argument parsing for common operations (refresh, add feed, list)
17. **No Feed Health Monitoring**: No tracking of fetch failures or feed availability

### Low Priority Gaps (P3)
18. **No OPML Import/Export**: Standard feed subscription format not supported
19. **No Search Functionality**: No way to search across entries
20. **No Notification System**: No alerts for new entries
21. **No Statistics**: No tracking of feed update frequency or entry counts
22. **Limited Timestamp Parsing**: Only handles `published_parsed` and `updated_parsed`

## Plan

### P0 Fixes

**1. Error Recovery**
```python
# Change from:
try:
    d = feedparser.parse(url)
    if log:
        sys.stdout.write(" - Done\n")
except:
    sys.exit(" - Failed\n" if log else 0)

# To:
try:
    d = feedparser.parse(url)
    if log:
        sys.stdout.write(" - Done\n")
except Exception as e:
    if log:
        sys.stderr.write(f" - Failed: {e}\n")
    continue  # Skip this feed and continue with others
```

**2. Rate Limiting**
```python
# Add at module level:
import time
from threading import Lock

_last_request_time = {}
_request_lock = Lock()
MIN_REQUEST_INTERVAL = 1.0  # seconds

# In get_feed_from_rss, before feedparser.parse:
with _request_lock:
    now = time.time()
    last = _last_request_time.get(url, 0)
    wait = MIN_REQUEST_INTERVAL - (now - last)
    if wait > 0:
        time.sleep(wait)
    _last_request_time[url] = time.time()
```

**3. Caching Strategy**
```python
# Add cache check before fetching:
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(cache_file):
    age = time.time() - os.path.getmtime(cache_file)
    if age < 300:  # 5 minutes
        with open(cache_file, 'r') as f:
            return json.load(f)
```

**4. Structured Error Logging**
```python
# Replace ad-hoc logging:
import logging

logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# In exception handlers:
except Exception as e:
    logging.error(f"Failed to parse feed {url}: {e}", exc_info=True)
```

### P1 Fixes

**5. HTTP Timeout**
```python
# feedparser doesn't expose timeout directly, use requests:
import requests
from io import BytesIO

response = requests.get(url, timeout=30, headers={'User-Agent': USER_AGENT})
d = feedparser.parse(BytesIO(response.content))
```

**6. User-Agent Header**
```python
# Add constant:
USER_AGENT = "RReader/1.0 (RSS Reader; +https://github.com/yourrepo)"

# In requests.get call:
headers = {
    'User-Agent': USER_AGENT,
    'Accept': 'application/rss+xml, application/atom+xml, application/xml'
}
```

**7. Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # Extract feed fetching logic here
    pass

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, src, url): src 
               for src, url in urls.items()}
    for future in as_completed(futures):
        source = futures[future]
        try:
            result = future.result()
            rslt.update(result)
        except Exception as e:
            logging.error(f"Failed to fetch {source}: {e}")
```

**8. Feed Metadata Storage**
```python
# Add to JSON structure:
rslt = {
    "entries": rslt,
    "created_at": int(time.time()),
    "feed_info": {
        source: {
            "title": d.feed.get('title', ''),
            "description": d.feed.get('description', ''),
            "link": d.feed.get('link', ''),
            "last_modified": d.get('modified', ''),
            "etag": d.get('etag', '')
        }
        for source, d in feed_data.items()
    }
}
```

**9. Entry Content Storage**
```python
# In entries dict:
entries = {
    "id": ts,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', '')[:500],  # truncate
    "content": getattr(feed, 'content', [{}])[0].get('value', '')[:2000]
}
```

**10. Configurable Settings**
```python
# Create config.py with environment variable support:
import os

TIMEZONE = datetime.timezone(
    datetime.timedelta(hours=int(os.getenv('RREADER_TZ_OFFSET', '9')))
)

DATA_PATH = os.getenv('RREADER_DATA_PATH', 
                      os.path.join(Path.home(), '.rreader'))

CACHE_TTL = int(os.getenv('RREADER_CACHE_TTL', '300'))
```

### P2 Fixes

**11. Feed Validation**
```python
from urllib.parse import urlparse

def validate_feed_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except:
        return False

# Before fetching:
if not validate_feed_url(url):
    logging.warning(f"Invalid URL: {url}")
    continue
```

**12. Stale Data Detection**
```python
# In rslt structure:
"expires_at": int(time.time()) + CACHE_TTL,

# When loading:
if data.get('expires_at', 0) < time.time():
    # Refetch
```

**13. Read/Unread Tracking**
```python
# Create separate tracking file:
READ_STATE_FILE = os.path.join(p["path_data"], "read_state.json")

def mark_as_read(entry_id):
    state = load_read_state()
    state['read'].add(entry_id)
    save_read_state(state)

# Add 'read' flag to entries when loading
```

**14. Entry Limits**
```python
MAX_ENTRIES_PER_FEED = 100

# After sorting:
rslt = [val for key, val in sorted(rslt.items(), reverse=True)][:MAX_ENTRIES_PER_FEED]
```

**15. Logging Framework**
```python
# Replace all sys.stdout.write and print:
logger = logging.getLogger(__name__)
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse: {e}")
```

**16. CLI Interface**
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('--category', help='Refresh specific category')
    parser.add_argument('--add-feed', nargs=2, metavar=('CATEGORY', 'URL'))
    parser.add_argument('--list', action='store_true', help='List categories')
    parser.add_argument('--verbose', '-v', action='store_true')
    
    args = parser.parse_args()
    
    if args.list:
        list_categories()
    elif args.add_feed:
        add_feed(args.add_feed[0], args.add_feed[1])
    else:
        do(args.category, log=args.verbose)
```

**17. Feed Health Monitoring**
```python
# Track fetch attempts:
HEALTH_FILE = os.path.join(p["path_data"], "feed_health.json")

def record_fetch(url, success, error=None):
    health = load_health()
    health[url]['last_attempt'] = time.time()
    health[url]['success'] = success
    if not success:
        health[url]['consecutive_failures'] = health[url].get('consecutive_failures', 0) + 1
        health[url]['last_error'] = str(error)
    else:
        health[url]['consecutive_failures'] = 0
    save_health(health)
```

### P3 Fixes

**18. OPML Support**
```python
import xml.etree.ElementTree as ET

def export_opml(filename):
    root = ET.Element('opml', version='2.0')
    body = ET.SubElement(root, 'body')
    
    with open(FEEDS_FILE_NAME, 'r') as f:
        feeds = json.load(f)
    
    for category, data in feeds.items():
        outline = ET.SubElement(body, 'outline', text=category)
        for name, url in data['feeds'].items():
            ET.SubElement(outline, 'outline', type='rss', text=name, xmlUrl=url)
    
    tree = ET.ElementTree(root)
    tree.write(filename)
```

**19-21. Additional Features**
These would require more extensive architectural changes including:
- Search: Add indexing with SQLite FTS or Whoosh
- Notifications: Integrate with desktop notification systems (notify-send, Windows toast)
- Statistics: Add database layer for historical tracking