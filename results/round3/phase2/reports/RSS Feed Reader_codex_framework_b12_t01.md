**Observations**

This system is a small RSS ingester and cache writer.

It currently does these things:

- Loads a bundled `feeds.json` and ensures a user-level feed config exists at `~/.rreader/feeds.json`.
- Merges in any new top-level categories from the bundled config into the user config without overwriting existing user categories.
- Reads feed definitions by category from that config.
- Fetches and parses RSS/Atom feeds with `feedparser`.
- Iterates feed entries and keeps only items with `published_parsed` or `updated_parsed`.
- Converts feed timestamps from UTC into a fixed configured timezone.
- Formats a display-oriented `pubDate` string.
- Builds normalized entry records with:
  - `id`
  - `sourceName`
  - `pubDate`
  - `timestamp`
  - `url`
  - `title`
- Optionally uses the entry’s author instead of the feed source name when `show_author=True`.
- Deduplicates entries implicitly by storing them in a dict keyed by `id`.
- Sorts entries newest-first.
- Writes one JSON file per category to `~/.rreader/rss_<category>.json`.
- Supports either:
  - refreshing one category via `do(target_category=...)`
  - refreshing all categories via `do()`
- Optionally prints feed URLs and basic progress logging.

So the current capability is: “read a configured set of feeds, normalize recent entries, and persist per-category JSON snapshots for later consumption.”

**Triage**

Ranked by importance:

1. `id` generation is unsafe and causes data loss.
- Entries are keyed only by Unix timestamp seconds.
- Two different posts published in the same second will collide and one will be dropped.
- Collisions can also happen across different feeds.

2. Error handling is too broad and can terminate the whole process incorrectly.
- There are bare `except:` blocks everywhere.
- Feed parse/network/config/file errors are swallowed or converted into abrupt `sys.exit`.
- A single bad feed can kill the run.

3. No network robustness.
- No timeout policy, retry/backoff, user agent, or per-feed failure isolation.
- Production ingestion needs predictable behavior under slow, flaky, or malformed feeds.

4. Filesystem initialization is fragile.
- It creates only `~/.rreader/` using `os.mkdir`, assuming the parent exists and the single directory is enough.
- No atomic writes, no temp-file swap, no corruption protection.

5. Timestamp handling is inconsistent and partly wrong.
- `time.mktime(parsed_time)` interprets the parsed struct as local time, not UTC.
- Earlier code treats feed times as UTC for display conversion.
- This can shift timestamps depending on machine locale.

6. Config migration is incomplete.
- Only new categories are merged.
- Changes inside existing categories or feeds are never reconciled.
- No schema versioning or validation.

7. Output is display-oriented, not API-stable.
- `pubDate` is a formatted string, not a canonical machine field.
- No raw ISO 8601 timestamp, feed/category metadata, or stable unique key.

8. No observability.
- Logging is print-based and minimal.
- No counts, no per-feed failures summary, no metrics, no structured logs.

9. No tests.
- The behavior around timezones, dedupe, config merge, and malformed feeds is easy to regress.

10. No incremental fetch or retention strategy.
- Every run reparses all configured feeds.
- No caching headers, last-seen entry tracking, pruning policy, or history management.

11. Directory and config assumptions are hard-coded.
- Uses `~/.rreader/` and a fixed timezone from code.
- Not flexible enough for multi-environment deployment.

12. Security and input hygiene are minimal.
- Untrusted feed fields are written directly.
- No length bounds, sanitization expectations, or malformed-content handling policy.

**Plan**

1. Fix entry identity.
- Replace `id = ts` with a stable composite key.
- Prefer feed-provided IDs in this order: `entry.id`, `entry.guid`, `entry.link`, then a hash of `(source, title, published/update time)`.
- Keep `timestamp` as a separate sortable field.
- Deduplicate on the stable ID, not on seconds.

2. Replace broad exception handling with scoped failures.
- Catch specific exceptions around:
  - config file read/parse
  - filesystem writes
  - feed fetch/parse
  - entry normalization
- Never `sys.exit` from inside feed processing.
- Return per-feed error results and continue processing other feeds.

3. Add resilient fetch behavior.
- Configure `feedparser` with a clear `User-Agent` if feasible in the surrounding stack.
- Add request timeout and retry behavior; if `feedparser` alone is insufficient, fetch with `requests/httpx` first, then parse response content.
- Track HTTP status, bozo feeds, parse warnings, and last success time.

4. Harden storage writes.
- Create directories with `os.makedirs(path, exist_ok=True)`.
- Write JSON to a temp file in the same directory, then atomically rename.
- Consider preserving the last known good file if a write fails.

5. Correct time handling.
- Convert parsed times using UTC-aware APIs consistently.
- Replace `time.mktime(parsed_time)` with `calendar.timegm(parsed_time)` when the struct is UTC-like.
- Store:
  - `timestamp` as UTC epoch seconds
  - `published_at` as ISO 8601 UTC
  - optionally a separate localized display field

6. Introduce config schema validation and migration.
- Define a config schema for categories, feeds, and options.
- Validate on load and report exact failures.
- Add a schema version field.
- Merge not just missing categories, but also missing keys within existing categories where safe.

7. Separate canonical data from presentation.
- Keep machine fields canonical and raw.
- Move formatting like `%H:%M` / `%b %d, %H:%M` to the consumer/UI layer, or at least emit both raw and formatted values.
- Include category, feed source key, and fetch metadata in output.

8. Add structured logging and run summaries.
- Replace `sys.stdout.write` with `logging`.
- Emit per-run summary:
  - feeds attempted
  - feeds succeeded
  - feeds failed
  - entries seen
  - entries kept
  - entries skipped for missing dates
- For production, prefer JSON logs.

9. Add tests.
- Unit tests for:
  - config bootstrap and merge
  - stable ID generation
  - timestamp normalization
  - dedupe behavior
  - malformed/missing entry fields
  - one-feed failure not aborting the whole run
- Fixture-based tests with saved RSS/Atom samples.

10. Add incremental sync behavior.
- Persist feed-level metadata such as ETag, Last-Modified, and last successful fetch.
- Skip unchanged feeds when supported.
- Optionally keep historical snapshots or a rolling window instead of rewriting only the latest category file.

11. Make runtime configuration explicit.
- Move paths, timezone, logging level, and refresh targets into config or CLI args.
- Use `zoneinfo.ZoneInfo` with an IANA timezone like `Asia/Seoul` instead of a fixed offset if DST or portability matters.

12. Define output and safety limits.
- Truncate pathological titles/authors if needed.
- Normalize missing/null fields explicitly.
- Document what fields are trusted, optional, and required.

The core is workable as a prototype: config bootstrap, feed fetch, normalization, and JSON output all exist. What it lacks for production is mostly reliability infrastructure: stable identity, correct time semantics, scoped failure handling, durable writes, validation, and tests.