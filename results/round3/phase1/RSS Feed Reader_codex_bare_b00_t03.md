**Observations.**

This system is a small RSS fetcher/cache writer.

It currently does these things correctly:

- Loads a bundled `feeds.json` and copies it into the user data directory on first run.
- Merges in any new top-level categories from the bundled feed list into the user’s existing `feeds.json`.
- Reads feed definitions by category and source URL.
- Fetches RSS/Atom feeds with `feedparser.parse(...)`.
- Extracts entries from each feed and normalizes a small record:
  - `id`
  - `sourceName`
  - `pubDate`
  - `timestamp`
  - `url`
  - `title`
- Uses either `published_parsed` or `updated_parsed` when available.
- Converts entry timestamps from UTC into the configured timezone.
- Formats dates differently for “today” vs older entries.
- Sorts entries newest-first.
- Deduplicates implicitly by using the Unix timestamp as the dictionary key.
- Writes per-category output files like `rss_<category>.json` into `~/.rreader/`.
- Can fetch one category or all categories.
- Has optional logging that prints feed URLs and completion status.
- Ensures the `~/.rreader/` directory exists before use.

**Triage.**

Ranked by importance:

1. **Error handling is unsafe and opaque**
- Bare `except:` blocks hide real failures.
- One feed failure can terminate the whole process with `sys.exit(...)`.
- Logging/error behavior is inconsistent and not machine-usable.

2. **Data integrity and deduplication are weak**
- Using `timestamp` as the unique `id` will collide when multiple articles share the same second.
- Articles without `published_parsed`/`updated_parsed` are silently dropped.
- No validation for missing `link`, `title`, malformed feeds, or bad category config.

3. **Filesystem robustness is incomplete**
- Directory creation uses `os.mkdir`, which fails for missing parent chains and is not resilient.
- Writes are not atomic, so partial/corrupt JSON is possible on interruption.
- No file locking or concurrency protection.

4. **Timezone/date logic is incorrect in edge cases**
- “Today” is checked against `datetime.date.today()` in local system time, not the configured timezone.
- `time.mktime(parsed_time)` interprets time as local time, which can skew timestamps if feed times are UTC structs.
- Hardcoded KST in config is inflexible for real deployments.

5. **Configuration and portability are limited**
- Paths are hardcoded under `~/.rreader/`.
- No env/config override for data directory, timezone, feed file path, request timeout, or user agent.
- The bundled/user feed merge only adds new categories, not new feeds within existing categories.

6. **Networking behavior is too minimal for production**
- No request timeout, retry, backoff, caching headers, or rate limiting.
- No custom user agent.
- No observability around slow feeds, bad responses, or parse quality.

7. **Output contract is underspecified**
- No schema/versioning for output JSON.
- No retention policy, pagination, or entry limits.
- No stable ordering guarantees beyond timestamp sort.

8. **Code structure/testability are limited**
- Business logic, IO, config, and CLI behavior are tightly coupled.
- Nested function structure makes testing harder.
- No tests for parsing, merging, formatting, or failure cases.

9. **CLI/product surface is incomplete**
- No proper command-line interface, help text, exit codes, or selective options.
- No dry-run mode, force refresh, or feed/category validation tools.

**Plan.**

1. **Fix error handling first**
- Replace bare `except:` with targeted exceptions.
- Stop calling `sys.exit(...)` inside feed-processing logic.
- Return structured per-feed errors such as `{source, url, error_type, message}`.
- Continue processing other feeds when one fails.
- Add logging through `logging` instead of `sys.stdout.write`.
- Define clear exit behavior at the CLI layer only.

2. **Make entry IDs and validation reliable**
- Use a stable unique ID per entry:
  - Prefer feed-provided `id`
  - Else hash `(source, link, title, published timestamp)`
- Validate required fields before writing.
- If time fields are missing, either:
  - keep the item with `timestamp=None`, or
  - fall back to another known date field
- Log dropped items with reasons.
- Add config/category validation before fetch begins.

3. **Harden file operations**
- Replace `os.mkdir` with `os.makedirs(path, exist_ok=True)`.
- Write JSON to a temporary file and atomically rename it into place.
- Create directories before every write path, not just startup.
- If concurrent runs are possible, add file locking around writes.

4. **Correct time handling**
- Convert parsed feed times with `calendar.timegm(parsed_time)` instead of `time.mktime(...)`.
- Compare “today” using the configured timezone:
  - `now = datetime.datetime.now(TIMEZONE).date()`
- Make timezone configurable from env or config file.
- Store canonical timestamps in UTC and format display dates separately.

5. **Improve configuration management**
- Move hardcoded settings into a config layer:
  - data directory
  - timezone
  - bundled feed path
  - user feed path
  - request timeout
  - retries
  - user agent
- Support env vars and/or a config file.
- Enhance feed merging to also add missing feeds inside existing categories, not just new categories.

6. **Add production-grade fetch behavior**
- Use a fetch layer with timeout and retry policy.
- Set a descriptive user agent.
- Capture fetch metrics:
  - success/failure
  - duration
  - entries parsed
- Optionally support ETag/Last-Modified if the fetch library permits.
- Distinguish network failure from parse failure in logs and results.

7. **Define the output schema**
- Version the JSON payload, e.g. `{"schema_version": 1, ...}`.
- Document field meanings and nullability.
- Consider adding:
  - `category`
  - `source`
  - canonical `published_at`
  - `fetched_at`
  - raw feed `id`
- Decide and document dedupe policy and max entry count per category.

8. **Refactor for maintainability**
- Split into modules:
  - config
  - feed loading/merge
  - fetch/parse
  - normalization
  - storage
  - CLI
- Pull `get_feed_from_rss` out of `do(...)`.
- Make pure functions for normalization and date formatting so they can be unit tested.

9. **Add tests and a real CLI**
- Add unit tests for:
  - feed merge behavior
  - timestamp conversion
  - “today” formatting
  - entry normalization
  - dedupe behavior
  - failure handling
- Add integration tests with sample RSS/Atom payloads.
- Add CLI args like:
  - `--category`
  - `--log-level`
  - `--dry-run`
  - `--config`
  - `--output-dir`

The highest-value immediate sequence is: error handling, ID/timestamp correctness, atomic writes, then config/network hardening. Those changes move it from “works locally” toward “safe to run unattended.”