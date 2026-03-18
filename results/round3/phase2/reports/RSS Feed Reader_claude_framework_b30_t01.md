# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS feed parsing and aggregation** from multiple sources organized by category
2. **Feed configuration management** with automatic initialization from bundled defaults
3. **Incremental configuration updates** that merge new categories from bundled feeds without overwriting user customizations
4. **Timestamp-based deduplication** using entry publication time as unique ID
5. **Timezone-aware date formatting** (configured for KST/UTC+9) with relative display (today shows HH:MM, others show abbreviated date)
6. **Per-category author display control** via `show_author` flag
7. **JSON persistence** of parsed feeds to `~/.rreader/` directory
8. **Sorted output** with newest entries first
9. **Graceful import handling** for both package and standalone execution modes
10. **Automatic directory creation** for data storage path

## Triage

### Critical (Production Blockers)

1. **No error recovery or retry logic** - Network failures cause silent data loss; the `try/except` around parsing swallows errors without logging
2. **Race conditions in file I/O** - Concurrent executions could corrupt JSON files; no file locking
3. **No feed validation** - Malformed feeds or invalid timestamps crash the parser
4. **Memory unbounded** - All feed entries accumulate in `rslt` dictionary with no size limits

### High (Operational Requirements)

5. **No cache invalidation strategy** - Stale data persists indefinitely; `created_at` timestamp is recorded but never checked
6. **No rate limiting** - Rapid repeated calls could trigger IP bans from feed providers
7. **Missing observability** - No structured logging, metrics, or health checks
8. **No entry content preservation** - Only metadata stored; full article content/summary discarded
9. **Duplicate detection inadequate** - Using timestamp as ID means simultaneous publications collide
10. **Configuration schema not enforced** - `feeds.json` structure is implicit; malformed config causes runtime errors

### Medium (Feature Gaps)

11. **No feed autodiscovery** - Cannot detect RSS/Atom links from HTML pages
12. **No incremental updates** - Always fetches entire feed; wastes bandwidth for large feeds
13. **No entry filtering** - Cannot exclude by keyword, date range, or read status
14. **No cleanup/archival** - Old entries accumulate forever
15. **Hardcoded timezone** - KST baked in; not configurable per-user

### Low (Polish)

16. **No progress indication** - Only shows per-feed status when `log=True`
17. **No feed metadata storage** - Feed title, description, update frequency not captured
18. **No OPML import/export** - Cannot bulk-manage subscriptions

## Plan

### 1. Error Recovery (Critical)
**Change:** Replace bare `except:` with specific exception handling and exponential backoff retry.
```python
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_feed(url):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return feedparser.parse(response.content)
```
**Reason:** Silent failures mean users see incomplete data. Retries handle transient network issues. Specific exceptions enable debugging.

### 2. File Locking (Critical)
**Change:** Use `fcntl` (Unix) or `msvcrt` (Windows) for advisory locks around JSON operations.
```python
import fcntl
import json

def atomic_json_write(path, data):
    tmp = path + '.tmp'
    with open(tmp, 'w') as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        json.dump(data, f)
        fcntl.flock(f, fcntl.LOCK_UN)
    os.replace(tmp, path)  # Atomic on POSIX
```
**Reason:** Multiple cron jobs or manual invocations could corrupt data files.

### 3. Feed Validation (Critical)
**Change:** Add Pydantic models for feed structure and validate before processing.
```python
from pydantic import BaseModel, HttpUrl, validator
from typing import Dict

class FeedEntry(BaseModel):
    id: int
    sourceName: str
    url: HttpUrl
    title: str
    timestamp: int
    
    @validator('timestamp')
    def timestamp_reasonable(cls, v):
        if not (0 < v < 2**31):  # Unix timestamp range
            raise ValueError('Invalid timestamp')
        return v
```
**Reason:** Prevents crashes from malformed data. Makes implicit schema explicit.

### 4. Memory Bounds (Critical)
**Change:** Add configurable max entries per feed and per category.
```python
MAX_ENTRIES_PER_FEED = 100
MAX_ENTRIES_PER_CATEGORY = 1000

rslt = {}
for source, url in urls.items():
    # ... fetch logic ...
    for feed in d.entries[:MAX_ENTRIES_PER_FEED]:  # Limit per source
        # ... process ...
        
rslt = [val for key, val in sorted(rslt.items(), reverse=True)[:MAX_ENTRIES_PER_CATEGORY]]
```
**Reason:** High-volume feeds (Reddit, Hacker News) can OOM the process.

### 5. Cache TTL (High)
**Change:** Add `ttl_seconds` to feed config and skip fetch if cache is fresh.
```python
def should_refresh(category, ttl=3600):
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(cache_file):
        return True
    with open(cache_file) as f:
        data = json.load(f)
    age = time.time() - data.get('created_at', 0)
    return age > ttl
```
**Reason:** Reduces server load and respects feed provider's update frequency.

### 6. Rate Limiting (High)
**Change:** Add per-domain request throttling with `ratelimit` or token bucket.
```python
from ratelimit import limits, sleep_and_retry
from urllib.parse import urlparse

@sleep_and_retry
@limits(calls=1, period=5)  # 1 req per 5 sec per domain
def rate_limited_fetch(url):
    domain = urlparse(url).netloc
    return fetch_feed(url)
```
**Reason:** Avoid 429 errors and IP bans from aggressive polling.

