# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS feed fetching and parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from URLs defined in a JSON configuration file.

2. **Multi-category organization**: Supports organizing feeds into categories, each with its own set of feed URLs and configuration (e.g., `show_author` flag).

3. **Feed data normalization**: Extracts and standardizes feed entry data (title, URL, publication date, author/source, timestamp) into a consistent JSON structure.

4. **Timestamp handling**: Converts feed timestamps to a configured timezone (currently KST/UTC+9) and formats them for display (relative for today, absolute for older entries).

5. **Deduplication by timestamp**: Uses timestamp as ID to prevent duplicate entries within a single fetch operation.

6. **Data persistence**: Writes fetched feeds to JSON files (one per category) in a user data directory (`~/.rreader/`).

7. **Configuration management**: Maintains a `feeds.json` configuration file, automatically copying bundled defaults on first run and merging new categories from updates.

8. **Selective fetching**: Can fetch all categories or target a specific category via the `target_category` parameter.

9. **Optional logging**: Provides progress output when `log=True`.

10. **Graceful bundled feed updates**: Detects new categories in bundled feeds and adds them to user config without overwriting existing customizations.

---

## Triage

### Critical Gaps

1. **No error recovery or retry logic** – Network failures, malformed feeds, or timeouts cause silent failures (try/except with `sys.exit(0)` swallows errors).

2. **No rate limiting or request management** – Fetching many feeds simultaneously can trigger rate limits or overload servers.

3. **No incremental updates** – Every fetch re-downloads entire feeds, wasting bandwidth and time. No mechanism to fetch only new entries since last run.

4. **No feed validation** – Accepts any URL as a feed; no check for valid RSS/Atom format before parsing.

### High-Priority Gaps

5. **No entry persistence across runs** – Each fetch overwrites previous data; no historical archive or "mark as read" functionality.

6. **Weak duplicate detection** – Timestamp-based ID collision is possible (multiple entries published at same second); no content-based deduplication.

7. **No feed health monitoring** – Doesn't track feed failures, stale feeds (not updated in X days), or permanently dead URLs.

8. **No concurrency** – Fetches feeds sequentially; slow for large feed lists.

9. **No user feedback for partial failures** – If 5 of 10 feeds fail, the system provides no summary or actionable error report.

### Medium-Priority Gaps

10. **Hardcoded timezone** – Timezone is fixed in code (`datetime.timezone(datetime.timedelta(hours=9))`), not configurable per user.

11. **No feed metadata caching** – ETags and Last-Modified headers are ignored, missing HTTP-level caching opportunities.

12. **No content sanitization** – Feed titles and descriptions are stored raw; no HTML stripping or XSS protection for display layer.

13. **Limited timestamp fallback** – Uses `published_parsed` or `updated_parsed`, but ignores other potential date fields (e.g., `created`).

14. **No configuration validation** – Malformed `feeds.json` (invalid JSON, missing required keys) will cause runtime crashes.

### Low-Priority Gaps

15. **No feed discovery** – No way to auto-detect feeds from a website URL (e.g., via `<link rel="alternate">`).

16. **No OPML import/export** – Cannot import feed lists from other readers or export for backup.

17. **No entry content storage** – Only stores title/link; full article content (if available) is discarded.

18. **No search or filtering** – Cannot search across entries or filter by date range, keyword, etc.

---

## Plan

### Critical Gaps

**1. Implement robust error handling and retry logic**

- **Change**: Wrap `feedparser.parse()` in a retry decorator (e.g., using `tenacity` library) with exponential backoff (3 retries, max 60s wait).
- **Add**: Logging for each failure (to file: `~/.rreader/errors.log`) with timestamp, feed URL, and exception type.
- **Replace**: `sys.exit(0)` with `continue` to skip failed feeds instead of silently exiting.
- **Add**: Final summary report: "Fetched X/Y feeds successfully. Z failures (see errors.log)."

**2. Add rate limiting**

- **Add**: Configurable `requests_per_second` setting in `feeds.json` (default: 1 req/sec).
- **Implement**: Token bucket rate limiter before each `feedparser.parse()` call.
- **Add**: Per-domain rate limiting (track last request time per domain, enforce minimum interval).

**3. Implement incremental updates**

- **Add**: New JSON file per category: `rss_{category}_state.json` storing:
  ```json
  {
    "last_fetch": 1234567890,
    "seen_ids": ["url1_hash", "url2_hash", ...],
    "feed_etags": {"url": "etag_value"}
  }
  ```
- **Change**: Before fetching, load state file. Pass ETags to `feedparser` via `request_headers` parameter.
- **Change**: After parsing, compare entry IDs against `seen_ids`. Only append new entries to output JSON.
- **Add**: Prune `seen_ids` older than 30 days to prevent unbounded growth.

