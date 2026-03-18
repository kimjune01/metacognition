# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **Feed ingestion**: Fetches RSS feeds from multiple sources via URLs using `feedparser`
2. **Data normalization**: Extracts standardized fields (title, link, timestamp, author) from heterogeneous RSS formats
3. **Time zone conversion**: Converts UTC timestamps to a configured timezone (KST/UTC+9)
4. **Timestamp-based deduplication**: Uses timestamp as unique ID, preventing duplicate entries within a single fetch
5. **Sorting**: Orders entries by timestamp (newest first)
6. **Persistence**: Writes results to JSON files per category (`rss_{category}.json`)
7. **Configuration management**: Maintains a `feeds.json` file with category-based feed organization
8. **Graceful degradation**: Continues processing if individual feeds fail (silent failure with try/except)

## Triage

Mapping to the diagnostic checklist reveals these gaps, ranked by severity:

### Critical (System is incomplete without these)

1. **CONSOLIDATE - Completely absent**: No backward pass. The system never learns from what it fetched. No feed quality tracking, no rate adjustment, no automatic cleanup of dead feeds.

2. **FILTER - Shallow**: Only implicit filtering (continues on parse errors). No validation of:
   - Content quality or spam detection
   - Duplicate content across different timestamps
   - Maximum age of entries
   - Broken/invalid URLs
   - Rate limiting or fetch throttling

3. **REMEMBER - Shallow**: Overwrites entire category file each run. Cannot:
   - Track which entries were previously seen
   - Mark items as read/unread
   - Maintain user interactions
   - Preserve history beyond the current fetch

### Important (Production readiness)

4. **ATTEND - Shallow**: Sorting exists but no intelligent ranking:
   - No relevance scoring
   - No diversity enforcement (one prolific source could dominate)
   - No personalization
   - No deduplication of near-identical content from different sources

5. **PERCEIVE - Shallow**: Basic ingestion works but lacks robustness:
   - No retry logic for transient failures
   - Silent error handling hides problems
   - No timeout configuration
   - No network error classification
   - No incremental/conditional fetching (If-Modified-Since headers)

6. **CACHE - Adequate but improvable**: Current implementation works but:
   - All data kept in memory before writing
   - No query interface beyond the output files
   - Timestamp collision handling is implicit (overwrites)

## Plan

### 1. Add CONSOLIDATE stage (Critical)

**File**: Create `consolidate.py` and modify `do()` function

**Changes needed**:
```python
# Create a feed_stats.json file structure:
{
  "source_url": {
    "success_rate": 0.95,
    "avg_fetch_time_ms": 450,
    "last_success": timestamp,
    "last_failure": timestamp,
    "failure_count": 2,
    "entry_count_avg": 25,
    "last_modified": "ETag or Last-Modified header"
  }
}

# After each fetch:
# - Update success/failure metrics
# - Calculate fetch time
# - Store HTTP caching headers
# - Remove feeds with >10 consecutive failures
# - Adjust fetch frequency based on update patterns
```

**Specific code additions**:
- Create `update_feed_stats()` function called after each `feedparser.parse()`
- Add `load_feed_stats()` at start of `do()`
- Add conditional fetching: `feedparser.parse(url, etag=..., modified=...)`
- Create weekly cleanup job to prune dead feeds

### 2. Strengthen FILTER stage (Critical)

**File**: Modify `get_feed_from_rss()` function

**Add validation layers**:
```python
# After parsing each feed entry, before adding to rslt:

# 1. Age filter
MAX_AGE_DAYS = 30
if (time.time() - ts) > (MAX_AGE_DAYS * 86400):
    continue

# 2. Required fields validation
if not feed.get('title') or not feed.get('link'):
    continue

# 3. URL validation
if not feed.link.startswith(('http://', 'https://')):
    continue

# 4. Content deduplication (cross-timestamp)
# Keep a rolling hash of seen URLs
seen_urls = load_seen_urls(category)  # Load last N URLs
if feed.link in seen_urls:
    continue

# 5. Title quality filter
if len(feed.title.strip()) < 5 or is_spam_pattern(feed.title):
    continue
```

**New functions needed**:
- `load_seen_urls(category, lookback_hours=48)`: Load recent URLs from history
- `is_spam_pattern(text)`: Basic regex checks for common spam patterns
- `validate_url(url)`: Proper URL validation with domain checks

