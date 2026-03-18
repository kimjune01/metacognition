# Information System Diagnostic Report: RSS Reader

## Observations

This system fetches RSS feeds and converts them into a standardized JSON format for display. Currently working capabilities:

1. **Perceive:** Fetches RSS/Atom feeds via HTTP using `feedparser`
2. **Cache:** Stores parsed feed entries in JSON files (`rss_{category}.json`) with normalized structure (id, sourceName, pubDate, timestamp, url, title)
3. **Filter:** Partial - deduplicates entries by timestamp (using timestamp as dict key, later entries overwrite earlier ones with same timestamp)
4. **Attend:** Present - sorts entries by timestamp descending (most recent first)
5. **Remember:** Present - persists results to disk as JSON files
6. **Consolidate:** Absent - no learning or adaptation based on past results

Additional working features:
- Multi-category feed organization
- Timezone-aware date formatting (Seoul KST)
- User feed configuration that preserves custom feeds while adding new bundled categories
- Per-category author display configuration

## Triage

### Critical gaps (blocks production use)

1. **Filter stage is shallow** - Only deduplicates by exact timestamp collision (rare). No validation of feed quality, broken links, malformed entries, or duplicate content with different timestamps.

2. **Perceive stage has no error resilience** - Single feed failure causes silent exit (`sys.exit(0)`). No retry logic, timeout handling, or partial success recovery.

3. **No staleness detection** - System can't identify or skip feeds that haven't updated, wasting bandwidth and time.

4. **Consolidate stage is absent** - No mechanism to learn which feeds are unreliable, which sources users prefer, or which entries get clicked.

### High-priority gaps (limits utility)

5. **No incremental updates** - Always fetches entire feed history, no tracking of "last seen" entry to fetch only new items.

6. **Timestamp collision handling is destructive** - When two entries share a timestamp, one is silently dropped. Should append sequence number or use compound key.

7. **No content extraction** - Only stores title/link, missing description/summary that most feeds provide.

8. **No rate limiting or politeness delay** - Could hammer servers or get blocked.

### Medium-priority gaps (quality of life)

9. **Silent failure modes** - Bare `except:` clauses swallow all errors, making debugging impossible.

10. **No feed metadata tracking** - Can't show when feed was last successfully updated, error rates, or average post frequency.

11. **No entry age filtering** - Fetches ancient entries on first run even if they're years old.

12. **Fixed timezone** - Hardcoded to KST, not configurable per user.

## Plan

### 1. Strengthen Filter stage

**What to add:**
- Entry validation before adding to results dict
- Content quality checks
- Age-based filtering

**Concrete changes:**

```python
def is_valid_entry(feed, max_age_days=30):
    """Filter stage validation"""
    # Must have both link and title
    if not getattr(feed, 'link', None) or not getattr(feed, 'title', '').strip():
        return False
    
    # Must have parseable timestamp
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        return False
    
    # Reject entries older than max_age_days
    entry_date = datetime.datetime(*parsed_time[:6])
    age = datetime.datetime.now() - entry_date
    if age.days > max_age_days:
        return False
    
    return True

# In get_feed_from_rss, add after "for feed in d.entries:"
if not is_valid_entry(feed):
    continue
```

### 2. Add error resilience to Perceive stage

**What to add:**
- Per-feed error handling with logging
- Timeout configuration
- Retry logic with exponential backoff

**Concrete changes:**

```python
import requests
from urllib.parse import urlparse

def fetch_with_retry(url, max_retries=3, timeout=10):
    """Resilient fetch with timeout and retry"""
    for attempt in range(max_retries):
        try:
            # Use requests instead of feedparser.parse directly for timeout control
            response = requests.get(url, timeout=timeout)
            response.raise_for_status()
            return feedparser.parse(response.content)
        except requests.Timeout:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # exponential backoff
        except requests.RequestException as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)
    return None

# Replace in get_feed_from_rss:
try:
    if log:
        sys.stdout.write(f"- {url}")
    d = fetch_with_retry(url)
    if log:
        sys.stdout.write(" - Done\n")
except Exception as e:
    if log:
        sys.stdout.write(f" - Failed: {str(e)}\n")
    continue  # Skip this feed, process others
```

