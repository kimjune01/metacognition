**Observations**

This system is a small RSS fetcher and cache writer.

It currently does these things:

- Loads feed definitions from a bundled `feeds.json` and a user-level `~/.rreader/feeds.json`.
- Bootstraps the user feed config by copying the bundled file if the user file does not exist.
- Merges in new categories from the bundled config into the user config without overwriting existing user categories.
- Fetches RSS/Atom feeds with `feedparser.parse(url)`.
- Iterates feed entries and extracts publish time from `published_parsed` or `updated_parsed`.
- Converts entry timestamps from UTC into a fixed configured timezone (`UTC+9`).
- Formats display dates as either `HH:MM` for same-day items or `Mon DD, HH:MM` otherwise.
- Builds a normalized entry shape with:
  - `id`
  - `sourceName`
  - `pubDate`
  - `timestamp`
  - `url`
  - `title`
- Optionally uses the entry author instead of the source name when `show_author=True`.
- Deduplicates entries only by integer timestamp key within a category fetch.
- Sorts entries newest-first.
- Writes per-category cache files to `~/.rreader/rss_<category>.json`.
- Supports fetching a single category or all categories through `do(target_category=None, log=False)`.
- Creates the data directory `~/.rreader/` on startup if it does not exist.
- Can be run as a script via `python <file>`.

**Triage**

Highest priority gaps first:

1. **Error handling is brittle and in some cases wrong**
- Broad bare `except:` blocks hide failures.
- `sys.exit(" - Failed\n" if log else 0)` mixes error reporting and process exit in a way that can silently mask problems.
- A single bad feed can terminate the whole run.
- File IO and JSON parsing are not protected.

2. **Data integrity and deduplication are weak**
- Entries are keyed only by Unix timestamp.
- Multiple posts with the same second will overwrite each other.
- Different feeds can collide.
- The stored data lacks stable unique identifiers such as GUID/feed ID.

3. **Timezone and date handling are not production-safe**
- “Today” is checked with `datetime.date.today()` in the local system timezone, not the configured timezone.
- The configured timezone is hardcoded to UTC+9.
- DST-aware regional timezone support is missing.

4. **No validation of configuration or input shape**
- Assumes `feeds.json` exists, is valid JSON, and has the expected schema.
- Assumes requested `target_category` exists.
- Assumes each category has a `feeds` mapping.

5. **No network controls or fetch resilience**
- No request timeout, retry, backoff, or circuit breaking.
- No user agent configuration.
- No conditional fetch support such as ETag or Last-Modified handling.
- No handling for slow, malformed, or intermittently unavailable sources.

6. **Output writing is not atomic**
- Cache files are written directly.
- Partial writes can corrupt output if the process is interrupted.

7. **Logging and observability are minimal**
- Uses `sys.stdout.write` instead of structured logging.
- No per-feed status, counts, durations, or failure summaries.
- No distinction between warnings and errors.

8. **Directory creation is fragile**
- Uses `os.mkdir` on only one path level.
- Will fail if parent directories are missing in a more complex path setup.
- Does this at import time, which is undesirable for library code.

9. **Code structure is hard to test and extend**
- Nested function inside `do()`.
- Side effects happen during import.
- Hardcoded globals and file paths.
- No separation between config loading, fetching, transformation, and persistence.

10. **No tests**
- No unit tests for parsing, time conversion, config merge, or deduplication.
- No integration tests around feed fetching and cache writing.

11. **Feed content model is minimal**
- Ignores summary/content, categories/tags, GUID, image, and feed metadata.
- No limit on number of retained entries.
- No normalization of malformed titles or links.

12. **CLI/API contract is incomplete**
- Script mode exists, but there is no proper CLI with arguments, exit codes, or help.
- Return values and error semantics are inconsistent for library use.

**Plan**

1. **Fix error handling**
- Replace bare `except:` with specific exceptions such as `OSError`, `json.JSONDecodeError`, and parsing-related failures.
- Never call `sys.exit` from deep inside fetch logic.
- Return structured per-feed results like `{"status": "ok"|"error", "error": "...", "entries": [...]}`.
- Continue processing other feeds when one fails.
- At the top level, summarize failures and choose a clean exit code.

2. **Introduce stable entry identity**
- Use a compound key such as `(feed_url, entry.id)` when available.
- Fall back to `(feed_url, link, published_timestamp)` if no GUID exists.
- Deduplicate on that stable key instead of timestamp alone.
- Store `entryId` explicitly in output JSON.

3. **Correct timezone handling**
- Replace fixed-offset timezone with `zoneinfo.ZoneInfo`, for example from config `"Asia/Seoul"`.
- Compare “today” using the same configured timezone:
  - `now = datetime.datetime.now(TIMEZONE).date()`
- Centralize time parsing/formatting in a helper function.
- Define behavior for entries with missing or invalid timestamps.

4. **Validate config early**
- Add schema checks when loading `feeds.json`.
- Validate:
  - category existence
  - category object shape
  - `feeds` is a dict of source name to URL
  - optional flags are correct types
- Raise or report clear errors like `Unknown category: ...` instead of `KeyError`.

5. **Add fetch resilience**
- If staying with `feedparser`, fetch content with `requests` first so you can set:
  - timeout
  - headers/user-agent
  - retries/backoff
  - conditional headers
- Then pass response content into `feedparser.parse`.
- Track HTTP status, redirect behavior, and parse bozo exceptions.

6. **Make writes atomic**
- Write JSON to a temporary file in the same directory.
- Use `os.replace()` to atomically swap it into place.
- Ensure UTF-8 writing and consistent formatting.

7. **Replace print-style logging**
- Use the `logging` module.
- Emit per-feed events:
  - fetch started
  - fetch succeeded
  - fetch failed
  - entries accepted/skipped
- Add optional verbose/debug mode.
- Include enough context to diagnose malformed feeds.

8. **Move startup side effects out of import**
- Remove directory creation from module import.
- Add an explicit `ensure_data_dir()` called from `do()` or app startup.
- Use `os.makedirs(path, exist_ok=True)`.

9. **Refactor for maintainability**
- Split into focused functions:
  - `load_config()`
  - `merge_bundled_categories()`
  - `fetch_feed(url)`
  - `normalize_entry(feed, source, entry, timezone)`
  - `write_category_cache(category, entries)`
- Consider a small dataclass for config and entry models.
- Keep `do()` as an orchestration layer only.

10. **Add tests**
- Unit tests for:
  - config bootstrap/merge
  - timestamp parsing
  - timezone-aware date formatting
  - deduplication
  - single-category vs all-category execution
- Integration tests using sample feed payloads instead of live network calls.
- Add regression tests for missing timestamps and duplicate timestamps.

11. **Improve the stored data model**
- Persist feed-level metadata such as source URL and fetch timestamp.
- Store optional fields when present:
  - `entryId`
  - `author`
  - `summary`
  - `categories`
- Add retention limits, for example keep latest `N` entries per category.

12. **Define a real interface**
- Add a CLI with `argparse`:
  - `--category`
  - `--log-level`
  - `--config`
  - `--dry-run`
- Return meaningful exit codes.
- Document the JSON output contract so other components can depend on it safely.

The core behavior is already useful: it bootstraps config, fetches feeds, normalizes entries, and writes cache files. The main work to make it production-ready is reliability: error handling, stable identity, timezone correctness, validation, and test coverage.