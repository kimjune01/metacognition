# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently performs the following functions:

**Core RSS Processing**
- Fetches and parses RSS/Atom feeds from multiple sources using `feedparser`
- Extracts entries with titles, URLs, publication dates, authors, and timestamps
- Handles both `published_parsed` and `updated_parsed` time fields as fallbacks
- Converts UTC timestamps to a configurable timezone (currently KST/UTC+9)
- Formats dates contextually: "HH:MM" for today, "Mon DD, HH:MM" for other dates

**Data Management**
- Deduplicates entries across sources using timestamps as unique IDs
- Sorts entries reverse-chronologically (newest first)
- Persists aggregated feeds as JSON files per category (`rss_{category}.json`)
- Stores metadata including creation timestamp for each category file
- Maintains a `feeds.json` configuration file mapping categories to source URLs

**Configuration Handling**
- Creates `~/.rreader/` directory structure on first run
- Bundles default feeds configuration alongside the code
- Copies bundled feeds to user directory if missing
- Merges new categories from bundled config into existing user config without overwriting

**Execution Modes**
- Can fetch all categories or target a specific one
- Optional logging to stdout showing fetch progress
- Supports per-category "show_author" flag to display feed author vs source name

## Triage

### Critical (P0) - System will fail or produce wrong results

1. **No error recovery for individual feeds** - One bad URL kills entire category fetch
2. **Timestamp collision handling** - Multiple entries at same second overwrite each other
3. **Missing timezone awareness** - Code assumes parsed times are UTC but doesn't validate
4. **No feed validation** - Accepts any URL; malformed feeds cause silent failures

### High (P1) - Severely limits usability

5. **No rate limiting** - Will trigger 429/403 responses from servers during batch fetches
6. **No caching/conditional requests** - Refetches entire feeds even if unchanged (wastes bandwidth)
7. **No entry deduplication across fetches** - Same article appears multiple times if re-fetched
8. **No concurrency** - Fetches run serially; slow with many feeds
9. **No feed health monitoring** - Can't tell which feeds are stale/broken
10. **Hardcoded paths** - `~/.rreader/` not configurable, breaks on non-standard environments

### Medium (P2) - Production polish needed

11. **No entry content extraction** - Only saves title/URL; can't preview articles
12. **No read/unread tracking** - Can't mark entries as consumed
13. **No entry age limits** - Old entries accumulate indefinitely
14. **No logging framework** - Using print statements; can't adjust verbosity or redirect
15. **No metrics** - Can't monitor fetch success rates, latency, storage growth

### Low (P3) - Nice to have

16. **No OPML import/export** - Can't migrate from/to other readers
17. **No feed discovery** - Must manually add URLs
18. **No full-text search** - Can only browse chronologically
19. **No categories management UI** - Must edit JSON by hand

## Plan

### P0 Fixes

**1. Per-feed error isolation**
```python
# In get_feed_from_rss(), wrap each source in try/except:
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        # ... process entries ...
    except Exception as e:
        # Log error but continue with next feed
        if log:
            sys.stderr.write(f"✗ {source}: {e}\n")
        continue  # Don't let one failure stop others
```

**2. Collision-resistant IDs**
```python
# Replace timestamp-only ID with composite key:
entry_id = f"{ts}_{hash(feed.link)}"  # timestamp + URL hash
# Or use feed GUID if available:
entry_id = getattr(feed, 'id', f"{ts}_{hash(feed.link)}")
```

**3. Explicit timezone handling**
```python
# Validate parsed_time has timezone info:
if parsed_time.tm_zone is None:
    # Assume UTC if missing
    at = datetime.datetime(*parsed_time[:6], tzinfo=datetime.timezone.utc)
else:
    at = datetime.datetime(*parsed_time[:6]).astimezone(TIMEZONE)
```

**4. Feed validation**
```python
# After feedparser.parse():
if d.bozo:  # feedparser detected malformed feed
    raise ValueError(f"Invalid feed: {d.bozo_exception}")
if not d.entries:
    raise ValueError("Feed contains no entries")
```

