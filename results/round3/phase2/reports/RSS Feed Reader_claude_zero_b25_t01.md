# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS feeds using `feedparser` library from multiple sources
2. **Multi-Category Support**: Organizes feeds into categories defined in a `feeds.json` configuration file
3. **Data Persistence**: Saves parsed feed entries to JSON files (one per category) in `~/.rreader/`
4. **Timestamp Handling**: Converts feed timestamps to a configurable timezone (currently hardcoded to UTC+9/KST)
5. **Deduplication**: Uses timestamp as ID to prevent duplicate entries within a single parse operation
6. **Date Formatting**: Shows time-only format for today's entries, full date for older entries
7. **Configuration Management**: 
   - Copies bundled default `feeds.json` on first run
   - Merges new categories from bundled config into user config on updates
8. **Flexible Author Display**: Supports per-category `show_author` flag to use feed author vs source name
9. **Selective Updates**: Can update a single category or all categories
10. **Import Flexibility**: Handles both package and standalone execution contexts

## Triage

### Critical Gaps (P0)
1. **No Error Recovery**: Parser fails completely on any feed error, potentially losing all data
2. **No Validation**: Missing JSON schema validation for config files
3. **Race Conditions**: No file locking for concurrent updates
4. **Uncaught Exceptions**: Bare `except:` clauses swallow all errors including KeyboardInterrupt

### High Priority (P1)
5. **No Logging Framework**: Uses print statements; no log levels, rotation, or persistence
6. **No Rate Limiting**: Could overwhelm feed servers or trigger rate limits
7. **No Caching Headers**: Ignores ETags/Last-Modified, wastes bandwidth
8. **Collision on Duplicate Timestamps**: Multiple entries at same second overwrite each other
9. **No Feed Health Monitoring**: No tracking of failed feeds or staleness
10. **Blocking I/O**: Sequential feed fetching is slow for many feeds

### Medium Priority (P2)
11. **No Configuration for TIMEZONE**: Hardcoded in config.py
12. **No Entry Retention Policy**: Old entries accumulate forever
13. **No Network Timeouts**: Feeds can hang indefinitely
14. **No User Agent**: May be blocked by some servers
15. **No HTML Sanitization**: Feed titles/content could contain malicious HTML
16. **No Incremental Updates**: Re-fetches and re-processes all entries every time

### Low Priority (P3)
17. **No CLI Interface**: Limited command-line options for users
18. **No Feed Discovery**: Can't auto-detect feeds from website URLs
19. **No Export Functionality**: Can't export to OPML or other formats
20. **No Statistics/Analytics**: No feed activity metrics

## Plan

### P0 Fixes

**1. Error Recovery**
```python
# Replace the try/except in get_feed_from_rss:
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
    except Exception as e:
        if log:
            sys.stdout.write(f" - Failed: {e}\n")
        # Continue processing other feeds instead of sys.exit
        continue
    
    # Wrap entry parsing similarly:
    for feed in d.entries:
        try:
            # ... existing parsing logic ...
        except Exception as e:
            if log:
                sys.stderr.write(f"Error parsing entry from {source}: {e}\n")
            continue  # Skip this entry, continue with others
```

**2. Validation**
```python
# Add at top of do():
def validate_feeds_config(config):
    """Validate feeds.json structure"""
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    for category, data in config.items():
        if not isinstance(data, dict) or 'feeds' not in data:
            raise ValueError(f"Category {category} missing 'feeds' key")
        if not isinstance(data['feeds'], dict):
            raise ValueError(f"Category {category} 'feeds' must be a dict")
    return True

# After loading RSS:
validate_feeds_config(RSS)
```

**3. File Locking**
```python
import fcntl  # Add to imports

def atomic_write_json(filepath, data):
    """Write JSON with file locking"""
    temp_path = filepath + '.tmp'
    with open(temp_path, 'w', encoding='utf-8') as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    os.replace(temp_path, filepath)  # Atomic on POSIX

# Replace all json.dump() calls with atomic_write_json()
```

**4. Specific Exception Handling**
```python
# Replace bare except clauses:
except Exception as e:
    # Log the specific error
    if log:
        sys.stderr.write(f"Error: {type(e).__name__}: {e}\n")
    continue  # Or other appropriate recovery

# Never catch:
# - KeyboardInterrupt
# - SystemExit
# - GeneratorExit
```

### P1 Fixes

**5. Logging Framework**
```python
import logging
from logging.handlers import RotatingFileHandler

# Setup in do() or module init:
logger = logging.getLogger('rreader')
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(
    os.path.join(p["path_data"], "rreader.log"),
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
))
logger.addHandler(handler)

# Replace all sys.stdout.write/sys.stderr.write:
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse {url}: {e}")
```

**6. Rate Limiting**
```python
import time

# Add to get_feed_from_rss():
MIN_DELAY = 1.0  # seconds between requests
last_request_time = 0

for source, url in urls.items():
    # Rate limit
    elapsed = time.time() - last_request_time
    if elapsed < MIN_DELAY:
        time.sleep(MIN_DELAY - elapsed)
    
    # ... fetch feed ...
    last_request_time = time.time()
```

