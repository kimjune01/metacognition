# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to fetch and parse RSS/Atom feeds from multiple sources
2. **Multi-category Support**: Organizes feeds into categories, each with multiple sources
3. **Data Persistence**: Saves parsed feed entries as JSON files (one per category) in `~/.rreader/`
4. **Timestamp Handling**: Converts feed timestamps to local timezone (currently hardcoded to UTC+9/KST)
5. **Deduplication**: Uses timestamp as ID to prevent duplicate entries from the same feed
6. **Date Formatting**: Displays time as "HH:MM" for today's entries, "Mon DD, HH:MM" for older entries
7. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Copies bundled default feeds on first run
   - Merges new categories from bundled config into user config
8. **Author Display**: Configurable per-category option to show feed author or source name
9. **Selective Updates**: Can update a single category or all categories
10. **Optional Logging**: Console output for feed fetch operations

## Triage

### Critical Gaps (Blocker for Production)

1. **No Error Recovery**: Single feed failure crashes entire category update
2. **No Network Timeouts**: Hangs indefinitely on unresponsive feeds
3. **No Feed Validation**: Missing or malformed feeds.json causes crashes
4. **Hardcoded Timezone**: UTC+9 is baked in, unusable for other regions
5. **No Rate Limiting**: Can hammer feed servers, risking IP bans

### High Priority (Major Usability Issues)

6. **Silent Failures**: Exception handler exits with code 0, masking errors
7. **No Stale Data Handling**: Old cached data persists indefinitely
8. **Duplicate Detection Flawed**: Timestamp collision overwrites distinct entries
9. **No Concurrent Fetching**: Sequential processing makes updates slow
10. **Missing User Feedback**: No UI/CLI interface for viewing feeds

### Medium Priority (Quality of Life)

11. **No Feed Management**: Cannot add/remove/edit feeds without manual JSON editing
12. **No Content Extraction**: Stores only metadata, not article content/summary
13. **No Read/Unread Tracking**: Cannot mark items as read
14. **Limited Sorting Options**: Only reverse chronological
15. **No Search/Filter**: Cannot find specific articles

### Low Priority (Nice to Have)

16. **No OPML Import/Export**: Cannot migrate feeds from other readers
17. **No Update Scheduling**: Must manually trigger updates
18. **No Favicon/Image Caching**: Plain text only
19. **No Analytics**: No insight into feed reliability or update frequency
20. **No Mobile/Web Interface**: Terminal-only (implied)

## Plan

### Critical Gaps - Detailed Solutions

**1. Error Recovery**
- Wrap each `feedparser.parse()` call in individual try-except blocks
- Change structure from:
  ```python
  for source, url in urls.items():
      d = feedparser.parse(url)
  ```
  To:
  ```python
  for source, url in urls.items():
      try:
          d = feedparser.parse(url)
          # process feeds
      except Exception as e:
          if log:
              sys.stderr.write(f"  Failed: {str(e)}\n")
          continue  # Skip this source, continue with others
  ```

**2. Network Timeouts**
- Add timeout parameter to feedparser (requires requests/urllib configuration)
- Implement before the parse loop:
  ```python
  import socket
  socket.setdefaulttimeout(30)  # 30 second timeout
  ```
- Better approach: Use `requests` with explicit timeout, pass to feedparser:
  ```python
  import requests
  response = requests.get(url, timeout=30)
  d = feedparser.parse(response.content)
  ```

**3. Feed Validation**
- Add schema validation for feeds.json:
  ```python
  def validate_feeds_config(config):
      if not isinstance(config, dict):
          raise ValueError("feeds.json must be a dict")
      for category, data in config.items():
          if 'feeds' not in data or not isinstance(data['feeds'], dict):
              raise ValueError(f"Category {category} missing 'feeds' dict")
          # Validate URLs
          for source, url in data['feeds'].items():
              if not url.startswith(('http://', 'https://')):
                  raise ValueError(f"Invalid URL for {source}: {url}")
      return True
  ```
- Call after loading JSON, provide helpful error messages

**4. Configurable Timezone**
- Add to feeds.json global config section:
  ```json
  {
    "_config": {
      "timezone_offset_hours": 9
    },
    "category1": {...}
  }
  ```
- Modify config.py:
  ```python
  def get_timezone():
      with open(FEEDS_FILE_NAME, 'r') as fp:
          config = json.load(fp)
      offset = config.get('_config', {}).get('timezone_offset_hours', 0)
      return datetime.timezone(datetime.timedelta(hours=offset))
  
  TIMEZONE = get_timezone()
  ```

**5. Rate Limiting**
- Add delay between feed fetches:
  ```python
  import time
  FETCH_DELAY = 1  # seconds between requests
  
  for source, url in urls.items():
      # ... fetch and process ...
      time.sleep(FETCH_DELAY)
  ```
