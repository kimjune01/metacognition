# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, processing each category's feeds separately.

3. **Feed Normalization**: Extracts and standardizes feed entries with:
   - Timestamp (Unix format)
   - Source name/author
   - Publication date (formatted as "HH:MM" for today, "MMM DD, HH:MM" otherwise)
   - URL and title

4. **Timezone Handling**: Converts UTC timestamps to a configured timezone (currently KST/UTC+9).

5. **Data Persistence**: 
   - Saves parsed feeds as JSON files (`rss_{category}.json`)
   - Maintains a feeds configuration file (`feeds.json`)
   - Creates necessary directories automatically

6. **Configuration Management**:
   - Ships with bundled default feeds
   - Merges new categories from bundled config into user config
   - Preserves user customizations

7. **Deduplication**: Uses timestamp as unique ID to prevent duplicate entries within a category.

8. **Optional Logging**: Provides feedback during feed fetching when enabled.

9. **Flexible Author Display**: Supports per-category configuration for showing feed source name vs. actual author.

## Triage

### Critical Gaps

1. **Error Handling** - The system will crash or silently fail on network issues, malformed feeds, or file system problems. Production systems need graceful degradation.

2. **Stale Data Management** - No mechanism to remove old entries or manage cache size. Feed files will grow indefinitely.

3. **Rate Limiting/Throttling** - Fetches all feeds simultaneously without delays, risking IP bans or server overload.

### High Priority Gaps

4. **Retry Logic** - Network failures cause immediate failure with no retry mechanism.

5. **Feed Validation** - No validation of feed URLs or structure in the configuration file.

6. **Concurrency** - Sequential processing makes the system slow when handling many feeds.

7. **Monitoring/Alerting** - No way to know if feeds are failing consistently or producing no content.

### Medium Priority Gaps

8. **Configuration Validation** - Missing schema validation for `feeds.json` structure.

9. **Duplicate Detection Weakness** - Using only timestamp as ID will fail if two articles publish at the same second.

10. **Testing Infrastructure** - No unit tests, integration tests, or mocks for feedparser.

### Low Priority Gaps

11. **Documentation** - No docstrings, API documentation, or usage examples beyond the text description.

12. **Logging Framework** - Uses print statements instead of proper logging (levels, rotation, structured logs).

13. **Performance Metrics** - No tracking of fetch times, success rates, or feed health.

## Plan

### 1. Error Handling (Critical)

**Changes needed:**
- Wrap `feedparser.parse()` in try-except to catch `URLError`, `HTTPError`, and generic exceptions
- Wrap file operations in try-except blocks with specific exception handling
- Replace `sys.exit()` with proper error returns and logging
- Add a `success_count` and `failure_count` to the return value
- Store error messages in the output JSON with a structure like:
  ```python
  {
    "entries": [...],
    "created_at": timestamp,
    "errors": [{"source": "source_name", "error": "error_message", "timestamp": ts}]
  }
  ```

**Example implementation:**
```python
try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser's error flag
        raise Exception(f"Feed parse error: {d.bozo_exception}")
except Exception as e:
    errors.append({"source": source, "error": str(e), "timestamp": int(time.time())})
    if log:
        sys.stdout.write(f" - Failed: {e}\n")
    continue  # Don't crash, continue to next feed
```

### 2. Stale Data Management (Critical)

**Changes needed:**
- Add a `max_age_days` parameter to configuration (default: 30)
- Filter entries by timestamp before writing to JSON:
  ```python
  cutoff_ts = int(time.time()) - (max_age_days * 86400)
  rslt = [val for key, val in sorted(rslt.items(), reverse=True) if val['timestamp'] > cutoff_ts]
  ```
- Add a `max_entries_per_category` configuration option (default: 500)
- Slice results: `rslt = rslt[:max_entries_per_category]`

### 3. Rate Limiting/Throttling (Critical)

**Changes needed:**
- Add `time.sleep()` between feed fetches:
  ```python
  import time
  FETCH_DELAY_SECONDS = 1.0  # Add to config.py
  
  for source, url in urls.items():
      time.sleep(FETCH_DELAY_SECONDS)
      # ... fetch logic
  ```
