# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-Category Support**: Organizes feeds into categories, each containing multiple source URLs
3. **Configuration Management**: 
   - Maintains user feeds in `~/.rreader/feeds.json`
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration
4. **Data Persistence**: Saves parsed feed entries as JSON files (`rss_{category}.json`) in the data directory
5. **Time Handling**: 
   - Converts published/updated timestamps to local timezone (KST/UTC+9)
   - Formats display dates as "HH:MM" for today, "MMM DD, HH:MM" for older entries
6. **Deduplication**: Uses timestamp as ID to prevent duplicate entries (same-second collisions will overwrite)
7. **Selective Updates**: Can update a single category or all categories
8. **Optional Logging**: Progress output for feed fetching when enabled
9. **Author Display**: Configurable per-category author/source name display

## Triage

### Critical Gaps
1. **Error Handling** - Bare `except` clauses swallow all errors; feed parsing failures call `sys.exit()` which terminates the entire process
2. **Feed Configuration Template** - No `feeds.json` template provided; system will fail if bundled file is missing
3. **Collision Handling** - Multiple entries with same timestamp (second precision) will overwrite each other

### Important Gaps
4. **Validation** - No validation of feed URLs, JSON structure, or category names
5. **Logging Infrastructure** - Only basic stdout logging; no proper logging framework, levels, or file output
6. **Rate Limiting** - No delays between feed requests; risks being blocked by servers
7. **Timeout Handling** - Feed requests have no timeout; can hang indefinitely
8. **Stale Data Detection** - No way to identify or handle outdated feeds

### Nice-to-Have Gaps
9. **Progress Indicators** - No indication of overall progress when processing multiple categories
10. **Configuration Validation** - Doesn't verify timezone or path settings
11. **Performance** - Sequential processing; no parallelization for multiple feeds
12. **Content Sanitization** - No HTML stripping or content cleaning from feed entries
13. **Update Metadata** - Doesn't track last successful update time per feed source

## Plan

### 1. Error Handling
**Changes needed:**
- Replace `except:` on line 23 with specific exception handling:
  ```python
  except (feedparser.FeedParserError, URLError, HTTPError, Timeout) as e:
      if log:
          sys.stderr.write(f" - Failed: {str(e)}\n")
      continue  # Skip this feed, don't exit
  ```
- Replace `except:` on line 39 with:
  ```python
  except (AttributeError, ValueError, TypeError) as e:
      if log:
          sys.stderr.write(f"  Warning: Skipping malformed entry: {str(e)}\n")
      continue
  ```
- Add try-except around file operations with specific `IOError`, `JSONDecodeError` handling
- Remove `sys.exit()` call on line 28; let the function continue with remaining feeds

### 2. Feed Configuration Template
**Changes needed:**
- Create `feeds.json` in the package directory with example structure:
  ```json
  {
      "tech": {
          "feeds": {
              "Hacker News": "https://news.ycombinator.com/rss",
              "TechCrunch": "https://techcrunch.com/feed/"
          },
          "show_author": false
      }
  }
  ```
- Add validation after line 67 to check if `bundled_feeds_file` exists:
  ```python
  if not os.path.isfile(bundled_feeds_file):
      raise FileNotFoundError(f"Bundled feeds.json not found at {bundled_feeds_file}")
  ```

### 3. Collision Handling
**Changes needed:**
- Change ID generation from timestamp-only to include source (line 57-58):
  ```python
  entry_id = f"{ts}_{hash(source + feed.link) % 10000}"
  ```
- Or use a counter for same-timestamp entries:
  ```python
  entry_id = ts
  counter = 0
  while f"{entry_id}_{counter}" in rslt:
      counter += 1
  entry_id = f"{entry_id}_{counter}"
  ```

### 4. Validation
**Changes needed:**
- Add schema validation after loading RSS config (line 80):
  ```python
  def validate_feeds_config(config):
      if not isinstance(config, dict):
          raise ValueError("feeds.json must be a dictionary")
      for category, data in config.items():
          if "feeds" not in data or not isinstance(data["feeds"], dict):
              raise ValueError(f"Category '{category}' missing 'feeds' dict")
          for name, url in data["feeds"].items():
              if not url.startswith(("http://", "https://")):
                  raise ValueError(f"Invalid URL for {name}: {url}")
  validate_feeds_config(RSS)
  ```

### 5. Logging Infrastructure
**Changes needed:**
- Add at top of file:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- Replace `sys.stdout.write` calls with `logger.info()`
- Replace `sys.stderr.write` calls with `logger.error()` or `logger.warning()`
- Add logging configuration in `do()`:
  ```python
  if log:
      logging.basicConfig(level=logging.INFO, 
                         format='%(asctime)s - %(levelname)s - %(message)s')
  ```

### 6. Rate Limiting
**Changes needed:**
- Add delay between feed requests (after line 30):
  ```python
  time.sleep(0.5)  # 500ms delay between requests
  ```
- Make delay configurable via config.py:
  ```python
  FEED_REQUEST_DELAY = 0.5  # seconds
  ```

### 7. Timeout Handling
**Changes needed:**
- Configure feedparser timeout (line 24):
  ```python
  import socket
  socket.setdefaulttimeout(30)  # 30 second timeout
  # Or pass to feedparser if supported in version
  d = feedparser.parse(url, timeout=30)
  ```

### 8. Stale Data Detection
**Changes needed:**
- Add age check after parsing (around line 30):
  ```python
  feed_age = time.time() - d.get('updated_parsed', time.gmtime())
  if feed_age > 86400 * 7:  # 7 days
      logger.warning(f"Feed {source} appears stale (last update: {feed_age/86400:.1f} days ago)")
  ```

### 9. Progress Indicators
**Changes needed:**
- Add progress counter in main loop (line 89):
  ```python
  total = len(RSS)
  for idx, (category, d) in enumerate(RSS.items(), 1):
      if log:
          print(f"[{idx}/{total}] Processing category: {category}")
  ```

### 10. Configuration Validation
**Changes needed:**
- Add validation in config.py:
  ```python
  if not isinstance(TIMEZONE, datetime.timezone):
      raise ValueError("TIMEZONE must be a datetime.timezone object")
  ```
- Validate paths in common.py after mkdir operations

### 11. Performance
**Changes needed:**
- Add concurrent processing option:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def do(target_category=None, log=False, max_workers=4):
      # ... existing code ...
      with ThreadPoolExecutor(max_workers=max_workers) as executor:
          futures = {executor.submit(get_feed_from_rss, cat, d["feeds"], 
                    d.get("show_author", False), log): cat 
                    for cat, d in RSS.items()}
          for future in as_completed(futures):
              category = futures[future]
              try:
                  future.result()
              except Exception as e:
                  logger.error(f"Failed to process {category}: {e}")
  ```

### 12. Content Sanitization
**Changes needed:**
- Add HTML cleaning function:
  ```python
  from html import unescape
  import re
  
  def sanitize_text(text):
      text = unescape(text)
      text = re.sub(r'<[^>]+>', '', text)  # Strip HTML tags
      return text.strip()
  ```
- Apply to title and author (line 64):
  ```python
  "title": sanitize_text(feed.title),
  ```

### 13. Update Metadata
**Changes needed:**
- Track per-source metadata in the output JSON (line 63):
  ```python
  rslt = {
      "entries": rslt_entries,
      "created_at": int(time.time()),
      "sources": {
          source: {
              "last_update": int(time.time()),
              "entry_count": len([e for e in rslt_entries if e["sourceName"] == source]),
              "status": "success"
          } for source in urls.keys()
      }
  }
  ```