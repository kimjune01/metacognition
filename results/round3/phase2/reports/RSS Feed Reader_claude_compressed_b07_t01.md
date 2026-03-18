# Diagnostic Report: RSS Feed Reader

## Observations

This system is an RSS feed aggregator with the following working capabilities:

1. **Perceive (Present):** Fetches RSS feeds from URLs using `feedparser`. Multiple feeds per category, multiple categories supported.

2. **Cache (Present but shallow):** 
   - Normalizes feed entries into a standard structure (id, sourceName, pubDate, timestamp, url, title)
   - Uses timestamp as unique ID
   - Stores in JSON files per category (`rss_{category}.json`)

3. **Filter (Absent):** No filtering logic. All parsed entries are accepted regardless of quality, duplicates, or validity.

4. **Attend (Present but shallow):**
   - Sorts entries by timestamp (newest first)
   - No deduplication: entries with identical timestamps overwrite each other in the dict
   - No diversity enforcement or ranking beyond recency

5. **Remember (Present):** Persists results to disk as JSON files. Includes `created_at` timestamp.

6. **Consolidate (Absent):** No learning or adaptation. Each run processes identically regardless of history.

**Current flow:** Download feeds → normalize → sort by time → save to JSON. Error handling is minimal (bare `except` blocks that either exit or continue silently).

## Triage

### Critical gaps (ship-blockers)

1. **Filter stage is missing entirely**
   - No validation of feed data quality
   - No duplicate detection across feeds or across time
   - Broken links, malformed titles, spam all pass through
   - Entries with identical timestamps silently overwrite each other

2. **Error handling is dangerous**
   - Bare `except:` clauses catch everything including KeyboardInterrupt
   - Failed feeds fail silently in non-log mode
   - No distinction between network errors, parse errors, and data errors

3. **Attend stage is too shallow**
   - Only criterion is timestamp recency
   - No deduplication: same article from multiple feeds appears multiple times
   - No diversity: one prolific source can dominate

### Important gaps (production readiness)

4. **Cache has no retrieval interface**
   - Can write JSON but no helper to read it back
   - No way to query "what did we already save?"
   - Makes deduplication impossible

5. **Consolidate stage completely absent**
   - Can't learn which feeds are reliable/broken
   - Can't adapt fetch frequency based on update patterns
   - Can't deprioritize sources that produce duplicates

6. **No rate limiting or politeness**
   - Fetches all feeds synchronously without delays
   - Could get IP-banned by aggressive feed hosts
   - No respect for feed's TTL hints

### Nice-to-have gaps

7. **Observability is poor**
   - Logging is boolean on/off, no levels
   - No metrics (success rate, fetch time, entry counts)
   - No structured logging for debugging

8. **Configuration is rigid**
   - Timezone hardcoded in config.py
   - No per-feed settings (timeout, user-agent, etc.)

## Plan

### 1. Add Filter stage

**What to build:**
- Create `filter_entry(entry, seen_urls)` function that returns True/False
- Check required fields exist and are non-empty: `title`, `url`, `timestamp`
- Validate URL format using `urllib.parse`
- Deduplicate by URL (case-insensitive, strip fragments)
- Optionally: check title length (reject < 5 chars or > 500 chars), reject future timestamps

**Where to insert:**
```python
# In get_feed_from_rss, after creating entries dict:
if not filter_entry(entries, seen_urls):
    continue
seen_urls.add(entries['url'].lower().split('#')[0])
```

**Add to state:**
- Pass `seen_urls=set()` parameter through function
- Load previously saved URLs from disk to persist across runs

### 2. Fix error handling

**Specific changes:**
```python
# Replace bare except:
except Exception as e:
    if log:
        sys.stderr.write(f" - Failed: {type(e).__name__}: {e}\n")
    continue  # Don't exit, continue to next feed
```

**Add timeout:**
```python
# Before feedparser.parse:
import socket
socket.setdefaulttimeout(30)
```

**Separate error types:**
- Catch `URLError` for network issues
- Catch `KeyboardInterrupt` and re-raise
- Log different errors differently

### 3. Improve Attend stage

**Add deduplication:**
```python
def normalize_url(url):
    """Strip tracking params, fragments, normalize case"""
    parsed = urllib.parse.urlparse(url.lower())
    # Remove common tracking params
    query = urllib.parse.parse_qs(parsed.query)
    cleaned = {k: v for k, v in query.items() 
               if k not in ['utm_source', 'utm_medium', 'utm_campaign']}
    return parsed._replace(query=urllib.parse.urlencode(cleaned, doseq=True), 
                          fragment='').geturl()

# Use normalized URL as key instead of timestamp
rslt[normalize_url(entries["url"])] = entries
```

**Add diversity:**
```python
# After sorting, limit entries per source:
def diversify(entries, max_per_source=5):
    counts = {}
    result = []
    for e in entries:
        source = e['sourceName']
        if counts.get(source, 0) < max_per_source:
            result.append(e)
            counts[source] = counts.get(source, 0) + 1
    return result

rslt['entries'] = diversify(rslt['entries'])
```

### 4. Add Cache retrieval

**Create helper function:**
```python
def load_cached_entries(category):
    """Load previously saved entries for a category"""
    path = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('entries', [])
    except (json.JSONDecodeError, IOError):
        return []
```

**Use for deduplication:**
```python
# At start of get_feed_from_rss:
previous_entries = load_cached_entries(category)
seen_urls = {normalize_url(e['url']) for e in previous_entries}
```

### 5. Add Consolidate stage

**Track feed reliability:**
```python
# Create stats file: feed_stats.json
# Structure: {category: {source: {success_count, fail_count, last_success_ts, avg_new_items}}}

def update_feed_stats(category, source, success, new_item_count=0):
    stats_file = os.path.join(p["path_data"], "feed_stats.json")
    stats = {}
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            stats = json.load(f)
    
    if category not in stats:
        stats[category] = {}
    if source not in stats[category]:
        stats[category][source] = {
            'success': 0, 'fail': 0, 
            'last_success': None, 'avg_items': 0
        }
    
    s = stats[category][source]
    if success:
        s['success'] += 1
        s['last_success'] = int(time.time())
        # Running average
        s['avg_items'] = (s['avg_items'] * 0.9) + (new_item_count * 0.1)
    else:
        s['fail'] += 1
    
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
```

**Use stats to skip bad feeds:**
```python
# Before parsing each feed:
if should_skip_feed(category, source):  # e.g., >80% fail rate
    if log:
        sys.stdout.write(f"- {url} - Skipped (unreliable)\n")
    continue
```

### 6. Add rate limiting

**Insert delays:**
```python
import time
# After each feed fetch:
time.sleep(1)  # Be polite, 1 second between requests
```

**Add per-feed timeout:**
```python
# Use requests instead of feedparser directly for better control:
import requests
response = requests.get(url, timeout=30, 
                       headers={'User-Agent': 'rreader/1.0'})
d = feedparser.parse(response.content)
```

### 7. Improve observability

**Add logging levels:**
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# Replace sys.stdout.write with:
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse {url}: {e}")
```

**Add metrics:**
```python
# At end of get_feed_from_rss:
metrics = {
    'feeds_attempted': len(urls),
    'feeds_succeeded': success_count,
    'entries_fetched': len(rslt['entries']),
    'entries_filtered': filtered_count,
    'duration_seconds': time.time() - start_time
}
logger.info(f"Category {category} complete: {metrics}")
```