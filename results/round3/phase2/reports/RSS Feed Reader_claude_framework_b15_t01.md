# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a working RSS feed aggregator with the following capabilities:

1. **Feed fetching and parsing**: Downloads and parses RSS/Atom feeds using `feedparser`
2. **Multi-source aggregation**: Handles multiple feed sources per category from a JSON configuration
3. **Timestamp normalization**: Converts feed timestamps to local timezone (KST/UTC+9)
4. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a single fetch
5. **Sorted output**: Returns entries reverse-chronologically by publication time
6. **Data persistence**: Saves parsed feeds as JSON files in `~/.rreader/`
7. **Configuration management**: 
   - Bundles default `feeds.json` with the package
   - Copies bundled config to user directory on first run
   - Merges new categories from bundled config without overwriting user modifications
8. **Flexible author display**: Supports per-category `show_author` flag to use feed author vs source name
9. **Human-readable timestamps**: Formats dates as "HH:MM" for today, "Mon DD, HH:MM" for older entries
10. **Selective fetching**: Can fetch a single category or all categories
11. **Optional logging**: Provides progress feedback when `log=True`

## Triage

### Critical (blocks production use)

1. **No error recovery or retry logic** - Single feed failure exits entire process
2. **No rate limiting** - Will hammer servers on large feed lists
3. **No caching between runs** - Refetches everything every time, wastes bandwidth
4. **Silent failures** - Try/except blocks swallow errors without logging what broke
5. **No data validation** - Malformed feeds can write corrupt JSON files

### High (degrades reliability/usability)

6. **No network timeouts** - Hung connections block indefinitely
7. **No stale data handling** - Old cached files persist forever with no expiration
8. **No incremental updates** - Can't fetch only new entries since last run
9. **Feed URL validation missing** - Invalid URLs accepted without checking
10. **No entry content storage** - Only saves title/link, loses article summaries

### Medium (limits functionality)

11. **No deduplication across fetches** - Same entry with different timestamps creates duplicates
12. **Hardcoded timezone** - KST is not configurable per-user
13. **No feed health monitoring** - Can't detect consistently failing feeds
14. **Missing OPML import/export** - Can't bulk import feed lists
15. **No entry read/unread tracking** - All entries treated as new every time

### Low (nice-to-have improvements)

16. **No concurrent fetching** - Fetches sequentially, slow for large lists
17. **No feed metadata** - Doesn't store feed title, description, icon
18. **Fixed storage location** - `~/.rreader/` not configurable via environment
19. **No entry search capability** - Can't filter by keyword
20. **Missing CLI interface** - Only callable as module

## Plan

### Critical Fixes

**1. Error recovery and retry logic**
```python
# In get_feed_from_rss(), replace the try/except blocks:

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Use session to fetch feeds with timeout:
session = create_session()
response = session.get(url, timeout=30)
d = feedparser.parse(response.content)

# Continue processing other feeds on individual failure instead of sys.exit()
```

**2. Rate limiting**
```python
# Add to top of get_feed_from_rss():
import time
from datetime import datetime

last_fetch = {}

for source, url in urls.items():
    # Enforce minimum 1 second between requests to same domain
    domain = urlparse(url).netloc
    if domain in last_fetch:
        elapsed = time.time() - last_fetch[domain]
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
    
    # ... fetch feed ...
    
    last_fetch[domain] = time.time()
```

**3. Implement caching with ETags/Last-Modified**
```python
# Add cache metadata file alongside each rss_{category}.json:
# rss_{category}_meta.json contains {url: {etag: "...", last_modified: "...", last_fetch: timestamp}}

def get_feed_from_rss(category, urls, show_author=False, log=False):
    cache_file = os.path.join(p["path_data"], f"rss_{category}_meta.json")
    cache_meta = {}
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cache_meta = json.load(f)
    
    for source, url in urls.items():
        headers = {}
        if url in cache_meta:
            if 'etag' in cache_meta[url]:
                headers['If-None-Match'] = cache_meta[url]['etag']
            if 'last_modified' in cache_meta[url]:
                headers['If-Modified-Since'] = cache_meta[url]['last_modified']
        
        response = session.get(url, headers=headers, timeout=30)
        
        if response.status_code == 304:
            # Not modified, skip parsing
            continue
        
        # Update cache metadata
        cache_meta[url] = {
            'etag': response.headers.get('ETag'),
            'last_modified': response.headers.get('Last-Modified'),
            'last_fetch': time.time()
        }
    
    # Save updated cache metadata
    with open(cache_file, 'w') as f:
        json.dump(cache_meta, f)
```

