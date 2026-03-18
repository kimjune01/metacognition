# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS/Atom feeds using the `feedparser` library from multiple sources organized by categories.

2. **Data Extraction**: Extracts key metadata from feed entries:
   - Publication/update timestamps
   - Article titles and URLs
   - Source/author names
   - Formatted publication dates

3. **Timezone Handling**: Converts UTC timestamps to a configured timezone (currently hardcoded to KST/UTC+9) with intelligent date formatting (shows time-only for today's articles, includes date for older ones).

4. **JSON Storage**: Persists parsed feed data to JSON files named `rss_{category}.json` in a `.rreader` directory in the user's home folder.

5. **Feed Configuration**: Uses a `feeds.json` configuration file that:
   - Organizes feeds by category
   - Supports per-category author display preferences
   - Auto-merges bundled default feeds with user customizations

6. **Deduplication**: Uses timestamp-based deduplication within each fetch operation (entries with identical timestamps overwrite each other).

7. **Sorting**: Orders entries by timestamp in reverse chronological order.

8. **Command-line Interface**: Supports optional category-specific updates via `target_category` parameter and logging via `log` parameter.

## Triage

### Critical Gaps (Production Blockers)

1. **No Error Handling for Network Failures**: Individual feed failures silently exit the entire program (`sys.exit(0)`), causing all subsequent feeds to be skipped.

2. **No Rate Limiting**: Could overwhelm RSS servers or trigger rate limits when fetching many feeds.

3. **No Timeout Configuration**: Feed parsing can hang indefinitely on slow/unresponsive servers.

4. **Missing Configuration Validation**: No validation of feed URLs, category names, or JSON structure.

5. **Hardcoded Timezone**: The timezone is hardcoded rather than configurable per-user.

### High Priority (Functionality Gaps)

6. **No Incremental Updates**: Fetches all entries on every run rather than tracking what's already been seen.

7. **No Feed Metadata**: Doesn't store feed-level information (description, last-updated, etc.).

8. **Primitive Deduplication**: Uses only timestamps; doesn't handle duplicate content with different timestamps or missing IDs.

9. **No Retry Logic**: Failed fetches aren't retried, even for transient errors.

10. **Missing Logging Framework**: Uses print statements rather than proper logging infrastructure.

11. **No User Feedback for Long Operations**: No progress indication during multi-feed fetches.

### Medium Priority (Quality-of-Life)

12. **No Feed Health Monitoring**: Doesn't track which feeds are consistently failing or outdated.

13. **No Content Caching**: Re-downloads feeds even if unchanged (no ETag/Last-Modified support).

14. **Limited CLI**: No commands for listing categories, adding/removing feeds, or viewing statistics.

15. **No Concurrency**: Fetches feeds sequentially, which is slow for many feeds.

16. **Missing Data Migration**: No version tracking or migration support for schema changes.

17. **No Feed Discovery**: Can't auto-detect RSS feeds from website URLs.

### Low Priority (Nice-to-Have)

18. **No Content Filtering**: Can't filter by keywords, date ranges, or read/unread status.

19. **No Export Functionality**: Can't export to OPML or other standard formats.

20. **No Statistics**: Doesn't track fetch success rates, article counts, or trends.

## Plan

### 1. Network Error Handling (Critical)

**Problem**: `sys.exit(0)` on parse failures terminates the entire program.

**Changes**:
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            d = feedparser.parse(url)
            if log:
                sys.stdout.write(" - Done\n")
        except Exception as e:
            error_msg = f"Failed to fetch {source}: {str(e)}"
            errors.append(error_msg)
            if log:
                sys.stderr.write(f" - {error_msg}\n")
            continue  # Continue with next feed
        
        # Check for bozo exception (malformed feed)
        if hasattr(d, 'bozo') and d.bozo and not d.entries:
            errors.append(f"Malformed feed {source}: {d.bozo_exception}")
            continue
            
        # Rest of processing...
    
    # Store errors in output
    rslt = {
        "entries": [val for key, val in sorted(rslt.items(), reverse=True)],
        "created_at": int(time.time()),
        "errors": errors
    }
```

### 2. Rate Limiting (Critical)

**Problem**: No delays between requests.

**Changes**:
- Add `time.sleep()` between feed fetches
- Make delay configurable per-category in `feeds.json`

```python
# In feeds.json structure:
{
    "category_name": {
        "feeds": {...},
        "fetch_delay": 0.5  # seconds between feeds
    }
}

# In code:
for source, url in urls.items():
    if source != list(urls.keys())[0]:  # Skip delay for first feed
        time.sleep(d.get("fetch_delay", 0.5))
    # ... fetch logic
```

### 3. Timeout Configuration (Critical)

**Problem**: Feeds can hang indefinitely.

**Changes**:
```python
import socket

# At module level, before feedparser.parse calls:
DEFAULT_TIMEOUT = 30  # seconds

# Wrap parse calls:
def parse_with_timeout(url, timeout=DEFAULT_TIMEOUT):
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        return feedparser.parse(url)
    finally:
        socket.setdefaulttimeout(old_timeout)

# Or use feedparser's agent parameter with requests:
import requests
response = requests.get(url, timeout=30)
d = feedparser.parse(response.content)
```

### 4. Configuration Validation (Critical)

**Problem**: Invalid JSON or URLs cause cryptic failures.

**Changes**:
```python
import jsonschema
from urllib.parse import urlparse

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {
                        ".*": {"type": "string", "format": "uri"}
                    }
                },
                "show_author": {"type": "boolean"}
            }
        }
    }
}

