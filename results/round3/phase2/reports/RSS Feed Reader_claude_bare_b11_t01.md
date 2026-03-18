# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS feeds using the `feedparser` library from multiple sources.

2. **Multi-source Aggregation**: Handles multiple RSS feed URLs per category and deduplicates entries using timestamps as unique identifiers.

3. **Time Localization**: Converts UTC timestamps to a configured timezone (currently KST/UTC+9) and formats display times contextually (HH:MM for today, "Mon DD, HH:MM" for other dates).

4. **Data Persistence**: Saves parsed feed data as JSON files (`rss_{category}.json`) in a user data directory (`~/.rreader/`).

5. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file with feed sources per category
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled feeds into existing user configurations

6. **Flexible Execution**: Can process all categories or target a specific category via the `target_category` parameter.

7. **Author Display**: Supports optional `show_author` flag per category to display feed author instead of source name.

8. **Sorted Output**: Returns entries sorted by timestamp in reverse chronological order (newest first).

## Triage

### Critical Gaps
1. **No Error Recovery**: Exception handling uses bare `except` clauses and `sys.exit()`, making the system brittle and difficult to debug.
2. **No Feed Validation**: Missing configuration file structure validation; malformed `feeds.json` will crash the system.
3. **No Rate Limiting**: Unlimited concurrent requests could trigger rate limits or overwhelm servers.

### High Priority Gaps
4. **No Caching Strategy**: Refetches all feeds on every run without checking if data is recent, wasting bandwidth.
5. **No Logging Infrastructure**: Uses `sys.stdout.write()` only when `log=True`; no persistent logs or error tracking.
6. **Duplicate ID Collision**: Uses only timestamp as ID, causing data loss when multiple entries share the same publication time.
7. **No Timeout Configuration**: Network requests have no timeout, risking indefinite hangs.

### Medium Priority Gaps
8. **No Feed Health Monitoring**: Doesn't track which feeds consistently fail or are stale.
9. **No User Feedback**: Command-line interface provides minimal feedback about what's happening.
10. **No Data Retention Policy**: Old JSON files accumulate without cleanup or archival strategy.
11. **Hard-coded Timezone**: Timezone is configured in code rather than user settings.

### Low Priority Gaps
12. **No Testing**: No unit tests, integration tests, or fixtures for development.
13. **No Feed Discovery**: Users must manually edit JSON to add feeds; no OPML import or feed discovery.
14. **Limited Metadata**: Doesn't capture descriptions, images, or categories from feeds.

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Replace bare `except:` with specific exception types:
  ```python
  except (feedparser.URLError, feedparser.HTTPError, socket.timeout) as e:
      logger.error(f"Failed to fetch {url}: {e}")
      continue  # Skip this feed, don't crash
  ```
- Remove `sys.exit()` calls in library code; raise custom exceptions instead
- Add a `FeedFetchError` exception class for recoverable errors
- Wrap the main loop to continue processing other feeds when one fails

### 2. Feed Validation (Critical)
**Changes needed:**
- Add JSON schema validation using `jsonschema` library:
  ```python
  FEEDS_SCHEMA = {
      "type": "object",
      "patternProperties": {
          ".*": {
              "type": "object",
              "required": ["feeds"],
              "properties": {
                  "feeds": {"type": "object"},
                  "show_author": {"type": "boolean"}
              }
          }
      }
  }
  ```
- Validate `feeds.json` after loading and provide helpful error messages
- Add a `validate_feeds_config()` function called before processing

### 3. Rate Limiting (Critical)
**Changes needed:**
- Add delays between requests:
  ```python
  import time
  RATE_LIMIT_DELAY = 1  # seconds between requests
  
  for source, url in urls.items():
      time.sleep(RATE_LIMIT_DELAY)
      # ... fetch feed
  ```
- Consider using `ratelimit` library for more sophisticated throttling
- Add configurable concurrent request limits if implementing async fetching

### 4. Caching Strategy (High Priority)
**Changes needed:**
- Check file modification time before refetching:
  ```python
  cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
  if os.path.exists(cache_file):
      cache_age = time.time() - os.path.getmtime(cache_file)
      if cache_age < CACHE_TTL:  # e.g., 300 seconds
          return json.load(open(cache_file))
  ```
- Add `--force-refresh` CLI flag to bypass cache
- Store ETags and Last-Modified headers to use conditional requests

