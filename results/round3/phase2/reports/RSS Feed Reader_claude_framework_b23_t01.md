# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a minimal RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from URLs
2. **Multi-source aggregation**: Reads feed sources from a JSON configuration file organized by category
3. **Deduplication by timestamp**: Uses publication timestamp as unique ID to prevent duplicate entries
4. **Time zone handling**: Converts all timestamps to a configured timezone (currently KST/UTC+9)
5. **Relative date formatting**: Shows "HH:MM" for today's items, "Mon DD, HH:MM" for older items
6. **Author attribution**: Supports optional per-category author display toggle
7. **JSON persistence**: Saves aggregated feeds to `~/.rreader/rss_{category}.json`
8. **Configuration management**: Creates default config from bundled `feeds.json` and merges new categories on updates
9. **Selective refresh**: Can update a single category or all categories
10. **Basic error handling**: Silently continues on feed fetch failures (with optional logging)

The code structure is clean with inline imports for standalone execution.

## Triage

### Critical Gaps

1. **No cache expiry or refresh logic** - Files are written but never read by this module; no TTL or staleness detection
2. **Silent failures mask problems** - Failed feeds are skipped with no user visibility unless logging is enabled
3. **Collision-prone ID scheme** - Using Unix timestamp as ID means feeds published in the same second collide and overwrite each other
4. **No feed validation** - Missing required fields (title, link) cause runtime errors downstream
5. **No rate limiting or politeness** - Fetches all feeds sequentially without delays; will anger servers and trigger bans

### Important Gaps

6. **No concurrency** - Sequential fetching is slow; production systems need async/parallel requests
7. **No content sanitization** - Feed titles/content are not HTML-escaped or length-limited
8. **No HTTP headers** - Missing User-Agent, etag support, conditional GET for bandwidth efficiency
9. **No feed health monitoring** - Can't detect chronically failing feeds or slow sources
10. **Configuration lacks validation** - Malformed `feeds.json` causes cryptic errors

### Nice-to-Have Gaps

11. **No enclosure/media handling** - Podcasts and images are ignored
12. **No full content fetching** - Only uses RSS summary; no fallback to fetch full article
13. **No deduplication by content** - Same story from different sources appears multiple times
14. **No feed discovery** - Must manually add feed URLs; no auto-detection from website URLs
15. **Limited timezone configurability** - Hardcoded in config.py rather than per-user setting

## Plan

### 1. Add cache expiry and refresh logic
```python
# In do() function, before fetching:
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        cached = json.load(f)
    age_seconds = int(time.time()) - cached['created_at']
    if age_seconds < 300:  # 5 minute TTL
        return cached  # Skip fetch if fresh
```

### 2. Add explicit error reporting
```python
# Replace try/except blocks with:
failed_feeds = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        if d.bozo:  # feedparser error flag
            failed_feeds.append((source, d.bozo_exception))
    except Exception as e:
        failed_feeds.append((source, str(e)))

# At end of function:
if failed_feeds:
    print(f"Failed to fetch {len(failed_feeds)} feeds:", file=sys.stderr)
    for source, error in failed_feeds:
        print(f"  {source}: {error}", file=sys.stderr)
```

### 3. Fix ID collision with composite key
```python
# Replace:
entries = {"id": ts, ...}
# With:
import hashlib
entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
entries = {"id": entry_id, ...}
```

### 4. Add feed entry validation
```python
# Before creating entries dict:
if not hasattr(feed, 'link') or not hasattr(feed, 'title'):
    continue  # Skip malformed entries
if not feed.link.startswith('http'):
    continue  # Skip invalid URLs
entries["title"] = feed.title[:200]  # Truncate long titles
```

### 5. Add rate limiting between requests
```python
import random
# In loop:
for source, url in urls.items():
    time.sleep(random.uniform(1.0, 2.0))  # Polite delay
    # ... fetch logic
```

### 6. Implement concurrent fetching
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_one_feed(source, url):
    try:
        d = feedparser.parse(url)
        return (source, d, None)
    except Exception as e:
        return (source, None, e)

results = {}
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_one_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source, d, error = future.result()
        if d:
            results[source] = d
```

### 7. Add HTML sanitization
```python
import html
# When creating entries:
entries["title"] = html.escape(feed.title)[:200]
```

### 8. Add HTTP best practices
```python
# Before feedparser.parse():
headers = {
    'User-Agent': 'rreader/1.0 (+https://github.com/yourrepo)',
    'Accept': 'application/rss+xml, application/atom+xml'
}
d = feedparser.parse(url, request_headers=headers)

# For etag support, persist and check:
# if cached_etag := get_cached_etag(url):
#     headers['If-None-Match'] = cached_etag
```

### 9. Add feed health tracking
```python
# In JSON output:
rslt = {
    "entries": rslt,
    "created_at": int(time.time()),
    "feed_health": {
        source: {
            "last_success": ts,
            "failure_count": 0,
            "avg_latency_ms": 150
        } for source in urls.keys()
    }
}
```

### 10. Validate configuration on load
```python
def validate_feeds_json(data):
    assert isinstance(data, dict), "Root must be object"
    for category, config in data.items():
        assert "feeds" in config, f"{category} missing 'feeds'"
        assert isinstance(config["feeds"], dict), f"{category} feeds must be object"
        for source, url in config["feeds"].items():
            assert url.startswith('http'), f"Invalid URL for {source}"
    return data

# After json.load(fp):
RSS = validate_feeds_json(json.load(fp))
```

### Priority Ordering for Implementation

**Week 1 (Critical):** Items 2, 3, 4 - Make failures visible and prevent data corruption  
**Week 2 (Important):** Items 1, 5, 7 - Add caching, politeness, basic security  
**Week 3 (Performance):** Items 6, 8 - Add concurrency and HTTP efficiency  
**Week 4 (Reliability):** Items 9, 10 - Add monitoring and validation  
**Backlog:** Items 11-15 - Feature additions for future consideration