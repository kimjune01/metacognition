# Diagnostic Report: RSS Reader System

## Observations

This system is an RSS feed aggregator with the following working capabilities:

1. **Feed Configuration Management**: Loads RSS feed URLs from a JSON config file, creates default config if missing, and merges new bundled categories into existing user configs
2. **Multi-source Ingestion**: Fetches and parses RSS feeds from multiple sources within categories
3. **Time Normalization**: Converts feed timestamps to a configured timezone (KST/UTC+9) with human-readable formatting
4. **Basic Deduplication**: Uses timestamp as unique ID to prevent duplicate entries within a single fetch
5. **Persistence**: Writes fetched entries to category-specific JSON files in `~/.rreader/`
6. **Reverse Chronological Sorting**: Orders entries by timestamp, newest first
7. **Optional Logging**: Provides feedback during fetch operations

## Triage

### Missing stages (by severity):

**CRITICAL:**
1. **Consolidate (Stage 6) - Completely Absent**: No learning, no update of filters/priorities based on reading history
2. **Attend (Stage 4) - Shallow**: Sorts by time only; no ranking by relevance, no diversity enforcement, no limit on output size

**HIGH:**
3. **Filter (Stage 3) - Shallow**: No quality gates beyond parsing success; accepts all parseable feeds regardless of content quality, age, or duplication across fetches
4. **Remember (Stage 5) - Shallow**: Overwrites previous results entirely; no accumulation or cross-run state tracking
5. **Error Handling**: Silent failures and sys.exit() calls make diagnosis impossible

**MEDIUM:**
6. **Cache (Stage 2) - Shallow**: Data stored but not indexed for efficient retrieval; no search capability
7. **Performance**: Synchronous fetching blocks on slow feeds
8. **Observability**: No metrics, no fetch success rates, no staleness tracking

## Plan

### 1. Consolidate (Stage 6) - Add Learning Layer

**What to change:**
- Create `~/.rreader/history.json` tracking: `{article_url: {read_at, clicked, dwell_time}}`
- Add `~/.rreader/preferences.json` storing: `{source: score, keywords: {term: weight}}`
- After each fetch, run `consolidate()` that:
  - Analyzes which sources/keywords appear in read articles
  - Increments weights for sources user engages with
  - Decrements weights for sources ignored for >7 days
  - Updates feed fetch frequencies based on engagement

**Implementation:**
```python
def consolidate():
    """Update system parameters based on reading history."""
    history = load_history()
    preferences = load_preferences()
    
    # Boost sources user clicks
    for url, data in history.items():
        if data.get('clicked'):
            source = find_source_for_url(url)
            preferences['sources'][source] = preferences['sources'].get(source, 1.0) + 0.1
    
    save_preferences(preferences)
```

### 2. Attend (Stage 4) - Add Smart Ranking

**What to change:**
- Before writing JSON, rank entries by composite score:
  - Source weight (from preferences)
  - Keyword matches (from preferences)
  - Recency (decay function, not just sort)
  - Diversity (penalize similar titles)
- Limit output to top N per category (configurable, default 50)
- Add `score` field to each entry explaining ranking

**Implementation:**
```python
def rank_entries(entries, preferences, limit=50):
    """Score and limit entries."""
    for entry in entries:
        score = 0
        score += preferences['sources'].get(entry['sourceName'], 1.0)
        score += keyword_match_score(entry['title'], preferences['keywords'])
        score += recency_score(entry['timestamp'])
        entry['_score'] = score
    
    # Diversity: penalize near-duplicates
    entries = deduplicate_similar(entries, threshold=0.8)
    
    return sorted(entries, key=lambda x: x['_score'], reverse=True)[:limit]
```

### 3. Filter (Stage 3) - Add Quality Gates

**What to change:**
- After parsing, reject entries that:
  - Are older than 30 days (configurable threshold)
  - Have titles shorter than 10 chars (likely malformed)
  - Match URL patterns in `~/.rreader/blocklist.json`
  - Are exact duplicates of previously fetched items (check against last run)
- Log rejection reasons to `~/.rreader/filtered.log`

