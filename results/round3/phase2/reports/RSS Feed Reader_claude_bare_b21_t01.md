# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, each containing multiple RSS sources.

3. **Feed Configuration Management**: 
   - Maintains a `feeds.json` configuration file in `~/.rreader/`
   - Copies bundled default feeds on first run
   - Merges new categories from bundled config into user config on updates

4. **Data Normalization**: Extracts and standardizes feed entries with:
   - Unique ID (timestamp-based)
   - Source name/author
   - Publication date (formatted as "HH:MM" for today, "Mon DD, HH:MM" otherwise)
   - Unix timestamp
   - URL and title

5. **Timezone Handling**: Converts UTC timestamps to configured timezone (KST/UTC+9).

6. **Deduplication**: Uses timestamp as ID to prevent duplicate entries from the same source.

7. **Sorting**: Orders entries by timestamp (newest first).

8. **Persistent Storage**: Saves parsed feeds as JSON files (`rss_{category}.json`) with metadata.

9. **Selective Processing**: Can process a single category or all categories via `target_category` parameter.

10. **Optional Logging**: Provides feedback on feed fetching progress when enabled.

## Triage

### Critical Gaps

1. **Error Handling**: Bare `except` clauses swallow all exceptions, making debugging impossible and causing silent failures.

2. **No Retry Logic**: Network failures result in immediate exit or skip with no recovery attempt.

3. **Missing Entry Validation**: No validation of required fields; malformed feeds could cause data corruption.

### High Priority Gaps

4. **ID Collision Risk**: Using timestamp as ID can create collisions for feeds published in the same second.

5. **No Caching/Conditional Requests**: Refetches entire feeds every time, wasting bandwidth and being unfriendly to feed providers.

6. **No Rate Limiting**: Could overwhelm feed servers or trigger rate limits when processing many feeds.

7. **Configuration Validation**: No validation that `feeds.json` is well-formed or contains required fields.

8. **No Feed Health Monitoring**: No tracking of failed feeds, stale feeds, or feed quality metrics.

### Medium Priority Gaps

9. **Timestamp Collision in Merging**: When merging feeds from multiple sources, entries with identical timestamps overwrite each other in the `rslt` dictionary.

10. **No Content Cleaning**: Feed titles/descriptions may contain HTML, invalid characters, or excessive whitespace.

11. **Limited Date Parsing Fallbacks**: Only tries `published_parsed` and `updated_parsed`; some feeds use other fields.

12. **No Maximum Age Filter**: Accumulates all entries regardless of age, potentially creating huge files.

13. **Hardcoded Timezone**: Timezone is hardcoded rather than being configurable per-user.

14. **No Concurrency**: Fetches feeds sequentially, which is slow for many sources.

### Low Priority Gaps

15. **No User Notification System**: No way to alert users of new entries or errors.

16. **Limited Metadata**: Doesn't capture descriptions, images, categories, or other useful RSS fields.

17. **No Import/Export**: No way to backup or share feed configurations.

18. **No Feed Discovery**: No mechanism to suggest or auto-discover related feeds.

## Plan

### 1. Error Handling

**Changes needed:**
- Replace `except:` on line 34-35 with specific exception types:
  ```python
  except (feedparser.exceptions.FeedParserError, urllib.error.URLError, TimeoutError) as e:
      if log:
          sys.stderr.write(f" - Failed: {str(e)}\n")
      continue  # Skip this feed, don't exit
  ```
- Replace `except:` on line 48-49 with:
  ```python
  except (AttributeError, TypeError, ValueError) as e:
      if log:
          sys.stderr.write(f"  Warning: Skipping malformed entry: {str(e)}\n")
      continue
  ```
- Add logging to file for production debugging.

### 2. Retry Logic

**Changes needed:**
- Add retry decorator or manual retry loop:
  ```python
  from urllib3.util.retry import Retry
  from requests.adapters import HTTPAdapter
  import requests
  
  def parse_with_retry(url, max_retries=3, backoff_factor=2):
      for attempt in range(max_retries):
          try:
              return feedparser.parse(url)
          except Exception as e:
              if attempt == max_retries - 1:
                  raise
              time.sleep(backoff_factor ** attempt)
  ```

### 3. Entry Validation

**Changes needed:**
- Add validation function before processing entries:
  ```python
  def validate_entry(feed):
      required = ['link', 'title']
      return all(hasattr(feed, attr) and getattr(feed, attr) for attr in required)
  
  # Use before line 38:
  if not validate_entry(feed):
      continue
  ```

### 4. ID Collision Prevention

**Changes needed:**
- Change ID generation to include URL hash:
  ```python
  import hashlib
  
  # Replace line 62:
  unique_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
  entries["id"] = unique_id
  ```