### 7. Structured Logging (High)
**Change:** Replace `sys.stdout.write` with `logging` module and JSON formatter.
```python
import logging
import logging.config

logging.config.dictConfig({
    'version': 1,
    'formatters': {'json': {'()': 'pythonjsonlogger.jsonlogger.JsonFormatter'}},
    'handlers': {'file': {'class': 'logging.FileHandler', 'filename': 'rreader.log', 'formatter': 'json'}},
    'root': {'level': 'INFO', 'handlers': ['file']}
})

logger = logging.getLogger(__name__)
logger.info('Fetching feed', extra={'url': url, 'category': category})
```
**Reason:** Enables debugging, monitoring, and alerting in production.

### 8. Content Preservation (High)
**Change:** Store `summary` or `content` field from feed entry.
```python
entries = {
    # ... existing fields ...
    "summary": getattr(feed, 'summary', ''),
    "content": getattr(feed, 'content', [{}])[0].get('value', ''),
}
```
**Reason:** Enables full-text search and offline reading without re-fetching.

### 9. Better Deduplication (High)
**Change:** Use content hash instead of timestamp as ID.
```python
import hashlib

def entry_id(feed):
    content = f"{feed.link}{feed.title}".encode('utf-8')
    return int(hashlib.sha256(content).hexdigest()[:16], 16)  # 64-bit int
```
**Reason:** Handles simultaneous publications and updates to existing articles.

### 10. Config Schema Enforcement (High)
**Change:** Validate `feeds.json` on load with Pydantic.
```python
class FeedConfig(BaseModel):
    feeds: Dict[str, HttpUrl]
    show_author: bool = False

class RSSConfig(BaseModel):
    __root__: Dict[str, FeedConfig]

def load_config(path):
    with open(path) as f:
        return RSSConfig.parse_obj(json.load(f))
```
**Reason:** Catches typos and structural errors early with clear error messages.

### 11. Feed Autodiscovery (Medium)
**Change:** Add function to extract RSS links from HTML `<link rel="alternate">` tags.
```python
import requests
from bs4 import BeautifulSoup

def discover_feeds(html_url):
    response = requests.get(html_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    return [link['href'] for link in soup.find_all('link', type='application/rss+xml')]
```
**Reason:** Improves UX—users can add blogs by homepage URL.

### 12. Incremental Updates (Medium)
**Change:** Store `ETag`/`Last-Modified` headers and use conditional requests.
```python
def fetch_if_modified(url, etag=None, last_modified=None):
    headers = {}
    if etag:
        headers['If-None-Match'] = etag
    if last_modified:
        headers['If-Modified-Since'] = last_modified
    response = requests.get(url, headers=headers)
    if response.status_code == 304:
        return None  # Not modified
    return response.content, response.headers.get('ETag'), response.headers.get('Last-Modified')
```
**Reason:** Reduces bandwidth by 95%+ for unchanged feeds.

### 13. Entry Filtering (Medium)
**Change:** Add `filters` dict to category config with regex patterns.
```python
import re

def matches_filters(entry, filters):
    if 'exclude_title' in filters:
        if re.search(filters['exclude_title'], entry['title'], re.I):
            return False
    if 'min_date' in filters:
        if entry['timestamp'] < filters['min_date']:
            return False
    return True
```
**Reason:** Lets users hide sponsored content, old news, or off-topic posts.

### 14. Entry Archival (Medium)
**Change:** Add `archive_after_days` config and move old entries to separate file.
```python
def archive_old_entries(category, keep_days=30):
    cutoff = time.time() - (keep_days * 86400)
    # ... split entries by timestamp, write to rss_{category}_archive.json
```
**Reason:** Keeps active dataset small while preserving history.

### 15. Configurable Timezone (Medium)
**Change:** Move `TIMEZONE` to per-user config file.
```python
# In user's ~/.rreader/config.json:
{"timezone": "America/New_York"}

# In code:
import pytz
tz = pytz.timezone(user_config['timezone'])
at = datetime.datetime(*parsed_time[:6]).replace(tzinfo=pytz.utc).astimezone(tz)
```
**Reason:** Supports global user base.

### 16. Progress Indication (Low)
**Change:** Use `tqdm` for progress bar during multi-feed fetch.
```python
from tqdm import tqdm

for source, url in tqdm(urls.items(), desc=f"Fetching {category}"):
    # ... fetch logic ...
```
**Reason:** Improves perceived performance on slow networks.

### 17. Feed Metadata Storage (Low)
**Change:** Store feed-level attributes in separate metadata file.
```python
metadata = {
    "title": d.feed.title,
    "subtitle": d.feed.subtitle,
    "updated": d.feed.updated,
}
with open(os.path.join(p["path_data"], f"rss_{category}_meta.json"), 'w') as f:
    json.dump(metadata, f)
```
**Reason:** Enables richer UI (show feed descriptions) and diagnostics (detect dead feeds).

### 18. OPML Support (Low)
**Change:** Add import/export functions for OPML XML format.
```python
import xml.etree.ElementTree as ET

def export_opml(config, output_path):
    root = ET.Element('opml', version='2.0')
    body = ET.SubElement(root, 'body')
    for category, feeds in config.items():
        outline = ET.SubElement(body, 'outline', text=category)
        for name, url in feeds['feeds'].items():
            ET.SubElement(outline, 'outline', type='rss', text=name, xmlUrl=url)
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
```
**Reason:** Standard interchange format for RSS readers—enables migration from Feedly, NewsBlur, etc.

---

**Priority sequence:** Implement items 1-4 (Critical) immediately as they prevent data loss. Then 5-10 (High) for production readiness. Items 11-18 (Medium/Low) can be iterative enhancements based on user feedback.