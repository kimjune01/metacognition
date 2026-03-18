**Observations**

This system is a basic RSS fetch-and-cache job.

- **Perceive: present.** It reads input from two places: `feeds.json` for configured feed URLs and the network via `feedparser.parse(url)` for RSS entries.
- **Cache: present but shallow.** It converts feed entries into a normalized dict with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`, sorts them by timestamp, and writes per-category JSON files like `rss_<category>.json`.
- **Filter: shallow.** It drops entries that lack parseable publish/update timestamps. It also deduplicates implicitly by using `timestamp` as the dict key, which suppresses collisions, but this is accidental and unsafe.
- **Attend: shallow.** It ranks only by recency. There is no scoring beyond timestamp, no limit, no diversity control across sources, and no handling for near-duplicate stories.
- **Remember: present but shallow.** It persists feed configuration and the latest fetched category snapshot to disk under `~/.rreader/`. State survives across runs.
- **Consolidate: absent.** Nothing in stored results changes future behavior. The fetch, filter, and ranking logic are fixed every run.

Working capabilities today:

- Bootstraps a user `feeds.json` from a bundled default.
- Merges in newly added bundled categories without overwriting user categories.
- Fetches one category or all categories.
- Extracts publication time, converts it to a configured timezone, and formats a display string.
- Writes category results to disk as JSON.
- Supports optional logging and optional author display.

**Triage**

Ranked by production importance:

1. **Filtering and identity are too weak.**
   - The system uses `timestamp` as the entry ID. Two different posts published in the same second collide, so one can overwrite the other.
   - There is no URL validation, content validation, duplicate detection by link/title/guid, or malformed-feed handling beyond broad `except`.
   - This is the first clearly shallow stage and the highest-priority fix.

2. **Error handling and observability are not production-safe.**
   - Broad bare `except` hides failure causes.
   - `sys.exit(" - Failed\n" if log else 0)` can terminate the whole run on one bad source.
   - No structured logs, retry policy, timeout control, or per-feed failure reporting.

3. **Remember exists only as snapshot overwrite, not durable history.**
   - Each run replaces `rss_<category>.json`; there is no accumulation of prior items, no fetch history, no watermark/last-seen state, and no way to tell what changed since last run.

4. **Attend is too naive.**
   - Sorting by timestamp alone is acceptable for a toy reader but weak for production.
   - No per-source balancing, duplicate clustering, stale-item suppression, item limits, or user-defined ranking.

5. **Consolidation is missing entirely.**
   - Stored results do not feed back into future fetch or ranking behavior.
   - No learned preferences, no adaptive suppression of noisy feeds, no source quality scoring.

6. **Time and parsing semantics are fragile.**
   - `datetime.date.today()` uses local system date, not the configured timezone, so “today” formatting can be wrong.
   - `time.mktime(parsed_time)` assumes local time semantics and is unsafe for UTC/feed timestamps.
   - Missing or inconsistent timezone handling will produce subtle bugs.

7. **Storage and schema are underspecified.**
   - JSON snapshots are fine initially, but there is no schema versioning, atomic write, locking, corruption recovery, or indexed retrieval.
   - Queryability is minimal: the system stores arrays, not a searchable store.

8. **Configuration and runtime controls are minimal.**
   - No per-feed options, rate limiting, user-agent configuration, disabled-feed state, or secrets/proxy support.
   - No CLI/reporting around what changed.

**Plan**

1. **Fix identity and filtering first.**
   - Replace `id = timestamp` with a stable unique key derived in priority order from `feed.id`/GUID, canonicalized `feed.link`, or a content hash of `(source, title, link, published)`.
   - Add explicit validation for required fields: `title`, `link`, parseable date.
   - Add duplicate detection rules based on canonical URL and normalized title, not timestamp collision.
   - Record rejected items with reasons so filter quality can be inspected.

2. **Make failure handling per-feed and explicit.**
   - Replace bare `except` with targeted exceptions around file I/O, JSON decoding, and feed parsing.
   - Do not exit the whole process because one feed fails; capture per-source status and continue.
   - Return a result object per feed/category with counts for fetched, accepted, rejected, and failed items.
   - Add structured logging with source URL, exception type, and message.

3. **Turn snapshot persistence into durable memory.**
   - Store entries incrementally instead of overwriting the full category file each run.
   - Maintain per-category state for `last_seen_ids`, `last_fetch_at`, and per-feed fetch status.
   - Preserve historical entries so downstream code can compare current vs previous runs.
   - If staying on JSON, split into state files with append/merge semantics; preferably move to SQLite for indexed lookup and history.

4. **Upgrade attention/ranking.**
   - Keep recency as one factor, but add source balancing and deduplication before ranking.
   - Introduce configurable result limits per category.
   - Cluster items with the same canonical URL or highly similar titles and keep one representative.
   - Make ranking policy explicit in code so it can evolve independently from fetch/parsing.

5. **Add consolidation as a backward pass.**
   - Persist signals such as click/read state, duplicate frequency, source failure rate, and source novelty.
   - Use those signals to modify future ranking or filtering, for example downrank chronically noisy feeds or prioritize sources with historically unique items.
   - Store these learned metrics separately from raw entries so policy can change without data loss.

6. **Correct time handling.**
   - Compare “today” using the configured timezone, not `datetime.date.today()`.
   - Replace `time.mktime(parsed_time)` with timezone-safe timestamp derivation from the parsed UTC-aware `datetime`.
   - Normalize all stored timestamps to UTC epoch plus a separate display-format layer.

7. **Harden storage.**
   - Write files atomically via temp file + rename.
   - Add schema version metadata to stored files.
   - Handle corrupted JSON with recovery behavior instead of crashing.
   - If query volume or history matters, migrate to SQLite with indexes on category, timestamp, canonical URL, and source.

8. **Expand production controls.**
   - Add feed-level config fields: enabled/disabled, timeout, polling interval, custom headers/user-agent, and source priority.
   - Validate config on startup and report invalid categories/feeds clearly.
   - Expose a CLI or API response that shows changed items since last run, not just the latest full dump.

If you want, I can turn this into a stage-by-stage checklist table (`present` / `absent` / `shallow`) or rewrite it as an engineering ticket set.