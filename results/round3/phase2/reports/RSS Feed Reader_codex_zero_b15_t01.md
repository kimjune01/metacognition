**Observations.**

This system is a small RSS fetcher and cache writer.

It currently does these things correctly:

- Loads a bundled `feeds.json` and ensures a user-scoped copy exists at `~/.rreader/feeds.json`.
- Merges in any new categories from the bundled feed config into the user config without overwriting existing user-defined categories.
- Reads feed definitions by category, where each category contains a `feeds` mapping of source name to RSS URL.
- Fetches RSS/Atom feeds with `feedparser.parse(url)`.
- Extracts entries from each feed and uses `published_parsed` or `updated_parsed` when available.
- Converts parsed timestamps from UTC into a configured timezone (`UTC+9` in the example).
- Formats display timestamps as either `HH:MM` for today or `Mon DD, HH:MM` for older items.
- Builds normalized entry objects with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`.
- Supports optional per-category author display via `show_author`.
- Deduplicates entries implicitly by timestamp key within a category result.
- Sorts entries newest-first.
- Writes per-category cache files like `~/.rreader/rss_<category>.json`.
- Supports fetching either one category or all categories.
- Provides optional progress logging to stdout.

**Triage.**

Ranked by importance:

1. **Error handling is unsafe and too broad**
- Bare `except:` blocks hide real failures.
- A single bad fetch can terminate the whole process with `sys.exit`.
- Parse failures, filesystem failures, malformed config, and bad feed entries are not distinguished.

2. **ID generation and deduplication are incorrect**
- `id = ts` means all entries sharing the same second collide.
- Different feeds can overwrite each other if published at the same timestamp.
- This will silently drop articles.

3. **Time handling is partially wrong**
- `time.mktime(parsed_time)` interprets the struct as local time, not UTC.
- `datetime.date.today()` uses the host local timezone, not the configured timezone.
- Output can be inconsistent if the machine timezone differs from `TIMEZONE`.

4. **No network robustness**
- No request timeout, retry policy, backoff, user-agent, or handling for transient failures.
- In production, some feeds will hang, rate-limit, or reject default clients.

5. **Config validation is missing**
- Assumes `feeds.json` has the correct shape.
- `target_category` lookup can crash with `KeyError`.
- Invalid URLs, missing fields, or malformed JSON are not reported cleanly.

6. **Filesystem behavior is fragile**
- Assumes `~/.rreader/` can be created with `os.mkdir` on a single level.
- Writes JSON directly without atomic replace.
- Concurrent runs can corrupt output or observe partial writes.

7. **Data model is too thin for production**
- Stores only a small subset of feed metadata.
- No summary/content, GUID, tags, image, feed title, language, or fetch status.
- No persistent history beyond overwriting the latest category snapshot.

8. **No observability**
- Logging is minimal and unstructured.
- No per-feed success/failure counts, latency, or diagnostics for skipped entries.

9. **No tests**
- Timezone logic, merge behavior, deduplication, and failure paths are unverified.

10. **Architecture is tightly coupled**
- Fetching, transformation, config migration, formatting, and persistence all live in one function.
- Harder to test, extend, or reuse.

**Plan.**

1. **Fix error handling**
- Replace bare `except:` with targeted exceptions: `FileNotFoundError`, `json.JSONDecodeError`, network/parser exceptions, `OSError`, `KeyError`.
- Return structured errors per feed instead of exiting the process.
- Make `do()` raise clear exceptions at the top level or accumulate errors and continue depending on mode.
- Add user-facing messages that identify category, feed URL, and failure reason.

2. **Fix entry identity and deduplication**
- Stop using timestamp alone as the entry ID.
- Prefer feed-provided stable identifiers in this order: `id`/`guid`, then `link`, then a hash of `(source, title, timestamp)`.
- Deduplicate on that stable key, not on second-level publish time.

3. **Correct timezone logic**
- Convert timestamps using UTC-aware APIs only.
- Replace `time.mktime(parsed_time)` with `calendar.timegm(parsed_time)` if the source tuple is UTC.
- Compare “today” using `datetime.datetime.now(TIMEZONE).date()` rather than host-local `date.today()`.
- Put all datetime formatting behind a helper so behavior is consistent and testable.

4. **Add network reliability**
- Fetch feeds through an HTTP client layer with timeout, retry, and custom `User-Agent`.
- If `feedparser` is kept, pass fetched content into it rather than relying on direct URL fetching.
- Mark failed feeds in output with status metadata so one bad feed does not block the rest.
- Consider conditional requests with `ETag` / `Last-Modified` for efficiency.

5. **Validate configuration**
- Add schema validation for the config file:
  - top-level categories must be objects
  - each category must contain `feeds`
  - `feeds` must map source names to non-empty URLs
  - `show_author` must be boolean if present
- Handle unknown `target_category` with a clear error message.
- On startup, validate bundled and user config before merge.

6. **Harden file writes**
- Replace `os.mkdir` with `os.makedirs(path, exist_ok=True)`.
- Write JSON to a temp file in the same directory, then `os.replace()` atomically.
- Ensure all file opens use explicit UTF-8.
- Optionally add file locking if concurrent execution is expected.

7. **Expand the stored record format**
- Add fields such as `guid`, `author`, `summary`, `content`, `feed_title`, `fetched_at`, and `fetch_status`.
- Separate raw ingestion fields from display fields; `pubDate` should be derived, not the only date representation.
- Preserve original publication timestamp in ISO 8601 alongside epoch seconds.

8. **Add observability**
- Replace ad hoc stdout writes with structured logging.
- Log category start/end, feed URL, entry count, duration, and error details.
- Include counters for feeds fetched, entries parsed, entries skipped, and entries written.

9. **Add tests**
- Unit tests for:
  - config migration
  - category lookup
  - timezone conversion
  - “today” formatting
  - deduplication rules
  - malformed feed entries
  - partial feed failures
- Integration tests using fixture RSS/Atom documents instead of live network calls.

10. **Refactor for maintainability**
- Split into modules/functions:
  - config loading and migration
  - feed fetch client
  - feed parsing and normalization
  - storage writer
  - presentation formatting
- Make dependencies injectable so tests can mock time, network, and filesystem.
- Add a small CLI layer for `all`, `category`, `verbose`, and `fail-fast` modes.

The main point: this is a functional prototype for personal use, but not yet a production feed ingestion service. The most urgent work is fixing failure handling, stable IDs, and timezone correctness, because those directly affect correctness and data loss.