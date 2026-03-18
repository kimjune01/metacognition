**Observations**

This system is a small RSS fetch-and-cache job.

It currently does these things:

- Loads a bundled `feeds.json`, and copies it into the user data directory on first run.
- Merges newly added bundled categories into an existing user `feeds.json` without overwriting user-defined categories.
- Creates `~/.rreader/` automatically if it does not exist.
- Reads feed definitions by category and source URL.
- Fetches RSS/Atom feeds with `feedparser.parse(url)`.
- Iterates feed entries and extracts:
  - publish/update timestamp
  - source/author name
  - link
  - title
- Converts timestamps from UTC into a configured timezone (`UTC+9` in this code).
- Formats display dates as either `HH:MM` for today or `Mon DD, HH:MM` otherwise.
- Deduplicates entries implicitly by using Unix timestamp as the dictionary key.
- Sorts entries newest-first.
- Writes one JSON cache file per category as `rss_<category>.json`.
- Supports:
  - fetching one category via `do(target_category=...)`
  - fetching all categories via `do()`
  - optional console logging

So the core capability already works: given a feed config, it pulls entries and materializes per-category JSON snapshots.

**Triage**

Ranked by importance:

1. **Error handling is unsafe and too broad**
- Bare `except:` blocks hide the actual failure mode.
- A single bad fetch can call `sys.exit`, which is wrong for library code and brittle for batch jobs.
- File I/O, JSON decode, missing keys, malformed feeds, and permission failures are not handled cleanly.

2. **Deduplication is incorrect**
- Entries are keyed only by `timestamp`.
- Two different articles published in the same second will collide and one will be silently dropped.
- The collision risk is real for feeds with bulk republishes or low timestamp granularity.

3. **Freshness and state management are incomplete**
- Each run rewrites a full category snapshot, but there is no incremental sync state, no ETag/Last-Modified handling, and no record of fetch success/failure per source.
- There is no way to distinguish “no new entries” from “fetch failed and stale cache remained” except by indirect inspection.

4. **Time handling is not production-safe**
- `datetime.date.today()` uses local system date, while entry times are converted through `TIMEZONE`; that can produce wrong “today” labeling if system timezone differs.
- `time.mktime(parsed_time)` interprets the struct as local time, which is wrong for feed timestamps that are usually UTC-like parsed structs.
- Timezone is hard-coded to KST.

5. **Data model is too thin**
- Stored fields are minimal: no summary, content, feed source id, GUID, categories/tags, fetch metadata, or raw published time.
- This limits downstream UI, search, dedupe, and debugging.

6. **Configuration and portability are weak**
- Storage path is hard-coded to `~/.rreader/`.
- Directory creation uses `os.mkdir` on one level only.
- No environment/config overrides.
- No validation for malformed `feeds.json`.

7. **Logging and observability are inadequate**
- Logging is plain `stdout` and incomplete.
- There are no structured logs, error counts, per-feed metrics, or traceability.

8. **No testing surface**
- Date formatting, feed parsing, merge behavior, dedupe, and failure handling are all untested.
- This code will regress easily when changed.

9. **No concurrency or throughput controls**
- Feeds are fetched serially.
- Fine for a small personal setup, but it does not scale to many feeds or slow sources.

10. **No production packaging/operational story**
- No CLI argument parsing beyond direct function call.
- No retry policy, timeout control, lockfile, scheduler integration, or graceful partial-failure behavior.

**Plan**

1. **Fix error handling first**
- Replace bare `except:` with narrow exceptions:
  - network/parser errors
  - JSON decode errors
  - filesystem errors
  - missing config keys
- Remove `sys.exit()` from inner functions.
- Return structured per-feed results such as `{status, error, entries_added}`.
- Decide failure policy explicitly:
  - continue on single-feed failure
  - fail the whole run only on config/output errors
- Preserve stale output unless a successful replacement is ready.

2. **Replace timestamp-only dedupe**
- Use a stable entry key in priority order:
  - feed GUID/id if present
  - canonicalized entry URL
  - hash of `(source, title, published, url)` as fallback
- Store timestamp as sortable metadata, not as primary identity.
- Keep dedupe scoped per source or globally based on product needs.

3. **Add explicit fetch state**
- Persist per-feed metadata:
  - last fetch time
  - last success time
  - last error
  - ETag
  - Last-Modified
- On next fetch, send conditional requests when supported.
- Include cache freshness metadata in output JSON so consumers know whether data is current or stale.

4. **Correct the time logic**
- Use timezone-aware datetime consistently.
- Replace `time.mktime(parsed_time)` with a UTC-safe conversion.
- Compute “today” in the same configured timezone as the entry conversion.
- Make timezone configurable instead of hard-coded.

5. **Expand the stored schema**
- Add fields like:
  - `entry_id`
  - `feed_name`
  - `feed_url`
  - `author`
  - `published_at_iso`
  - `updated_at_iso`
  - `summary`
  - `tags`
  - `fetched_at`
- Version the output schema so consumers can migrate safely.

6. **Harden config and filesystem behavior**
- Validate `feeds.json` shape before processing.
- Handle missing categories and missing `feeds` keys with clear errors.
- Use `os.makedirs(..., exist_ok=True)`.
- Support configurable data directory via env var or config file.
- Sanitize category names before using them in filenames.

7. **Introduce real logging**
- Use the `logging` module.
- Emit per-feed start/end/error records.
- Log counts of feeds processed, entries emitted, entries dropped, collisions detected.
- Make log level configurable.

8. **Add tests**
- Unit tests for:
  - bundled/user config merge
  - timestamp parsing and formatting
  - dedupe behavior
  - target-category handling
  - malformed entries
- Integration tests using saved feed fixtures instead of live network calls.

9. **Improve fetch execution**
- Add request timeout and retry policy.
- Consider parallel fetches with bounded concurrency once correctness is stable.
- Rate-limit or back off on repeated failures.

10. **Make it operable as a production job**
- Add a proper CLI with flags like `--category`, `--log-level`, `--data-dir`, `--dry-run`.
- Return meaningful exit codes.
- Write output atomically via temp file + rename.
- Add a lockfile or equivalent to prevent overlapping runs.

The shortest path to “production enough” is: fix error handling, fix dedupe identity, fix time correctness, and add fetch-state metadata. Those four changes move this from “working script” to “reliable ingestion component.”