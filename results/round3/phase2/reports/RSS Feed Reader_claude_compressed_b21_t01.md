# Diagnostic Report: RSS Feed Reader

## Observations

This system is an RSS feed aggregator that:

1. **Perceives** RSS feeds from configured URLs via `feedparser.parse()`
2. **Caches** parsed feed entries in a dictionary keyed by timestamp
3. **Filters** entries by checking for valid time fields (rejects entries without `published_parsed` or `updated_parsed`)
4. **Attends** by sorting entries by timestamp (reverse chronological order)
5. **Remembers** by writing aggregated feeds to JSON files (`rss_{category}.json`)
6. Manages feed configuration with automatic updates from bundled defaults
7. Formats publication dates relative to current day
8. Handles multiple feed categories and sources per category

**What works:** The forward pipeline from ingestion through storage is functional. The system can fetch, parse, deduplicate by timestamp, sort, and persist RSS entries.

## Triage

### Critical gaps (blocks production use):

1. **Consolidate is absent** — No learning, adaptation, or feedback loop. The system processes identically every run regardless of what users read or ignore.

2. **Filter is shallow** — Only checks for time field existence. No quality gates for: malformed URLs, duplicate content with different timestamps, spam, broken feeds, or rate-limiting failures.

3. **Attend is shallow** — Only sorts by time. No prioritization by relevance, diversity enforcement across sources, or deduplication of semantically identical articles.

4. **Error handling is destructive** — Bare `except:` clauses silently skip entries or exit the program, losing context about what failed and why.

### Important gaps (limits usability):

5. **No read/unread state** — Remember stage stores results but doesn't track user interaction. Previous runs are overwritten, not accumulated.

6. **No incremental updates** — Always fetches entire feeds. Wasteful for large feeds; vulnerable to rate limiting.

7. **No feed health monitoring** — Can't identify dead feeds, slow sources, or feeds that stopped updating.

### Nice-to-have gaps:

8. **No content preview** — Only stores title/link. Users can't preview without clicking through.

9. **No search or tag support** — Can't query historical entries or organize beyond categories.

## Plan

### 1. Add Consolidate stage (learning loop)

**Goal:** System adapts based on user behavior and feed quality.

**Changes needed:**

```python
# In Remember stage, also track:
# - Click-through rates per source
# - Last successful fetch time per feed
# - Error rates per feed

# New function:
def consolidate_metrics():
    """Read rss_*.json files and update feed rankings"""
    metrics_file = os.path.join(p["path_data"], "feed_metrics.json")
    
    # Load existing metrics or initialize
    if os.path.exists(metrics_file):
        with open(metrics_file) as f:
            metrics = json.load(f)
    else:
        metrics = {}
    
    # For each feed, calculate:
    # - Fetch success rate (last 10 attempts)
    # - Average entries per fetch
    # - Age of last successful entry
    
    # Update feeds.json to:
    # - Disable feeds with >80% error rate
    # - Adjust fetch frequency based on update patterns
    # - Rank sources by engagement (if tracking clicks)
    
    with open(metrics_file, 'w') as f:
        json.dump(metrics, f)
    
    return metrics

# Call at end of do():
consolidate_metrics()
```

### 2. Strengthen Filter stage

**Goal:** Reject low-quality input before storage.

**Changes needed:**

```python
def validate_entry(feed, source, seen_urls):
    """Return (valid, reason) tuple"""
    
    # Check 1: Required fields
    if not hasattr(feed, 'link') or not hasattr(feed, 'title'):
        return False, "missing_required_fields"
    
    # Check 2: Valid URL
    if not feed.link.startswith(('http://', 'https://')):
        return False, "invalid_url"
    
    # Check 3: Duplicate URL in this batch
    if feed.link in seen_urls:
        return False, "duplicate_url"
    
    # Check 4: Title quality (not just punctuation/whitespace)
    if len(feed.title.strip()) < 5:
        return False, "title_too_short"
    
    # Check 5: Not from a failed source (check metrics)
    # if source in disabled_sources:
    #     return False, "source_disabled"
    
    return True, None

# In get_feed_from_rss(), before creating entries:
seen_urls = set()
rejected = []

for feed in d.entries:
    valid, reason = validate_entry(feed, source, seen_urls)
    if not valid:
        rejected.append((feed.get('link', 'unknown'), reason))
        continue
    
    seen_urls.add(feed.link)
    # ... rest of processing

# Log rejection stats
if log:
    sys.stdout.write(f"  Accepted: {len(seen_urls)}, Rejected: {len(rejected)}\n")
```

### 3. Improve Attend stage

**Goal:** Prioritize diverse, relevant content.

**Changes needed:**

