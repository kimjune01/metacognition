# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing and aggregation**: Fetches multiple RSS feeds from configurable sources using `feedparser`
2. **Multi-category support**: Organizes feeds into categories (e.g., tech, news, blogs) defined in `feeds.json`
3. **Time normalization**: Converts feed timestamps to a configurable timezone (default: KST/UTC+9)
4. **Smart date formatting**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older entries
5. **Deduplication by timestamp**: Uses publication timestamp as unique ID to prevent duplicate entries
6. **Persistent storage**: Caches parsed feeds as JSON files (`rss_{category}.json`) in `~/.rreader/`
7. **Configuration management**: Copies bundled `feeds.json` on first run, merges new categories from updates
8. **Selective updates**: Can refresh a single category or all categories
9. **Optional logging**: Shows progress during feed fetching when enabled
10. **Author attribution**: Supports per-category `show_author` flag to display feed author vs source name

The code structure separates concerns (fetch logic, config, common utilities) and handles basic error cases (missing timestamps, network failures).

## Triage

### Critical (P0) - System will fail in production without these:

1. **No error recovery or retry logic**: Network failures, malformed feeds, or timeouts cause silent data loss
2. **Unbounded memory growth**: The deduplication dict accumulates all entries before sorting; large feeds will OOM
3. **No rate limiting**: Simultaneous requests to the same domain will trigger 429s or bans
4. **Feed update staleness**: No TTL/cache expiration; stale data persists indefinitely
5. **Blocking I/O**: Synchronous `feedparser.parse()` blocks the entire process during slow fetches

### High (P1) - Major usability/reliability issues:

6. **No feed validation**: Accepts any URL; doesn't verify feed format or accessibility before storing
7. **Silent failure mode**: `sys.exit(0)` on error means operators can't distinguish success from failure
8. **No monitoring/observability**: No metrics, health checks, or structured logging for production debugging
9. **Timestamp collision handling**: Multiple entries at the same second overwrite each other
10. **Missing data integrity checks**: Corrupted JSON files crash the system; no validation or recovery

### Medium (P2) - Quality-of-life improvements:

11. **No incremental updates**: Always fetches full feeds; wastes bandwidth and processing
12. **Hard-coded paths**: `~/.rreader/` isn't configurable; breaks containerized deployments
13. **No feed metadata preservation**: Loses description, tags, enclosures, content body
14. **Inefficient sorting**: Re-sorts entire feed list on every update instead of merge-sorting new entries
15. **No CLI interface**: Requires calling `do()` programmatically; lacks user-friendly commands

## Plan

### P0 Fixes

**1. Error recovery and retry logic**
```python
# In get_feed_from_rss(), replace the bare try/except with:
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
session.mount("http://", HTTPAdapter(max_retries=retry_strategy))
session.mount("https://", HTTPAdapter(max_retries=retry_strategy))

# Pass session to feedparser:
d = feedparser.parse(url, request_headers={'User-Agent': 'rreader/1.0'}, 
                     handlers=[session.get])
```
Log failures to a separate error file with timestamp and URL for later investigation.

**2. Stream processing for memory efficiency**
```python
# Replace dict accumulation with generator + external merge:
def stream_entries(d):
    for feed in d.entries:
        # ... existing parsing logic ...
        yield entries

# In get_feed_from_rss():
all_entries = heapq.merge(
    *[stream_entries(feedparser.parse(url)) for url in urls.values()],
    key=lambda x: x['timestamp'],
    reverse=True
)
# Write to file incrementally using json.dump with iterencode
```

**3. Rate limiting**
```python
# At module level:
from urllib.parse import urlparse
from collections import defaultdict
import threading

rate_limiters = defaultdict(lambda: threading.Semaphore(2))  # 2 concurrent per domain

# In get_feed_from_rss():
domain = urlparse(url).netloc
with rate_limiters[domain]:
    time.sleep(0.5)  # 500ms between requests to same domain
    d = feedparser.parse(url)
```

**4. Cache expiration with ETags/Last-Modified**
```python
# Store feed metadata alongside entries:
metadata = {
    'etag': d.get('etag'),
    'modified': d.get('modified'),
    'last_fetch': int(time.time())
}

# On subsequent fetches:
cached_meta = load_metadata(category)
d = feedparser.parse(url, 
                     etag=cached_meta.get('etag'),
                     modified=cached_meta.get('modified'))
if d.status == 304:  # Not modified
    return cached_data
```
Add a `max_age` field in `feeds.json` (default: 3600s) and skip fetches if `time.time() - last_fetch < max_age`.

