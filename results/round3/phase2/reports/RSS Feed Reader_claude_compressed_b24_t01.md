# Diagnostic Report: RSS Feed Reader

## Observations

This system currently implements a basic RSS feed aggregator with the following capabilities:

1. **Perceive (Present):** Fetches RSS feeds from configured URLs using `feedparser.parse()`
2. **Cache (Present):** Stores parsed feed entries in JSON files (`rss_{category}.json`) with normalized structure (id, sourceName, pubDate, timestamp, url, title)
3. **Filter (Shallow):** Uses timestamp as deduplication key (entry ID), but only implicitly—duplicate timestamps would overwrite in the `rslt` dict
4. **Attend (Present):** Sorts entries by timestamp (reverse chronological) before persisting
5. **Remember (Present):** Writes results to disk as JSON files that persist across runs
6. **Consolidate (Absent):** No learning or adaptation mechanism exists

The system handles multiple feed categories, merges bundled and user feeds, and formats timestamps relative to today's date.

## Triage

### Critical Gaps

1. **Consolidate is completely absent** — The system never learns from what users actually read or changes its behavior based on past results. Each run is identical.

2. **Filter is shallow** — Only deduplicates by timestamp collision (rare). No validation of feed quality, malformed entries, spam detection, or broken links. The try-except blocks silently skip bad entries with no logging of what failed.

3. **Attend lacks user modeling** — Sorting by timestamp alone ignores relevance, user preferences, source credibility, or topic diversity.

4. **Perceive has no error resilience** — Single feed failure in a category terminates the entire process (`sys.exit(0)`). Network timeouts have no retry logic.

5. **Cache doesn't track read/unread state** — No way to distinguish new content from already-seen content across runs.

### Important Gaps

6. **No observability** — Logging only exists when `log=True` and goes to stdout. No structured logging, error tracking, or performance metrics.

7. **No incremental updates** — Always fetches entire feeds even if only checking for new items. Wasteful for large feeds.

8. **Timestamp collision vulnerability** — Using timestamp as ID means entries published in the same second overwrite each other.

### Nice-to-Have

9. **No feed health monitoring** — Doesn't track which feeds are consistently failing or stale.

10. **No rate limiting** — Could hammer servers if many feeds are configured.

## Plan

### 1. Add Consolidate stage (Critical)

**Goal:** Learn from user behavior and adapt processing.

**Changes needed:**
- Create `rss_{category}_history.json` to track per-entry metadata: `{entry_id: {"fetched_at": ts, "viewed": bool, "clicked": bool}}`
- Expose an API endpoint or CLI command to mark entries as viewed/clicked
- In `get_feed_from_rss()`, after sorting, apply scoring:
  ```python
  # Weight recent items from sources user clicks more often
  source_scores = calculate_source_engagement(category)
  for entry in rslt:
      entry['_score'] = base_time_score(entry['timestamp']) * source_scores.get(entry['sourceName'], 1.0)
  rslt = sorted(rslt, key=lambda x: x['_score'], reverse=True)
  ```
- Weekly: prune sources with 0 clicks in last 30 days from `feeds.json`

### 2. Strengthen Filter stage (Critical)

**Goal:** Reject low-quality input before storage.

**Changes needed:**
- Add validation checks in the feed loop:
  ```python
  # After parsing each feed entry:
  if not feed.get('title') or len(feed.title.strip()) < 10:
      continue  # Skip entries with missing/trivial titles
  if not feed.get('link') or not feed.link.startswith('http'):
      continue  # Skip entries with invalid URLs
  if is_duplicate_title(feed.title, rslt):  # Fuzzy match
      continue
  ```
- Create `filtered_log.json` to record what was rejected and why: `{"url": url, "reason": "missing_title", "timestamp": ts}`
- Add configurable filter rules in `feeds.json`:
  ```json
  "filters": {
      "min_title_length": 10,
      "blocked_keywords": ["sponsored", "ad:"],
      "max_age_days": 30
  }
  ```

### 3. Improve Attend with diversity (Critical)

**Goal:** Prevent single source from dominating results.

