# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Successfully fetches and parses RSS/Atom feeds using `feedparser`
2. **Multi-source aggregation**: Handles multiple feed sources organized by category
3. **Timestamp normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
5. **Persistence**: Saves parsed feeds as JSON files in `~/.rreader/` directory
6. **Time-aware display**: Shows "HH:MM" for today's entries, "Mon DD, HH:MM" for older ones
7. **Configuration management**: Maintains a `feeds.json` config file with automatic migration of new bundled categories
8. **Author attribution**: Supports per-category author display preferences
9. **Sorted output**: Returns entries in reverse chronological order
10. **Graceful degradation**: Falls back to source name when author is unavailable, handles missing timestamps

## Triage

### Critical Gaps

1. **No error recovery or retry logic** (Priority: HIGH)
   - Single feed failure exits entire process with `sys.exit(0)`
   - Network timeouts have no handling
   - Malformed feeds crash the category processing

2. **No stale data handling** (Priority: HIGH)
   - Cached JSON files never expire
   - No indication of when feeds were last successfully updated
   - Cannot distinguish between "old but valid" and "failed to update"

3. **Memory inefficiency** (Priority: MEDIUM)
   - Loads all historical entries into memory for deduplication
   - No limit on feed size or entry count
   - Dictionary grows unbounded with timestamp keys

4. **Missing observability** (Priority: MEDIUM)
   - Silent failures when `log=False`
   - No metrics on feed health (success rate, latency, error types)
   - Cannot diagnose why a feed stopped updating

### Important Gaps

5. **No concurrent fetching** (Priority: MEDIUM)
   - Processes feeds serially
   - One slow feed blocks all others in its category
   - No timeout configuration

6. **Weak feed validation** (Priority: MEDIUM)
   - Accepts any URL without schema validation
   - Doesn't verify feed format before parsing
   - No detection of dead/moved feeds

7. **No entry content storage** (Priority: LOW)
   - Only stores title, link, and metadata
   - Cannot provide summaries or full-text search
   - Loses `feed.summary` or `feed.content` fields

8. **Primitive logging** (Priority: LOW)
   - Mix of stdout writes and implicit returns
   - No structured logging or severity levels
   - Cannot filter or route diagnostic output

## Plan

### 1. Error Recovery and Retry Logic

**Changes needed:**
- Replace `sys.exit()` with `continue` in the URL loop
- Wrap `feedparser.parse()` in try-except to catch `URLError`, `HTTPError`, `Timeout`
- Add feed-level result tracking:
  ```python
  failed_feeds = []
  for source, url in urls.items():
      try:
          d = feedparser.parse(url, timeout=30)
          if d.bozo:  # feedparser's error flag
              failed_feeds.append((source, str(d.bozo_exception)))
              continue
      except Exception as e:
          failed_feeds.append((source, str(e)))
          continue
  ```
- Return both `rslt` and `failed_feeds` from `get_feed_from_rss()`
- Write failures to a separate `rss_{category}_errors.json` file with timestamp

### 2. Stale Data Handling

**Changes needed:**
- Add `last_updated` and `last_success` timestamps to output JSON
- Before writing new file, check age of existing:
  ```python
  old_data = None
  cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
  if os.path.exists(cache_file):
      with open(cache_file) as f:
          old_data = json.load(f)
          if time.time() - old_data.get("created_at", 0) < 300:  # 5min cache
              return old_data
  ```
- Add `status` field: `"fresh"`, `"stale"`, `"failed"`
- Include feed-level metadata: `{"feed_url": {"last_success": ts, "last_error": msg}}`

### 3. Memory Efficiency

**Changes needed:**
- Limit deduplication window to recent entries:
  ```python
  MAX_ENTRIES = 1000
  DEDUP_WINDOW_DAYS = 7
  cutoff_ts = int(time.time()) - (DEDUP_WINDOW_DAYS * 86400)
  
  rslt = {entry["id"]: entry for entry in existing_entries 
          if entry["timestamp"] > cutoff_ts}[:MAX_ENTRIES]
  ```
- Stream-process feeds instead of loading all into memory
- Use `heapq.nlargest()` for top-N selection instead of full sort

### 4. Observability

**Changes needed:**
- Replace stdout writes with Python's `logging` module:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  
  logger.info(f"Fetching {url}")
  logger.error(f"Failed to parse {url}: {e}")
  ```
- Add structured metrics dict:
  ```python
  metrics = {
      "feeds_attempted": len(urls),
      "feeds_succeeded": success_count,
      "entries_added": new_entry_count,
      "duration_ms": int((end - start) * 1000)
  }
  ```
- Write metrics to `rss_{category}_metrics.json`

### 5. Concurrent Fetching

**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor`:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def fetch_one_feed(source, url, timeout=30):
      try:
          d = feedparser.parse(url)
          return source, d, None
      except Exception as e:
          return source, None, str(e)
  
  with ThreadPoolExecutor(max_workers=10) as executor:
      futures = {executor.submit(fetch_one_feed, s, u): s 
                 for s, u in urls.items()}
      for future in as_completed(futures):
          source, data, error = future.result()
  ```
- Add `feed_timeout` to config per-category
- Implement max retries with exponential backoff

### 6. Feed Validation

**Changes needed:**
- Add schema validation before first fetch:
  ```python
  from urllib.parse import urlparse
  
  def validate_feed_url(url):
      parsed = urlparse(url)
      if parsed.scheme not in ('http', 'https'):
          raise ValueError(f"Invalid scheme: {parsed.scheme}")
      if not parsed.netloc:
          raise ValueError("Missing domain")
      return True
  ```
- Check `feedparser.bozo` flag and log warning for malformed feeds
- Implement HTTP HEAD request health check:
  ```python
  response = requests.head(url, timeout=5)
  if response.status_code >= 400:
      logger.warning(f"Feed returned {response.status_code}")
  ```
- Store per-feed health history (last 10 checks) in metadata

### 7. Entry Content Storage

**Changes needed:**
- Extend entry dict to include:
  ```python
  entries = {
      # ... existing fields ...
      "summary": getattr(feed, 'summary', '')[:500],  # truncate
      "content": getattr(feed, 'content', [{}])[0].get('value', '')[:2000],
      "tags": [tag.term for tag in getattr(feed, 'tags', [])],
  }
  ```
- Add config flag `store_content: bool` per category to opt-in
- Implement separate content storage for large entries (e.g., `{entry_id}.txt` files)

### 8. Structured Logging

**Changes needed:**
- Configure logging at module level:
  ```python
  import logging
  import sys
  
  def setup_logging(level=logging.INFO):
      handler = logging.StreamHandler(sys.stdout)
      handler.setFormatter(logging.Formatter(
          '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
      ))
      logger = logging.getLogger(__name__)
      logger.addHandler(handler)
      logger.setLevel(level)
      return logger
  ```
- Replace all `sys.stdout.write()` and `print()` calls with `logger.info()`/`logger.error()`
- Add `--log-level` CLI argument to control verbosity
- Write errors to separate log file: `~/.rreader/errors.log`