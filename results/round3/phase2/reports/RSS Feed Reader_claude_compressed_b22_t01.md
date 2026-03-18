# Diagnostic Report: RSS Feed Reader

## Observations

This system fetches RSS feeds and stores them as JSON files. Current working capabilities:

1. **Perceive:** Reads RSS/Atom feeds from URLs via `feedparser.parse()`
2. **Cache:** Stores parsed entries in memory dictionary, keyed by timestamp
3. **Filter (shallow):** Rejects entries without valid timestamps; deduplicates by timestamp within a single run
4. **Attend (shallow):** Sorts by timestamp descending (newest first)
5. **Remember:** Persists results to `rss_{category}.json` files with metadata including `created_at`
6. **Consolidate:** Absent

The system manages feed configuration through `feeds.json`, merging bundled defaults with user customizations. It processes feeds by category and formats timestamps for display.

## Triage

### Critical gaps

1. **Consolidate is absent** — No learning, adaptation, or updating of processing rules based on history
2. **Filter is shallow** — Only validates timestamp existence; no quality checks, no spam detection, no duplicate URL detection across runs
3. **Attend is shallow** — Only sorts by time; no diversity enforcement, no source balancing, no read/unread tracking

### Important gaps

4. **Cache doesn't support retrieval** — No query interface; can't look up "show me entries from last week" or "find entry by URL"
5. **Error handling is broken** — `sys.exit(0)` on parse failure silently succeeds; bare `except:` swallows all errors
6. **No state accumulation** — Each run overwrites previous results completely; no history, no "mark as read," no archive

### Nice-to-have gaps

7. **No rate limiting or politeness delays** — Could hammer servers or get blocked
8. **No validation of feed configuration** — Malformed `feeds.json` causes cryptic failures
9. **No incremental updates** — Always fetches full feeds even if only checking for new entries

## Plan

### 1. Add Consolidate (backward pass)

**Goal:** System learns from past behavior to improve future processing.

**Changes needed:**

```python
# Add to each stored entry:
{
    "read": false,
    "clicked": false,
    "dismissed": false,
    "score": 0.0  # computed relevance
}

# New function:
def update_feed_weights(category):
    """Read stored results and adjust source priorities."""
    history_file = os.path.join(p["path_data"], f"rss_{category}_history.json")
    weights_file = os.path.join(p["path_data"], f"weights_{category}.json")
    
    if not os.path.exists(history_file):
        return {}
    
    with open(history_file) as f:
        history = json.load(f)
    
    # Calculate click-through rate per source
    source_stats = {}
    for entry in history.get("entries", []):
        source = entry["sourceName"]
        if source not in source_stats:
            source_stats[source] = {"shown": 0, "clicked": 0}
        source_stats[source]["shown"] += 1
        if entry.get("clicked"):
            source_stats[source]["clicked"] += 1
    
    # Convert to weights (higher CTR = higher weight)
    weights = {}
    for source, stats in source_stats.items():
        ctr = stats["clicked"] / max(stats["shown"], 1)
        weights[source] = max(0.1, ctr)  # minimum weight 0.1
    
    with open(weights_file, "w") as f:
        json.dump(weights, f)
    
    return weights

# Call in do() before fetching:
weights = update_feed_weights(category)
```

### 2. Strengthen Filter

**Goal:** Reject low-quality entries before they reach the user.

**Changes needed:**

```python
def should_filter_entry(entry, category, seen_urls):
    """Return True if entry should be rejected."""
    
    # Duplicate URL within category (across all runs)
    if entry["url"] in seen_urls:
        return True
    
    # Title quality checks
    title = entry.get("title", "")
    if len(title) < 10:  # too short
        return True
    if title.isupper() and len(title) > 20:  # SPAM TITLE
        return True
    if title.count("!") > 3:  # clickbait
        return True
    
    # Content checks (if available)
    content = getattr(feed, 'summary', '')
    if 'viagra' in content.lower() or 'casino' in content.lower():
        return True
    
    return False

# Load seen URLs from persistent storage
def load_seen_urls(category):
    seen_file = os.path.join(p["path_data"], f"seen_{category}.json")
    if os.path.exists(seen_file):
        with open(seen_file) as f:
            return set(json.load(f))
    return set()

def save_seen_urls(category, urls):
    seen_file = os.path.join(p["path_data"], f"seen_{category}.json")
    with open(seen_file, "w") as f:
        json.dump(list(urls), f)

# Use in get_feed_from_rss():
seen_urls = load_seen_urls(category)
# ... after creating entries dict ...
if not should_filter_entry(entries, category, seen_urls):
    rslt[entries["id"]] = entries
    seen_urls.add(entries["url"])
save_seen_urls(category, seen_urls)
```

### 3. Strengthen Attend

**Goal:** Intelligent ranking that balances recency, source diversity, and user preferences.

**Changes needed:**

