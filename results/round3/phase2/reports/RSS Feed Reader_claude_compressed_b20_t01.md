# Diagnostic Report: RSS Feed Reader

## Observations

This system is an RSS feed aggregator that:

1. **Perceives**: Fetches RSS feeds from multiple URLs via `feedparser.parse()`
2. **Cache**: Stores parsed entries temporarily in a dictionary keyed by timestamp
3. **Filter**: (Shallow) Skips entries missing time data; deduplicates by timestamp (last write wins)
4. **Attend**: Sorts entries by timestamp (most recent first)
5. **Remember**: Persists results to JSON files (`rss_{category}.json`) with creation timestamp
6. **Consolidate**: (Absent) No learning or adaptation mechanism

**Working capabilities:**
- Multi-source RSS ingestion per category
- Time parsing with timezone conversion (UTC → KST)
- Duplicate elimination by timestamp collision
- Reverse chronological sorting
- Per-category JSON output with metadata
- User feed configuration with bundled defaults
- Category-selective or full refresh modes

## Triage

### Critical gaps (system is fragile/incomplete):

1. **Filter is shallow** - Only rejects entries without timestamps. No validation of URLs, titles, or feed health. Malformed data propagates.

2. **Consolidate is absent** - System never learns. Doesn't track read/unread state, user preferences, feed reliability, or optimize fetch frequency.

3. **Cache collision handling** - Using timestamp as ID causes silent data loss when multiple entries share the same second.

4. **Error handling is inadequate** - Bare `except:` clauses mask failures. Silent continuation after feed failures hides broken sources.

5. **No incremental updates** - Fetches and rewrites entire category state every run. Wastes bandwidth, loses intermediate results on failure.

### Production needs (operational maturity):

6. **Attend lacks sophistication** - No diversity enforcement, source balancing, or quality ranking. Just raw time sorting.

7. **No rate limiting or caching** - Hammers RSS sources on every invocation. No HTTP caching headers, ETags, or politeness delays.

8. **Remember has no retention policy** - JSON files grow unbounded. No pruning of old entries.

9. **No observability** - Logging only in opt-in mode. No metrics on feed health, fetch times, or error rates.

10. **Configuration is brittle** - Direct JSON file manipulation. No validation, no migration strategy, no backup.

## Plan

### 1. Strengthen Filter (Critical)

**Add multi-layer validation:**

```python
def validate_entry(feed, source):
    """Return (is_valid, sanitized_entry) tuple"""
    
    # Required fields
    if not getattr(feed, 'link', None):
        return False, None
    if not feed.title or len(feed.title.strip()) == 0:
        return False, None
    
    # URL validation
    if not feed.link.startswith(('http://', 'https://')):
        return False, None
    
    # Timestamp validation (existing logic)
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        return False, None
    
    # Future date rejection
    ts = int(time.mktime(parsed_time))
    if ts > time.time() + 86400:  # More than 1 day in future
        return False, None
    
    # Sanitize title (length limit, strip HTML)
    title = feed.title[:500].strip()
    
    return True, {
        'parsed_time': parsed_time,
        'title': title,
        'link': feed.link,
        'source': source
    }
```

**Track rejection reasons:**
```python
rejection_stats = {'no_link': 0, 'no_title': 0, 'invalid_url': 0, 'future_date': 0}
```

Write rejection stats to output JSON for monitoring.

---

### 2. Fix Cache ID Collisions (Critical)

**Replace timestamp-only IDs with composite keys:**

```python
import hashlib

def generate_entry_id(feed, timestamp):
    """Create collision-resistant ID"""
    unique_str = f"{timestamp}:{feed.link}:{feed.title}"
    hash_suffix = hashlib.md5(unique_str.encode()).hexdigest()[:8]
    return f"{timestamp}_{hash_suffix}"

# Usage
entries = {
    "id": generate_entry_id(feed, ts),
    "timestamp": ts,  # Keep for sorting
    # ...
}
```

---

### 3. Implement Consolidate (Critical)

**Add read/unread tracking:**

```python
def load_state(category):
    """Load previous run state"""
    state_file = os.path.join(p["path_data"], f"state_{category}.json")
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            return json.load(f)
    return {'read_ids': set(), 'last_fetch': {}}

def save_state(category, state):
    """Persist state for next run"""
    state_file = os.path.join(p["path_data"], f"state_{category}.json")
    # Convert sets to lists for JSON
    serializable = {
        'read_ids': list(state['read_ids']),
        'last_fetch': state['last_fetch']
    }
    with open(state_file, 'w') as f:
        json.dump(serializable, f)

def mark_new_entries(entries, state):
    """Flag entries not seen before"""
    for entry in entries:
        entry['is_new'] = entry['id'] not in state['read_ids']
    return entries
```

**Track per-source fetch success:**

```python
state['last_fetch'][source] = {
    'timestamp': int(time.time()),
    'success': True,
    'entry_count': len(new_entries)
}
```

**Use fetch history to adjust behavior:**
- Skip sources that have failed 3+ times in a row
- Add exponential backoff for failed sources
- Prioritize sources with higher success rates in Attend stage

---

### 4. Robust Error Handling (Critical)

**Replace bare excepts with specific handling:**

