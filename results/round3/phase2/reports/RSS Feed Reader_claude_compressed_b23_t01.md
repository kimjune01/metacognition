# Diagnostic Report: RSS Reader System

## Observations

This system implements an RSS feed aggregator with the following working capabilities:

1. **Perceive**: Fetches RSS feeds from URLs defined in a JSON configuration file using `feedparser`
2. **Cache**: Parses RSS entries and normalizes them into a consistent JSON structure with id, sourceName, pubDate, timestamp, url, and title
3. **Filter**: Implicit shallow filtering—skips entries missing time metadata (published_parsed or updated_parsed)
4. **Attend**: Sorts entries by timestamp (reverse chronological) and deduplicates by timestamp-as-ID
5. **Remember**: Persists parsed feeds to category-specific JSON files (`rss_{category}.json`)
6. **Configuration management**: Merges bundled default feeds with user customizations

The system runs as a batch job, processes one or all categories, and stores results to disk.

## Triage

### Critical Gaps

1. **Consolidate is completely absent** — The system never learns or adapts. No feedback loop exists.
2. **Filter is shallow** — Only checks for presence of time fields; accepts duplicate content, malformed data, or low-quality entries
3. **Attend has a fatal flaw** — Uses timestamp as ID, causing collisions when multiple articles publish at the same second
4. **Remember lacks read capability in main flow** — The system writes state but never reads previous results to inform current behavior
5. **Error handling is destructive** — `sys.exit()` on parse failure; silent `continue` on entry errors

### Important Gaps

6. **No deduplication across runs** — Same article republished will appear multiple times
7. **No content validation** — Missing title, empty URLs, or malformed links pass through
8. **No rate limiting or politeness** — Could hammer RSS servers or get blocked
9. **No staleness detection** — Old cached data never expires
10. **No incremental updates** — Always fetches entire feed history

### Nice-to-Have Gaps

11. **No monitoring or observability** — Silent failures in production
12. **No concurrency** — Sequential feed fetching is slow
13. **Limited timezone handling** — Hardcoded to KST

## Plan

### 1. Consolidate (Critical - Enables Learning)

**Add feedback loop for feed quality scoring:**

```python
# In get_feed_from_rss, before writing:
def load_feed_stats(category):
    stats_file = os.path.join(p["path_data"], f"stats_{category}.json")
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            return json.load(f)
    return {}

def update_feed_stats(category, source, entries_count, had_error):
    stats = load_feed_stats(category)
    if source not in stats:
        stats[source] = {"success": 0, "failure": 0, "total_entries": 0}
    
    if had_error:
        stats[source]["failure"] += 1
    else:
        stats[source]["success"] += 1
        stats[source]["total_entries"] += entries_count
    
    stats[source]["reliability"] = stats[source]["success"] / (stats[source]["success"] + stats[source]["failure"])
    
    with open(os.path.join(p["path_data"], f"stats_{category}.json"), 'w') as f:
        json.dump(stats, f)
    
    return stats

# Use stats to skip unreliable feeds:
stats = load_feed_stats(category)
if stats.get(source, {}).get("reliability", 1.0) < 0.3:
    continue  # Skip feeds that fail >70% of the time
```

### 2. Filter (Critical - Data Quality)

**Add multi-layer validation before accepting entries:**

```python
def validate_entry(feed, source):
    """Return (is_valid, reason) tuple"""
    
    # Required fields
    if not hasattr(feed, 'link') or not feed.link:
        return False, "missing_link"
    if not hasattr(feed, 'title') or not feed.title.strip():
        return False, "missing_title"
    
    # URL validation
    if not feed.link.startswith(('http://', 'https://')):
        return False, "invalid_url_scheme"
    
    # Content quality heuristics
    if len(feed.title) < 10:
        return False, "title_too_short"
    if len(feed.title) > 300:
        return False, "title_too_long"
    
    # Check for spam patterns
    spam_patterns = ['CLICK HERE', 'YOU WON', '💰💰💰']
    if any(pattern in feed.title.upper() for pattern in spam_patterns):
        return False, "spam_detected"
    
    return True, None

# In the loop:
is_valid, reason = validate_entry(feed, source)
if not is_valid:
    if log:
        sys.stdout.write(f"  Rejected: {reason}\n")
    continue
```

### 3. Attend (Critical - Fix ID Collision)

**Generate collision-resistant IDs using content hash:**

