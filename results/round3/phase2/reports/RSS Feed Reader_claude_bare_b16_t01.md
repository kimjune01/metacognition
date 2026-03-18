# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` library to fetch and parse RSS/Atom feeds from multiple sources
2. **Multi-Source Aggregation**: Processes multiple RSS feeds organized by categories from a JSON configuration file
3. **Data Persistence**: Stores parsed feed entries as JSON files in a user data directory (`~/.rreader/`)
4. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries from the same feed
5. **Time Localization**: Converts feed timestamps to a configured timezone (currently KST/UTC+9)
6. **Smart Date Formatting**: Displays times as "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
7. **Configuration Management**: 
   - Copies bundled `feeds.json` if user doesn't have one
   - Merges new categories from bundled feeds into existing user configuration
8. **Selective Processing**: Can process all categories or a single target category
9. **Sorted Output**: Orders entries by timestamp (newest first)
10. **Author Attribution**: Supports showing feed-level or entry-level authors based on configuration

## Triage

### Critical Gaps
1. **Error Handling**: Minimal exception handling; failures are silently ignored or cause abrupt exits
2. **Configuration Validation**: No validation of feeds.json structure or URL formats
3. **Data Freshness**: No cache invalidation or TTL logic; stale data persists indefinitely

### High Priority Gaps
4. **Logging Infrastructure**: Uses ad-hoc `sys.stdout.write()` instead of proper logging framework
5. **Rate Limiting**: No delays between feed requests; risks being blocked by servers
6. **Network Resilience**: No retry logic, timeout configuration, or connection pooling
7. **Content Sanitization**: Feed titles and content aren't sanitized (potential XSS if displayed in web UI)

### Medium Priority Gaps
8. **Performance**: Sequential feed processing; no concurrency for multiple feeds
9. **Storage Management**: No cleanup of old entries; disk usage grows unbounded
10. **Feed Health Monitoring**: No tracking of failed feeds, HTTP errors, or parse failures
11. **User Feedback**: No progress indication for long-running operations

### Low Priority Gaps
12. **Testing**: No unit tests, integration tests, or fixtures
13. **Documentation**: Missing docstrings, API documentation, and usage examples
14. **Internationalization**: Hardcoded date formats and no locale support
15. **Feed Discovery**: No OPML import/export or automatic feed URL detection

## Plan

### 1. Error Handling (Critical)
**Changes needed:**
- Wrap `feedparser.parse()` in try-except to catch network errors (ConnectionError, Timeout, URLError)
- Add specific exception handling for parsing errors and invalid feed formats
- Log failed feeds with error details instead of `sys.exit(0)`
- Add fallback for missing `published_parsed`/`updated_parsed` fields
- Return error statistics from `get_feed_from_rss()` to track failure rates

```python
# Example structure:
try:
    d = feedparser.parse(url, timeout=30)
    if d.bozo:  # feedparser's error flag
        log_error(f"Feed parse error for {url}: {d.bozo_exception}")
        continue
except (urllib.error.URLError, TimeoutError) as e:
    log_error(f"Network error for {url}: {e}")
    continue
```

### 2. Configuration Validation (Critical)
**Changes needed:**
- Add JSON schema validation for `feeds.json` structure
- Validate URLs using `urllib.parse.urlparse()` before processing
- Check that required keys exist (`feeds`, category names)
- Provide meaningful error messages for malformed configuration
- Add a `validate_config()` function called at startup

### 3. Data Freshness (Critical)
**Changes needed:**
- Add `max_age` parameter to feed configuration (e.g., 3600 seconds)
- Check `created_at` timestamp in existing JSON files
- Skip re-fetching if data is younger than `max_age`
- Add `force_refresh` parameter to override cache
- Store HTTP ETags and Last-Modified headers for conditional requests

### 4. Logging Infrastructure (High Priority)
**Changes needed:**
- Replace `sys.stdout.write()` with Python's `logging` module
- Configure log levels (DEBUG, INFO, WARNING, ERROR)
- Add file-based logging to `~/.rreader/rreader.log`
- Include timestamps, log levels, and context in log messages
- Add `--verbose` command-line flag to control verbosity

```python
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### 5. Rate Limiting (High Priority)
**Changes needed:**
- Add `time.sleep()` between feed requests (e.g., 0.5-1 second)
- Make delay configurable per-category in `feeds.json`
- Implement exponential backoff for failed requests
- Add randomized jitter to avoid thundering herd

### 6. Network Resilience (High Priority)
**Changes needed:**
- Add timeout parameter to `feedparser.parse()` (default 30 seconds)
- Implement retry logic with `tenacity` or manual retry loop (3 attempts)
- Use `requests.Session()` for connection pooling if switching from feedparser's internal mechanism
- Add User-Agent header to avoid being blocked as a bot

### 7. Content Sanitization (High Priority)
**Changes needed:**
- Use `html.escape()` or `bleach.clean()` on feed titles before storing
- Strip or sanitize HTML tags in content fields
- Validate URLs in `feed.link` to prevent javascript: or data: schemes
- Add content length limits to prevent storage abuse

### 8. Performance (Medium Priority)
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` to fetch feeds in parallel
- Set max_workers to 5-10 to avoid overwhelming servers
- Maintain sequential processing within a single source for politeness
- Add progress bar using `tqdm` library

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_feed, url): url for url in urls.items()}
    for future in as_completed(futures):
        # process results
```

### 9. Storage Management (Medium Priority)
**Changes needed:**
- Add `max_entries` configuration per category (default 100)
- Trim old entries when saving new data
- Add `--cleanup` command to remove entries older than N days
- Implement entry rotation based on file size limits
- Add disk space check before writing files

### 10. Feed Health Monitoring (Medium Priority)
**Changes needed:**
- Create `feed_status.json` tracking last success/failure per feed
- Record HTTP status codes, parse errors, and last fetch time
- Add `--status` command to display feed health dashboard
- Send alerts (stdout or email) for feeds failing >3 consecutive times
- Track average fetch time and entry count trends

### 11. User Feedback (Medium Priority)
**Changes needed:**
- Add progress indication: "Fetching 3/15 feeds..."
- Show statistics after completion: "Processed 15 feeds, 234 new entries, 2 errors"
- Add `--quiet` flag to suppress non-error output
- Use colored terminal output (via `colorama`) for errors/warnings

### 12. Testing (Low Priority)
**Changes needed:**
- Create `tests/` directory with pytest structure
- Mock `feedparser.parse()` responses for unit tests
- Add fixture RSS feeds in `tests/fixtures/`
- Test error conditions (network failures, malformed feeds, missing fields)
- Add integration test with live feed samples
- Aim for >80% code coverage

### 13. Documentation (Low Priority)
**Changes needed:**
- Add module and function docstrings following Google or NumPy style
- Create README.md with installation, configuration, and usage examples
- Document `feeds.json` schema with example
- Add inline comments for complex logic (deduplication, timestamp handling)
- Generate API docs with Sphinx

### 14. Internationalization (Low Priority)
**Changes needed:**
- Make TIMEZONE configurable in `feeds.json` or CLI argument
- Use `locale.setlocale()` for date formatting based on user preference
- Support multiple date format patterns in configuration
- Add translations for user-facing messages using `gettext`

### 15. Feed Discovery (Low Priority)
**Changes needed:**
- Add `--import-opml` command to parse OPML files
- Implement `--export-opml` to generate OPML from current feeds
- Add `--discover` to find RSS links from a website URL
- Support feed autodiscovery via `<link rel="alternate">` HTML tags