**4. Add feed validation**

- **Add**: Function `validate_feed(url)`:
  - Check URL scheme is `http` or `https`.
  - Send HEAD request, verify `Content-Type` contains `xml`, `rss`, or `atom`.
  - Return `(is_valid: bool, error_msg: str)`.
- **Change**: Call `validate_feed()` before `feedparser.parse()`. Skip invalid feeds, log error.
- **Add**: Validation cache (in state file) to avoid re-checking working feeds every run.

---

### High-Priority Gaps

**5. Persist entry history**

- **Change**: Instead of overwriting `rss_{category}.json`, append new entries to it.
- **Add**: `max_entries_per_category` config (default: 500). Trim oldest entries when limit exceeded.
- **Add**: `read` field to each entry (default: false). Provide CLI command to mark entries read.

**6. Improve duplicate detection**

- **Change**: Generate entry ID as `hash(url + published_date)` instead of timestamp alone.
- **Add**: Secondary content-based deduplication: If two entries have same title + source (within 1 hour), keep only first.

**7. Add feed health monitoring**

- **Add**: `feed_stats.json`:
  ```json
  {
    "url": {
      "last_success": 1234567890,
      "last_failure": null,
      "consecutive_failures": 0,
      "last_entry_date": 1234567890
    }
  }
  ```
- **Add**: After each fetch, update stats. Flag feeds as "stale" (no new entries in 60 days) or "dead" (5 consecutive failures).
- **Add**: CLI command `rreader status` to display health summary.

**8. Add concurrent fetching**

- **Add**: Use `concurrent.futures.ThreadPoolExecutor` with `max_workers=5`.
- **Change**: Refactor `get_feed_from_rss()` to process one URL at a time, return `(source, entries_or_error)`.
- **Change**: Map URL list to executor, collect results, merge into final JSON.

**9. Provide partial failure reports**

- **Add**: Return value from `get_feed_from_rss()` becomes:
  ```python
  {
    "entries": [...],
    "created_at": ...,
    "fetch_summary": {
      "total": 10,
      "succeeded": 8,
      "failed": ["url1", "url2"]
    }
  }
  ```
- **Change**: When `log=True`, print summary table at end.

---

### Medium-Priority Gaps

**10. Make timezone configurable**

- **Add**: `timezone` field to `feeds.json`:
  ```json
  {"timezone": "America/New_York"}
  ```
- **Change**: Replace hardcoded `TIMEZONE` with `pytz.timezone(config["timezone"])`.
- **Add**: Default to system timezone if not specified.

**11. Support HTTP caching**

- **Change**: Use `requests` library directly (instead of feedparser's built-in fetcher) to access response headers.
- **Add**: Store `ETag` and `Last-Modified` headers in state file per feed URL.
- **Change**: On subsequent fetches, pass `If-None-Match` and `If-Modified-Since` headers. If server returns 304, skip parsing.

**12. Sanitize content**

- **Add**: Function `sanitize_html(text)` using `bleach` library to strip all HTML tags except whitelisted safe ones.
- **Change**: Apply to `feed.title` before storing (keep raw version in `title_raw` field for debugging).

**13. Expand timestamp fallback**

- **Change**: Timestamp extraction logic to try fields in order: `published_parsed`, `updated_parsed`, `created_parsed`, `dc:date`.
- **Add**: If all fail, log warning and use current time as fallback (mark entry with `"timestamp_guessed": true`).

**14. Validate configuration**

- **Add**: JSON schema file (`feeds_schema.json`) defining required structure.
- **Add**: On startup, validate `feeds.json` against schema using `jsonschema` library.
- **Change**: If invalid, print error with specific issue location, refuse to start.

---

### Low-Priority Gaps

**15. Add feed discovery**

- **Add**: CLI command `rreader discover <url>` that:
  - Fetches HTML from URL.
  - Parses `<link rel="alternate" type="application/rss+xml">` tags.
  - Prints discovered feed URLs with descriptions.

**16. Support OPML import/export**

- **Add**: CLI command `rreader import <file.opml>` that:
  - Parses OPML XML.
  - Extracts feed URLs and categories.
  - Merges into `feeds.json`.
- **Add**: CLI command `rreader export <output.opml>` that generates OPML from current `feeds.json`.

**17. Store full content**

- **Add**: `content` field to entries, storing `feed.content[0].value` or `feed.summary`.
- **Add**: Config flag `store_full_content` (default: false, to avoid bloat).
- **Change**: If true, include content in JSON; otherwise omit.

**18. Add search capability**

- **Add**: CLI command `rreader search <query>` that:
  - Loads all `rss_*.json` files.
  - Filters entries where title/content matches query (case-insensitive substring or regex).
  - Prints results sorted by date.