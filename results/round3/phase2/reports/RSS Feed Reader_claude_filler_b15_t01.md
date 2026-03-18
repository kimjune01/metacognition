# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from configured URLs
2. **Multi-Source Aggregation**: Processes multiple feeds grouped by category, combining entries from different sources
3. **Time Handling**: Converts feed timestamps to a configurable timezone (KST/UTC+9) with smart date formatting (shows time for today's entries, date+time for older ones)
4. **Deduplication**: Uses timestamp-based keys to prevent duplicate entries from the same feed
5. **Data Persistence**: Saves aggregated feeds as JSON files (`rss_{category}.json`) with metadata including creation timestamp
6. **Configuration Management**: 
   - Loads feed definitions from `feeds.json`
   - Copies bundled default feeds on first run
   - Merges new categories from bundled config into user config on updates
7. **Selective Updates**: Can update a single category or all categories
8. **Optional Logging**: Progress output for debugging feed retrieval
9. **Author Display**: Configurable per-category author/source attribution

## Triage

### Critical Gaps (P0 - Blocks Production Use)

1. **No Error Recovery**: Feed failures cause complete program termination (`sys.exit(0)`)
2. **No Rate Limiting**: Could overwhelm feed servers or get IP-banned
3. **No Data Validation**: Malformed feed data could corrupt the JSON output
4. **Silent Failures**: Empty `except` blocks hide all errors except when logging is enabled

### High Priority (P1 - Severely Limits Usability)

5. **No Caching/Conditional Requests**: Re-downloads entire feeds every time (wasteful bandwidth, slow)
6. **No Entry Content**: Only stores title/link, not article summaries or content
7. **No Feed Metadata Storage**: Feed title, description, update frequency not captured
8. **Collision-Prone ID Strategy**: Using Unix timestamp as ID will collide if feeds publish multiple articles in the same second
9. **No Concurrency**: Sequential feed fetching is slow for many feeds

### Medium Priority (P2 - Quality of Life)

10. **No User Feedback**: Silent operation unless `log=True` (user doesn't know if it's working)
11. **No Staleness Detection**: No way to know if feeds are down or outdated
12. **Fixed Timezone**: Hardcoded to UTC+9, should be configurable
13. **No Feed Validation**: Accepts any URL, will fail silently on non-feed URLs
14. **No Entry Limit**: Could create enormous JSON files for prolific feeds
15. **No OPML Import/Export**: Manual JSON editing required for feed management

### Low Priority (P3 - Nice to Have)

16. **No Database Backend**: JSON files don't scale, no query capabilities
17. **No Read/Unread Tracking**: Can't mark articles as read
18. **No Filtering/Tagging**: No way to organize entries beyond categories
19. **No Update Scheduling**: Requires external cron/scheduler
20. **No Web Interface**: Command-line only

## Plan

### P0 Fixes

**1. Error Recovery**
```python
# In get_feed_from_rss(), replace:
except:
    sys.exit(" - Failed\n" if log else 0)

# With:
except Exception as e:
    if log:
        sys.stderr.write(f" - Failed: {str(e)}\n")
    continue  # Skip this feed, continue with others

# Add error tracking:
errors = []
# ... in except block:
errors.append({"source": source, "url": url, "error": str(e)})
# ... at end:
rslt["errors"] = errors
```

**2. Rate Limiting**
```python
import time

# Add to get_feed_from_rss():
RATE_LIMIT_DELAY = 1.0  # seconds between requests

for source, url in urls.items():
    time.sleep(RATE_LIMIT_DELAY)
    # ... existing code
```

**3. Data Validation**
```python
# After feedparser.parse():
if not d.entries:
    if log:
        sys.stderr.write(" - No entries found\n")
    continue

# For each feed entry, validate required fields:
if not hasattr(feed, 'link') or not hasattr(feed, 'title'):
    continue

# Sanitize title to prevent JSON issues:
title = feed.title.strip().replace('\x00', '')
```

**4. Specific Exception Handling**
```python
# Replace bare except blocks with:
except (urllib.error.URLError, socket.timeout) as e:
    # Network errors
except xml.parsers.expat.ExpatError as e:
    # Feed parsing errors
except Exception as e:
    # Unexpected errors - log with full traceback
    import traceback
    if log:
        sys.stderr.write(f"\n{traceback.format_exc()}")
```

### P1 Fixes

**5. Caching with ETags/Last-Modified**
```python
# Add cache storage in get_feed_from_rss():
cache_file = os.path.join(p["path_data"], f"cache_{category}.json")
cache = {}
if os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        cache = json.load(f)

# Pass headers to feedparser:
headers = {}
if url in cache:
    if 'etag' in cache[url]:
        headers['If-None-Match'] = cache[url]['etag']
    if 'modified' in cache[url]:
        headers['If-Modified-Since'] = cache[url]['modified']

d = feedparser.parse(url, etag=headers.get('If-None-Match'), 
                     modified=headers.get('If-Modified-Since'))

# Update cache:
cache[url] = {
    'etag': getattr(d, 'etag', None),
    'modified': getattr(d, 'modified', None)
}
```

**6. Store Entry Content**
```python
# In entries dict, add:
"summary": getattr(feed, 'summary', ''),
"content": feed.content[0].value if hasattr(feed, 'content') and feed.content else '',
```

**7. Store Feed Metadata**
```python
# Add to rslt before writing:
rslt["feed_info"] = {
    "title": getattr(d.feed, 'title', category),
    "description": getattr(d.feed, 'subtitle', ''),
    "link": getattr(d.feed, 'link', ''),
    "updated": getattr(d.feed, 'updated', '')
}
```

**8. Better ID Generation**
```python
import hashlib

# Replace:
entries = {"id": ts, ...}

# With:
unique_key = f"{feed.link}{ts}"
entry_id = hashlib.md5(unique_key.encode()).hexdigest()
entries = {"id": entry_id, "timestamp": ts, ...}
```

**9. Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    """Fetch a single feed, return (source, parsed_data, error)"""
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
        return (source, d, None)
    except Exception as e:
        return (source, None, str(e))

# In get_feed_from_rss():
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, src, url, log): (src, url) 
               for src, url in urls.items()}
    
    for future in as_completed(futures):
        source, d, error = future.result()
        if error:
            # handle error
            continue
        # process d.entries as before