### 5. Caching/Conditional Requests

**Changes needed:**
- Store ETags and Last-Modified headers:
  ```python
  # Load cache metadata
  cache_file = os.path.join(p["path_data"], "feed_cache.json")
  cache = json.load(open(cache_file)) if os.path.exists(cache_file) else {}
  
  # Use in request
  d = feedparser.parse(url, 
                       etag=cache.get(url, {}).get('etag'),
                       modified=cache.get(url, {}).get('modified'))
  
  # Update cache
  if hasattr(d, 'etag') or hasattr(d, 'modified'):
      cache[url] = {'etag': d.get('etag'), 'modified': d.get('modified')}
      json.dump(cache, open(cache_file, 'w'))
  ```

### 6. Rate Limiting

**Changes needed:**
- Add delay between requests:
  ```python
  from time import sleep
  
  REQUEST_DELAY = 1.0  # seconds between requests
  
  # After line 36:
  sleep(REQUEST_DELAY)
  ```
- Or use token bucket algorithm for more sophisticated limiting.

### 7. Configuration Validation

**Changes needed:**
- Add schema validation using `jsonschema`:
  ```python
  from jsonschema import validate, ValidationError
  
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
  
  # After line 109:
  try:
      validate(instance=RSS, schema=FEEDS_SCHEMA)
  except ValidationError as e:
      sys.exit(f"Invalid feeds.json: {e.message}")
  ```

### 8. Feed Health Monitoring

**Changes needed:**
- Add health tracking structure:
  ```python
  health_file = os.path.join(p["path_data"], "feed_health.json")
  
  def update_health(url, success, error_msg=None):
      health = json.load(open(health_file)) if os.path.exists(health_file) else {}
      if url not in health:
          health[url] = {'successes': 0, 'failures': 0, 'last_error': None, 'last_success': None}
      
      if success:
          health[url]['successes'] += 1
          health[url]['last_success'] = int(time.time())
      else:
          health[url]['failures'] += 1
          health[url]['last_error'] = {'time': int(time.time()), 'msg': error_msg}
      
      json.dump(health, open(health_file, 'w'))
  ```

### 9. Timestamp Collision in Dictionary

**Changes needed:**
- Use list instead of dict for accumulation, or append counter to ID:
  ```python
  # Replace line 24 and lines 64-66:
  rslt = []  # Use list instead
  
  # Line 66:
  rslt.append(entries)
  
  # Replace line 68 with:
  rslt = sorted(rslt, key=lambda x: x['timestamp'], reverse=True)
  ```

### 10. Content Cleaning

**Changes needed:**
- Add sanitization function:
  ```python
  from html import unescape
  import re
  
  def clean_text(text):
      text = unescape(text)
      text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags
      text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
      return text
  
  # Apply on line 65:
  "title": clean_text(feed.title),
  ```

### 11. Date Parsing Fallbacks

**Changes needed:**
- Expand date field attempts:
  ```python
  # Replace lines 40-43:
  parsed_time = (getattr(feed, 'published_parsed', None) or 
                 getattr(feed, 'updated_parsed', None) or
                 getattr(feed, 'created_parsed', None) or
                 time.gmtime())  # Use current time as last resort
  ```

### 12. Maximum Age Filter

**Changes needed:**
- Add age filtering:
  ```python
  MAX_AGE_DAYS = 30
  
  # After line 56:
  age_days = (time.time() - ts) / 86400
  if age_days > MAX_AGE_DAYS:
      continue
  ```

### 13. Configurable Timezone

**Changes needed:**
- Move timezone to feeds.json:
  ```python
  # In feeds.json, add global settings
  # In code, replace hardcoded TIMEZONE:
  timezone_offset = RSS.get('_settings', {}).get('timezone_hours', 9)
  TIMEZONE = datetime.timezone(datetime.timedelta(hours=timezone_offset))
  ```

### 14. Concurrency

**Changes needed:**
- Use ThreadPoolExecutor:
  ```python
  from concurrent.futures import ThreadPoolExecutor, as_completed
  
  def fetch_single_feed(source, url):
      # Extract inner logic
      pass
  
  with ThreadPoolExecutor(max_workers=5) as executor:
      futures = {executor.submit(fetch_single_feed, s, u): s 
                 for s, u in urls.items()}
      for future in as_completed(futures):
          result = future.result()
          # Process result
  ```

### 15-18. Lower Priority Items

These can be addressed in subsequent iterations after core stability is achieved. Each would require:
- **Notifications**: Integration with system notification API or email
- **Extended Metadata**: Expand `entries` dict to include description, enclosures, etc.
- **Import/Export**: Add CLI commands with JSON serialization
- **Feed Discovery**: Integrate OPML parsing or use feed directory APIs