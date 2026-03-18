# Diagnostic Report: RSS Feed Reader

## Observations

This system currently implements a basic RSS feed aggregator with the following working capabilities:

1. **Perceive**: Fetches RSS feeds from configured URLs using `feedparser`
2. **Cache**: Parses and normalizes feed entries into a consistent JSON structure with timestamps, titles, URLs, source names, and publication dates
3. **Filter**: Performs minimal filtering—skips entries without parseable timestamps
4. **Attend**: Sorts entries by timestamp (most recent first) and deduplicates by using timestamp as ID
5. **Remember**: Persists aggregated feeds to disk as JSON files (`rss_{category}.json`)
6. **Consolidate**: **ABSENT**—no learning or adaptation mechanism

The system handles multiple feed categories, merges bundled and user configurations, and formats timestamps relative to today's date.

## Triage

### Critical gaps (blocks production use):

1. **Consolidate stage is completely absent** — The system never improves. It can't learn which feeds are reliable, which entries users engage with, or adapt to changing feed quality.

2. **Filter stage is shallow** — Only checks for timestamp presence. Accepts duplicate content from different sources, malformed entries, spam, and stale feeds.

3. **Attend stage is shallow** — Timestamp-based deduplication is inadequate (multiple entries can share timestamps). No diversity across sources, no relevance ranking, no user preference consideration.

4. **Perceive stage lacks resilience** — Silent failures via bare `except:` clauses. No retry logic, timeout handling, or partial failure recovery.

5. **Remember stage lacks integrity** — No versioning, no backup, no transaction safety. File writes can corrupt on failure.

### Important gaps (reduce reliability):

6. **No error visibility** — Failed feeds disappear silently. Users can't tell what's broken.

7. **No staleness detection** — System can't identify dead feeds or feeds that stopped updating.

8. **No rate limiting** — Could hammer feed servers or get blocked.

9. **Timestamp collision handling is naive** — Using `int(time.mktime())` as ID means entries published in the same second collide; only the last survives.

## Plan

### 1. Add Consolidate stage (Critical)

**What to build**: A feedback system that tracks feed quality and adjusts future processing.

**Concrete changes**:
```python
# Add new file: consolidate.py
class FeedQualityTracker:
    def __init__(self):
        self.stats_file = os.path.join(p["path_data"], "feed_stats.json")
        self.stats = self._load_stats()
    
    def _load_stats(self):
        # Per-feed metrics: fetch_success_rate, avg_new_entries, last_success, staleness_score
        pass
    
    def record_fetch(self, source, url, success, entry_count, new_entry_count):
        # Update rolling statistics
        pass
    
    def get_priority_order(self, category):
        # Return feeds sorted by quality score for preferential fetching
        pass
    
    def should_skip_feed(self, source, url):
        # Return True if feed has failed >5 times or been stale >30 days
        pass

# In do():
tracker = FeedQualityTracker()
for source, url in urls.items():
    if tracker.should_skip_feed(source, url):
        continue
    # ... existing fetch logic ...
    tracker.record_fetch(source, url, success=True, ...)
```

### 2. Enhance Filter stage (Critical)

**What to build**: Quality gates that reject malformed, duplicate, and spam entries.

**Concrete changes**:
```python
class EntryFilter:
    def __init__(self):
        self.seen_content_hashes = self._load_seen_hashes()
        
    def is_valid(self, feed_entry):
        # Check 1: Required fields present
        if not (feed_entry.title and feed_entry.link):
            return False, "missing_required_fields"
        
        # Check 2: Content hash deduplication (catch same story from multiple feeds)
        content_hash = hashlib.md5(
            f"{feed_entry.title}{feed_entry.get('summary', '')}".encode()
        ).hexdigest()
        if content_hash in self.seen_content_hashes:
            return False, "duplicate_content"
        
        # Check 3: URL validation
        if not feed_entry.link.startswith(('http://', 'https://')):
            return False, "invalid_url"
        
        # Check 4: Title spam detection (all caps, excessive punctuation)
        if feed_entry.title.isupper() and len(feed_entry.title) > 20:
            return False, "suspected_spam"
        
        self.seen_content_hashes.add(content_hash)
        return True, None

# In get_feed_from_rss():
filter = EntryFilter()
for feed in d.entries:
    valid, reason = filter.is_valid(feed)
    if not valid:
        if log:
            sys.stdout.write(f"  Filtered: {reason}\n")
        continue
    # ... existing processing ...
```

### 3. Strengthen Attend stage (Critical)

**What to build**: Proper deduplication and relevance-based ranking.

