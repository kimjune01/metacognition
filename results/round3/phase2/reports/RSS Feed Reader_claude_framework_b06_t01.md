# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed aggregator with the following capabilities:

**Working Features:**
- Parses multiple RSS/Atom feeds from configurable sources organized by category
- Extracts essential metadata: title, URL, publication date, author/source, timestamp
- Handles multiple date formats (`published_parsed`, `updated_parsed`)
- Deduplicates entries by timestamp across sources within a category
- Sorts entries chronologically (newest first)
- Formats publication dates contextually (time-only for today, date+time for older)
- Timezone-aware datetime handling (currently hardcoded to UTC+9/KST)
- Persists aggregated data as JSON per category (`rss_{category}.json`)
- Manages user configuration file (`feeds.json`) with automatic initialization
- Merges new bundled categories into existing user config without overwriting
- Supports per-category `show_author` toggle (defaults to source name)
- Command-line interface with optional category filtering and logging
- Graceful fallback when feed parsing fails (continues processing remaining feeds)

**Architecture:**
- Separation of concerns: feed fetching, parsing, persistence
- Configuration-driven design (feeds defined in JSON, not hardcoded)
- Timestamp-based deduplication handles same article from multiple sources
- Creates data directory automatically if missing

## Triage

### Critical (Blocks Production Use)

1. **No error recovery or retry logic** — Single network timeout kills entire category update
2. **No rate limiting** — Can overwhelm feed servers or trigger bans
3. **No feed validation** — Malformed feeds crash silently; no health monitoring
4. **No concurrent fetching** — Sequential processing makes updates very slow at scale
5. **Hardcoded timezone** — Violates portability; breaks for non-KST users

### High (Degrades User Experience)

6. **No caching/conditional requests** — Wastes bandwidth; re-downloads unchanged feeds
7. **No entry limits** — Memory/disk usage unbounded; performance degrades over time
8. **Silent failure mode** — `sys.exit(0)` on error hides problems from users/monitoring
9. **No feed metadata** — Can't display feed title, description, last-updated timestamp
10. **No entry content** — Only stores title/link; can't show summaries or full text

### Medium (Limits Functionality)

11. **No incremental updates** — Always processes all feeds; can't update single source
12. **No duplicate URL detection** — Same article from different feeds creates duplicate entries
13. **No category management** — Can't add/remove/rename categories without manual JSON editing
14. **No entry expiration** — Old entries accumulate forever
15. **Timestamp collision handling** — Two entries published at same second clobber each other

### Low (Nice to Have)

16. **No feed discovery** — Can't auto-detect feeds from website URLs
17. **No OPML import/export** — Can't migrate from other readers
18. **No read/unread tracking** — All entries treated as new every time
19. **No search/filtering** — Must scan entire JSON to find entries
20. **No HTML sanitization** — Stored content could contain malicious markup

## Plan

### Critical Fixes

**1. Error Recovery and Retry**
```python
# Replace bare try/except with structured error handling
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def get_feed_with_retry(url, max_retries=3):
    session = requests.Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    response = session.get(url, timeout=15)
    return feedparser.parse(response.content)

# Store failures for reporting
failed_feeds = []
try:
    d = get_feed_with_retry(url)
except Exception as e:
    failed_feeds.append({'url': url, 'error': str(e)})
    continue  # Don't exit; process remaining feeds
```

**2. Rate Limiting**
```python
import time
from collections import defaultdict

last_request = defaultdict(float)
MIN_INTERVAL = 1.0  # seconds between requests to same domain

def rate_limited_fetch(url):
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    
    elapsed = time.time() - last_request[domain]
    if elapsed < MIN_INTERVAL:
        time.sleep(MIN_INTERVAL - elapsed)
    
    last_request[domain] = time.time()
    return get_feed_with_retry(url)
```

**3. Feed Validation**
```python
def validate_feed(parsed_feed, url):
    errors = []
    
    if parsed_feed.bozo:  # feedparser's error flag
        errors.append(f"Parse error: {parsed_feed.bozo_exception}")
    
    if not parsed_feed.entries:
        errors.append("No entries found")
    
    if not hasattr(parsed_feed, 'feed'):
        errors.append("Missing feed metadata")
    
    # Store validation results
    with open(f"{p['path_data']}/feed_health.json", 'a') as f:
        json.dump({
            'url': url,
            'timestamp': int(time.time()),
            'valid': len(errors) == 0,
            'errors': errors
        }, f)
        f.write('\n')
    
    return len(errors) == 0
```