```python
import hashlib

def generate_entry_id(feed, timestamp):
    """Create unique ID from URL + timestamp"""
    content = f"{feed.link}|{timestamp}".encode('utf-8')
    hash_suffix = hashlib.md5(content).hexdigest()[:8]
    return f"{timestamp}_{hash_suffix}"

# Replace:
# "id": ts,
# With:
"id": generate_entry_id(feed, ts),

# Change sorting to use timestamp field:
rslt = [val for key, val in sorted(rslt.items(), key=lambda x: x[1]["timestamp"], reverse=True)]
```

### 4. Remember (Critical - Enable Stateful Operation)

**Load previous results to enable deduplication:**

```python
def load_previous_entries(category):
    """Load existing entries to prevent duplicates"""
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            data = json.load(f)
            return {e['url']: e for e in data.get('entries', [])}
    return {}

# In get_feed_from_rss:
seen_urls = load_previous_entries(category)

# After creating entries dict:
if entries["url"] in seen_urls:
    continue  # Skip already-seen articles

# Keep last N days only:
cutoff = int(time.time()) - (7 * 24 * 60 * 60)  # 7 days
rslt = [val for key, val in sorted(rslt.items(), reverse=True) if val["timestamp"] > cutoff]
```

### 5. Error Handling (Critical - Production Reliability)

**Replace destructive error handling with graceful degradation:**

```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []

    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            
            d = feedparser.parse(url)
            
            # Check if parse succeeded
            if d.bozo and not d.entries:
                raise Exception(f"Parse failed: {d.bozo_exception}")
            
            if log:
                sys.stdout.write(" - Done\n")
                
        except Exception as e:
            error_msg = f"Failed to fetch {source}: {str(e)}"
            errors.append(error_msg)
            if log:
                sys.stdout.write(f" - Failed: {str(e)}\n")
            update_feed_stats(category, source, 0, had_error=True)
            continue  # Continue with other feeds
        
        # Process entries...
        update_feed_stats(category, source, len(d.entries), had_error=False)
    
    # Always save what we got, even if some feeds failed
    if errors and log:
        sys.stdout.write(f"\nErrors encountered: {len(errors)}\n")
    
    return rslt
```

### 6. Incremental Updates (Important - Performance)

**Only fetch new entries using conditional GET:**

```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    # Load etag/modified headers from previous fetch
    meta_file = os.path.join(p["path_data"], f"meta_{category}.json")
    feed_meta = {}
    if os.path.exists(meta_file):
        with open(meta_file, 'r') as f:
            feed_meta = json.load(f)
    
    for source, url in urls.items():
        # Use conditional GET
        headers = {}
        if source in feed_meta:
            if 'etag' in feed_meta[source]:
                headers['If-None-Match'] = feed_meta[source]['etag']
            if 'modified' in feed_meta[source]:
                headers['If-Modified-Since'] = feed_meta[source]['modified']
        
        d = feedparser.parse(url, etag=headers.get('If-None-Match'), 
                            modified=headers.get('If-Modified-Since'))
        
        # Save new etag/modified for next time
        feed_meta[source] = {}
        if hasattr(d, 'etag'):
            feed_meta[source]['etag'] = d.etag
        if hasattr(d, 'modified'):
            feed_meta[source]['modified'] = d.modified
        
        # Handle 304 Not Modified
        if d.status == 304:
            if log:
                sys.stdout.write(" - Not modified\n")
            continue
    
    # Save metadata
    with open(meta_file, 'w') as f:
        json.dump(feed_meta, f)
```

### 7. Monitoring (Important - Observability)

**Add structured logging and metrics:**

```python
import logging
from datetime import datetime

logging.basicConfig(
    filename=os.path.join(p["path_data"], 'rreader.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    start_time = time.time()
    metrics = {
        'category': category,
        'feeds_attempted': len(urls),
        'feeds_succeeded': 0,
        'feeds_failed': 0,
        'entries_processed': 0,
        'entries_rejected': 0,
    }
    
    # ... existing code ...
    
    # At end:
    metrics['duration_seconds'] = time.time() - start_time
    metrics['feeds_succeeded'] = len(urls) - len(errors)
    metrics['feeds_failed'] = len(errors)
    
    logging.info(f"Feed update completed: {json.dumps(metrics)}")
    
    # Write metrics file for external monitoring
    with open(os.path.join(p["path_data"], f"metrics_{category}.json"), 'w') as f:
        json.dump(metrics, f)
```