**Concrete changes**:
```python
# Fix ID collision issue
entries = {
    "id": f"{ts}_{hash(feed.link)[:8]}",  # Combine timestamp with URL hash
    # ... rest of fields ...
}

# Add ranking function
def rank_entries(entries, category_config):
    scored = []
    for entry in entries:
        score = entry["timestamp"]  # Base: recency
        
        # Boost: source diversity (prefer different sources in top results)
        source_count = sum(1 for e in scored[:10] if e["sourceName"] == entry["sourceName"])
        score -= source_count * 3600  # Penalty for repeated sources
        
        # Boost: user preferences (if available)
        if entry["sourceName"] in category_config.get("preferred_sources", []):
            score += 7200
        
        scored.append((score, entry))
    
    return [entry for score, entry in sorted(scored, reverse=True)]

# In get_feed_from_rss():
rslt = rank_entries(list(rslt.values()), RSS[category])
```

### 4. Harden Perceive stage (Critical)

**What to build**: Robust error handling with retry logic and visibility.

**Concrete changes**:
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def fetch_feed_with_retry(url, timeout=10, max_retries=3):
    session = requests.Session()
    retry_strategy = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    
    try:
        response = session.get(url, timeout=timeout)
        return feedparser.parse(response.content), None
    except requests.Timeout:
        return None, "timeout"
    except requests.ConnectionError:
        return None, "connection_failed"
    except Exception as e:
        return None, f"error_{type(e).__name__}"

# In get_feed_from_rss():
d, error = fetch_feed_with_retry(url)
if error:
    if log:
        sys.stdout.write(f" - FAILED: {error}\n")
    # Record failure for Consolidate stage
    tracker.record_fetch(source, url, success=False, error=error)
    continue
```

### 5. Add transactional Remember stage (Critical)

**What to build**: Atomic writes that prevent data loss.

**Concrete changes**:
```python
import tempfile

def atomic_write_json(filepath, data):
    """Write JSON atomically using temp file + rename"""
    dirpath = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile(
        mode='w',
        encoding='utf-8',
        dir=dirpath,
        delete=False,
        suffix='.tmp'
    ) as f:
        temp_path = f.name
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Atomic rename (POSIX) or copy+delete (Windows fallback)
    try:
        os.replace(temp_path, filepath)
    except OSError:
        shutil.copy2(temp_path, filepath)
        os.unlink(temp_path)

# Replace all `json.dump()` calls:
atomic_write_json(
    os.path.join(p["path_data"], f"rss_{category}.json"),
    rslt
)
```

### 6. Add error reporting (Important)

**What to build**: A summary of what failed and why.

**Concrete changes**:
```python
# Return error summary from get_feed_from_rss():
return {
    "entries": rslt,
    "created_at": int(time.time()),
    "fetch_summary": {
        "total_sources": len(urls),
        "successful": success_count,
        "failed": failed_sources  # List of (source, error) tuples
    }
}

# Write separate error log:
error_log_path = os.path.join(p["path_data"], f"errors_{category}.json")
atomic_write_json(error_log_path, {
    "timestamp": int(time.time()),
    "failures": failed_sources
})
```

### 7. Add staleness detection (Important)

**What to build**: Identify feeds that haven't updated recently.

**Concrete changes**:
```python
# In FeedQualityTracker:
def check_staleness(self, source, url, latest_entry_timestamp):
    now = int(time.time())
    age_days = (now - latest_entry_timestamp) / 86400
    
    self.stats[url]["last_entry_age_days"] = age_days
    
    if age_days > 30:
        return "stale"
    elif age_days > 7:
        return "aging"
    return "fresh"

# Alert user in feed output:
rslt["feed_health"] = {
    source: tracker.check_staleness(source, url, max_ts)
    for source, url, max_ts in feed_timestamps
}
```

### 8. Add rate limiting (Important)

**What to build**: Throttle requests to avoid overwhelming servers.

**Concrete changes**:
```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, requests_per_minute=30):
        self.requests = defaultdict(list)
        self.limit = requests_per_minute
    
    def wait_if_needed(self, domain):
        now = time.time()
        recent = [t for t in self.requests[domain] if now - t < 60]
        self.requests[domain] = recent
        
        if len(recent) >= self.limit:
            sleep_time = 60 - (now - recent[0])
            time.sleep(sleep_time)
        
        self.requests[domain].append(now)

# In get_feed_from_rss():
limiter = RateLimiter()
for source, url in urls.items():
    domain = urlparse(url).netloc
    limiter.wait_if_needed(domain)
    # ... fetch ...
```

### 9. Fix timestamp collision (Important)

Already covered in #3 above—use composite key: `f"{ts}_{hash(feed.link)[:8]}"`.