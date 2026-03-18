**Observations.**

This system is a small RSS fetcher/cache writer.

It currently does these things correctly:

- Loads a bundled `feeds.json` from the package directory and copies it to the user data directory on first run.
- Merges newly added bundled categories into an existing user `feeds.json` without overwriting user-defined categories.
- Reads feed definitions from `~/.rreader/feeds.json`.
- Fetches RSS/Atom feeds with `feedparser.parse(url)`.
- Iterates feed entries and extracts publication time from `published_parsed` or `updated_parsed`.
- Converts timestamps from UTC into a configured fixed timezone (`UTC+9`).
- Formats display timestamps differently for “today” vs older items.
- Builds normalized entry records with:
  - `id`
  - `sourceName`
  - `pubDate`
  - `timestamp`
  - `url`
  - `title`
- Optionally uses the entry author instead of the source name when `show_author=True`.
- Deduplicates entries implicitly by using the Unix timestamp as the dictionary key.
- Sorts entries newest-first.
- Writes one JSON cache file per category to `~/.rreader/rss_<category>.json`.
- Supports fetching either:
  - one target category, returning that category’s result, or
  - all categories, writing each cache file.
- Creates the data directory `~/.rreader/` if it does not exist.

**Triage.**

Ranked by importance:

1. **Data integrity and deduplication are unreliable**
- Entries are keyed only by second-level timestamp.
- Different articles published in the same second will overwrite each other.
- A stable feed item ID is not used.

2. **Error handling is too weak for production**
- Broad bare `except:` blocks hide failures.
- One failure path calls `sys.exit`, which is inappropriate for library-style code.
- There is no structured error reporting per feed or per category.

3. **Timezone and date handling are incorrect or brittle**
- “Today” is compared against `datetime.date.today()` in the local system timezone, not the configured `TIMEZONE`.
- `time.mktime(parsed_time)` interprets the tuple in local system time, which can shift timestamps incorrectly.
- `TIMEZONE` is a fixed offset, not a real zone with DST rules.

4. **No network robustness**
- No request timeout, retry policy, or backoff.
- No handling for transient failures, malformed feeds, or slow endpoints.
- `feedparser.parse(url)` directly against remote URLs gives little control.

5. **No validation of feed configuration**
- Assumes category exists and has the expected shape.
- Missing keys or malformed `feeds.json` will raise unhelpful exceptions.

6. **Writes are not atomic or concurrency-safe**
- JSON files are written directly.
- Interrupted writes can corrupt cache files.
- Concurrent runs can race on the same files.

7. **No observability**
- Logging is just optional `stdout` text.
- No structured logs, no counts, no error summaries, no metrics.

8. **Output model is too minimal for a real reader**
- No content summary, no feed title, no GUID, no tags, no read state, no per-source metadata.
- No pagination, retention, or archive behavior.

9. **No tests**
- Time conversion, merging behavior, error handling, and deduplication are all unverified.

10. **Code structure is not production-grade**
- Nested function with mixed responsibilities.
- Hardcoded paths and side effects at import time.
- Limited separation between config, IO, parsing, normalization, and persistence.

**Plan.**

1. **Fix entry identity and deduplication**
- Stop using `timestamp` alone as the primary key.
- Build a stable ID from feed fields in priority order: `id`/`guid`, else `link`, else a hash of `(source, title, published time)`.
- Keep `timestamp` as sortable metadata, not as identity.
- Preserve multiple entries that share a publication second.

2. **Replace broad exception handling with explicit failures**
- Catch specific exceptions around:
  - config file IO
  - JSON decode
  - network fetch
  - feed parse anomalies
  - timestamp parsing
- Return structured results like:
  - successful entries
  - skipped entries
  - feed-level errors
- Remove `sys.exit()` from internal logic; raise exceptions or collect errors instead.
- Define whether one bad feed should fail the category or just be reported.

3. **Correct time handling**
- Use timezone-aware “now” in the configured zone:
  - compare against `datetime.datetime.now(TIMEZONE).date()`
- Replace `time.mktime(parsed_time)` with UTC-safe conversion:
  - `calendar.timegm(parsed_time)`
- Store timestamps consistently as UTC epoch seconds.
- Prefer `zoneinfo.ZoneInfo("Asia/Seoul")` over a fixed offset if the app is meant to represent a real locality.

4. **Add controlled fetching**
- Fetch URLs with `requests` or similar first, using explicit:
  - timeout
  - retry/backoff
  - user agent
  - status handling
- Pass response content to `feedparser.parse(...)`.
- Record feed fetch status and parse warnings.
- Optionally support conditional requests with `ETag` and `Last-Modified`.

5. **Validate configuration**
- Validate `feeds.json` schema before use.
- Check that each category contains a `feeds` mapping and optional supported flags like `show_author`.
- Handle unknown `target_category` with a clear exception or user-facing message.
- Reject malformed feed URLs early.

6. **Make file writes safe**
- Write JSON to a temp file in the same directory, then atomically rename.
- Ensure the data directory exists with `os.makedirs(..., exist_ok=True)`.
- Consider file locking if concurrent execution is expected.

7. **Improve logging and diagnostics**
- Replace raw `stdout.write` with the `logging` module.
- Log at feed and category granularity:
  - start/end
  - number of entries fetched
  - number skipped
  - error details
- Return a summary object from `do()` so callers can inspect outcomes programmatically.

8. **Expand the stored data model**
- Include additional normalized fields when available:
  - `guid`
  - `feedTitle`
  - `summary`
  - `author`
  - `categories/tags`
- Decide on a schema version and include it in output JSON.
- Define retention rules if cache files will grow over time.

9. **Add tests**
- Unit tests for:
  - bundled/user feed merge behavior
  - timestamp conversion
  - “today” formatting
  - duplicate timestamps
  - missing `published_parsed`
  - malformed config
- Integration tests using local sample feed files instead of live network calls.

10. **Refactor into clearer modules**
- Split responsibilities into functions/modules such as:
  - config loading
  - feed fetching
  - entry normalization
  - persistence
  - reporting
- Remove side effects from import time where possible.
- Make `do()` orchestration-only, with small testable helpers underneath.

If useful, I can turn this into a stricter engineering review format with severity labels and proposed code-level refactors.