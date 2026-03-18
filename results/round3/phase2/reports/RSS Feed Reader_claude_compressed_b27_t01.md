# Diagnostic Report: RSS Reader System

## Observations

This system currently implements an RSS feed aggregator with the following working capabilities:

1. **Perceive**: Fetches RSS feeds from multiple sources via `feedparser.parse(url)`
2. **Cache**: Parses and normalizes feed entries into a consistent JSON structure with standardized fields (id, sourceName, pubDate, timestamp, url, title)
3. **Filter**: Minimal filtering exists - entries without valid timestamps are silently skipped via `continue` statements
4. **Attend**: Sorts entries by timestamp (reverse chronological) and deduplicates by using timestamp as dictionary key
5. **Remember**: Persists aggregated feeds to disk as `rss_{category}.json` files
6. **Consolidate**: **Absent** - no learning or adaptation occurs

The system handles feed configuration management (bundled vs user feeds), supports multiple categories, and provides timezone-aware date formatting.

## Triage

### Critical gaps (production blockers):

1. **Shallow Filter** - Only rejects entries missing timestamps; no validation of URLs, no detection of malformed data, no duplicate detection across runs, no spam filtering
2. **Shallow Attend** - Deduplication by timestamp is fragile (collisions possible); no relevance ranking, no diversity enforcement across sources, no limit on result size
3. **Missing Consolidate** - System never learns from user behavior or past results; cannot improve recommendations or adjust source weights
4. **Fragile Perceive** - Bare `except:` clauses swallow all errors; no retry logic, no timeout handling, no circuit breaker for failing feeds

### Important gaps (reliability/usability):

5. **Shallow Remember** - Overwrites entire result set each run; no incremental updates, no history tracking, no ability to mark items as read
6. **No feedback loop** - User interactions (clicks, reads, dismissals) are not captured anywhere
7. **No error visibility** - Failed feeds silently disappear from results; users can't tell what's broken

### Minor gaps (polish):

8. **Poor observability** - Optional logging only, no metrics, no monitoring hooks
9. **Synchronous blocking** - Fetches feeds sequentially; slow for many sources

## Plan

### 1. Strengthen Filter (Critical)

**What to add:**
- URL validation using `urllib.parse` before storage
- Content validation: check for required fields (title, link), reject empty/malformed entries
- Duplicate detection across runs by maintaining a seen-items database
- Content quality checks: minimum title length, blacklist patterns

**Concrete changes:**
```python
# In get_feed_from_rss(), after parsing each feed entry:
def validate_entry(feed):
    if not getattr(feed, 'title', '').strip():
        return False, "missing_title"
    if not getattr(feed, 'link', '').strip():
        return False, "missing_link"
    if len(feed.title.strip()) < 10:
        return False, "title_too_short"
    # Check against seen items
    if is_duplicate(feed.link):
        return False, "duplicate"
    return True, None

# Add before entries dict creation:
valid, reason = validate_entry(feed)
if not valid:
    if log:
        sys.stdout.write(f" (rejected: {reason})")
    continue
```

### 2. Strengthen Attend (Critical)

**What to add:**
- Replace timestamp-as-key with proper deduplication using content hashing
- Implement result limiting (e.g., top 100 per category)
- Add source diversity scoring to prevent one prolific source from dominating
- Add relevance signals (recency + source weight)

**Concrete changes:**
```python
import hashlib

def entry_hash(feed):
    # Dedupe by content, not timestamp
    return hashlib.md5(f"{feed.link}|{feed.title}".encode()).hexdigest()

# Replace rslt dict with:
rslt = {}  # key: content_hash
for feed in d.entries:
    h = entry_hash(feed)
    if h in rslt:
        continue  # Already seen this content
    # ... existing validation ...
    rslt[h] = entries

# After sorting, add diversity filtering:
def diversify(entries, max_per_source=5, total_limit=100):
    source_counts = {}
    result = []
    for e in entries:
        src = e["sourceName"]
        if source_counts.get(src, 0) >= max_per_source:
            continue
        source_counts[src] = source_counts.get(src, 0) + 1
        result.append(e)
        if len(result) >= total_limit:
            break
    return result

rslt = diversify(rslt)
```

### 3. Implement Consolidate (Critical)

**What to add:**
- Read history to track which items were actually clicked/read
- Adjust source weights based on engagement
- Store and apply learned preferences