**Implementation:**
```python
def should_reject(entry, previous_entries, blocklist, max_age_days=30):
    """Return (should_reject, reason)."""
    age_days = (time.time() - entry['timestamp']) / 86400
    if age_days > max_age_days:
        return True, f"too_old:{age_days:.1f}d"
    
    if len(entry['title']) < 10:
        return True, "title_too_short"
    
    if any(pattern in entry['url'] for pattern in blocklist):
        return True, "blocklisted_url"
    
    if entry['url'] in {e['url'] for e in previous_entries}:
        return True, "already_fetched"
    
    return False, None
```

### 4. Remember (Stage 5) - Add Accumulation

**What to change:**
- Instead of overwriting `rss_{category}.json`, append new entries
- Store `last_updated` per source to track fetch freshness
- Add `mark_as_read(url)` and `mark_as_archived(url)` functions
- Create read/unread/archived states in the data structure
- Implement rotation: archive entries older than 90 days to `rss_{category}_archive.json`

**Implementation:**
```python
def update_feed_file(category, new_entries):
    """Merge new entries with existing, maintaining state."""
    filepath = os.path.join(p["path_data"], f"rss_{category}.json")
    
    existing = {"entries": [], "created_at": 0}
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            existing = json.load(f)
    
    # Merge: new entries + existing unread
    url_to_entry = {e['url']: e for e in existing['entries']}
    for new_entry in new_entries:
        if new_entry['url'] not in url_to_entry:
            new_entry['state'] = 'unread'
            url_to_entry[new_entry['url']] = new_entry
    
    # Archive old entries
    cutoff = time.time() - (90 * 86400)
    current = [e for e in url_to_entry.values() if e['timestamp'] > cutoff]
    archived = [e for e in url_to_entry.values() if e['timestamp'] <= cutoff]
    
    if archived:
        append_to_archive(category, archived)
    
    save_feed_file(filepath, current)
```

### 5. Error Handling

**What to change:**
- Replace `sys.exit()` with proper exception handling
- Add retry logic with exponential backoff for network failures
- Create `~/.rreader/errors.log` with timestamps and full tracebacks
- Continue processing other feeds if one fails
- Add timeout (30s default) to feedparser.parse()

**Implementation:**
```python
def fetch_with_retry(url, max_attempts=3, timeout=30):
    """Fetch with exponential backoff."""
    for attempt in range(max_attempts):
        try:
            d = feedparser.parse(url, timeout=timeout)
            if d.bozo and d.bozo_exception:
                raise d.bozo_exception
            return d
        except Exception as e:
            wait = 2 ** attempt
            log_error(f"Attempt {attempt+1} failed for {url}: {e}")
            if attempt < max_attempts - 1:
                time.sleep(wait)
            else:
                log_error(f"Giving up on {url} after {max_attempts} attempts")
                return None
```

### 6. Cache (Stage 2) - Add Indexing

**What to change:**
- Create SQLite database `~/.rreader/cache.db` with schema:
  ```sql
  CREATE TABLE entries (
      url TEXT PRIMARY KEY,
      title TEXT,
      source TEXT,
      timestamp INTEGER,
      category TEXT,
      state TEXT,
      full_text TEXT
  );
  CREATE INDEX idx_timestamp ON entries(timestamp);
  CREATE INDEX idx_state ON entries(state);
  CREATE VIRTUAL TABLE entries_fts USING fts5(title, full_text);
  ```
- Add `search(query)` function using FTS5
- Add `get_unread_count()`, `get_by_source()`, `get_by_date_range()`

### 7. Performance

**What to change:**
- Use `concurrent.futures.ThreadPoolExecutor` to fetch feeds in parallel
- Add `max_workers=5` parameter (configurable)
- Add conditional GET support (ETag/Last-Modified headers)
- Store and send these headers to avoid re-downloading unchanged feeds

**Implementation:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_all_feeds(urls, max_workers=5):
    """Fetch feeds in parallel."""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(fetch_with_retry, url): (source, url)
            for source, url in urls.items()
        }
        
        results = {}
        for future in as_completed(future_to_url):
            source, url = future_to_url[future]
            try:
                results[source] = future.result()
            except Exception as e:
                log_error(f"Failed to fetch {url}: {e}")
        
        return results
```

### 8. Observability

**What to change:**
- Add `~/.rreader/metrics.json` tracking:
  - Per-source: `{fetch_count, success_count, avg_items, last_success}`
  - System-wide: `{total_fetches, total_errors, cache_hit_rate}`
- Add `--stats` CLI flag to display dashboard
- Log fetch duration per source
- Track and alert on feeds that haven't updated in 7+ days