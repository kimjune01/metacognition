**Observations**

This system is a small RSS fetcher and cache writer.

It currently does these things correctly:

- Loads feed definitions from a bundled `feeds.json` and copies them into a user data directory at `~/.rreader/feeds.json` on first run.
- Merges newly added bundled categories into an existing user `feeds.json` without overwriting the user’s existing categories.
- Reads feed URLs by category from `feeds.json`.
- Fetches and parses RSS/Atom feeds with `feedparser`.
- Extracts entries from each feed and uses `published_parsed` or `updated_parsed` when available.
- Converts entry timestamps from UTC into a configured timezone.
- Formats display dates as either `HH:MM` for today or `Mon DD, HH:MM` for older items.
- Builds a normalized entry shape with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`.
- Supports category-specific output files named `rss_<category>.json` under `~/.rreader/`.
- Supports fetching either one category or all categories.
- Optionally uses the feed entry author instead of the source name when `show_author` is enabled.
- Supports a basic progress log mode for feed fetches.
- Creates the `~/.rreader/` directory automatically if it does not exist.

**Triage**

Ranked by importance:

1. **Error handling is too weak and sometimes wrong**
- Broad bare `except:` blocks hide real failures.
- `sys.exit(" - Failed\n" if log else 0)` mixes string and numeric exit behavior and can terminate the whole process because one feed fails.
- Parse failures, malformed JSON, missing categories, filesystem errors, and bad feed data are not handled cleanly.

2. **No network robustness**
- No request timeout, retry, backoff, or per-feed failure isolation.
- One slow or broken feed can stall or degrade the run.
- Production feed fetching needs predictable failure behavior.

3. **Deduplication is unsafe**
- Entries are keyed only by `ts = int(time.mktime(parsed_time))`.
- Multiple different articles published in the same second will overwrite each other.
- Dedup should use stable unique identifiers such as entry ID, link, or a composite key.

4. **Timezone and “today” handling are inconsistent**
- Output timestamps are converted into `TIMEZONE`, but `"today"` is checked against `datetime.date.today()`, which uses the machine’s local timezone, not necessarily `TIMEZONE`.
- That can mislabel entries around midnight.

5. **No validation of feed configuration**
- Assumes `FEEDS_FILE_NAME` exists and contains valid JSON with the expected schema.
- Assumes `target_category` exists in `RSS`.
- A malformed config will crash.

6. **Filesystem operations are not production-safe**
- Writes JSON directly to the target file with no atomic write.
- A crash or interruption can leave corrupted cache files.
- Directory creation uses `os.mkdir` and assumes only one level and no races.

7. **Logging and observability are minimal**
- No structured logs, no per-feed error reporting, no counts, no timing, no warning surface.
- Difficult to debug feed failures in production.

8. **No testability or separation of concerns**
- Fetching, parsing, formatting, config bootstrap, and file output are all mixed together.
- Hard to unit test and hard to swap components.

9. **No CLI or API contract beyond `do()`**
- There is no explicit command-line interface, argument parsing, exit code strategy, or documented output contract.
- Production usage usually needs a stable interface.

10. **Data model is thin**
- Does not preserve summary/content, categories/tags, feed title, GUID, or raw published timestamp string.
- That may be fine for a reader, but it limits downstream features.

11. **Performance and scaling are basic**
- Feeds are fetched serially.
- No conditional requests, caching headers, concurrency, or rate limiting.

12. **Security and input hygiene are limited**
- Accepts arbitrary URLs from config with no validation.
- No guardrails around file permissions, malformed content, or oversized responses.

**Plan**

1. **Fix error handling**
- Replace bare `except:` with targeted exceptions such as `KeyError`, `JSONDecodeError`, `OSError`, and parser/network exceptions.
- Stop calling `sys.exit` inside `get_feed_from_rss`; return structured per-feed errors instead.
- Keep processing other feeds when one fails.
- Define explicit return data like:
  - `{"entries": [...], "created_at": ..., "errors": [...]}`
- Raise only for fatal initialization errors, not routine feed failures.

2. **Add network resilience**
- Set request timeouts.
- Add retry with exponential backoff for transient failures.
- Record fetch status per feed: success, timeout, parse error, HTTP error.
- If `feedparser` alone is insufficient for timeout control, fetch with `requests` first, then parse the response body.

3. **Replace timestamp-only dedup**
- Use a stronger key priority such as:
  - entry `id` or `guid`
  - else `link`
  - else hash of `(title, link, published)`
- Keep timestamp as metadata, not primary identity.
- If dedup is intended across feeds, make that explicit; otherwise namespace keys by source.

4. **Make timezone handling consistent**
- Compare “today” in the configured timezone:
  - use `datetime.datetime.now(TIMEZONE).date()`
- Avoid naive datetimes in comparisons.
- Document whether `TIMEZONE` is user-configurable and where it comes from.

5. **Validate config aggressively**
- On load, validate that the JSON is a dict of categories and each category has a `feeds` dict.
- If `target_category` is missing, raise a clear error or return a structured failure.
- Handle malformed `feeds.json` with a repair path or readable error message.

6. **Make writes atomic**
- Ensure the data directory exists with `os.makedirs(path, exist_ok=True)`.
- Write to a temporary file first, then rename into place.
- Use UTF-8 consistently.
- Consider file locking if concurrent runs are possible.

7. **Improve logging**
- Replace `sys.stdout.write` with `logging`.
- Log category start/end, feed URL, item counts, elapsed time, and exceptions.
- Add log levels so normal operation is quiet and debug mode is useful.

8. **Refactor for testability**
- Split into focused functions:
  - `load_feed_config()`
  - `merge_bundled_categories()`
  - `fetch_feed(url)`
  - `normalize_entry(feed, source, timezone, show_author)`
  - `write_category_cache(category, entries)`
- Inject dependencies like timezone, paths, and fetcher so tests can control them.

9. **Define a real interface**
- Add CLI arguments such as `--category`, `--log`, `--output-dir`, `--timezone`.
- Return meaningful process exit codes:
  - `0` success
  - nonzero for fatal init/config errors
- Document the output JSON schema.

10. **Expand the stored schema if needed**
- Preserve optional fields like `guid`, `summary`, `feed_title`, `author`, and original published string.
- Include the originating category and source URL.
- Add versioning to the cache format if clients will depend on it.

11. **Improve throughput**
- Fetch feeds concurrently with a bounded worker pool.
- Respect reasonable concurrency limits to avoid hammering servers.
- Support HTTP conditional requests using ETag/Last-Modified if persistent metadata is stored.

12. **Add tests**
- Unit tests for date parsing, timezone formatting, dedup logic, config merge, and malformed entries.
- Integration tests using sample RSS/Atom payloads.
- Regression tests for feeds missing `published_parsed`, duplicate timestamps, and invalid categories.

If you want, I can turn this report into a prioritized engineering checklist or a GitHub issue set.