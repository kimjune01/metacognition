# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS feeds using the `feedparser` library
2. **Multi-source Aggregation**: Handles multiple feed sources organized by categories
3. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Deduplication**: Uses timestamps as unique IDs to prevent duplicate entries within a category
5. **Sorting**: Orders entries by timestamp in reverse chronological order (newest first)
6. **Persistence**: Stores parsed feeds as JSON files in a user data directory (`~/.rreader/`)
7. **Configuration Management**: Maintains a `feeds.json` configuration file with bundled defaults
8. **Incremental Updates**: Merges new categories from bundled feeds without overwriting user customizations
9. **Flexible Author Display**: Supports per-category toggle for showing feed author vs. source name
10. **Human-Readable Dates**: Formats timestamps as "HH:MM" for today, "MMM DD, HH:MM" for older dates
11. **Selective Updates**: Can refresh a single category or all categories
12. **Basic Error Handling**: Catches and handles parsing failures with optional logging

## Triage

### Critical Gaps (Block Production Use)

1. **No Error Recovery**: Failed feed fetches terminate silently or exit entirely; no retry logic or graceful degradation
2. **Security Vulnerabilities**: No timeout on HTTP requests; susceptible to SSRF attacks and DoS via malicious feeds
3. **No Validation**: Feed URLs, JSON structure, and configuration are not validated before use
4. **Race Conditions**: Concurrent updates to the same category will corrupt JSON files
5. **Memory Issues**: Entire feed history loaded into memory; no pagination or size limits

### Major Gaps (Limit Functionality)

6. **No Incremental Updates**: Re-fetches entire feeds every time; wastes bandwidth and is slow
7. **No User Feedback**: Silent failures make debugging impossible for end users
8. **No Feed Management**: No way to add, remove, or modify feeds without editing JSON manually
9. **Poor Scalability**: Synchronous fetching means hundreds of feeds would take minutes to update
10. **No Content Storage**: Only stores metadata; actual article content never retrieved

### Minor Gaps (Quality of Life)

11. **Hardcoded Configuration**: Timezone and paths are not user-configurable
12. **No Data Migration**: Schema changes would break existing installations
13. **Limited Date Formatting**: Only shows today vs. older; no "yesterday" or relative times
14. **No Feed Health Monitoring**: No tracking of which feeds consistently fail
15. **No Update Scheduling**: System requires external cron/scheduler; no built-in automation

## Plan

### 1. Error Recovery (Critical)

**Changes needed:**
- Wrap each feed fetch in try/except with specific exception types (URLError, HTTPError, socket.timeout)
- Implement exponential backoff retry logic (3 attempts with 1s, 2s, 4s delays)
- On final failure, log error details and continue to next feed rather than exiting
- Store last successful fetch time in category JSON; display stale data with warning if fetch fails
- Add `--strict` flag that exits on first error for CI/CD use cases

**Specific code locations:**
- In `get_feed_from_rss()`, replace bare `except:` at line ~35 with specific exceptions
- Add retry decorator or manual loop around `feedparser.parse(url)`
- Store fetch metadata: `{"entries": [...], "created_at": ts, "last_error": {...}}`

### 2. Security Hardening (Critical)

**Changes needed:**
- Add timeout parameter to feedparser: `feedparser.parse(url, timeout=30)`
- Validate URLs with allowlist of schemes (http, https only) and reject private IP ranges
- Set maximum feed size limit (e.g., 10MB) using `Content-Length` header check
- Implement rate limiting: max 1 request per second per domain
- Sanitize all feed content (titles, URLs) before storing to prevent XSS if displayed in web UI

**Specific code locations:**
- Create `validate_url()` function checking scheme and using `ipaddress` module for IP validation
- Add `requests.head(url, timeout=5)` before full fetch to check size
- Use `time.sleep()` with per-domain tracking dictionary

### 3. Configuration Validation (Critical)