**4. Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    def fetch_single(source, url):
        try:
            d = rate_limited_fetch(url)
            if validate_feed(d, url):
                return source, d
        except Exception as e:
            if log:
                sys.stderr.write(f"Failed {url}: {e}\n")
        return source, None
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_single, src, url): (src, url)
            for src, url in urls.items()
        }
        
        for future in as_completed(futures):
            source, feed = future.result()
            if feed:
                # Process entries as before
                pass
```

**5. Configurable Timezone**
```python
# In config.py, change to:
import os
from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo(os.getenv('TZ', 'Asia/Seoul'))

# Or add to feeds.json:
{
    "settings": {
        "timezone": "America/New_York"
    },
    "categories": { ... }
}
```

### High Priority

**6. Conditional Requests (ETags/Last-Modified)**
```python
# Add to each category's JSON:
{
    "entries": [...],
    "feed_metadata": {
        "url": {
            "etag": "abc123",
            "last_modified": "Mon, 01 Jan 2024 00:00:00 GMT"
        }
    }
}

# Use in request:
headers = {}
if existing_etag := feed_metadata.get(url, {}).get('etag'):
    headers['If-None-Match'] = existing_etag
if existing_modified := feed_metadata.get(url, {}).get('last_modified'):
    headers['If-Modified-Since'] = existing_modified

response = session.get(url, headers=headers)
if response.status_code == 304:
    # Use cached entries
    pass
```

**7. Entry Limits and Rotation**
```python
# Add to feeds.json per category:
{
    "feeds": {...},
    "max_entries": 500,  # Keep newest 500 entries
    "max_age_days": 30    # Drop entries older than 30 days
}

# Apply when storing:
now = int(time.time())
max_age = now - (category_config['max_age_days'] * 86400)

rslt = [
    entry for entry in sorted(rslt.values(), reverse=True, key=lambda x: x['timestamp'])
    if entry['timestamp'] > max_age
][:category_config['max_entries']]
```

**8. Structured Error Reporting**
```python
# Replace sys.exit(0) with:
import logging

logging.basicConfig(
    filename=f"{p['path_data']}/rreader.log",
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# On error:
logging.error(f"Failed to fetch {url}: {e}")
# Don't exit; continue processing

# Return summary:
return {
    'entries': rslt,
    'created_at': int(time.time()),
    'stats': {
        'feeds_attempted': len(urls),
        'feeds_succeeded': len(urls) - len(failed_feeds),
        'entries_new': len(rslt),
        'errors': failed_feeds
    }
}
```

**9. Feed Metadata Storage**
```python
# Extract and store:
feed_info = {
    'title': getattr(d.feed, 'title', 'Unknown'),
    'subtitle': getattr(d.feed, 'subtitle', ''),
    'link': getattr(d.feed, 'link', url),
    'updated': getattr(d.feed, 'updated', None)
}

# Add to category JSON:
{
    'feed_metadata': {url: feed_info for url, feed_info in ...},
    'entries': [...]
}
```

**10. Entry Content Extraction**
```python
# Add to entries dict:
'summary': getattr(feed, 'summary', ''),
'content': getattr(feed, 'content', [{}])[0].get('value', ''),
'media': [
    {'url': m.get('url'), 'type': m.get('type')}
    for m in getattr(feed, 'media_content', [])
]
```

### Medium Priority

**11-15**: Implement incremental updates by checking `created_at` timestamp, add URL normalization for deduplication (`urllib.parse.urlparse` + comparison), create CLI commands for feed management, add `max_age_days` pruning on load, switch from timestamp-as-key to UUID for entries (store timestamp collision as list).

### Low Priority

**16-20**: Add `feedfinder` library for auto-discovery, implement OPML parser/generator, add `read_status` boolean to entries dict, create search index with `whoosh` or SQLite FTS, implement HTML sanitization with `bleach` library before storage.