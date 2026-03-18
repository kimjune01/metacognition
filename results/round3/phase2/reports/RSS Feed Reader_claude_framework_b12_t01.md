# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **Feed Discovery & Initialization**
   - Bundles a default `feeds.json` configuration file with the package
   - Copies bundled feeds to user data directory (`~/.rreader/`) on first run
   - Merges new categories from bundled config into existing user config on updates

2. **RSS Parsing**
   - Fetches and parses RSS/Atom feeds using `feedparser`
   - Extracts: title, link, publish date, author, and source name
   - Handles both `published_parsed` and `updated_parsed` timestamps
   - Falls back gracefully when timestamps are missing

3. **Data Normalization**
   - Converts timestamps to local timezone (KST/UTC+9)
   - Formats dates as "HH:MM" for today, "Mon DD, HH:MM" for older entries
   - Deduplicates entries by timestamp across sources within a category
   - Sorts entries reverse-chronologically

4. **Storage**
   - Writes one JSON file per category: `rss_{category}.json`
   - Stores entries array plus `created_at` timestamp
   - Preserves Unicode characters (non-ASCII) in output

5. **Operational Modes**
   - Can refresh all categories or target a single category
   - Optional logging to stdout
   - Can be run as module or standalone script

## Triage

### Critical Gaps

1. **No Error Recovery** – Failed feed fetches abort the entire category with `sys.exit(0)`, losing all progress. A production system should skip broken feeds and continue.

2. **No Rate Limiting** – Sequential HTTP requests with no delays will trigger 429 responses or bans from aggressive sites. Needs backoff.

3. **No Caching Headers** – Every run re-downloads full feeds. Should send `If-Modified-Since` / `ETag` headers and respect 304 responses.

4. **Silent Data Loss** – Entries without timestamps are silently dropped (`continue`). No logging means debugging is impossible.

### High-Priority Gaps

5. **No Concurrency** – Fetches are sequential. With 20+ feeds, refresh takes minutes. Should use `asyncio` or thread pool.

6. **No Staleness Detection** – Old cached data persists indefinitely. Should track last successful fetch per feed and flag stale sources.

7. **No Feed Validation** – Malformed URLs, dead domains, or redirect loops cause `feedparser` to hang or fail silently.

8. **Collision-Prone Deduplication** – Using Unix timestamp as ID causes collisions when multiple entries publish at the same second. Needs composite key or hash.

### Medium-Priority Gaps

9. **No Configuration Validation** – Malformed `feeds.json` crashes at runtime. Should validate schema on load.

10. **No Incremental Updates** – Always overwrites entire output file. Should append new entries and prune old ones.

11. **No User Feedback** – Progress indication only exists when `log=True`. CLI should show spinner or progress bar.

12. **Hardcoded Timezone** – KST is baked in. Should read from system locale or config.

### Low-Priority Gaps

13. **No Output Format Options** – Only writes JSON. Should support formats readers expect (OPML, HTML, etc.).

14. **No Content Extraction** – Only saves metadata. Many readers want full text or summaries.

15. **No Read/Unread Tracking** – Requires external system to track user state.

## Plan

### 1. Error Recovery
**Change:** Wrap feed fetch in try-except, log failure, continue loop.
```python
for source, url in urls.items():
    try:
        # existing fetch logic
    except Exception as e:
        if log:
            sys.stderr.write(f"✗ {source}: {e}\n")
        continue  # don't exit, skip to next feed
```

### 2. Rate Limiting
**Change:** Add configurable delay between requests.
```python
import time
FETCH_DELAY = 1.0  # seconds, make configurable

for source, url in urls.items():
    # fetch logic
    time.sleep(FETCH_DELAY)
```

### 3. Caching Headers
**Change:** Track ETags/Last-Modified per feed, send on subsequent requests.
```python
# In feeds.json schema, add per-feed:
"feeds": {
    "Source": {
        "url": "https://...",
        "etag": "...",
        "last_modified": "..."
    }
}

# In fetch logic:
headers = {}
if feed_meta.get("etag"):
    headers["If-None-Match"] = feed_meta["etag"]
d = feedparser.parse(url, request_headers=headers)
if d.status == 304:
    continue  # not modified
# Update etag/last_modified in feeds.json
```

### 4. Structured Logging
**Change:** Replace print statements with logging module.
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rreader")