### 3. Enhance REMEMBER stage (Critical)

**File**: Modify storage strategy in `get_feed_from_rss()`

**Change from overwrite to append-and-prune**:
```python
# Instead of writing fresh each time:
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")

if os.path.exists(existing_file):
    with open(existing_file, 'r') as f:
        existing_data = json.load(f)
    existing_entries = {e['id']: e for e in existing_data['entries']}
else:
    existing_entries = {}

# Merge new with existing
all_entries = {**existing_entries, **rslt}

# Prune entries older than retention period
RETENTION_HOURS = 72
cutoff = time.time() - (RETENTION_HOURS * 3600)
kept_entries = {k: v for k, v in all_entries.items() if v['timestamp'] > cutoff}

# Sort and write
final_entries = sorted(kept_entries.values(), key=lambda x: x['id'], reverse=True)
```

**Add read-state tracking**:
```python
# Create user_state.json:
{
  "read_items": [ts1, ts2, ...],  # List of read timestamps
  "starred_items": [ts3, ...],
  "last_viewed": {"category": timestamp}
}
```

### 4. Improve ATTEND stage (Important)

**File**: Create `ranking.py` module

**Add before final sort**:
```python
def rank_entries(entries, category, user_state):
    """
    Score each entry based on:
    - Recency (exponential decay)
    - Source diversity (penalize if same source appears frequently)
    - User interaction history (boost similar sources)
    - Time of day (prefer items published during user's active hours)
    """
    
    scored = []
    source_count = {}
    
    for entry in entries:
        score = 0
        
        # Recency score (decay over 24 hours)
        age_hours = (time.time() - entry['timestamp']) / 3600
        score += 100 * math.exp(-age_hours / 12)
        
        # Diversity penalty
        source_count[entry['sourceName']] = source_count.get(entry['sourceName'], 0) + 1
        if source_count[entry['sourceName']] > 3:
            score *= 0.5
        
        # User preference boost (if they've clicked this source before)
        if entry['sourceName'] in user_state.get('preferred_sources', []):
            score *= 1.5
            
        scored.append((score, entry))
    
    # Return sorted by score, then timestamp
    return [entry for score, entry in sorted(scored, key=lambda x: (x[0], x[1]['timestamp']), reverse=True)]
```

**Integration point**: Call `rank_entries()` before writing to JSON file

### 5. Harden PERCEIVE stage (Important)

**File**: Modify error handling in `get_feed_from_rss()`

**Replace try/except with structured error handling**:
```python
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def create_session():
    """Create session with retry logic and timeout"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# In get_feed_from_rss():
session = create_session()

for source, url in urls.items():
    start_time = time.time()
    error = None
    
    try:
        # Fetch with timeout
        response = session.get(url, timeout=10)
        response.raise_for_status()
        d = feedparser.parse(response.content)
        fetch_time = (time.time() - start_time) * 1000
        
        # Log success
        log_fetch_result(source, url, success=True, fetch_time=fetch_time)
        
    except requests.Timeout:
        error = "timeout"
    except requests.HTTPError as e:
        error = f"http_{e.response.status_code}"
    except Exception as e:
        error = f"parse_error: {str(e)}"
    
    if error:
        log_fetch_result(source, url, success=False, error=error)
        continue
```

**Add logging function**:
```python
def log_fetch_result(source, url, success, fetch_time=None, error=None):
    """Append to fetch_log.jsonl for monitoring"""
    log_entry = {
        "timestamp": time.time(),
        "source": source,
        "url": url,
        "success": success,
        "fetch_time_ms": fetch_time,
        "error": error
    }
    with open(os.path.join(p["path_data"], "fetch_log.jsonl"), "a") as f:
        f.write(json.dumps(log_entry) + "\n")
```

### 6. Improve CACHE structure (Lower priority)

**File**: Consider adding `storage.py` abstraction

**Current limitation**: Direct file I/O scattered throughout code

**Improvement**:
```python
class FeedCache:
    def __init__(self, data_path):
        self.data_path = data_path
        
    def get_entries(self, category, since=None):
        """Query interface for retrieving entries"""
        
    def add_entries(self, category, entries):
        """Merge new entries with existing"""
        
    def get_sources(self, category):
        """List all sources in a category"""
        
    def mark_as_read(self, entry_ids):
        """Update user state"""
```

This abstraction would centralize storage logic and make it easier to migrate to SQLite or other backends later.