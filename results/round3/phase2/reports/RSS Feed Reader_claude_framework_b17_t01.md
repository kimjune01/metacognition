# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed reader with the following capabilities:

**Core Functionality:**
- Parses multiple RSS feeds from JSON configuration (`feeds.json`)
- Extracts standard feed entry fields: title, link, author, publication date
- Handles both `published_parsed` and `updated_parsed` timestamps as fallbacks
- Converts timestamps to a configurable timezone (currently KST/UTC+9)
- Formats publication dates context-aware: "HH:MM" for today, "MMM DD, HH:MM" for older entries
- Deduplicates entries by timestamp across multiple sources within a category
- Sorts entries reverse-chronologically by timestamp
- Outputs JSON files per category to `~/.rreader/` directory

**Configuration Management:**
- Auto-creates data directory if missing
- Ships with bundled default `feeds.json`
- Copies bundled feeds to user directory on first run
- Merges new categories from bundled config into existing user config

**Error Handling:**
- Gracefully skips feeds with missing timestamps
- Optional logging mode for network operations
- Silent failure on network errors (exits with code 0)

**Entry Data Structure:**
```json
{
  "entries": [...],
  "created_at": <unix_timestamp>
}
```

Each entry contains: `id`, `sourceName`, `pubDate`, `timestamp`, `url`, `title`

---

## Triage

### Critical Gaps

**1. Error Handling & Observability** ⚠️
- Network failures exit silently or with unclear messages
- No retry logic for transient failures
- No structured logging
- No health metrics or feed staleness detection
- Parse errors lose which feed failed

**2. Feed Configuration Validation** ⚠️
- No schema validation for `feeds.json`
- Malformed URLs cause cryptic feedparser errors
- Missing required keys (`feeds`, category names) cause KeyErrors
- No validation that URLs are actually RSS/Atom feeds

**3. Data Integrity** ⚠️
- Timestamp collisions overwrite entries (dict keyed by timestamp)
- No deduplication by content (same article from multiple aggregators)
- Race conditions if multiple processes write simultaneously

### Important Gaps

**4. Performance & Scalability**
- Sequential feed fetching blocks on slow feeds
- No caching of feed responses (refetches everything)
- No rate limiting or respect for feed TTL headers
- Large feeds load entirely into memory

**5. User Experience**
- No command to add/remove feeds without editing JSON
- No way to mark entries as read
- No search or filtering capabilities
- Timezone hardcoded, not user-configurable

**6. Code Quality**
- Broad `except:` clauses hide bugs
- Magic numbers (e.g., `[:6]` for datetime tuple slicing)
- Import fallback pattern suggests packaging confusion
- No type hints
- Mixing concerns (network I/O + data transformation + file I/O)

### Minor Gaps

**7. Feed Format Support**
- No handling of media enclosures (podcasts, videos)
- No support for feed categories/tags
- Doesn't preserve feed descriptions/summaries
- No handling of HTML entities in titles

**8. Maintenance**
- No version tracking for data format
- No migration strategy for schema changes
- No cleanup of stale JSON files
- Bundled feeds updated only through code releases

---

## Plan

### 1. Error Handling & Observability

**Network Errors:**
```python
import logging
from urllib.error import URLError

logger = logging.getLogger(__name__)

# Replace bare except with specific exceptions
try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser's error flag
        logger.error(f"Feed parse error for {url}: {d.bozo_exception}")
        continue
except (URLError, TimeoutError) as e:
    logger.warning(f"Network error fetching {url}: {e}")
    # Implement exponential backoff retry here
    continue
```

**Staleness Detection:**
```python
# Add to output JSON
"feed_metadata": {
    "last_successful_fetch": timestamp,
    "consecutive_failures": 0,
    "last_entry_timestamp": max_entry_ts
}

# Alert if no new entries in 7 days
if (now - last_entry_timestamp) > 7 * 86400:
    logger.warning(f"Feed {source} appears stale")
```

**Structured Logging:**
```python
logger.info("feed_fetch", extra={
    "category": category,
    "source": source,
    "url": url,
    "entry_count": len(d.entries),
    "duration_ms": elapsed
})
```

---

### 2. Feed Configuration Validation

**Schema Validation (use `jsonschema`):**
```python
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {  # category name
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

jsonschema.validate(RSS, FEEDS_SCHEMA)
```

**URL Validation:**
```python
from urllib.parse import urlparse

def validate_url(url):
    parsed = urlparse(url)
    if not parsed.scheme in ['http', 'https']:
        raise ValueError(f"Invalid URL scheme: {url}")
    # Optional: HEAD request to check Content-Type contains xml/rss
```

---

### 3. Data Integrity

**Fix Timestamp Collisions:**
```python
# Change dict key from timestamp to composite key
key = f"{ts}_{hash(feed.link) % 10000}"  # or use uuid
rslt[key] = entries

# Or use list and dedupe later
entries_list = []
seen_urls = set()
for entry in all_entries:
    if entry['url'] not in seen_urls:
        entries_list.append(entry)
        seen_urls.add(entry['url'])
```

