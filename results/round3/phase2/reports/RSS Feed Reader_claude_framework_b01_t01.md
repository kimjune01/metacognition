# Diagnostic Report: RSS Feed Reader System

## Observations

This is an RSS feed aggregator that periodically fetches and caches articles from multiple sources. Currently working capabilities:

1. **Feed parsing** - Uses `feedparser` to retrieve and parse RSS/Atom feeds from URLs
2. **Multi-source aggregation** - Handles multiple feeds per category from a JSON configuration file
3. **Timestamp normalization** - Converts various feed date formats to consistent Unix timestamps
4. **Time-aware display** - Shows "HH:MM" for today's posts, "Mon DD, HH:MM" for older ones
5. **Timezone handling** - Converts UTC publish times to configured timezone (KST/UTC+9)
6. **Deduplication by timestamp** - Uses publication timestamp as ID to prevent duplicates within a fetch
7. **Sorted output** - Returns entries in reverse chronological order (newest first)
8. **Category-based organization** - Supports multiple feed categories with per-category settings
9. **JSON persistence** - Writes results to `~/.rreader/rss_{category}.json` files
10. **Author display control** - Optional `show_author` flag per category to show feed author vs source name
11. **Configuration management** - Copies bundled `feeds.json` to user directory, auto-merges new categories
12. **Selective fetching** - Can fetch single category or all categories

## Triage

### Critical (blocks production use)

1. **No error recovery** - `sys.exit()` on parse failure kills the entire process. One bad feed URL takes down all categories.
2. **No feed validation** - Missing required fields (title, link) will cause KeyError. Malformed feeds crash the parser.
3. **No rate limiting** - Fetches all feeds simultaneously with no delays. Will trigger rate limits or IP bans from feed hosts.
4. **Timestamp collision handling** - Using timestamp as ID means two posts published in the same second overwrite each other.

### High (necessary for reliability)

5. **No staleness detection** - Old cached data persists indefinitely. No TTL, no "last updated" checks.
6. **No network timeouts** - `feedparser.parse()` can hang indefinitely on slow/dead hosts.
7. **No logging** - The `log` parameter only prints to stdout. No persistent logs for debugging production issues.
8. **No retry logic** - Transient network failures are permanent. Should retry with exponential backoff.
9. **Missing feed metadata** - Doesn't store feed-level info (description, last-modified headers, etag) for conditional requests.

### Medium (quality of life)

10. **No incremental updates** - Re-fetches entire feed history every time. Should use etag/last-modified headers to fetch only new entries.
11. **No entry content** - Only stores title/link/pubdate. Doesn't capture description, content, or media attachments.
12. **Hard-coded paths** - `~/.rreader/` is not configurable via environment variables or CLI args.
13. **No feed health monitoring** - Doesn't track success/failure rates per feed to identify chronic failures.
14. **Weak deduplication** - Only dedupes within a single fetch. Doesn't merge with existing cached entries.

### Low (nice to have)

15. **No compression** - JSON files grow large with no archival or rotation strategy.
16. **No feed discovery** - Can't auto-detect RSS URLs from website URLs.
17. **No OPML import/export** - Industry-standard feed list format not supported.
18. **Silent bundled feed updates** - Auto-merges new categories from bundled file without notifying user.

## Plan

### Critical fixes

**1. Error recovery**
```python
# Replace sys.exit() with logging and continue
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        if d.bozo:  # feedparser's malformed feed flag
            logger.warning(f"Malformed feed {source}: {d.bozo_exception}")
            continue
    except Exception as e:
        logger.error(f"Failed to fetch {source} ({url}): {e}")
        continue  # Don't kill the whole process
```

**2. Feed validation**
```python
# Check required fields before accessing
required_fields = ['title', 'link']
if not all(hasattr(feed, field) for field in required_fields):
    logger.warning(f"Skipping incomplete entry from {source}")
    continue
```

**3. Rate limiting**
```python
import time
for source, url in urls.items():
    time.sleep(1)  # 1 second between feeds
    # Or use: from ratelimit import limits, sleep_and_retry
```

**4. Unique IDs**
```python
# Replace timestamp-based ID with hash of (url + timestamp + title)
import hashlib
entry_id = hashlib.sha256(
    f"{feed.link}{ts}{feed.title}".encode()
).hexdigest()[:16]
```

### High priority

**5. Staleness detection**
```python
# Add created_at check when reading cache
cache_age = time.time() - rslt.get("created_at", 0)
if cache_age > 3600:  # 1 hour TTL
    # Re-fetch feeds
```

**6. Network timeouts**
```python
# Configure feedparser with timeout
import socket
socket.setdefaulttimeout(10)  # 10 second timeout
# Or: use requests with timeout, then feed to feedparser
```

**7. Proper logging**
```python
import logging
logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)
```

**8. Retry logic**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_feed(url):
    return feedparser.parse(url)
```

**9. Feed metadata storage**
```python
# Store etag and last-modified per feed
feed_meta = {
    "etag": d.get("etag"),
    "modified": d.get("modified"),
    "last_fetch": int(time.time())
}
# Use in next request: feedparser.parse(url, etag=etag, modified=modified)
```

### Medium priority

**10. Conditional requests**
```python
# Load previous etag/modified from metadata file
prev_meta = load_feed_metadata(source)
d = feedparser.parse(
    url,
    etag=prev_meta.get("etag"),
    modified=prev_meta.get("modified")
)
if d.status == 304:  # Not modified
    continue
```

**11. Entry content capture**
```python
entries = {
    # ... existing fields ...
    "description": getattr(feed, 'summary', ''),
    "content": getattr(feed, 'content', [{}])[0].get('value', ''),
    "media": [m.get('href') for m in getattr(feed, 'media_content', [])]
}
```

**12. Configurable paths**
```python
# In config.py
DATA_PATH = os.getenv("RREADER_DATA_PATH", str(Path.home()) + "/.rreader/")
```

**13. Feed health tracking**
```python
# Store per-feed metrics
feed_stats = {
    "success_count": 0,
    "failure_count": 0,
    "last_success": None,
    "consecutive_failures": 0
}
# Disable feeds after N consecutive failures
```

**14. Merge with existing cache**
```python
# Load existing entries from file
existing = load_existing_entries(category)
# Merge by ID, keeping newest
all_entries = {**existing, **rslt}
```