# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a minimal RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from configured URLs
2. **Multi-source Aggregation**: Combines multiple feed sources within named categories
3. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
4. **Time Handling**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
5. **Time Display Formatting**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
6. **Data Persistence**: Saves parsed feeds as JSON files (`rss_{category}.json`) in `~/.rreader/`
7. **Configuration Management**: 
   - Bundles default feeds in `feeds.json` alongside the script
   - Copies to user directory on first run
   - Merges new categories from bundled config into user config
8. **Selective Updates**: Can refresh all categories or target a single category
9. **Optional Logging**: Can output fetch progress to stdout
10. **Author Display**: Supports per-category toggle for showing feed author vs source name

## Triage

### Critical Gaps (P0 - System Won't Work Reliably)

1. **No Error Recovery**: Single feed failure exits the entire program
2. **No Network Timeouts**: Hanging feeds will block indefinitely
3. **No Validation**: Malformed JSON or missing keys will crash
4. **Timestamp Collision Handling**: Multiple entries published in the same second overwrite each other

### High Priority Gaps (P1 - Production Blockers)

5. **No Rate Limiting**: Could hammer feed servers or get IP-banned
6. **No Caching/Conditional Requests**: Re-downloads entire feeds every time (no ETags, Last-Modified)
7. **No Concurrency**: Sequential feed fetching is slow for many feeds
8. **No Feed Health Monitoring**: No way to detect persistently failing feeds
9. **No User Feedback**: Silent failures in non-log mode
10. **No Configuration Validation**: Invalid feed URLs accepted without verification

### Medium Priority Gaps (P2 - User Experience)

11. **No Entry Deduplication Across Updates**: Same entry appears multiple times if feed is refetched
12. **No Max Entry Limits**: JSON files grow unbounded
13. **No Content Extraction**: Only stores titles and links, no descriptions or content
14. **No OPML Import/Export**: Can't easily migrate feeds
15. **Hardcoded Timezone**: Requires code change to adjust timezone

### Low Priority Gaps (P3 - Nice to Have)

16. **No Feed Discovery**: Can't auto-detect RSS feeds from website URLs
17. **No Read/Unread Tracking**: No way to mark entries as consumed
18. **No Filtering/Search**: Can't filter by keyword or date range
19. **No Feed Metadata**: Doesn't store feed titles, descriptions, icons
20. **No Analytics**: No stats on fetch success rates, entry counts, etc.

## Plan

### P0 Fixes

**1. Error Recovery**
- **Current**: `sys.exit()` on any feed failure terminates the program
- **Change**: 
  - Wrap the inner `feedparser.parse()` in try-except to catch all exceptions
  - Log the error (feed URL, exception type, message) to a list
  - Continue to next feed
  - At end of `get_feed_from_rss()`, return both results and errors
  - In `do()`, collect all errors and write to `~/.rreader/fetch_errors.log`

**2. Network Timeouts**
- **Current**: No timeout parameter
- **Change**:
  - Add `timeout=30` parameter to `feedparser.parse()` call
  - Document that feedparser respects socket timeout via `socket.setdefaulttimeout(30)` at module top
  - Add retry logic: attempt each feed 2 times with exponential backoff (5s, 10s)

**3. Validation**
- **Current**: Direct attribute access with `getattr()` fallbacks for some fields, but missing for others
- **Change**:
  - Add `validate_feed_entry(feed)` function that checks for required fields
  - Return None for invalid entries, continue processing valid ones
  - For JSON loading, wrap in try-except and handle corruption by recreating from bundled template
  - Validate URLs with `urllib.parse.urlparse()` before adding to config

**4. Timestamp Collision**
- **Current**: `ts` as int seconds used as dictionary key
- **Change**:
  - Use compound key: `f"{ts}_{hash(feed.link)[:8]}"` as entry ID
  - Ensures uniqueness even for simultaneous publications
  - Modify sorting to split ID and sort by numeric prefix

### P1 Fixes

**5. Rate Limiting**
- **Change**:
  - Add `time.sleep(0.5)` between feed fetches within a category
  - Track last fetch time per feed in `~/.rreader/fetch_times.json`
  - Skip feeds fetched within last 5 minutes unless force flag set
  - Add `--force` CLI flag to override minimum interval

**6. Caching**
- **Change**:
  - Store ETag and Last-Modified headers from responses in `~/.rreader/feed_cache.json`
  - Pass as `etag` and `modified` kwargs to `feedparser.parse()`
  - Check `d.status` code: if 304 (Not Modified), use cached data
  - Only write new JSON if feed actually updated

