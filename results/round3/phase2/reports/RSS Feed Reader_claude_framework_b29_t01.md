# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Fetches and parses RSS/Atom feeds using `feedparser`
2. **Multi-category support**: Processes multiple feed categories from a JSON configuration file
3. **Bundled defaults**: Ships with default feeds that are copied on first run
4. **Timestamp normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
5. **Deduplication**: Uses timestamp as ID to prevent duplicate entries within a single fetch
6. **Sorted output**: Returns entries in reverse chronological order
7. **JSON persistence**: Writes processed feeds to separate JSON files per category
8. **Author display toggle**: Supports per-category configuration for showing feed author vs source name
9. **Graceful degradation**: Skips entries missing required fields rather than failing entirely
10. **Incremental config updates**: Merges new bundled categories into user config without overwriting

The data flow: `feeds.json` → parse RSS → dedupe by timestamp → sort → write `rss_{category}.json`

## Triage

### Critical (ship-blocking)

1. **No error recovery or retry logic** - Network failures cause silent data loss. The `try/except` around feed parsing exits with status 0 on failure, making monitoring impossible.

2. **Race conditions on concurrent execution** - Multiple processes could write `rss_{category}.json` simultaneously, corrupting data. No file locking.

3. **Unbounded memory growth** - All entries from all feeds in a category load into memory before deduplication. A malicious or misconfigured feed could exhaust memory.

4. **Timestamp collision overwrites entries** - Using `int(time.mktime())` as the deduplication key means two articles published in the same second from different feeds will overwrite each other.

### High (production-required)

5. **No feed health monitoring** - System can't distinguish between "feed down" vs "no new content" vs "parsing failed". No metrics on staleness.

6. **Missing HTTP client configuration** - No timeout, User-Agent, or respect for HTTP caching headers (ETags, Last-Modified). Will hammer dead feeds indefinitely.

7. **No incremental updates** - Every run fetches entire feeds and rewrites the JSON. For feeds with thousands of items, this is wasteful and loses the ability to track "seen" vs "new".

8. **Silent configuration errors** - Invalid feed URLs or malformed `feeds.json` fail silently. User has no visibility into what broke.

### Medium (operational quality)

9. **Hardcoded timezone** - `TIMEZONE = UTC+9` is in code. Should be in config or auto-detected.

10. **No entry expiration** - Old entries accumulate forever in the JSON files. No TTL or size limit.

11. **Blocking I/O in sequence** - Feeds are fetched serially. With 50 feeds @ 2sec each, that's 100 seconds per run.

12. **Poor date parsing fallback** - If both `published_parsed` and `updated_parsed` are missing, the entry is dropped entirely. Could fall back to feed-level date or current time.

### Low (nice-to-have)

13. **No entry content/summary** - Only stores title/link/date. Many use cases need article text or description.

14. **Inflexible output format** - Hardcoded JSON. Could support other formats (SQLite, CSV, RSS).

15. **No CLI flexibility** - Can only fetch all categories or one specific category. Can't fetch multiple specific categories.

## Plan

### For Critical Issues

**1. Error recovery and retry**
- Replace the bare `try/except` around `feedparser.parse(url)` with specific exception handling:
  ```python
  from urllib.error import URLError
  from http.client import HTTPException
  
  max_retries = 3
  for attempt in range(max_retries):
      try:
          d = feedparser.parse(url)
          if d.bozo:  # feedparser's error flag
              raise ValueError(f"Parse error: {d.bozo_exception}")
          break
      except (URLError, HTTPException, ValueError) as e:
          if attempt == max_retries - 1:
              # Log to stderr and continue to next feed
              sys.stderr.write(f"Failed to fetch {url}: {e}\n")
              return {}  # Return empty rather than exit
          time.sleep(2 ** attempt)  # exponential backoff
  ```
- Change `sys.exit()` calls to logging + return empty dict so other feeds can succeed

**2. Race condition protection**
- Add file locking before writing JSON:
  ```python
  import fcntl
  
  with open(output_path, 'w') as f:
      fcntl.flock(f.fileno(), fcntl.LOCK_EX)
      f.write(json.dumps(rslt, ensure_ascii=False))
      fcntl.flock(f.fileno(), fcntl.LOCK_UN)
  ```
- Or use atomic writes:
  ```python
  import tempfile
  
  with tempfile.NamedTemporaryFile('w', delete=False, dir=os.path.dirname(output_path)) as tmp:
      tmp.write(json.dumps(rslt, ensure_ascii=False))
      tmp.flush()
      os.fsync(tmp.fileno())
  os.replace(tmp.name, output_path)  # atomic on POSIX
  ```

**3. Memory bounds**
- Stream feed entries instead of loading all into `rslt` dict:
  ```python
  # Read existing entries first
  existing = {}
  if os.path.exists(output_path):
      with open(output_path) as f:
          existing = {e['id']: e for e in json.load(f).get('entries', [])}
  
  # Limit total entries
  MAX_ENTRIES = 1000
  for feed in d.entries[:100]:  # limit per-feed too
      # ... process feed ...
      existing[entries['id']] = entries
      if len(existing) > MAX_ENTRIES:
          # Remove oldest
          oldest = min(existing.keys())
          del existing[oldest]
  ```

