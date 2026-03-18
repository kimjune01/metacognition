# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Configuration Management**: Loads RSS feed sources from a JSON configuration file, with automatic initialization from bundled defaults and merging of new categories into existing user configurations.

2. **RSS Parsing**: Fetches and parses RSS/Atom feeds using the `feedparser` library from multiple sources organized by category.

3. **Time Normalization**: Converts feed timestamps to a configured timezone (currently hardcoded to UTC+9/KST) and formats them for display (showing time only for today's items, date+time for older items).

4. **Data Persistence**: Saves parsed feed entries as JSON files (one per category) in the user's home directory (`~/.rreader/`).

5. **Deduplication**: Uses timestamps as unique IDs to prevent duplicate entries within a single fetch operation.

6. **Selective Processing**: Supports fetching either all categories or a single target category via the `target_category` parameter.

7. **Author Attribution**: Configurable per-category option to display feed author or source name.

8. **Progress Logging**: Optional console output to track feed fetching progress.

## Triage

### Critical Gaps (Must Fix)

1. **Silent Exception Handling**: The broad `except:` blocks swallow all errors, making debugging impossible and potentially hiding serious issues like network problems, malformed feeds, or filesystem errors.

2. **Duplicate ID Collisions**: Using Unix timestamp as the unique ID means multiple articles published in the same second will overwrite each other (only the last one survives).

3. **No Error Recovery**: A single failed feed causes `sys.exit(0)`, terminating the entire batch process and preventing other feeds from being fetched.

4. **Missing Data Validation**: No validation that required feed fields exist before accessing them, risking crashes on malformed feeds.

### High Priority Gaps (Should Fix)

5. **No Retry Logic**: Network failures or temporary outages cause immediate failure with no retry attempts.

6. **No Rate Limiting**: Rapid-fire requests to feed servers could result in being blocked or rate-limited.

7. **Missing Configuration Validation**: No checks that `feeds.json` is properly formatted or contains required fields.

8. **Hardcoded Timezone**: The timezone is hardcoded rather than configurable per user.

9. **No Concurrency**: Sequential feed fetching is slow; no parallelization for multiple feeds.

10. **No Feed Freshness Tracking**: The system refetches all items every time, with no mechanism to identify or filter new items.

### Medium Priority Gaps (Nice to Have)

11. **No Logging Framework**: Uses print statements and `sys.stdout.write()` instead of proper logging (levels, rotation, etc.).

12. **No User Feedback**: When not in log mode, the system provides no feedback about success/failure.

13. **No Metrics/Monitoring**: No tracking of fetch success rates, performance, or feed health.

14. **Limited CLI Interface**: No command-line arguments for common operations (specify category, verbose mode, force refresh, etc.).

15. **No Feed Metadata**: Doesn't capture useful feed-level information (description, image, last build date).

16. **No Content Sanitization**: Doesn't clean or validate HTML/text content that might contain malicious code.

## Plan

### 1. Fix Exception Handling
**Changes needed:**
- Replace all bare `except:` with specific exception types:
  - `except (urllib.error.URLError, http.client.HTTPException)` for network errors
  - `except feedparser.FeedParserError` for parsing errors
  - `except (KeyError, AttributeError)` for missing fields
- Add logging of exception details using `logging.exception()`
- Continue processing remaining feeds instead of exiting
- Return status dictionary indicating success/failure per feed

```python
import logging
from urllib.error import URLError

logger = logging.getLogger(__name__)

try:
    d = feedparser.parse(url)
except (URLError, Exception) as e:
    logger.error(f"Failed to fetch {url}: {e}")
    continue  # Skip to next feed instead of exiting
```

### 2. Fix Duplicate ID System
**Changes needed:**
- Change ID strategy to combine timestamp with URL hash or incremental counter:
  ```python
  import hashlib
  
  unique_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
  ```
- Or use the feed's native GUID if available:
  ```python
  feed_id = getattr(feed, 'id', None) or f"{ts}_{feed.link}"
  ```

### 3. Implement Graceful Error Recovery
**Changes needed:**
- Remove `sys.exit()` calls from error handling
- Accumulate errors in a list and continue processing
- Return summary of successes and failures:
  ```python
  results = {"successful": [], "failed": []}
  for source, url in urls.items():
      try:
          # ... process feed
          results["successful"].append(source)
      except Exception as e:
          results["failed"].append({"source": source, "error": str(e)})
  return results
  ```

### 4. Add Data Validation
**Changes needed:**
- Validate required fields before use:
  ```python
  if not hasattr(feed, 'link') or not hasattr(feed, 'title'):
      logger.warning(f"Skipping malformed entry from {source}")
      continue
  ```
- Validate `feeds.json` structure on load using JSON schema or manual checks:
  ```python
  def validate_feeds_config(config):
      if not isinstance(config, dict):
          raise ValueError("Feeds config must be a dictionary")
      for cat, data in config.items():
          if "feeds" not in data or not isinstance(data["feeds"], dict):
              raise ValueError(f"Category {cat} missing 'feeds' dict")
  ```

### 5. Add Retry Logic
**Changes needed:**
- Wrap feed fetching in retry decorator or manual loop:
  ```python
  import time
  
  MAX_RETRIES = 3
  RETRY_DELAY = 2  # seconds
  
  for attempt in range(MAX_RETRIES):
      try:
          d = feedparser.parse(url)
          break
      except Exception as e:
          if attempt == MAX_RETRIES - 1:
              raise
          time.sleep(RETRY_DELAY * (attempt + 1))
  ```

### 6. Add Rate Limiting
**Changes needed:**
- Insert delays between requests:
  ```python
  import time
  
  RATE_LIMIT_DELAY = 0.5  # seconds between requests
  
  for source, url in urls.items():
      # ... fetch feed
      time.sleep(RATE_LIMIT_DELAY)
  ```
- Or use a proper rate limiter library like `ratelimit` or `pyrate-limiter`

### 7. Validate Configuration Files
**Changes needed:**
- Add validation function called after loading JSON:
  ```python
  def validate_config(config):
      required_keys = ["feeds"]
      for category, data in config.items():
          for key in required_keys:
              if key not in data:
                  raise ValueError(f"Missing '{key}' in category '{category}'")
          if not isinstance(data["feeds"], dict):
              raise ValueError(f"'feeds' must be dict in '{category}'")
  
  RSS = json.load(fp)
  validate_config(RSS)
  ```

### 8. Make Timezone Configurable
**Changes needed:**
- Move timezone to `feeds.json` or separate config file:
  ```json
  {
    "settings": {
      "timezone_offset_hours": 9
    },
    "categories": { ... }
  }
  ```
- Or add to user config with default fallback:
  ```python
  tz_hours = RSS.get("settings", {}).get("timezone_offset_hours", 0)
  TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_hours))
  ```

### 9. Add Concurrent Fetching
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetching:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def fetch_single_feed(source, url):
      # ... existing fetch logic
      return source, entries
  
  with ThreadPoolExecutor(max_workers=5) as executor:
      futures = {executor.submit(fetch_single_feed, src, url): src 
                 for src, url in urls.items()}
      for future in as_completed(futures):
          source, entries = future.result()
          rslt.update(entries)
  ```

### 10. Track Feed Freshness
**Changes needed:**
- Store last-fetch timestamp per category
- Add `is_new` flag to entries by comparing against previous fetch
- Store seen entry IDs in separate file:
  ```python
  seen_file = os.path.join(p["path_data"], f"seen_{category}.json")
  if os.path.exists(seen_file):
      with open(seen_file) as f:
          seen_ids = set(json.load(f))
  else:
      seen_ids = set()
  
  # Mark new entries
  for entry in entries:
      entry["is_new"] = entry["id"] not in seen_ids
  ```

### 11. Implement Proper Logging
**Changes needed:**
- Replace print statements with logging module:
  ```python
  import logging
  
  logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
      handlers=[
          logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
          logging.StreamHandler()
      ]
  )
  logger = logging.getLogger(__name__)
  
  # Replace sys.stdout.write(f"- {url}") with:
  logger.info(f"Fetching feed: {url}")
  ```

### 12. Add CLI Argument Parsing
**Changes needed:**
- Use `argparse` for proper CLI interface:
  ```python
  import argparse
  
  if __name__ == "__main__":
      parser = argparse.ArgumentParser(description="RSS Feed Aggregator")
      parser.add_argument("-c", "--category", help="Specific category to fetch")
      parser.add_argument("-v", "--verbose", action="store_true", 
                         help="Enable verbose logging")
      parser.add_argument("--force", action="store_true",
                         help="Force refresh all feeds")
      args = parser.parse_args()
      
      do(target_category=args.category, log=args.verbose)
  ```