# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Downloads and parses RSS/Atom feeds using the `feedparser` library
2. **Multi-source aggregation**: Processes multiple feed URLs organized by category from a JSON configuration file
3. **Time normalization**: Converts feed timestamps to a configurable timezone (default: UTC+9 KST Seoul)
4. **Smart date formatting**: Displays times as "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
5. **Deduplication**: Uses timestamp as unique ID to prevent duplicate entries within a single fetch
6. **JSON output**: Writes processed feeds to category-specific JSON files in `~/.rreader/`
7. **Configuration management**: 
   - Bundles default feeds with the package
   - Copies defaults to user directory on first run
   - Merges new categories from bundled config without overwriting user customizations
8. **Author display**: Supports per-category toggle for showing feed author vs. source name
9. **Sorted output**: Returns entries in reverse chronological order (newest first)
10. **Optional logging**: Can trace feed fetch progress to stdout

## Triage

### Critical (blocks production use)

1. **No error handling for individual feed failures**: One bad URL crashes the entire category fetch or silently continues with incomplete data
2. **No network timeout configuration**: Hung connections can block indefinitely
3. **No rate limiting**: Aggressive polling could get IP-banned by feed providers
4. **No data validation**: Malformed JSON files corrupt the entire system state
5. **No concurrent processing**: Fetches are sequential; 20 feeds = 20× the latency of one

### High (degrades reliability)

6. **No caching/conditional requests**: Re-downloads entire feeds even when unchanged (wastes bandwidth, violates feed etiquette)
7. **No feed health monitoring**: Dead feeds accumulate silently; user has no visibility
8. **Weak deduplication**: Timestamp collisions possible; no GUID/link-based fallback
9. **No entry limits**: Unbounded feed history could exhaust memory/disk
10. **Hardcoded file paths**: User directory fixed to `~/.rreader/`, not configurable

### Medium (limits functionality)

11. **No entry expiration**: Old entries never purge; JSON files grow indefinitely
12. **No incremental updates**: Always rewrites entire category file; no append/update
13. **Missing timezone fallback**: Entries without `published_parsed` or `updated_parsed` silently dropped
14. **No feed metadata persistence**: Fetch timestamps exist but feed title/description ignored
15. **No entry content extraction**: Only stores title/link; summaries/full text unavailable

### Low (polish issues)

16. **Inconsistent logging**: `log` parameter only controls stdout trace, no structured logging
17. **No version migration**: Config schema changes would break existing installations
18. **Generic exception catching**: `except:` blocks hide actual error types
19. **No CLI interface**: `do()` function not exposed as proper command-line tool
20. **Missing type hints**: Function signatures undocumented

## Plan

### Critical fixes

**1. Individual feed error isolation**
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            # ... existing fetch logic ...
        except feedparser.FeedParserError as e:
            errors.append({"source": source, "url": url, "error": str(e)})
            if log:
                sys.stderr.write(f"Failed to parse {url}: {e}\n")
            continue  # Process remaining feeds
        except Exception as e:
            errors.append({"source": source, "url": url, "error": str(e)})
            if log:
                sys.stderr.write(f"Unexpected error for {url}: {e}\n")
            continue
    
    rslt["errors"] = errors  # Include in output JSON
    rslt["fetched_at"] = int(time.time())
```

**2. Network timeout configuration**
```python
import socket

def do(target_category=None, log=False, timeout=10):
    socket.setdefaulttimeout(timeout)  # Global fallback
    
def get_feed_from_rss(...):
    d = feedparser.parse(url, request_headers={
        'User-Agent': 'rreader/1.0 (+https://github.com/yourorg/rreader)'
    })
```

**3. Rate limiting**
```python
import threading

class RateLimiter:
    def __init__(self, calls_per_second=2):
        self.delay = 1.0 / calls_per_second
        self.last_call = 0
        self.lock = threading.Lock()
    
    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_call
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_call = time.time()

limiter = RateLimiter(calls_per_second=2)

def get_feed_from_rss(...):
    for source, url in urls.items():
        limiter.wait()
        # ... fetch logic ...
```

**4. Data validation**
```python
import jsonschema

