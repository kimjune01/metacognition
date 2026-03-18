# Diagnostic Report: RSS Feed Reader System

## Observations

This system fetches RSS/Atom feeds and stores them as timestamped JSON files. Current working capabilities:

1. **Perceive**: Fetches RSS feeds from configured URLs using `feedparser`
2. **Cache**: Parses feed entries and extracts structured fields (title, link, author, timestamp)
3. **Filter**: Deduplicates entries by timestamp (uses `ts` as dict key, so later entries with same timestamp overwrite)
4. **Attend**: Sorts entries by timestamp (reverse chronological order)
5. **Remember**: Writes results to JSON files (`rss_{category}.json`) with metadata
6. **Configuration management**: Merges bundled feeds with user feeds, preserving user customizations

The system runs as a synchronous batch processor, fetching all configured feeds and writing output files.

## Triage

### Critical gaps (blocks production use)

1. **Filter is shallow** - Only deduplicates by timestamp collision (rare). No validation, quality checks, or malformed entry handling
2. **Attend is absent** - No prioritization beyond chronological sort. No diversity enforcement, relevance ranking, or result limiting
3. **Consolidate is absent** - System never learns. No read tracking, no preference learning, no feed quality scoring

### Important gaps (limits usefulness)

4. **Perceive is fragile** - Bare `except:` clauses hide errors. Network failures are silent or cause exits
5. **Cache is shallow** - No content extraction (only metadata). No full-text storage for search
6. **Remember has no retention policy** - Files grow unbounded. No archival, no cleanup, no size limits

### Minor gaps (quality of life)

7. **No incremental updates** - Fetches entire feed history each run, even if already seen
8. **No rate limiting** - Could hammer feed servers if run too frequently
9. **No monitoring** - No metrics on fetch success, latency, or entry counts

## Plan

### 1. Strengthen Filter (Critical)

**Current problem**: Only timestamp collision prevents duplicates. Malformed entries crash or produce garbage.

**Changes needed**:
```python
def validate_entry(feed, source):
    """Return validated entry dict or None if invalid."""
    # Required fields
    if not hasattr(feed, 'link') or not feed.link:
        return None
    if not hasattr(feed, 'title') or not feed.title.strip():
        return None
    
    # Timestamp validation
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        return None
    
    # Reject future dates (likely parser errors)
    ts = int(time.mktime(parsed_time))
    if ts > time.time() + 86400:  # More than 1 day in future
        return None
    
    # Reject too old (configurable threshold)
    if ts < time.time() - (90 * 86400):  # Older than 90 days
        return None
        
    return {"parsed_time": parsed_time, "ts": ts}

# In get_feed_from_rss, replace the try/except block:
for feed in d.entries:
    validated = validate_entry(feed, source)
    if not validated:
        continue
    # ... rest of processing using validated data
```

### 2. Implement Attend (Critical)

**Current problem**: Returns all entries chronologically. No limit on count, no diversity, no relevance.

**Changes needed**:
```python
def attend_entries(entries_dict, category_config):
    """Rank, diversify, and limit entries."""
    entries = sorted(entries_dict.values(), key=lambda x: x['timestamp'], reverse=True)
    
    # Limit by count (most recent N)
    max_entries = category_config.get('max_entries', 100)
    entries = entries[:max_entries]
    
    # Diversity: limit entries per source
    max_per_source = category_config.get('max_per_source', 10)
    source_counts = {}
    filtered = []
    for entry in entries:
        source = entry['sourceName']
        if source_counts.get(source, 0) < max_per_source:
            filtered.append(entry)
            source_counts[source] = source_counts.get(source, 0) + 1
    
    return filtered

# In get_feed_from_rss, before writing:
rslt = attend_entries(rslt, {"max_entries": 100, "max_per_source": 10})
```

### 3. Add Consolidate (Critical)

**Current problem**: No learning. System can't improve based on what users read or what feeds are reliable.

