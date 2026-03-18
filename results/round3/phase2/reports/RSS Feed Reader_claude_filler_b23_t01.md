# Diagnostic Report: RSS Reader System

## Observations

This is a functional RSS feed aggregator system with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS feeds using the `feedparser` library
2. **Multi-source Aggregation**: Handles multiple RSS sources per category from a JSON configuration file
3. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Data Persistence**: Saves parsed feeds to JSON files in `~/.rreader/` directory
5. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries from the same feed
6. **Chronological Sorting**: Orders entries by timestamp in reverse chronological order
7. **Configuration Management**: 
   - Copies bundled default feeds on first run
   - Merges new categories from updates while preserving user customizations
8. **Flexible Display**: Supports per-category `show_author` flag to toggle between source name and article author
9. **User-friendly Timestamps**: Shows time-only for today's articles, date+time for older ones
10. **Selective Updates**: Can update a single category or all categories
11. **Error Handling**: Graceful continuation when individual feeds fail to parse

## Triage

### Critical Gaps
1. **No User Interface** - System has no way to display the collected data to users
2. **No Error Logging** - Failed feeds disappear silently (except in log mode)
3. **No Rate Limiting** - Could hammer servers or get IP-banned with frequent updates

### High Priority Gaps
4. **No Caching/Conditional Requests** - Downloads entire feeds every time, wasting bandwidth
5. **No Configuration Validation** - Malformed feeds.json will cause runtime errors
6. **Single-threaded Fetching** - Sequential processing is slow for many feeds
7. **No Duplicate Detection Across Updates** - Entries with same URL but different timestamps will duplicate
8. **Hardcoded Timezone** - Should be user-configurable rather than hardcoded to KST

### Medium Priority Gaps
9. **No Feed Health Monitoring** - No tracking of which feeds are consistently failing
10. **Limited Metadata Storage** - Doesn't capture descriptions, images, categories, tags
11. **No Update Scheduling** - Requires external cron/scheduler
12. **No Data Retention Policy** - JSON files grow indefinitely
13. **No Network Timeout Configuration** - Feeds can hang indefinitely
14. **Weak ID Generation** - Second-precision timestamps can collide

### Low Priority Gaps
15. **No Feed Discovery** - Users must manually add feed URLs
16. **No OPML Import/Export** - Standard format for feed lists not supported
17. **No Read/Unread Tracking** - No way to mark which articles have been seen
18. **No Search/Filtering** - Can't search across feeds or filter by keyword
19. **No Analytics** - No metrics on feed freshness, update frequency, etc.

## Plan

### 1. User Interface (Critical)
**Changes needed:**
- Create `display.py` module with functions:
  - `list_categories()` - show available feed categories
  - `show_category(name, limit=20)` - display latest N entries from a category
  - `show_all(limit=50)` - unified view across all categories
- Add CLI using `argparse`:
  ```python
  # In __main__.py or cli.py
  parser = argparse.ArgumentParser()
  parser.add_argument('command', choices=['update', 'list', 'show'])
  parser.add_argument('--category', help='Category name')
  parser.add_argument('--limit', type=int, default=20)
  ```
- Use `rich` or `tabulate` library for formatted console output with columns for date, source, title
- Add web UI option using Flask/FastAPI serving the JSON files

### 2. Error Logging (Critical)
**Changes needed:**
- Replace `sys.exit()` with proper exception handling:
  ```python
  import logging
  
  logging.basicConfig(
      filename=os.path.join(p['path_data'], 'rreader.log'),
      level=logging.INFO,
      format='%(asctime)s - %(levelname)s - %(message)s'
  )
  
  try:
      d = feedparser.parse(url)
  except Exception as e:
      logging.error(f"Failed to parse {url}: {e}")
      continue  # Don't exit, continue with other feeds
  ```
- Track failures in a separate `feed_health.json` file with counters and last error messages
- Add summary statistics at end of update run

### 3. Rate Limiting (Critical)
**Changes needed:**
- Add minimum interval between requests:
  ```python
  import time
  
  MIN_REQUEST_INTERVAL = 1.0  # seconds
  last_request_time = 0
  
  for source, url in urls.items():
      elapsed = time.time() - last_request_time
      if elapsed < MIN_REQUEST_INTERVAL:
          time.sleep(MIN_REQUEST_INTERVAL - elapsed)
      
      d = feedparser.parse(url)
      last_request_time = time.time()
  ```
- Respect `Retry-After` headers if present
- Add per-domain rate limiting using `urllib.parse.urlparse(url).netloc`

### 4. HTTP Caching (High Priority)
**Changes needed:**
- Use `requests` library instead of feedparser's built-in fetcher:
  ```python
  import requests
  from requests_cache import CachedSession
  
  session = CachedSession(
      cache_name=os.path.join(p['path_data'], 'http_cache'),
      expire_after=300  # 5 minutes
  )
  
  response = session.get(url, headers={
      'User-Agent': 'rreader/1.0',
      'If-Modified-Since': last_modified,  # from metadata
      'If-None-Match': etag  # from metadata
  })
  
  if response.status_code == 304:
      continue  # Not modified
  
  d = feedparser.parse(response.content)
  ```
- Store ETags and Last-Modified in metadata JSON per feed
- Only parse if server indicates content changed