- Implement per-domain rate limiting:
  ```python
  from urllib.parse import urlparse
  from collections import defaultdict
  
  last_fetch = defaultdict(float)
  
  domain = urlparse(url).netloc
  elapsed = time.time() - last_fetch[domain]
  if elapsed < FETCH_DELAY:
      time.sleep(FETCH_DELAY - elapsed)
  last_fetch[domain] = time.time()
  ```

### High Priority - Detailed Solutions

**6. Silent Failures**
- Fix the exception handler:
  ```python
  except Exception as e:
      error_msg = f" - Failed: {str(e)}\n"
      sys.stderr.write(error_msg if log else "")
      sys.exit(1)  # Non-zero exit code
  ```
- Add error aggregation:
  ```python
  errors = []
  # In exception handler:
  errors.append(f"{source}: {str(e)}")
  # After loop:
  if errors and log:
      sys.stderr.write(f"\nErrors in {category}:\n" + "\n".join(errors))
  ```

**7. Stale Data Handling**
- Add cache expiration check:
  ```python
  def is_cache_stale(category, max_age_hours=24):
      cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
      if not os.path.exists(cache_file):
          return True
      
      with open(cache_file, 'r') as f:
          data = json.load(f)
      
      age_seconds = time.time() - data.get('created_at', 0)
      return age_seconds > (max_age_hours * 3600)
  ```
- Use to trigger automatic updates or show warning

**8. Duplicate Detection**
- Change ID generation to include source:
  ```python
  # Instead of: "id": ts
  unique_id = f"{source}:{ts}:{hash(feed.link) % 10000}"
  entries = {
      "id": unique_id,
      "timestamp": ts,
      # ...
  }
  ```
- Use dict with composite key to detect true duplicates

**9. Concurrent Fetching**
- Add parallel processing:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def fetch_single_feed(source, url, log):
      # Extract current loop body into function
      try:
          d = feedparser.parse(url)
          return source, d, None
      except Exception as e:
          return source, None, str(e)
  
  results = {}
  with ThreadPoolExecutor(max_workers=5) as executor:
      futures = {
          executor.submit(fetch_single_feed, src, url, log): src 
          for src, url in urls.items()
      }
      for future in as_completed(futures):
          source, data, error = future.result()
          if error is None:
              # process data
  ```

**10. User Feedback Interface**
- Create basic CLI viewer:
  ```python
  def list_feeds(category):
      cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
      with open(cache_file, 'r') as f:
          data = json.load(f)
      
      for i, entry in enumerate(data['entries'][:20], 1):
          print(f"{i}. [{entry['pubDate']}] {entry['title']}")
          print(f"   {entry['sourceName']} - {entry['url']}\n")
  ```
- Add argument parsing:
  ```python
  if __name__ == "__main__":
      import argparse
      parser = argparse.ArgumentParser()
      parser.add_argument('--update', help='Update feeds')
      parser.add_argument('--list', help='List feeds')
      parser.add_argument('--category', help='Target category')
      args = parser.parse_args()
      
      if args.list:
          list_feeds(args.category or 'default')
      elif args.update:
          do(args.category, log=True)
  ```

### Medium Priority - Detailed Solutions

**11. Feed Management**
- Add CRUD functions:
  ```python
  def add_feed(category, source_name, url):
      with open(FEEDS_FILE_NAME, 'r') as f:
          config = json.load(f)
      
      if category not in config:
          config[category] = {"feeds": {}, "show_author": False}
      
      config[category]["feeds"][source_name] = url
      
      with open(FEEDS_FILE_NAME, 'w') as f:
          json.dump(config, f, indent=4, ensure_ascii=False)
  
  def remove_feed(category, source_name):
      # Similar structure, del config[category]["feeds"][source_name]
  ```

**12. Content Extraction**
- Store summary/description:
  ```python
  entries = {
      # ... existing fields ...
      "summary": getattr(feed, 'summary', '')[:500],  # Limit length
      "content": getattr(feed, 'content', [{}])[0].get('value', '')[:1000],
  }
  ```

**13. Read/Unread Tracking**
- Add read_items.json:
  ```python
  def mark_as_read(entry_id):
      read_file = os.path.join(p["path_data"], "read_items.json")
      if os.path.exists(read_file):
          with open(read_file, 'r') as f:
              read_items = json.load(f)
      else:
          read_items = []
      
      if entry_id not in read_items:
          read_items.append(entry_id)
      
      with open(read_file, 'w') as f:
          json.dump(read_items, f)
  ```

**14-20. Lower Priority Items**
- These follow similar patterns: add new functions/modules, integrate with main flow
- OPML: Use `xml.etree.ElementTree` to parse/generate OPML format
- Scheduling: Use `schedule` library or cron integration
- Images: Add `requests` downloads, cache in `~/.rreader/cache/`
- Analytics: Extend JSON with fetch success/failure counts, last_updated timestamps
- Web interface: Consider Flask/FastAPI + simple HTML templates