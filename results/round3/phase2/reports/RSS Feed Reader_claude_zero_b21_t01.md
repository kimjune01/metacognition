# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Data Persistence**: Saves parsed feed entries to JSON files (one per category) in `~/.rreader/`
4. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Auto-initializes missing configuration by copying bundled defaults
   - Merges new categories from bundled config without overwriting user customization
5. **Timestamp Handling**: Converts feed timestamps to a configured timezone (currently KST/UTC+9)
6. **Flexible Date Display**: Shows time-only for today's entries, full date for older entries
7. **Author Attribution**: Supports per-category toggle for showing feed author vs. source name
8. **Selective Updates**: Can update a single category or all categories
9. **Deduplication**: Uses timestamp as unique ID to prevent duplicate entries (within a category)
10. **Optional Logging**: Provides progress output when `log=True`

## Triage

### Critical (P0) - System Breaks Without These
1. **No error handling for feed parsing failures** - Currently calls `sys.exit(0)` on parse errors, silently failing
2. **Timestamp collision vulnerability** - Using timestamp as ID causes data loss when multiple entries share the same second
3. **Missing bundled feeds.json** - Code references a bundled file that doesn't exist in the snippet
4. **Bare except clauses** - Catches and silently ignores all exceptions, hiding real problems

### High Priority (P1) - Production Blockers
5. **No retry logic** - Network failures permanently skip feeds
6. **No timeout configuration** - Feed parsing can hang indefinitely
7. **No data validation** - Doesn't verify JSON structure or required feed fields
8. **Hardcoded timezone** - Should be configurable per-user
9. **No feed update frequency control** - Could hammer servers or waste bandwidth
10. **Missing logging framework** - Uses print/stdout instead of proper logging

### Medium Priority (P2) - Quality & Maintainability
11. **No content sanitization** - Trusts feed data for titles/URLs without validation
12. **No entry limits** - Unlimited feed entries could cause memory/disk issues
13. **No stale data cleanup** - Old JSON files accumulate forever
14. **Missing feed metadata** - Doesn't track last successful update, error counts, etc.
15. **No async/concurrent fetching** - Sequential feed parsing is slow
16. **Import path hackery** - Try/except import pattern is fragile

### Low Priority (P3) - Nice to Have
17. **No CLI interface** - Limited command-line options
18. **No progress indicators** - Only basic stdout messages
19. **No metrics/monitoring** - Can't track system health
20. **No tests** - Zero test coverage evident

## Plan

### P0 Fixes

**1. Fix error handling for feed parsing**
```python
# Replace the bare except with specific exception handling:
try:
    d = feedparser.parse(url)
    if log:
        sys.stdout.write(" - Done\n")
    if d.bozo:  # feedparser sets this flag for malformed feeds
        raise feedparser.ParseError(d.bozo_exception)
except (feedparser.ParseError, urllib.error.URLError, 
        http.client.HTTPException) as e:
    if log:
        sys.stderr.write(f" - Failed: {str(e)}\n")
    continue  # Skip this feed, process others
```

**2. Fix timestamp collision issue**
```python
# Create unique IDs combining timestamp and URL hash:
import hashlib

entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"

# Or use incrementing counter for same-second entries:
if entry_id in rslt:
    counter = 1
    while f"{entry_id}_{counter}" in rslt:
        counter += 1
    entry_id = f"{entry_id}_{counter}"
```

**3. Create bundled feeds.json**
```python
# Create a feeds.json file in the package:
# rreader/feeds.json:
{
    "tech": {
        "feeds": {
            "Example": "https://example.com/feed.xml"
        },
        "show_author": false
    }
}
```

**4. Replace bare except clauses**
```python
# In timestamp parsing section:
try:
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        continue
    at = (datetime.datetime(*parsed_time[:6])
          .replace(tzinfo=datetime.timezone.utc)
          .astimezone(TIMEZONE))
except (TypeError, ValueError, AttributeError) as e:
    # Log specific error and skip this entry
    if log:
        sys.stderr.write(f"  Skipping entry due to timestamp error: {e}\n")
    continue
```

### P1 Fixes

**5. Add retry logic**
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, 
                  status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# Use in parsing:
session = create_session()
d = feedparser.parse(url, request_headers={'User-Agent': 'rreader/1.0'})
```

**6. Add timeout configuration**
```python
# In config.py:
FEED_TIMEOUT = 30  # seconds

# In do() function:
import socket
socket.setdefaulttimeout(FEED_TIMEOUT)
```

**7. Add data validation**
```python
def validate_feed_entry(feed):
    """Validate required fields exist and are safe."""
    required = ['link', 'title']
    for field in required:
        if not hasattr(feed, field) or not getattr(feed, field):
            return False
    # Validate URL format
    if not feed.link.startswith(('http://', 'https://')):
        return False
    return True

