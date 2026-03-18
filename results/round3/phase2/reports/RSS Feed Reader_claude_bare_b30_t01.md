# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, reading configuration from a `feeds.json` file.

3. **Feed Management**: 
   - Copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration without overwriting existing ones

4. **Entry Deduplication**: Uses timestamp-based IDs to prevent duplicate entries from the same feed.

5. **Time Handling**: 
   - Converts UTC timestamps to a configured timezone (KST/UTC+9)
   - Formats publication dates as either "HH:MM" for today or "MMM DD, HH:MM" for other dates

6. **Data Persistence**: Saves processed feeds as JSON files (one per category) in `~/.rreader/` directory.

7. **Sorting**: Outputs entries in reverse chronological order (newest first).

8. **Flexible Author Display**: Supports toggling between source name and feed author per category.

9. **Directory Initialization**: Automatically creates required data directories on first run.

10. **CLI Interface**: Can process all categories or target a specific one via parameter.

## Triage

### Critical Gaps
1. **Error Handling**: Minimal exception handling; failures are silent or cause system exit
2. **Feed Validation**: No validation of feeds.json structure or URL formats
3. **Logging**: Only basic stdout messages; no proper logging framework

### High Priority
4. **Retry Logic**: No retry mechanism for transient network failures
5. **Rate Limiting**: No throttling between requests; could trigger rate limits
6. **Caching**: No HTTP caching (ETags, Last-Modified headers)
7. **Configuration Validation**: TIMEZONE is hardcoded; no validation of user settings
8. **Entry ID Collisions**: Timestamp-based IDs can collide if multiple entries have same publish time

### Medium Priority
9. **Timeout Configuration**: No request timeouts defined
10. **Feed Health Monitoring**: No tracking of consistently failing feeds
11. **Data Migration**: No versioning or migration strategy for JSON format changes
12. **Concurrency**: Sequential processing; could be parallelized
13. **Memory Management**: All entries loaded into memory; problematic for large feeds

### Low Priority
14. **Entry Limit**: No maximum entries per feed or age-based filtering
15. **Progress Indication**: Minimal feedback during long operations
16. **Cleanup**: No removal of old JSON files or pruning of stale entries
17. **Unicode Handling**: While `ensure_ascii=False` is used, no normalization

## Plan

### 1. Error Handling
**Changes needed:**
- Replace bare `except:` clauses with specific exception types (`feedparser.FeedParserException`, `urllib.error.URLError`, `socket.timeout`)
- Add per-feed error handling to continue processing other feeds when one fails
- Store error states in output JSON with structure: `{"entries": [...], "errors": [{"source": "X", "error": "Y", "timestamp": Z}]}`
- Return partial results instead of calling `sys.exit(0)` on failure

### 2. Feed Validation
**Changes needed:**
- Add JSON schema validation for `feeds.json` using `jsonschema` library
- Validate URL format using `urllib.parse.urlparse()` and check for http/https schemes
- Add startup validation function that runs before processing:
```python
def validate_feeds_config(rss_config):
    for category, data in rss_config.items():
        assert "feeds" in data and isinstance(data["feeds"], dict)
        for source, url in data["feeds"].items():
            parsed = urlparse(url)
            assert parsed.scheme in ['http', 'https']
```

### 3. Logging
**Changes needed:**
- Replace `sys.stdout.write()` and print statements with Python's `logging` module
- Create logger: `logger = logging.getLogger(__name__)`
- Add log levels: DEBUG for feed processing details, INFO for progress, WARNING for recoverable errors, ERROR for failures
- Add optional file logging to `~/.rreader/rreader.log` with rotation

### 4. Retry Logic
**Changes needed:**
- Wrap `feedparser.parse()` in retry decorator or loop
- Implement exponential backoff: 1s, 2s, 4s delays
- Make retry count configurable (default: 3)
```python
for attempt in range(MAX_RETRIES):
    try:
        d = feedparser.parse(url)
        break
    except Exception as e:
        if attempt < MAX_RETRIES - 1:
            time.sleep(2 ** attempt)
        else:
            # log and continue to next feed
```

### 5. Rate Limiting
**Changes needed:**
- Add delay between requests: `time.sleep(0.5)` after each `feedparser.parse()`
- Make delay configurable per category in feeds.json: `"rate_limit_seconds": 1.0`
- For multiple feeds from same domain, group and add longer delays

### 6. Caching
**Changes needed:**
- Store ETags and Last-Modified headers in separate cache file: `~/.rreader/cache.json`
- Pass headers to feedparser: `feedparser.parse(url, etag=cached_etag, modified=cached_modified)`
- Check `d.status` for 304 (Not Modified) and skip processing
- Structure: `{"url": {"etag": "...", "modified": "...", "last_check": timestamp}}`

### 7. Configuration Validation
**Changes needed:**
- Move TIMEZONE to feeds.json or separate config.json
- Add validation for timezone offset range (-12 to +14 hours)
- Provide timezone name support using `pytz` or `zoneinfo`
```python
TIMEZONE = datetime.timezone(datetime.timedelta(hours=config.get("timezone_offset", 9)))
```

### 8. Entry ID Collisions
**Changes needed:**
- Change ID generation to include URL hash: 
```python
import hashlib
id_base = f"{ts}_{feed.link}"
entry_id = hashlib.md5(id_base.encode()).hexdigest()
```
- Alternatively, use sequential counter when timestamps match

### 9. Timeout Configuration
**Changes needed:**
- Set socket timeout before parsing: `socket.setdefaulttimeout(30)`
- Or configure feedparser agent with timeout (if supported by underlying library)
- Make timeout configurable in feeds.json

### 10. Feed Health Monitoring
**Changes needed:**
- Track failure count in persistent state file: `~/.rreader/feed_health.json`
- Structure: `{"category/source": {"failures": 3, "last_success": timestamp, "last_failure": timestamp}}`
- Implement exponential backoff for repeatedly failing feeds (check every 2^n hours)
- Add reporting command to show unhealthy feeds

### 11. Data Migration
**Changes needed:**
- Add version field to all JSON outputs: `{"version": 1, "entries": [...]}`
- Create migration functions: `migrate_v1_to_v2(data)`
- Check version on load and run migrations sequentially

### 12. Concurrency
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel feed fetching
```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_feed, url): source for source, url in urls.items()}
    for future in as_completed(futures):
        results[futures[future]] = future.result()
```
- Respect rate limits by domain using semaphores

### 13. Memory Management
**Changes needed:**
- Process entries as stream instead of loading all into dictionary
- Write to JSON incrementally or limit in-memory entries to last N (configurable, default 1000)
- Implement generator pattern for large feeds

### 14. Entry Limit
**Changes needed:**
- Add to feeds.json: `"max_entries": 100, "max_age_days": 30`
- Filter entries: `if (current_time - ts) > max_age_seconds: continue`
- Apply limit after sorting: `rslt[:max_entries]`

### 15. Progress Indication
**Changes needed:**
- Add progress bar using `tqdm` library for multi-feed operations
- Show: `Processing feeds: 45/120 [####------] example.com/feed`

### 16. Cleanup
**Changes needed:**
- Add cleanup function to remove entries older than configured retention period
- Archive or delete old JSON files: check file mtime and remove if > 90 days
- Add `--cleanup` CLI flag to trigger maintenance

### 17. Unicode Handling
**Changes needed:**
- Normalize feed titles: `unicodedata.normalize('NFC', feed.title)`
- Sanitize control characters: `re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)`
- Add encoding detection fallback if feedparser fails