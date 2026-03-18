# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-Category Support**: Organizes feeds into categories, processing each category separately
3. **Feed Configuration Management**: 
   - Loads feed configurations from a JSON file (`feeds.json`)
   - Copies bundled default feeds if user configuration doesn't exist
   - Merges new categories from bundled config into existing user config
4. **Data Persistence**: Saves parsed feed entries to JSON files (one per category: `rss_{category}.json`)
5. **Timestamp Handling**: 
   - Converts feed timestamps to a configured timezone (currently KST/UTC+9)
   - Displays relative time formatting (HH:MM for today, "Mon DD, HH:MM" for older)
6. **Deduplication**: Uses timestamp as ID to prevent duplicate entries in the same fetch
7. **Flexible Source Attribution**: Supports both feed source name and author attribution via `show_author` flag
8. **Optional Logging**: Can output progress to stdout during feed fetching
9. **Selective Updates**: Can update a single category or all categories

## Triage

### Critical Gaps (P0)
1. **No Error Handling**: Bare `except` clauses swallow all exceptions; failed feeds silently skip or exit
2. **ID Collision Risk**: Using timestamp (seconds) as ID causes duplicates when multiple entries publish in same second
3. **No Data Directory Initialization**: Creates directory but doesn't ensure FEEDS_FILE_NAME parent exists before operations

### High Priority (P1)
4. **No Rate Limiting**: Could hammer RSS servers, risking IP bans
5. **No Caching/Conditional Requests**: Re-fetches entire feeds every time, wasting bandwidth
6. **No Feed Validation**: Doesn't check if URLs are valid or if feeds are actually RSS/Atom
7. **No Retry Logic**: Single failure aborts entire category processing
8. **Timezone Hardcoded**: TIMEZONE is not configurable by users

### Medium Priority (P2)
9. **No Feed Health Monitoring**: Doesn't track which feeds consistently fail
10. **No Entry Limit**: Could create massive JSON files with unlimited entries
11. **No Concurrency**: Processes feeds sequentially, slow for many feeds
12. **Missing Required Fields**: Doesn't validate presence of `link` or `title` before use
13. **No User Feedback**: Limited progress indication, no summary statistics

### Low Priority (P3)
14. **No Data Migration**: No version handling for schema changes
15. **No Export/Import**: Can't backup or share feed collections easily
16. **No Feed Discovery**: Users must manually add feed URLs

## Plan

### P0 Fixes

**1. Implement Proper Error Handling**
```python
# Replace bare excepts with specific exception handling:
try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser sets this on errors
        raise feedparser.bozo_exception
except (urllib.error.URLError, socket.timeout) as e:
    if log:
        sys.stderr.write(f" - Failed: {e}\n")
    continue  # Skip this feed, continue with others
except Exception as e:
    if log:
        sys.stderr.write(f" - Unexpected error: {e}\n")
    continue
```

**2. Fix ID Collision**
```python
# Create unique ID by combining timestamp with feed link hash:
import hashlib
unique_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
entries = {
    "id": unique_id,
    # ... rest of fields
}
# Use unique_id as dictionary key, not integer timestamp
rslt[entries["id"]] = entries
```

**3. Ensure Directory Structure**
```python
# In common.py, ensure full path creation:
for d in p["pathkeys"]:
    os.makedirs(p[d], exist_ok=True)  # Use makedirs instead of mkdir
```

### P1 Fixes

**4. Add Rate Limiting**
```python
import time
DELAY_BETWEEN_FEEDS = 1.0  # seconds

# In get_feed_from_rss loop:
for i, (source, url) in enumerate(urls.items()):
    if i > 0:
        time.sleep(DELAY_BETWEEN_FEEDS)
    # ... fetch feed
```

**5. Implement Conditional Requests**
```python
# Store ETags and Last-Modified headers:
# In each category JSON, add:
rslt = {
    "entries": rslt,
    "created_at": int(time.time()),
    "feed_metadata": {
        url: {
            "etag": d.get('etag'),
            "modified": d.get('modified')
        } for url in urls.values()
    }
}

# On next fetch, use stored values:
# Load previous metadata, then:
d = feedparser.parse(url, etag=prev_etag, modified=prev_modified)
if d.status == 304:  # Not modified
    continue
```

