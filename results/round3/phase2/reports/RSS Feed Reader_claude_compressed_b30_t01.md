# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently performs the following:

1. **Perceives** RSS feeds by fetching from configured URLs via `feedparser`
2. **Caches** parsed entries in memory using a dictionary keyed by timestamp
3. **Filters** entries minimally (requires `published_parsed` or `updated_parsed`, silently skips failures)
4. **Attends** by sorting entries by timestamp (reverse chronological) and deduplicating by timestamp ID
5. **Remembers** by writing JSON snapshots to disk (`rss_{category}.json`)
6. **Does NOT consolidate** - no backward pass, no learning, no adaptation

**Working capabilities:**
- Multi-source RSS aggregation per category
- Timezone conversion (UTC → configured timezone)
- Date formatting (today vs. older)
- User feed configuration with fallback to bundled defaults
- Per-category author display toggle
- Incremental category updates

## Triage

### Critical gaps (breaks in production)

1. **Filter is shallow** - Silent failure handling masks data quality issues; no validation of feed content, URL reachability, or entry completeness
2. **Remember lacks read path** - System writes snapshots but never reads them back; each run starts from scratch
3. **Attend has collision risk** - Timestamp-based IDs will collide if two entries publish in the same second
4. **Perceive has no retry/timeout** - Network failures cause silent data loss or full system exit

### Important gaps (limits usefulness)

5. **Consolidate is absent** - No learning from user behavior, no feed quality tracking, no adaptive refresh rates
6. **Cache is not queryable** - In-memory dictionary discarded after write; no incremental updates, no "since last run" queries
7. **Attend lacks diversity** - No per-source balancing; a high-volume feed dominates output

### Quality-of-life gaps

8. **No observability** - `log` parameter barely used; can't diagnose why feeds fail or entries disappear
9. **No rate limiting** - Hammers all feeds sequentially; could be blocked by aggressive servers
10. **No entry content** - Only captures title/link; no description/summary for preview

## Plan

### 1. Filter is shallow
**Change:** Add explicit validation and error reporting pipeline.

```python
def validate_entry(feed, source, url):
    """Returns (is_valid, error_reason, normalized_entry)"""
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        return False, "no_timestamp", None
    
    if not hasattr(feed, 'link') or not feed.link:
        return False, "no_link", None
    
    if not hasattr(feed, 'title') or not feed.title:
        return False, "no_title", None
    
    # Validate timestamp is reasonable (not future, not ancient)
    ts = int(time.mktime(parsed_time))
    now = int(time.time())
    if ts > now + 3600 or ts < now - (365 * 86400):
        return False, "invalid_timestamp", None
    
    return True, None, {parsed_time: ..., link: feed.link, title: feed.title}

# In get_feed_from_rss, track rejections:
stats = {"accepted": 0, "rejected": defaultdict(int)}
for feed in d.entries:
    valid, reason, entry_data = validate_entry(feed, source, url)
    if not valid:
        stats["rejected"][reason] += 1
        continue
    stats["accepted"] += 1
    # ... process entry_data

# Write stats alongside results for observability
rslt["stats"] = dict(stats)
```

### 2. Remember lacks read path
**Change:** Load previous snapshot and merge with new entries.

```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    output_path = os.path.join(p["path_data"], f"rss_{category}.json")
    
    # Load existing entries
    existing = {}
    if os.path.exists(output_path):
        with open(output_path, "r", encoding="utf-8") as f:
            prev = json.load(f)
            existing = {e["id"]: e for e in prev.get("entries", [])}
    
    rslt = existing.copy()  # Start with what we had
    
    # ... fetch and parse feeds, adding to rslt ...
    
    # Keep only last N days to prevent unbounded growth
    cutoff = int(time.time()) - (7 * 86400)
    rslt = {k: v for k, v in rslt.items() if v["timestamp"] > cutoff}
```

### 3. Attend has collision risk
**Change:** Use compound key with counter for same-second entries.

```python
# Track used IDs per timestamp
id_counters = defaultdict(int)

def make_unique_id(ts):
    counter = id_counters[ts]
    id_counters[ts] += 1
    return f"{ts}_{counter}" if counter > 0 else str(ts)

entries = {
    "id": make_unique_id(ts),
    # ... rest of entry
}
```

### 4. Perceive has no retry/timeout
**Change:** Add timeout and retry with exponential backoff.