**5. Async I/O with connection pooling**
```python
import asyncio
import aiohttp

async def fetch_feed(session, source, url):
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        content = await resp.text()
        return feedparser.parse(content)

async def get_feed_from_rss_async(category, urls, ...):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_feed(session, src, url) for src, url in urls.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
    # ... rest of processing ...
```
Change `do()` to `asyncio.run(do_async())`.

### P1 Fixes

**6. Feed validation**
```python
# Add to feeds.json schema:
{
  "tech": {
    "feeds": {
      "TechCrunch": "https://techcrunch.com/feed/"
    },
    "validation": {
      "required_fields": ["title", "link"],
      "max_age_days": 90
    }
  }
}

# On feed addition:
def validate_feed(url, rules):
    d = feedparser.parse(url)
    if d.bozo:  # Parse error
        raise ValueError(f"Invalid feed: {d.bozo_exception}")
    if not d.entries:
        raise ValueError("Feed has no entries")
    # Check required fields, date range, etc.
```

**7. Structured logging**
```python
import logging
import json

logger = logging.getLogger('rreader')
handler = logging.FileHandler(os.path.join(p['path_data'], 'rreader.log'))
handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
logger.addHandler(handler)

# Replace print statements:
logger.info(json.dumps({
    'event': 'feed_fetch',
    'category': category,
    'source': source,
    'url': url,
    'entries_count': len(d.entries),
    'duration_ms': elapsed
}))

# Return structured status instead of sys.exit(0):
return {
    'success': True,
    'entries_count': len(rslt['entries']),
    'errors': []
}
```

**8. Monitoring endpoints**
```python
# Add health check:
def health_check():
    checks = {
        'feeds_file_exists': os.path.exists(FEEDS_FILE_NAME),
        'data_dir_writable': os.access(p['path_data'], os.W_OK),
        'last_update_age': get_last_update_age(),
    }
    return {
        'status': 'healthy' if all(checks.values()) else 'degraded',
        'checks': checks
    }

# Add metrics collection:
from prometheus_client import Counter, Histogram
fetch_duration = Histogram('feed_fetch_duration_seconds', 'Feed fetch time')
fetch_errors = Counter('feed_fetch_errors_total', 'Feed fetch failures', ['category', 'source'])
```

**9. Collision-resistant IDs**
```python
# Replace timestamp-only ID with composite key:
import hashlib

entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
```

**10. Data integrity validation**
```python
import jsonschema

ENTRY_SCHEMA = {
    "type": "object",
    "required": ["id", "sourceName", "timestamp", "url", "title"],
    "properties": {
        "timestamp": {"type": "integer", "minimum": 0},
        "url": {"type": "string", "format": "uri"}
    }
}

# Before writing:
jsonschema.validate(rslt, FEED_SCHEMA)

# On load, catch JSONDecodeError:
try:
    with open(json_path, 'r') as f:
        data = json.load(f)
except json.JSONDecodeError:
    logger.error(f"Corrupted file: {json_path}")
    shutil.copy(json_path, f"{json_path}.corrupted.{int(time.time())}")
    return default_data
```

### P2 Improvements

**11. Incremental updates with ETags (covered in #4)**

**12. Configurable paths**
```python
# Add environment variable support:
p = {
    'path_data': os.getenv('RREADER_DATA_DIR', defaultdir + '.rreader/')
}

# Or use XDG Base Directory spec:
from platformdirs import user_data_dir
p = {'path_data': user_data_dir('rreader')}
```

**13. Extended metadata storage**
```python
# Expand entries dict:
entries = {
    "id": entry_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', '')[:500],
    "content": getattr(feed, 'content', [{}])[0].get('value', '')[:2000],
    "tags": [tag.term for tag in getattr(feed, 'tags', [])],
    "enclosures": [e.href for e in getattr(feed, 'enclosures', [])]
}
```

**14. Efficient merge sorting**
```python
# Load existing entries and merge:
existing = load_existing_entries(category)
new_entries = fetch_new_entries(category)

merged = list(heapq.merge(
    existing,
    new_entries,
    key=lambda x: x['timestamp'],
    reverse=True
))[:1000]  # Keep only latest 1000
```

**15. CLI interface**
```python
# Add argparse entrypoint:
def main():
    parser = argparse.ArgumentParser(description='RSS feed reader')
    parser.add_argument('command', choices=['fetch', 'list', 'add'])
    parser.add_argument('--category', help='Target category')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    
    if args.command == 'fetch':
        do(target_category=args.category, log=args.verbose)
    # ... other commands

if __name__ == '__main__':
    main()
```