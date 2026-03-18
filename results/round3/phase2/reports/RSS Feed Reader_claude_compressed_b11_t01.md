# Diagnostic Report: RSS Feed Reader

## Observations

This system fetches RSS feeds and stores them as JSON. Current capabilities:

1. **Perceive**: Downloads RSS feeds from configured URLs using feedparser
2. **Cache**: Writes parsed entries to JSON files (`rss_{category}.json`) with timestamp keys
3. **Filter**: Shallow implementation—rejects entries missing time metadata; deduplicates by timestamp (last write wins in dict)
4. **Attend**: Reverse chronological sort (most recent first)
5. **Remember**: Persists to disk between runs; manages user feed configuration with merge logic for bundled defaults
6. **Consolidate**: Absent—no learning or adaptation based on past results

The system handles multiple feed categories, preserves user customization while adding new defaults, and formats timestamps relative to today.

## Triage

### Critical gaps (blocking production use)

1. **Filter is shallow** — No quality validation, content deduplication, or error isolation
2. **Attend is minimal** — No actual selection happens; all filtered items are returned
3. **Perceive lacks resilience** — Single feed failure can corrupt output; no timeout handling

### Important gaps (reduce utility)

4. **Cache doesn't support retrieval** — Write-only; can't query "show me yesterday's tech feeds"
5. **Remember has no retention policy** — Files grow unbounded; no archival or cleanup
6. **Consolidate is absent** — Can't learn which feeds are stale, low-quality, or unread

### Nice-to-have gaps

7. **No observability** — Silent failures (bare `except: continue`); can't diagnose issues
8. **No incremental updates** — Always fetches all feeds; no "only new items" logic

## Plan

### 1. Filter: Add quality gates and error isolation

**Current problem**: Single malformed entry silently skips; duplicate content from different sources passes through; timestamp collisions overwrite.

**Changes needed**:
```python
# In get_feed_from_rss():

# Replace bare excepts with specific handling
except feedparser.ParserError as e:
    if log:
        sys.stderr.write(f"Parse failed for {source}: {e}\n")
    continue  # Isolated: one bad feed doesn't stop others

# Add content-based deduplication
def normalize_title(title):
    return title.lower().strip().replace(' ', '')

seen_content = set()
for feed in d.entries:
    # ... existing time parsing ...
    
    # Reject duplicates by content
    content_hash = normalize_title(feed.title)
    if content_hash in seen_content:
        continue
    seen_content.add(content_hash)
    
    # Reject if missing required fields
    if not getattr(feed, 'link', None) or not getattr(feed, 'title', None):
        continue
    
    # Handle timestamp collisions with composite key
    entries = {
        "id": f"{ts}_{hash(feed.link) % 10000}",  # Collision-resistant
        # ... rest unchanged ...
    }
```

### 2. Attend: Implement actual selection logic

**Current problem**: Returns everything. No limit on output size, no diversity enforcement, no relevance ranking.

**Changes needed**:
```python
# After building rslt dict, before writing:

def attend(entries, max_items=50, max_per_source=5):
    """Select top items with source diversity."""
    source_counts = {}
    selected = []
    
    for entry in entries:  # Already reverse-sorted by time
        source = entry['sourceName']
        if len(selected) >= max_items:
            break
        if source_counts.get(source, 0) >= max_per_source:
            continue  # Enforce diversity
        
        source_counts[source] = source_counts.get(source, 0) + 1
        selected.append(entry)
    
    return selected

rslt_list = [val for key, val in sorted(rslt.items(), reverse=True)]
rslt_list = attend(rslt_list)  # Apply attention
rslt = {"entries": rslt_list, "created_at": int(time.time())}
```

### 3. Perceive: Add timeout and retry logic

**Current problem**: `feedparser.parse()` blocks indefinitely on slow servers; no timeout configuration.

**Changes needed**:
```python
import socket

# At top of get_feed_from_rss():
original_timeout = socket.getdefaulttimeout()
socket.setdefaulttimeout(10)  # 10-second timeout

try:
    d = feedparser.parse(url)
    
    # Validate parse succeeded
    if d.bozo and not d.entries:
        raise feedparser.ParserError(d.bozo_exception)
        
finally:
    socket.setdefaulttimeout(original_timeout)
```

