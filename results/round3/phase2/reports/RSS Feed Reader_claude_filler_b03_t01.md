# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed reader with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from configured URLs
2. **Multi-source Aggregation**: Processes multiple feeds per category, combining entries from different sources
3. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries in the output
4. **Time Normalization**: Converts feed timestamps to a configured timezone (KST/UTC+9) with intelligent formatting (shows time only for today's entries, includes date for older ones)
5. **JSON Output**: Writes parsed feeds to category-specific JSON files (`rss_{category}.json`) with metadata
6. **Configuration Management**: 
   - Stores feed URLs in a `feeds.json` configuration file
   - Auto-creates user config from bundled defaults
   - Merges new categories from bundled config into existing user config
7. **Author Attribution**: Supports optional per-category author display via `show_author` flag
8. **Chronological Sorting**: Orders entries by timestamp (newest first)
9. **Directory Initialization**: Auto-creates data directory at `~/.rreader/`
10. **Selective Processing**: Can target a single category or process all categories

## Triage

### Critical Gaps

1. **Error Handling**: Catastrophic failure modes with no recovery
   - Feed parsing failures call `sys.exit()`, terminating the entire process
   - Network timeouts will hang indefinitely (no timeout configured)
   - Malformed JSON in config files will crash with unhelpful errors

2. **Data Integrity**: No validation or sanitization
   - Missing title/URL fields will cause KeyError exceptions
   - Malformed timestamps crash instead of being skipped gracefully
   - No validation that required fields exist in config

3. **ID Collision**: Timestamp-based IDs are not unique
   - Multiple articles published in the same second will overwrite each other
   - Only the last article at each timestamp survives

### Important Gaps

4. **Logging**: The `log` parameter only controls stdout, not real logging
   - No persistent logs for debugging feed failures
   - No error details captured (which feed failed, what the error was)
   - Silent failures when `log=False`

5. **Performance**: Sequential processing is slow for many feeds
   - No concurrent fetching (each feed blocks the next)
   - No caching (refetches everything every time)
   - No rate limiting (could get blocked by servers)

6. **Stale Data**: Old entries accumulate forever
   - No pruning of old entries
   - JSON files grow unbounded
   - No configurable retention policy

7. **Configuration**: Limited flexibility
   - Timezone is hardcoded in config.py
   - No per-feed configuration (timeouts, headers, etc.)
   - No way to disable individual feeds without editing JSON

### Nice-to-Have Gaps

8. **Monitoring**: No visibility into system health
   - No metrics (fetch success rate, response times)
   - No alerting when feeds fail repeatedly
   - No dashboard or status endpoint

9. **Testing**: No test coverage visible in this code

10. **Documentation**: Missing docstrings and usage examples

## Plan

### 1. Error Handling

**Changes needed:**

- Replace `sys.exit()` with exception catching and logging:
  ```python
  except Exception as e:
      logging.error(f"Failed to parse {url}: {e}")
      continue  # Skip this feed, process others
  ```

- Add timeout to feedparser:
  ```python
  d = feedparser.parse(url, timeout=30)
  ```

- Wrap config file reads in try/except with helpful error messages:
  ```python
  try:
      with open(FEEDS_FILE_NAME, "r") as fp:
          RSS = json.load(fp)
  except json.JSONDecodeError as e:
      sys.stderr.write(f"Invalid JSON in {FEEDS_FILE_NAME}: {e}\n")
      sys.exit(1)
  except FileNotFoundError:
      # Handle missing file case
  ```

### 2. Data Integrity

**Changes needed:**

- Add defensive field access with defaults:
  ```python
  entries = {
      "id": ts,
      "sourceName": author,
      "pubDate": pubDate,
      "timestamp": ts,
      "url": getattr(feed, 'link', ''),
      "title": getattr(feed, 'title', 'Untitled'),
  }
  
  # Skip entries missing critical fields
  if not entries["url"] or not entries["title"]:
      continue
  ```

- Add config validation function:
  ```python
  def validate_config(config):
      for category, data in config.items():
          if "feeds" not in data or not isinstance(data["feeds"], dict):
              raise ValueError(f"Category {category} missing 'feeds' dict")
      return config
  ```

### 3. ID Collision

**Changes needed:**

- Change ID generation to include URL hash:
  ```python
  import hashlib
  
  id_components = f"{ts}_{feed.link}"
  unique_id = hashlib.md5(id_components.encode()).hexdigest()
  
  entries = {
      "id": unique_id,
      # ... rest of fields
  }
  ```

- Or use incrementing counter within each timestamp:
  ```python
  # Change rslt from dict to list, append all entries
  rslt = []
  for feed in d.entries:
      # ... build entries ...
      rslt.append(entries)
  
  # Sort after collecting all
  rslt.sort(key=lambda x: x["timestamp"], reverse=True)
  ```

### 4. Logging

**Changes needed:**

- Replace print statements with proper logging:
  ```python
  import logging
  
  logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s - %(levelname)s - %(message)s',
      handlers=[
          logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
          logging.StreamHandler()
      ]
  )
  
  logger = logging.getLogger(__name__)
  ```

- Log all significant events:
  ```python
  logger.info(f"Fetching {url}")
  logger.error(f"Failed to parse {url}: {e}")
  logger.info(f"Processed {len(rslt)} entries for {category}")
  ```

### 5. Performance

**Changes needed:**

- Add concurrent fetching using ThreadPoolExecutor:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def fetch_single_feed(source, url):
      try:
          d = feedparser.parse(url, timeout=30)
          return source, d, None
      except Exception as e:
          return source, None, e
  
  with ThreadPoolExecutor(max_workers=10) as executor:
      futures = {executor.submit(fetch_single_feed, src, url): (src, url) 
                 for src, url in urls.items()}
      
      for future in as_completed(futures):
          source, parsed, error = future.result()
          if error:
              logger.error(f"Failed {source}: {error}")
              continue
          # Process parsed feed...
  ```

- Add response caching with ETags/Last-Modified headers:
  ```python
  # Store ETags in cache file
  # Pass to feedparser: d = feedparser.parse(url, etag=cached_etag)
  # Check d.status and skip if 304 (Not Modified)
  ```

### 6. Stale Data

**Changes needed:**

- Add pruning function to remove old entries:
  ```python
  def prune_old_entries(entries, max_age_days=30):
      cutoff = int(time.time()) - (max_age_days * 86400)
      return [e for e in entries if e["timestamp"] > cutoff]
  
  # Call before writing:
  rslt["entries"] = prune_old_entries(rslt["entries"])
  ```

- Add configuration option:
  ```json
  {
      "category_name": {
          "feeds": {...},
          "max_age_days": 30
      }
  }
  ```

### 7. Configuration

**Changes needed:**

- Move timezone to feeds.json:
  ```json
  {
      "_settings": {
          "timezone_offset_hours": 9
      },
      "category_name": {...}
  }
  ```

- Add per-feed options:
  ```json
  {
      "category": {
          "feeds": {
              "Source Name": {
                  "url": "https://...",
                  "enabled": true,
                  "timeout": 30
              }
          }
      }
  }
  ```

- Update parsing logic to handle both string URLs and dict configs with backward compatibility

### 8. Monitoring

**Changes needed:**

- Track metrics during execution:
  ```python
  metrics = {
      "total_feeds": 0,
      "successful": 0,
      "failed": 0,
      "total_entries": 0,
      "duration_seconds": 0
  }
  ```

- Write metrics to JSON file:
  ```python
  metrics_file = os.path.join(p["path_data"], "metrics.json")
  with open(metrics_file, "w") as f:
      json.dump(metrics, f)
  ```

- Add simple health check function:
  ```python
  def health_check():
      """Returns dict with status of last run"""
      # Read metrics.json, check timestamps, return status
  ```

### 9. Testing

**Changes needed:**

- Create `tests/` directory with:
  - `test_parsing.py`: Test feed parsing with mock responses
  - `test_config.py`: Test config loading/validation
  - `test_deduplication.py`: Test ID generation
  - `test_time.py`: Test timezone conversion

- Use `pytest` with fixtures:
  ```python
  @pytest.fixture
  def mock_feed():
      return feedparser.parse("test_feed.xml")
  
  def test_entry_extraction(mock_feed):
      # Test entry processing logic
  ```

### 10. Documentation

**Changes needed:**

- Add module docstring:
  ```python
  """
  RSS Feed Reader
  
  Fetches and aggregates RSS/Atom feeds into category-specific JSON files.
  
  Configuration:
      Feeds are configured in ~/.rreader/feeds.json
      
  Usage:
      import rreader
      rreader.do()  # Process all categories
      rreader.do("news")  # Process single category
  """
  ```

- Add docstrings to functions:
  ```python
  def get_feed_from_rss(category, urls, show_author=False, log=False):
      """
      Fetch and parse RSS feeds for a category.
      
      Args:
          category: Category name (used for output filename)
          urls: Dict mapping source names to feed URLs
          show_author: If True, use feed author; else use source name
          log: If True, print progress to stdout
          
      Returns:
          Dict with 'entries' list and 'created_at' timestamp
      """
  ```

- Create README.md with setup instructions, configuration examples, and API documentation