# Replace:
sys.stdout.write(f"- {url}")
# With:
logger.info(f"Fetching {source} from {url}")

# For errors:
logger.warning(f"Skipping {source}: missing timestamp")
```

### 5. Concurrency
**Change:** Use `concurrent.futures.ThreadPoolExecutor` for I/O-bound fetches.
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_one(source, url, show_author):
    # existing per-feed logic, return dict or None
    pass

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_one, s, u, show_author): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        result = future.result()
        if result:
            rslt.update(result)
```

### 6. Staleness Detection
**Change:** Store last successful fetch timestamp per feed, flag if >24h old.
```python
# In output JSON:
"feeds": {
    "Source": {
        "last_success": 1704067200,
        "is_stale": false
    }
}

# During fetch:
now = int(time.time())
if now - feed_meta.get("last_success", 0) > 86400:
    feed_meta["is_stale"] = True
```

### 7. Feed Validation
**Change:** Pre-validate URLs, set timeout, handle redirects.
```python
from urllib.parse import urlparse

def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Invalid scheme: {parsed.scheme}")
    return url

# In feedparser.parse():
d = feedparser.parse(url, request_headers={"User-Agent": "rreader/1.0"}, 
                     timeout=10)
if d.bozo:  # feedparser's error flag
    logger.warning(f"Malformed feed: {d.bozo_exception}")
```

### 8. Deduplication Fix
**Change:** Use composite key or content hash instead of timestamp.
```python
import hashlib

def make_entry_id(feed):
    # Use link + title as unique identifier
    key = f"{feed.link}|{feed.title}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]

entries = {
    "id": make_entry_id(feed),  # not timestamp
    "timestamp": ts,
    # rest of fields
}
```

### 9. Configuration Validation
**Change:** Add JSON schema validation on load.
```python
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"}
            },
            "required": ["feeds"]
        }
    }
}

with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
    jsonschema.validate(RSS, FEEDS_SCHEMA)
```

### 10. Incremental Updates
**Change:** Load existing entries, merge new ones, prune old (>30 days).
```python
existing_path = os.path.join(p["path_data"], f"rss_{category}.json")
existing_entries = {}
if os.path.exists(existing_path):
    with open(existing_path) as f:
        data = json.load(f)
        existing_entries = {e["id"]: e for e in data["entries"]}

# After fetching new entries:
existing_entries.update(new_entries)
cutoff = int(time.time()) - (30 * 86400)
pruned = {k: v for k, v in existing_entries.items() if v["timestamp"] > cutoff}
```

### 11. Progress Feedback
**Change:** Use `tqdm` for progress bar.
```python
from tqdm import tqdm

for source, url in tqdm(urls.items(), desc=f"Fetching {category}"):
    # existing logic
```

### 12. Configurable Timezone
**Change:** Read from environment or config file.
```python
import os
import datetime

tz_offset = int(os.getenv("TZ_OFFSET", "9"))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```

### 13. Output Format Options
**Change:** Add `--format` CLI argument, dispatch to serializers.
```python
def write_opml(feeds, path):
    # Generate OPML XML
    pass

def write_html(entries, path):
    # Generate HTML page
    pass

# In do():
if output_format == "json":
    write_json(rslt, output_path)
elif output_format == "opml":
    write_opml(RSS, output_path)
```

### 14. Content Extraction
**Change:** Store `summary` or `content` fields when present.
```python
entries = {
    # existing fields
    "summary": getattr(feed, "summary", ""),
    "content": feed.content[0].value if hasattr(feed, "content") else ""
}
```

### 15. Read/Unread Tracking
**Change:** Add SQLite database to track user state.
```python
import sqlite3

conn = sqlite3.connect(os.path.join(p["path_data"], "state.db"))
conn.execute("""
    CREATE TABLE IF NOT EXISTS read_status (
        entry_id TEXT PRIMARY KEY,
        read_at INTEGER
    )
""")

# Mark as read:
conn.execute("INSERT OR IGNORE INTO read_status VALUES (?, ?)",
             (entry_id, int(time.time())))
```

---

**Implementation Priority:** Address Critical gaps (1-4) first—they cause data loss and operational failures. High-priority gaps (5-8) block production scalability. Medium and low gaps improve UX but the system functions without them.