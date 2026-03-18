# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS/Atom feeds using `feedparser` library
2. **Multi-source Aggregation**: Handles multiple RSS sources organized by category
3. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a category
5. **Smart Date Display**: Shows "HH:MM" for today's entries, "Mon DD, HH:MM" for older ones
6. **Data Persistence**: Stores processed feeds as JSON files in `~/.rreader/` directory
7. **Configuration Management**: Maintains user feed subscriptions in `feeds.json` with automatic updates from bundled defaults
8. **Optional Author Display**: Configurable per-category author/source attribution
9. **Selective Updates**: Can refresh a single category or all categories
10. **Output Caching**: Timestamps cached data for freshness tracking

## Triage

### Critical (Blocks Production Use)
1. **No Error Handling**: Silent failures on network errors, malformed feeds, or corrupted JSON
2. **No Rate Limiting**: Can hammer feed sources, risking IP bans
3. **No Concurrency Control**: Sequential processing makes multi-feed updates extremely slow
4. **Entry ID Collision Risk**: Using timestamp as ID fails when multiple posts share the same second

### High (Impacts Reliability)
5. **No Stale Data Handling**: Cached data never expires; no TTL mechanism
6. **Missing Logging Infrastructure**: Debug-only stdout messages; no proper logging system
7. **No Feed Validation**: Doesn't verify feed health or track persistent failures
8. **Incomplete Fallback Logic**: `parsed_time` fallback exists but feed/URL failures have bare `except` clauses

### Medium (Impacts Usability)
9. **No Entry Limit**: Unbounded storage growth; could cache thousands of old entries
10. **No Configuration Validation**: Invalid `feeds.json` structure will cause runtime crashes
11. **Hardcoded Timezone**: TIMEZONE in config.py should be user-configurable
12. **No CLI Interface**: Can't specify categories, force refresh, or set verbosity from command line

### Low (Quality of Life)
13. **No Summary Statistics**: Doesn't report how many entries were fetched/updated
14. **No Content Extraction**: Only stores title/link; no description/summary field
15. **No Feed Metadata**: Missing last-fetch timestamp, ETag/Last-Modified headers for conditional requests
16. **No Read/Unread Tracking**: Can't mark entries as read

## Plan

### 1. Error Handling (Critical)
**Changes needed:**
- Replace bare `except:` blocks with specific exception types:
  - `feedparser.parse()` → catch `urllib.error.URLError`, `socket.timeout`, `http.client.HTTPException`
  - JSON operations → catch `json.JSONDecodeError`
- Add per-feed error tracking: store `{"url": str, "last_error": str, "error_count": int}` in separate `feed_errors.json`
- Implement retry logic with exponential backoff (3 attempts, 2^n seconds delay)
- Log errors with full traceback to `~/.rreader/errors.log`
- Continue processing remaining feeds when one fails; return summary of successes/failures

### 2. Rate Limiting (Critical)
**Changes needed:**
- Add `time.sleep(1)` between feed fetches (configurable via `feeds.json` → `"rate_limit_seconds": 1`)
- Implement token bucket algorithm for burst handling
- Add per-domain tracking to respect different sources' limits
- Store last-fetch timestamp in `feed_metadata.json`: `{"url": str, "last_fetched": int}`
- Skip fetches if last attempt was within configurable cooldown (default 300s)

### 3. Concurrency (Critical)
**Changes needed:**
- Replace sequential loop with `concurrent.futures.ThreadPoolExecutor`
- Set max workers to `min(10, len(urls))` to limit concurrent connections
- Refactor `get_feed_from_rss()` to process one URL at a time, return `(source, entries_dict)`
- Merge results in main thread before writing JSON
- Add `requests` library with session pooling and timeout configuration (connect=5s, read=10s)

### 4. Entry ID Collision (Critical)
**Changes needed:**
- Change ID from `ts` to `hashlib.sha256(f"{feed.link}{ts}".encode()).hexdigest()[:16]`
- Falls back gracefully when `feed.link` is missing by using `feed.title`
- Update dictionary merge logic to handle hash collisions (append to list, then sort by timestamp)