```python
def rank_entries(entries, category_config):
    """Sort by relevance, not just time"""
    
    # Diversity: limit entries per source
    max_per_source = category_config.get('max_per_source', 5)
    source_counts = {}
    ranked = []
    
    for entry in sorted(entries, key=lambda x: x['timestamp'], reverse=True):
        source = entry['sourceName']
        count = source_counts.get(source, 0)
        
        if count < max_per_source:
            entry['_score'] = calculate_score(entry, category_config)
            ranked.append(entry)
            source_counts[source] = count + 1
    
    # Sort by score (time-decay + source quality)
    return sorted(ranked, key=lambda x: x['_score'], reverse=True)

def calculate_score(entry, config):
    """Combine recency with source quality"""
    age_hours = (time.time() - entry['timestamp']) / 3600
    recency_score = 1.0 / (1.0 + age_hours / 24)  # decay over days
    
    # TODO: multiply by source_quality from metrics
    # source_quality = get_source_quality(entry['sourceName'])
    
    return recency_score  # * source_quality
```

### 4. Fix error handling

**Goal:** Preserve context, don't lose data silently.

**Changes needed:**

```python
# Replace all bare except: with specific handling
import logging

logging.basicConfig(
    filename=os.path.join(p["path_data"], 'rreader.log'),
    level=logging.WARNING
)

# In feed parsing:
try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser's error flag
        logging.warning(f"Parse warning for {url}: {d.bozo_exception}")
except Exception as e:
    logging.error(f"Failed to fetch {url}: {e}")
    if log:
        sys.stdout.write(f" - Failed: {e}\n")
    continue  # Don't exit, try next feed

# In time parsing:
try:
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        logging.debug(f"No timestamp for entry: {feed.get('link', 'unknown')}")
        continue
except Exception as e:
    logging.warning(f"Time parse error: {e} for {feed.get('link')}")
    continue
```

### 5. Track read state (enhance Remember)

**Goal:** Accumulate history, don't overwrite.

**Changes needed:**

```python
# Change storage format to append-only log
def save_entries(category, new_entries):
    """Append new entries, mark with fetch timestamp"""
    history_file = os.path.join(p["path_data"], f"rss_{category}_history.jsonl")
    
    # Read existing IDs to avoid duplicates
    seen_ids = set()
    if os.path.exists(history_file):
        with open(history_file) as f:
            for line in f:
                entry = json.loads(line)
                seen_ids.add(entry['id'])
    
    # Append only new entries
    with open(history_file, 'a', encoding='utf-8') as f:
        for entry in new_entries:
            if entry['id'] not in seen_ids:
                entry['_fetched_at'] = int(time.time())
                entry['_read'] = False  # Track read state
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    # Maintain recent.json for UI (last 100 entries)
    recent = [e for e in new_entries if e['id'] not in seen_ids][:100]
    with open(os.path.join(p["path_data"], f"rss_{category}.json"), 'w') as f:
        json.dump({"entries": recent, "created_at": int(time.time())}, f)
```

### 6. Implement incremental fetching

**Goal:** Fetch only new content.

**Changes needed:**

```python
# Store last fetch timestamp per feed
def get_last_entry_time(category, source):
    """Get timestamp of most recent entry from this source"""
    try:
        with open(os.path.join(p["path_data"], f"rss_{category}.json")) as f:
            data = json.load(f)
        for entry in data['entries']:
            if entry['sourceName'] == source:
                return entry['timestamp']
    except:
        pass
    return 0

# In get_feed_from_rss():
last_seen = get_last_entry_time(category, source)

for feed in d.entries:
    # ... parse timestamp ...
    
    # Skip if we've seen this before
    if ts <= last_seen:
        continue
    
    # Process only new entries
```

### 7. Add feed health monitoring

**Goal:** Identify and handle problematic feeds.

**Changes needed:**

```python
def update_feed_health(category, source, url, success, entry_count=0):
    """Track feed reliability"""
    health_file = os.path.join(p["path_data"], "feed_health.json")
    
    # Load existing
    if os.path.exists(health_file):
        with open(health_file) as f:
            health = json.load(f)
    else:
        health = {}
    
    key = f"{category}:{source}"
    if key not in health:
        health[key] = {
            "url": url,
            "attempts": [],
            "last_success": None,
            "total_entries": 0
        }
    
    # Record this attempt (keep last 20)
    health[key]["attempts"].append({
        "timestamp": int(time.time()),
        "success": success,
        "entry_count": entry_count
    })[-20:]
    
    if success:
        health[key]["last_success"] = int(time.time())
        health[key]["total_entries"] += entry_count
    
    # Calculate success rate
    recent = health[key]["attempts"][-10:]
    success_rate = sum(1 for a in recent if a["success"]) / len(recent)
    health[key]["success_rate"] = success_rate
    
    with open(health_file, 'w') as f:
        json.dump(health, f, indent=2)
    
    return success_rate < 0.5  # Return True if feed should be disabled
```

**Priority order for implementation:** 4 (errors) → 2 (filter) → 5 (read state) → 6 (incremental) → 3 (attend) → 7 (monitoring) → 1 (consolidate)