**Atomic Writes:**
```python
import tempfile

# Write to temp file, then atomic rename
tmp_file = tempfile.NamedTemporaryFile(
    mode='w', 
    delete=False, 
    dir=p["path_data"],
    suffix='.json'
)
json.dump(rslt, tmp_file, ensure_ascii=False)
tmp_file.close()
os.replace(tmp_file.name, final_path)  # atomic on POSIX
```

---

### 4. Performance & Scalability

**Parallel Fetching:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_feed(source, url):
    return source, feedparser.parse(url)

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_feed, src, url): src 
               for src, url in urls.items()}
    
    for future in as_completed(futures):
        source, feed_data = future.result()
        # process feed_data
```

**HTTP Caching:**
```python
# Add ETag and Last-Modified support
import requests

response = requests.get(url, headers={
    'If-None-Match': cached_etag,
    'If-Modified-Since': cached_last_modified
})

if response.status_code == 304:  # Not Modified
    return cached_data

# Update cache with response.headers['ETag'] etc.
```

**Respect TTL:**
```python
# Parse ttl from feed (in minutes)
ttl = feed.feed.get('ttl', 60)
next_fetch_time = now + (ttl * 60)

# Store in metadata, skip fetch if too soon
```

---

### 5. User Experience

**CLI for Feed Management:**
```python
import click

@click.group()
def cli():
    pass

@cli.command()
@click.argument('category')
@click.argument('name')
@click.argument('url')
def add_feed(category, name, url):
    """Add a feed to a category"""
    with open(FEEDS_FILE_NAME, 'r+') as f:
        feeds = json.load(f)
        if category not in feeds:
            feeds[category] = {"feeds": {}}
        feeds[category]["feeds"][name] = url
        f.seek(0)
        json.dump(feeds, f, indent=4)
        f.truncate()

# Similar for remove_feed, list_feeds
```

**Configurable Timezone:**
```python
# In config.py
TIMEZONE = os.getenv('RREADER_TIMEZONE', 'UTC')

# Use zoneinfo (Python 3.9+)
from zoneinfo import ZoneInfo
TIMEZONE = ZoneInfo(TIMEZONE)
```

---

### 6. Code Quality

**Specific Exception Handling:**
```python
# Replace all bare except:
try:
    at = datetime.datetime(*parsed_time[:6])
except (TypeError, ValueError) as e:
    logger.warning(f"Invalid timestamp in {feed.link}: {e}")
    continue
```

**Type Hints:**
```python
from typing import Dict, List, Optional

def get_feed_from_rss(
    category: str, 
    urls: Dict[str, str], 
    show_author: bool = False,
    log: bool = False
) -> Dict[str, any]:
    ...
```

**Extract Functions:**
```python
def parse_feed_entry(feed, source: str, show_author: bool) -> Optional[Dict]:
    """Extract and normalize a single feed entry"""
    ...

def format_pub_date(timestamp: time.struct_time) -> str:
    """Format publication date based on age"""
    ...

def save_category_feed(category: str, entries: List[Dict]) -> None:
    """Atomically save feed entries to disk"""
    ...
```

---

### 7. Feed Format Support

**Add to Entry Schema:**
```python
entry = {
    # ... existing fields ...
    "summary": getattr(feed, 'summary', ''),
    "content": getattr(feed, 'content', [{}])[0].get('value', ''),
    "media": [
        {
            "url": enc.get('href'),
            "type": enc.get('type'),
            "length": enc.get('length')
        }
        for enc in getattr(feed, 'enclosures', [])
    ],
    "tags": [tag.term for tag in getattr(feed, 'tags', [])]
}
```

**HTML Entity Decoding:**
```python
from html import unescape

title = unescape(feed.title)
```

---

### 8. Maintenance

**Version Data Format:**
```json
{
  "format_version": "1.0",
  "entries": [...],
  "created_at": 1234567890
}
```

**Migration System:**
```python
def migrate_v0_to_v1(data: dict) -> dict:
    """Add format_version field"""
    return {"format_version": "1.0", **data}

MIGRATIONS = {
    None: migrate_v0_to_v1,
    # Future: "1.0": migrate_v1_to_v2
}

def load_with_migration(path):
    with open(path) as f:
        data = json.load(f)
    
    version = data.get('format_version')
    while version in MIGRATIONS:
        data = MIGRATIONS[version](data)
        version = data.get('format_version')
    
    return data
```

**Cleanup Stale Files:**
```python
# Delete category files not in current config
config_categories = set(RSS.keys())
existing_files = glob.glob(os.path.join(p["path_data"], "rss_*.json"))

for filepath in existing_files:
    category = Path(filepath).stem.replace('rss_', '')
    if category not in config_categories:
        os.remove(filepath)
        logger.info(f"Removed stale file: {filepath}")
```

---

## Priority Implementation Order

1. **Fix timestamp collision bug** (data loss risk)
2. **Add specific exception handling** (hiding real errors)
3. **Schema validation** (prevents user config corruption)
4. **Structured logging** (enables debugging production issues)
5. **Parallel fetching** (performance bottleneck)
6. **CLI for feed management** (usability blocker)
7. **HTTP caching** (reduces bandwidth/load)
8. **Type hints + extract functions** (maintainability)
9. **Format version + migrations** (future-proofing)
10. **Extended feed support** (feature completeness)