# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS feeds from multiple sources using `feedparser`
2. **Multi-category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Time Localization**: Converts UTC timestamps to a configured timezone (KST/UTC+9)
4. **Smart Date Formatting**: Shows "HH:MM" for today's entries, "Mon DD, HH:MM" for older ones
5. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries in the same category
6. **JSON Output**: Saves aggregated feeds to `rss_{category}.json` files with metadata
7. **Configuration Management**: Copies bundled default feeds and merges new categories into user configs
8. **Selective Updates**: Can refresh a single category or all categories
9. **Author Attribution**: Supports per-category `show_author` flag to display feed author vs source name
10. **Directory Initialization**: Automatically creates `~/.rreader/` data directory

## Triage

### Critical Gaps
1. **Error Handling** - System exits on any feed failure, no graceful degradation
2. **Collision Detection** - Timestamp-based IDs will collide for simultaneous posts
3. **No Stale Data Management** - Old entries never expire; JSON files grow indefinitely

### High Priority
4. **Logging Infrastructure** - Inconsistent logging; errors swallowed silently
5. **Configuration Validation** - No validation of feeds.json structure
6. **Network Timeout Handling** - No timeout configuration for hanging feeds
7. **Entry Limits** - No cap on entries per category

### Medium Priority
8. **Testing** - No unit tests or integration tests
9. **Performance** - Sequential feed fetching blocks on slow sources
10. **Date Handling Edge Cases** - "today" comparison ignores timezone properly
11. **Documentation** - No docstrings or user documentation

### Low Priority
12. **CLI Interface** - Minimal command-line options
13. **Progress Indicators** - Only shows progress when `log=True`
14. **Feed Metadata** - Doesn't capture description, tags, or images

## Plan

### 1. Error Handling (Critical)
**Changes needed:**
- Replace bare `except:` blocks with specific exception handling
- In `get_feed_from_rss()`, catch per-feed exceptions and continue processing other feeds
- Replace `sys.exit()` with logging and continue execution
- Add retry logic with exponential backoff for transient failures

```python
for source, url in urls.items():
    try:
        # ... parsing logic
    except feedparser.exceptions.ParseError as e:
        logger.error(f"Parse error for {url}: {e}")
        continue
    except requests.exceptions.Timeout as e:
        logger.warning(f"Timeout for {url}: {e}")
        continue
    except Exception as e:
        logger.error(f"Unexpected error for {url}: {e}")
        continue
```

### 2. Collision Detection (Critical)
**Changes needed:**
- Replace `int(time.mktime(parsed_time))` ID with a composite key: `f"{ts}_{hash(feed.link)[:8]}"`
- Or use UUID generation: `str(uuid.uuid5(uuid.NAMESPACE_URL, feed.link))`
- Add collision detection that appends incrementing suffix if ID exists

### 3. Stale Data Management (Critical)
**Changes needed:**
- Add `MAX_ENTRY_AGE_DAYS` configuration constant
- Filter entries older than threshold when loading existing JSON
- Add `MAX_ENTRIES_PER_CATEGORY` limit (e.g., 100 most recent)
- Implement in a `prune_old_entries(entries, max_age_days, max_count)` function

### 4. Logging Infrastructure (High Priority)
**Changes needed:**
- Replace print statements with Python `logging` module
- Create logger: `logger = logging.getLogger(__name__)`
- Add log levels: DEBUG for feed processing, INFO for completion, ERROR for failures
- Add optional log file output: `~/.rreader/rreader.log`
- Remove `log` parameter in favor of log level configuration

### 5. Configuration Validation (High Priority)
**Changes needed:**
- Create `validate_feeds_config(config)` function
- Check required keys: each category has "feeds" dict
- Validate URLs with `urllib.parse.urlparse()`
- Provide clear error messages pointing to invalid lines
- Add JSON schema validation using `jsonschema` library

### 6. Network Timeout Handling (High Priority)
**Changes needed:**
- Add `REQUEST_TIMEOUT = 30` to config.py
- Pass timeout to feedparser: Use `urllib` with timeout via custom agent
- Implement connection pooling for efficiency
- Add `MAX_RETRIES = 3` configuration

```python
import socket
socket.setdefaulttimeout(REQUEST_TIMEOUT)
d = feedparser.parse(url)
```

### 7. Entry Limits (High Priority)
**Changes needed:**
- Add to config.py: `MAX_ENTRIES_PER_CATEGORY = 100`
- After sorting entries, slice: `rslt = rslt[:MAX_ENTRIES_PER_CATEGORY]`
- Make configurable per-category in feeds.json: `"max_entries": 50`

### 8. Testing (Medium Priority)
**Changes needed:**
- Create `tests/` directory with `test_rss_fetch.py`
- Mock `feedparser.parse()` responses for deterministic tests
- Test timezone conversion with various input timezones
- Test collision handling with duplicate timestamps
- Test error scenarios (malformed feeds, network errors)
- Add pytest configuration and CI integration

### 9. Performance (Medium Priority)
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetching
- Add `MAX_WORKERS = 5` to config
- Wrap each feed fetch in executor.submit()
- Aggregate results with `concurrent.futures.as_completed()`

```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_feed, url): source 
               for source, url in urls.items()}
    for future in as_completed(futures):
        # process results
```

### 10. Date Handling Edge Cases (Medium Priority)
**Changes needed:**
- Replace `datetime.date.today()` with `datetime.datetime.now(TIMEZONE).date()`
- This ensures "today" comparison uses configured timezone, not system timezone
- Add tests for boundary cases (midnight transitions)

### 11. Documentation (Medium Priority)
**Changes needed:**
- Add module-level docstring explaining purpose and usage
- Add docstrings to `do()` and `get_feed_from_rss()` with parameter descriptions
- Create `README.md` with installation, configuration, and usage examples
- Document feeds.json schema format
- Add inline comments for complex logic (duplicate detection, timezone handling)

### 12. CLI Interface (Low Priority)
**Changes needed:**
- Add `argparse` for command-line parsing
- Support: `--category`, `--verbose`, `--config-path`, `--data-path`
- Add `--list-categories` to show available categories
- Add `--validate` to check feeds.json without fetching

### 13. Progress Indicators (Low Priority)
**Changes needed:**
- Use `tqdm` library for progress bars: `from tqdm import tqdm`
- Wrap feed iteration: `for source, url in tqdm(urls.items(), desc=category):`
- Show: "Processing Tech [2/5]" style indicators

### 14. Feed Metadata (Low Priority)
**Changes needed:**
- Capture additional fields: `description`, `summary`, `tags`, `media_content`
- Add optional `include_content` flag to feeds.json
- Store in entries dict: `"description": getattr(feed, 'summary', '')[:500]`
- Limit description length to prevent bloat