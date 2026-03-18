# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a basic RSS feed aggregator with the following working capabilities:

1. **Feed parsing and aggregation**: Fetches RSS feeds from multiple sources defined in a JSON configuration file
2. **Time normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
3. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
4. **Chronological sorting**: Orders entries by publication time, newest first
5. **Data persistence**: Saves aggregated feeds as JSON files in `~/.rreader/` directory
6. **Configuration management**: Automatically copies bundled default feeds and merges new categories from updates
7. **Selective updates**: Can refresh a single category or all categories
8. **Flexible author display**: Supports per-category toggle between source name and original author
9. **Date formatting**: Shows time-only for today's entries, date+time for older ones
10. **Module/script duality**: Works both as importable module and standalone script

## Triage

### Critical (blocks production use)

1. **No error recovery or retry logic**: Single network failure kills the entire category update
2. **No rate limiting**: Will hammer feeds if run repeatedly, risking IP bans
3. **No stale data handling**: Old cached data persists indefinitely with no freshness indicator
4. **Silent failures**: Bare `except:` clauses swallow all errors without logging what went wrong
5. **No feed validation**: Malformed RSS or missing required fields cause unpredictable behavior

### High (limits reliability)

6. **No concurrency**: Sequential feed fetching makes updates slow for categories with many sources
7. **No HTTP timeout configuration**: Hung connections block indefinitely
8. **No user-agent header**: Some feeds block requests without proper identification
9. **No conditional GET support**: Re-downloads entire feeds even when unchanged (wastes bandwidth)
10. **No entry limit per source**: A single prolific feed can dominate a category

### Medium (impacts usability)

11. **No feed health monitoring**: No way to detect consistently failing feeds
12. **No incremental updates**: Always processes all entries, even ones already seen
13. **Timestamp collision handling**: Multiple entries published at same second will clobber each other
14. **No content sanitization**: Titles and URLs from feeds are trusted without validation
15. **No category-level caching strategy**: Can't specify different refresh intervals per category

### Low (polish issues)

16. **Inconsistent logging**: `log` parameter only partially implemented
17. **No progress indication**: Long updates provide no feedback
18. **Magic numbers**: File paths and defaults hardcoded rather than configurable
19. **No feed discovery**: Users must manually add feed URLs
20. **No OPML import/export**: Standard feed list format not supported

## Plan

### Critical fixes

**1. Error recovery**
```python
# Replace bare except in do():
for source, url in urls.items():
    max_retries = 3
    for attempt in range(max_retries):
        try:
            if log:
                sys.stdout.write(f"- {url} (attempt {attempt+1})")
            d = feedparser.parse(url)
            if d.bozo and not d.entries:
                raise ValueError(f"Invalid feed: {d.bozo_exception}")
            break
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"\nFailed after {max_retries} attempts: {e}", file=sys.stderr)
                # Log to error file: append to ~/.rreader/errors.log
                continue  # Skip this feed, don't kill entire category
            time.sleep(2 ** attempt)  # Exponential backoff
```

**2. Rate limiting**
```python
# Add to top of get_feed_from_rss():
from threading import Lock
import time

_last_request_time = {}
_request_lock = Lock()

def rate_limited_parse(url, min_interval=1.0):
    """Ensure at least min_interval seconds between requests to same domain."""
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    
    with _request_lock:
        last_time = _last_request_time.get(domain, 0)
        elapsed = time.time() - last_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        _last_request_time[domain] = time.time()
    
    return feedparser.parse(url)
```

**3. Stale data handling**
```python
# In do() before returning rslt:
rslt["created_at"] = int(time.time())
rslt["ttl_seconds"] = 3600  # Add time-to-live metadata

# When reading cached data elsewhere:
def is_stale(cache_file, max_age_seconds=3600):
    with open(cache_file) as f:
        data = json.load(f)
    return (time.time() - data.get("created_at", 0)) > max_age_seconds
```

**4. Structured error logging**
```python
import logging

# Replace sys.stdout.write and except blocks:
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

handler = logging.FileHandler(os.path.join(p["path_data"], "rreader.log"))
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# In parsing loop:
try:
    d = feedparser.parse(url)
except Exception as e:
    logger.error(f"Failed to parse {url}: {type(e).__name__}: {e}")
    continue
```

**5. Feed validation**
```python
def validate_entry(feed):
    """Return cleaned entry dict or None if invalid."""
    required = ['link', 'title']
    if not all(hasattr(feed, attr) for attr in required):
        logger.warning(f"Entry missing required fields: {feed.get('title', 'NO_TITLE')}")
        return None
    
    # Require at least one time field
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        logger.warning(f"Entry missing timestamp: {feed.title}")
        return None
    
    return {
        "url": feed.link[:2000],  # Limit length
        "title": feed.title[:500],
        "timestamp": int(time.mktime(parsed_time)),
        # ... other fields
    }
```

### High priority improvements

