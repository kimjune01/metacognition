# Diagnostic Report: RSS Feed Aggregator System

## Observations

This system is a **functional RSS feed aggregator** with the following working capabilities:

1. **Feed Parsing** - Uses `feedparser` to retrieve and parse RSS/Atom feeds from configured URLs
2. **Multi-Source Aggregation** - Supports multiple feed sources organized into categories
3. **Timestamp Normalization** - Converts feed timestamps to a configured timezone (currently KST/UTC+9)
4. **Deduplication** - Uses timestamps as IDs to prevent duplicate entries from the same feed
5. **Sorting** - Orders entries by publication time (newest first)
6. **Persistent Storage** - Saves parsed feeds as JSON files per category in `~/.rreader/`
7. **Configuration Management** - Maintains a `feeds.json` config file with automatic migration from bundled defaults
8. **Time Display Formatting** - Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
9. **Optional Author Display** - Per-category toggle to show feed author vs. source name
10. **Selective Updates** - Can refresh all categories or target a single category

## Triage

### Critical Gaps (Must-have for production)

1. **No Error Recovery** - System exits on any parse failure; no retry logic or graceful degradation
2. **No HTTP Timeout Configuration** - Feeds that hang will block indefinitely
3. **No Feed Validation** - Accepts malformed URLs without validation
4. **No Stale Data Handling** - No TTL/expiry for cached feed data
5. **No Logging Infrastructure** - `log=True` just prints to stdout; no structured logging or persistence

### High-Priority Gaps (Should-have)

6. **No Concurrency** - Fetches feeds sequentially; 20 feeds = 20× slower than necessary
7. **No Rate Limiting** - Could hammer feed servers and get blocked
8. **No User Agent String** - Some servers block requests without proper UA
9. **Incomplete ID Strategy** - Timestamp-based IDs cause collisions if multiple posts published at same second
10. **No Entry Limits** - Will store unlimited entries, causing unbounded file growth
11. **Missing Content Extraction** - Only stores title/link/date; no description/summary/content

### Medium-Priority Gaps (Nice-to-have)

12. **No Read/Unread State** - No way to track which entries have been viewed
13. **No Search/Filter Capability** - Can't search across entries or filter by keyword
14. **No Update Scheduling** - Requires manual/cron triggering; no built-in scheduler
15. **No OPML Import/Export** - Standard feed reader feature for portability
16. **No Statistics** - No tracking of feed health, fetch success rates, or update frequency

### Low-Priority Gaps

17. **Hardcoded Timezone** - Should be configurable per-user
18. **No Category Management API** - Can only edit JSON manually to add/remove categories
19. **No Thumbnail/Image Extraction** - Modern feeds often include images
20. **No Web UI/API** - CLI-only system; no programmatic access layer

## Plan

### 1. Error Recovery (Critical)
**Change Required:** Wrap feed parsing in try-except blocks with per-feed granularity
```python
# Replace current sys.exit() with:
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
    except Exception as e:
        if log:
            sys.stderr.write(f" - Failed: {e}\n")
        continue  # Skip this feed, continue with others
```
**Add:** Error metadata to output JSON: `{"fetch_errors": {"source_name": "error_msg"}}`

### 2. HTTP Timeout Configuration (Critical)
**Change Required:** Add timeout parameter to feedparser calls
```python
import socket
socket.setdefaulttimeout(15)  # Set at module level
# Or pass timeout to feedparser.parse() if supported in newer versions
```
**Add:** Configurable timeout in `config.py`: `FEED_TIMEOUT = 15`

### 3. Feed Validation (Critical)
**Change Required:** Validate URLs before parsing
```python
from urllib.parse import urlparse

def validate_feed_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False
```
**Add:** Validation in `get_feed_from_rss()` before the parse loop

### 4. Stale Data Handling (Critical)
**Change Required:** Add expiry logic when reading cached files
```python
# In do() function, check age before returning cached data:
MAX_AGE = 3600  # 1 hour
if target_category:
    cache_file = os.path.join(p["path_data"], f"rss_{target_category}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            data = json.load(f)
        if time.time() - data.get('created_at', 0) < MAX_AGE:
            return data
    # Else fetch fresh data...
```

### 5. Structured Logging (Critical)
**Change Required:** Replace print statements with `logging` module
```python
import logging
logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
# Replace: sys.stdout.write(f"- {url}")
# With: logging.info(f"Fetching {url}")
```

### 6. Concurrency (High-Priority)
**Change Required:** Use `concurrent.futures` to parallelize feed fetching
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # Move inner parsing logic here
    return source, parsed_entries

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source, entries = future.result()
        rslt.update(entries)
```

### 7. Rate Limiting (High-Priority)
**Change Required:** Add delay between requests
```python
import time
RATE_LIMIT_DELAY = 0.5  # 500ms between requests

# In ThreadPoolExecutor approach, use a semaphore:
from threading import Semaphore
rate_limiter = Semaphore(2)  # Max 2 concurrent requests

def fetch_with_rate_limit(source, url):
    with rate_limiter:
        result = fetch_single_feed(source, url)
        time.sleep(RATE_LIMIT_DELAY)
        return result
```

### 8. User Agent String (High-Priority)
**Change Required:** Configure feedparser with custom UA
```python
# At module level:
feedparser.USER_AGENT = "rreader/1.0 (https://github.com/yourrepo/rreader)"
```

### 9. Robust ID Strategy (High-Priority)
**Change Required:** Use feed GUID or hash-based ID instead of timestamp
```python
import hashlib

def generate_entry_id(feed):
    guid = getattr(feed, 'id', None) or getattr(feed, 'guid', None)
    if guid:
        return hashlib.md5(guid.encode()).hexdigest()[:16]
    # Fallback: hash(url + published_time)
    return hashlib.md5(f"{feed.link}{parsed_time}".encode()).hexdigest()[:16]
```

### 10. Entry Limits (High-Priority)
**Change Required:** Keep only N most recent entries per category
```python
MAX_ENTRIES_PER_CATEGORY = 200

# Before writing JSON:
rslt = [val for key, val in sorted(rslt.items(), reverse=True)[:MAX_ENTRIES_PER_CATEGORY]]
```

### 11. Content Extraction (High-Priority)
**Change Required:** Extract additional fields from feed
```python
entries = {
    "id": entry_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "description": getattr(feed, 'summary', getattr(feed, 'description', '')),
    "content": getattr(feed, 'content', [{}])[0].get('value', ''),
    "tags": [tag.term for tag in getattr(feed, 'tags', [])]
}
```

### 12-20. Lower Priority Items
For the remaining gaps, the implementation approach is:

- **Read/Unread State:** Add `"read": false` field to entries, expose `mark_read(entry_id)` function
- **Search/Filter:** Add `search(query, category=None)` function that greps through JSON files
- **Update Scheduling:** Create `scheduler.py` using `APScheduler` with configurable intervals
- **OPML Support:** Add `import_opml(file)` and `export_opml()` functions using `xml.etree`
- **Statistics:** Track metrics in separate `stats_{category}.json` with fetch times, success rates
- **Configurable Timezone:** Move `TIMEZONE` to user config file with default fallback
- **Category Management:** Add `add_category()`, `remove_category()`, `edit_feeds()` CLI commands
- **Image Extraction:** Add `"image": feed.get('media_content', [{}])[0].get('url', '')` to entries
- **Web UI/API:** Build Flask/FastAPI wrapper with REST endpoints for `GET /feeds`, `POST /refresh`, etc.