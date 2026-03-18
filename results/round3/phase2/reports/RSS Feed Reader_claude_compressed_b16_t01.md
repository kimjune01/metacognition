# Diagnostic Report: RSS Feed Reader

## Observations

This is an RSS feed aggregator that:

1. **Perceives**: Fetches RSS/Atom feeds from URLs defined in a JSON configuration file
2. **Cache**: Parses feed entries and extracts structured fields (title, link, timestamp, author, publication date)
3. **Filter**: Performs minimal validation—skips entries without parseable timestamps
4. **Attend**: Sorts entries by timestamp (newest first) and deduplicates by timestamp-as-ID
5. **Remember**: Writes aggregated results to category-specific JSON files (`rss_{category}.json`)
6. **Consolidate**: **Absent**—no learning or adaptation occurs

The system handles multiple feed categories, merges bundled and user feed configurations, formats timestamps for local timezone display, and can process all categories or a single target.

## Triage

### Critical gaps (blocks production use)

1. **Shallow Filter (Stage 3)**: Only validates timestamp existence. No duplicate detection across runs, no stale entry removal, no malformed URL rejection, no content validation.

2. **Shallow Attend (Stage 4)**: Timestamp collisions cause data loss (later entries overwrite earlier ones with same second-level timestamp). No diversity enforcement—one prolific source can dominate output.

3. **Absent Consolidate (Stage 6)**: System never learns which feeds are broken, slow, or low-quality. No adaptation to user behavior.

4. **Fragile Perceive (Stage 1)**: Bare `except:` clauses hide errors. Network timeouts not configured. No retry logic. One bad feed can crash the entire category refresh.

### Important gaps (limit usability)

5. **Shallow Remember (Stage 5)**: Overwrites entire history each run—no incremental updates, no item-level editing or deletion.

6. **No observability**: Silent failures. No logging of what was fetched, filtered, or why something failed.

7. **No rate limiting**: Could hammer feed servers or trigger rate limits.

### Nice-to-have gaps

8. **No feed metadata**: Doesn't track last successful fetch time, ETag headers, or conditional GET support.

9. **No output versioning**: Breaking changes to JSON schema would break downstream consumers.

## Plan

### 1. Fix Filter (Stage 3)

**Problem**: Accepts duplicate entries, stale content, and malformed data.

**Changes**:
```python
# In get_feed_from_rss(), after parsing each feed:

# Load existing data to check for duplicates
existing_ids = set()
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(existing_file):
    with open(existing_file, "r") as f:
        old_data = json.load(f)
        existing_ids = {e["id"] for e in old_data.get("entries", [])}

# Filter logic
MAX_AGE_DAYS = 30
now = time.time()

for feed in d.entries:
    # Existing timestamp parsing...
    
    # NEW: Validate URL format
    if not feed.link or not feed.link.startswith(('http://', 'https://')):
        continue
    
    # NEW: Check age
    if now - ts > (MAX_AGE_DAYS * 86400):
        continue
    
    # NEW: Skip duplicates (by URL or timestamp)
    if ts in existing_ids:
        continue
    
    # NEW: Validate title exists
    if not getattr(feed, 'title', '').strip():
        continue
```

### 2. Fix Attend (Stage 4)

**Problem**: Timestamp collisions and no diversity control.

**Changes**:
```python
# Replace timestamp-as-ID with collision-resistant ID
entries = {
    "id": f"{ts}_{hash(feed.link) % 10000}",  # Compound key
    # ... rest of fields
}

# Store in list, not dict (to preserve collisions)
rslt_list = []
for feed in d.entries:
    # ... validation ...
    rslt_list.append(entries)

# NEW: Diversity-aware ranking
from collections import defaultdict
source_counts = defaultdict(int)
MAX_PER_SOURCE = 5

diverse_results = []
for entry in sorted(rslt_list, key=lambda x: x["timestamp"], reverse=True):
    if source_counts[entry["sourceName"]] < MAX_PER_SOURCE:
        diverse_results.append(entry)
        source_counts[entry["sourceName"]] += 1

rslt = {"entries": diverse_results[:100], ...}  # Cap total
```