### 5. Stale Data Handling (High)
**Changes needed:**
- Add `"max_age_seconds": 3600` to each category config in `feeds.json`
- Check `rslt["created_at"]` when loading cached JSON; if `time.time() - created_at > max_age_seconds`, trigger refresh
- Add `force_refresh` parameter to `do()` function to bypass cache
- Implement entry pruning: keep only entries from last N days (configurable, default 7)

### 6. Logging Infrastructure (High)
**Changes needed:**
- Replace `sys.stdout.write()` with Python's `logging` module
- Create logger: `logging.basicConfig(filename=p["path_data"]+'rreader.log', level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')`
- Add log parameter: `do(target_category, log_level="INFO")`
- Log: feed fetch start/complete, parse errors, entry counts, cache writes

### 7. Feed Validation (High)
**Changes needed:**
- After `feedparser.parse()`, check `d.bozo` flag (indicates malformed XML)
- Validate required fields exist: `d.entries`, `feed.title`, `feed.link`
- Store validation results in `feed_metadata.json`: `{"url": str, "is_valid": bool, "last_validated": int}`
- Mark persistently failing feeds (3+ consecutive failures) and skip them with warning log

### 8. Fallback Logic (High)
**Changes needed:**
- In timestamp extraction, add explicit fallback chain:
  ```python
  parsed_time = (
      getattr(feed, 'published_parsed', None) or 
      getattr(feed, 'updated_parsed', None) or
      getattr(feed, 'created_parsed', None) or
      time.localtime()  # Use current time as last resort
  )
  ```
- Log when fallback timestamps are used for debugging
- Add URL validation before `feedparser.parse()`: check scheme is http/https

### 9. Entry Limit (Medium)
**Changes needed:**
- Add `"max_entries": 100` per category in `feeds.json`
- After sorting by timestamp, slice: `rslt = rslt[:config["max_entries"]]`
- Document that entries are kept in reverse chronological order

### 10. Configuration Validation (Medium)
**Changes needed:**
- Add JSON schema validation using `jsonschema` library
- Schema requires: `{"category_name": {"feeds": {"source": "url"}, "show_author": bool, "max_entries": int}}`
- Validate on load; exit with clear error message showing which field is invalid
- Add `rreader --validate-config` command

### 11. User-Configurable Timezone (Medium)
**Changes needed:**
- Move TIMEZONE from `config.py` to `feeds.json`: add top-level `"timezone_offset_hours": 9`
- Parse in `do()`: `TIMEZONE = datetime.timezone(datetime.timedelta(hours=config.get("timezone_offset_hours", 0)))`
- Document supported range: -12 to +14

### 12. CLI Interface (Medium)
**Changes needed:**
- Add `argparse` in `if __name__ == "__main__"` block
- Arguments: `--category`, `--force-refresh`, `--log-level`, `--validate-config`
- Example: `python -m rreader.fetch --category tech --log-level DEBUG`
- Add `--list-categories` to show available categories from `feeds.json`

### 13. Summary Statistics (Low)
**Changes needed:**
- Return value from `get_feed_from_rss()`: `{"entries": [...], "stats": {"total": int, "new": int, "sources": int}}`
- Track "new" by comparing against previous `rss_{category}.json` entry IDs
- Print summary at end: `"Fetched 47 entries (12 new) from 5 sources in tech category"`

### 14. Content Extraction (Low)
**Changes needed:**
- Add to entries dict: `"summary": getattr(feed, 'summary', '')[:500]` (truncate to 500 chars)
- Strip HTML tags from summary using `html.parser.HTMLParser` or `bleach.clean()`
- Make summary field optional; UI can decide whether to display it

### 15. Feed Metadata (Low)
**Changes needed:**
- Store HTTP headers in `feed_metadata.json`: `{"url": str, "etag": str, "last_modified": str}`
- Pass to `feedparser.parse()`: `d = feedparser.parse(url, etag=etag, modified=last_modified)`
- If `d.status == 304`, skip processing (feed unchanged); log cache hit

### 16. Read/Unread Tracking (Low)
**Changes needed:**
- Create `read_entries.json`: `{"entry_id": true}` for marked-as-read entries
- Add field to entries: `"read": entry_id in read_set`
- This is presentation logic; keep separate from fetch logic
- Implement in UI layer, not in `do()` function