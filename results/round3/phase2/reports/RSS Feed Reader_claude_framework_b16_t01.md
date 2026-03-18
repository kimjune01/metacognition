# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-category support**: Organizes feeds into categories (e.g., "tech", "news") via a JSON configuration file
3. **Timestamp normalization**: Converts feed publication dates to a configurable timezone (currently KST/UTC+9)
4. **Deduplication by timestamp**: Uses publication timestamp as entry ID to prevent duplicates within a single fetch
5. **Sorted output**: Returns entries in reverse chronological order (newest first)
6. **Persistent storage**: Writes aggregated feeds to JSON files in `~/.rreader/` directory
7. **Configuration management**: 
   - Bundles default feeds in the package
   - Copies bundled config on first run
   - Merges new categories from package updates into user config
8. **Flexible date display**: Shows time-only for today's entries, full date for older ones
9. **Author handling**: Optional per-category author display from feed metadata
10. **Selective refresh**: Can update a single category or all categories

The code runs as both a library (`do()` function) and CLI script.

---

## Triage

### Critical gaps (blocks production use):

1. **No error recovery** - Any feed failure crashes the entire category refresh
2. **No staleness detection** - System never knows if cached data is too old
3. **No rate limiting** - Will hammer feed servers if called repeatedly
4. **No feed validation** - Malformed URLs or configs cause silent failures
5. **No concurrent fetching** - Sequential fetches make refresh slow for many feeds

### High-priority gaps (degrades user experience):

6. **No entry deduplication across fetches** - Same article appears multiple times if fetched twice
7. **No HTTP caching** - Ignores ETags/Last-Modified, wastes bandwidth
8. **No timeout handling** - Hangs indefinitely on slow/dead feeds
9. **No feed health tracking** - Can't detect persistently failing feeds
10. **Logging is optional and incomplete** - Hard to debug issues

### Medium-priority gaps (limits functionality):

11. **No entry content storage** - Only stores title/link, can't show previews
12. **No read/unread tracking** - Can't mark entries as consumed
13. **No search/filtering** - Can't find old entries
14. **No feed autodiscovery** - Must manually find RSS URLs
15. **No OPML import/export** - Can't migrate feed lists

### Low-priority gaps (nice-to-have):

16. **No entry age pruning** - Old entries accumulate forever
17. **No feed metadata** (favicon, description) - UI has limited info
18. **No custom entry grouping** - Stuck with source-based organization
19. **No webhook/notification support** - Can't alert on new entries

---

## Plan

### 1. Error recovery (Critical)
**Problem**: `feedparser.parse()` and file writes can fail, crashing the entire refresh.

**Changes needed**:
```python
# In get_feed_from_rss():
for source, url in urls.items():
    try:
        # ... existing parse code ...
    except Exception as e:
        if log:
            sys.stderr.write(f"ERROR fetching {url}: {e}\n")
        continue  # Skip to next feed
```

Add exception handling around:
- Each feed fetch (network failures)
- Each entry parse (malformed data)
- JSON file writes (disk full, permissions)

Return a status dict: `{"success": int, "failed": int, "errors": [...]}` instead of just the entries.

### 2. Staleness detection (Critical)
**Problem**: No way to know if `rss_{category}.json` is fresh enough to skip refetch.

**Changes needed**:
```python
# Add to do() function:
CACHE_TTL_SECONDS = 600  # 10 minutes

def should_refresh(category):
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(cache_file):
        return True
    
    with open(cache_file, 'r') as f:
        data = json.load(f)
    
    age = time.time() - data.get("created_at", 0)
    return age > CACHE_TTL_SECONDS

# In do():
if not should_refresh(target_category):
    # Return cached data
```

Add `--force` CLI flag to override staleness check.

### 3. Rate limiting (Critical)
**Problem**: No protection against hammering feed servers or hitting API limits.

**Changes needed**:
```python
import time
from collections import defaultdict

# Module-level state:
_last_fetch = defaultdict(float)
MIN_FETCH_INTERVAL = 60  # seconds per feed

def get_feed_from_rss(...):
    for source, url in urls.items():
        # Rate limit per-feed:
        elapsed = time.time() - _last_fetch[url]
        if elapsed < MIN_FETCH_INTERVAL:
            time.sleep(MIN_FETCH_INTERVAL - elapsed)
        
        _last_fetch[url] = time.time()
        # ... fetch feed ...
```

Alternatively, use a library like `ratelimit` or implement token bucket.

### 4. Feed validation (Critical)
**Problem**: Invalid configs silently fail or cause confusing errors.

**Changes needed**:
```python
import re
from urllib.parse import urlparse

def validate_feeds_config(config):
    errors = []
    
    for category, data in config.items():
        if not isinstance(data.get("feeds"), dict):
            errors.append(f"{category}: 'feeds' must be a dict")
            continue
        
        for source, url in data["feeds"].items():
            parsed = urlparse(url)
            if not parsed.scheme in ('http', 'https'):
                errors.append(f"{category}/{source}: invalid URL '{url}'")
    
    return errors

# In do(), after loading feeds.json:
errors = validate_feeds_config(RSS)
if errors:
    sys.stderr.write("Config validation failed:\n")
    for err in errors:
        sys.stderr.write(f"  - {err}\n")
    sys.exit(1)
```