### 3. Implement incremental updates (Remember + Filter integration)

**What to add:**
- Track last-seen entry per feed
- Only process new entries
- Merge with existing cached entries

**Concrete changes:**

```python
# Add to get_feed_from_rss before processing feeds:
existing_data_path = os.path.join(p["path_data"], f"rss_{category}.json")
last_seen = {}
existing_entries = {}

if os.path.exists(existing_data_path):
    with open(existing_data_path, 'r', encoding='utf-8') as f:
        existing = json.load(f)
        existing_entries = {e['id']: e for e in existing.get('entries', [])}
        # Track highest timestamp per source
        for entry in existing['entries']:
            source = entry['sourceName']
            last_seen[source] = max(last_seen.get(source, 0), entry['timestamp'])

# In feed processing loop, add after timestamp calculation:
if ts <= last_seen.get(author, 0):
    continue  # Already seen this entry

# Before writing, merge with existing:
rslt.update(existing_entries)  # Add existing entries back
```

### 4. Fix timestamp collision handling

**What to add:**
- Compound key using timestamp + URL hash
- Or append entries to list instead of using dict

**Concrete changes:**

```python
import hashlib

# Replace id generation:
entry_hash = hashlib.md5(feed.link.encode()).hexdigest()[:8]
unique_id = f"{ts}_{entry_hash}"

entries = {
    "id": unique_id,  # Now collision-resistant
    # ... rest of fields
}

rslt[entries["id"]] = entries
```

### 5. Add Consolidate stage (learning)

**What to add:**
- Track feed reliability metrics
- Record user preferences (if UI exists)
- Adjust fetch frequency based on update patterns

**Concrete changes:**

```python
# New file: feed_stats.json structure
{
    "category_name": {
        "source_name": {
            "last_success": timestamp,
            "last_failure": timestamp,
            "failure_count": int,
            "success_count": int,
            "avg_entries_per_fetch": float,
            "avg_update_interval_hours": float
        }
    }
}

# Add after each feed fetch:
def update_feed_stats(category, source, success, entry_count=0):
    stats_file = os.path.join(p["path_data"], "feed_stats.json")
    stats = {}
    if os.path.exists(stats_file):
        with open(stats_file, 'r') as f:
            stats = json.load(f)
    
    if category not in stats:
        stats[category] = {}
    if source not in stats[category]:
        stats[category][source] = {
            "failure_count": 0,
            "success_count": 0,
            "last_success": None,
            "last_failure": None
        }
    
    source_stats = stats[category][source]
    now = int(time.time())
    
    if success:
        source_stats["success_count"] += 1
        source_stats["last_success"] = now
        source_stats["last_entry_count"] = entry_count
    else:
        source_stats["failure_count"] += 1
        source_stats["last_failure"] = now
    
    # Skip unreliable feeds (>80% failure rate over 10+ attempts)
    total = source_stats["success_count"] + source_stats["failure_count"]
    if total > 10 and source_stats["failure_count"] / total > 0.8:
        return False  # Signal to skip this feed
    
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    return True

# Use before fetching each feed to decide whether to skip
```

### 6. Add structured logging

**What to add:**
- Replace bare `except:` with specific exception handling
- Log errors to file with timestamps
- Return structured results

**Concrete changes:**

```python
import logging

# At module level:
logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Replace all bare except clauses:
except feedparser.NonXMLContentType as e:
    logging.error(f"Invalid feed format for {url}: {e}")
    continue
except Exception as e:
    logging.error(f"Unexpected error fetching {url}: {e}", exc_info=True)
    continue
```

### 7. Add content extraction

**What to add:**
- Store summary/description field
- Extract full content if available

**Concrete changes:**

```python
entries = {
    "id": unique_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', '')[:500],  # Limit length
    "content": getattr(feed, 'content', [{}])[0].get('value', '')[:2000] if hasattr(feed, 'content') else ''
}
```