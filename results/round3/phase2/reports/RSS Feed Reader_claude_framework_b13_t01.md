# Diagnostic Report: RSS Feed Aggregation System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Successfully fetches and parses RSS/Atom feeds using `feedparser`
2. **Multi-source aggregation**: Handles multiple feed sources per category
3. **Timestamp normalization**: Converts feed timestamps to a configurable timezone (KST/UTC+9)
4. **Deduplication by timestamp**: Uses Unix timestamp as unique ID to prevent duplicate entries
5. **Time-aware display formatting**: Shows "HH:MM" for today's posts, "Mon DD, HH:MM" for older ones
6. **Sorted output**: Entries sorted reverse-chronologically by timestamp
7. **JSON persistence**: Saves aggregated feeds to `~/.rreader/rss_{category}.json`
8. **Configuration management**: 
   - Bundles default `feeds.json` with the package
   - Copies to user directory on first run
   - Merges new categories from bundled version into user config
9. **Author display toggle**: Per-category control over showing feed author vs source name
10. **Optional logging**: Can print progress during feed fetching
11. **Selective updates**: Can refresh a single category or all categories

## Triage

### Critical (blocks production use)

1. **No error recovery**: Silent failures swallow network errors, parse failures, and malformed feeds
2. **No rate limiting**: Will hammer feed servers if run frequently
3. **No caching strategy**: Re-fetches entire feeds even when unchanged (wastes bandwidth)
4. **Collision-prone deduplication**: Unix timestamp as ID fails when feeds publish multiple items in the same second
5. **No feed validation**: Accepts any URL without checking if it's actually RSS/Atom

### High (degrades user experience)

6. **No timeout controls**: Slow/hung feeds block the entire refresh process
7. **No concurrent fetching**: Sequential processing makes multi-category updates slow
8. **Missing content preservation**: Doesn't store article summaries/descriptions
9. **No read/unread tracking**: Can't distinguish seen from new entries
10. **No entry limits**: Unbounded growth of JSON files over time

### Medium (limits flexibility)

11. **Hardcoded timezone**: `TIMEZONE` in config.py can't be changed at runtime
12. **No CLI interface**: Can only run programmatically or with `python -m`
13. **Missing feed metadata**: Doesn't store feed title, description, or last-updated
14. **No export formats**: Only outputs JSON, no HTML/OPML/etc.
15. **Limited timestamp fallback**: Only tries `published_parsed` then `updated_parsed`

### Low (nice to have)

16. **No feed health monitoring**: Doesn't track failure rates or stale feeds
17. **No user-agent string**: Some feeds block generic parsers
18. **Missing enclosure support**: Doesn't handle podcast/media attachments
19. **No category reordering**: Categories appear in dict iteration order

## Plan

### 1. Error Recovery (Critical)
**Current state**: `try/except` blocks do nothing except skip entries
```python
except:
    continue  # or sys.exit(0)
```

**Required changes**:
- Add structured error logging with `logging` module
- Create `FeedError` exception class with fields: `url`, `category`, `error_type`, `timestamp`
- Store failed feeds in `failed_feeds.json` with retry metadata
- Log to `~/.rreader/errors.log` with rotation
- Return partial results instead of failing completely

**Implementation**:
```python
import logging
from dataclasses import dataclass
from typing import Optional

@dataclass
class FeedError:
    url: str
    category: str
    error_type: str  # 'network', 'parse', 'timeout'
    timestamp: int
    message: str

def get_feed_from_rss(...):
    errors = []
    for source, url in urls.items():
        try:
            # existing fetch logic
        except requests.Timeout as e:
            errors.append(FeedError(url, category, 'timeout', int(time.time()), str(e)))
        except Exception as e:
            errors.append(FeedError(url, category, 'unknown', int(time.time()), str(e)))
    
    # Save errors separately
    with open(os.path.join(p["path_data"], f"errors_{category}.json"), "w") as f:
        json.dump([vars(e) for e in errors], f)
```

### 2. Rate Limiting (Critical)
**Current state**: No throttling between requests

**Required changes**:
- Add `requests_cache` library with expiry
- Implement per-domain rate limiting (default: 1 req/second)
- Add `Last-Modified` and `ETag` support for conditional requests
- Store last-fetch timestamp per feed

**Implementation**:
```python
import requests
import requests_cache
from time import sleep
from collections import defaultdict

requests_cache.install_cache(
    os.path.join(p["path_data"], 'http_cache'),
    expire_after=900  # 15 minutes
)

last_fetch = defaultdict(float)  # domain -> timestamp

def fetch_with_rate_limit(url, delay=1.0):
    domain = urlparse(url).netloc
    elapsed = time.time() - last_fetch[domain]
    if elapsed < delay:
        sleep(delay - elapsed)
    
    response = requests.get(url, timeout=10)
    last_fetch[domain] = time.time()
    return response
```

### 3. Fix Deduplication (Critical)
**Current state**: Uses timestamp as ID
```python
"id": ts,  # Collision when multiple entries published same second
```

**Required changes**:
- Generate hash from `(url, title, timestamp)` tuple
- Add `feed_id` field separate from `id` for UI
- Check for hash collisions and append counter if needed

**Implementation**:
```python
import hashlib

def generate_entry_id(url: str, title: str, timestamp: int) -> str:
    content = f"{url}|{title}|{timestamp}".encode('utf-8')
    return hashlib.sha256(content).hexdigest()[:16]

entries = {
    "id": generate_entry_id(feed.link, feed.title, ts),
    "timestamp": ts,  # Keep for sorting
    # ... rest
}
```