### 5. Concurrent fetching (Critical)
**Problem**: Fetching 20 feeds sequentially takes 20× longer than parallel fetch.

**Changes needed**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_one_feed(source, url, log):
    """Extract feed-fetching logic into separate function."""
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
        return source, d, None
    except Exception as e:
        return source, None, str(e)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_one_feed, src, url, log): src 
            for src, url in urls.items()
        }
        
        for future in as_completed(futures):
            source, d, error = future.result()
            if error:
                if log:
                    sys.stderr.write(f"Failed {source}: {error}\n")
                continue
            
            # ... process d.entries as before ...
```

### 6. Cross-fetch deduplication (High)
**Problem**: Fetching the same feed twice creates duplicate entries.

**Changes needed**:
```python
def get_feed_from_rss(...):
    # Load existing entries:
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    existing_ids = set()
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            existing_ids = {e["id"] for e in json.load(f)["entries"]}
    
    rslt = {}
    for feed in d.entries:
        # ... parse feed ...
        ts = int(time.mktime(parsed_time))
        
        # Skip if already seen:
        if ts in existing_ids:
            continue
        
        # ... add to rslt ...
```

Or use entry GUID instead of timestamp (more reliable):
```python
entry_id = getattr(feed, 'id', None) or feed.link
entries["id"] = hash(entry_id)  # Use stable hash
```

### 7. HTTP caching (High)
**Problem**: Refetching unchanged feeds wastes bandwidth and server resources.

**Changes needed**:
```python
import requests
from email.utils import formatdate, parsedate_to_datetime

# Store ETags/Last-Modified per feed:
# Add to rss_{category}.json: "feed_metadata": {"url": {"etag": "...", "last_modified": "..."}}

def fetch_with_caching(url, cached_etag=None, cached_modified=None):
    headers = {}
    if cached_etag:
        headers["If-None-Match"] = cached_etag
    if cached_modified:
        headers["If-Modified-Since"] = cached_modified
    
    response = requests.get(url, headers=headers, timeout=30)
    
    if response.status_code == 304:  # Not Modified
        return None, cached_etag, cached_modified
    
    return (
        response.content,
        response.headers.get("ETag"),
        response.headers.get("Last-Modified")
    )
```

Replace `feedparser.parse(url)` with `feedparser.parse(content)` where `content` comes from cached fetch.

### 8. Timeout handling (High)
**Problem**: Slow feeds block indefinitely.

**Changes needed**:
```python
# If using requests (see #7):
requests.get(url, timeout=30)

# If staying with feedparser:
import socket
socket.setdefaulttimeout(30)  # Global timeout

# Or use feedparser with custom User-Agent and timeout:
d = feedparser.parse(url, request_headers={
    'User-Agent': 'rreader/1.0',
    'Timeout': '30'
})
```

### 9. Feed health tracking (High)
**Problem**: No visibility into which feeds are broken.

**Changes needed**:
```python
# Add to each category's JSON:
# "feed_health": {
#     "url": {
#         "last_success": timestamp,
#         "last_failure": timestamp,
#         "consecutive_failures": int,
#         "last_error": str
#     }
# }

def update_feed_health(category, url, success, error=None):
    health_file = os.path.join(p["path_data"], f"health_{category}.json")
    
    health = {}
    if os.path.exists(health_file):
        with open(health_file, 'r') as f:
            health = json.load(f)
    
    if url not in health:
        health[url] = {"consecutive_failures": 0}
    
    if success:
        health[url].update({
            "last_success": int(time.time()),
            "consecutive_failures": 0
        })
    else:
        health[url].update({
            "last_failure": int(time.time()),
            "consecutive_failures": health[url]["consecutive_failures"] + 1,
            "last_error": error
        })
    
    with open(health_file, 'w') as f:
        json.dump(health, f, indent=2)
```

Add CLI command to show failing feeds: `rreader health`.

### 10. Complete logging (High)
**Problem**: `log` parameter only controls some output, no structured logging.

**Changes needed**:
```python
import logging

# Setup in do():
logging.basicConfig(
    level=logging.INFO if log else logging.WARNING,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Replace print statements:
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse {url}: {e}")
logger.debug(f"Parsed {len(d.entries)} entries from {source}")
```

Add `--verbose` flag for DEBUG level, `--quiet` for ERROR only.

---

### Lower-priority items (brief):

**11. Entry content**: Store `feed.summary` or `feed.content[0].value` in entries dict.

**12. Read tracking**: Add `"read": false` to entries, persist read state in separate JSON, add `mark-read` CLI command.

**13. Search**: Add `rreader search <query>` that greps through stored entries' titles/content.

**14. Autodiscovery**: Add `rreader add <webpage_url>` that parses HTML for `<link rel="alternate" type="application/rss+xml">`.

**15. OPML**: Add `rreader export opml.xml` and `import` commands using `xml.etree.ElementTree`.

**16. Pruning**: In `get_feed_from_rss()`, filter entries older than N days before writing.

**17. Feed metadata**: Store `d.feed.title`, `d.feed.subtitle`, `d.feed.image` in category JSON.

**18. Custom grouping**: Add "tags" array to feed config, add `rreader list --tag <name>` command.

**19. Notifications**: Add webhook URL to config, POST to it when `len(new_entries) > 0`.