**6. Concurrent fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    def fetch_one(source, url):
        # Move existing fetch logic here
        return source, entries_dict
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_source = {
            executor.submit(fetch_one, source, url): source 
            for source, url in urls.items()
        }
        
        for future in as_completed(future_to_source):
            try:
                source, entries = future.result(timeout=30)
                rslt.update(entries)
            except Exception as e:
                logger.error(f"Failed to fetch {source}: {e}")
    
    # Continue with dedup and sorting...
```

**7. HTTP timeout configuration**
```python
# Add to config.py:
FEED_TIMEOUT = 30  # seconds

# Modify feedparser call:
d = feedparser.parse(url, timeout=FEED_TIMEOUT)
```

**8. User-agent header**
```python
# Add to config.py:
USER_AGENT = "rreader/1.0 (+https://github.com/yourusername/rreader)"

# Configure feedparser globally:
feedparser.USER_AGENT = USER_AGENT
```

**9. Conditional GET support**
```python
# Store ETags and Last-Modified in category JSON:
{
    "entries": [...],
    "created_at": 123456,
    "feed_metadata": {
        "https://example.com/feed": {
            "etag": "abc123",
            "modified": "Wed, 01 Jan 2025 12:00:00 GMT"
        }
    }
}

# Use when fetching:
def parse_with_cache(url, etag=None, modified=None):
    d = feedparser.parse(url, etag=etag, modified=modified)
    if d.status == 304:  # Not modified
        return None  # Use cached data
    return d, d.get('etag'), d.get('modified')
```

**10. Entry limit per source**
```python
# Add to feeds.json schema:
{
    "tech": {
        "feeds": {"Source": "url"},
        "max_entries_per_feed": 20,  # New field
        "show_author": false
    }
}

# Apply when building rslt:
from collections import defaultdict
entries_per_source = defaultdict(int)

for feed in d.entries:
    if entries_per_source[source] >= max_entries:
        continue
    # ... process entry
    entries_per_source[source] += 1
```

### Medium priority enhancements

**11. Feed health monitoring**
```python
# Add to category JSON:
{
    "feed_health": {
        "https://example.com/feed": {
            "last_success": 1234567890,
            "consecutive_failures": 0,
            "total_failures": 5,
            "disabled": false
        }
    }
}

# Update after each fetch attempt:
def update_feed_health(url, success):
    # Load existing health data
    if success:
        health[url]["consecutive_failures"] = 0
        health[url]["last_success"] = int(time.time())
    else:
        health[url]["consecutive_failures"] += 1
        health[url]["total_failures"] += 1
        if health[url]["consecutive_failures"] >= 10:
            health[url]["disabled"] = True
            logger.warning(f"Disabling feed after 10 failures: {url}")
```

**12. Incremental updates**
```python
# Track highest seen timestamp per category:
def get_new_entries_only(category, entries):
    state_file = os.path.join(p["path_data"], f"state_{category}.json")
    
    try:
        with open(state_file) as f:
            state = json.load(f)
        last_ts = state.get("last_timestamp", 0)
    except FileNotFoundError:
        last_ts = 0
    
    new_entries = [e for e in entries if e["timestamp"] > last_ts]
    
    if new_entries:
        state = {"last_timestamp": max(e["timestamp"] for e in new_entries)}
        with open(state_file, "w") as f:
            json.dump(state, f)
    
    return new_entries
```

**13. Timestamp collision prevention**
```python
# Change ID generation:
seen_ids = set()

for feed in d.entries:
    base_id = int(time.mktime(parsed_time))
    entry_id = base_id
    counter = 0
    
    # Append counter if collision
    while entry_id in seen_ids or entry_id in rslt:
        counter += 1
        entry_id = f"{base_id}_{counter}"
    
    seen_ids.add(entry_id)
    entries["id"] = entry_id
```

**14. Content sanitization**
```python
import html
from urllib.parse import urlparse

def sanitize_entry(entry):
    # HTML-decode titles
    entry["title"] = html.unescape(entry["title"])
    
    # Validate URLs
    parsed = urlparse(entry["url"])
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid URL scheme: {entry['url']}")
    
    # Strip dangerous characters from source names
    entry["sourceName"] = "".join(
        c for c in entry["sourceName"] 
        if c.isalnum() or c in (" ", "-", "_")
    )
    
    return entry
```

**15. Per-category refresh intervals**
```python
# Add to feeds.json:
{
    "tech": {
        "feeds": {...},
        "refresh_interval_seconds": 1800  # 30 minutes
    },
    "news": {
        "feeds": {...},
        "refresh_interval_seconds": 300  # 5 minutes (more urgent)
    }
}

# Check before fetching:
def should_refresh(category, config):
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(cache_file):
        return True
    
    with open(cache_file) as f:
        data = json.load(f)
    
    age = time.time() - data.get("created_at", 0)
    interval = config.get("refresh_interval_seconds", 3600)
    
    return age >= interval
```

This plan prioritizes reliability and production-readiness first, then performance, then user experience polish. Each fix is scoped to be implementable in isolation.