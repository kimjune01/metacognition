**Observations**

This system is a small RSS fetcher and cache writer.

It currently does the following:

- Loads a bundled `feeds.json` from the package directory and ensures a user-level feeds file exists at `~/.rreader/feeds.json`.
- Merges any new categories from the bundled feeds file into the user feeds file without overwriting existing user categories.
- Reads feed definitions by category from `feeds.json`.
- Fetches RSS/Atom feeds with `feedparser.parse(url)`.
- Iterates feed entries and extracts:
  - publication time from `published_parsed` or `updated_parsed`
  - link
  - title
  - author, optionally
- Converts entry timestamps from UTC into a configured local timezone (`UTC+9` in this code).
- Formats publication time differently for today vs older entries.
- Builds a normalized JSON payload per category:
  - `entries`
  - `created_at`
- Writes category cache files to `~/.rreader/rss_<category>.json`.
- Supports:
  - fetching one category via `do(target_category=...)`
  - fetching all categories via `do()`
  - optional console logging of feed URLs as they are fetched

Working capability summary:

- Local config/bootstrap
- Feed ingestion
- Basic timestamp normalization
- Basic deduplication by timestamp key
- Per-category JSON output cache
- Simple CLI entrypoint

**Triage**

Ranked by importance:

1. **Error handling is unsafe and incomplete**
- Broad bare `except:` blocks hide real failures.
- A single failure can terminate the whole run with `sys.exit`.
- Feed parsing, file I/O, malformed config, and directory creation are not handled robustly.

2. **Deduplication and IDs are incorrect**
- Entries are keyed only by Unix timestamp.
- Multiple posts published in the same second will overwrite each other.
- IDs are not stable across feeds unless timestamps differ.

3. **Filesystem setup is fragile**
- `os.mkdir` only creates one directory level.
- No handling for missing parent directories, permission errors, or concurrent creation.
- Writes are non-atomic and can leave partial JSON files.

4. **Timezone and “today” handling are wrong/inconsistent**
- `datetime.date.today()` uses the host local timezone, not `TIMEZONE`.
- `time.mktime(parsed_time)` interprets time as local system time, not UTC.
- This can produce incorrect timestamps and wrong “today” formatting.

5. **No validation of feed config structure**
- Assumes categories and feed definitions always exist and have the expected shape.
- `target_category` can raise `KeyError`.
- No schema validation for `feeds.json`.

6. **No network resilience or fetch controls**
- No timeouts, retries, backoff, rate limiting, or user agent.
- `feedparser.parse(url)` is used as a black box with no HTTP status handling.
- Production ingestion needs better control over remote failures.

7. **No observability**
- Logging is minimal and not structured.
- No metrics, per-feed status, error counts, or fetch summaries.
- Hard to debug silent skips and partial failures.

8. **Data model is too thin for production use**
- Only stores title, link, source, time.
- No content summary, GUID, categories/tags, feed metadata, status, or error info.
- No distinction between newly fetched and previously seen items.

9. **No tests**
- No unit tests for time conversion, merge logic, parsing behavior, or failure cases.
- No integration tests with sample feeds.

10. **Hard-coded configuration limits reuse**
- Timezone is fixed to KST in code.
- Data path is fixed to `~/.rreader/`.
- No CLI/config/env-based overrides.

11. **Scalability and performance are limited**
- Feeds are fetched serially.
- No conditional requests, caching headers, or concurrency.
- Fine for small personal use, weak for larger feed sets.

12. **Security and input trust assumptions are loose**
- Accepts arbitrary URLs from config.
- No restrictions or sanitization.
- Could matter in a multi-user or hosted deployment.

**Plan**

1. **Fix error handling**
- Replace bare `except:` with targeted exceptions.
- Do not `sys.exit` from inside feed-processing logic.
- Return per-feed success/error results instead of aborting the whole run.
- Add explicit handling for:
  - JSON decode errors
  - missing files
  - permission issues
  - malformed feed entries
  - network/parser failures

2. **Use stable entry identifiers**
- Prefer feed-provided stable identifiers in this order:
  - `id`
  - `guid`
  - `link`
  - hash of `(source, title, published, link)`
- Deduplicate on that stable ID, not timestamp.
- Keep timestamp as a sortable field, not a primary key.

3. **Make file operations robust**
- Create directories with `os.makedirs(path, exist_ok=True)`.
- Write JSON to a temp file and `os.replace()` it into place atomically.
- Handle write failures and preserve last good cache when a write fails.

4. **Correct time handling**
- Replace `time.mktime(parsed_time)` with `calendar.timegm(parsed_time)` for UTC-based tuples.
- Compute “today” in the configured timezone:
  - `now = datetime.datetime.now(TIMEZONE).date()`
- Centralize timestamp parsing in one helper so formatting and numeric timestamps stay consistent.

5. **Validate configuration**
- Add validation when loading `feeds.json`:
  - category exists
  - each category has `feeds`
  - `feeds` is a dict of source -> URL
  - optional `show_author` is boolean
- Raise clear application errors for invalid config.
- Handle unknown `target_category` with a user-facing error or empty result.

6. **Improve network fetching**
- Use a proper HTTP client layer before parsing, or inspect `feedparser` response metadata.
- Add:
  - request timeout
  - retry with backoff
  - user-agent header
  - HTTP status validation
- Preserve feed-level errors in output/logs instead of silently skipping.

7. **Add observability**
- Replace `sys.stdout.write` with `logging`.
- Log feed URL, category, status, item count, and exception details.
- Return or persist a summary object:
  - feeds attempted
  - feeds succeeded
  - feeds failed
  - entries parsed
  - entries skipped

8. **Expand the output schema**
- Add fields such as:
  - `entry_id`
  - `feed_source`
  - `author`
  - `summary`
  - `published_at`
  - `fetched_at`
  - `raw_guid`
- Consider storing feed-level metadata and fetch status alongside `entries`.

9. **Add tests**
- Unit tests for:
  - directory/bootstrap behavior
  - bundled/user feed merge logic
  - timestamp conversion
  - “today” formatting in configured timezone
  - deduplication rules
- Integration tests using saved feed fixtures, not live network calls.

10. **Externalize configuration**
- Make timezone configurable via env var, config file, or CLI option.
- Make data directory configurable.
- Allow optional output path override and category filtering from the command line.

11. **Improve throughput**
- Fetch feeds concurrently with a bounded worker pool.
- Sort entries after aggregation as today, but parallelize network work.
- Optionally support incremental fetch based on ETag/Last-Modified if the HTTP layer supports it.

12. **Define operational boundaries**
- If this is meant for local desktop use, document that clearly.
- If it is meant for production/server use, add:
  - dependency pinning
  - packaging
  - structured exit codes
  - health/error reporting
  - deployment-safe config handling

The shortest path to “production-ready enough” is: fix error handling, fix timestamp logic, replace timestamp-based IDs, validate config, and make writes atomic. Those five changes address the biggest correctness and reliability risks first.