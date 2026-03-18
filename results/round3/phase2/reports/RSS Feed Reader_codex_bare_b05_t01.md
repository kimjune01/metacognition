**Observations**

This system is a local RSS fetcher and cache writer.

Working capabilities:
- Loads a bundled `feeds.json` and copies it into the user data directory (`~/.rreader/feeds.json`) if no user config exists.
- Merges newly added categories from the bundled feed config into the user’s existing config.
- Reads category definitions from `feeds.json` and fetches each RSS/Atom URL with `feedparser`.
- Extracts entries from each parsed feed and keeps:
  - timestamp-based `id`
  - `sourceName`
  - formatted `pubDate`
  - raw Unix `timestamp`
  - article `url`
  - article `title`
- Supports fetching:
  - one category via `do(target_category=...)`
  - all categories via `do()`
- Optionally switches displayed author from feed source name to entry author when `show_author=True`.
- Converts feed timestamps from UTC into a configured timezone.
- Writes per-category output files like `~/.rreader/rss_<category>.json`.
- Deduplicates entries only by integer timestamp key within a category and sorts newest-first.
- Can print basic progress logging for feed URLs.

**Triage**

Ranked by importance:

1. **Error handling is fragile and sometimes incorrect**
- Broad `except:` blocks hide failures.
- `sys.exit(" - Failed\n" if log else 0)` is not appropriate inside library logic.
- A single feed failure can abort the whole run.
- No structured error reporting for malformed feeds, network issues, missing fields, or write failures.

2. **Data integrity and deduplication are weak**
- Entry IDs are based only on `time.mktime(parsed_time)`.
- Multiple posts published in the same second can overwrite each other.
- Feeds without `published_parsed` or `updated_parsed` are silently dropped.
- No stable canonical ID from feed GUID/link/title.

3. **Configuration and filesystem setup are incomplete**
- `os.mkdir` only creates one level and assumes parent exists.
- Paths are hardcoded and not portable/configurable enough.
- Missing validation that `feeds.json` has the expected schema.
- No protection against corrupted or partially written config/data files.

4. **Timezone and time handling are inaccurate**
- `TIMEZONE` is hardcoded to KST while `datetime.date.today()` uses local system date, which may not match that timezone.
- `time.mktime(parsed_time)` interprets the struct as local time, which is wrong for UTC feed timestamps.
- Mixed timezone assumptions can produce incorrect display dates and IDs.

5. **No production-grade network behavior**
- No request timeout, retry, backoff, or user-agent control.
- No conditional requests (`ETag`, `Last-Modified`) to reduce bandwidth and speed up polling.
- No rate limiting or concurrency strategy.

6. **Output model is too minimal**
- Stores only title/link/time/source.
- Omits summary, content, feed title, GUID, tags, and fetch metadata.
- No per-entry normalization status or source diagnostics.

7. **Library/API design is rough**
- `do()` mixes orchestration, config migration, fetching, transformation, and persistence.
- Nested `get_feed_from_rss()` is hard to test independently.
- Return values are inconsistent with error conditions and side effects.

8. **No tests or observability**
- No unit tests for parsing, merge behavior, timezone formatting, or deduplication.
- No logging framework, metrics, or traceability for failed feeds.

9. **No security or robustness hardening**
- Blindly trusts feed config and remote content.
- No atomic writes.
- No file locking for concurrent runs.

**Plan**

1. **Fix error handling first**
- Replace broad `except:` with targeted exceptions: feed parse/network errors, `KeyError`, `OSError`, `JSONDecodeError`.
- Remove `sys.exit()` from lower-level functions; raise exceptions or collect errors in a result object.
- Change all-category fetch so one bad feed records an error and the rest continue.
- Return a structured result:
  - `entries`
  - `errors`
  - `fetched_sources`
  - `created_at`

2. **Introduce stable entry identity and safer deduplication**
- Build entry IDs from feed GUID if present, else link, else hash of `(source, title, published timestamp)`.
- Keep timestamp as a separate sortable field, not as the dictionary key.
- Deduplicate on stable ID, not second-level publish time.
- Accept entries without publish time by assigning `fetched_at` and marking `published_at=None`.

3. **Refactor into testable components**
- Split into functions/modules:
  - `load_and_migrate_config()`
  - `fetch_feed(url)`
  - `normalize_entry(feed, source)`
  - `write_category_cache(category, entries)`
- Move the nested function to top level.
- Keep `do()` as a thin orchestration entrypoint.

4. **Correct time handling**
- Use timezone-aware UTC conversion consistently.
- Replace `time.mktime(parsed_time)` with `calendar.timegm(parsed_time)` if the struct is UTC.
- Compare dates in the configured timezone, not system local time.
- Replace fixed KST config with a real configurable zone, ideally `zoneinfo.ZoneInfo("Asia/Seoul")` or user-provided value.

5. **Harden filesystem and config management**
- Replace `os.mkdir` with `os.makedirs(path, exist_ok=True)`.
- Validate `feeds.json` schema before use:
  - category exists
  - `feeds` is a mapping
  - URLs are strings
- Write JSON atomically via temp file + rename.
- Handle corrupt user config by backing it up and restoring from bundled defaults or failing clearly.

6. **Improve network behavior**
- Use a fetch layer with timeout and retries.
- Set a meaningful user-agent.
- Persist and send `ETag` / `Last-Modified` headers per feed.
- Record fetch status per source: success, skipped-not-modified, parse error, timeout.

7. **Expand stored data model**
- Add normalized fields:
  - `entry_id`
  - `feed_source`
  - `feed_title`
  - `author`
  - `published_at`
  - `fetched_at`
  - `summary`
  - `tags`
- Keep `pubDate` as a presentation field only, or generate it at read time instead of storage time.

8. **Add tests**
- Unit tests for:
  - config migration
  - deduplication logic
  - timestamp parsing
  - timezone formatting
  - handling entries missing author/date
- Integration tests with fixture RSS/Atom feeds and malformed feeds.

9. **Add operational visibility**
- Replace `sys.stdout.write` with `logging`.
- Log per-category and per-feed counts, durations, and failures.
- Expose summary stats from `do()` so a caller or scheduler can alert on failures.

If you want, I can turn this report into a production-ready backlog with priorities like `P0/P1/P2` and suggested file/module boundaries.