FEED_CONFIG_SCHEMA = {
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

def load_feeds_config():
    try:
        with open(FEEDS_FILE_NAME, "r") as fp:
            config = json.load(fp)
        jsonschema.validate(config, FEED_CONFIG_SCHEMA)
        return config
    except (json.JSONDecodeError, jsonschema.ValidationError) as e:
        sys.stderr.write(f"Invalid config: {e}\nRestoring from backup...\n")
        shutil.copyfile(bundled_feeds_file, FEEDS_FILE_NAME)
        return load_feeds_config()
```

**5. Concurrent processing**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    try:
        limiter.wait()
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url, request_headers={...})
        if log:
            sys.stdout.write(" - Done\n")
        return source, d, None
    except Exception as e:
        return source, None, str(e)

def get_feed_from_rss(category, urls, show_author=False, log=False, max_workers=5):
    rslt = {}
    errors = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {
            executor.submit(fetch_single_feed, src, url, log): src 
            for src, url in urls.items()
        }
        
        for future in as_completed(future_to_source):
            source, feed_data, error = future.result()
            if error:
                errors.append({"source": source, "error": error})
                continue
            # ... process feed_data ...
```

### High priority

**6. Conditional requests (ETag/Last-Modified)**
```python
CACHE_FILE = os.path.join(p["path_data"], "feed_cache.json")

def load_cache():
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def fetch_single_feed(source, url, log, cache):
    headers = {'User-Agent': 'rreader/1.0'}
    
    if url in cache:
        if 'etag' in cache[url]:
            headers['If-None-Match'] = cache[url]['etag']
        if 'modified' in cache[url]:
            headers['If-Modified-Since'] = cache[url]['modified']
    
    d = feedparser.parse(url, request_headers=headers)
    
    if d.status == 304:  # Not Modified
        return source, None, None  # Use cached data
    
    cache[url] = {}
    if hasattr(d, 'etag'):
        cache[url]['etag'] = d.etag
    if hasattr(d, 'modified'):
        cache[url]['modified'] = d.modified
    
    return source, d, None
```

**7. Feed health monitoring**
```python
def get_feed_from_rss(...):
    health = {
        "total": len(urls),
        "success": 0,
        "failed": 0,
        "last_checked": int(time.time())
    }
    
    # ... after processing all feeds ...
    health["success"] = len(rslt) - len(errors)
    health["failed"] = len(errors)
    
    rslt["health"] = health
```

**8. GUID-based deduplication**
```python
for feed in d.entries:
    entry_id = getattr(feed, 'id', None) or feed.link  # GUID fallback to URL
    
    if entry_id in rslt:
        continue  # Skip duplicate
    
    rslt[entry_id] = {
        "id": entry_id,
        "timestamp": ts,
        # ... rest of fields ...
    }
```

**9. Entry limits**
```python
MAX_ENTRIES_PER_CATEGORY = 500

def get_feed_from_rss(...):
    # ... after building rslt ...
    
    sorted_entries = sorted(rslt.items(), key=lambda x: x[1]["timestamp"], reverse=True)
    rslt = dict(sorted_entries[:MAX_ENTRIES_PER_CATEGORY])
```

**10. Configurable paths**
```python
# In config.py
import os

DATA_DIR = os.getenv("RREADER_DATA_DIR", str(Path.home()) + "/.rreader/")
MAX_ENTRIES = int(os.getenv("RREADER_MAX_ENTRIES", "500"))
FETCH_TIMEOUT = int(os.getenv("RREADER_TIMEOUT", "10"))
```

### Medium priority

**11. Entry expiration**
```python
RETENTION_DAYS = 30

def prune_old_entries(entries):
    cutoff = time.time() - (RETENTION_DAYS * 86400)
    return [e for e in entries if e["timestamp"] > cutoff]

# In get_feed_from_rss:
rslt["entries"] = prune_old_entries(rslt["entries"])
```

**12. Incremental updates**
```python
def merge_entries(old_file, new_entries):
    try:
        with open(old_file, "r") as f:
            old_data = json.load(f)
        old_entries = {e["id"]: e for e in old_data["entries"]}
    except FileNotFoundError:
        old_entries = {}
    
    # Merge, preferring new data for duplicates
    old_entries.update({e["id"]: e for e in new_entries})
    
    return list(old_entries.values())
```

**13. Timezone fallback**
```python
def extract_timestamp(feed):
    parsed_time = getattr(feed, 'published_parsed', None) or \
                  getattr(feed, 'updated_parsed', None)
    
    if not parsed_time:
        # Fallback: use current time with warning flag
        parsed_time = time.gmtime()
        missing_date = True
    else:
        missing_date = False
    
    return parsed_time, missing_date
```

**14. Feed metadata persistence**
```python
rslt["feed_metadata"] = {
    "title": getattr(d.feed, 'title', category),
    "description": getattr(d.feed, 'subtitle', ''),
    "link": getattr(d.feed, 'link', ''),
    "updated": getattr(d.feed, 'updated', '')
}
```

**15. Entry content extraction**
```python
entries = {
    "id": entry_id,
    "title": feed.title,
    "url": feed.link,
    "summary": getattr(feed, 'summary', '')[:500],  # Truncate
    "content": getattr(feed, 'content', [{}])[0].get('value', '')[:2000],
    # ... existing fields ...
}
```

### Low priority

**16. Structured logging**
```python
import logging

logger = logging.getLogger("rreader")

def do(target_category=None, log_level=logging.INFO):
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger.info(f"Fetching feeds for category: {target_category or 'all'}")
```

**17. Version migration**
```python
CONFIG_VERSION = 2

def migrate_config(config):
    version = config.get("_version", 1)
    
    if version < 2:
        # Example: rename "feeds" to "sources"
        for category in config.values():
            if "feeds" in category:
                category["sources"] = category.pop("feeds")
        config["_version"] = 2
    
    return config
```

**18. Specific exception handling**
```python
try:
    d = feedparser.parse(url)
except (feedparser.FeedParserError, ValueError) as e:
    logger.error(f"Parse error for {url}: {e}")
except (socket.timeout, urllib.error.URLError) as e:
    logger.error(f"Network error for {url}: {e}")
except Exception as e:
    logger.exception(f"Unexpected error for {url}")
```

**19. CLI interface**
```python
# New file: cli.py
import argparse

def main():
    parser = argparse.ArgumentParser(description="RSS feed reader")
    parser.add_argument("--category", help="Fetch specific category")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--config", help="Custom config path")
    
    args = parser.parse_args()
    
    if args.config:
        global FEEDS_FILE_NAME
        FEEDS_FILE_NAME = args.config
    
    do(target_category=args.category, log=args.verbose)

if __name__ == "__main__":
    main()
```

**20. Type hints**
```python
from typing import Dict, List, Optional, Tuple

def get_feed_from_rss(
    category: str,
    urls: Dict[str, str],
    show_author: bool = False,
    log: bool = False
) -> Dict[str, any]:
    ...

def fetch_single_feed(
    source: str,
    url: str,
    log: bool
) -> Tuple[str, Optional[feedparser.FeedParserDict], Optional[str]]:
    ...
```