**Changes needed**:
```python
# New file: consolidate.py
def track_read_entry(category, entry_id):
    """Record that user opened an entry."""
    tracking_file = os.path.join(p["path_data"], f"tracking_{category}.json")
    
    if os.path.exists(tracking_file):
        with open(tracking_file, 'r') as f:
            tracking = json.load(f)
    else:
        tracking = {"read_entries": [], "source_scores": {}}
    
    tracking["read_entries"].append({"id": entry_id, "ts": int(time.time())})
    
    with open(tracking_file, 'w') as f:
        json.dump(tracking, f)

def update_source_scores(category):
    """Update source quality scores based on read rate."""
    tracking_file = os.path.join(p["path_data"], f"tracking_{category}.json")
    entries_file = os.path.join(p["path_data"], f"rss_{category}.json")
    
    with open(tracking_file, 'r') as f:
        tracking = json.load(f)
    with open(entries_file, 'r') as f:
        entries = json.load(f)
    
    # Calculate read rate per source
    source_presented = {}
    source_read = {}
    
    for entry in entries["entries"]:
        source = entry["sourceName"]
        source_presented[source] = source_presented.get(source, 0) + 1
        
        if entry["id"] in tracking["read_entries"]:
            source_read[source] = source_read.get(source, 0) + 1
    
    # Compute scores (read rate with smoothing)
    for source in source_presented:
        read_count = source_read.get(source, 0)
        presented_count = source_presented[source]
        score = (read_count + 1) / (presented_count + 2)  # Laplace smoothing
        tracking["source_scores"][source] = score
    
    with open(tracking_file, 'w') as f:
        json.dump(tracking, f)

# Modify attend_entries to use scores for ranking
```

### 4. Harden Perceive (Important)

**Current problem**: Network errors are hidden or cause abrupt exits.

**Changes needed**:
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_session():
    """Return requests session with retry logic."""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def fetch_feed_safely(url, timeout=10):
    """Fetch feed with proper error handling."""
    try:
        session = get_session()
        response = session.get(url, timeout=timeout)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except requests.exceptions.Timeout:
        print(f"Timeout fetching {url}")
        return None
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

# Replace feedparser.parse(url) with fetch_feed_safely(url)
# Add None check after fetch
```

### 5. Deepen Cache (Important)

**Current problem**: Only metadata stored. No content for search or preview.

**Changes needed**:
```python
# In entries dict, add:
entries = {
    # ... existing fields ...
    "summary": getattr(feed, 'summary', '')[:500],  # First 500 chars
    "content": extract_content(feed),  # Full content if available
}

def extract_content(feed):
    """Extract full content from feed entry."""
    # Try content field first (Atom)
    if hasattr(feed, 'content') and feed.content:
        return feed.content[0].value
    # Fall back to summary (RSS)
    if hasattr(feed, 'summary'):
        return feed.summary
    return ""
```

### 6. Add Retention Policy (Important)

**Current problem**: JSON files grow indefinitely.

**Changes needed**:
```python
def apply_retention(entries, max_age_days=30):
    """Remove entries older than max_age_days."""
    cutoff = int(time.time()) - (max_age_days * 86400)
    return [e for e in entries if e["timestamp"] > cutoff]

# Before writing rslt, add:
rslt["entries"] = apply_retention(rslt["entries"], max_age_days=30)
```

### 7. Add Incremental Updates (Minor)

**Current problem**: Re-processes entire feed history on every run.

**Changes needed**:
```python
def get_last_seen_timestamp(category):
    """Return newest timestamp from last run."""
    entries_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(entries_file):
        return 0
    
    with open(entries_file, 'r') as f:
        data = json.load(f)
    
    if data["entries"]:
        return data["entries"][0]["timestamp"]  # Already sorted newest first
    return 0

# Only process entries newer than last_seen
last_seen = get_last_seen_timestamp(category)
for feed in d.entries:
    # ... validation ...
    if ts <= last_seen:
        continue  # Already have this entry
```

### 8. Add Rate Limiting (Minor)

**Changes needed**:
```python
import time

FEED_FETCH_DELAY = 1  # seconds between feeds

# In get_feed_from_rss loop:
for i, (source, url) in enumerate(urls.items()):
    if i > 0:
        time.sleep(FEED_FETCH_DELAY)
    # ... fetch feed ...
```

### 9. Add Monitoring (Minor)

**Changes needed**:
```python
def log_metrics(category, metrics):
    """Append metrics to log file."""
    metrics_file = os.path.join(p["path_data"], "metrics.jsonl")
    
    entry = {
        "timestamp": int(time.time()),
        "category": category,
        **metrics
    }
    
    with open(metrics_file, 'a') as f:
        f.write(json.dumps(entry) + "\n")

# Track: fetch_duration, entry_count, error_count, sources_fetched
```