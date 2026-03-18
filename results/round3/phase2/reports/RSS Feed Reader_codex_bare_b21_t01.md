**Observations**

This system is a small RSS fetcher/cache writer.

It currently does these things correctly:

- Loads a bundled `feeds.json` and copies it to the user data directory on first run.
- Merges newly added categories from the bundled feed config into an existing user `feeds.json`.
- Reads feed definitions by category from `FEEDS_FILE_NAME`.
- Fetches RSS/Atom feeds with `feedparser.parse(url)`.
- Iterates feed entries and extracts:
  - publish/update time
  - link
  - title
  - source/author name
- Converts feed timestamps from UTC into a configured local timezone (`TIMEZONE`, currently fixed to UTC+9).
- Formats publication time differently for “today” vs older entries.
- Normalizes entries into a JSON structure with:
  - `id`
  - `sourceName`
  - `pubDate`
  - `timestamp`
  - `url`
  - `title`
- Deduplicates entries implicitly by using the Unix timestamp as the dictionary key.
- Sorts entries newest-first.
- Writes one cache file per category: `rss_<category>.json`.
- Supports:
  - fetching one category via `do(target_category=...)`
  - fetching all categories via `do()`
  - optional progress logging
- Creates the data directory `~/.rreader/` if missing.

**Triage**

Ranked by importance:

1. **Error handling is too weak and sometimes wrong**
- Broad bare `except:` hides root causes.
- `sys.exit(" - Failed\n" if log else 0)` can terminate the whole process from inside one feed fetch.
- A single bad feed can stop processing unexpectedly.
- Failures are not captured in output or logs in a structured way.

2. **Deduplication and identity are unreliable**
- `id = ts` means multiple different articles published in the same second will collide.
- Collisions overwrite entries silently.
- Timestamp is not a stable article identifier.

3. **Timezone/date handling is inconsistent**
- Display uses `datetime.date.today()` in local system time, not `TIMEZONE`.
- `time.mktime(parsed_time)` assumes local system timezone, which can distort timestamps.
- Config comment says KST, but runtime environment may differ.

4. **No validation of feed data or config**
- Assumes `RSS[target_category]["feeds"]` exists.
- Assumes each feed has `link`, `title`, and valid parsed dates.
- No schema validation for `feeds.json`.

5. **No production-grade logging/observability**
- Logging is just `stdout.write`.
- No severity levels, context, retry counts, or per-feed diagnostics.
- No metrics on fetched feeds, skipped entries, failures, or stale caches.

6. **No network robustness**
- No timeout control, retry policy, backoff, user agent, or rate limiting.
- No handling for transient network failures, invalid SSL, or feedparser bozo feeds.

7. **Writes are not atomic**
- JSON is written directly to the target file.
- A crash/interruption can leave truncated or corrupt cache files.

8. **No tests**
- No unit tests for parsing, merge behavior, formatting, or failure cases.
- No integration tests with sample feed payloads.

9. **Data model is minimal and not extensible**
- Stores only a few fields.
- Drops useful metadata like summary, categories/tags, GUID, content hash, favicon, and read status.
- No versioning for cache format.

10. **Directory setup is fragile**
- Uses `os.mkdir` only for listed directories and assumes parent exists.
- No permission handling.
- Path configuration is hard-coded and user-home-centric.

11. **CLI/runtime UX is incomplete**
- `__main__` just runs `do()`.
- No command-line arguments for category, refresh mode, output path, debug mode, or dry run.

12. **Code structure needs cleanup**
- Nested function inside `do()` makes testing harder.
- Import fallback pattern is acceptable but suggests packaging/runtime ambiguity.
- Mixed concerns: config bootstrap, fetching, parsing, formatting, persistence all in one file.

**Plan**

1. **Fix error handling first**
- Replace bare `except:` with explicit exceptions.
- Never `sys.exit()` inside feed-processing logic.
- Return structured per-feed results like `{"status": "ok|error", "error": "...", "entries": [...]}`.
- Continue processing other feeds when one fails.
- Surface failures in logs and optionally in output JSON.

2. **Use stable entry IDs**
- Prefer feed GUID/`id` if present.
- Fallback to URL-based hash, e.g. SHA-256 of `feed.link`.
- If needed, combine source + guid/link + published timestamp.
- Keep timestamp as a sortable field, not the primary identifier.

3. **Correct time handling**
- Compare “today” using the configured timezone, not system-local date.
- Convert parsed times using timezone-aware UTC logic end-to-end.
- Replace `time.mktime(parsed_time)` with `calendar.timegm(parsed_time)` for UTC-safe epoch conversion.
- Make timezone configurable from environment/config, not hard-coded KST.

4. **Validate configuration and feed fields**
- Validate `feeds.json` on load.
- Fail clearly if category is missing or malformed.
- Guard access to optional fields like `author`, `link`, `title`.
- Skip malformed entries with a counted warning instead of silent loss.

5. **Add proper logging**
- Switch to the `logging` module.
- Include category, source, URL, elapsed time, entry counts, and exception details.
- Add debug mode for parser diagnostics.
- Log summary stats after each run.

6. **Harden network behavior**
- Use a real HTTP client if necessary before parsing, with:
  - timeout
  - retry with backoff
  - custom user agent
  - conditional requests via ETag/Last-Modified if supported
- Detect and record malformed feeds instead of silently failing.

7. **Make file writes safe**
- Write JSON to a temp file in the same directory, then `os.replace`.
- Ensure UTF-8 and optional pretty-print/debug mode.
- Consider file locking if concurrent runs are possible.

8. **Add tests**
- Unit tests for:
  - first-run config copy
  - bundled/user merge behavior
  - timestamp conversion
  - “today” formatting
  - deduplication behavior
  - malformed entry skipping
- Integration tests with fixture feeds.

9. **Expand the stored schema**
- Add optional fields like `guid`, `summary`, `author`, `feed_url`, `tags`.
- Include fetch metadata:
  - `created_at`
  - `source_count`
  - `error_count`
  - `schema_version`
- Document the JSON contract.

10. **Improve filesystem/config handling**
- Use `Path` throughout.
- Create directories with `mkdir(parents=True, exist_ok=True)`.
- Separate app config path, cache path, and data path if needed.
- Handle permission errors cleanly.

11. **Add a real CLI**
- Support commands/options like:
  - `--category`
  - `--log-level`
  - `--debug`
  - `--output-dir`
  - `--refresh-all`
- Return useful exit codes.

12. **Refactor for maintainability**
- Split into modules:
  - config/bootstrap
  - feed loading/validation
  - fetch/parse
  - transform
  - persistence
  - CLI
- Move the nested function to top level.
- Add type hints and docstrings for core interfaces.

If you want, I can turn this into a stricter engineering document format with severity labels, acceptance criteria, and an implementation sequence.