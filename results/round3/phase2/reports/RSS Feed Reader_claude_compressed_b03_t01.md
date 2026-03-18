# RSS Reader Diagnostic Report

## Observations

This system fetches and caches RSS feeds into local JSON files. Here's what it currently does:

**Working capabilities:**
- **Perceive**: Ingests RSS feeds via `feedparser.parse()` from configured URLs
- **Cache**: Stores normalized feed entries as JSON at `~/.rreader/rss_{category}.json`
- **Filter**: Basic filtering exists - drops entries without valid timestamps
- **Partial Consolidate**: Merges new bundled feed categories into user's feed list (forward-only merge)
- **Multi-source aggregation**: Combines multiple RSS sources per category, deduplicates by timestamp
- **Time normalization**: Converts all timestamps to KST (UTC+9), formats for display
- **Selective refresh**: Can update single category or all categories

## Triage

**Critical gaps:**

1. **No Attend stage** - System dumps all filtered entries in reverse chronological order. No ranking, no diversity enforcement, no limit on output size.

2. **No Remember stage** - Each run overwrites the previous cache completely. No accumulation, no read history, no state between runs.

3. **Shallow Filter** - Only rejects missing timestamps. Doesn't handle: duplicates across runs, invalid URLs, malformed titles, or quality thresholds.

4. **Shallow Consolidate** - Only adds new categories from bundled feeds. Doesn't learn from user behavior, doesn't prune dead feeds, doesn't adjust rankings.

**Secondary gaps:**

5. **No error recovery** - `sys.exit()` on parse failure kills the entire run instead of skipping one bad feed

6. **No staleness detection** - Can't tell if a feed hasn't updated in months

7. **No rate limiting** - Hits all URLs synchronously with no backoff

## Plan

### 1. Add Attend stage (highest priority)

**What to change:**
- Add `MAX_ENTRIES_PER_CATEGORY` config constant (e.g., 50)
- After aggregating all entries, implement diversity ranking:
  - Group by `sourceName` 
  - Interleave entries to prevent one source dominating
  - Cap total at `MAX_ENTRIES_PER_CATEGORY`
- Add function: `def rank_entries(entries: list, max_count: int) -> list`

**Where:** Insert between line 76 (after sorting) and line 79 (before writing JSON)

### 2. Add Remember stage

**What to change:**
- Create `~/.rreader/rss_{category}_history.json` to track:
  - `read_ids`: set of entry IDs user has seen
  - `last_fetch`: timestamp of previous fetch
- On each run:
  - Load history file
  - Mark new vs. returning entries: `"is_new": entry_id not in read_ids`
  - Append current entry IDs to `read_ids`
  - Update `last_fetch`
  - Write history file
- Expose read status in output JSON: `"unread_count": len([e for e in entries if e["is_new"]])`

**Where:** Add `load_history()` and `save_history()` functions, call them at start/end of `get_feed_from_rss()`

### 3. Strengthen Filter stage

**What to change:**
- Add validation checks in the feed loop (before line 52):
  ```python
  if not getattr(feed, 'link', None):
      continue  # reject entries without URLs
  if not getattr(feed, 'title', '').strip():
      continue  # reject blank titles
  ```
- Add cross-run duplicate detection:
  - Load previous `rss_{category}.json` 
  - Build set of seen `(url, timestamp)` tuples
  - Skip entries already present: `if (feed.link, ts) in seen: continue`

**Where:** Lines 39-52 in the feed processing loop

### 4. Implement Consolidate learning

**What to change:**
- Create `~/.rreader/feed_stats.json` tracking per-feed metrics:
  - `last_success`: timestamp
  - `failure_count`: consecutive failures
  - `entries_per_fetch`: rolling average
- After each fetch:
  - Update stats for each feed
  - Mark feeds with `failure_count > 5` as inactive
  - Remove inactive feeds from `feeds.json` (with user confirmation)
- Add CLI command: `rreader prune` to trigger cleanup

**Where:** New module `consolidate.py` with `update_feed_stats()` and `prune_dead_feeds()`, called from `do()` after all fetches complete

### 5. Add error recovery

**What to change:**
- Replace `sys.exit()` at line 34 with:
  ```python
  except Exception as e:
      if log:
          sys.stderr.write(f" - Failed: {e}\n")
      continue  # skip this feed, try next one
  ```
- Return success/failure count: `return {"entries": rslt, "failed_feeds": failed_count}`

**Where:** Lines 28-34 in exception handler

### 6. Add staleness detection

**What to change:**
- In output JSON, add per-entry field:
  ```python
  "age_hours": (time.time() - ts) / 3600
  ```
- Add feed-level staleness warning:
  ```python
  newest_entry = max(entries, key=lambda e: e["timestamp"])
  if time.time() - newest_entry["timestamp"] > 7*24*3600:
      # feed hasn't updated in 7 days
      rslt["stale_warning"] = True
  ```

**Where:** Lines 78-80 when building result dict

### 7. Add rate limiting

**What to change:**
- Add `time.sleep(0.5)` between feed fetches in the loop
- Use `concurrent.futures.ThreadPoolExecutor` with `max_workers=3` to parallelize while respecting limits
- Add `Last-Modified` / `ETag` header support via `feedparser` to minimize bandwidth

**Where:** Lines 24-35, refactor loop into `fetch_feed(source, url)` function and submit to executor

---

**Implementation order:** 1 → 2 → 3 (these three form the minimum viable production system), then 5 → 4 → 6 → 7.