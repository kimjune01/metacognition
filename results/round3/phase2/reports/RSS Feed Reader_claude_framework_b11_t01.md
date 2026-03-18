# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from configured URLs
2. **Multi-source aggregation**: Processes multiple feeds organized by categories
3. **Timestamp handling**: Converts feed publication times to a configurable timezone (currently KST/UTC+9)
4. **Deduplication**: Uses timestamp-based dictionary keys to eliminate duplicate entries within a category
5. **Sorting**: Presents entries in reverse chronological order (newest first)
6. **Persistence**: Saves parsed results as JSON files (`rss_{category}.json`) in `~/.rreader/`
7. **Configuration management**: 
   - Maintains a `feeds.json` configuration file
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled config without overwriting user modifications
8. **Optional author display**: Supports per-category `show_author` flag to display feed author instead of source name
9. **Selective updates**: Can update a single category or all categories
10. **Logging**: Optional progress output during feed fetching

The data structure is clean: each entry contains id, sourceName, pubDate (human-readable), timestamp (Unix), url, and title.

## Triage

### Critical (blocks production use)

1. **Error handling is broken**: The bare `except:` clauses swallow all exceptions, making debugging impossible and hiding network failures, parsing errors, and configuration problems
2. **No retry logic**: Network failures instantly fail with no backoff or retry, making the system fragile to transient issues
3. **No rate limiting**: Could hammer servers if feeds are misconfigured or the update frequency is too high
4. **Silent data loss**: Failed feeds are skipped with no record, and users have no visibility into what succeeded vs. failed

### Important (degrades user experience)

5. **No staleness detection**: Cached results have `created_at` timestamps but nothing checks feed age or forces refresh
6. **No feed validation**: Accepts any URL without checking if it's actually an RSS/Atom feed
7. **Blocking I/O**: Fetches feeds sequentially; updating 20 feeds takes 20× longer than necessary
8. **No content deduplication across categories**: Same article from different feeds creates duplicate entries
9. **Timestamp collision handling**: If two articles share a timestamp (rare but possible), one silently overwrites the other
10. **No pruning**: Old entries accumulate indefinitely, bloating the JSON files

### Minor (polish and maintainability)

11. **Import structure inconsistency**: The try/except import block suggests this should be a package, but the inline code at the bottom contradicts that
12. **No logging framework**: Uses print/sys.stdout instead of proper logging levels
13. **Hardcoded timezone**: TIMEZONE should be in user config, not system config
14. **No entry limit**: Could fetch thousands of entries if a feed returns its entire archive
15. **Date formatting not localized**: Month abbreviations are English-only

## Plan

### 1. Fix error handling
**Current problem**: `except:` swallows all exceptions including KeyboardInterrupt and SystemExit.

**Change needed**:
```python
# In get_feed_from_rss, replace:
try:
    d = feedparser.parse(url)
except:
    sys.exit(" - Failed\n" if log else 0)

# With:
try:
    d = feedparser.parse(url)
except (urllib.error.URLError, http.client.HTTPException) as e:
    if log:
        sys.stderr.write(f" - Failed: {type(e).__name__}: {e}\n")
    continue  # Skip this feed, don't kill entire process
```

Similar pattern for the timestamp parsing block: catch specific exceptions (`AttributeError`, `ValueError`, `TypeError`) and log which feed/entry caused the problem.

### 2. Add retry logic with exponential backoff
**Current problem**: Single network hiccup fails permanently.

**Change needed**: Add before the feedparser.parse call:
```python
from urllib.error import URLError
import time

max_retries = 3
for attempt in range(max_retries):
    try:
        d = feedparser.parse(url)
        break
    except URLError as e:
        if attempt == max_retries - 1:
            raise
        wait_time = 2 ** attempt  # 1s, 2s, 4s
        if log:
            sys.stderr.write(f" - Retry {attempt+1}/{max_retries} after {wait_time}s\n")
        time.sleep(wait_time)
```

### 3. Implement rate limiting
**Current problem**: No delay between requests to same or different servers.

**Change needed**: Add to top of `get_feed_from_rss`:
```python
import time
last_request_time = {}

# Before feedparser.parse(url):
domain = urllib.parse.urlparse(url).netloc
now = time.time()
if domain in last_request_time:
    elapsed = now - last_request_time[domain]
    if elapsed < 1.0:  # Min 1 second between requests to same domain
        time.sleep(1.0 - elapsed)
last_request_time[domain] = time.time()
```

### 4. Create failure tracking
**Current problem**: Users don't know which feeds failed or why.

**Change needed**: Modify return structure:
```python
rslt = {
    "entries": rslt, 
    "created_at": int(time.time()),
    "feed_status": {
        source: {"ok": True, "last_error": None} for source in urls
    }
}

# In exception handlers, update:
rslt["feed_status"][source] = {
    "ok": False, 
    "last_error": str(e),
    "failed_at": int(time.time())
}
```

