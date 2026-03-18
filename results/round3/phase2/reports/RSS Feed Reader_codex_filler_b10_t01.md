**Observations**

This system is a small RSS ingester and cache writer.

It currently does these things correctly:

- Loads a bundled `feeds.json` and ensures a user copy exists at `~/.rreader/feeds.json`.
- Merges in newly added bundled categories if the user already has a feeds file.
- Reads configured RSS categories and feed URLs from JSON.
- Fetches and parses feeds with `feedparser.parse(url)`.
- Iterates feed entries and extracts:
  - publication time from `published_parsed` or `updated_parsed`
  - link
  - title
  - author, optionally
- Converts entry timestamps from UTC into a configured timezone.
- Formats display dates as either `HH:MM` for today or `Mon DD, HH:MM` for older items.
- Sorts items newest-first.
- Writes one cache file per category to `~/.rreader/rss_<category>.json`.
- Supports:
  - refreshing one category via `do(target_category=...)`
  - refreshing all categories via `do()`
  - optional progress logging
- Creates the base data directory `~/.rreader/` if it does not exist.

In short: it is a working local feed fetcher/cache generator for a fixed JSON-based feed configuration.

**Triage**

Highest-priority gaps:

1. **Error handling is unsafe and opaque**
- Broad bare `except:` blocks hide failures.
- A single parse failure can terminate the whole process with `sys.exit`.
- Errors are not surfaced in structured form, so operators cannot tell what failed or why.

2. **Entry identity and deduplication are incorrect**
- Entries are keyed only by Unix timestamp.
- Multiple posts published in the same second will overwrite each other.
- Different feeds can collide, causing silent data loss.

3. **Filesystem setup is fragile**
- `os.mkdir` only creates one directory level.
- No handling for missing parent dirs, permission errors, partial writes, or concurrent runs.

4. **Timezone and date handling are inconsistent**
- “Today” is checked with `datetime.date.today()` in local system time, not the configured timezone.
- `time.mktime(parsed_time)` interprets time as local time, which is wrong for UTC-normalized feed timestamps.
- This can produce incorrect timestamps and date labels.

5. **No network robustness**
- No timeout control, retry policy, backoff, user agent, or per-feed failure isolation.
- Production fetchers need predictable behavior under slow, malformed, or unavailable feeds.

6. **No schema validation for input config or output**
- Assumes `feeds.json` is valid and category structure is correct.
- Missing keys or malformed JSON will crash unexpectedly.

7. **Output format is too minimal for production**
- No feed-level metadata, error state, fetch duration, content hash, GUID, summary, or canonical entry ID.
- No status to distinguish “empty feed” from “fetch failed.”

8. **Logging and observability are minimal**
- Logging is plain stdout and incomplete.
- No structured logs, metrics, warnings, or diagnostics.

9. **Code structure is hard to maintain**
- Nested function inside `do`.
- Business logic, I/O, configuration bootstrap, and CLI behavior are tightly coupled.
- The inlined module layout suggests this was assembled for convenience, not maintainability.

10. **No tests**
- No unit tests for timestamp conversion, merge behavior, dedupe, or file writing.
- No integration tests with sample feed payloads.

**Plan**

1. **Fix error handling**
- Replace bare `except:` with targeted exceptions such as `OSError`, `json.JSONDecodeError`, and feed parsing/network exceptions.
- Do not call `sys.exit` inside library logic.
- Return structured per-feed results like `{status, error, entries}` so one bad feed does not abort the category.
- Emit actionable error messages including category, source name, and URL.

2. **Introduce stable entry IDs**
- Stop using publication timestamp as the dictionary key.
- Prefer feed-provided stable identifiers in this order: `id`/`guid`, then `link`, then a hash of `(source, title, published_time)`.
- Deduplicate on that stable ID and keep timestamp only for sorting.

3. **Harden filesystem writes**
- Replace `os.mkdir` with `os.makedirs(path, exist_ok=True)`.
- Write JSON to a temporary file and atomically rename it into place.
- Handle permission and disk-write failures explicitly.
- Ensure the data directory creation happens in a dedicated initialization function.

4. **Correct time handling**
- Compute “today” in the configured timezone, not system local time.
- Replace `time.mktime(parsed_time)` with a UTC-safe conversion path, for example via `calendar.timegm(parsed_time)`.
- Normalize all stored timestamps to UTC seconds and all rendered display times to the configured timezone.
- Decide whether cache output should store raw UTC plus formatted display strings, and keep both.

5. **Add network resilience**
- Use a fetch layer with request timeout, retry with backoff, and a configured user agent.
- If `feedparser` is kept, feed it response bytes fetched by a controlled HTTP client instead of letting it manage network access implicitly.
- Record per-feed fetch outcome and continue processing remaining feeds.

6. **Validate config**
- Validate `feeds.json` on load:
  - top-level categories must be dicts
  - each category must contain `feeds`
  - `feeds` must map source names to URL strings
  - optional flags like `show_author` must be typed correctly
- Fail with a clear config error message instead of a later `KeyError`.

7. **Expand output schema**
- Include per-category metadata such as:
  - `created_at`
  - `category`
  - `feed_count`
  - `success_count`
  - `error_count`
  - `errors`
- Include richer entry fields such as:
  - stable `id`
  - `source_key`
  - raw published timestamp in UTC
  - optional `author`
  - optional `summary`
- Preserve enough metadata for downstream UI/debugging.

8. **Improve logging**
- Replace ad hoc stdout writes with the `logging` module.
- Support log levels and structured messages.
- Log start/end of category refresh, per-feed duration, entry count, and failures.

9. **Refactor the codebase**
- Split responsibilities into modules:
  - config loading/validation
  - feed fetching
  - entry normalization
  - cache writing
  - CLI entrypoint
- Move `get_feed_from_rss` out of `do`.
- Keep `do()` as a thin orchestration layer.

10. **Add tests**
- Unit tests for:
  - timezone conversion
  - “today” formatting
  - stable ID generation
  - deduplication behavior
  - config merge behavior
- Integration tests using fixture RSS/Atom feeds, including malformed feeds and duplicate timestamps.
- Filesystem tests for initial bootstrap and atomic cache writes.

The short version: this is a functional prototype, not a production service. The biggest risks are silent data loss, wrong timestamps, and poor failure handling. Those should be fixed first.