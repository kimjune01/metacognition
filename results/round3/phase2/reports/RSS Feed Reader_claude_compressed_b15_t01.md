# Diagnostic Report: RSS Feed Reader

## Observations

This system is an RSS feed aggregator with the following working capabilities:

1. **Perceive:** Fetches RSS/Atom feeds from URLs defined in a JSON configuration file
2. **Cache:** Parses feed entries and normalizes them into a consistent structure (id, sourceName, pubDate, timestamp, url, title)
3. **Filter:** Implicit deduplication by using timestamp as unique ID (later entries with same timestamp overwrite earlier ones)
4. **Remember:** Persists parsed feeds to JSON files (`rss_{category}.json`) in a data directory
5. **Configuration management:** Copies bundled feeds.json on first run, merges new categories from updates
6. **Timezone handling:** Converts UTC timestamps to configured timezone (KST)
7. **Time-relative formatting:** Shows time for today's entries, date+time for older ones
8. **Category-based organization:** Processes feeds by category, with optional per-category author display

## Triage

### Critical gaps (blocks production use)

1. **Attend is shallow:** Sorting by timestamp (reverse chronological) exists, but no prioritization beyond recency. No diversity enforcement—if one source dominates by volume, it dominates the output.

2. **Filter is shallow:** Only implicit deduplication via ID collision. No validation of feed quality, content appropriateness, or duplicate content detection across different timestamps.

3. **Consolidate is absent:** No learning or adaptation. The system never updates based on what was previously fetched or user behavior.

4. **Error handling is broken:** Bare `except:` clauses silently fail or exit without logging. The fetch failure case calls `sys.exit(0)` (success code) when it should signal failure.

### Important gaps (affect reliability)

5. **Perceive has no resilience:** Network failures, timeouts, malformed XML, or slow feeds can stall the entire category or crash the process.

6. **Cache has no TTL:** Old cached files persist indefinitely. No indication of staleness. The `created_at` timestamp is written but never checked.

7. **Remember has no versioning:** Overwrites the entire result set each time. No incremental updates, no history, can't detect what's new since last run.

### Nice-to-have gaps (affect usability)

8. **No observability:** Minimal logging (`-Done/-Failed`). No metrics on fetch duration, entry counts, or error rates.

9. **No concurrency:** Fetches are sequential. With many feeds, updates will be slow.

10. **No user feedback loop:** System doesn't know which entries were read, clicked, or ignored.

## Plan

### 1. Fix Attend (shallow → complete)

**Problem:** No prioritization beyond time. Volume-heavy sources crowd out others.

**Changes needed:**
- Add a scoring function that considers: recency (current), source diversity, and entry quality signals (title length, has description, etc.)
- Implement interleaving: when building the final `rslt` list, ensure top N positions include entries from different sources
- Add configurable limits per source (e.g., max 5 entries per feed in top 20)

```python
# In get_feed_from_rss, after collecting entries:
def score_entry(entry, source_count):
    score = entry['timestamp']  # Base: recency
    score += (1000 / source_count)  # Boost underrepresented sources
    return score

# Track entries per source
source_counts = {}
scored_entries = []
for entry in rslt.values():
    source = entry['sourceName']
    source_counts[source] = source_counts.get(source, 0) + 1
    entry['_score'] = score_entry(entry, source_counts[source])
    scored_entries.append(entry)

rslt = sorted(scored_entries, key=lambda x: x['_score'], reverse=True)
```

### 2. Strengthen Filter

**Problem:** Accepts anything feedparser can parse. No quality gates.

**Changes needed:**
- Add validation: reject entries missing title or link
- Add content-based deduplication: detect near-duplicate titles using normalized text (lowercase, strip punctuation, check Levenshtein distance)
- Add per-feed health checks: if a feed returns zero valid entries N times in a row, flag it
- Add configurable blocklists (keywords in title/URL)

```python
import re
from difflib import SequenceMatcher

def normalize_title(title):
    return re.sub(r'[^\w\s]', '', title.lower().strip())

def is_duplicate(title, seen_titles, threshold=0.85):
    norm = normalize_title(title)
    for seen in seen_titles:
        if SequenceMatcher(None, norm, seen).ratio() > threshold:
            return True
    return False

# In feed loop:
seen_titles = []
if not feed.get('title') or not feed.get('link'):
    continue  # Reject incomplete entries
if is_duplicate(feed.title, seen_titles):
    continue  # Reject near-duplicates
seen_titles.append(normalize_title(feed.title))
```

### 3. Add Consolidate

**Problem:** System never learns or adapts.

**Changes needed:**
- Track fetch success rates per feed URL in a persistent `feed_health.json`
- Update feed priority based on: success rate, average entry quality, fetch speed
- After N failures, automatically disable a feed (with user notification)
- Store aggregate stats: total entries per source over time, which feeds consistently produce content

