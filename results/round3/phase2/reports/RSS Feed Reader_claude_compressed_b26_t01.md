# Diagnostic Report: RSS Feed Reader

## Observations

This system currently implements a basic RSS feed aggregator with the following working capabilities:

1. **Perceive**: Fetches RSS feeds from URLs defined in a JSON configuration file
2. **Cache**: Parses RSS entries and normalizes them into a consistent schema (id, sourceName, pubDate, timestamp, url, title)
3. **Filter**: Implicitly filters out entries without valid timestamps (skips via `continue`)
4. **Attend**: Sorts entries by timestamp (reverse chronological) and uses timestamp as ID to deduplicate within a single fetch
5. **Remember**: Persists aggregated feeds to JSON files (one per category) in `~/.rreader/`
6. **Configuration management**: Merges bundled feeds with user feeds, preserving user customizations

The system processes multiple feed categories, handles timezone conversion to KST, and formats dates based on whether they're today or earlier.

## Triage

### Critical gaps (blocks production use)

1. **Consolidate is absent**: No learning or adaptation. The system always processes feeds the same way regardless of history.
2. **Filter is shallow**: Only rejects feeds without timestamps. No validation for duplicates across runs, malformed URLs, or content quality.
3. **Remember doesn't deduplicate across runs**: Each fetch overwrites the previous JSON file completely. Users lose historical context.
4. **No error resilience**: `sys.exit()` on feed failure kills the entire process instead of continuing with remaining feeds.

### Important gaps (reduce reliability)

5. **Attend is shallow**: Deduplication only works within a single fetch via dictionary keying. Same article from different sources uses timestamp as ID, causing collisions.
6. **Cache doesn't preserve metadata**: Raw feed data is immediately transformed and original HTML/summary content is discarded.
7. **No rate limiting or HTTP caching**: Will hammer feed servers on every run, risking IP bans.
8. **Silent failures**: `try/except: continue` patterns hide errors without logging what went wrong.

### Nice-to-have gaps (improve usability)

9. **No incremental updates**: Always fetches entire feed history rather than "since last run"
10. **No read/unread tracking**: Users can't mark items as consumed
11. **No feed health monitoring**: Dead feeds continue to be attempted indefinitely

## Plan

### 1. Add Consolidate stage (implement learning)

**Create a read-tracking and feed statistics system:**

```python
# Add to get_feed_from_rss(), before writing JSON:
stats_file = os.path.join(p["path_data"], f"rss_{category}_stats.json")
if os.path.exists(stats_file):
    with open(stats_file, "r") as f:
        stats = json.load(f)
else:
    stats = {"last_fetch": 0, "error_count": {}, "seen_ids": []}

# Track seen entries to enable smarter filtering next time
new_ids = [e["id"] for e in rslt["entries"]]
stats["seen_ids"] = list(set(stats["seen_ids"] + new_ids))[-10000:]  # Keep last 10k
stats["last_fetch"] = int(time.time())

with open(stats_file, "w") as f:
    json.dump(stats, f)

# Use stats to adjust behavior:
# - Skip feeds with high error_count
# - Filter out already-seen entries before returning
# - Adjust fetch frequency based on update patterns
```

### 2. Strengthen Filter stage

**Add multi-layer validation:**

```python
def validate_entry(feed, source, seen_ids):
    """Returns (valid, reason) tuple"""
    
    # Existing timestamp check
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        return False, "no_timestamp"
    
    ts = int(time.mktime(parsed_time))
    
    # Deduplicate against history
    if ts in seen_ids:
        return False, "duplicate"
    
    # Validate URL
    if not hasattr(feed, 'link') or not feed.link.startswith(('http://', 'https://')):
        return False, "invalid_url"
    
    # Validate title
    if not hasattr(feed, 'title') or len(feed.title.strip()) == 0:
        return False, "no_title"
    
    # Age filter (optional: skip items older than 30 days)
    age_days = (time.time() - ts) / 86400
    if age_days > 30:
        return False, "too_old"
    
    return True, "ok"

# Use in loop:
valid, reason = validate_entry(feed, source, stats["seen_ids"])
if not valid:
    if log:
        sys.stdout.write(f"  Skipped {feed.get('title', 'untitled')}: {reason}\n")
    continue
```

### 3. Fix Remember to accumulate history

**Change from overwrite to merge pattern:**

```python
# Load existing entries
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(existing_file):
    with open(existing_file, "r") as f:
        existing = json.load(f)
    existing_entries = {e["id"]: e for e in existing.get("entries", [])}
else:
    existing_entries = {}

# Merge new with old
for entry in rslt:
    existing_entries[entry["id"]] = entry

# Sort and limit (keep last 1000 entries)
merged = [val for key, val in sorted(existing_entries.items(), reverse=True)][:1000]

rslt = {"entries": merged, "created_at": int(time.time())}
```

### 4. Add error resilience

**Replace sys.exit with error tracking:**

```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            
            d = feedparser.parse(url)
            
            # Check for HTTP errors
            if hasattr(d, 'status') and d.status >= 400:
                raise Exception(f"HTTP {d.status}")
            
            if log:
                sys.stdout.write(" - Done\n")
                
        except Exception as e:
            error_msg = f"Failed to fetch {source}: {str(e)}"
            errors.append(error_msg)
            if log:
                sys.stdout.write(f" - Failed: {e}\n")
            
            # Update error stats for Consolidate stage
            if source not in stats.get("error_count", {}):
                stats["error_count"][source] = 0
            stats["error_count"][source] += 1
            
            continue  # Don't exit, continue with other feeds
        
        # ... process feed entries ...
    
    if errors and log:
        sys.stderr.write(f"\nErrors in {category}:\n" + "\n".join(errors) + "\n")
```

### 5. Fix Attend to use proper IDs

**Generate content-based IDs instead of timestamp-only:**

```python
import hashlib

# Replace:
entries = {
    "id": ts,
    # ...
}

# With:
content_hash = hashlib.md5(f"{feed.link}{feed.title}".encode()).hexdigest()[:8]
unique_id = f"{ts}_{content_hash}"  # Timestamp + content hash

entries = {
    "id": unique_id,
    "timestamp": ts,  # Keep for sorting
    # ...
}
```

### 6. Preserve more Cache metadata

**Store summary/content for later display:**

```python
entries = {
    "id": unique_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', '')[:500],  # First 500 chars
    "content": getattr(feed, 'content', [{}])[0].get('value', '')[:2000] if hasattr(feed, 'content') else '',
}
```

### 7. Add HTTP caching and rate limiting

**Implement conditional requests:**

```python
import time
from email.utils import formatdate

last_modified = stats.get("last_modified", {}).get(url)
etag = stats.get("etag", {}).get(url)

# Add headers for conditional requests
headers = {}
if last_modified:
    headers['If-Modified-Since'] = last_modified
if etag:
    headers['If-None-Match'] = etag

# Pass to feedparser (requires custom urllib)
# Or: implement delay between requests
time.sleep(1)  # Simple rate limiting: 1 second between feeds
```

### 8. Add structured logging

**Replace print statements:**

```python
import logging

logger = logging.getLogger(__name__)

def get_feed_from_rss(...):
    logger.info(f"Fetching {category} feeds")
    for source, url in urls.items():
        logger.debug(f"Fetching {source}: {url}")
        try:
            # ...
        except Exception as e:
            logger.error(f"Failed to fetch {source}", exc_info=True)
```