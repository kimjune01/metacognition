# Diagnostic Report: RSS Feed Reader

## Observations

This system currently implements a basic RSS feed aggregator with the following working capabilities:

1. **Perceive (present):** Fetches RSS feeds from configured URLs using `feedparser.parse()`. Handles multiple sources per category.

2. **Cache (shallow):** Writes parsed entries to JSON files (`rss_{category}.json`) with timestamp-based IDs. Uses in-memory dictionary during processing.

3. **Filter (shallow):** Rejects entries missing time metadata (`published_parsed` or `updated_parsed`). Silently skips malformed entries with try/except blocks.

4. **Attend (absent):** Uses timestamp-only sorting (reverse chronological). No deduplication—duplicate entries with identical timestamps overwrite each other by accident, not design.

5. **Remember (present):** Persists results to disk as JSON. Maintains user feed configuration with merge capability for bundled defaults.

6. **Consolidate (absent):** No learning or adaptation. Processes identically every run regardless of history.

## Triage

### Critical gaps (ship-blockers)

1. **Attend is functionally absent** — The deduplication is accidental (same timestamp = same dict key). Multiple articles published in the same second from different sources will collide. No diversity enforcement, no read/unread tracking, no relevance ranking.

2. **Filter is too permissive** — Only validates time metadata exists. Accepts duplicate URLs, spam, malformed titles, broken links. No content quality checks.

3. **No error recovery** — `sys.exit()` on feed failure kills the entire batch. One bad feed URL prevents all other feeds from updating.

### Important gaps (production-hardening)

4. **Consolidate completely missing** — No user feedback loop. Can't mark articles as read, hide sources, boost/bury topics, or learn preferences.

5. **Cache has no retrieval interface** — Data is write-only. System can't query "what did I already fetch?" to enable incremental updates or prevent re-showing seen items.

6. **No staleness handling** — Cached JSON files persist forever. No TTL, no refresh logic, no indication if data is hours or months old.

### Nice-to-have gaps

7. **Limited observability** — Logging only when `log=True`. No structured logging, metrics, or debugging for production operations.

8. **No rate limiting or retry logic** — Could hammer failing feeds or get banned by aggressive polling.

## Plan

### 1. Fix Attend (implement proper deduplication and ranking)

**What to change:**
- Add a composite key for deduplication: `hash(url + title)` or use `feed.id` if available
- Maintain a separate "seen entries" index across runs (load previous JSON, extract IDs, filter new entries)
- Add explicit ranking beyond timestamp:
  ```python
  # After building rslt dict
  seen_ids = load_seen_ids(category)  # from previous runs
  rslt = {k: v for k, v in rslt.items() if k not in seen_ids}
  
  # Rank by timestamp, break ties by source priority
  source_priority = {s: i for i, s in enumerate(urls.keys())}
  rslt = sorted(
      rslt.values(), 
      key=lambda x: (x["timestamp"], source_priority.get(x["sourceName"], 999)),
      reverse=True
  )[:MAX_ENTRIES]  # limit output size
  ```

### 2. Strengthen Filter (add content validation)

**What to change:**
- Add URL deduplication within batch:
  ```python
  seen_urls = set()
  # Inside feed loop:
  if feed.link in seen_urls:
      continue
  seen_urls.add(feed.link)
  ```
- Validate required fields exist and are non-empty:
  ```python
  if not all([
      getattr(feed, 'title', '').strip(),
      getattr(feed, 'link', '').startswith('http'),
      len(feed.title) < 500  # spam check
  ]):
      continue
  ```
- Add configurable blacklist patterns in feeds.json:
  ```python
  blacklist = d.get("title_blacklist", [])
  if any(pattern in feed.title.lower() for pattern in blacklist):
      continue
  ```

### 3. Add graceful error handling

**What to change:**
- Replace `sys.exit()` with error collection:
  ```python
  errors = []
  for source, url in urls.items():
      try:
          d = feedparser.parse(url)
          # ... process ...
      except Exception as e:
          errors.append({"source": source, "url": url, "error": str(e)})
          if log:
              sys.stderr.write(f"✗ {source}: {e}\n")
          continue  # process other feeds
  
  # Include errors in output JSON
  rslt["errors"] = errors
  ```

### 4. Implement Consolidate (basic learning)

**What to change:**
- Add `rss_{category}_metadata.json` to track:
  ```python
  {
      "seen_entry_ids": set(),  # all historical IDs
      "read_entry_ids": set(),  # user marked as read
      "source_weights": {"source_name": 1.0},  # boost/bury
      "last_updated": timestamp
  }
  ```
- Provide CLI commands:
  ```python
  def mark_read(category, entry_id):
      meta = load_metadata(category)
      meta["read_entry_ids"].add(entry_id)
      save_metadata(category, meta)
  
  def adjust_source_weight(category, source, delta):
      meta = load_metadata(category)
      meta["source_weights"][source] = max(0, 
          meta["source_weights"].get(source, 1.0) + delta)
  ```
- Use weights in Attend stage ranking

### 5. Build Cache retrieval interface

**What to change:**
- Add query functions:
  ```python
  def get_entries(category, since_ts=None, unread_only=False):
      with open(os.path.join(p["path_data"], f"rss_{category}.json")) as f:
          data = json.load(f)
      
      entries = data["entries"]
      
      if since_ts:
          entries = [e for e in entries if e["timestamp"] > since_ts]
      
      if unread_only:
          meta = load_metadata(category)
          read_ids = meta.get("read_entry_ids", set())
          entries = [e for e in entries if e["id"] not in read_ids]
      
      return entries
  ```
- Use this in `do()` to implement incremental updates

### 6. Add staleness tracking

**What to change:**
- Check `created_at` timestamp before using cached data:
  ```python
  MAX_AGE_SECONDS = 3600  # 1 hour
  
  cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
  if os.path.exists(cache_file):
      with open(cache_file) as f:
          cached = json.load(f)
      
      age = int(time.time()) - cached.get("created_at", 0)
      if age < MAX_AGE_SECONDS:
          return cached  # use cache
  
  # Otherwise refresh
  ```
- Add `--force-refresh` CLI flag to override cache

### 7. Add structured logging

**What to change:**
- Replace print statements with proper logger:
  ```python
  import logging
  
  logger = logging.getLogger(__name__)
  
  # In do():
  logger.info(f"Fetching {category}: {len(urls)} sources")
  logger.debug(f"Parsed {len(d.entries)} entries from {source}")
  logger.error(f"Failed to fetch {url}: {e}")
  
  # Add metrics
  logger.info(f"Completed {category}: {len(rslt['entries'])} entries, "
              f"{len(errors)} errors, {time.time() - start:.2f}s")
  ```

### 8. Add rate limiting

**What to change:**
- Throttle requests:
  ```python
  import time
  
  MIN_INTERVAL_SECONDS = 1.0
  last_request_time = 0
  
  for source, url in urls.items():
      elapsed = time.time() - last_request_time
      if elapsed < MIN_INTERVAL_SECONDS:
          time.sleep(MIN_INTERVAL_SECONDS - elapsed)
      
      d = feedparser.parse(url)
      last_request_time = time.time()
  ```
- Add exponential backoff for failed feeds (store failure count in metadata)