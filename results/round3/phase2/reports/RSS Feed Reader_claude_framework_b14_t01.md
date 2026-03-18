# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Fetches and parses RSS feeds from multiple sources using `feedparser`
2. **Multi-category support**: Organizes feeds into categories defined in a JSON configuration file
3. **Bundled defaults**: Ships with default feeds that are copied on first run
4. **Graceful configuration merging**: When new categories appear in bundled feeds, they're automatically added to user config
5. **Timestamp normalization**: Converts feed timestamps to a configured timezone (currently KST/UTC+9)
6. **Human-readable dates**: Formats timestamps as "HH:MM" for today's items, "MMM DD, HH:MM" for older items
7. **Deduplication by timestamp**: Uses Unix timestamp as unique ID to prevent duplicate entries
8. **Author attribution**: Supports optional per-category author display
9. **JSON output**: Writes aggregated feeds to `~/.rreader/rss_{category}.json` files
10. **Batch and single-category modes**: Can refresh all feeds or target one category

## Triage

### Critical (blocks production use)

1. **Silent failure on malformed feeds**: Try-except blocks swallow errors without logging what failed or why
2. **No error recovery**: One bad URL in a category kills the entire category fetch
3. **No rate limiting**: Hammers all feeds simultaneously, risks IP bans from providers
4. **Missing feed validation**: Accepts any URL without checking if it's actually RSS/Atom
5. **No timeout handling**: Network hangs will block indefinitely
6. **Credential exposure risk**: If feeds.json supports authenticated feeds, passwords would be in plaintext

### High (needed for reliability)

7. **No stale data handling**: Cached feed files have no expiration; users can't tell if data is hours or weeks old
8. **Missing HTTP caching**: Ignores ETags and Last-Modified headers, wastes bandwidth
9. **No concurrent fetching**: Sequential processing makes refresh times linear with feed count
10. **Memory inefficient**: Loads entire feed history into RAM before deduplication
11. **No user feedback**: Long-running fetches provide no progress indication
12. **Hardcoded paths**: `~/.rreader/` can't be overridden for testing or multi-user systems

### Medium (quality of life)

13. **No feed health monitoring**: Doesn't track which feeds consistently fail or go stale
14. **Missing OPML import/export**: Can't easily migrate feed lists
15. **No entry limit**: Categories with prolific feeds will grow JSON files unbounded
16. **Timezone not configurable per-user**: Hardcoded to KST
17. **No filtering/search**: Can't exclude keywords or filter by date range
18. **Title/description truncation missing**: Long titles break UI layouts

### Low (nice to have)

19. **No feed discovery**: Can't auto-detect RSS links from website URLs
20. **Missing analytics**: No stats on feed volume, update frequency
21. **No notification system**: Can't alert on new entries matching criteria
22. **Duplicate detection only by timestamp**: Doesn't catch near-duplicates with different publish times

## Plan

### Critical Fixes

**1. Implement structured logging**
```python
import logging

logger = logging.getLogger(__name__)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    failed_feeds = []
    for source, url in urls.items():
        try:
            d = feedparser.parse(url)
            if d.bozo:  # feedparser's error flag
                logger.warning(f"Malformed feed {source}: {d.bozo_exception}")
                failed_feeds.append((source, str(d.bozo_exception)))
        except Exception as e:
            logger.error(f"Failed to fetch {source} ({url}): {e}")
            failed_feeds.append((source, str(e)))
            continue  # Don't kill entire category
    
    # Include failed_feeds in output JSON for UI display
```

**2. Add per-feed timeout and retry**
```python
import requests
from requests.adapters import HTTPAdapter, Retry

session = requests.Session()
retry_strategy = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)

# In get_feed_from_rss:
response = session.get(url, timeout=10)
d = feedparser.parse(response.content)
```

**3. Validate feed URLs before parsing**
```python
def validate_feed_url(url):
    """Check if URL returns RSS/Atom content"""
    try:
        response = session.head(url, timeout=5, allow_redirects=True)
        content_type = response.headers.get('content-type', '')
        valid_types = ['application/rss+xml', 'application/atom+xml', 
                       'application/xml', 'text/xml']
        return any(t in content_type.lower() for t in valid_types)
    except:
        return False  # Be permissive, some servers don't support HEAD
```