def validate_feeds_config(config):
    try:
        jsonschema.validate(config, FEEDS_SCHEMA)
    except jsonschema.ValidationError as e:
        raise ValueError(f"Invalid feeds.json: {e.message}")
    
    # Additional URL validation
    for cat, data in config.items():
        for source, url in data["feeds"].items():
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                raise ValueError(f"Invalid URL for {source} in {cat}: {url}")
```

### 5. Configurable Timezone (Critical)

**Problem**: Timezone hardcoded to KST.

**Changes**:
```python
# In config.py or user settings:
import os
import datetime

def get_user_timezone():
    # Try environment variable first
    tz_str = os.environ.get('RREADER_TIMEZONE', 'UTC+9')
    
    # Parse format like "UTC+9" or "UTC-5"
    if tz_str.startswith('UTC'):
        sign = 1 if '+' in tz_str else -1
        hours = int(tz_str.split('+' if sign == 1 else '-')[1])
        return datetime.timezone(datetime.timedelta(hours=sign * hours))
    
    # Default fallback
    return datetime.timezone.utc

TIMEZONE = get_user_timezone()
```

### 6. Incremental Updates (High Priority)

**Problem**: Re-processes all entries every time.

**Changes**:
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    # Load existing entries
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    existing_ids = set()
    
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            existing_ids = {entry['id'] for entry in cached.get('entries', [])}
    
    new_entries = {}
    
    for feed in d.entries:
        # ... existing parsing logic ...
        
        entry_id = f"{source}:{feed.get('id', ts)}"  # Better ID
        
        if entry_id not in existing_ids:
            new_entries[ts] = entries
    
    # Merge with existing, keeping recent N entries
    MAX_ENTRIES = 1000
    all_entries = cached.get('entries', []) + list(new_entries.values())
    all_entries.sort(key=lambda x: x['timestamp'], reverse=True)
    all_entries = all_entries[:MAX_ENTRIES]
```

### 7. Proper Logging (High Priority)

**Problem**: Uses print statements and sys.stdout.write.

**Changes**:
```python
import logging

# Setup in __main__ or module init:
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p["path_data"], 'rreader.log')),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger('rreader')

# Replace all sys.stdout.write/print:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {source}: {e}")
logger.debug(f"Parsed {len(d.entries)} entries from {source}")
```

### 8. Better Deduplication (High Priority)

**Problem**: Only uses timestamps; no GUID/link-based deduplication.

**Changes**:
```python
def generate_entry_id(feed, source):
    """Generate stable ID for entry"""
    # Priority: feed's GUID > link > title+date hash
    if hasattr(feed, 'id') and feed.id:
        return f"{source}:{feed.id}"
    elif hasattr(feed, 'link') and feed.link:
        return f"{source}:{feed.link}"
    else:
        # Fallback: hash of title and timestamp
        import hashlib
        content = f"{feed.title}:{getattr(feed, 'published', '')}"
        hash_id = hashlib.md5(content.encode()).hexdigest()[:16]
        return f"{source}:{hash_id}"

# Use in main loop:
entry_id = generate_entry_id(feed, source)
if entry_id not in seen_ids:
    rslt[entry_id] = entries
    seen_ids.add(entry_id)
```