### 5. Configuration Validation (High Priority)
**Changes needed:**
- Add JSON schema validation:
  ```python
  import jsonschema
  
  FEEDS_SCHEMA = {
      "type": "object",
      "patternProperties": {
          ".*": {
              "type": "object",
              "properties": {
                  "feeds": {"type": "object"},
                  "show_author": {"type": "boolean"}
              },
              "required": ["feeds"]
          }
      }
  }
  
  try:
      jsonschema.validate(RSS, FEEDS_SCHEMA)
  except jsonschema.ValidationError as e:
      logging.error(f"Invalid feeds.json: {e}")
      sys.exit(1)
  ```
- Validate URLs using `validators.url(url)` library
- Provide helpful error messages pointing to specific configuration issues

### 6. Parallel Fetching (High Priority)
**Changes needed:**
- Use `concurrent.futures` for parallel downloads:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def fetch_feed(source, url):
      try:
          d = feedparser.parse(url)
          return source, d, None
      except Exception as e:
          return source, None, str(e)
  
  results = {}
  with ThreadPoolExecutor(max_workers=5) as executor:
      futures = {
          executor.submit(fetch_feed, src, url): src 
          for src, url in urls.items()
      }
      
      for future in as_completed(futures):
          source, data, error = future.result()
          if data:
              results[source] = data
          else:
              logging.error(f"{source} failed: {error}")
  ```
- Make max_workers configurable (default 5 to avoid overwhelming servers)

### 7. Cross-Update Deduplication (High Priority)
**Changes needed:**
- Change ID strategy to use URL hash instead of timestamp:
  ```python
  import hashlib
  
  def generate_entry_id(url, title):
      # Combine URL and title for uniqueness
      content = f"{url}|{title}".encode('utf-8')
      return hashlib.sha256(content).hexdigest()[:16]
  
  entry_id = generate_entry_id(feed.link, feed.title)
  ```
- Load existing entries before parsing new ones:
  ```python
  existing_ids = set()
  if os.path.exists(output_file):
      with open(output_file) as f:
          existing = json.load(f)
          existing_ids = {e['id'] for e in existing['entries']}
  
  # Only add if not seen before
  if entry_id not in existing_ids:
      rslt[entry_id] = entries
  ```

### 8. Configurable Timezone (High Priority)
**Changes needed:**
- Move timezone to `feeds.json`:
  ```json
  {
      "_settings": {
          "timezone": "America/New_York",
          "display_limit": 20
      },
      "Tech": {...}
  }
  ```
- Use `pytz` or `zoneinfo` for proper timezone handling:
  ```python
  from zoneinfo import ZoneInfo
  
  tz_str = RSS.get('_settings', {}).get('timezone', 'UTC')
  TIMEZONE = ZoneInfo(tz_str)
  ```

### 9. Feed Health Monitoring (Medium Priority)
**Changes needed:**
- Create `feed_health.json` tracking:
  ```python
  health = {
      "category/source": {
          "last_success": timestamp,
          "last_failure": timestamp,
          "consecutive_failures": 0,
          "total_requests": 100,
          "total_failures": 5,
          "last_error": "Connection timeout"
      }
  }
  ```
- Update after each fetch attempt
- Add `health` command to CLI showing problematic feeds
- Auto-disable feeds after N consecutive failures (with warning)

### 10. Enhanced Metadata (Medium Priority)
**Changes needed:**
- Expand stored entry data:
  ```python
  entries = {
      "id": entry_id,
      "sourceName": author,
      "pubDate": pubDate,
      "timestamp": ts,
      "url": feed.link,
      "title": feed.title,
      "description": getattr(feed, 'summary', '')[:500],  # truncate
      "image": getattr(feed, 'media_thumbnail', [{}])[0].get('url'),
      "categories": [tag.term for tag in getattr(feed, 'tags', [])],
      "enclosures": [e.href for e in getattr(feed, 'enclosures', [])]
  }
  ```
- Add full-text storage option for offline reading

### 11. Network Timeout Configuration (Medium Priority)
**Changes needed:**
- Add timeout to feedparser calls:
  ```python
  import socket
  socket.setdefaulttimeout(30)  # 30 second timeout
  
  # Or with requests:
  response = session.get(url, timeout=30)
  ```
- Make timeout configurable in settings

### 12. Data Retention Policy (Medium Priority)
**Changes needed:**
- Add entry pruning:
  ```python
  MAX_ENTRIES_PER_CATEGORY = 500
  MAX_AGE_DAYS = 30
  
  cutoff_time = time.time() - (MAX_AGE_DAYS * 86400)
  
  entries = [
      e for e in entries 
      if e['timestamp'] > cutoff_time
  ][:MAX_ENTRIES_PER_CATEGORY]
  ```
- Make limits configurable per category

### 13. Improved ID Generation (Medium Priority)
**Changes needed:**
- Use compound keys for truly unique IDs:
  ```python
  # Combine multiple fields for uniqueness
  unique_str = f"{feed.link}|{feed.title}|{parsed_time}"
  entry_id = hashlib.sha256(unique_str.encode()).hexdigest()[:16]
  ```
- Add collision detection and handling

### 14-19. Lower Priority Features
These can be addressed in future iterations:
- **Feed Discovery**: Add `discover_feeds(website_url)` using `feedfinder2`
- **OPML Support**: Add `import_opml()` and `export_opml()` functions
- **Read Tracking**: Add `read_entries.json` with set of read IDs
- **Search**: Add full-text search using `whoosh` or SQLite FTS
- **Analytics**: Add `stats` command showing feed metrics
- **Update Scheduling**: Document systemd timer or Windows Task Scheduler setup