**6. Add Feed Validation**
```python
def validate_feed_url(url):
    """Check if URL is valid and returns RSS/Atom content"""
    if not url.startswith(('http://', 'https://')):
        raise ValueError(f"Invalid URL scheme: {url}")
    
    d = feedparser.parse(url)
    if d.bozo and not d.entries:
        raise ValueError(f"Invalid feed or parse error: {d.bozo_exception}")
    
    return d

# Use in get_feed_from_rss:
try:
    d = validate_feed_url(url)
except ValueError as e:
    if log:
        sys.stderr.write(f" - Validation failed: {e}\n")
    continue
```

**7. Add Retry Logic**
```python
from functools import wraps
import time

def retry(max_attempts=3, delay=2, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt_delay = delay
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(attempt_delay)
                    attempt_delay *= backoff
            return None
        return wrapper
    return decorator

@retry(max_attempts=3)
def fetch_feed(url):
    return feedparser.parse(url)
```

**8. Make Timezone Configurable**
```python
# In config.py, load from environment or config file:
import os
TIMEZONE_OFFSET = int(os.getenv('RREADER_TZ_OFFSET', '9'))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET))

# Or add to feeds.json:
{
    "settings": {
        "timezone_offset": 9
    },
    "categories": { ... }
}
```

### P2 Fixes

**9. Feed Health Monitoring**
```python
# Add to each category JSON:
"feed_health": {
    url: {
        "last_success": timestamp,
        "last_failure": timestamp,
        "consecutive_failures": count,
        "total_failures": count
    }
}

# Update after each fetch attempt
# Alert/disable feeds with consecutive_failures > threshold
```

**10. Implement Entry Limits**
```python
MAX_ENTRIES_PER_CATEGORY = 100
MAX_AGE_DAYS = 30

# After sorting entries:
rslt = [val for key, val in sorted(rslt.items(), reverse=True)]
# Apply limits:
rslt = rslt[:MAX_ENTRIES_PER_CATEGORY]
# Filter by age:
cutoff = int(time.time()) - (MAX_AGE_DAYS * 86400)
rslt = [e for e in rslt if e['timestamp'] > cutoff]
```

**11. Add Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    """Fetch one feed, return (source, result_dict)"""
    # Move inner feed-fetching logic here
    pass

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_single_feed, source, url, log): source
            for source, url in urls.items()
        }
        
        for future in as_completed(futures):
            try:
                source, entries = future.result()
                rslt.update(entries)
            except Exception as e:
                if log:
                    sys.stderr.write(f"Failed {source}: {e}\n")
    # ... rest of processing
```

**12. Validate Required Fields**
```python
# Before creating entries dict:
if not hasattr(feed, 'link') or not hasattr(feed, 'title'):
    continue  # Skip malformed entries

# Add defensive checks:
entries = {
    "id": unique_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": getattr(feed, 'link', ''),
    "title": getattr(feed, 'title', 'Untitled'),
    "description": getattr(feed, 'summary', '')[:500]  # Add description
}
```

**13. Enhanced User Feedback**
```python
def do(target_category=None, log=False):
    stats = {"total_feeds": 0, "successful": 0, "failed": 0, "new_entries": 0}
    
    # Track stats throughout processing
    
    if log:
        print(f"\nSummary: {stats['successful']}/{stats['total_feeds']} feeds successful")
        print(f"Retrieved {stats['new_entries']} entries")
        if stats['failed'] > 0:
            print(f"Warning: {stats['failed']} feeds failed")
```

### P3 Fixes

**14. Data Migration System**
```python
SCHEMA_VERSION = 1

def migrate_data(old_data, from_version):
    """Migrate data between schema versions"""
    if from_version < 1:
        # Add new fields, transform structure
        pass
    return old_data

# Check version when loading, migrate if needed
```

**15. Export/Import Functions**
```python
def export_feeds(output_file):
    """Export feeds.json and all cached data to archive"""
    import tarfile
    with tarfile.open(output_file, 'w:gz') as tar:
        tar.add(FEEDS_FILE_NAME)
        tar.add(p['path_data'])

def import_feeds(input_file):
    """Import feeds from archive"""
    # Extract and merge with existing
```

**16. Feed Discovery Helper**
```python
def discover_feed(webpage_url):
    """Attempt to find RSS feed from webpage URL"""
    import requests
    from bs4 import BeautifulSoup
    
    response = requests.get(webpage_url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    # Look for <link rel="alternate" type="application/rss+xml">
    feeds = soup.find_all('link', type='application/rss+xml')
    return [feed.get('href') for feed in feeds]
```