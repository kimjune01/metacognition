# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides a working RSS feed aggregator with the following capabilities:

1. **Feed parsing and aggregation**: Downloads and parses RSS feeds from multiple sources using `feedparser`
2. **Multi-category organization**: Supports grouping feeds by category (e.g., "tech", "news")
3. **Time normalization**: Converts all timestamps to a configurable timezone (currently KST/UTC+9)
4. **Intelligent date display**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older entries
5. **Deduplication by timestamp**: Uses Unix timestamp as unique ID to prevent duplicate entries
6. **Persistence**: Caches parsed results as JSON files in `~/.rreader/`
7. **Feed configuration management**: 
   - Bundles default feeds with the package
   - Copies to user directory on first run
   - Automatically merges new categories from updates without overwriting user customizations
8. **Author attribution**: Optional per-category setting to show individual authors vs. source name
9. **Selective refresh**: Can update a single category or all categories
10. **Logging capability**: Optional verbose output during fetch operations

## Triage

### Critical (blocks production use)

1. **No error recovery**: Single feed failure crashes entire category update
2. **No rate limiting**: Could trigger 429 responses or IP bans from feed providers
3. **No timeout handling**: Slow/dead feeds block indefinitely
4. **No data validation**: Malformed feeds silently corrupt output
5. **Unbounded memory growth**: `rslt` dict holds all entries in memory before writing

### High priority (impacts reliability)

6. **No stale data detection**: No way to know if cached data is days old
7. **No HTTP caching**: Ignores ETags/Last-Modified, wastes bandwidth
8. **No concurrent fetching**: Sequential processing makes updates slow
9. **Missing feed metadata**: No tracking of last successful fetch, error counts, or feed health
10. **No retry logic**: Transient network failures are treated as permanent

### Medium priority (quality of life)

11. **Poor logging**: Stdout prints mix with data, no log levels, no persistence
12. **No entry limits**: A prolific feed can dominate the output
13. **No content sanitization**: HTML/script tags in titles could cause issues downstream
14. **Hardcoded timezone**: TIMEZONE in config.py but no runtime override
15. **No feed discovery**: Must manually edit JSON to add feeds

### Low priority (nice to have)

16. **No feed validation on add**: Can add broken URLs to feeds.json
17. **No OPML import/export**: Standard format for feed lists not supported
18. **No entry filtering**: No way to exclude entries by keyword/regex
19. **No sorting options**: Only reverse chronological, no by-source or by-category
20. **No entry read tracking**: Can't mark entries as read/unread

## Plan

### Critical fixes

**1. Error recovery per feed**
```python
# In get_feed_from_rss(), wrap feed processing:
for source, url in urls.items():
    try:
        # existing fetch logic
    except Exception as e:
        if log:
            sys.stderr.write(f"✗ {source}: {str(e)}\n")
        continue  # Don't crash, move to next feed
```

**2. Add timeouts and rate limiting**
```python
import requests
from time import sleep

# At module level:
SESSION = requests.Session()
SESSION.headers.update({'User-Agent': 'rreader/1.0'})

# Replace feedparser.parse(url) with:
response = SESSION.get(url, timeout=10)
response.raise_for_status()
d = feedparser.parse(response.content)
sleep(0.5)  # 500ms between requests
```

**3. Validate feed data before processing**
```python
# After parsing:
if not d.entries:
    raise ValueError(f"No entries in feed: {url}")
if d.bozo and d.bozo_exception:
    raise d.bozo_exception
```

**4. Stream writing to limit memory**
```python
# Instead of building rslt dict, write incrementally:
seen_ids = set()
with open(output_path, 'w') as f:
    f.write('{"entries": [')
    first = True
    for feed in sorted_feeds:
        if feed['id'] not in seen_ids:
            if not first:
                f.write(',')
            json.dump(feed, f)
            seen_ids.add(feed['id'])
            first = False
    f.write('], "created_at": %d}' % int(time.time()))
```