**7. Concurrency**
- **Change**:
  - Import `concurrent.futures.ThreadPoolExecutor`
  - Create executor with `max_workers=5`
  - Submit each feed fetch as separate task
  - Collect results with `as_completed()` to show progress
  - Maintain sequential behavior for single-category mode

**8. Feed Health Monitoring**
- **Change**:
  - Create `~/.rreader/feed_health.json` tracking per-feed stats
  - Store: last_success, last_failure, consecutive_failures, total_attempts
  - Flag feeds with >10 consecutive failures in logs
  - Add `--health` command to display feed statistics

**9. User Feedback**
- **Change**:
  - Add progress bar using `tqdm` library (optional dependency)
  - If not in log mode, print one-line summary: "Fetched 12/15 feeds (3 errors)"
  - Write human-readable summary to `~/.rreader/last_update.txt`

**10. Configuration Validation**
- **Change**:
  - Add `validate_feeds_config()` function called after loading JSON
  - Check: valid JSON structure, URLs are well-formed, categories are non-empty
  - On validation failure, log issues to stderr and skip invalid entries
  - Add `--validate-config` CLI command to check without fetching

### P2 Fixes

**11. Cross-Update Deduplication**
- **Change**:
  - Before writing JSON, load existing file if present
  - Merge old and new entries by ID, keeping newest timestamp
  - Deduplicate by URL: if same URL appears with different IDs, keep only most recent

**12. Max Entry Limits**
- **Change**:
  - Add `"max_entries": 100` to category config (default 500 if unspecified)
  - After merging old/new entries, sort by timestamp descending and slice to max
  - Add global config option `"retention_days": 30` to delete entries older than N days

**13. Content Extraction**
- **Change**:
  - Add fields to entry dict: `"description"`, `"content"`, `"thumbnail"`
  - Extract: `feed.summary` → description, `feed.content[0].value` → content (with fallback chain)
  - Extract thumbnail from `feed.media_thumbnail` or `feed.media_content`
  - Make content storage opt-in per category: `"store_content": true`

**14. OPML Support**
- **Change**:
  - Add `import_opml(filepath)` function using `xml.etree.ElementTree`
  - Parse `<outline>` elements, group by category or create "Imported" category
  - Add `export_opml()` to convert `feeds.json` to OPML format
  - Add CLI commands: `--import-opml FILE`, `--export-opml FILE`

**15. Configurable Timezone**
- **Change**:
  - Move timezone from `config.py` to `~/.rreader/settings.json`
  - Add `"timezone": "+09:00"` setting
  - Parse with `datetime.timezone(datetime.timedelta(hours=offset))`
  - Add `--set-timezone OFFSET` CLI command

### P3 Fixes

**16. Feed Discovery**
- **Change**:
  - Add `discover_feeds(url)` using `feedparser.parse()` on common paths
  - Try: `/feed`, `/rss`, `/atom.xml`, parse HTML for `<link rel="alternate">`
  - Use `requests` + `BeautifulSoup` to find RSS links in HTML head
  - Add `--discover URL` CLI command

**17. Read/Unread Tracking**
- **Change**:
  - Create `~/.rreader/read_entries.json` with set of read entry IDs
  - Add `"read": false` boolean to each entry in output
  - Add CLI/API to mark entries as read by ID
  - Add filter option to show only unread

**18. Filtering**
- **Change**:
  - Add optional parameters to `do()`: `keyword`, `date_from`, `date_to`
  - Filter entries after collection before writing JSON
  - Support regex patterns for keyword matching
  - Add `--filter KEYWORD --since DATE` CLI options

**19. Feed Metadata**
- **Change**:
  - Extract from `d.feed`: `title`, `subtitle`, `icon`, `logo`
  - Store in separate `~/.rreader/feed_metadata.json`
  - Update only when feed structure changes
  - Include in exported data structures

**20. Analytics**
- **Change**:
  - Create `~/.rreader/stats.json` tracking aggregate metrics
  - Record: total fetches, success rate, entries per feed, fetch duration
  - Update after each refresh cycle
  - Add `--stats` command to display formatted report with averages and trends

---

### Implementation Priority Order

**Sprint 1 (Critical)**: Fixes #1-4  
**Sprint 2 (Stability)**: Fixes #5-7  
**Sprint 3 (Monitoring)**: Fixes #8-10  
**Sprint 4 (Features)**: Fixes #11-13  
**Sprint 5 (Portability)**: Fixes #14-15  
**Sprint 6 (Polish)**: Fixes #16-20 as time permits