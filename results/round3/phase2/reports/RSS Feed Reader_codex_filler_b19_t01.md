**Observations**

This script is a small RSS ingestion job with local persistence.

It currently does these things correctly:

- Loads feed definitions from a bundled `feeds.json` and ensures a user-level copy exists at `~/.rreader/feeds.json`.
- Merges in new categories from the bundled feed config into the user config without overwriting existing user-defined categories.
- Fetches RSS/Atom feeds with `feedparser.parse(url)`.
- Iterates feed entries and extracts publication time from `published_parsed` or `updated_parsed`.
- Converts feed timestamps from UTC into a configured timezone (`UTC+9` in the current code).
- Formats display timestamps as either `HH:MM` for same-day items or `Mon DD, HH:MM` for older items.
- Builds normalized entry objects with:
  - `id`
  - `sourceName`
  - `pubDate`
  - `timestamp`
  - `url`
  - `title`
- Supports a `show_author` option per category, falling back to the feed source name if the entry has no author.
- Sorts entries newest-first.
- Writes one JSON cache file per category to `~/.rreader/rss_<category>.json`.
- Supports either:
  - updating one category via `do(target_category=...)`
  - updating all categories via `do()`
- Provides optional progress logging for each feed URL.

In short: it is a functional local RSS fetcher/cache generator for predefined categories.

**Triage**

Ranked by importance:

1. **Error handling is unsafe and opaque**
- Broad bare `except:` blocks hide failures.
- A single feed failure can terminate the whole process with `sys.exit`.
- Failures are not structured, logged meaningfully, or recoverable.

2. **Data model is lossy and deduplication is incorrect**
- Entries are keyed only by Unix timestamp.
- Multiple articles published in the same second will overwrite each other.
- Important feed metadata is discarded.
- No stable unique identity is preserved across runs.

3. **Configuration and timezone handling are not production-ready**
- Timezone is hardcoded to Korea Standard Time.
- Paths and config are implicit and not injectable.
- No validation exists for malformed or missing config structure.

4. **Filesystem behavior is fragile**
- Directory creation uses `os.mkdir` only for one level and is not robust.
- Writes are not atomic.
- No handling exists for partial writes, permissions issues, or concurrent runs.

5. **No network robustness**
- No timeout, retry, backoff, or user-agent control.
- `feedparser.parse(url)` is used directly with little visibility into HTTP status, redirects, or invalid feeds.
- No caching headers or conditional fetch support.

6. **No schema/versioning for persisted output**
- Output JSON structure is informal and unversioned.
- Future changes could silently break consumers.

7. **No observability**
- Logging is minimal and only prints URLs.
- No counts, durations, per-feed errors, skipped-entry counts, or summary metrics.

8. **No tests**
- Core behavior around timestamp parsing, config merge, output generation, and failure handling is unverified.

9. **CLI and API surface are minimal**
- No command-line options for category selection, dry-run, output path, verbosity, or validation.
- `do()` mixes orchestration, I/O, transformation, and side effects.

10. **Code structure is too monolithic for growth**
- Nested function plus heavy reliance on globals makes extension harder.
- Inlined `common.py` and `config.py` indicate packaging/dependency boundaries are not clean.

**Plan**

1. **Fix error handling first**
- Replace bare `except:` with specific exceptions.
- Never `sys.exit` from deep inside feed processing; return structured errors instead.
- Process feeds independently so one bad feed does not abort the category.
- Capture per-feed result objects such as `{source, url, status, error, entry_count}`.
- Log parse failures, bad timestamps, file write failures, and config errors separately.

2. **Redesign entry identity and deduplication**
- Stop using `timestamp` as the dictionary key.
- Prefer feed-provided stable IDs in this order: `entry.id`, `guid`, `link`, then a hash of `(source, title, published, link)`.
- Preserve timestamp as a sortable field only.
- Deduplicate by stable entry ID, not publish second.
- Store more raw metadata where available: `author`, `summary`, `tags`, `published`, `updated`.

3. **Make configuration explicit and validated**
- Move timezone, data directory, and feeds file path into a validated config object.
- Support standard IANA timezone names instead of a fixed UTC offset.
- Validate `feeds.json` shape:
  - category exists
  - `feeds` is a dict
  - URLs are strings
  - `show_author` is boolean if present
- Fail with actionable messages when config is invalid.

4. **Harden filesystem writes**
- Use `Path(...).mkdir(parents=True, exist_ok=True)`.
- Write JSON to a temp file and atomically replace the target file.
- Handle and report permission errors.
- Consider a file lock if concurrent runs are possible.
- Ensure JSON output always ends in a fully valid file, even on interruption.

5. **Improve fetch reliability**
- Add explicit HTTP fetching with timeout, retry, and backoff, then pass content to `feedparser`.
- Set a user-agent.
- Record HTTP status and feed bozo/parse warnings.
- Support conditional requests with `ETag` and `Last-Modified` to reduce bandwidth and avoid unnecessary parsing.
- Decide whether invalid feeds should be skipped, quarantined, or retried.

6. **Version the output format**
- Add a top-level schema version, for example:
  - `schema_version`
  - `created_at`
  - `category`
  - `entries`
  - `errors`
- Keep backward compatibility rules documented.

7. **Add meaningful logging and metrics**
- Replace `sys.stdout.write` with `logging`.
- Emit structured information:
  - feed start/end
  - fetch duration
  - entries parsed
  - entries skipped
  - errors by type
- Add a final per-run summary.

8. **Add tests around core behavior**
- Unit tests:
  - config bootstrap and merge behavior
  - timestamp conversion and formatting
  - author fallback logic
  - deduplication rules
  - JSON output shape
- Failure-path tests:
  - invalid feed
  - missing timestamp
  - malformed config
  - write failure
- Integration tests with sample RSS/Atom fixtures.

9. **Separate orchestration from transformation**
- Break code into functions/classes such as:
  - `load_config()`
  - `merge_bundled_feeds()`
  - `fetch_feed()`
  - `normalize_entry()`
  - `write_category_cache()`
- Keep `do()` as a thin coordinator.

10. **Add a real CLI**
- Support flags like:
  - `--category <name>`
  - `--all`
  - `--log-level`
  - `--data-dir`
  - `--timezone`
  - `--dry-run`
  - `--validate-config`
- Return meaningful exit codes for automation.

If you want, I can turn this into a stricter engineering review format with severity labels and proposed milestones.