### 5. Logging Infrastructure (High Priority)
**Changes needed:**
- Replace `sys.stdout.write()` with proper logging:
  ```python
  import logging
  
  logger = logging.getLogger(__name__)
  logging.basicConfig(
      level=logging.INFO,
      format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
      handlers=[
          logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
          logging.StreamHandler()
      ]
  )
  ```
- Log all fetch attempts, successes, failures with timestamps
- Add different log levels for debugging vs. production

### 6. Duplicate ID Collision (High Priority)
**Changes needed:**
- Generate composite IDs:
  ```python
  import hashlib
  
  unique_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
  entries = {
      "id": unique_id,
      # ... rest of fields
  }
  ```
- Use URL + timestamp as the deduplication key
- Alternatively, use a UUID if feed entries lack stable identifiers

### 7. Timeout Configuration (High Priority)
**Changes needed:**
- Add timeout to feedparser:
  ```python
  FETCH_TIMEOUT = 30  # seconds
  d = feedparser.parse(url, request_headers={'User-Agent': 'RReader/1.0'})
  ```
- Note: feedparser uses underlying HTTP library timeout; may need to use `urllib` or `requests` with explicit timeout wrapper

### 8. Feed Health Monitoring (Medium Priority)
**Changes needed:**
- Track feed status in separate metadata file:
  ```python
  feed_status = {
      url: {
          "last_success": timestamp,
          "last_failure": timestamp,
          "consecutive_failures": count,
          "last_error": error_message
      }
  }
  ```
- Alert users when feeds haven't updated in N days
- Disable feeds after X consecutive failures with option to re-enable

### 9. User Feedback (Medium Priority)
**Changes needed:**
- Add progress indicators:
  ```python
  from tqdm import tqdm
  
  for source, url in tqdm(urls.items(), desc=f"Fetching {category}"):
      # ... fetch feed
  ```
- Print summary statistics after completion (X feeds processed, Y new entries)
- Add `--quiet` and `--verbose` flags

### 10. Data Retention Policy (Medium Priority)
**Changes needed:**
- Add configurable retention in `config.py`:
  ```python
  MAX_ENTRIES_PER_CATEGORY = 1000
  MAX_ENTRY_AGE_DAYS = 30
  ```
- Filter old entries when saving:
  ```python
  cutoff_time = time.time() - (MAX_ENTRY_AGE_DAYS * 86400)
  rslt = [e for e in rslt if e["timestamp"] > cutoff_time][:MAX_ENTRIES_PER_CATEGORY]
  ```

### 11. Hard-coded Timezone (Medium Priority)
**Changes needed:**
- Move timezone to `feeds.json` or separate user config:
  ```python
  # In feeds.json:
  {
      "_settings": {
          "timezone_offset": 9
      },
      "tech": { ... }
  }
  ```
- Add timezone detection: `datetime.datetime.now().astimezone().tzinfo`
- Allow per-user override via environment variable

### 12. Testing (Low Priority)
**Changes needed:**
- Create `tests/` directory with pytest structure
- Add fixtures with sample RSS XML responses
- Mock `feedparser.parse()` to avoid network calls:
  ```python
  @pytest.fixture
  def mock_feed_response():
      return feedparser.FeedParserDict({
          'entries': [{'title': 'Test', 'link': 'http://...', ...}]
      })
  ```
- Test edge cases: empty feeds, malformed dates, missing fields

### 13. Feed Discovery (Low Priority)
**Changes needed:**
- Add OPML import function:
  ```python
  import xml.etree.ElementTree as ET
  
  def import_opml(opml_file):
      tree = ET.parse(opml_file)
      # Parse <outline> elements and add to feeds.json
  ```
- Add CLI command: `rreader import feeds.opml`
- Consider auto-discovering feeds from URLs using `feedfinder2`

### 14. Limited Metadata (Low Priority)
**Changes needed:**
- Expand captured fields:
  ```python
  entries = {
      # ... existing fields
      "description": getattr(feed, 'summary', '')[:500],
      "image": getattr(feed, 'media_thumbnail', [{}])[0].get('url', ''),
      "categories": [tag.term for tag in getattr(feed, 'tags', [])]
  }
  ```
- Make additional fields optional to maintain backward compatibility
- Update JSON schema accordingly