**4. Fix timestamp collision**
- Change ID generation to include source and a counter:
  ```python
  import hashlib
  
  unique_id = f"{ts}:{source}:{feed.link}"
  entry_id = hashlib.sha256(unique_id.encode()).hexdigest()[:16]
  
  entries = {
      "id": entry_id,
      "timestamp": ts,
      # ... rest
  }
  ```

### For High Priority Issues

**5. Feed health monitoring**
- Add status tracking to each feed in output:
  ```python
  rslt = {
      "entries": rslt,
      "created_at": int(time.time()),
      "feed_status": {
          source: {
              "last_success": ts or None,
              "last_error": error_msg or None,
              "entry_count": count
          }
          for source in urls.keys()
      }
  }
  ```

**6. HTTP client configuration**
- Replace bare `feedparser.parse()` with configured requests:
  ```python
  import requests
  
  session = requests.Session()
  session.headers.update({'User-Agent': 'rreader/1.0'})
  
  response = session.get(url, timeout=10)
  d = feedparser.parse(response.content)
  ```
- Store ETags and use conditional requests:
  ```python
  # In feed metadata JSON:
  if etag := metadata.get(url, {}).get('etag'):
      session.headers['If-None-Match'] = etag
  
  if response.status_code == 304:
      return cached_entries
  
  metadata[url] = {'etag': response.headers.get('ETag')}
  ```

**7. Incremental updates**
- Load existing entries before fetching:
  ```python
  existing_path = os.path.join(p["path_data"], f"rss_{category}.json")
  existing_entries = {}
  if os.path.exists(existing_path):
      with open(existing_path) as f:
          data = json.load(f)
          existing_entries = {e['id']: e for e in data.get('entries', [])}
  
  # Merge new with existing
  for new_entry in new_entries:
      existing_entries[new_entry['id']] = new_entry
  ```
- Add `seen` boolean field to track new items

**8. Configuration validation**
- Add schema validation at startup:
  ```python
  def validate_feeds_config(config):
      required_keys = {'feeds'}
      for category, data in config.items():
          if not isinstance(data, dict):
              raise ValueError(f"Category {category} must be a dict")
          if not required_keys.issubset(data.keys()):
              raise ValueError(f"Category {category} missing required keys")
          for source, url in data['feeds'].items():
              if not url.startswith(('http://', 'https://')):
                  raise ValueError(f"Invalid URL for {source}: {url}")
      return True
  
  # Call after loading feeds.json
  try:
      validate_feeds_config(RSS)
  except ValueError as e:
      sys.stderr.write(f"Configuration error: {e}\n")
      sys.exit(1)
  ```

### For Medium Priority Issues

**9. Configurable timezone**
- Move timezone to `feeds.json`:
  ```json
  {
      "_config": {
          "timezone": "Asia/Seoul"
      },
      "tech": { ... }
  }
  ```
- Update code:
  ```python
  import pytz
  
  tz_name = RSS.get('_config', {}).get('timezone', 'UTC')
  TIMEZONE = pytz.timezone(tz_name)
  ```

**10. Entry expiration**
- Add TTL to config and enforce:
  ```python
  MAX_AGE_DAYS = RSS[category].get('max_age_days', 30)
  cutoff_ts = int(time.time()) - (MAX_AGE_DAYS * 86400)
  
  rslt = [e for e in rslt if e['timestamp'] > cutoff_ts]
  ```

**11. Concurrent feed fetching**
- Use `concurrent.futures`:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def fetch_feed(source, url):
      # existing parse logic
      return source, entries
  
  with ThreadPoolExecutor(max_workers=10) as executor:
      futures = {executor.submit(fetch_feed, s, u): s 
                 for s, u in urls.items()}
      for future in as_completed(futures):
          source, entries = future.result()
          rslt.update(entries)
  ```

**12. Robust date parsing**
- Add fallback chain:
  ```python
  parsed_time = (
      getattr(feed, 'published_parsed', None) or
      getattr(feed, 'updated_parsed', None) or
      d.feed.get('updated_parsed') or  # feed-level fallback
      time.localtime()  # last resort: now
  )
  ```

### For Low Priority Issues

**13. Store entry content**
- Add to entries dict:
  ```python
  entries['summary'] = getattr(feed, 'summary', '')[:500]  # truncate
  entries['content'] = getattr(feed, 'content', [{}])[0].get('value', '')[:2000]
  ```

**14. Pluggable output formats**
- Add format parameter and dispatch:
  ```python
  def write_output(data, category, format='json'):
      if format == 'json':
          write_json(data, category)
      elif format == 'sqlite':
          write_sqlite(data, category)
      # etc
  ```

**15. Multi-category CLI**
- Change argument parsing:
  ```python
  import argparse
  
  parser = argparse.ArgumentParser()
  parser.add_argument('categories', nargs='*', help='Categories to fetch')
  args = parser.parse_args()
  
  categories = args.categories or RSS.keys()
  for cat in categories:
      get_feed_from_rss(cat, RSS[cat]['feeds'])
  ```