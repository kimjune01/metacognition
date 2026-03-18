# Diagnostic Report: RSS Feed Reader

## Observations

This system currently performs the following functions:

1. **Perceives:** Fetches RSS feeds from configured URLs using `feedparser.parse()`
2. **Caches:** Parses feed entries and extracts structured fields (title, link, timestamp, author, publication date)
3. **Filters (shallow):** Rejects entries missing both `published_parsed` and `updated_parsed` timestamps; deduplicates by timestamp (uses timestamp as ID, so same-second entries overwrite)
4. **Attends (shallow):** Sorts entries by timestamp (reverse chronological order only)
5. **Remembers:** Writes aggregated feeds to JSON files (`rss_{category}.json`) with creation timestamp
6. **Consolidate:** Absent—no learning or adaptation occurs

The system manages configuration by merging bundled feeds with user feeds, preserving user customizations while adding new bundled categories.

## Triage

### Critical gaps (blocks production use)

1. **Filter stage is shallow** — Only validates timestamp presence. No handling for: malformed URLs, duplicate titles, feed parse errors, network timeouts, or stale feeds.

2. **Attend stage is shallow** — Only sorts by time. No relevance ranking, no diversity enforcement (single source can dominate), no read/unread tracking, no result limits.

3. **Remember stage lacks read/write state** — System can't track which entries the user has seen, clicked, or dismissed. Every run treats all entries as new.

### Important gaps (limits usefulness)

4. **No error recovery in Perceive** — `sys.exit()` on any parse failure kills the entire batch. One bad feed URL breaks all categories.

5. **No incremental updates** — Re-fetches and re-parses entire feeds every run. Wastes bandwidth and processing for unchanged content.

6. **Consolidate stage absent** — System never learns which feeds/sources are valuable, which entries get clicked, or optimal refresh intervals.

### Minor gaps (quality of life)

7. **No rate limiting or caching headers** — Could hit feed providers' rate limits or ignore HTTP 304 Not Modified responses.

8. **Timestamp collision handling is naive** — Two entries published in the same second from same feed: last one wins silently.

9. **No feed health monitoring** — Can't detect dead feeds, permanently moved URLs, or declining update frequency.

## Plan

### 1. Strengthen Filter stage

**What to add:**
- Validate feed URLs before parsing (check scheme, reachability)
- Add try/except around individual feed parsing with logging
- Check for minimum required fields (title, link) before accepting entry
- Deduplicate by content hash (title + link) not just timestamp
- Add staleness filter: reject feeds not updated in N days (configurable)
- Validate URLs in entries (reject javascript:, data:, etc.)

**Implementation:**
```python
def validate_entry(feed, source):
    """Returns (is_valid, normalized_entry) tuple"""
    required = ['title', 'link']
    if not all(hasattr(feed, field) for field in required):
        return False, None
    
    # Create content hash for deduplication
    content_id = hashlib.md5(
        f"{feed.title}|{feed.link}".encode()
    ).hexdigest()
    
    # Validate URL scheme
    if not feed.link.startswith(('http://', 'https://')):
        return False, None
    
    return True, content_id
```

### 2. Enhance Attend stage

**What to add:**
- Track read/unread state in separate JSON file per category
- Implement result limits (e.g., top 50 entries per category)
- Add diversity: limit entries per source (e.g., max 5 from same source in top 20)
- Support multiple sort orders: by time, by source, by unread status
- Mark entries older than N days as automatically read

**Implementation:**
```python
# In rss_{category}.json, add per-entry:
{
    "id": "abc123",  # Use content hash not timestamp
    "read": false,
    "read_at": null,
    "click_count": 0
}

# Add diversity filter:
def enforce_diversity(entries, max_per_source=5):
    source_counts = {}
    result = []
    for entry in entries:
        source = entry['sourceName']
        if source_counts.get(source, 0) < max_per_source:
            result.append(entry)
            source_counts[source] = source_counts.get(source, 0) + 1
    return result
```

### 3. Add read/write state to Remember stage

**What to add:**
- Create `rss_{category}_state.json` for user interaction data
- Track: read status, click timestamps, dismissals, pins
- Merge state with entries before returning to UI
- Expire old state (delete tracking for entries >30 days old)

**Implementation:**
```python
def load_state(category):
    state_file = os.path.join(p["path_data"], f"rss_{category}_state.json")
    if os.path.exists(state_file):
        with open(state_file) as f:
            return json.load(f)
    return {}

def save_interaction(category, entry_id, interaction_type):
    state = load_state(category)
    if entry_id not in state:
        state[entry_id] = {}
    state[entry_id][interaction_type] = int(time.time())
    # Save atomically
    state_file = os.path.join(p["path_data"], f"rss_{category}_state.json")
    with open(state_file + '.tmp', 'w') as f:
        json.dump(state, f)
    os.replace(state_file + '.tmp', state_file)
```

