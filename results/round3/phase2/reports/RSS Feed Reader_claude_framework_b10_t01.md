# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed aggregator with the following capabilities:

**Working features:**
1. **Feed parsing** — Uses `feedparser` to retrieve and parse RSS/Atom feeds from configured URLs
2. **Multi-source aggregation** — Processes multiple feeds organized by category from a JSON configuration file
3. **Time normalization** — Converts feed timestamps to a configured timezone (currently KST/UTC+9)
4. **Deduplication by timestamp** — Uses timestamp as ID to prevent duplicate entries within a single fetch
5. **Chronological sorting** — Orders entries newest-first by publication time
6. **Persistent storage** — Saves aggregated feeds as JSON files (`rss_{category}.json`) in `~/.rreader/`
7. **Configuration management** — Copies bundled default feeds on first run and merges new categories into user config
8. **Conditional author display** — Supports per-category toggle for showing feed author vs. source name
9. **Human-readable timestamps** — Formats times as "HH:MM" for today, "Mon DD, HH:MM" for older items
10. **Selective updates** — Can refresh a single category or all categories
11. **Error tolerance** — Continues processing other feeds if one fails (with optional logging)

**Architecture:**
- Modular structure with separation of concerns (feed fetching, config, storage)
- Inlined dependencies suggest this is a self-contained script
- Uses standard library where possible (datetime, json, os)

## Triage

### Critical gaps (would prevent production use):

1. **No incremental updates** — Every fetch rewrites the entire feed file, discarding history. Production systems need to preserve previously-fetched items that may have fallen off the RSS feed window.

2. **Zero error reporting** — Silent failures (`except: continue`) make debugging impossible. No logging of HTTP errors, parsing failures, or invalid timestamps.

3. **No rate limiting** — Fetches all feeds sequentially with no throttling. Will get IP-banned by aggressive feed providers or trigger DDoS protection.

4. **No feed validation** — Accepts malformed URLs, doesn't check for redirects, and has no timeout handling for hanging connections.

5. **Thread-unsafe file writes** — Concurrent executions would corrupt JSON files. No locking mechanism.

### Important gaps (would cause operational issues):

6. **No content sanitization** — Feed titles/content could contain malicious HTML/JavaScript that gets passed through unchecked.

7. **Missing retry logic** — Transient network failures permanently skip feeds for that execution cycle.

8. **No cache headers** — Doesn't use ETags or Last-Modified headers, wastes bandwidth re-fetching unchanged feeds.

9. **Timestamp collision vulnerability** — Uses second-precision timestamps as IDs; two posts in the same second will clobber each other.

10. **No feed health monitoring** — Doesn't track which feeds are consistently failing or stale.

### Nice-to-have gaps (would improve usability):

11. **No CLI interface** — The `if __name__ == "__main__"` block accepts no arguments for categories or options.

12. **Hardcoded timezone** — The KST timezone is in config but there's no mechanism to change it per-user.

13. **No read/unread tracking** — Can't mark items as seen or filter out already-read content.

14. **No content preview** — Only stores title/link/metadata, not the article summary or content.

15. **No OPML import/export** — Can't easily migrate feed lists from other readers.

## Plan

### For gap #1 (incremental updates):
**Change required:** Modify `get_feed_from_rss()` to merge new entries with existing ones.
```python
# Before writing, load existing file if it exists
existing_entries = {}
json_path = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.isfile(json_path):
    with open(json_path, "r") as f:
        old_data = json.load(f)
        existing_entries = {e["id"]: e for e in old_data.get("entries", [])}

# Merge new with old (new entries take precedence)
existing_entries.update(rslt)

# Sort and limit to most recent N items (e.g., 1000)
final_entries = sorted(existing_entries.values(), key=lambda x: x["timestamp"], reverse=True)[:1000]
```