# Use before processing:
if not validate_feed_entry(feed):
    continue
```

**8. Make timezone configurable**
```python
# In config.py, read from environment or config file:
import os

TIMEZONE_OFFSET = int(os.getenv('RREADER_TZ_OFFSET', '9'))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET))

# Or read from feeds.json:
# Add "timezone_offset": 9 to the config structure
```

**9. Add update frequency control**
```python
def should_update(category, min_interval=300):
    """Check if enough time has passed since last update."""
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(cache_file):
        return True
    
    with open(cache_file, 'r') as f:
        data = json.load(f)
    
    last_update = data.get('created_at', 0)
    return (time.time() - last_update) > min_interval

# Use in do():
if not should_update(category):
    if log:
        print(f"Skipping {category}, updated recently")
    continue
```

**10. Implement proper logging**
```python
import logging

# At module level:
logger = logging.getLogger(__name__)

# Replace all sys.stdout.write/print:
logger.info(f"Processing feed: {url}")
logger.error(f"Failed to parse {url}: {e}")
logger.debug(f"Found {len(rslt)} entries")

# Configure in main:
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
```

### P2 Fixes

**11. Add content sanitization**
```python
import html
import re

def sanitize_text(text, max_length=500):
    """Remove HTML, limit length, handle encoding."""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)  # Strip HTML tags
    text = text.strip()[:max_length]
    return text

# Apply to titles:
"title": sanitize_text(feed.title),
```

**12. Implement entry limits**
```python
# In feeds.json, add per-category limits:
"tech": {
    "feeds": {...},
    "max_entries": 100
}

# In code:
max_entries = d.get("max_entries", 200)
rslt = [val for key, val in sorted(rslt.items(), reverse=True)][:max_entries]
```

**13. Add stale data cleanup**
```python
def cleanup_old_entries(max_age_days=30):
    """Remove entries older than max_age_days."""
    cutoff = time.time() - (max_age_days * 86400)
    
    for category_file in os.listdir(p["path_data"]):
        if not category_file.startswith("rss_"):
            continue
        
        filepath = os.path.join(p["path_data"], category_file)
        with open(filepath, 'r') as f:
            data = json.load(f)
        
        data['entries'] = [e for e in data['entries'] 
                          if e.get('timestamp', 0) > cutoff]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, ensure_ascii=False)
```

**14. Track feed metadata**
```python
# Add to output JSON:
rslt = {
    "entries": rslt,
    "created_at": int(time.time()),
    "metadata": {
        "total_feeds": len(urls),
        "successful_feeds": successful_count,
        "failed_feeds": failed_feeds_list,
        "last_error": last_error_msg
    }
}
```

**15. Add concurrent fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    """Fetch and parse a single feed."""
    try:
        if log:
            logger.info(f"Fetching {url}")
        return source, feedparser.parse(url)
    except Exception as e:
        logger.error(f"Failed {url}: {e}")
        return source, None

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_single_feed, src, url, log): src 
                   for src, url in urls.items()}
        
        for future in as_completed(futures):
            source, parsed = future.result()
            if parsed:
                # Process parsed.entries as before
                pass
    # ... rest of function
```

**16. Fix import structure**
```python
# Create proper package structure:
# rreader/__init__.py
from .fetch import do as fetch_feeds
from .config import TIMEZONE

# Use absolute imports throughout:
from rreader.common import p, FEEDS_FILE_NAME
from rreader.config import TIMEZONE
```

### P3 Fixes

**17. Add CLI interface**
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('-c', '--category', help='Update specific category')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('--force', action='store_true', 
                       help='Force update ignoring cache')
    args = parser.parse_args()
    
    do(target_category=args.category, log=args.verbose)

if __name__ == "__main__":
    main()
```

**18. Add progress indicators**
```python
from tqdm import tqdm

# Wrap feed iteration:
for source, url in tqdm(urls.items(), desc=f"Fetching {category}"):
    # ... existing code
```

**19. Add metrics/monitoring**
```python
# Add metrics collection:
metrics = {
    'feeds_processed': 0,
    'feeds_failed': 0,
    'entries_found': 0,
    'processing_time': 0
}

# Write metrics file:
with open(os.path.join(p["path_data"], "metrics.json"), 'w') as f:
    json.dump(metrics, f)
```

**20. Add tests**
```python
# tests/test_fetch.py
import pytest
from unittest.mock import Mock, patch
from rreader.fetch import do, get_feed_from_rss

def test_feed_parsing_with_mock():
    mock_feed = Mock()
    mock_feed.entries = [...]
    # ... test implementation
```