**7. Caching Headers**
```python
# Store feed metadata in separate file:
# ~/.rreader/feed_cache.json with structure:
# {url: {"etag": "...", "modified": "...", "last_fetch": timestamp}}

def get_feed_from_rss(category, urls, show_author=False, log=False):
    cache_file = os.path.join(p["path_data"], "feed_cache.json")
    cache = load_cache(cache_file)
    
    for source, url in urls.items():
        etag = cache.get(url, {}).get('etag')
        modified = cache.get(url, {}).get('modified')
        
        d = feedparser.parse(url, etag=etag, modified=modified)
        
        if d.status == 304:  # Not modified
            logger.info(f"{url} not modified, skipping")
            continue
        
        # Update cache
        cache[url] = {
            'etag': d.get('etag'),
            'modified': d.get('modified'),
            'last_fetch': time.time()
        }
        # ... rest of processing ...
    
    save_cache(cache_file, cache)
```

**8. Collision-Free IDs**
```python
# Change ID generation:
import hashlib

def generate_entry_id(feed, timestamp):
    """Generate unique ID from URL + timestamp"""
    key = f"{feed.link}:{timestamp}"
    return f"{timestamp}_{hashlib.md5(key.encode()).hexdigest()[:8]}"

# In entry parsing:
entry_id = generate_entry_id(feed, ts)
entries = {
    "id": entry_id,  # Use generated ID
    # ... rest of fields ...
}
rslt[entry_id] = entries
```

**9. Feed Health Monitoring**
```python
# Add to feed_cache.json structure:
# {"url": {"status": "ok"|"error", "error_count": 0, 
#          "last_success": timestamp, "last_error": timestamp}}

def update_feed_health(cache, url, success, error_msg=None):
    if url not in cache:
        cache[url] = {}
    
    if success:
        cache[url]['status'] = 'ok'
        cache[url]['error_count'] = 0
        cache[url]['last_success'] = time.time()
    else:
        cache[url]['status'] = 'error'
        cache[url]['error_count'] = cache[url].get('error_count', 0) + 1
        cache[url]['last_error'] = time.time()
        cache[url]['last_error_msg'] = error_msg

# Add health check command to report stale/failing feeds
```

**10. Async I/O**
```python
import asyncio
import aiohttp

async def fetch_feed_async(session, source, url):
    """Async feed fetching"""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            content = await response.text()
            return source, feedparser.parse(content)
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return source, None

async def get_feed_from_rss_async(category, urls, show_author=False):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_feed_async(session, src, url) for src, url in urls.items()]
        results = await asyncio.gather(*tasks)
    
    # Process results (rest of existing logic)
    for source, feed_data in results:
        if feed_data is None:
            continue
        # ... parse entries ...

# In do():
asyncio.run(get_feed_from_rss_async(...))
```

### P2 Fixes

**11. Configurable Timezone**
```python
# In feeds.json, add global settings:
{
    "_settings": {
        "timezone_offset_hours": 9,
        "max_age_days": 30
    },
    "tech": {"feeds": {...}},
    ...
}

# In config.py or do():
settings = RSS.get('_settings', {})
tz_offset = settings.get('timezone_offset_hours', 9)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```

**12. Retention Policy**
```python
def cleanup_old_entries(rslt, max_age_days=30):
    """Remove entries older than max_age_days"""
    cutoff = time.time() - (max_age_days * 86400)
    rslt['entries'] = [
        e for e in rslt['entries'] 
        if e['timestamp'] > cutoff
    ]
    return rslt

# Apply before saving
```

**13. Network Timeouts**
```python
# For feedparser (uses urllib internally):
import socket
socket.setdefaulttimeout(30)  # 30 second timeout

# Or pass directly if using requests/aiohttp (see #10)
```

**14. User Agent**
```python
# Add custom user agent to feedparser:
d = feedparser.parse(url, agent='rreader/1.0 (+https://github.com/yourrepo)')
```

**15. HTML Sanitization**
```python
import html
import re

def sanitize_text(text):
    """Remove HTML tags and decode entities"""
    text = re.sub(r'<[^>]+>', '', text)  # Strip tags
    text = html.unescape(text)  # Decode entities
    return text.strip()

# Apply to feed.title before storing
```

**16. Incremental Updates**
```python
def merge_entries(existing_entries, new_entries):
    """Merge new entries with existing, avoiding duplicates"""
    existing_ids = {e['id'] for e in existing_entries}
    merged = existing_entries + [
        e for e in new_entries if e['id'] not in existing_ids
    ]
    return sorted(merged, key=lambda x: x['timestamp'], reverse=True)

# Load existing JSON, merge, then save
```

### P3 Fixes

**17. CLI Interface**
```python
import argparse

# Add to if __name__ == "__main__":
parser = argparse.ArgumentParser(description='RSS Feed Aggregator')
parser.add_argument('--category', help='Update specific category')
parser.add_argument('--verbose', '-v', action='store_true')
parser.add_argument('--add-feed', nargs=3, metavar=('CATEGORY', 'NAME', 'URL'))
parser.add_argument('--list-categories', action='store_true')
args = parser.parse_args()

if args.list_categories:
    # ... list categories ...
elif args.add_feed:
    # ... add feed to config ...
else:
    do(target_category=args.category, log=args.verbose)
```

**18-20**: Implement as separate feature modules with dedicated functions for feed discovery (OPML parsing, auto-detection), export (OPML generation), and analytics (SQLite for metrics tracking).