**4. Implement rate limiting**
```python
import time
from collections import defaultdict

last_fetch_time = defaultdict(float)
MIN_FETCH_INTERVAL = 60  # seconds between fetches per domain

def rate_limited_fetch(url):
    domain = urlparse(url).netloc
    elapsed = time.time() - last_fetch_time[domain]
    if elapsed < MIN_FETCH_INTERVAL:
        time.sleep(MIN_FETCH_INTERVAL - elapsed)
    last_fetch_time[domain] = time.time()
    return session.get(url, timeout=10)
```

**5. Secure credential handling**
```python
# In feeds.json schema, support:
{
  "feeds": {
    "Source Name": {
      "url": "https://example.com/feed",
      "auth": {
        "type": "basic",  # or "bearer"
        "username_env": "RSS_USERNAME",  # read from env var
        "password_env": "RSS_PASSWORD"
      }
    }
  }
}

# In code:
auth = feed_config.get('auth')
if auth:
    username = os.getenv(auth['username_env'])
    password = os.getenv(auth['password_env'])
    session.auth = (username, password)
```

### High Priority Improvements

**6. Add staleness metadata**
```python
# In output JSON:
{
    "entries": [...],
    "created_at": 1234567890,
    "feed_metadata": {
        "source_name": {
            "last_fetch": 1234567890,
            "last_modified": "Wed, 01 Jan 2025 12:00:00 GMT",
            "etag": "abc123",
            "status": "ok"  # or "stale", "error"
        }
    }
}
```

**7. Implement HTTP caching**
```python
import requests_cache

# Cache responses for 1 hour
session = requests_cache.CachedSession(
    cache_name='rreader_cache',
    expire_after=3600,
    allowable_codes=[200],
    stale_if_error=True
)
```

**8. Concurrent fetching with thread pool**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_feed_from_rss(category, urls, show_author=False, log=False):
    results = {}
    failed_feeds = []
    
    def fetch_single(source, url):
        try:
            d = rate_limited_fetch(url)
            return source, feedparser.parse(d.content), None
        except Exception as e:
            return source, None, str(e)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_single, s, u): (s, u) 
                   for s, u in urls.items()}
        
        for future in as_completed(futures):
            source, feed, error = future.result()
            if error:
                failed_feeds.append((source, error))
            else:
                # Process feed entries...
```

**9. Limit entries per category**
```python
MAX_ENTRIES_PER_CATEGORY = 500

rslt = [val for key, val in sorted(rslt.items(), reverse=True)[:MAX_ENTRIES_PER_CATEGORY]]
```

**10. Make paths configurable**
```python
# In config.py:
DATA_DIR = os.getenv('RREADER_DATA_DIR', str(Path.home()) + "/.rreader/")

# Support XDG Base Directory spec on Linux:
if sys.platform == 'linux':
    DATA_DIR = os.getenv('XDG_DATA_HOME', str(Path.home()) + "/.local/share") + "/rreader/"
```

### Medium Priority Enhancements

**11. Add feed health tracking**
```python
# Maintain in separate health.json:
{
    "category_name": {
        "source_name": {
            "last_success": 1234567890,
            "consecutive_failures": 0,
            "avg_entry_count": 15,
            "avg_update_frequency": 3600  # seconds
        }
    }
}
```

**12. OPML support**
```python
import xml.etree.ElementTree as ET

def export_to_opml(feeds_dict, output_path):
    opml = ET.Element('opml', version='2.0')
    body = ET.SubElement(opml, 'body')
    
    for category, data in feeds_dict.items():
        outline = ET.SubElement(body, 'outline', text=category, title=category)
        for source, url in data['feeds'].items():
            ET.SubElement(outline, 'outline', 
                         type='rss', text=source, 
                         title=source, xmlUrl=url)
    
    tree = ET.ElementTree(opml)
    tree.write(output_path, encoding='utf-8', xml_declaration=True)
```

**13. Configurable timezone per user**
```python
# In feeds.json or separate settings.json:
{
    "timezone": "America/New_York"  # or "UTC+9"
}

# In code:
import pytz
user_tz = pytz.timezone(config.get('timezone', 'UTC'))
```

**14. Title truncation with smart ellipsis**
```python
def truncate_smart(text, max_length=100):
    """Truncate at word boundary"""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length].rsplit(' ', 1)[0]
    return truncated + '…'
```

This plan addresses the gaps in order of impact on production readiness. The critical fixes prevent data loss and service disruption. High priority improvements make the system reliable at scale. Medium priority enhancements improve maintainability and user experience.