**Changes needed:**
- Define JSON schema for `feeds.json` using `jsonschema` library
- Validate on load; provide clear error messages pointing to line/field with issue
- Check that all required fields exist: category name, feeds dict, each feed has name and URL
- Validate URL format for each feed using `urllib.parse.urlparse()`
- Add `--validate` command that checks config without fetching

**Specific code locations:**
- Create `schemas/feeds_schema.json` with required structure
- Add validation call after `json.load()` at line ~72
- Wrap in try/except jsonschema.ValidationError with user-friendly message

### 4. Concurrent Safety (Critical)

**Changes needed:**
- Use file locking (`fcntl.flock` on Unix, `msvcrt.locking` on Windows) around JSON read/write
- Alternative: atomic writes using temp file + rename pattern
- Add lock timeout (30s) with error if can't acquire
- Consider using SQLite instead of JSON for built-in ACID properties
- Add `--no-parallel` flag to disable concurrent updates if needed

**Specific code locations:**
- Create `safe_json_write()` wrapper function
- Pattern: write to `rss_{category}.json.tmp`, then `os.rename()` atomically
- Replace `open().write()` at line ~66 with atomic write

### 5. Memory Management (Critical)

**Changes needed:**
- Limit stored entries per category (default 1000, configurable in feeds.json)
- Implement sliding window: keep only entries from last N days (default 30)
- Add pruning step before saving: `entries = entries[:max_entries]`
- Stream large feeds instead of loading entirely: use SAX parser for giant feeds
- Add `--prune` command to clean old data from all categories

**Specific code locations:**
- In `get_feed_from_rss()`, after sorting at line ~65, add slice: `rslt["entries"] = rslt["entries"][:1000]`
- Add config: `RSS[category].get("max_entries", 1000)`

### 6. Incremental Updates (Major)

**Changes needed:**
- Store `ETag` and `Last-Modified` headers from feed responses
- Send conditional GET requests using stored headers
- Parse 304 Not Modified responses; skip processing if feed unchanged
- Store feed metadata in separate `_meta.json` files per category
- Add `--force-refresh` flag to ignore cached headers

**Specific code locations:**
- Switch from `feedparser.parse(url)` to manual requests: `response = requests.get(url, headers={...})`
- Store: `{"etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}`
- Pass to next fetch: `headers = {"If-None-Match": etag, "If-Modified-Since": last_modified}`

### 7. User Feedback (Major)

**Changes needed:**
- Replace print statements with proper logging using `logging` module
- Add verbosity levels: ERROR (default), WARNING, INFO (-v), DEBUG (-vv)
- Create structured logs in JSON format for machine parsing
- Add progress bar using `tqdm` when fetching multiple feeds
- Write summary report: "Fetched X/Y feeds, Z new entries, N errors"

**Specific code locations:**
- Replace `sys.stdout.write()` at lines ~24, 30 with `logger.info()`
- Add at top: `logger = logging.getLogger(__name__)`
- Configure handler in `if __name__ == "__main__"` based on --verbose flag
- Wrap main loop with `tqdm(RSS.items(), desc="Fetching categories")`

### 8. Feed Management API (Major)

**Changes needed:**
- Add `add_feed(category, name, url)` function with validation
- Add `remove_feed(category, name)` function
- Add `list_feeds()` function returning structured data
- Add `update_feed(category, old_name, new_name, new_url)` function
- Expose via CLI subcommands: `rreader add-feed CATEGORY NAME URL`

**Specific code locations:**
- Create new file `rreader/manage.py` with management functions
- Each function loads feeds.json, modifies, validates, saves atomically
- Update `__main__.py` to parse subcommands using `argparse`
- Add commands: `add-feed`, `remove-feed`, `list-feeds`, `update-feed`

### 9. Async Fetching (Major)

**Changes needed:**
- Convert to async/await using `asyncio` and `aiohttp`
- Fetch all feeds in a category concurrently with `asyncio.gather()`
- Limit concurrent requests with `asyncio.Semaphore(10)`
- Add connection pooling for better performance
- Fall back to synchronous mode if async fails