### 9. Retry Logic (High Priority)

**Problem**: Single failures are permanent.

**Changes**:
```python
from functools import wraps
import time

def retry(max_attempts=3, delay=1, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    logger.warning(f"Attempt {attempt} failed: {e}. Retrying in {current_delay}s")
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator

@retry(max_attempts=3, delay=2)
def fetch_feed(url, timeout=30):
    return feedparser.parse(url)
```

### 10. Concurrency (Medium Priority)

**Problem**: Sequential fetching is slow.

**Changes**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, show_author, timeout=30):
    """Fetch a single feed, return (source, parsed_data, error)"""
    try:
        d = feedparser.parse(url)
        return (source, d, None)
    except Exception as e:
        return (source, None, str(e))

def get_feed_from_rss(category, urls, show_author=False, log=False, max_workers=5):
    rslt = {}
    errors = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {
            executor.submit(fetch_single_feed, source, url, show_author): source
            for source, url in urls.items()
        }
        
        for future in as_completed(future_to_source):
            source, data, error = future.result()
            if error:
                errors.append(f"{source}: {error}")
                continue
            
            # Process data as before...
```

### 11. Health Monitoring (Medium Priority)

**Problem**: No tracking of feed reliability.

**Changes**:
```python
# Add health tracking file: feed_health.json
{
    "category_name": {
        "source_name": {
            "last_success": timestamp,
            "last_failure": timestamp,
            "consecutive_failures": int,
            "total_fetches": int,
            "total_failures": int
        }
    }
}

# Update after each fetch:
def update_feed_health(category, source, success):
    health_file = os.path.join(p["path_data"], "feed_health.json")
    health = json.load(open(health_file)) if os.path.exists(health_file) else {}
    
    if category not in health:
        health[category] = {}
    if source not in health[category]:
        health[category][source] = {
            "consecutive_failures": 0,
            "total_fetches": 0,
            "total_failures": 0
        }
    
    stats = health[category][source]
    stats['total_fetches'] += 1
    
    if success:
        stats['last_success'] = int(time.time())
        stats['consecutive_failures'] = 0
    else:
        stats['last_failure'] = int(time.time())
        stats['consecutive_failures'] += 1
        stats['total_failures'] += 1
    
    with open(health_file, 'w') as f:
        json.dump(health, f, indent=2)
```

### 12. HTTP Caching (Medium Priority)

**Problem**: Re-downloads unchanged feeds.

**Changes**:
```python
import requests
from datetime import datetime, timedelta

def fetch_with_cache(url, cache_dir):
    """Fetch with ETag/Last-Modified support"""
    cache_file = os.path.join(cache_dir, hashlib.md5(url.encode()).hexdigest())
    headers = {}
    
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            if 'etag' in cached:
                headers['If-None-Match'] = cached['etag']
            if 'last_modified' in cached:
                headers['If-Modified-Since'] = cached['last_modified']
    
    response = requests.get(url, headers=headers, timeout=30)
    
    if response.status_code == 304:  # Not Modified
        return cached['content']
    
    # Cache new content with headers
    cache_data = {
        'content': response.text,
        'etag': response.headers.get('ETag'),
        'last_modified': response.headers.get('Last-Modified'),
        'cached_at': datetime.now().isoformat()
    }
    
    with open(cache_file, 'w') as f:
        json.dump(cache_data, f)
    
    return response.text
```

### 13. Enhanced CLI (Medium Priority)

**Problem**: Limited command-line interface.

**Changes**:
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    subparsers = parser.add_subparsers(dest='command')
    
    # Fetch command
    fetch_parser = subparsers.add_parser('fetch', help='Fetch feeds')
    fetch_parser.add_argument('--category', help='Specific category to fetch')
    fetch_parser.add_argument('--verbose', action='store_true')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List categories')
    
    # Add command
    add_parser = subparsers.add_parser('add', help='Add a feed')
    add_parser.add_argument('category')
    add_parser.add_argument('name')
    add_parser.add_argument('url')
    
    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    
    args = parser.parse_args()
    
    if args.command == 'fetch':
        do(target_category=args.category, log=args.verbose)
    elif args.command == 'list':
        list_categories()
    elif args.command == 'add':
        add_feed(args.category, args.name, args.url)
    elif args.command == 'stats':
        show_stats()
```

These changes would transform the system from a working prototype into a production-ready RSS aggregator with robust error handling, better performance, and enhanced usability.