```

### P2 Fixes

**10. Progress Indicators**
```python
# Add tqdm for progress bars:
from tqdm import tqdm

for source, url in tqdm(urls.items(), desc=f"Fetching {category}", 
                        disable=not log):
    # existing code
```

**11. Staleness Detection**
```python
# In rslt, add per-feed metadata:
"feed_status": {
    source: {
        "last_successful_fetch": int(time.time()),
        "entry_count": len([e for e in rslt["entries"] if e["sourceName"] == source]),
        "status": "ok" if d.entries else "empty"
    }
    for source in urls.keys()
}
```

**12. Configurable Timezone**
```python
# In config.py, change to:
import os
TIMEZONE_OFFSET = int(os.getenv('RREADER_TZ_OFFSET', '9'))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET))
```

**13. Feed URL Validation**
```python
def validate_feed_url(url):
    """Check if URL looks like a feed"""
    if not url.startswith(('http://', 'https://')):
        return False
    # Try to fetch and check content-type
    try:
        response = urllib.request.urlopen(url, timeout=5)
        content_type = response.headers.get('Content-Type', '')
        return any(t in content_type for t in ['xml', 'rss', 'atom', 'feed'])
    except:
        return False

# Use in do() before processing:
urls = {s: u for s, u in RSS[category]["feeds"].items() 
        if validate_feed_url(u)}
```

**14. Entry Limits**
```python
# In feeds.json, add per-category config:
{
    "category": {
        "feeds": {...},
        "max_entries": 100  # limit per category
    }
}

# In get_feed_from_rss():
max_entries = d.get('max_entries', 500)
rslt["entries"] = rslt["entries"][:max_entries]
```

**15. OPML Support**
```python
import xml.etree.ElementTree as ET

def import_opml(opml_file, category_name):
    """Import feeds from OPML file"""
    tree = ET.parse(opml_file)
    root = tree.getroot()
    feeds = {}
    
    for outline in root.findall('.//outline[@type="rss"]'):
        title = outline.get('title') or outline.get('text')
        url = outline.get('xmlUrl')
        if title and url:
            feeds[title] = url
    
    # Merge into feeds.json
    with open(FEEDS_FILE_NAME, 'r') as f:
        current = json.load(f)
    
    current[category_name] = {
        "feeds": feeds,
        "show_author": True
    }
    
    with open(FEEDS_FILE_NAME, 'w') as f:
        json.dump(current, f, indent=4, ensure_ascii=False)
```