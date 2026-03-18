# Diagnostic Report: RSS Feed Reader

## Observations

This system is an RSS feed aggregator that:

1. **Perceives:** Fetches RSS/Atom feeds from URLs defined in a JSON configuration file
2. **Cache:** Parses feed entries and transforms them into a normalized JSON structure with timestamps, titles, URLs, and source names
3. **Filter:** Applies minimal filtering—rejects entries without valid time data (published or updated timestamps)
4. **Attend:** Sorts entries by timestamp (newest first) and uses entry timestamp as deduplication key
5. **Remember:** Persists results to category-specific JSON files (`rss_{category}.json`) with creation timestamp
6. **Consolidate:** *(Absent)* No learning or adaptation mechanism

**Working capabilities:**
- Multi-category feed management
- Timezone-aware timestamp handling (UTC to local conversion)
- User configuration inheritance from bundled defaults
- Graceful degradation on feed parsing failures
- Per-category author display toggle
- Human-readable date formatting (today shows time only, older shows date)

## Triage

### Critical gaps (ship-blockers):

1. **Shallow Filter (Stage 3):** Only rejects entries missing timestamps. Doesn't handle malformed data, duplicate titles, broken links, or invalid content. A single malicious feed can inject garbage.

2. **Shallow Attend (Stage 4):** Uses timestamp as deduplication key, which fails when multiple entries publish simultaneously or when feeds reformat timestamps. No diversity enforcement—one prolific source can dominate results.

3. **Missing Consolidate (Stage 6):** No history awareness. The system can't detect already-shown entries, trending topics, or dead feeds. It rewrites output files completely each run with no learning.

### Important gaps (production-readiness):

4. **Shallow Remember (Stage 5):** Overwrites state files atomically without backup. Concurrent writes would corrupt data. No retention policy means files grow unbounded.

5. **Fragile Perceive (Stage 1):** Silent failure handling (`sys.exit(0)` on parse errors). No timeout, retry logic, or rate limiting. One slow feed blocks all others in sequence.

6. **No observability:** Error swallowing makes debugging impossible in production. No metrics on feed health, fetch duration, or entry counts.

### Nice-to-have:

7. **No content validation:** Doesn't check if links resolve, if titles are non-empty, or if entries have minimum quality thresholds
8. **No incremental updates:** Always fetches full feeds even if only checking for new entries
9. **No user feedback loop:** Can't mark entries as read, favorite sources, or adjust ranking

## Plan

### 1. Fix Filter (Stage 3)

**Current code:**
```python
if not parsed_time:
    continue
```

**Add after timestamp parsing:**
```python
# Require title and valid URL
if not feed.title or not feed.title.strip():
    continue
if not feed.link or not feed.link.startswith(('http://', 'https://')):
    continue

# Deduplicate by content hash, not just timestamp
content_key = f"{feed.title}|{feed.link}"
content_hash = hash(content_key)
if content_hash in seen_hashes:
    continue
seen_hashes.add(content_hash)
```

Initialize `seen_hashes = set()` at function start.

### 2. Fix Attend (Stage 4)

**Replace deduplication logic:**
```python
# Current: rslt[entries["id"]] = entries  # timestamp collision overwrites

# New: Use composite key
unique_id = f"{ts}_{hash(feed.link)}"
entries["id"] = unique_id

rslt[unique_id] = entries
```

**Add diversity enforcement before writing:**
```python
# Limit entries per source
from collections import Counter
source_counts = Counter()
filtered_results = []

for entry in sorted(rslt.values(), key=lambda x: x['timestamp'], reverse=True):
    if source_counts[entry['sourceName']] < 10:  # max 10 per source
        filtered_results.append(entry)
        source_counts[entry['sourceName']] += 1

rslt = {"entries": filtered_results, "created_at": int(time.time())}
```

### 3. Add Consolidate (Stage 6)

**Before `get_feed_from_rss` writes new file:**
```python
history_file = os.path.join(p["path_data"], f"rss_{category}_history.json")

# Load what user has already seen
seen_entries = set()
if os.path.exists(history_file):
    with open(history_file, 'r') as f:
        seen_entries = set(json.load(f).get('seen_ids', []))

# Mark new vs. seen
for entry in rslt['entries']:
    entry['is_new'] = entry['id'] not in seen_entries

# Update history (keep last 1000)
all_ids = list(seen_entries) + [e['id'] for e in rslt['entries']]
with open(history_file, 'w') as f:
    json.dump({'seen_ids': all_ids[-1000:]}, f)
```

### 4. Fix Remember (Stage 5)

**Replace file write with atomic operation:**
```python
import tempfile

output_file = os.path.join(p["path_data"], f"rss_{category}.json")
fd, temp_path = tempfile.mkstemp(dir=p["path_data"], suffix='.json')

try:
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        f.write(json.dumps(rslt, ensure_ascii=False))
    shutil.move(temp_path, output_file)  # Atomic on POSIX
except:
    os.unlink(temp_path)
    raise
```

**Add retention policy:**
```python
# Before sorting, filter by age
cutoff = int(time.time()) - (7 * 86400)  # 7 days
rslt = {k: v for k, v in rslt.items() if v['timestamp'] > cutoff}
```

### 5. Fix Perceive (Stage 1)

**Add timeout and better error handling:**
```python
import requests

for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        
        # Use requests instead of feedparser.parse directly
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        d = feedparser.parse(response.content)
        
        if log:
            sys.stdout.write(" - Done\n")
            
    except requests.Timeout:
        if log:
            sys.stderr.write(f" - Timeout\n")
        continue  # Don't exit, try next feed
    except Exception as e:
        if log:
            sys.stderr.write(f" - Error: {e}\n")
        continue
```

**Add parallelization:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_one_feed(source, url, log):
    # Move inner try/except logic here
    pass

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_one_feed, src, url, log): src 
               for src, url in urls.items()}
    
    for future in as_completed(futures):
        result = future.result()
        if result:
            # Merge into rslt
            pass
```

### 6. Add Observability

**Wrap main execution:**
```python
import logging

logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# In get_feed_from_rss:
start = time.time()
logging.info(f"Fetching category {category}")

# After processing:
logging.info(f"Category {category}: {len(rslt['entries'])} entries in {time.time()-start:.2f}s")
```

**Track feed health:**
```python
# In catch blocks:
logging.error(f"Feed failed: {url} - {str(e)}")

# Store in feeds.json:
user[category]['feeds'][source]['last_success'] = int(time.time())
user[category]['feeds'][source]['failure_count'] = 0  # reset on success
```