### P1 Improvements

**5. Rate limiting**
```python
import time
from collections import defaultdict

# Add to module level:
_last_fetch = defaultdict(float)  # domain -> timestamp
MIN_INTERVAL = 1.0  # seconds between requests to same domain

# In fetch loop:
domain = urlparse(url).netloc
elapsed = time.time() - _last_fetch[domain]
if elapsed < MIN_INTERVAL:
    time.sleep(MIN_INTERVAL - elapsed)
_last_fetch[domain] = time.time()
```

**6. Conditional requests**
```python
# Store ETags/Last-Modified in metadata file:
# rss_{category}_meta.json: {"url": {"etag": "...", "modified": "..."}}

# Use with feedparser:
d = feedparser.parse(url, etag=stored_etag, modified=stored_modified)
if d.status == 304:  # Not modified
    continue  # Skip processing
# Update stored values after successful fetch
```

**7. Cross-fetch deduplication**
```python
# Load existing entries before adding new:
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(existing_file):
    with open(existing_file) as f:
        old_data = json.load(f)
        existing_ids = {e["id"] for e in old_data["entries"]}
else:
    existing_ids = set()

# When building rslt dict, check:
if entries["id"] not in existing_ids:
    rslt[entries["id"]] = entries
```

**8. Concurrent fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # Extract single-feed logic into separate function
    return source, feedparser.parse(url)

# Replace serial loop:
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source, d = future.result()
        # ... process d.entries ...
```

**9. Health monitoring**
```python
# Add to each category's JSON:
"feed_status": {
    "source_name": {
        "last_success": timestamp,
        "last_error": timestamp,
        "error_count": int,
        "entry_count": int
    }
}
# Update after each fetch attempt
```

**10. Configurable paths**
```python
# Replace hardcoded ~/.rreader/ with:
DEFAULT_DIR = os.getenv("RREADER_DIR", str(Path.home()) + "/.rreader/")
p = {"path_data": DEFAULT_DIR}
# Document environment variable in README
```

### P2 Enhancements

**11. Content extraction**
```python
# feedparser already provides content:
content = getattr(feed, 'summary', '') or getattr(feed, 'content', [{}])[0].get('value', '')
entries["preview"] = content[:500]  # First 500 chars
entries["content_hash"] = hash(content)  # For dedup by content
```

**12. Read tracking**
```python
# Add to entries:
entries["read"] = False
# Provide mark_read(category, entry_id) function:
def mark_read(category, entry_id):
    data = load_category_data(category)
    for entry in data["entries"]:
        if entry["id"] == entry_id:
            entry["read"] = True
    save_category_data(category, data)
```

**13. Age limits**
```python
# Add to config:
MAX_AGE_DAYS = 30

# Filter old entries:
cutoff = int(time.time()) - (MAX_AGE_DAYS * 86400)
rslt = [val for key, val in sorted(rslt.items(), reverse=True)
        if val["timestamp"] > cutoff]
```

**14. Proper logging**
```python
import logging

logger = logging.getLogger("rreader")
logger.setLevel(logging.INFO)

# Replace sys.stdout.write with:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}: {e}")

# Users can configure:
# logging.basicConfig(level=logging.DEBUG)
```

**15. Metrics collection**
```python
# Add global metrics dict:
metrics = {
    "fetches_total": 0,
    "fetches_failed": 0,
    "entries_new": 0,
    "fetch_duration_ms": []
}

# Update during execution, save to:
# ~/.rreader/metrics.json
```

### P3 Future Work

**16. OPML support**: Add `import_opml(file)` and `export_opml()` using `xml.etree`

**17. Feed discovery**: Parse HTML `<link rel="alternate">` tags from website URLs

**18. Search**: Build inverted index of title words → entry IDs, query with set intersection

**19. Management UI**: Simple CLI using `argparse` subcommands or TUI with `rich`/`textual`

---

**Recommended implementation order**: 1→2→4→5→7→8→10→14. This fixes crashes, adds resilience, improves performance, and establishes proper infrastructure for further enhancements.