```python
import requests
from urllib.parse import urlparse

def fetch_with_retry(url, max_retries=3, timeout=10):
    """Returns (success, feed_data_or_error)"""
    for attempt in range(max_retries):
        try:
            # Use requests with timeout instead of feedparser's default
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            d = feedparser.parse(response.content)
            return True, d
        except requests.Timeout:
            if attempt == max_retries - 1:
                return False, "timeout"
            time.sleep(2 ** attempt)  # 1s, 2s, 4s
        except requests.RequestException as e:
            return False, f"network_error: {str(e)}"
    return False, "max_retries_exceeded"

# In get_feed_from_rss:
success, result = fetch_with_retry(url)
if not success:
    stats["feed_errors"][source] = result
    continue
d = result
```

### 5. Consolidate is absent
**Change:** Track feed health and adjust refresh strategy.

```python
# New file: rss_{category}_meta.json
def update_feed_metadata(category, source, stats):
    """Track success rate, last fetch time, avg entry count"""
    meta_path = os.path.join(p["path_data"], f"rss_{category}_meta.json")
    
    meta = {}
    if os.path.exists(meta_path):
        with open(meta_path, "r") as f:
            meta = json.load(f)
    
    if source not in meta:
        meta[source] = {"success": 0, "failure": 0, "last_fetch": None}
    
    meta[source]["last_fetch"] = int(time.time())
    if stats["accepted"] > 0:
        meta[source]["success"] += 1
    else:
        meta[source]["failure"] += 1
    
    # Calculate reliability score
    total = meta[source]["success"] + meta[source]["failure"]
    meta[source]["reliability"] = meta[source]["success"] / total if total > 0 else 0
    
    with open(meta_path, "w") as f:
        json.dump(meta, f)

# Use reliability to skip consistently failing feeds
def should_fetch(category, source):
    # ... load meta ...
    if source in meta and meta[source]["reliability"] < 0.1 and meta[source]["failure"] > 10:
        return False  # Disable dead feeds
    return True
```

### 6. Cache is not queryable
**Change:** Use SQLite for structured storage.

```python
import sqlite3

def init_db(category):
    db_path = os.path.join(p["path_data"], f"rss_{category}.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS entries (
            id TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            url TEXT,
            timestamp INTEGER,
            pub_date TEXT,
            created_at INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON entries(timestamp DESC)")
    return conn

# Replace dictionary with DB inserts
conn.execute("INSERT OR REPLACE INTO entries VALUES (?, ?, ?, ?, ?, ?, ?)",
             (entry_id, source, title, url, timestamp, pub_date, int(time.time())))

# Query support
def get_entries_since(category, since_ts):
    conn = init_db(category)
    return conn.execute(
        "SELECT * FROM entries WHERE timestamp > ? ORDER BY timestamp DESC",
        (since_ts,)
    ).fetchall()
```

### 7. Attend lacks diversity
**Change:** Implement round-robin or quota-based selection.

```python
def diversify_entries(entries, max_per_source=5):
    """Limit entries per source to prevent domination"""
    source_counts = defaultdict(int)
    diverse = []
    
    for entry in entries:  # Already sorted by timestamp
        source = entry["sourceName"]
        if source_counts[source] < max_per_source:
            diverse.append(entry)
            source_counts[source] += 1
    
    return diverse

rslt = diversify_entries(sorted_entries, max_per_source=5)
```

### 8. No observability
**Change:** Structured logging throughout.

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
        logging.StreamHandler(sys.stdout) if log else logging.NullHandler()
    ]
)

logger = logging.getLogger(__name__)

# Replace sys.stdout.write with:
logger.info(f"Fetching {url} for {source}")
logger.warning(f"Rejected {count} entries from {source}: {reason}")
logger.error(f"Failed to fetch {url}: {error}")
```

### 9. No rate limiting
**Change:** Add delays between requests.

```python
import time

def fetch_all_feeds(urls, delay=1.0):
    results = {}
    for i, (source, url) in enumerate(urls.items()):
        if i > 0:
            time.sleep(delay)  # Be nice to servers
        success, data = fetch_with_retry(url)
        results[source] = (success, data)
    return results
```

### 10. No entry content
**Change:** Capture and store description/summary.

```python
entries = {
    "id": entry_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', '')[:500],  # First 500 chars
    "content": getattr(feed, 'content', [{}])[0].get('value', '')[:1000] if hasattr(feed, 'content') else ''
}
```