```python
import logging
from urllib.error import URLError
import socket

logger = logging.getLogger(__name__)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            
            d = feedparser.parse(url)
            
            # Check for parsing errors
            if d.bozo and not d.entries:
                raise ValueError(f"Feed parse error: {d.bozo_exception}")
            
            if log:
                sys.stdout.write(f" - Done ({len(d.entries)} entries)\n")
                
        except (URLError, socket.timeout) as e:
            error_msg = f"Network error fetching {url}: {str(e)}"
            logger.error(error_msg)
            errors.append({'source': source, 'error': error_msg})
            if log:
                sys.stdout.write(f" - Failed: {error_msg}\n")
            continue
            
        except Exception as e:
            error_msg = f"Unexpected error parsing {url}: {str(e)}"
            logger.exception(error_msg)
            errors.append({'source': source, 'error': error_msg})
            if log:
                sys.stdout.write(f" - Failed: {error_msg}\n")
            continue
        
        # Process entries...
    
    # Include errors in output
    rslt['errors'] = errors
    rslt['success_count'] = len(urls) - len(errors)
```

---

### 5. Incremental Updates (Critical)

**Only fetch changed feeds:**

```python
def should_fetch(source, state, min_interval=300):
    """Check if enough time has passed since last fetch"""
    last_fetch = state.get('last_fetch', {}).get(source, {})
    if not last_fetch:
        return True
    
    time_since = time.time() - last_fetch.get('timestamp', 0)
    return time_since >= min_interval

def merge_entries(old_entries, new_entries, max_age_days=7):
    """Combine old and new, pruning ancient entries"""
    cutoff = time.time() - (max_age_days * 86400)
    
    by_id = {e['id']: e for e in old_entries if e['timestamp'] > cutoff}
    by_id.update({e['id']: e for e in new_entries})
    
    return sorted(by_id.values(), key=lambda x: x['timestamp'], reverse=True)
```

---

### 6. Enhance Attend (Production)

**Add source diversity and quality signals:**

```python
def rank_entries(entries, state, max_per_source=5):
    """Prioritize by recency but enforce source diversity"""
    
    # Group by source
    by_source = {}
    for entry in entries:
        source = entry['sourceName']
        by_source.setdefault(source, []).append(entry)
    
    # Interleave sources
    result = []
    source_lists = list(by_source.values())
    
    while source_lists:
        for source_entries in source_lists[:]:
            if source_entries:
                result.append(source_entries.pop(0))
                
                # Limit per source
                if len([e for e in result if e['sourceName'] == source_entries[0]['sourceName'] if source_entries else None]) >= max_per_source:
                    source_lists.remove(source_entries)
            else:
                source_lists.remove(source_entries)
    
    return result
```

---

### 7. Add HTTP Caching (Production)

**Respect cache headers:**

```python
def fetch_with_cache(url, state):
    """Use ETags and Last-Modified headers"""
    headers = {}
    
    cache_data = state.get('http_cache', {}).get(url, {})
    if 'etag' in cache_data:
        headers['If-None-Match'] = cache_data['etag']
    if 'last_modified' in cache_data:
        headers['If-Modified-Since'] = cache_data['last_modified']
    
    # feedparser supports headers via request_headers parameter
    d = feedparser.parse(url, request_headers=headers)
    
    # Store cache headers for next time
    if hasattr(d, 'etag'):
        state.setdefault('http_cache', {})[url] = {
            'etag': d.etag,
            'last_modified': getattr(d, 'modified', None)
        }
    
    return d
```

---

### 8. Add Retention Policy (Production)

**Automatic pruning:**

```python
def prune_old_entries(entries, max_entries=1000, max_age_days=30):
    """Keep only recent entries"""
    cutoff = time.time() - (max_age_days * 86400)
    
    recent = [e for e in entries if e['timestamp'] > cutoff]
    return recent[:max_entries]  # Also limit by count
```

Apply in `get_feed_from_rss` before saving.

---

### 9. Add Observability (Production)

**Structured logging and metrics:**

```python
import logging.config

LOGGING = {
    'version': 1,
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': os.path.join(p['path_data'], 'rreader.log'),
            'maxBytes': 10485760,  # 10MB
            'backupCount': 3,
        }
    },
    'root': {
        'level': 'INFO',
        'handlers': ['file']
    }
}

def record_metrics(category, fetch_stats):
    """Write metrics for monitoring"""
    metrics = {
        'timestamp': time.time(),
        'category': category,
        'sources_attempted': fetch_stats['total'],
        'sources_succeeded': fetch_stats['success'],
        'entries_fetched': fetch_stats['entries'],
        'duration_seconds': fetch_stats['duration']
    }
    
    # Append to metrics file
    metrics_file = os.path.join(p['path_data'], 'metrics.jsonl')
    with open(metrics_file, 'a') as f:
        f.write(json.dumps(metrics) + '\n')
```

---

### 10. Validate Configuration (Production)

**Schema validation on load:**

```python
def validate_feeds_config(config):
    """Ensure feeds.json is well-formed"""
    if not isinstance(config, dict):
        raise ValueError("Config must be a dictionary")
    
    for category, data in config.items():
        if 'feeds' not in data:
            raise ValueError(f"Category {category} missing 'feeds' key")
        
        if not isinstance(data['feeds'], dict):
            raise ValueError(f"Category {category} feeds must be a dict")
        
        for source, url in data['feeds'].items():
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL for {source}: {url}")
    
    return config

# Use in load path
with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = validate_feeds_config(json.load(fp))
```

---

## Summary Priority

**Week 1:** Items 1-4 (Filter, Cache IDs, Consolidate basics, Error handling)  
**Week 2:** Item 5 (Incremental updates)  
**Week 3:** Items 6-8 (Attend, HTTP caching, Retention)  
**Week 4:** Items 9-10 (Observability, Config validation)

The current system works for personal use but lacks production resilience. The consolidate stage is the biggest conceptual gap—without it, the system cannot improve or adapt. The cache collision bug is the most dangerous defect.