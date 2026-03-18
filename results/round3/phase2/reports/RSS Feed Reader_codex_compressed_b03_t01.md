**Observations**

This system is a working RSS fetch-and-store pipeline.

- `Perceive`: Present. It ingests external data by reading RSS/Atom URLs with `feedparser.parse(url)`.
- `Cache`: Present but shallow. It converts feed entries into a normalized dict with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`, then sorts them.
- `Filter`: Present but very shallow. It drops entries with no parseable published/updated time and silently skips entries that fail timestamp handling.
- `Attend`: Present but shallow. It ranks only by recency and deduplicates only by timestamp-derived `id`.
- `Remember`: Present. It writes per-category results to `~/.rreader/rss_<category>.json` and preserves a user `feeds.json`.
- `Consolidate`: Absent. Nothing in stored results changes future fetching, filtering, ranking, or source management.

Working capabilities today:

- Bootstraps a default `feeds.json` into the user data directory.
- Merges newly bundled categories into an existing user config.
- Fetches either one category or all categories.
- Normalizes entries into a simple JSON structure.
- Persists fetched results to disk.
- Supports optional author display per category.
- Logs feed fetch progress when `log=True`.

**Triage**

Highest-priority gaps, in order:

1. **Weak identity and deduplication**
   - `id` is just `int(time.mktime(parsed_time))`.
   - Multiple items published in the same second will collide and overwrite each other.
   - Different feeds can also collide on the same timestamp.
   - This is the first serious shallow stage because both cache quality and attend quality depend on stable item identity.

2. **No real validation or quality filter**
   - The system accepts almost everything with a timestamp.
   - It does not reject malformed URLs, empty titles, duplicate links, stale entries, broken feeds, or unexpected payloads.
   - Silent `except:` blocks hide failure modes.

3. **No durable item-level memory**
   - It rewrites the latest snapshot per category, but does not track seen items, fetch history, failures, or item state across runs.
   - A production system needs accumulation, not just overwrite.

4. **No consolidation/learning loop**
   - Stored results are never used to improve future runs.
   - There is no adaptation based on feed reliability, duplicates, user interaction, or past errors.

5. **Fragile error handling and observability**
   - Broad bare `except:` suppresses actionable errors.
   - In one path it calls `sys.exit`, which makes this hard to embed as a library.
   - No structured logs, metrics, retry policy, or per-feed failure reporting.

6. **Ranking is too primitive**
   - Recency-only ordering is acceptable for a toy reader, but production needs better attention logic.
   - No source balancing, no duplicate clustering, no pinning, no stale suppression, no confidence weighting.

7. **Time handling is inconsistent**
   - Display formatting compares against `datetime.date.today()` in local system time, not `TIMEZONE`.
   - `time.mktime(parsed_time)` uses local machine assumptions, while display conversion uses `TIMEZONE`.
   - This can produce inconsistent timestamps across environments.

8. **Storage and file safety are minimal**
   - Writes are not atomic.
   - No file locking, schema versioning, corruption recovery, or migration path.
   - `os.mkdir` only creates one level and assumes parent exists.

9. **Configuration and extensibility are limited**
   - Hard-coded timezone.
   - No request timeouts, user agent configuration, polling interval, retention policy, or per-feed overrides.
   - No CLI/API contract beyond `do()`.

**Plan**

1. **Fix item identity and deduplication**
   - Build a stable item key from feed-provided GUID/ID first, then fallback to canonicalized link, then `(source, title, published_at)` hash.
   - Store both `item_id` and `feed_id`.
   - Deduplicate on stable identity, not timestamp.
   - Keep timestamp as a sortable field only.

2. **Add explicit filtering rules**
   - Validate required fields: link, title, publish/update time, source.
   - Canonicalize URLs before comparison.
   - Reject duplicate links within a run and across runs.
   - Add feed-level validation: bad status, parse failure, empty entry list, malformed schema.
   - Replace bare `except:` with specific exceptions and record rejection reasons.

3. **Introduce real persistence**
   - Split storage into:
     - `feeds.json` for config
     - `items.jsonl` or SQLite table for durable item store
     - `runs.jsonl` or a runs table for fetch history
     - `feed_state.json` or table for per-feed metadata
   - Preserve seen item IDs so later runs know what is new vs already known.
   - Track first-seen, last-seen, and fetch status.

4. **Implement consolidation**
   - Read prior run data before fetching.
   - Track feed reliability metrics: success rate, parse errors, duplicate rate, latency, empty-run rate.
   - Use those metrics to influence future behavior:
     - down-rank noisy feeds
     - back off failing feeds
     - prefer feeds with consistently valid metadata
   - If this is user-facing, incorporate click/save/read signals into ranking.

5. **Improve error handling and observability**
   - Return structured results instead of calling `sys.exit`.
   - Emit per-feed status objects: success, partial, failed, skipped.
   - Add logging with enough context: category, source, URL, exception type, item counts.
   - Add retry and timeout controls around fetches.
   - Surface summary stats for each run.

6. **Strengthen attention/ranking**
   - Rank by a composite score, not just timestamp.
   - Start with:
     - recency
     - source reliability
     - duplicate suppression
     - optional source diversity cap
   - Group near-duplicate items by normalized title/link and keep the best representative.

7. **Correct time semantics**
   - Use timezone-aware datetimes end to end.
   - Derive Unix timestamps with `datetime.timestamp()` from aware datetimes, not `time.mktime`.
   - Compare “today” in the configured timezone, not the host machine timezone.
   - Store ISO 8601 timestamps in addition to Unix seconds.

8. **Make storage safe**
   - Create directories with `os.makedirs(..., exist_ok=True)`.
   - Write JSON atomically via temp file + rename.
   - Add a schema version field to stored files.
   - Handle corrupt files with backup/rebuild behavior.
   - Consider SQLite if concurrent runs or larger scale matter.

9. **Make the system operable**
   - Move hard-coded settings into config: timezone, timeout, retention, fetch frequency, user agent, max items per feed.
   - Define a clear library API and CLI behavior.
   - Add tests for:
     - timestamp parsing
     - deduplication collisions
     - malformed feeds
     - config merge behavior
     - persistence across runs

If you want, I can turn this into a tighter stage-by-stage checklist table with `present / shallow / absent` for each of the six stages.