```python
# Load feed health on startup
HEALTH_FILE = os.path.join(p["path_data"], "feed_health.json")
if os.path.exists(HEALTH_FILE):
    with open(HEALTH_FILE) as f:
        feed_health = json.load(f)
else:
    feed_health = {}

# Update after each fetch:
feed_key = f"{category}:{source}"
if feed_key not in feed_health:
    feed_health[feed_key] = {'attempts': 0, 'successes': 0, 'last_success': None}

feed_health[feed_key]['attempts'] += 1
if fetch_succeeded:
    feed_health[feed_key]['successes'] += 1
    feed_health[feed_key]['last_success'] = int(time.time())

# Save updated health
with open(HEALTH_FILE, 'w') as f:
    json.dump(feed_health, f)

# Use health to skip broken feeds:
success_rate = feed_health[feed_key]['successes'] / feed_health[feed_key]['attempts']
if success_rate < 0.3 and feed_health[feed_key]['attempts'] > 5:
    continue  # Skip this feed
```

### 4. Fix error handling

**Problem:** Bare excepts hide problems, wrong exit codes.

**Changes needed:**
- Replace bare `except:` with specific exceptions
- Log all errors with context (which feed, what error)
- Return error info instead of calling `sys.exit`
- Add a summary of failures at the end

```python
import logging
import traceback

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

errors = []

try:
    d = feedparser.parse(url)
    if log:
        sys.stdout.write(" - Done\n")
except requests.exceptions.Timeout:
    errors.append({'source': source, 'url': url, 'error': 'timeout'})
    logger.error(f"Timeout fetching {url}")
    continue
except Exception as e:
    errors.append({'source': source, 'url': url, 'error': str(e)})
    logger.error(f"Failed to fetch {url}: {e}\n{traceback.format_exc()}")
    continue

# At end of function:
if errors and log:
    logger.warning(f"Completed with {len(errors)} errors")
```

### 5. Add Perceive resilience

**Problem:** No timeouts, retries, or circuit breaking.

**Changes needed:**
- Add explicit timeouts to feedparser (requires switching to requests + feedparser)
- Implement retry logic with exponential backoff
- Add connection pooling for concurrent fetches
- Add circuit breaker: if a feed fails 3 times in a row, stop trying for 1 hour

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
session.mount('http://', HTTPAdapter(max_retries=retries))
session.mount('https://', HTTPAdapter(max_retries=retries))

# Replace feedparser.parse(url) with:
response = session.get(url, timeout=10)
d = feedparser.parse(response.content)
```

### 6. Add Cache TTL awareness

**Problem:** Can't tell if cached data is stale.

**Changes needed:**
- Check `created_at` timestamp when loading cached files
- Add configurable TTL per category (e.g., news=15min, blogs=1hour)
- Surface staleness in the output (add `is_stale` flag)
- Add forced refresh mechanism

```python
def is_cache_stale(cache_file, ttl_seconds):
    if not os.path.exists(cache_file):
        return True
    with open(cache_file) as f:
        data = json.load(f)
    age = int(time.time()) - data.get('created_at', 0)
    return age > ttl_seconds

# Before returning cached data:
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
if is_cache_stale(cache_file, ttl_seconds=900):  # 15 min
    # Re-fetch
    pass
```

### 7. Add Remember versioning

**Problem:** Can't detect what's new or track history.

**Changes needed:**
- Before overwriting, load existing file and diff entry IDs
- Tag entries as `{new: true}` if not in previous version
- Maintain a separate `seen_ids.json` that accumulates all historical IDs
- Add incremental mode: only fetch and add new entries

```python
# Before writing rslt:
old_file = os.path.join(p["path_data"], f"rss_{category}.json")
old_ids = set()
if os.path.exists(old_file):
    with open(old_file) as f:
        old_data = json.load(f)
    old_ids = {e['id'] for e in old_data.get('entries', [])}

# Mark new entries
for entry in rslt['entries']:
    entry['is_new'] = entry['id'] not in old_ids

# Update seen_ids
seen_file = os.path.join(p["path_data"], "seen_ids.json")
if os.path.exists(seen_file):
    with open(seen_file) as f:
        seen_ids = set(json.load(f))
else:
    seen_ids = set()

seen_ids.update(entry['id'] for entry in rslt['entries'])

with open(seen_file, 'w') as f:
    json.dump(list(seen_ids), f)
```

### 8-10. Lower priority improvements

**Observability:** Add `logging` throughout, write metrics JSON (fetch_duration, entry_counts, error_counts per run)

**Concurrency:** Use `concurrent.futures.ThreadPoolExecutor` to fetch feeds in parallel (limit to 5-10 concurrent)

**User feedback:** Add a `mark_read(entry_id)` function that stores read IDs, then use in Attend scoring to deprioritize similar unread content