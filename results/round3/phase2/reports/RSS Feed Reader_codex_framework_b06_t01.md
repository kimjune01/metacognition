**Observations**

This system is a small RSS ingester with local persistence.

It currently does these things:

- Loads a bundled `feeds.json` and ensures a user-level feeds file exists at `~/.rreader/feeds.json`.
- Merges new categories from the bundled feeds file into the user feeds file without overwriting existing user categories.
- Reads one category or all categories from the feeds config.
- Fetches RSS/Atom feeds with `feedparser.parse(url)`.
- Extracts entries using `published_parsed` or `updated_parsed`.
- Converts timestamps into a configured timezone.
- Formats display dates as `HH:MM` for today, otherwise `Mon DD, HH:MM`.
- Emits a normalized JSON file per category at `~/.rreader/rss_<category>.json`.
- Sorts entries newest-first.
- Optionally uses feed author instead of source name when `show_author` is enabled.
- Supports a minimal log mode that prints feed URLs as they are fetched.

What it does not currently do is as important as what it does: this is a basic batch fetcher, not yet a reliable sync service.

**Triage**

Ranked by importance:

1. **Error handling is unsafe and opaque**
- Bare `except:` blocks hide real failures.
- One failed fetch can terminate the whole process via `sys.exit(...)`.
- Logging and exit behavior are inconsistent and in one path incorrect (`sys.exit(" - Failed\n" if log else 0)`).

2. **Deduplication is broken**
- Entry IDs are just `int(time.mktime(parsed_time))`.
- Multiple items published in the same second will collide.
- Collisions overwrite earlier entries in `rslt`, silently losing data.

3. **Filesystem initialization is fragile**
- `os.mkdir` only creates one level and assumes the parent exists.
- No recovery if `~/.rreader/` cannot be created or written.
- Writes are not atomic, so interrupted writes can corrupt JSON files.

4. **Configuration validation is missing**
- Assumes `feeds.json` exists, is valid JSON, and has the expected shape.
- Assumes `target_category` exists in `RSS`.
- Assumes each category has a `"feeds"` mapping.

5. **Feed parsing and network behavior are too naive for production**
- No request timeout control, retries, backoff, headers, conditional fetch, or rate limiting.
- No tracking of feed-level failures or partial success.
- No distinction between malformed feeds, network errors, and empty feeds.

6. **Time handling is incomplete**
- `time.mktime(parsed_time)` uses local machine time semantics, while display uses `TIMEZONE`.
- `"today"` is checked against `datetime.date.today()`, not the configured timezone’s current date.
- The default timezone is hardcoded to KST in the inlined config, which is not portable.

7. **Data model is too thin**
- Stores only a few fields: `id`, `sourceName`, `pubDate`, `timestamp`, `url`, `title`.
- No content summary, guid, feed source, categories/tags, read state, fetch status, or stable canonical identifier.
- JSON output is overwritten each run; there is no historical state or incremental sync model.

8. **API and structure need cleanup**
- Nested function design makes testing harder.
- Side effects happen at import time (`os.mkdir(...)`).
- Function names are vague (`do`).
- No types, docstrings, or explicit interfaces.

9. **Observability is minimal**
- No structured logs, metrics, or per-feed diagnostics.
- No way to know how many feeds succeeded, failed, or produced zero entries.

10. **No tests**
- Timezone logic, merge behavior, deduplication, and file-writing behavior are all untested.

**Plan**

1. **Fix error handling first**
- Replace bare `except:` with specific exceptions.
- Never call `sys.exit` inside feed-processing helpers.
- Return structured results per feed: success, error type, message, entry count.
- Accumulate failures and continue processing other feeds.
- Emit a final summary with counts of succeeded/failed feeds.

2. **Introduce stable entry IDs**
- Use feed-provided identifiers in priority order: `entry.id`, `guid`, `link`, then a hash of `(source, title, published timestamp)`.
- Deduplicate on that stable key instead of publication second.
- Keep `timestamp` as a sortable field, not as identity.

3. **Harden storage**
- Replace `os.mkdir` with `Path(...).mkdir(parents=True, exist_ok=True)`.
- Validate write permissions up front.
- Write JSON atomically: write to temp file, then `os.replace`.
- Handle JSON decode failures for both bundled and user config with actionable errors.

4. **Validate config explicitly**
- Add a config loader that checks:
  - top-level object shape
  - category existence
  - `"feeds"` is a dict of source name to URL
  - optional booleans like `show_author`
- Raise clear exceptions for invalid categories and malformed config.
- Separate bundled config merge logic from fetch logic.

5. **Make fetching production-safe**
- Use an HTTP client with explicit timeout and retry/backoff behavior.
- Send a descriptive user-agent.
- Persist `ETag` and `Last-Modified` per feed and use conditional requests.
- Track consecutive failures and last successful fetch time.
- Limit concurrency carefully if multiple feeds are fetched in parallel.

6. **Correct time semantics**
- Use timezone-aware UTC internally for all timestamps.
- Replace `time.mktime(parsed_time)` with a UTC-safe conversion.
- Compare “today” using the configured timezone’s current date, not system local date.
- Move timezone config to user config or environment, and default sanely.

7. **Expand the data model**
- Preserve feed metadata and entry metadata:
  - `feed_source`
  - `author`
  - `summary`
  - `guid`
  - `published_at`
  - `fetched_at`
  - `tags`
- Separate raw normalized entries from presentation fields like `pubDate`.
- Keep display formatting out of the stored canonical record if possible.

8. **Refactor into testable units**
- Split into:
  - `load_config()`
  - `merge_bundled_config()`
  - `fetch_feed(url, ...)`
  - `normalize_entry(...)`
  - `write_category_output(...)`
- Rename `do()` to something explicit like `sync_feeds`.
- Remove import-time side effects.

9. **Add observability**
- Replace ad hoc `stdout.write` with `logging`.
- Log per-feed start/end/error, duration, and entry count.
- Return a machine-readable summary for CLI and automation.

10. **Add tests before further expansion**
- Unit tests for:
  - config merge behavior
  - invalid config handling
  - stable deduplication
  - timezone formatting
  - today-vs-not-today logic
  - atomic write path
- Integration tests with mocked feeds for success, malformed timestamps, duplicates, and network failures.

If you want, I can turn this into a production-readiness checklist or rewrite it as a concrete implementation plan with modules, function signatures, and test cases.