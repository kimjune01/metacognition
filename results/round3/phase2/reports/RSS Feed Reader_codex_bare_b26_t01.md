**Observations.**

This system is a local RSS ingester and cache writer.

Working capabilities:
- Loads a bundled `feeds.json` and copies it into the user data directory on first run.
- Merges newly added bundled categories into an existing user `feeds.json` without overwriting the user’s existing categories.
- Reads feed categories from `~/.rreader/feeds.json`.
- Fetches RSS/Atom feeds with `feedparser.parse(...)`.
- Iterates feed entries and extracts:
  - publication time from `published_parsed` or `updated_parsed`
  - link
  - title
  - source/author label
- Converts feed timestamps from UTC into a configured timezone (`UTC+9` in this code).
- Formats display dates as either `HH:MM` for same-day items or `Mon DD, HH:MM` otherwise.
- Deduplicates entries within a category by using the Unix timestamp as the entry ID.
- Sorts entries newest-first.
- Writes one cache file per category as `rss_<category>.json` under `~/.rreader/`.
- Supports:
  - full refresh of all categories
  - refresh of a single category via `do(target_category=...)`
  - optional logging of feed fetch progress

**Triage.**

Ranked by importance:

1. **Error handling is too weak and sometimes wrong**
- Broad bare `except:` blocks hide real failures.
- A single feed failure can terminate the whole process with `sys.exit(...)`.
- `sys.exit(" - Failed\n" if log else 0)` is inconsistent and hard to reason about.
- File I/O and JSON parsing have no recovery path.

2. **Deduplication and IDs are unreliable**
- Using only `timestamp` as the entry ID will collide when multiple entries share the same second.
- Distinct articles can overwrite each other silently.

3. **No network robustness**
- No request timeout, retry, backoff, or partial-failure handling policy.
- No validation of bad feeds, empty feeds, malformed entries, or transient outages.

4. **Timezone and date handling are incorrect for general use**
- `datetime.date.today()` uses local system date, not the configured `TIMEZONE`.
- `time.mktime(parsed_time)` interprets time in the host local timezone, which can produce wrong timestamps for UTC feed data.
- Timezone is hardcoded to Korea time.

5. **Data model is too thin for production**
- No content summary, GUID, categories/tags, feed title, or stable canonical entry metadata.
- No per-feed fetch metadata such as last success, last failure, or error details.
- Output JSON schema is implicit and undocumented.

6. **No input/config validation**
- Assumes `target_category` exists.
- Assumes `feeds.json` has the expected structure.
- Missing keys can raise exceptions.

7. **Storage behavior is not safe**
- Writes directly to destination files rather than atomically replacing them.
- Concurrent runs can corrupt output.
- No file locking.

8. **Logging and observability are minimal**
- Only prints URL progress when `log=True`.
- No structured logs, no warning/error levels, no metrics.

9. **No testability or separation of concerns**
- Business logic, filesystem setup, config, and CLI behavior are mixed together.
- Nested function makes reuse and unit testing harder.
- No tests.

10. **CLI/product surface is incomplete**
- No real command-line interface, help text, exit codes, or user-facing error messages.
- No scheduling, incremental updates, filtering, or output controls.

11. **Portability and maintainability issues**
- Creates directories with `os.mkdir` only one level deep.
- Uses global mutable paths/config.
- Hardcoded home-directory layout and filename conventions.

**Plan.**

1. **Fix error handling**
- Replace bare `except:` with targeted exceptions such as `OSError`, `json.JSONDecodeError`, and feed parsing/network exceptions.
- Do not exit on one failed feed; collect errors per source and continue processing other feeds.
- Return a result object like:
```python
{
  "entries": [...],
  "created_at": ...,
  "sources": {
    "source_name": {"status": "ok"|"error", "error": "...", "count": 12}
  }
}
```
- Use explicit exit codes only in the CLI layer.

2. **Use stable entry identifiers**
- Prefer feed-provided identifiers in order:
  - `feed.id`
  - `feed.guid`
  - normalized `feed.link`
  - fallback hash of `(source, title, published time, link)`
- Deduplicate on that stable ID instead of timestamp.
- Store timestamp separately as sortable metadata.

3. **Harden network fetching**
- Wrap feed fetches with retry logic and bounded timeouts.
- Distinguish malformed feed vs timeout vs HTTP failure.
- Continue processing remaining feeds even if one fails.
- Record per-feed error state in output or logs.

4. **Correct time handling**
- Convert parsed feed times using `calendar.timegm(parsed_time)` instead of `time.mktime(...)`.
- Compare “today” in the configured timezone, not the host timezone:
```python
now = datetime.datetime.now(TIMEZONE)
same_day = at.date() == now.date()
```
- Make timezone configurable via user config or environment variable instead of hardcoding UTC+9.

5. **Expand and formalize the data schema**
- Add fields like:
  - `entry_id`
  - `feed_name`
  - `author`
  - `summary`
  - `published_at`
  - `updated_at`
  - `tags`
  - `fetched_at`
- Define the output schema in code comments or docs so downstream consumers can rely on it.

6. **Validate config and inputs**
- Validate `FEEDS_FILE_NAME` contents on load.
- Check that each category has a `feeds` mapping.
- Handle unknown `target_category` with a clear error.
- Consider schema validation for `feeds.json`.

7. **Make writes atomic and safe**
- Write JSON to a temp file in the same directory, then `os.replace(...)`.
- Ensure the data directory exists with `os.makedirs(path, exist_ok=True)`.
- If concurrent execution matters, add file locking around writes.

8. **Improve logging**
- Replace `sys.stdout.write` with `logging`.
- Emit feed/category/source context in messages.
- Log counts, durations, and failures.
- Keep human-readable CLI logs and optional structured logs separate.

9. **Refactor for testability**
- Split into functions/modules:
  - config loading
  - feed definition loading/merging
  - single-feed fetch
  - entry normalization
  - category aggregation
  - cache writing
- Move side effects out of import time; directory creation should happen in startup code, not module import.
- Add unit tests for:
  - timestamp conversion
  - deduplication
  - config merge behavior
  - malformed feeds
  - missing fields

10. **Add a proper CLI**
- Use `argparse` or `typer`.
- Support flags like:
  - `--category`
  - `--log-level`
  - `--output-dir`
  - `--timezone`
  - `--dry-run`
- Return meaningful exit codes:
  - `0` success
  - nonzero for partial/full failure depending on policy

11. **Improve portability**
- Use `pathlib.Path` consistently.
- Avoid hardcoded path concatenation with `+`.
- Support XDG/appdirs-style data locations where appropriate.
- Make default paths overridable.

If you want, I can turn this report into a production-readiness checklist or a concrete refactor roadmap by module/function.