### For gap #2 (error reporting):
**Change required:** Replace bare `except:` with specific exceptions and add logging.
```python
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# In feed fetch:
try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser's error flag
        logging.warning(f"Feed parse warning for {url}: {d.bozo_exception}")
except Exception as e:
    logging.error(f"Failed to fetch {url}: {type(e).__name__}: {e}")
    continue

# In entry processing:
try:
    parsed_time = ...
except AttributeError as e:
    logging.debug(f"Missing timestamp in entry from {source}: {feed.get('title', 'Unknown')}")
    continue
```

### For gap #3 (rate limiting):
**Change required:** Add delays between requests and respect Retry-After headers.
```python
import time
from urllib.error import HTTPError

RATE_LIMIT_DELAY = 1.0  # seconds between requests

for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        time.sleep(RATE_LIMIT_DELAY)
    except HTTPError as e:
        if e.code == 429 and 'Retry-After' in e.headers:
            wait_time = int(e.headers['Retry-After'])
            logging.warning(f"Rate limited on {url}, waiting {wait_time}s")
            time.sleep(wait_time)
```

### For gap #4 (feed validation):
**Change required:** Add URL validation and timeout configuration.
```python
from urllib.parse import urlparse
import socket

FEED_TIMEOUT = 30  # seconds

def is_valid_url(url):
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and parsed.netloc

# Before parsing:
if not is_valid_url(url):
    logging.error(f"Invalid URL: {url}")
    continue

# Set timeout:
socket.setdefaulttimeout(FEED_TIMEOUT)
d = feedparser.parse(url)
```

### For gap #5 (file locking):
**Change required:** Use `fcntl` (Unix) or `msvcrt` (Windows) for file locking.
```python
import fcntl  # Unix
import tempfile

def atomic_write_json(path, data):
    """Write JSON atomically with file locking"""
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        json.dump(data, f, ensure_ascii=False, indent=2)
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    os.replace(temp_path, path)  # atomic on POSIX
```

### For gap #6 (content sanitization):
**Change required:** Use `bleach` or `html` module to escape untrusted content.
```python
import html

entries = {
    "id": ts,
    "sourceName": html.escape(author),
    "title": html.escape(feed.title),
    "url": feed.link,  # URLs don't need escaping but should be validated
    # ...
}
```

### For gap #7 (retry logic):
**Change required:** Implement exponential backoff for failed requests.
```python
import time

def fetch_with_retry(url, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return feedparser.parse(url)
        except Exception as e:
            if attempt < max_attempts - 1:
                wait = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                logging.warning(f"Attempt {attempt+1} failed for {url}, retrying in {wait}s")
                time.sleep(wait)
            else:
                logging.error(f"All {max_attempts} attempts failed for {url}")
                raise
```

### For gap #8 (cache headers):
**Change required:** Track ETags/Last-Modified and pass them to feedparser.
```python
# Store metadata with each category's feeds
cache_file = os.path.join(p["path_data"], f"cache_{category}.json")
cache = {}
if os.path.isfile(cache_file):
    with open(cache_file, "r") as f:
        cache = json.load(f)

# Pass cached headers to feedparser
d = feedparser.parse(url, 
                     etag=cache.get(url, {}).get('etag'),
                     modified=cache.get(url, {}).get('modified'))

# Update cache after successful fetch
if d.get('etag') or d.get('modified'):
    cache[url] = {'etag': d.get('etag'), 'modified': d.get('modified')}
    with open(cache_file, "w") as f:
        json.dump(cache, f)
```

### For gap #9 (ID collisions):
**Change required:** Use composite key or UUID instead of timestamp alone.
```python
import hashlib

# Create stable ID from multiple fields
id_string = f"{feed.link}|{ts}|{feed.title}"
entry_id = hashlib.sha256(id_string.encode()).hexdigest()[:16]

entries = {
    "id": entry_id,
    "timestamp": ts,  # keep for sorting
    # ...
}
```