### 3. Fix Perceive (Stage 1)

**Problem**: Error handling loses information and crashes unpredictably.

**Changes**:
```python
import logging
from urllib.error import URLError
import socket

# At module level
logger = logging.getLogger(__name__)

# In get_feed_from_rss()
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        
        # NEW: Configure timeout
        d = feedparser.parse(url, timeout=10)
        
        # NEW: Check for parse errors
        if d.bozo and not isinstance(d.bozo_exception, 
                                     feedparser.CharacterEncodingOverride):
            logger.warning(f"Parse error for {url}: {d.bozo_exception}")
            if log:
                sys.stdout.write(f" - Parse warning\n")
        elif log:
            sys.stdout.write(" - Done\n")
            
    except (URLError, socket.timeout) as e:
        logger.error(f"Network error fetching {url}: {e}")
        if log:
            sys.stdout.write(f" - Failed: {e}\n")
        continue  # Don't crash, skip this feed
    except Exception as e:
        logger.exception(f"Unexpected error for {url}")
        continue
```

### 4. Add Consolidate (Stage 6)

**Problem**: No learning from past behavior.

**Changes**:
```python
# New file: feed_stats.json stores per-feed metrics
STATS_FILE = os.path.join(p["path_data"], "feed_stats.json")

def load_stats():
    if os.path.exists(STATS_FILE):
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    return {}

def update_stats(url, success, item_count, fetch_duration):
    stats = load_stats()
    if url not in stats:
        stats[url] = {
            "success_count": 0,
            "fail_count": 0,
            "total_items": 0,
            "avg_fetch_time": 0,
            "last_success": None
        }
    
    s = stats[url]
    if success:
        s["success_count"] += 1
        s["total_items"] += item_count
        s["last_success"] = int(time.time())
    else:
        s["fail_count"] += 1
    
    # Exponential moving average
    alpha = 0.3
    s["avg_fetch_time"] = (alpha * fetch_duration + 
                           (1 - alpha) * s["avg_fetch_time"])
    
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f)
    
    return s

# In get_feed_from_rss(), wrap each feed fetch
start = time.time()
try:
    d = feedparser.parse(url, timeout=10)
    items = len(d.entries)
    stats = update_stats(url, True, items, time.time() - start)
    
    # NEW: Skip feeds with poor track record
    if stats["fail_count"] > 10 and stats["success_count"] < 2:
        logger.info(f"Skipping unreliable feed: {url}")
        continue
        
except Exception as e:
    update_stats(url, False, 0, time.time() - start)
    raise
```

### 5. Fix Remember (Stage 5)

**Problem**: Loses history on every run.

**Changes**:
```python
# Load existing entries
existing_entries = []
if os.path.exists(existing_file):
    with open(existing_file, "r") as f:
        old_data = json.load(f)
        existing_entries = old_data.get("entries", [])

# Merge new and old (keeping recent ones)
MAX_ENTRIES = 1000
all_entries = rslt["entries"] + existing_entries

# Deduplicate by ID, keeping newest
seen_ids = set()
merged = []
for entry in all_entries:
    if entry["id"] not in seen_ids:
        seen_ids.add(entry["id"])
        merged.append(entry)

# Re-sort and trim
merged.sort(key=lambda x: x["timestamp"], reverse=True)
rslt["entries"] = merged[:MAX_ENTRIES]
```

### 6. Add observability

**Changes**:
```python
# At start of do()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
        logging.StreamHandler() if log else logging.NullHandler()
    ]
)

# Add metrics to output JSON
rslt["stats"] = {
    "fetch_time": time.time() - start_time,
    "feeds_attempted": len(urls),
    "feeds_succeeded": success_count,
    "entries_added": len(new_entries),
    "entries_filtered": filtered_count
}
```

### 7. Add rate limiting

**Changes**:
```python
import time

DELAY_BETWEEN_FEEDS = 1.0  # seconds

for source, url in urls.items():
    # ... fetch logic ...
    time.sleep(DELAY_BETWEEN_FEEDS)
```