**5. Enforce entry limits per category**
```python
# In feeds.json schema, add:
{"tech": {"feeds": {...}, "max_entries": 100}}

# In get_feed_from_rss():
max_entries = RSS[category].get("max_entries", 200)
rslt = rslt[:max_entries]  # Trim after sorting
```

### High priority improvements

**6. Add staleness indicators**
```python
# In output JSON:
"metadata": {
    "created_at": 1234567890,
    "oldest_entry": 1234560000,
    "newest_entry": 1234567880,
    "feed_count": 5,
    "entry_count": 42
}

# Check age before returning cached data:
if time.time() - cached['created_at'] > 3600:  # 1 hour
    sys.stderr.write(f"Warning: {category} cache is stale\n")
```

**7. Implement HTTP caching**
```python
# Store ETags/Last-Modified in feed metadata:
feed_meta = {
    "url": url,
    "etag": response.headers.get('ETag'),
    "last_modified": response.headers.get('Last-Modified'),
    "last_fetch": time.time()
}

# On subsequent fetches:
headers = {}
if meta.get('etag'):
    headers['If-None-Match'] = meta['etag']
response = SESSION.get(url, headers=headers, timeout=10)
if response.status_code == 304:
    return cached_data  # Not modified
```

**8. Concurrent fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_one_feed(source, url):
    # Extract per-feed logic here
    return source, entries

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_one_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source, entries = future.result()
        rslt.update(entries)
```

**9. Track feed health metrics**
```python
# New file: ~/.rreader/feed_health.json
{
    "https://example.com/rss": {
        "last_success": 1234567890,
        "last_failure": null,
        "consecutive_failures": 0,
        "avg_latency_ms": 250,
        "entry_count_history": [45, 43, 47]  # Last 3 fetches
    }
}

# Update after each fetch:
health[url]['last_success'] = time.time()
health[url]['consecutive_failures'] = 0
# On failure:
health[url]['consecutive_failures'] += 1
if health[url]['consecutive_failures'] > 5:
    sys.stderr.write(f"Feed may be dead: {url}\n")
```

**10. Exponential backoff retry**
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_with_retry(url):
    response = SESSION.get(url, timeout=10)
    response.raise_for_status()
    return response
```

### Medium priority enhancements

**11. Structured logging**
```python
import logging

# Setup:
logging.basicConfig(
    filename=os.path.join(p['path_data'], 'rreader.log'),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)
logger = logging.getLogger(__name__)

# Replace sys.stdout.write:
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse {url}: {e}")
```

**12. Entry limits per feed and category**
```python
# Already addressed in item #5
```

**13. Sanitize entry content**
```python
import html
import re

def sanitize_text(text):
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)  # Strip tags
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text[:500]  # Enforce max length

entries['title'] = sanitize_text(feed.title)
```

**14. Runtime timezone override**
```python
# Add to do() function signature:
def do(target_category=None, log=False, timezone=None):
    tz = timezone or TIMEZONE
    at = datetime.datetime(*parsed_time[:6]) \
           .replace(tzinfo=datetime.timezone.utc) \
           .astimezone(tz)
```

**15. Feed discovery helper**
```python
def discover_feeds(url):
    """Find RSS/Atom feeds linked from a webpage"""
    import requests
    from bs4 import BeautifulSoup
    
    r = requests.get(url, timeout=10)
    soup = BeautifulSoup(r.content, 'html.parser')
    feeds = []
    for link in soup.find_all('link', type=['application/rss+xml', 
                                              'application/atom+xml']):
        feeds.append({
            'url': link.get('href'),
            'title': link.get('title', 'Untitled')
        })
    return feeds
```

### Low priority additions

**16-20**: These would require significant new features (OPML parser, UI for marking read state, etc.) and should be deferred until the critical and high-priority issues are resolved. Document as future enhancements in a roadmap file.