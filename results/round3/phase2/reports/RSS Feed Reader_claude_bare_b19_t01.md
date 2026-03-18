# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS feeds from multiple sources
2. **Multi-source Aggregation**: Processes multiple RSS feeds organized by category from a JSON configuration file
3. **Timestamp Normalization**: Converts feed publication times to a configurable timezone (currently KST/UTC+9)
4. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
5. **Time Formatting**: Displays "HH:MM" for today's entries, "Mon DD, HH:MM" for older entries
6. **Persistence**: Stores parsed feeds as JSON files in `~/.rreader/` directory
7. **Configuration Management**: Copies bundled feeds.json on first run and merges new categories from updates
8. **Selective Processing**: Can target a single category or process all categories
9. **Author Display**: Supports optional author attribution per category via `show_author` flag
10. **Basic Logging**: Optional console output showing feed processing progress

## Triage

### Critical Gaps
1. **No Error Handling Granularity** - Single feed failure causes entire program exit; should isolate failures per-feed
2. **No Entry Content Storage** - Only stores title/link; doesn't preserve article summaries or content
3. **No Data Validation** - Missing feeds.json schema validation; malformed JSON will crash silently

### Important Gaps
4. **No Rate Limiting** - Sequential requests without delays could trigger rate limits or IP bans
5. **No Caching/Conditional Requests** - Always fetches full feeds; doesn't use ETags or Last-Modified headers
6. **No Feed Health Monitoring** - Doesn't track feed failures, timeouts, or stale feeds
7. **Unbounded Data Growth** - Old entries accumulate indefinitely; no cleanup or archival strategy
8. **Silent Import Failures** - Try/except on imports masks dependency issues in production

### Nice-to-Have Gaps
9. **No Concurrent Fetching** - Sequential processing is slow for many feeds
10. **Limited Logging Infrastructure** - Uses print statements instead of proper logging framework
11. **No Entry Update Detection** - Can't detect if an entry's content changed after initial fetch
12. **Hardcoded Timezone** - Timezone in config.py but not configurable per-user
13. **No Feed Discovery** - Can't auto-detect RSS feed URLs from website URLs
14. **No Output Format Options** - Only JSON output; no HTML, RSS, or other formats

## Plan

### 1. Error Handling Granularity
**Change**: Wrap individual feed processing in try/except within the loop
```python
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
        
        # Process entries...
    except Exception as e:
        if log:
            sys.stdout.write(f" - Failed: {e}\n")
        continue  # Continue with next feed instead of exiting
```

### 2. Entry Content Storage
**Change**: Extract and store `summary` and `content` fields
```python
entries = {
    "id": ts,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', ''),
    "content": getattr(feed, 'content', [{}])[0].get('value', '') if hasattr(feed, 'content') else ''
}
```

### 3. Data Validation
**Change**: Add JSON schema validation using `jsonschema` library
```python
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"}
            }
        }
    }
}

with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
    jsonschema.validate(RSS, FEEDS_SCHEMA)
```

### 4. Rate Limiting
**Change**: Add configurable delay between requests
```python
import time

RATE_LIMIT_DELAY = 1  # seconds between requests

for source, url in urls.items():
    time.sleep(RATE_LIMIT_DELAY)
    # ... existing fetch code
```

### 5. Caching/Conditional Requests
**Change**: Store and use ETags/Last-Modified headers
```python
# In get_feed_from_rss, before parsing:
cache_file = os.path.join(p["path_data"], f"cache_{category}_{source}.json")
headers = {}
if os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        cache = json.load(f)
        if 'etag' in cache:
            headers['If-None-Match'] = cache['etag']
        if 'modified' in cache:
            headers['If-Modified-Since'] = cache['modified']

d = feedparser.parse(url, etag=headers.get('If-None-Match'), 
                     modified=headers.get('If-Modified-Since'))

if d.status == 304:  # Not modified
    continue

# Save new etag/modified for next request
with open(cache_file, 'w') as f:
    json.dump({'etag': d.get('etag'), 'modified': d.get('modified')}, f)
```