```python
def rank_entries(entries, weights, max_per_source=3):
    """Apply sophisticated ranking with diversity."""
    
    # Score each entry
    for entry in entries:
        source_weight = weights.get(entry["sourceName"], 0.5)
        age_hours = (time.time() - entry["timestamp"]) / 3600
        recency_score = 1.0 / (1.0 + age_hours/24)  # decay over days
        
        entry["score"] = source_weight * 0.6 + recency_score * 0.4
    
    # Sort by score
    entries.sort(key=lambda e: e["score"], reverse=True)
    
    # Enforce diversity: limit entries per source
    source_counts = {}
    filtered = []
    for entry in entries:
        source = entry["sourceName"]
        count = source_counts.get(source, 0)
        if count < max_per_source:
            filtered.append(entry)
            source_counts[source] = count + 1
    
    return filtered

# Replace simple sort in get_feed_from_rss():
# OLD: rslt = [val for key, val in sorted(rslt.items(), reverse=True)]
# NEW:
entries_list = list(rslt.values())
ranked = rank_entries(entries_list, weights, max_per_source=3)
rslt = {"entries": ranked, "created_at": int(time.time())}
```

### 4. Add Cache query interface

**Goal:** Enable lookups and time-range queries.

**Changes needed:**

```python
class FeedCache:
    def __init__(self, category):
        self.category = category
        self.file = os.path.join(p["path_data"], f"rss_{category}.json")
        self.data = self._load()
    
    def _load(self):
        if os.path.exists(self.file):
            with open(self.file) as f:
                return json.load(f)
        return {"entries": [], "created_at": 0}
    
    def query(self, since=None, until=None, source=None, unread_only=False):
        """Query cached entries with filters."""
        results = self.data["entries"]
        
        if since:
            results = [e for e in results if e["timestamp"] >= since]
        if until:
            results = [e for e in results if e["timestamp"] <= until]
        if source:
            results = [e for e in results if e["sourceName"] == source]
        if unread_only:
            results = [e for e in results if not e.get("read", False)]
        
        return results
    
    def get_by_url(self, url):
        """Find entry by URL."""
        for entry in self.data["entries"]:
            if entry["url"] == url:
                return entry
        return None
    
    def mark_read(self, url):
        """Mark entry as read."""
        entry = self.get_by_url(url)
        if entry:
            entry["read"] = True
            self.save()
    
    def save(self):
        with open(self.file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, ensure_ascii=False)
```

### 5. Fix error handling

**Goal:** Fail loudly, log clearly, continue gracefully.

**Changes needed:**

```python
import logging

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Replace try/except blocks:

# In fetch loop:
try:
    if log:
        sys.stdout.write(f"- {url}")
    d = feedparser.parse(url)
    
    if d.bozo:  # feedparser sets this on parse errors
        logger.warning(f"Parse warning for {url}: {d.bozo_exception}")
    
    if log:
        sys.stdout.write(" - Done\n")
        
except Exception as e:
    logger.error(f"Failed to fetch {url}: {e}")
    if log:
        sys.stdout.write(f" - Failed: {e}\n")
    continue  # Don't exit, skip this feed

# In entry parsing:
try:
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        logger.debug(f"No timestamp for entry: {feed.get('title', 'unknown')}")
        continue
    # ... rest of parsing ...
except Exception as e:
    logger.warning(f"Failed to parse entry: {e}")
    continue
```

### 6. Add incremental state accumulation

**Goal:** Preserve history across runs, support read tracking.

**Changes needed:**

```python
def merge_with_existing(category, new_entries):
    """Merge new entries with existing, preserving read state."""
    cache = FeedCache(category)
    existing = {e["url"]: e for e in cache.data["entries"]}
    
    merged = []
    for entry in new_entries:
        url = entry["url"]
        if url in existing:
            # Preserve user state from existing entry
            entry["read"] = existing[url].get("read", False)
            entry["clicked"] = existing[url].get("clicked", False)
            entry["score"] = existing[url].get("score", 0.0)
        merged.append(entry)
    
    # Keep old entries that weren't in new fetch (up to 1000 total)
    for url, old_entry in existing.items():
        if url not in {e["url"] for e in merged}:
            merged.append(old_entry)
    
    # Trim to reasonable size, keep most recent
    merged.sort(key=lambda e: e["timestamp"], reverse=True)
    return merged[:1000]

# Use in get_feed_from_rss() before saving:
rslt["entries"] = merge_with_existing(category, rslt["entries"])
```

### 7. Add rate limiting

**Goal:** Be a good HTTP citizen.

**Changes needed:**

```python
import time
from collections import defaultdict

last_fetch_time = defaultdict(float)
MIN_FETCH_INTERVAL = 1.0  # seconds between requests

def polite_fetch(url):
    """Fetch with rate limiting."""
    domain = url.split('/')[2]  # extract domain
    
    elapsed = time.time() - last_fetch_time[domain]
    if elapsed < MIN_FETCH_INTERVAL:
        time.sleep(MIN_FETCH_INTERVAL - elapsed)
    
    result = feedparser.parse(url)
    last_fetch_time[domain] = time.time()
    return result

# Use instead of feedparser.parse(url) directly
```