**4. Structured logging with error details**
```python
import logging

# Replace all log parameters with proper logging:
logger = logging.getLogger('rreader')

# In exception handlers:
except Exception as e:
    logger.error(f"Failed to fetch {url}: {type(e).__name__}: {e}")
    continue  # Don't exit, try next feed
```

**5. JSON schema validation**
```python
# Add validation before writing:
def validate_feed_data(data):
    assert 'entries' in data
    assert 'created_at' in data
    assert isinstance(data['entries'], list)
    for entry in data['entries']:
        required = ['id', 'sourceName', 'pubDate', 'timestamp', 'url', 'title']
        assert all(k in entry for k in required), f"Missing keys in entry: {entry}"
    return True

# Before writing:
validate_feed_data(rslt)
with open(...) as f:
    f.write(json.dumps(rslt, ensure_ascii=False))
```

### High Priority Enhancements

**6. Network timeouts (covered in #1)**

**7. Stale data expiration**
```python
# Add to beginning of do():
MAX_AGE_DAYS = 30

for category_file in os.listdir(p["path_data"]):
    if category_file.startswith("rss_") and category_file.endswith(".json"):
        filepath = os.path.join(p["path_data"], category_file)
        mtime = os.path.getmtime(filepath)
        age_days = (time.time() - mtime) / 86400
        if age_days > MAX_AGE_DAYS:
            os.remove(filepath)
            logger.info(f"Removed stale cache: {category_file}")
```

**8. Incremental updates**
```python
# Merge new entries with existing instead of overwriting:
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
existing_entries = {}
if os.path.exists(existing_file):
    with open(existing_file) as f:
        old_data = json.load(f)
        existing_entries = {e['id']: e for e in old_data['entries']}

# Merge new entries, keeping up to 1000 most recent:
existing_entries.update(rslt)
merged = [val for key, val in sorted(existing_entries.items(), reverse=True)[:1000]]

rslt = {"entries": merged, "created_at": int(time.time())}
```

**9. URL validation**
```python
from urllib.parse import urlparse

def validate_feed_url(url):
    parsed = urlparse(url)
    if not parsed.scheme in ['http', 'https']:
        raise ValueError(f"Invalid URL scheme: {url}")
    if not parsed.netloc:
        raise ValueError(f"Invalid URL, no domain: {url}")
    return True

# Call before fetching each feed
```

**10. Store entry content**
```python
# In the loop building entries dict:
entries = {
    # ... existing fields ...
    "summary": getattr(feed, 'summary', ''),
    "content": feed.get('content', [{}])[0].get('value', ''),
}
```

### Medium Priority Features

**11. Cross-fetch deduplication**
```python
# Use content-based ID instead of timestamp:
import hashlib

def generate_entry_id(feed):
    # Use URL as primary key, hash as fallback
    return feed.link or hashlib.md5(
        f"{feed.title}{getattr(feed, 'published', '')}".encode()
    ).hexdigest()

entries = {
    "id": generate_entry_id(feed),
    # ... rest of fields ...
}
```

**12. Configurable timezone**
```python
# In config.py:
TIMEZONE_OFFSET = int(os.getenv('RREADER_TZ_OFFSET', '9'))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET))
```

**13. Feed health monitoring**
```python
# Track failures in metadata:
cache_meta[url]['failures'] = cache_meta.get(url, {}).get('failures', 0)
cache_meta[url]['last_success'] = time.time()

# On failure:
cache_meta[url]['failures'] += 1

# Alert on consistent failures:
if cache_meta[url]['failures'] > 5:
    logger.warning(f"Feed {url} has failed {cache_meta[url]['failures']} times")
```

**14. OPML support**
```python
import xml.etree.ElementTree as ET

def import_opml(opml_file):
    tree = ET.parse(opml_file)
    feeds = {}
    for outline in tree.findall('.//outline[@type="rss"]'):
        category = outline.get('category', 'imported')
        if category not in feeds:
            feeds[category] = {"feeds": {}, "show_author": False}
        feeds[category]["feeds"][outline.get('title')] = outline.get('xmlUrl')
    return feeds

def export_opml(feeds_dict, output_file):
    # Generate OPML XML from feeds.json structure
    pass
```

**15. Read/unread tracking**
```python
# Add new file: rss_state.json with structure:
# {entry_id: {"read": bool, "starred": bool, "read_at": timestamp}}

def mark_read(entry_id):
    state_file = os.path.join(p["path_data"], "rss_state.json")
    state = {}
    if os.path.exists(state_file):
        with open(state_file) as f:
            state = json.load(f)
    
    state[entry_id] = {
        "read": True,
        "read_at": int(time.time())
    }
    
    with open(state_file, 'w') as f:
        json.dump(state, f)
```