### 4. Add error recovery to Perceive stage

**What to add:**
- Wrap each feed fetch in try/except, continue on failure
- Log errors to `rss_errors.log` with timestamp and URL
- Set timeout on `feedparser.parse()` (requires urllib timeout)
- Return partial results if some feeds succeed

**Implementation:**
```python
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        
        # Add timeout
        d = feedparser.parse(url, timeout=10)
        
        if d.bozo:  # feedparser detected malformed feed
            log_error(category, url, d.bozo_exception)
            continue
            
        if log:
            sys.stdout.write(" - Done\n")
    except Exception as e:
        log_error(category, url, str(e))
        if log:
            sys.stdout.write(f" - Failed: {e}\n")
        continue  # Don't sys.exit(), keep processing other feeds
```

### 5. Implement incremental updates

**What to add:**
- Store `Last-Modified` and `ETag` headers per feed
- Send conditional requests using these headers
- Only parse feeds that return 200 (not 304)
- Store last fetch timestamp, skip feeds fetched within refresh interval

**Implementation:**
```python
# In rss_{category}_meta.json:
{
    "feeds": {
        "source_name": {
            "last_modified": "Wed, 21 Oct 2023 07:28:00 GMT",
            "etag": "\"abc123\"",
            "last_fetch": 1234567890,
            "refresh_interval": 3600  # seconds
        }
    }
}

# When fetching:
import urllib.request
meta = load_feed_meta(category)
if should_skip_fetch(meta, source, current_time):
    continue
    
request = urllib.request.Request(url)
if 'last_modified' in meta['feeds'][source]:
    request.add_header('If-Modified-Since', meta['feeds'][source]['last_modified'])
# ... handle 304 response
```

### 6. Add Consolidate stage (learning)

**What to add:**
- Track click-through rate per feed source
- Calculate optimal refresh interval based on update frequency
- Auto-disable feeds with 0 clicks over 30 days
- Boost sources with high engagement in Attend ranking
- Suggest removing stale feeds

**Implementation:**
```python
def consolidate_metrics(category):
    """Run after each fetch to update feed quality scores"""
    state = load_state(category)
    meta = load_feed_meta(category)
    
    for source in meta['feeds']:
        # Calculate clicks per entry for this source
        source_entries = [e for e in state.values() 
                         if e.get('sourceName') == source]
        if not source_entries:
            continue
            
        clicks = sum(e.get('click_count', 0) for e in source_entries)
        ctr = clicks / len(source_entries) if source_entries else 0
        
        # Update quality score
        meta['feeds'][source]['quality_score'] = ctr
        
        # Adjust refresh interval based on update frequency
        # (track timestamps between updates, calculate median interval)
    
    save_feed_meta(category, meta)

# Call after each fetch:
do(target_category)
consolidate_metrics(target_category)
```

### 7. Add rate limiting and HTTP caching

**What to add:**
- Respect `Retry-After` headers on 429 responses
- Honor feed's `ttl` or `sy:updatePeriod` if present
- Add minimum interval between requests to same domain (e.g., 1 second)
- Cache responses for 5 minutes to handle rapid re-runs

**Implementation:**
```python
import time
from urllib.parse import urlparse

last_request_time = {}  # domain -> timestamp

def rate_limited_fetch(url, min_interval=1.0):
    domain = urlparse(url).netloc
    now = time.time()
    
    if domain in last_request_time:
        elapsed = now - last_request_time[domain]
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
    
    result = feedparser.parse(url)
    last_request_time[domain] = time.time()
    return result
```

### 8. Fix timestamp collision handling

**What to add:**
- Use content-based ID (hash of title + URL) instead of timestamp
- Fall back to timestamp + counter for true duplicates
- Warn when duplicate content detected

**Implementation:**
```python
import hashlib

def generate_entry_id(feed):
    """Generate unique ID from content"""
    content = f"{feed.title}|{feed.link}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

# In loop:
entry_id = generate_entry_id(feed)
if entry_id in rslt:
    # This is a duplicate entry
    continue
rslt[entry_id] = entries
```

### 9. Add feed health monitoring

**What to add:**
- Track consecutive fetch failures per feed
- Record response times and success rate
- Alert when feed hasn't updated in 2x its normal interval
- Provide health dashboard data

**Implementation:**
```python
# In feed metadata:
{
    "health": {
        "consecutive_failures": 0,
        "last_success": 1234567890,
        "avg_response_time": 1.2,
        "success_rate_30d": 0.95,
        "last_update_seen": 1234567890,
        "update_frequency_days": 1.5
    }
}

def update_health_metrics(source, success, response_time):
    # Increment/reset failure counter
    # Update moving averages
    # Check if feed appears dead
    pass
```