### 5. Add staleness checks
**Current problem**: Old cached data served indefinitely.

**Change needed**: In `do()`, before returning cached data:
```python
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(cache_file):
    with open(cache_file, "r") as f:
        cached = json.load(f)
    age_seconds = int(time.time()) - cached.get("created_at", 0)
    max_age = RSS[category].get("max_cache_age", 3600)  # Default 1 hour
    if age_seconds < max_age:
        return cached
```

Add `max_cache_age` to feeds.json schema.

### 6. Add feed format validation
**Current problem**: Non-feed URLs accepted without warning.

**Change needed**: After `d = feedparser.parse(url)`:
```python
if not d.entries and not d.bozo:  # bozo flag indicates malformed but parseable
    if log:
        sys.stderr.write(f" - Warning: No entries found, may not be a valid feed\n")
    continue
if d.bozo and log:
    sys.stderr.write(f" - Warning: Malformed feed: {d.bozo_exception}\n")
```

### 7. Parallelize feed fetching
**Current problem**: Sequential fetching is slow.

**Change needed**: Replace the for-loop in `get_feed_from_rss`:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_one_feed(source, url):
    # Move existing try/except block here
    # Return (source, entries_dict) tuple
    pass

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_one_feed, src, url): src 
               for src, url in urls.items()}
    
    for future in as_completed(futures):
        source = futures[future]
        try:
            source_name, entries = future.result()
            rslt.update(entries)
        except Exception as e:
            if log:
                sys.stderr.write(f"Failed to fetch {source}: {e}\n")
```

### 8. Implement content-based deduplication
**Current problem**: Same article from multiple feeds creates duplicates.

**Change needed**: Use content hash instead of timestamp as primary key:
```python
import hashlib

# Replace:
entries = {"id": ts, ...}

# With:
content_hash = hashlib.md5(
    f"{feed.title}{feed.link}".encode('utf-8')
).hexdigest()[:12]
entries = {"id": content_hash, "timestamp": ts, ...}
```

Then sort by timestamp instead of key during serialization.

### 9. Fix timestamp collision handling
**Current problem**: `rslt[entries["id"]] = entries` silently overwrites.

**Change needed**:
```python
# Replace dictionary with list during collection:
entries_list = []
for feed in d.entries:
    # ... build entries dict ...
    entries_list.append(entries)

# Deduplicate and sort later:
seen_urls = set()
unique_entries = []
for entry in sorted(entries_list, key=lambda x: x['timestamp'], reverse=True):
    if entry['url'] not in seen_urls:
        seen_urls.add(entry['url'])
        unique_entries.append(entry)
```

### 10. Add entry pruning
**Current problem**: JSON files grow unbounded.

**Change needed**: Before writing JSON:
```python
max_entries = RSS[category].get("max_entries", 100)
rslt["entries"] = rslt["entries"][:max_entries]
```

Add `max_entries` to feeds.json schema.

### 11. Standardize package structure
**Current problem**: Mixed inline and import patterns.

**Change needed**: Remove the inline constants at the bottom. Create proper `rreader/__init__.py`:
```python
from .update import do as update_feeds
from .common import p, FEEDS_FILE_NAME
from .config import TIMEZONE

__all__ = ['update_feeds', 'p', 'FEEDS_FILE_NAME', 'TIMEZONE']
```

Make `update.py` not executable directly (remove `if __name__ == "__main__"`).

### 12. Add proper logging
**Current problem**: Mix of print, sys.stdout, sys.stderr with no levels.

**Change needed**:
```python
import logging

logger = logging.getLogger(__name__)

# Replace all sys.stdout.write with:
logger.info(f"Fetching {url}")
logger.debug(f"Parsed {len(d.entries)} entries")
logger.error(f"Failed to fetch {url}: {e}")
```

Let caller configure logging level.

### 13. Make timezone configurable
**Current problem**: Hardcoded in config.py.

**Change needed**: Add to feeds.json:
```json
{
  "_settings": {
    "timezone_offset_hours": 9
  },
  "tech": { "feeds": {...} }
}
```

Read it in `do()` and pass to `get_feed_from_rss`.

### 14. Add entry limits per feed
**Current problem**: Could fetch 10,000+ entries if feed includes archive.

**Change needed**: After parsing:
```python
max_entries_per_feed = RSS[category].get("max_entries_per_feed", 50)
for feed in d.entries[:max_entries_per_feed]:
    # ... process feed ...
```

### 15. Support locale-based date formatting
**Current problem**: English-only month names.

**Change needed**:
```python
import locale

# In config.py, add:
LOCALE = "ko_KR.UTF-8"  # Or read from settings

# In get_feed_from_rss:
try:
    locale.setlocale(locale.LC_TIME, LOCALE)
except locale.Error:
    pass  # Fall back to system default

pubDate = at.strftime(
    "%H:%M" if at.date() == datetime.date.today() else "%b %d, %H:%M"
)
```