### 4. Feed Validation (Critical)
**Current state**: Blindly parses any URL

**Required changes**:
- Validate URL format before fetch
- Check `Content-Type` header is XML/RSS/Atom
- Verify `feedparser.parse()` result has entries
- Add validation on feed addition (when editing `feeds.json`)

**Implementation**:
```python
import validators
from typing import Optional

def validate_feed(url: str) -> Optional[str]:
    if not validators.url(url):
        return f"Invalid URL format: {url}"
    
    try:
        response = requests.head(url, timeout=5)
        content_type = response.headers.get('Content-Type', '')
        if not any(t in content_type for t in ['xml', 'rss', 'atom']):
            return f"Not a feed (Content-Type: {content_type})"
    except Exception as e:
        return f"Unreachable: {str(e)}"
    
    d = feedparser.parse(url)
    if not d.entries:
        return f"No entries found in feed"
    
    return None  # Valid
```

### 5. Timeout Controls (High)
**Current state**: No timeouts set

**Required changes**:
- Add configurable timeout to config.py (default: 10s)
- Use `requests` library with timeout instead of bare `feedparser.parse()`
- Add per-feed timeout override in feeds.json

**Implementation**:
```python
# In config.py
FEED_TIMEOUT = 10  # seconds

# In feed fetching
import requests
response = requests.get(url, timeout=FEED_TIMEOUT)
d = feedparser.parse(response.content)
```

### 6. Concurrent Fetching (High)
**Current state**: Sequential for-loop

**Required changes**:
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetches
- Limit to 5 concurrent connections (configurable)
- Maintain per-domain rate limiting across threads

**Implementation**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_feed(source, url, category, show_author):
    # Extract current loop body here
    return (source, entries_dict)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_feed, src, url, category, show_author): src
            for src, url in urls.items()
        }
        
        for future in as_completed(futures):
            source = futures[future]
            try:
                _, entries = future.result()
                rslt.update(entries)
            except Exception as e:
                if log:
                    print(f"Failed to fetch {source}: {e}")
```

### 7. Content Preservation (High)
**Current state**: Only stores title and link

**Required changes**:
- Add `summary` field from `feed.summary` or `feed.description`
- Add `content` field from `feed.content` (full article if available)
- Sanitize HTML with `bleach` library to prevent XSS

**Implementation**:
```python
import bleach

entries = {
    # ... existing fields ...
    "summary": bleach.clean(
        getattr(feed, 'summary', getattr(feed, 'description', '')),
        tags=['p', 'br', 'strong', 'em'],
        strip=True
    ),
    "content": bleach.clean(
        getattr(feed, 'content', [{}])[0].get('value', ''),
        tags=['p', 'br', 'strong', 'em', 'a', 'ul', 'ol', 'li'],
        strip=True
    ) if hasattr(feed, 'content') else None,
}
```

### 8. Read/Unread Tracking (High)
**Current state**: No state tracking

**Required changes**:
- Create `~/.rreader/read_entries.json` with set of read entry IDs
- Add `is_read` boolean to JSON output
- Provide function to mark entries as read

**Implementation**:
```python
def load_read_entries() -> set:
    read_file = os.path.join(p["path_data"], "read_entries.json")
    if os.path.exists(read_file):
        with open(read_file, 'r') as f:
            return set(json.load(f))
    return set()

def save_read_entries(read_set: set):
    with open(os.path.join(p["path_data"], "read_entries.json"), 'w') as f:
        json.dump(list(read_set), f)

def mark_as_read(entry_ids: list):
    read = load_read_entries()
    read.update(entry_ids)
    save_read_entries(read)

# In output generation
read_entries = load_read_entries()
entries["is_read"] = entries["id"] in read_entries
```

### 9. Entry Limits (High)
**Current state**: Stores all entries forever

**Required changes**:
- Add `max_entries_per_category` to config (default: 200)
- Trim old entries when saving
- Add `max_age_days` option (default: 30)

**Implementation**:
```python
# In config.py
MAX_ENTRIES_PER_CATEGORY = 200
MAX_AGE_DAYS = 30

# Before saving
cutoff_ts = int(time.time()) - (MAX_AGE_DAYS * 86400)
rslt["entries"] = [
    e for e in rslt["entries"]
    if e["timestamp"] > cutoff_ts
][:MAX_ENTRIES_PER_CATEGORY]
```

### 10. CLI Interface (Medium)
**Current state**: Only callable as module

**Required changes**:
- Add `click` or `argparse` CLI with commands:
  - `rreader refresh [category]` - update feeds
  - `rreader list` - show categories
  - `rreader add <category> <name> <url>` - add feed
  - `rreader remove <category> <name>` - remove feed
  - `rreader show <category>` - display entries

**Implementation**:
```python
import click

@click.group()
def cli():
    pass

@cli.command()
@click.argument('category', required=False)
@click.option('--verbose', is_flag=True)
def refresh(category, verbose):
    """Refresh RSS feeds"""
    do(target_category=category, log=verbose)

@cli.command()
def list_categories():
    """List all feed categories"""
    with open(FEEDS_FILE_NAME, 'r') as f:
        feeds = json.load(f)
    for cat in feeds.keys():
        print(cat)

if __name__ == '__main__':
    cli()
```

This plan addresses the gaps in order of severity. Start with critical items (1-5) before production deployment, implement high-priority items (6-9) for a good user experience, then add medium/low priority features based on user needs.