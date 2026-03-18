# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-source Aggregation**: Handles multiple feed URLs per category, merging entries from different sources
3. **Timestamp Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries from the same moment
5. **Sorting**: Orders entries by timestamp in reverse chronological order (newest first)
6. **Data Persistence**: Saves parsed feeds as JSON files in `~/.rreader/` directory
7. **Configuration Management**: Maintains a `feeds.json` configuration file with feed URLs organized by category
8. **Configuration Updates**: Automatically merges new bundled categories into user configuration without overwriting existing ones
9. **Selective Updates**: Can update a single category or all categories
10. **Logging**: Optional verbose output to track parsing progress
11. **Date Formatting**: Displays time-only for today's entries, date+time for older entries
12. **Author Attribution**: Configurable per-category author display (source name vs. feed author)

## Triage

### Critical Gaps (P0 - System Reliability)

1. **Error Handling**: Broad exception catching with `sys.exit(0)` on failure silently suppresses errors
2. **Network Timeouts**: No timeout configuration for HTTP requests, causing indefinite hangs
3. **Rate Limiting**: No delays between feed requests, risking IP bans from RSS providers
4. **Data Corruption**: No atomic file writes; crashes during write operations leave corrupted JSON

### High Priority (P1 - Production Readiness)

5. **Logging Infrastructure**: Uses print statements instead of proper logging framework
6. **Configuration Validation**: No validation that feeds.json has correct structure
7. **Stale Data Handling**: No maximum age for cached data or forced refresh mechanism
8. **Missing Feed Detection**: Can't distinguish between network failures and missing feeds
9. **Concurrent Access**: No file locking; simultaneous updates corrupt JSON files
10. **Resource Cleanup**: Open network connections not explicitly closed

### Medium Priority (P2 - Operational Excellence)

11. **Performance Metrics**: No tracking of fetch duration or success rates
12. **Partial Failures**: One failed feed aborts entire category update
13. **Entry ID Collisions**: Timestamp-only IDs fail when multiple entries published simultaneously
14. **Memory Management**: Loads all entries into memory before writing (problematic with large feeds)
15. **Duplicate URL Detection**: Can add same feed URL multiple times in configuration
16. **HTTP Caching**: No support for ETags or Last-Modified headers to reduce bandwidth

### Low Priority (P3 - User Experience)

17. **Progress Indication**: No progress bar or completion percentage for multiple feeds
18. **Feed Metadata**: Doesn't store feed title, description, or icon
19. **Entry Content**: Only stores title and link, not full content or summary
20. **Command-Line Interface**: No CLI argument parsing for options like verbosity or data directory
21. **Configuration Comments**: JSON doesn't support comments; no user guidance in feeds.json

## Plan

### P0 - Critical Gaps

**1. Error Handling**
- **Change**: Replace `except:` with specific exception types (`feedparser.ParseError`, `urllib.error.URLError`, etc.)
- **Action**: In `get_feed_from_rss()`, catch each exception type separately and log the specific error with URL and category context
- **Add**: Return a status dict: `{"success": bool, "error": str, "entries_count": int}` per feed
- **Remove**: The `sys.exit(0)` call that silently fails

**2. Network Timeouts**
- **Change**: Add to function signature: `def do(target_category=None, log=False, timeout=30):`
- **Action**: Configure feedparser before parsing: `feedparser.USER_AGENT = "rreader/1.0"` and pass timeout to underlying urllib
- **Alternative**: Use `requests` library with explicit timeout: `response = requests.get(url, timeout=30)` then pass to feedparser

**3. Rate Limiting**
- **Change**: Add `time.sleep(1)` between feed fetches in the loop
- **Action**: Make delay configurable in feeds.json per category: `"rate_limit_seconds": 1.0`
- **Add**: Exponential backoff on HTTP 429 responses: `time.sleep(min(2 ** retry_count, 60))`

**4. Data Corruption Protection**
- **Change**: Write to temporary file first: `temp_file = f"rss_{category}.json.tmp"`
- **Action**: After successful write, atomically rename: `os.replace(temp_file, final_file)`
- **Add**: Validation step: load and parse JSON before replacing original
- **Fallback**: On write failure, keep existing file intact

### P1 - High Priority

**5. Logging Infrastructure**
- **Change**: Add at top of file: `import logging; logger = logging.getLogger(__name__)`
- **Action**: Replace `sys.stdout.write()` with `logger.info()`, `logger.error()`, etc.
- **Add**: Configure in main: `logging.basicConfig(level=logging.INFO if log else logging.WARNING)`
- **Format**: Include timestamp and level: `'%(asctime)s - %(levelname)s - %(message)s'`

**6. Configuration Validation**
- **Change**: Add validation function after loading feeds.json:
```python
def validate_config(config):
    assert isinstance(config, dict), "Config must be dict"
    for cat, data in config.items():
        assert "feeds" in data, f"Category {cat} missing 'feeds'"
        assert isinstance(data["feeds"], dict), f"Category {cat} feeds must be dict"
        for source, url in data["feeds"].items():
            assert url.startswith("http"), f"Invalid URL: {url}"
```
- **Action**: Call after loading, before any processing
- **Add**: Try to parse bundled feeds.json at install time as sanity check

**7. Stale Data Handling**
- **Change**: Check `created_at` timestamp when loading cached data
- **Add**: Parameter `max_age_seconds=3600` to `do()` function
- **Action**: Compare `time.time() - loaded_data["created_at"]` against max_age
- **Behavior**: Force refetch if stale, or add "stale" flag to returned data

