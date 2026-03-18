**Observations**

This system is a small RSS fetcher and cache writer.

It currently does these things:

- Loads feed configuration from a user file at `~/.rreader/feeds.json`.
- If that file does not exist, copies a bundled `feeds.json` into place.
- If the user file exists, merges in any new categories found in the bundled file without overwriting existing user categories.
- Parses one category or all categories from the feed config.
- Fetches RSS/Atom feeds with `feedparser`.
- Extracts entries from each feed and normalizes a small record:
  - `id`
  - `sourceName`
  - `pubDate`
  - `timestamp`
  - `url`
  - `title`
- Converts published/updated timestamps from UTC into a configured local timezone.
- Formats dates differently for today vs older items.
- Deduplicates entries within a category by using the Unix timestamp as the key.
- Sorts entries newest-first.
- Writes per-category output to JSON files like `~/.rreader/rss_<category>.json`.
- Supports a `show_author` option per category.
- Supports a basic logging mode that prints feed URLs and completion status.
- Creates the base data directory `~/.rreader/` if missing.

**Triage**

Ranked by importance:

1. **Error handling is unsafe and too broad**
- Bare `except:` blocks hide real failures.
- A single bad feed can terminate the whole run.
- `sys.exit(" - Failed\n" if log else 0)` is inconsistent and can silently suppress errors.

2. **Data integrity and deduplication are weak**
- Using `timestamp` as the entry ID can collide across different feeds or multiple posts published in the same second.
- Collisions overwrite entries silently.

3. **Filesystem setup is incomplete**
- Directory creation only handles one level and uses `os.mkdir`.
- File writes are not atomic.
- Missing protection against partial/corrupt JSON writes.

4. **Configuration handling is fragile**
- Assumes bundled and user JSON are valid.
- Assumes requested `target_category` exists.
- No schema validation for feed config.

5. **Time handling is inconsistent**
- Compares converted entry date to `datetime.date.today()` in the system local timezone, not the configured `TIMEZONE`.
- Uses fixed UTC+9 instead of a DST-aware named timezone.
- Uses `time.mktime(parsed_time)` on a UTC-ish struct, which depends on host local time and can produce wrong timestamps.

6. **Networking behavior is not production-ready**
- No request timeout, retry, backoff, or per-feed failure isolation.
- No user agent configuration.
- No handling for transient network failures or malformed feeds beyond skipping/exiting.

7. **Output model is minimal**
- Drops useful fields like summary, GUID, categories, author metadata, feed title, and fetch status.
- No metadata about failures, counts, or source freshness.

8. **Logging and observability are minimal**
- Uses `sys.stdout.write` instead of structured logging.
- No error details, metrics, or per-feed diagnostics.

9. **Testing and maintainability gaps**
- No tests.
- Core logic is nested inside `do()`, making unit testing harder.
- Side effects are tightly coupled to parsing logic.

10. **CLI and operational usability are limited**
- No proper argument parsing.
- No exit codes that reflect partial failure vs full success.
- No scheduling/locking support to avoid overlapping runs.

**Plan**

1. **Fix error handling first**
- Replace bare `except:` with specific exceptions.
- Never call `sys.exit` from inside feed-processing helpers.
- Return structured per-feed results like `{status, error, entries}`.
- Continue processing other feeds if one feed fails.
- At the top level, aggregate failures and return a meaningful exit status.

2. **Make entry IDs stable and collision-resistant**
- Prefer feed entry GUID/`id` when available.
- Fall back to `link`.
- If needed, generate a hash from `source + link + published timestamp`.
- Keep timestamp as a sortable field, not the primary key.

3. **Harden filesystem operations**
- Use `os.makedirs(path, exist_ok=True)` for directory creation.
- Write JSON to a temp file and `os.replace()` it into place atomically.
- Validate that `p["path_data"]` exists before any read/write.
- Handle JSON decode failures on existing files and surface a clear error.

4. **Validate configuration**
- Check that `FEEDS_FILE_NAME` contains the expected shape:
  - category object
  - `feeds` mapping
  - optional `show_author`
- When `target_category` is provided, raise a clear error if missing.
- Separate “merge bundled categories” logic into its own function and test it.

5. **Correct time logic**
- Compute timestamps with `calendar.timegm(parsed_time)` or equivalent UTC-safe logic.
- Compare “today” in the configured timezone, not the host timezone.
- Replace fixed-offset timezone with `zoneinfo.ZoneInfo("Asia/Seoul")` or a configurable IANA timezone string.
- Store ISO 8601 timestamps in output in addition to display strings.

6. **Improve network robustness**
- Configure feed fetching with explicit timeouts.
- Add retry/backoff for temporary failures.
- Set a custom user agent.
- Capture parser bozo flags and HTTP status where available.
- Treat malformed feeds as recoverable errors and record them in output/logs.

7. **Enrich output schema**
- Include feed-level metadata:
  - source/feed name
  - fetch time
  - fetch status
  - error message if failed
  - entry count
- Include entry-level optional fields when present:
  - `guid`
  - `author`
  - `summary`
  - `tags`
- Define the JSON schema explicitly so downstream consumers can rely on it.

8. **Add real logging**
- Replace ad hoc stdout writes with the `logging` module.
- Support log levels.
- Log per feed:
  - start
  - success/failure
  - number of entries parsed
  - exception details
- Keep CLI output concise, but preserve detailed logs for debugging.

9. **Refactor for testability**
- Pull out pure functions:
  - config loading/merging
  - feed parsing
  - entry normalization
  - date formatting
  - output writing
- Add unit tests for:
  - config merge behavior
  - timezone conversion
  - deduplication
  - invalid/missing feed fields
  - partial feed failures
- Add fixture-based tests with sample RSS/Atom payloads.

10. **Add a proper CLI and operational behavior**
- Use `argparse` for options like:
  - category
  - log level
  - output dir
  - dry run
- Return explicit exit codes:
  - `0` success
  - nonzero for partial/full failure
- Optionally add lockfile support if this will run from cron/systemd.

If you want, I can turn this report into a concrete refactor checklist or draft the production-ready version of this module.