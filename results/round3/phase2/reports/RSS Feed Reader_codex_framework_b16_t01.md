**Observations**

This system is a small RSS ingestion job that reads a category/feed configuration, fetches feeds with `feedparser`, normalizes entries, and writes one JSON file per category under `~/.rreader/`.

Working capabilities:

- It bootstraps a user config file:
  - If `~/.rreader/feeds.json` does not exist, it copies a bundled `feeds.json`.
  - If it does exist, it merges in any newly added bundled categories without overwriting existing user categories.
- It ensures the data directory exists:
  - Creates `~/.rreader/` if missing.
- It supports two execution modes:
  - Refresh one category with `do(target_category=...)`
  - Refresh all categories with `do()`
- For each configured feed URL, it:
  - Fetches and parses the feed with `feedparser.parse(url)`
  - Iterates over `d.entries`
  - Uses `published_parsed` or `updated_parsed` when present
  - Converts timestamps from UTC into a configured local timezone
- It normalizes each item into a consistent structure:
  - `id`
  - `sourceName`
  - `pubDate`
  - `timestamp`
  - `url`
  - `title`
- It supports optional author display:
  - Uses feed entry author if `show_author=True`, otherwise uses the configured source name
- It sorts entries newest-first and writes category output as:
  - `{"entries": [...], "created_at": ...}`
- It has optional progress logging for feed fetches.

In short: this is a working feed-to-JSON batch exporter with basic config bootstrapping and timezone-aware timestamp formatting.

**Triage**

Ranked by importance:

1. **Error handling is too weak and sometimes wrong**
- Bare `except:` blocks suppress useful failures.
- A single feed parse failure can terminate the whole process with `sys.exit(...)`.
- The expression `sys.exit(" - Failed\n" if log else 0)` is inconsistent:
  - with `log=False`, it exits successfully on failure
  - with `log=True`, it exits with a string error
- Individual bad entries are silently skipped with no visibility.

2. **Deduplication is unsafe**
- Entries are keyed only by `ts = int(time.mktime(parsed_time))`.
- Multiple posts published in the same second will collide.
- Collisions overwrite previous items silently.
- Same article appearing across feeds is not deduplicated meaningfully.

3. **Time handling is incorrect or fragile**
- `time.mktime(parsed_time)` interprets the struct as local time, not UTC.
- Earlier code correctly treats parsed feed times as UTC for display, but the stored integer timestamp may not match.
- `datetime.date.today()` uses system local time, not the configured `TIMEZONE`, so `pubDate` formatting can be wrong around day boundaries.

4. **No network robustness**
- No request timeout, retry, backoff, or per-feed failure isolation.
- No handling for temporary outages, malformed XML, rate limits, or slow feeds.
- `feedparser` is being used in its simplest mode only.

5. **No validation of configuration or inputs**
- Assumes categories exist and contain `"feeds"`.
- `target_category` can raise `KeyError`.
- No schema validation for `feeds.json`.
- No sanitization of feed metadata before writing output.

6. **Storage/output model is too primitive for production**
- Full category output is rewritten every run.
- No incremental updates, retention policy, archive strategy, or atomic writes.
- No locking, so concurrent runs could corrupt output.
- No stable internal IDs beyond a timestamp.

7. **No observability**
- No structured logs, metrics, error counts, or feed health reporting.
- No way to know which feeds are stale, broken, empty, or slow.
- Silent skips make debugging difficult.

8. **Timezone/configuration is hardcoded**
- `TIMEZONE` is fixed to UTC+9 in code comments as “KST Seoul UTC+9”.
- Not configurable per user or environment.
- `~/.rreader/` path is also hardcoded.

9. **No tests**
- Critical behaviors are unverified:
  - time conversion
  - category merge behavior
  - duplicate handling
  - malformed feed handling
  - output format compatibility

10. **No product boundary beyond a library function**
- No CLI argument parsing, no service mode, no scheduler integration, no packaging story.
- It works as a script, but not yet as an operational component.

**Plan**

1. **Fix error handling first**
- Replace all bare `except:` with specific exceptions.
- Do not call `sys.exit()` from inside feed-processing helpers.
- Return structured per-feed results such as success/failure counts and error messages.
- Continue processing other feeds even if one fails.
- Log entry-level parse skips with enough detail to debug, but keep the batch running.
- Define clear failure semantics for `do()`:
  - successful with partial failures
  - total failure
  - invalid configuration

2. **Introduce stable IDs and real deduplication**
- Stop using raw publish timestamp as the dictionary key.
- Build a stable entry ID from feed GUID if available, otherwise hash a tuple like `(feed_url, entry.link, entry.title, published_time)`.
- Deduplicate on that stable ID, not on second-level timestamp.
- Keep timestamp only for sorting.
- Decide policy for cross-feed duplicates:
  - preserve separate source attribution, or
  - collapse equivalent URLs into one canonical item

3. **Correct all time semantics**
- Replace `time.mktime(parsed_time)` with a UTC-safe conversion such as `calendar.timegm(parsed_time)`.
- Compare dates in the configured timezone, not system local timezone.
- Derive “today” using `datetime.datetime.now(TIMEZONE).date()`.
- Store machine-readable timestamps in UTC and format display strings separately.
- Consider storing ISO 8601 strings alongside epoch timestamps.

4. **Add network resilience**
- Wrap feed fetches with timeout and retry behavior.
- If `feedparser` alone is insufficient, fetch with `requests` first, then parse response content.
- Record feed-level HTTP and parse failures without aborting the batch.
- Add backoff for transient errors.
- Mark stale feeds when fetch succeeds but returns no usable entries unexpectedly.

5. **Validate configuration before execution**
- Define a schema for `feeds.json`.
- Validate:
  - category exists
  - `"feeds"` is a mapping
  - feed names and URLs are strings
  - optional fields like `show_author` are typed correctly
- Raise a clean, actionable error for invalid config.
- If `target_category` is missing, return a user-facing error instead of a `KeyError`.

6. **Harden output writing**
- Write to a temporary file and rename atomically.
- Add file locking or a single-writer guarantee if concurrent runs are possible.
- Preserve prior output if a refresh fails partway.
- Decide whether output is:
  - a snapshot per category, or
  - an append/update store with history
- If snapshot remains the design, document that explicitly.

7. **Add observability**
- Replace `sys.stdout.write` with structured logging.
- Emit counts per run:
  - feeds attempted
  - feeds failed
  - entries parsed
  - entries skipped
  - duplicates dropped
- Include per-feed latency and last-success timestamp.
- Optionally write a health/status JSON for downstream monitoring.

8. **Make runtime configuration explicit**
- Move timezone and data path into config or environment variables.
- Default sanely, but allow override.
- Remove the hardcoded KST assumption from general-purpose code.
- Make path creation recursive and robust with `mkdir(parents=True, exist_ok=True)`.

9. **Add tests before expanding scope**
- Unit tests:
  - category merge logic
  - timestamp conversion
  - `pubDate` formatting across timezone boundaries
  - dedup behavior
  - malformed entries
- Integration tests:
  - sample RSS/Atom payloads
  - partial feed failure
  - atomic output writing
- Regression tests for collision cases where multiple items share one second.

10. **Define the production surface**
- Add a real CLI:
  - refresh all
  - refresh one category
  - validate config
  - show health
- Package it as an installable module.
- Decide intended deployment:
  - cron job
  - long-running service
  - library used by another app
- Add exit codes that reflect operational status for schedulers and monitoring.

The shortest path to “production-capable” is: fix failure handling, fix IDs/time semantics, validate config, and make writes atomic. Those four changes address most of the current correctness risk.