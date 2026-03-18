# Diagnostic Report: RSS Feed Reader

## Observations

This system fetches RSS feeds and stores them as JSON files. Current capabilities:

1. **Perceive:** Reads RSS/Atom feeds from URLs via feedparser
2. **Cache:** Writes parsed entries to JSON files (`rss_{category}.json`)
3. **Filter:** Deduplicates entries by timestamp (using timestamp as `id` key in dict)
4. **Attend:** Sorts entries by timestamp (newest first)
5. **Remember:** Persists results to disk as JSON files

The system handles multiple feed categories, manages a user configuration file, and formats timestamps based on timezone. It merges bundled default feeds with user configurations.

## Triage

### Critical gaps (system cannot adapt or clean up):

1. **Consolidate is absent** — No backward pass. The system never learns which feeds are stale, broken, or valuable. It processes identically every run regardless of past success/failure.

2. **Filter is shallow** — Only deduplicates by timestamp collision (weak). No quality gates: doesn't reject malformed entries, broken links, duplicate titles from different sources, or spam.

3. **Attend is shallow** — Only sorts by time. No ranking by relevance, no diversity enforcement across sources, no "de-boring" logic to prevent one prolific feed from dominating.

### Moderate gaps (robustness issues):

4. **Perceive is fragile** — Bare `except` clauses swallow all errors. Failed feeds exit the program (when `log=True`) or silently continue, but don't mark feeds as problematic for future runs.

5. **Remember has no retention policy** — JSON files grow unbounded. Old entries never expire. No archival, no cleanup.

6. **Cache doesn't preserve metadata** — Loses feed descriptions, categories, media attachments. Only stores minimal entry data.

### Minor gaps (user experience):

7. **No incremental updates** — Always re-fetches all feeds completely. Wastes bandwidth and time for feeds that update infrequently.

8. **No user feedback on data quality** — User can't mark entries as "good" or "bad" to influence future filtering/ranking.

## Plan

### 1. Add Consolidate stage (highest priority)

**What:** Create a feedback loop that tracks feed health and user behavior.

**Changes:**
- Add `rss_metadata_{category}.json` file to track per-feed metrics:
  ```python
  {
    "source_name": {
      "fetch_success_rate": 0.95,
      "last_success": timestamp,
      "consecutive_failures": 0,
      "avg_entries_per_fetch": 12,
      "user_click_rate": 0.03  # if tracking enabled
    }
  }
  ```
- In `get_feed_from_rss()`, before parsing each feed:
  - Load metadata
  - Check `consecutive_failures` — if >5, skip this feed and log warning
  - Update metrics after each fetch attempt
- Add weekly cleanup task that removes feeds with `fetch_success_rate < 0.2` from metadata (user must manually remove from config)

### 2. Strengthen Filter stage

**What:** Add validation rules beyond timestamp deduplication.

**Changes:**
- After parsing entry, reject if:
  ```python
  # No valid link
  if not feed.link or not feed.link.startswith('http'):
      continue
  
  # Title too short or missing
  if not getattr(feed, 'title', None) or len(feed.title.strip()) < 10:
      continue
  
  # Duplicate title in last 24 hours (check existing JSON)
  if is_duplicate_title(feed.title, category, hours=24):
      continue
  ```
- Add `is_duplicate_title()` helper that loads existing entries and checks normalized titles (lowercase, stripped)
- Store rejected count in metadata for Consolidate stage

### 3. Strengthen Attend stage

**What:** Add relevance ranking beyond chronological sort.

**Changes:**
- Before final sort, score each entry:
  ```python
  def score_entry(entry, source_metadata):
      score = entry['timestamp']  # baseline: recency
      
      # Boost entries from reliable sources
      score += source_metadata.get('fetch_success_rate', 0.5) * 86400
      
      # Penalty for over-represented sources (diversity)
      source_count = sum(1 for e in recent_entries if e['sourceName'] == entry['sourceName'])
      if source_count > 5:
          score -= (source_count - 5) * 3600
      
      return score
  ```
- Sort by score instead of raw timestamp
- Add config option: `"ranking": "chronological" | "scored"`

### 4. Harden Perceive stage

**What:** Replace bare `except` with specific error handling.

**Changes:**
```python
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        
        # Validate response
        if d.bozo and isinstance(d.bozo_exception, Exception):
            raise d.bozo_exception
        
        if not d.entries:
            raise ValueError("No entries found")
            
        if log:
            sys.stdout.write(" - Done\n")
        
        # Update success metrics
        update_feed_metadata(category, source, success=True)
        
    except (URLError, HTTPError, ValueError, feedparser.CharacterEncodingOverride) as e:
        if log:
            sys.stdout.write(f" - Failed: {e}\n")
        update_feed_metadata(category, source, success=False)
        continue  # Don't exit, try other feeds
```

### 5. Add retention policy to Remember stage

**What:** Prevent unbounded growth of JSON files.

**Changes:**
- At end of `get_feed_from_rss()`, before writing:
  ```python
  # Keep only last 7 days
  cutoff = int(time.time()) - (7 * 86400)
  rslt["entries"] = [e for e in rslt["entries"] if e["timestamp"] > cutoff]
  ```
- Make retention period configurable per category:
  ```python
  retention_days = RSS[category].get("retention_days", 7)
  ```

### 6. Expand Cache to preserve metadata

**What:** Store richer entry data for future use.

**Changes:**
- Extend `entries` dict:
  ```python
  entries = {
      "id": ts,
      "sourceName": author,
      "pubDate": pubDate,
      "timestamp": ts,
      "url": feed.link,
      "title": feed.title,
      # Add these:
      "summary": getattr(feed, 'summary', '')[:500],  # first 500 chars
      "tags": [tag.term for tag in getattr(feed, 'tags', [])],
      "media": getattr(feed, 'media_content', []),
  }
  ```

### 7. Add incremental fetch support

**What:** Use HTTP conditional requests to avoid re-downloading unchanged feeds.

**Changes:**
- Store `etag` and `last_modified` in feed metadata
- Pass to feedparser:
  ```python
  d = feedparser.parse(url, 
                       etag=metadata.get('etag'),
                       modified=metadata.get('modified'))
  if d.status == 304:  # Not modified
      continue
  # Update metadata with d.etag and d.modified
  ```

### 8. Add user feedback mechanism

**What:** Let users signal entry quality (optional, for future ML).

**Changes:**
- Add `mark_entry()` function:
  ```python
  def mark_entry(category, entry_id, rating):
      """rating: 1 (good) or -1 (bad)"""
      feedback_file = os.path.join(p["path_data"], f"feedback_{category}.json")
      # Append {entry_id: rating, timestamp: now}
  ```
- Consolidate stage can use this to adjust source scores

---

**Implementation order:** 5 → 4 → 2 → 3 → 1 → 6 → 7 → 8

Start with retention (prevents immediate disk bloat), then error handling (prevents crashes), then filtering/ranking (improves output quality), then consolidation (enables learning), then nice-to-haves.