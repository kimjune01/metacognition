**Observations**

This system is a small RSS ingester and cache writer.

It currently does these things correctly:

- Loads a bundled `feeds.json` and ensures a user-local copy exists at `~/.rreader/feeds.json`.
- Merges in any new categories from the bundled feed config into the user-local config without overwriting existing user categories.
- Reads feed definitions by category from JSON.
- Fetches and parses RSS/Atom feeds with `feedparser`.
- Iterates feed entries and keeps only items with a usable published or updated timestamp.
- Converts feed timestamps from UTC into a configured local timezone (`UTC+9` as currently hardcoded).
- Formats publication time differently for items from “today” vs older items.
- Builds normalized entry objects with:
  - `id`
  - `sourceName`
  - `pubDate`
  - `timestamp`
  - `url`
  - `title`
- Optionally uses the feed item's author instead of the source name when `show_author=True`.
- Deduplicates entries implicitly by timestamp key within a category result.
- Sorts entries newest-first.
- Writes per-category cache files like `rss_<category>.json` into `~/.rreader/`.
- Supports:
  - refreshing one category via `do(target_category=...)`
  - refreshing all categories via `do()`
  - simple progress logging with `log=True`
- Creates the data directory if it does not exist.

**Triage**

Ranked by importance:

1. **Error handling is too weak and sometimes wrong**
- Broad bare `except:` blocks hide real failures.
- `sys.exit(" - Failed\n" if log else 0)` is not appropriate inside a library function.
- One bad source can terminate the whole process.
- JSON/file errors are not handled.

2. **Identity and deduplication are unreliable**
- Entries are keyed only by Unix timestamp.
- Multiple items published in the same second will overwrite each other.
- This can silently drop articles.

3. **Timezone/date handling is inconsistent**
- “Today” is checked with `datetime.date.today()` in the machine’s local timezone, not `TIMEZONE`.
- `time.mktime(parsed_time)` interprets the tuple as local time, which is wrong for UTC-like feed timestamps.
- Time logic will be wrong on systems not set to Korea time.

4. **No network robustness**
- No request timeout, retry, backoff, or per-feed failure isolation.
- No validation of malformed feeds.
- No user-agent or transport control.

5. **No schema or config validation**
- Assumes `feeds.json` has the expected structure.
- `target_category` is assumed valid.
- Missing keys like `feeds` will raise exceptions.

6. **Unsafe and incomplete file-writing behavior**
- Writes directly to final JSON files instead of atomic writes.
- No locking, so concurrent runs may corrupt output.
- Directory creation is minimal and not recursive.

7. **Poor separation of concerns**
- Fetching, normalization, formatting, config bootstrap, and persistence are all mixed into one function.
- Harder to test and extend.

8. **No observability**
- Logging is just stdout text.
- No structured logs, metrics, or per-feed error reporting.
- Hard to diagnose bad feeds in production.

9. **No tests**
- This code needs unit tests around time parsing, merge behavior, deduplication, and failure modes.
- Productionizing without tests would be risky.

10. **Data model is minimal**
- Drops useful feed fields like summary, categories, GUID, source feed, and content hash.
- No pagination, limits, retention policy, or metadata about failed feeds.

11. **Hardcoded environment assumptions**
- Timezone is fixed to KST.
- Data path is fixed to `~/.rreader/`.
- No CLI options, env config, or dependency injection.

**Plan**

1. **Fix error handling**
- Replace bare `except:` with specific exceptions: parsing errors, file I/O errors, JSON decode errors, key errors.
- Remove `sys.exit()` from inner functions.
- Return structured errors per feed, for example:
  - `{"entries": [...], "errors": [{"source": ..., "url": ..., "error": ...}]}`
- Continue processing other feeds when one fails.
- Raise exceptions only at the program boundary, not in core logic.

2. **Replace timestamp-based IDs**
- Use a stable unique key per entry:
  - prefer `feed.id` or `feed.guid`
  - fallback to `feed.link`
  - fallback to hash of `(source, title, published, link)`
- Keep timestamp as a sortable field, but do not use it as the dictionary key.
- Deduplicate on stable ID, not publish second.

3. **Correct time handling**
- Use timezone-aware comparisons consistently.
- Replace `datetime.date.today()` with “today in configured timezone”.
- Replace `time.mktime(parsed_time)` with `calendar.timegm(parsed_time)` if the tuple is UTC-based.
- Centralize all time parsing in one helper so formatting and timestamps come from the same normalized datetime.

4. **Add resilient fetching**
- Wrap feed fetches per source and record failures instead of aborting.
- If `feedparser` is fetching over HTTP directly, consider switching to `requests` with:
  - timeout
  - retry policy
  - custom user-agent
  - status-code checks
- Then pass the response body into `feedparser.parse()`.
- Track malformed feeds and skipped entries.

5. **Validate config and inputs**
- Validate `FEEDS_FILE_NAME` contents on load.
- Confirm each category has expected keys like `feeds`.
- If `target_category` is unknown, raise a clear `ValueError`.
- Add a config schema, even if lightweight, before processing.

6. **Make writes safe**
- Ensure the data directory exists with `os.makedirs(path, exist_ok=True)`.
- Write JSON to a temporary file and atomically replace the destination.
- Consider file locking if multiple processes may refresh feeds simultaneously.

7. **Refactor into testable units**
- Split the logic into functions like:
  - `load_feed_config()`
  - `merge_bundled_categories()`
  - `fetch_feed(url)`
  - `normalize_entry(feed, source, timezone)`
  - `write_category_cache(category, entries)`
- Keep `do()` as orchestration only.

8. **Improve observability**
- Replace ad hoc stdout writes with the `logging` module.
- Log per-source start, success, failure, item count, and elapsed time.
- Include category and URL in every error log.
- Optionally write a refresh summary to disk.

9. **Add tests**
- Unit tests for:
  - bundled/user config merge behavior
  - unknown category handling
  - timezone conversion and “today” formatting
  - stable deduplication behavior
  - handling entries with missing timestamps
  - partial feed failures
- Integration tests using fixture RSS/Atom payloads instead of live network calls.

10. **Expand the stored entry schema**
- Preserve fields that production consumers usually need:
  - stable ID
  - source key
  - feed URL
  - title
  - link
  - author
  - published ISO timestamp
  - summary/content preview
- Store refresh metadata:
  - `created_at`
  - `feed_count`
  - `error_count`
  - `errors`

11. **Make configuration explicit**
- Move timezone and data path to config or environment variables.
- Do not hardcode KST unless this is intentionally Korea-only software.
- Add a small CLI interface for:
  - refresh all
  - refresh one category
  - verbose logging
  - dry run

The biggest production risks are silent data loss, incorrect timestamps, and brittle failure handling. Those should be fixed before adding features.