### 6. Feed Health Monitoring
**Change**: Track feed metadata in separate health status file
```python
health = {
    "last_success": None,
    "last_failure": None,
    "consecutive_failures": 0,
    "total_entries": 0
}

# After successful fetch:
health["last_success"] = int(time.time())
health["consecutive_failures"] = 0
health["total_entries"] = len(d.entries)

# After failure:
health["last_failure"] = int(time.time())
health["consecutive_failures"] += 1

# Save to {category}_health.json
```

### 7. Unbounded Data Growth
**Change**: Implement retention policy with configurable max age
```python
MAX_ENTRY_AGE_DAYS = 30

def prune_old_entries(entries, max_age_days):
    cutoff = int(time.time()) - (max_age_days * 86400)
    return [e for e in entries if e["timestamp"] > cutoff]

rslt["entries"] = prune_old_entries(rslt["entries"], MAX_ENTRY_AGE_DAYS)
```

### 8. Silent Import Failures
**Change**: Make import handling explicit with helpful error messages
```python
# Remove try/except from imports
# Add dependency check at module level:
try:
    import feedparser
except ImportError:
    sys.exit("ERROR: feedparser not installed. Run: pip install feedparser")

# For relative imports, use absolute fallback explicitly:
try:
    from rreader.common import p, FEEDS_FILE_NAME
    from rreader.config import TIMEZONE
except ImportError:
    # Running as script
    from common import p, FEEDS_FILE_NAME
    from config import TIMEZONE
```

### 9. Concurrent Fetching
**Change**: Use `concurrent.futures.ThreadPoolExecutor` for parallel fetches
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    """Fetch a single feed, return (source, parsed_feed) or (source, None) on error"""
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
        return (source, d)
    except Exception as e:
        if log:
            sys.stdout.write(f" - Failed: {e}\n")
        return (source, None)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_single_feed, source, url, log): source 
                   for source, url in urls.items()}
        
        for future in as_completed(futures):
            source, d = future.result()
            if d is None:
                continue
            # Process entries as before...
```

### 10. Logging Infrastructure
**Change**: Replace print statements with Python logging module
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Replace sys.stdout.write with:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}: {e}")
```

### 11. Entry Update Detection
**Change**: Store content hash and detect changes
```python
import hashlib

def get_content_hash(feed):
    content = f"{feed.title}{getattr(feed, 'summary', '')}"
    return hashlib.md5(content.encode()).hexdigest()

# In entries dict:
entries["content_hash"] = get_content_hash(feed)

# When processing, check if hash changed for existing entry
```

### 12. User-Configurable Timezone
**Change**: Move timezone to user config file
```python
# In feeds.json add top-level config:
{
    "_config": {
        "timezone_offset_hours": 9
    },
    "category1": {...}
}

# In code:
config = RSS.get("_config", {})
tz_hours = config.get("timezone_offset_hours", 0)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_hours))
```

### 13. Feed Discovery
**Change**: Add helper function to discover feeds from HTML pages
```python
import requests
from bs4 import BeautifulSoup

def discover_feeds(url):
    """Find RSS/Atom feed links in HTML page"""
    try:
        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        feeds = []
        for link in soup.find_all('link', type=['application/rss+xml', 'application/atom+xml']):
            feeds.append(link.get('href'))
        return feeds
    except:
        return []
```

### 14. Output Format Options
**Change**: Add format parameter and rendering functions
```python
def render_html(data, category):
    """Render entries as HTML"""
    html = f"<h1>{category}</h1><ul>"
    for entry in data["entries"]:
        html += f'<li><a href="{entry["url"]}">{entry["title"]}</a> - {entry["pubDate"]}</li>'
    html += "</ul>"
    return html

def do(target_category=None, log=False, output_format="json"):
    # ... existing code ...
    
    if output_format == "html":
        html_output = render_html(rslt, category)
        with open(os.path.join(p["path_data"], f"rss_{category}.html"), "w") as f:
            f.write(html_output)
    else:
        # existing JSON output
```