### For gap #10 (health monitoring):
**Change required:** Track success/failure stats per feed.
```python
health_file = os.path.join(p["path_data"], "feed_health.json")

def update_feed_health(url, success):
    health = {}
    if os.path.isfile(health_file):
        with open(health_file, "r") as f:
            health = json.load(f)
    
    if url not in health:
        health[url] = {"successes": 0, "failures": 0, "last_success": None}
    
    if success:
        health[url]["successes"] += 1
        health[url]["last_success"] = int(time.time())
    else:
        health[url]["failures"] += 1
    
    with open(health_file, "w") as f:
        json.dump(health, f, indent=2)
```

### For gap #11 (CLI interface):
**Change required:** Add argparse for command-line options.
```python
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RSS feed reader")
    parser.add_argument("--category", "-c", help="Update specific category only")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    parser.add_argument("--list-categories", "-l", action="store_true", help="List available categories")
    
    args = parser.parse_args()
    
    if args.list_categories:
        with open(FEEDS_FILE_NAME, "r") as fp:
            categories = json.load(fp).keys()
        print("\n".join(sorted(categories)))
        sys.exit(0)
    
    do(target_category=args.category, log=args.verbose)
```

### For gap #12 (configurable timezone):
**Change required:** Move timezone to user-editable config file.
```python
# In config loading:
config_file = os.path.join(p["path_data"], "config.json")
if os.path.isfile(config_file):
    with open(config_file, "r") as f:
        user_config = json.load(f)
        tz_offset = user_config.get("timezone_offset_hours", 9)
        TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```

### For gap #13 (read/unread tracking):
**Change required:** Add read status field and update mechanism.
```python
entries = {
    "id": entry_id,
    "read": False,  # default to unread
    # ...
}

def mark_as_read(category, entry_id):
    json_path = os.path.join(p["path_data"], f"rss_{category}.json")
    with open(json_path, "r+") as f:
        data = json.load(f)
        for entry in data["entries"]:
            if entry["id"] == entry_id:
                entry["read"] = True
        f.seek(0)
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.truncate()
```

### For gap #14 (content preview):
**Change required:** Store feed summary/content fields.
```python
entries = {
    "id": entry_id,
    "title": html.escape(feed.title),
    "summary": html.escape(getattr(feed, 'summary', '')[:500]),  # limit length
    "content": html.escape(getattr(feed, 'content', [{}])[0].get('value', '')[:2000]),
    # ...
}
```

### For gap #15 (OPML support):
**Change required:** Add import/export functions using `xml.etree.ElementTree`.
```python
import xml.etree.ElementTree as ET

def import_opml(opml_file):
    tree = ET.parse(opml_file)
    feeds = {}
    for outline in tree.findall('.//outline[@type="rss"]'):
        category = outline.get('category', 'Uncategorized')
        if category not in feeds:
            feeds[category] = {"feeds": {}, "show_author": False}
        feeds[category]["feeds"][outline.get('title')] = outline.get('xmlUrl')
    
    # Merge with existing feeds.json
    with open(FEEDS_FILE_NAME, "r+") as f:
        existing = json.load(f)
        existing.update(feeds)
        f.seek(0)
        json.dump(existing, f, indent=4, ensure_ascii=False)
        f.truncate()

def export_opml(output_file):
    root = ET.Element('opml', version='2.0')
    body = ET.SubElement(root, 'body')
    
    with open(FEEDS_FILE_NAME, "r") as f:
        feeds = json.load(f)
    
    for category, data in feeds.items():
        cat_outline = ET.SubElement(body, 'outline', text=category, title=category)
        for title, url in data["feeds"].items():
            ET.SubElement(cat_outline, 'outline', 
                         type='rss', text=title, title=title, xmlUrl=url)
    
    tree = ET.ElementTree(root)
    tree.write(output_file, encoding='utf-8', xml_declaration=True)
```

**Priority order for implementation:**
1. Gaps #1, #2, #5 (data integrity and debuggability)
2. Gaps #3, #4, #7 (reliability and network behavior)
3. Gaps #6, #9 (security and correctness)
4. Gaps #8, #10, #11 (efficiency and usability)
5. Gaps #12-15 (features and convenience)