### 4. Cache: Enable temporal queries

**Current problem**: Can't answer "what did I fetch yesterday?" without parsing JSON; no index by date range.

**Changes needed**:
```python
# Create index file alongside data
index_entry = {
    "category": category,
    "fetch_time": int(time.time()),
    "item_count": len(rslt["entries"]),
    "time_range": {
        "newest": rslt["entries"][0]["timestamp"] if rslt["entries"] else None,
        "oldest": rslt["entries"][-1]["timestamp"] if rslt["entries"] else None,
    }
}

index_file = os.path.join(p["path_data"], "fetch_index.jsonl")
with open(index_file, "a") as f:
    f.write(json.dumps(index_entry) + "\n")

# Add retrieval function
def get_entries_between(category, start_ts, end_ts):
    """Query cache for entries in time range."""
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    with open(cache_file) as f:
        data = json.load(f)
    return [e for e in data["entries"] 
            if start_ts <= e["timestamp"] <= end_ts]
```

### 5. Remember: Add retention policy

**Current problem**: `rss_{category}.json` grows forever; old data never purges.

**Changes needed**:
```python
# Before writing rslt:
MAX_AGE_DAYS = 30
cutoff_ts = int(time.time()) - (MAX_AGE_DAYS * 86400)

# If file exists, merge with recent entries
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(cache_file):
    with open(cache_file) as f:
        old_data = json.load(f)
    
    # Keep recent old entries
    recent_old = [e for e in old_data.get("entries", []) 
                  if e["timestamp"] > cutoff_ts]
    
    # Merge with new, dedupe by ID
    all_entries = {e["id"]: e for e in recent_old}
    all_entries.update({e["id"]: e for e in rslt["entries"]})
    
    rslt["entries"] = [v for k, v in sorted(all_entries.items(), reverse=True)]
```

### 6. Consolidate: Track feed health

**Current problem**: No adaptation. Dead feeds keep getting fetched; high-quality sources aren't prioritized.

**Changes needed**:
```python
# Create feed health tracker
HEALTH_FILE = os.path.join(p["path_data"], "feed_health.json")

def update_feed_health(source, url, success, item_count):
    """Track success rate and productivity per feed."""
    health = {}
    if os.path.exists(HEALTH_FILE):
        with open(HEALTH_FILE) as f:
            health = json.load(f)
    
    key = f"{source}|{url}"
    if key not in health:
        health[key] = {"attempts": 0, "successes": 0, "total_items": 0}
    
    health[key]["attempts"] += 1
    if success:
        health[key]["successes"] += 1
        health[key]["total_items"] += item_count
    
    with open(HEALTH_FILE, "w") as f:
        json.dump(health, f)
    
    return health[key]

# In feed loop:
try:
    d = feedparser.parse(url)
    item_count = len([e for e in d.entries if should_include(e)])
    update_feed_health(source, url, True, item_count)
except Exception as e:
    update_feed_health(source, url, False, 0)

# Use health data to skip consistently failing feeds
def should_fetch(source, url):
    """Skip feeds with <20% success rate over last 10 attempts."""
    # Implementation left as exercise
    pass
```

### 7. Observability: Structured logging

**Current problem**: Bare `except` blocks hide errors; no way to debug "why didn't my feed update?"

**Changes needed**:
```python
import logging

logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s'
)

# Replace sys.stdout.write with:
logging.info(f"Fetching {url}")

# Replace bare except with:
except Exception as e:
    logging.error(f"Failed to parse {url}: {type(e).__name__}: {e}")
    continue
```

### 8. Incremental updates: Track last-fetch per feed

**Current problem**: Refetches entire feed history every run; wastes bandwidth.

**Changes needed**:
```python
# Store last-seen timestamp per feed
LAST_FETCH_FILE = os.path.join(p["path_data"], "last_fetch.json")

def get_last_fetch(category, source):
    if os.path.exists(LAST_FETCH_FILE):
        with open(LAST_FETCH_FILE) as f:
            data = json.load(f)
            return data.get(f"{category}|{source}", 0)
    return 0

# In feed processing:
last_ts = get_last_fetch(category, source)
new_entries = [e for e in d.entries if parse_time(e) > last_ts]
# ... process only new_entries ...
```