**8. Missing Feed Detection**
- **Change**: Check `d.bozo` attribute from feedparser (indicates parse errors)
- **Action**: Log `d.bozo_exception` when `d.bozo == 1`
- **Add**: Track HTTP status codes: check `d.status` (200, 404, 500, etc.)
- **Store**: Add to output JSON: `"feed_status": {"url": {"status": 200, "error": null}}`

**9. Concurrent Access Protection**
- **Change**: Use `fcntl.flock()` on Unix or `msvcrt.locking()` on Windows
- **Action**: Wrap file operations:
```python
import fcntl
with open(file, 'w') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    json.dump(data, f)
    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```
- **Alternative**: Use file-based lock with `filelock` library
- **Timeout**: Fail after 5 seconds if can't acquire lock

**10. Resource Cleanup**
- **Change**: feedparser handles this internally, but verify by checking connection pooling
- **Action**: If switching to `requests` library, use context manager: `with requests.Session() as session:`
- **Add**: Explicitly close any file handles in exception paths
- **Monitor**: Check for file descriptor leaks with `lsof` during testing

### P2 - Medium Priority

**11. Performance Metrics**
- **Change**: Add timing: `start = time.time()` before parse, `duration = time.time() - start` after
- **Store**: Add to output JSON: `"metadata": {"fetch_duration": 1.23, "entry_count": 42}`
- **Track**: Maintain rolling statistics in separate file: `stats.json` with per-feed averages
- **Display**: Log summary after all feeds: "Fetched 5 feeds in 12.3s, 156 entries"

**12. Partial Failure Handling**
- **Change**: Move try/except inside the `for source, url in urls.items():` loop
- **Action**: Continue processing remaining feeds after one fails
- **Collect**: Build list of failures: `failures.append({"source": source, "error": str(e)})`
- **Return**: Include failures in result: `{"entries": [...], "failures": [...]}`

**13. Entry ID Collisions**
- **Change**: Replace `entries["id"] = ts` with `entries["id"] = f"{ts}_{hash(feed.link)[:8]}"`
- **Action**: Use stable hash of URL to differentiate simultaneous posts
- **Alternative**: Use feed's GUID if available: `feed.get("id", f"{ts}_{hash(feed.link)[:8]}")`
- **Dedupe**: Still check for exact duplicates by comparing URLs

**14. Memory Management**
- **Change**: Use generator pattern for large feeds instead of storing all in `rslt` dict
- **Action**: Write entries incrementally to JSON using `json.JSONEncoder` with streaming
- **Alternative**: Process in batches of 100 entries
- **Limit**: Add configuration option `max_entries_per_feed: 200`

**15. Duplicate URL Detection**
- **Change**: Add validation in configuration file load:
```python
all_urls = []
for cat_data in RSS.values():
    all_urls.extend(cat_data["feeds"].values())
assert len(all_urls) == len(set(all_urls)), "Duplicate URLs detected"
```
- **Action**: Run validation before processing any feeds
- **Report**: Log warning with duplicate URLs and their categories

**16. HTTP Caching**
- **Change**: Store ETags/Last-Modified from response headers
- **Action**: Add to stored data: `"cache_headers": {"etag": "...", "last_modified": "..."}`
- **Request**: Send headers on subsequent requests: `If-None-Match`, `If-Modified-Since`
- **Handle**: If 304 Not Modified, reuse cached entries instead of parsing

### P3 - Low Priority

**17. Progress Indication**
- **Change**: Add to loop: `for i, (source, url) in enumerate(urls.items(), 1):`
- **Display**: Log `f"[{i}/{len(urls)}] Fetching {source}..."`
- **Library**: Consider `tqdm` for progress bars: `for url in tqdm(urls.values()):`
- **Conditional**: Only show progress if `log=True` and output is TTY

**18. Feed Metadata Storage**
- **Change**: Extract from `d.feed`: `title = d.feed.get("title")`, `description = d.feed.get("description")`
- **Store**: Add to output JSON at top level: `"feed_info": {"title": "...", "description": "..."}`
- **Icon**: Extract `d.feed.get("image", {}).get("href")` for feed logo
- **Update**: Store separately since it changes rarely

**19. Entry Content**
- **Change**: Add to entries dict: `"summary": feed.get("summary", "")`, `"content": feed.get("content", [{}])[0].get("value", "")`
- **Sanitize**: Use `bleach` library to strip dangerous HTML: `bleach.clean(content, tags=['p', 'br', 'a'])`
- **Truncate**: Store first 500 characters if content is very long
- **Config**: Make content storage optional per category

**20. Command-Line Interface**
- **Change**: Add at bottom:
```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RSS Feed Reader")
    parser.add_argument("--category", help="Update specific category")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--data-dir", default=p["path_data"], help="Data directory")
    args = parser.parse_args()
    do(target_category=args.category, log=args.verbose)
```
- **Action**: Replace `sys` module calls with argparse
- **Add**: `--version`, `--list-categories`, `--validate-config` flags

**21. Configuration Documentation**
- **Change**: Create separate `feeds.example.json` with inline documentation as values
- **Action**: Generate HTML documentation from schema: describe each field
- **Alternative**: Switch to YAML which supports comments
- **Provide**: README.md with configuration examples and common feed sources