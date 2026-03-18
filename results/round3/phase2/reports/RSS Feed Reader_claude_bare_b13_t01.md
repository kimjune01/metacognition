# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-source Aggregation**: Processes multiple feed URLs organized by categories from a JSON configuration file
3. **Time Handling**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9) and formats them for display
4. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
5. **Data Persistence**: Saves parsed feeds as JSON files (one per category) in `~/.rreader/`
6. **Configuration Management**: 
   - Copies bundled `feeds.json` if user doesn't have one
   - Merges new categories from bundled config into existing user config
7. **Selective Processing**: Can process either all categories or a single target category
8. **Date-aware Formatting**: Shows time-only for today's entries, full date for older entries
9. **Author Handling**: Optional per-category display of author names vs source names

## Triage

### Critical Gaps
1. **Error Handling**: Bare `except` clauses that silently fail or exit with minimal information
2. **Feed Validation**: No verification that parsed feeds contain valid/expected data structure
3. **Network Resilience**: No timeout, retry logic, or connection error handling

### High Priority
4. **Logging Infrastructure**: Inconsistent logging (parameter exists but only used for stdout)
5. **Configuration Validation**: No schema validation for `feeds.json` structure
6. **Data Staleness**: No mechanism to handle or flag outdated cached data
7. **Concurrency**: Sequential feed fetching could be slow with many sources

### Medium Priority
8. **ID Collision Risk**: Using timestamp as ID could cause collisions for feeds published simultaneously
9. **Memory Efficiency**: Loads all entries into memory before sorting; could be problematic with large feeds
10. **URL Validation**: No checking if feed URLs are well-formed before fetching
11. **Disk Space Management**: No cleanup of old JSON files or size limits

### Low Priority
12. **Testing Infrastructure**: No unit tests, integration tests, or mock data
13. **Documentation**: Missing docstrings and inline comments
14. **CLI Interface**: No argument parsing for command-line usage
15. **Progress Indication**: Minimal user feedback during long operations

## Plan

### 1. Error Handling (Critical)
**Changes needed:**
- Replace `except:` on line 34-35 with specific exception types:
  ```python
  except (URLError, HTTPError, socket.timeout) as e:
      if log:
          sys.stderr.write(f" - Failed: {str(e)}\n")
      continue  # Don't exit, skip this feed
  ```
- Replace generic `except:` on line 41 with:
  ```python
  except (AttributeError, ValueError, KeyError) as e:
      if log:
          sys.stderr.write(f"Warning: Skipping malformed entry: {str(e)}\n")
      continue
  ```
- Add try-except around file operations (lines 61-64, 74-76) with `IOError, PermissionError`

### 2. Feed Validation (Critical)
**Changes needed:**
- Add validation function after line 36:
  ```python
  def validate_feed(feed_data):
      required_fields = ['link', 'title']
      return all(hasattr(feed_data, field) and getattr(feed_data, field) for field in required_fields)
  ```
- Insert validation check at line 42:
  ```python
  if not validate_feed(feed):
      continue
  ```

### 3. Network Resilience (Critical)
**Changes needed:**
- Add timeout to feedparser call at line 30:
  ```python
  d = feedparser.parse(url, timeout=10)
  ```
- Implement retry logic wrapper:
  ```python
  def fetch_with_retry(url, max_attempts=3, backoff=2):
      for attempt in range(max_attempts):
          try:
              return feedparser.parse(url, timeout=10)
          except Exception as e:
              if attempt == max_attempts - 1:
                  raise
              time.sleep(backoff ** attempt)
  ```

### 4. Logging Infrastructure (High Priority)
**Changes needed:**
- Add proper logging setup at module level:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- Replace all `sys.stdout.write` and create log configuration:
  ```python
  def setup_logging(verbose=False):
      level = logging.DEBUG if verbose else logging.INFO
      logging.basicConfig(
          format='%(asctime)s - %(levelname)s - %(message)s',
          level=level,
          handlers=[
              logging.FileHandler(os.path.join(p['path_data'], 'rreader.log')),
              logging.StreamHandler()
          ]
      )
  ```

### 5. Configuration Validation (High Priority)
**Changes needed:**
- Add schema validation after loading feeds.json (line 85):
  ```python
  def validate_config(config):
      if not isinstance(config, dict):
          raise ValueError("Config must be a dictionary")
      for category, data in config.items():
          if 'feeds' not in data or not isinstance(data['feeds'], dict):
              raise ValueError(f"Category '{category}' missing 'feeds' dict")
      return True
  
  RSS = json.load(fp)
  validate_config(RSS)
  ```

### 6. Data Staleness Handling (High Priority)
**Changes needed:**
- Add check when loading cached data:
  ```python
  def is_cache_fresh(filepath, max_age_seconds=3600):
      if not os.path.exists(filepath):
          return False
      age = time.time() - os.path.getmtime(filepath)
      return age < max_age_seconds
  ```
- Add cache expiry metadata in saved JSON:
  ```python
  rslt = {
      "entries": rslt,
      "created_at": int(time.time()),
      "expires_at": int(time.time()) + 3600
  }
  ```

### 7. Concurrency (High Priority)
**Changes needed:**
- Import concurrent.futures at top
- Refactor feed fetching at line 88-92:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def fetch_single_category(category, config):
      return category, get_feed_from_rss(
          category, config["feeds"], 
          show_author=config.get("show_author", False), 
          log=log
      )
  
  with ThreadPoolExecutor(max_workers=5) as executor:
      futures = {executor.submit(fetch_single_category, cat, cfg): cat 
                 for cat, cfg in RSS.items()}
      for future in as_completed(futures):
          category, result = future.result()
  ```

### 8. ID Collision Risk (Medium Priority)
**Changes needed:**
- Replace timestamp-only ID at line 56 with composite key:
  ```python
  import hashlib
  
  url_hash = hashlib.md5(feed.link.encode()).hexdigest()[:8]
  entry_id = f"{ts}_{url_hash}"
  ```

### 9. Memory Efficiency (Medium Priority)
**Changes needed:**
- Use generator for large feed processing:
  ```python
  def generate_entries(feeds):
      for feed in feeds:
          # ... validation and processing ...
          yield entry
  
  entries_list = sorted(generate_entries(d.entries), 
                       key=lambda x: x['timestamp'], 
                       reverse=True)
  ```

### 10. URL Validation (Medium Priority)
**Changes needed:**
- Add validation before fetching at line 26:
  ```python
  from urllib.parse import urlparse
  
  def is_valid_url(url):
      try:
          result = urlparse(url)
          return all([result.scheme in ['http', 'https'], result.netloc])
      except:
          return False
  
  if not is_valid_url(url):
      logger.warning(f"Invalid URL skipped: {url}")
      continue
  ```