**Changes needed:**
- After initial sort, apply diversity filter:
  ```python
  def diversify(entries, max_per_source=3):
      seen_sources = {}
      result = []
      for entry in entries:
          source = entry['sourceName']
          if seen_sources.get(source, 0) < max_per_source:
              result.append(entry)
              seen_sources[source] = seen_sources.get(source, 0) + 1
      return result
  
  rslt['entries'] = diversify(rslt['entries'])
  ```
- Make `max_per_source` configurable per category in `feeds.json`

### 4. Add error resilience to Perceive (Critical)

**Goal:** Isolated failures don't crash the system.

**Changes needed:**
- Replace `sys.exit(0)` with continue:
  ```python
  except Exception as e:
      if log:
          sys.stderr.write(f" - Failed: {str(e)}\n")
      # Log to errors file
      with open(os.path.join(p["path_data"], "fetch_errors.log"), "a") as f:
          f.write(f"{time.time()},{source},{url},{str(e)}\n")
      continue  # Skip this feed, process others
  ```
- Add retry logic with exponential backoff:
  ```python
  for attempt in range(3):
      try:
          d = feedparser.parse(url, timeout=10)
          break
      except:
          if attempt < 2:
              time.sleep(2 ** attempt)
          else:
              # log and continue
  ```

### 5. Track read/unread in Cache (Critical)

**Goal:** Users see what's new since last session.

**Changes needed:**
- Load previous results at start of `get_feed_from_rss()`:
  ```python
  old_entries = {}
  cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
  if os.path.exists(cache_file):
      with open(cache_file, 'r') as f:
          old_data = json.load(f)
          old_entries = {e['id']: e for e in old_data.get('entries', [])}
  ```
- Mark entries as new:
  ```python
  entries['is_new'] = entries['id'] not in old_entries
  ```
- Add `last_viewed_at` field updated by user interaction

### 6. Add structured logging (Important)

**Goal:** Diagnose issues in production.

**Changes needed:**
- Replace print statements with Python `logging` module:
  ```python
  import logging
  logging.basicConfig(
      filename=os.path.join(p["path_data"], "rreader.log"),
      level=logging.INFO,
      format='%(asctime)s - %(levelname)s - %(message)s'
  )
  
  logging.info(f"Fetching {url}")
  logging.error(f"Failed to parse {url}: {str(e)}")
  ```
- Log metrics: fetch duration, entry count, filter rejection rate

### 7. Implement incremental updates (Important)

**Goal:** Only fetch entries newer than last run.

**Changes needed:**
- Store `last_fetch_timestamp` per feed in `feeds.json`
- Use HTTP `If-Modified-Since` header:
  ```python
  headers = {}
  if last_fetch:
      headers['If-Modified-Since'] = format_http_date(last_fetch)
  d = feedparser.parse(url, request_headers=headers)
  if d.status == 304:  # Not modified
      continue
  ```
- Update `last_fetch_timestamp` after successful fetch

### 8. Use content-based IDs (Important)

**Goal:** Prevent timestamp collision bugs.

**Changes needed:**
- Replace timestamp ID with hash of (url + title):
  ```python
  import hashlib
  entry_id = hashlib.sha256(f"{feed.link}||{feed.title}".encode()).hexdigest()[:16]
  entries['id'] = entry_id
  entries['timestamp'] = ts  # Keep for sorting
  ```

### 9. Add feed health monitoring (Nice-to-have)

**Goal:** Surface broken feeds to users.

**Changes needed:**
- Track success/failure per feed in `feed_health.json`:
  ```python
  {"source_name": {"last_success": ts, "failure_count": 0, "last_error": ""}}
  ```
- Generate weekly report of consistently failing feeds
- Add `--health-check` CLI command

### 10. Add rate limiting (Nice-to-have)

**Goal:** Be a good HTTP citizen.

**Changes needed:**
- Add delay between requests:
  ```python
  time.sleep(0.5)  # 500ms between feeds
  ```
- Respect `Retry-After` headers in 429 responses
- Add `--parallel` flag to fetch feeds concurrently with semaphore limit