**Specific code locations:**
- Convert `get_feed_from_rss()` to `async def get_feed_from_rss_async()`
- Replace `feedparser.parse()` with `async with aiohttp.ClientSession()` fetch + parse
- In `do()`, wrap with `asyncio.run(asyncio.gather(*tasks))`
- Keep synchronous version for single-category updates

### 10. Content Retrieval (Major)

**Changes needed:**
- Add optional full-text extraction using `readability-lxml` or `newspaper3k`
- Store article content in separate files: `articles/{category}/{entry_id}.html`
- Add `fetch_content` boolean flag per category in feeds.json
- Implement content caching: only fetch if not already stored
- Add `--fetch-content` CLI flag to enable/disable

**Specific code locations:**
- After line ~55 where entry is created, add: `if fetch_content: content = extract_article(url)`
- Create `get_article_content(url)` function using requests + readability
- Store in entry dict: `"content_path": f"articles/{category}/{ts}.html"`
- Write content to file after JSON is saved

### 11. Configurable Settings (Minor)

**Changes needed:**
- Create `~/.rreader/config.json` for user preferences
- Add settings: timezone, max_entries, fetch_timeout, data_path
- Provide defaults if config doesn't exist
- Add `--config` flag to specify alternate config path
- Validate config schema like feeds.json

**Specific code locations:**
- In `config.py`, load from config.json instead of hardcoding
- Pattern: `TIMEZONE = config.get("timezone", "UTC+9")`; parse using `dateutil.tz`
- Move `p["path_data"]` to config: `data_path`

### 12. Data Migrations (Minor)

**Changes needed:**
- Add version number to all JSON files: `{"version": 1, "entries": [...]}`
- Create migration functions: `migrate_v1_to_v2()`, etc.
- Check version on load; run migrations if older than current
- Store current version constant: `SCHEMA_VERSION = 2`
- Add `--migrate` command to manually trigger migrations

**Specific code locations:**
- Add `SCHEMA_VERSION = 1` constant in common.py
- On JSON load, check `data.get("version", 0)`
- If `data["version"] < SCHEMA_VERSION`, call appropriate migration chain
- Migrations in `rreader/migrations.py`

### 13. Enhanced Date Formatting (Minor)

**Changes needed:**
- Add "Yesterday" for entries from previous day
- Add relative times for recent entries: "5 minutes ago", "2 hours ago"
- Use `humanize` library for relative time formatting
- Make format configurable per user preference
- Add timezone info to display: "2 hours ago (KST)"

**Specific code locations:**
- In `get_feed_from_rss()` around line ~47, replace format logic
- Add: `if at.date() == today: format = relative; elif at.date() == yesterday: format = "Yesterday, HH:MM"`
- Use `humanize.naturaltime(at)` for entries < 24 hours old

### 14. Feed Health Monitoring (Minor)

**Changes needed:**
- Track success/failure history per feed: last 10 fetch attempts
- Store in metadata: `{"url": ..., "history": [{"ts": ..., "success": bool, "error": str}]}`
- Calculate uptime percentage and average fetch time
- Add `--health` command showing feed statistics
- Warn users about consistently failing feeds (< 50% uptime)

**Specific code locations:**
- Create `rss_{category}_meta.json` files storing per-feed stats
- Update after each fetch attempt in `get_feed_from_rss()`
- Create `health_report()` function iterating all meta files
- Display in terminal as table using `tabulate` library

### 15. Update Scheduling (Minor)

**Changes needed:**
- Add daemon mode: `rreader daemon --interval 3600`
- Run update loop every N seconds in background
- Use `schedule` library for cron-like syntax: `schedule.every().hour.do(update)`
- Add PID file to prevent multiple instances
- Support systemd service file for Linux installations

**Specific code locations:**
- Create `rreader/daemon.py` with main loop
- Pattern: `while True: do(); time.sleep(interval)`
- Add signal handlers (SIGTERM, SIGINT) for graceful shutdown
- Create PID file in `~/.rreader/rreader.pid`
- Include example `rreader.service` file in repository