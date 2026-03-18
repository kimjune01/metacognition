# Diagnostic Report: RSS Feed Reader System

## Observations

This system fetches RSS feeds and writes them to local JSON files. Current working capabilities:

1. **Perceive**: Fetches RSS feeds from URLs using `feedparser`
2. **Cache**: Writes parsed entries to `rss_{category}.json` files with timestamp-indexed structure
3. **Filter**: Basic implicit filtering - skips entries without time information, deduplicates by timestamp (using timestamp as ID)
4. **Attend**: Sorts entries by timestamp (reverse chronological), includes all filtered items
5. **Remember**: Persists feed entries to disk in JSON format
6. **Consolidate**: Absent - no learning or adaptation based on past fetches

The system handles multiple feed categories, merges bundled and user feed configurations, and formats timestamps for display.

## Triage

### Critical gaps (blocks production use)

1. **Filter is shallow** - Only checks for presence of time fields. No validation for malformed data, duplicate URLs across different timestamps, or content quality.

2. **Attend is shallow** - No prioritization beyond chronological sorting. Returns everything, which scales poorly. No diversity enforcement (one prolific source can dominate).

3. **Error handling is broken** - Bare `except` clauses swallow errors silently or exit with ambiguous status codes.

4. **Consolidate is absent** - System never learns which feeds are dead, slow, or high-quality. Processes identically every run.

### Important gaps (limit usefulness)

5. **Remember doesn't accumulate** - Each fetch overwrites the previous file. Historical entries are lost. Can't track "read/unread" state.

6. **Perceive has no timeout** - Slow feeds block the entire process. No concurrent fetching.

7. **Cache doesn't handle conflicts** - Timestamp collision strategy (last-write-wins via dictionary) is implicit and lossy.

### Minor gaps (polish issues)

8. **No observability** - Logging is optional and incomplete. No metrics on fetch times, failure rates, or entry counts.

9. **No configuration validation** - System assumes `feeds.json` structure is correct.

## Plan

### 1. Strengthen Filter

**Changes needed:**
```python
def validate_entry(feed, source):
    """Return (is_valid, normalized_entry) or (False, None)"""
    # Check required fields
    if not getattr(feed, 'link', None):
        return False, None
    if not getattr(feed, 'title', '').strip():
        return False, None
    
    # Validate URL format
    if not feed.link.startswith(('http://', 'https://')):
        return False, None
    
    # Check for placeholder/empty content
    if feed.title.lower() in ['untitled', 'no title', '']:
        return False, None
        
    return True, feed
```

**Integration point:** Call before creating `entries` dict. Accumulate rejection reasons for logging.

### 2. Implement real Attend

**Changes needed:**
```python
def attend_entries(entries_list, max_items=50, max_per_source=10):
    """Rank and limit entries with diversity enforcement"""
    # Group by source
    by_source = {}
    for entry in entries_list:
        source = entry['sourceName']
        by_source.setdefault(source, []).append(entry)
    
    # Interleave sources, cap per source
    result = []
    source_iters = {s: iter(items[:max_per_source]) 
                    for s, items in by_source.items()}
    
    while len(result) < max_items and source_iters:
        for source in list(source_iters.keys()):
            try:
                result.append(next(source_iters[source]))
            except StopIteration:
                del source_iters[source]
            if len(result) >= max_items:
                break
                
    return result
```

**Integration point:** Apply after sorting, before writing JSON. Add `max_items` to category config.

### 3. Fix error handling

**Changes needed:**
```python
# Replace this:
except:
    sys.exit(" - Failed\n" if log else 0)

# With this:
except Exception as e:
    error_msg = f" - Failed: {type(e).__name__}: {e}\n"
    if log:
        sys.stderr.write(error_msg)
    continue  # Skip this feed, process others
```

**Additional:** Wrap the outer loop to catch fatal errors separately. Return success/failure counts.

### 4. Add Consolidate stage

**Changes needed:**
```python
# New file: feed_stats.json structure
{
  "feeds": {
    "https://example.com/feed": {
      "last_success": timestamp,
      "last_failure": timestamp,
      "failure_count": 3,
      "avg_fetch_time": 1.2,
      "avg_items_per_fetch": 15,
      "quality_score": 0.85
    }
  }
}

def update_feed_stats(url, success, fetch_time, item_count):
    """Update historical performance data"""
    stats = load_stats()  # from feed_stats.json
    
    if url not in stats['feeds']:
        stats['feeds'][url] = {
            'failure_count': 0,
            'fetch_times': [],
            'item_counts': []
        }
    
    feed_stat = stats['feeds'][url]
    
    if success:
        feed_stat['last_success'] = time.time()
        feed_stat['failure_count'] = 0
        feed_stat['fetch_times'].append(fetch_time)
        feed_stat['item_counts'].append(item_count)
    else:
        feed_stat['last_failure'] = time.time()
        feed_stat['failure_count'] += 1
    
    # Skip feeds with 5+ consecutive failures
    # Deprioritize slow feeds (timeout after 10s)
    
    save_stats(stats)
```

**Integration point:** Call after each `feedparser.parse()`. Check stats before fetching to skip known-bad feeds.

### 5. Implement accumulative Remember

**Changes needed:**
```python
# Load existing entries
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(existing_file):
    with open(existing_file, 'r') as f:
        existing = json.load(f)
    existing_entries = {e['id']: e for e in existing.get('entries', [])}
else:
    existing_entries = {}

# Merge with new entries (new entries take precedence)
existing_entries.update(rslt)  # rslt is the dict of new entries

# Limit history (keep last 1000 items)
all_entries = sorted(existing_entries.values(), 
                     key=lambda x: x['timestamp'], 
                     reverse=True)[:1000]

# Add read/unread tracking
for entry in all_entries:
    if 'read' not in entry:
        entry['read'] = False
```

**Integration point:** Replace the current `rslt = [val for key, val in sorted...]` logic.

### 6. Add fetch timeouts and concurrency

**Changes needed:**
```python
import concurrent.futures
import socket

# Set global timeout
socket.setdefaulttimeout(10)

def fetch_one_feed(source, url, log):
    """Fetch single feed with timeout"""
    try:
        start = time.time()
        d = feedparser.parse(url)
        fetch_time = time.time() - start
        return source, d, fetch_time, None
    except Exception as e:
        return source, None, 0, e

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    # Fetch concurrently with ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(fetch_one_feed, source, url, log): (source, url)
            for source, url in urls.items()
        }
        
        for future in concurrent.futures.as_completed(future_to_url):
            source, result, fetch_time, error = future.result()
            if error:
                if log:
                    sys.stderr.write(f"- {source} failed: {error}\n")
                continue
            # Process result...
```

### 7. Handle timestamp collisions explicitly

**Changes needed:**
```python
# Replace: rslt[entries["id"]] = entries
# With:
entry_id = entries["id"]
collision_suffix = 0
while entry_id in rslt:
    collision_suffix += 1
    entry_id = f"{entries['id']}_{collision_suffix}"
entries["id"] = entry_id
rslt[entry_id] = entries
```

### 8. Add structured logging

**Changes needed:**
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Replace sys.stdout.write with:
logging.info(f"Fetching {url}")
logging.info(f"Retrieved {len(d.entries)} entries")
logging.error(f"Failed to fetch {url}: {e}")

# Add summary stats:
logging.info(f"Category {category}: {len(rslt)} total entries, "
             f"{success_count}/{total_count} feeds succeeded")
```