**Concrete changes:**
```python
# New file: rreader/analytics.py
def record_interaction(item_id, action):
    """action: 'click', 'dismiss', etc."""
    history_file = os.path.join(p["path_data"], "interactions.jsonl")
    with open(history_file, "a") as f:
        f.write(json.dumps({
            "item_id": item_id,
            "action": action,
            "timestamp": time.time()
        }) + "\n")

def compute_source_weights():
    """Returns dict of {source_name: weight_multiplier}"""
    # Read interactions.jsonl
    # Calculate click-through rate per source
    # Return weights (default 1.0, range 0.5-2.0)
    pass

# In get_feed_from_rss(), after creating entries:
weights = compute_source_weights()
entries["score"] = ts * weights.get(author, 1.0)

# Sort by score instead of raw timestamp:
rslt = [val for key, val in sorted(rslt.items(), 
                                    key=lambda x: x[1]["score"], 
                                    reverse=True)]
```

### 4. Harden Perceive (Critical)

**What to add:**
- Specific exception handling with error categorization
- Retry logic with exponential backoff
- Request timeouts
- Track and expose feed health status

**Concrete changes:**
```python
import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

def fetch_with_retry(url, max_retries=3, timeout=10):
    session = requests.Session()
    retry = Retry(total=max_retries, backoff_factor=0.5, 
                  status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    try:
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except requests.Timeout:
        return {"error": "timeout", "entries": []}
    except requests.RequestException as e:
        return {"error": str(e), "entries": []}

# Replace feedparser.parse(url) with:
d = fetch_with_retry(url)
if "error" in d:
    if log:
        sys.stdout.write(f" - Error: {d['error']}\n")
    # Store error for status reporting
    save_feed_error(source, d["error"])
    continue
```

### 5. Enhance Remember (Important)

**What to add:**
- Incremental updates instead of full rewrites
- Maintain read/unread state
- Archive old items instead of discarding

**Concrete changes:**
```python
def merge_with_existing(new_entries, category):
    """Merge new entries with existing, preserve read state"""
    existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
    
    if os.path.exists(existing_file):
        with open(existing_file, "r") as f:
            existing = json.load(f)
        existing_map = {e["url"]: e for e in existing.get("entries", [])}
    else:
        existing_map = {}
    
    # Merge: preserve 'read' field if exists
    for entry in new_entries:
        if entry["url"] in existing_map:
            entry["read"] = existing_map[entry["url"]].get("read", False)
        else:
            entry["read"] = False
    
    return new_entries

# Before writing rslt:
rslt["entries"] = merge_with_existing(rslt["entries"], category)
```

### 6. Add feedback capture (Important)

**What to add:**
- API/hooks for recording user interactions
- Schema for interaction events

**Concrete changes:**
```python
# New file: rreader/api.py
def mark_as_read(item_url):
    record_interaction(item_url, "read")
    # Update the stored JSON to set read=True

def mark_clicked(item_url):
    record_interaction(item_url, "click")

# Expose these functions for the UI layer to call
```

### 7. Add error visibility (Important)

**What to add:**
- Feed health status file
- Error reporting in output

**Concrete changes:**
```python
# Save alongside each category's JSON:
health_status = {
    "last_updated": time.time(),
    "feeds": {
        source: {"status": "ok", "last_error": None}
        for source in urls.keys()
    }
}

# Update when errors occur:
health_status["feeds"][source] = {
    "status": "error",
    "last_error": error_message,
    "last_success": previous_success_timestamp
}

# Write health file:
with open(os.path.join(p["path_data"], f"health_{category}.json"), "w") as f:
    json.dump(health_status, f)
```

### 8. Improve observability (Minor)

**What to add:**
- Structured logging using Python's `logging` module
- Metrics: feed fetch duration, entry counts, error rates

**Concrete changes:**
```python
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace sys.stdout.write with:
logger.info(f"Fetching {url}")
logger.info(f"Parsed {len(d.entries)} entries from {source}")
logger.error(f"Failed to fetch {url}: {error}")
```

### 9. Add async fetching (Minor)

**What to add:**
- Concurrent feed fetching using `asyncio` or `ThreadPoolExecutor`

**Concrete changes:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, show_author, log):
    # Extract inner loop logic
    pass

# In get_feed_from_rss():
with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(fetch_single_feed, s, u, show_author, log): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source = futures[future]
        try:
            entries = future.result()
            rslt.update(entries)
        except Exception as e:
            logger.error(f"Failed {source}: {e}")
```