- Add per-domain rate limiting using a dictionary tracking last access time
- Consider adding exponential backoff for failed requests

### 4. Retry Logic (High Priority)

**Changes needed:**
- Create a retry decorator or wrapper function:
  ```python
  def fetch_with_retry(url, max_retries=3, backoff_factor=2):
      for attempt in range(max_retries):
          try:
              return feedparser.parse(url)
          except Exception as e:
              if attempt == max_retries - 1:
                  raise
              wait_time = backoff_factor ** attempt
              time.sleep(wait_time)
  ```
- Add `max_retries` and `retry_backoff` to config
- Log each retry attempt

### 5. Feed Validation (High Priority)

**Changes needed:**
- Add URL validation when loading `feeds.json`:
  ```python
  from urllib.parse import urlparse
  
  def is_valid_url(url):
      try:
          result = urlparse(url)
          return all([result.scheme in ('http', 'https'), result.netloc])
      except:
          return False
  ```
- Check feed structure and warn on invalid entries
- Add HTTP HEAD request check during feed addition to verify URL is accessible

### 6. Concurrency (High Priority)

**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor`:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def fetch_single_feed(source, url):
      # Extract single feed logic
      pass
  
  with ThreadPoolExecutor(max_workers=5) as executor:
      future_to_source = {executor.submit(fetch_single_feed, src, url): src 
                          for src, url in urls.items()}
      for future in as_completed(future_to_source):
          # Collect results
  ```
- Add `max_concurrent_fetches` to config (default: 5)
- Maintain rate limiting per thread

### 7. Monitoring/Alerting (High Priority)

**Changes needed:**
- Create a `feed_health.json` file tracking:
  ```python
  {
    "category_name": {
      "source_name": {
        "last_success": timestamp,
        "last_failure": timestamp,
        "consecutive_failures": count,
        "total_entries_last_fetch": count
      }
    }
  }
  ```
- Update after each fetch attempt
- Add function to generate health report identifying feeds with >5 consecutive failures

### 8. Configuration Validation (Medium Priority)

**Changes needed:**
- Add JSON schema validation using `jsonschema` library:
  ```python
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
  ```
- Validate on load and provide helpful error messages

### 9. Duplicate Detection Improvement (Medium Priority)

**Changes needed:**
- Change ID generation to include URL hash:
  ```python
  import hashlib
  
  entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
  ```
- Or use feed GUID if available: `getattr(feed, 'id', None)`

### 10. Testing Infrastructure (Medium Priority)

**Changes needed:**
- Create `tests/` directory with:
  - `test_feed_parsing.py` - Unit tests with mocked feedparser responses
  - `test_date_formatting.py` - Timezone and date formatting tests
  - `test_config_management.py` - Config loading and merging tests
- Add `pytest` and `pytest-mock` to requirements
- Create fixture RSS feed samples in `tests/fixtures/`

### 11. Documentation (Low Priority)

**Changes needed:**
- Add module-level docstring explaining the system
- Add docstrings to all functions following Google or NumPy style
- Create `README.md` with usage examples, configuration format, and troubleshooting
- Add inline comments for complex logic (timezone conversion, deduplication)

### 12. Logging Framework (Low Priority)

**Changes needed:**
- Replace print statements with Python `logging` module:
  ```python
  import logging
  
  logger = logging.getLogger(__name__)
  
  # In config.py
  LOG_LEVEL = logging.INFO
  LOG_FILE = os.path.join(p["path_data"], "rreader.log")
  
  logging.basicConfig(
      level=LOG_LEVEL,
      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
      handlers=[
          logging.FileHandler(LOG_FILE),
          logging.StreamHandler()
      ]
  )
  ```
- Use appropriate log levels (DEBUG, INFO, WARNING, ERROR)

### 13. Performance Metrics (Low Priority)

**Changes needed:**
- Track and store metrics:
  ```python
  metrics = {
      "fetch_start": time.time(),
      "feeds_attempted": 0,
      "feeds_successful": 0,
      "entries_collected": 0,
      "fetch_duration": 0
  }
  ```
- Write metrics to separate `metrics_{category}.json` file
- Add optional function to display summary statistics