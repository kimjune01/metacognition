**Observations**

This system is a basic RSS ingestion job with working forward flow through the early stages:

- `Perceive`: Present. It reads RSS URLs from `feeds.json`, fetches each feed with `feedparser.parse(url)`, and iterates through `d.entries`.
- `Cache`: Shallow. It converts feed entries into a normalized dict with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`, then sorts them and stores them in memory before writing JSON.
- `Filter`: Shallow. It rejects entries with missing or unparsable timestamps, and it deduplicates implicitly by using `timestamp` as the dict key. That is a weak filter because it only screens for parseability and accidental key collision.
- `Attend`: Present but shallow. It ranks entries by descending timestamp and returns all of them. There is ordering, but no real prioritization beyond recency and no diversity or redundancy control.
- `Remember`: Present. It writes per-category snapshots to `~/.rreader/rss_<category>.json` and persists feed configuration in `~/.rreader/feeds.json`.
- `Consolidate`: Absent. Stored results are never read back to improve later runs.

Other working capabilities:

- Initializes local storage directory `~/.rreader/`.
- Seeds bundled feeds into the user feed file on first run.
- Merges newly added bundled categories into an existing user config.
- Supports fetching either one category or all categories.
- Optionally substitutes feed author for source name with `show_author`.
- Formats timestamps into local display strings using a configured timezone.

**Triage**

Highest-priority gap: `Filter` is too weak.

- The first shallow stage is `Filter`, so this is the main production blocker.
- Deduplicating by Unix timestamp is incorrect. Two different articles published in the same second will overwrite each other.
- There is no validation of URL, title, link, content shape, feed health, or duplicate items across runs.
- Broad bare `except:` blocks hide failures and make bad data indistinguishable from transient errors.

Second: `Attend` is too weak.

- The system just returns everything sorted by time.
- A production reader needs relevance controls: caps, source balancing, duplicate suppression, stale-item handling, maybe scoring by recency/source/category.

Third: `Remember` is only snapshot persistence.

- It writes the latest run, but does not maintain durable history, fetch metadata, seen-item state, or incremental sync state.
- Because there is no persistent item identity, the system cannot reliably tell what is new versus already processed.

Fourth: `Consolidate` is missing entirely.

- The system does not learn from past fetches, user behavior, feed quality, or prior errors.
- It processes every run the same way.

Fifth: `Cache` needs to become a real queryable store.

- Current storage is just a JSON dump of the final list.
- There is no index, no retrieval API, no schema versioning, and no way to compare new data to old data except by rewriting the whole file.

Sixth: `Perceive` needs production hardening.

- No network timeout, retry, user agent, conditional requests, or structured error handling.
- Feed fetch failures can terminate execution or silently skip items.
- The timezone/date handling is inconsistent: display formatting compares against `datetime.date.today()` in local system time, not necessarily the configured timezone.

**Plan**

1. Strengthen `Filter` first.
- Replace `id = timestamp` with a stable item identity. Prefer `feed.id` or `feed.guid` when available; otherwise hash a tuple like `(feed.link, feed.title, published_time, source)`.
- Add validation rules before accepting an item:
  - require non-empty `title`
  - require valid `link`
  - require parseable publication or update time
  - optionally reject very old items on initial ingest windows
- Add duplicate detection on stable ID and canonicalized URL, not timestamp alone.
- Replace bare `except:` with specific exceptions and structured logging so rejected items are measurable.

2. Upgrade `Attend` from sort-only to real selection.
- Separate ranking from filtering.
- Introduce a scoring function, initially simple:
  - recency score
  - source freshness/health score
  - duplicate penalty
  - optional category-specific boosts
- Add output constraints:
  - maximum items per category
  - maximum items per source
  - near-duplicate suppression by normalized title or URL
- Keep the raw accepted pool and the selected output distinct so the decision process is inspectable.

3. Make `Remember` durable and incremental.
- Store items in a persistent database, preferably SQLite, instead of rewriting a single JSON list.
- Add tables for:
  - feeds
  - items
  - fetch runs
  - item-source associations if needed
- Persist fields such as `first_seen_at`, `last_seen_at`, `published_at`, `fetch_status`, `etag`, and `last_modified`.
- Mark whether an item is new, updated, or previously seen so later runs can behave incrementally.

4. Add `Consolidate`.
- On each run, read historical data before fetching/selection.
- Track feed reliability:
  - consecutive failures
  - empty fetch rate
  - parse error rate
  - duplicate rate
- Use that history to adapt:
  - deprioritize noisy or failing feeds
  - tune polling intervals
  - boost sources that consistently produce novel items
- If this is user-facing, add feedback signals like read/starred/hidden and use them in ranking.

5. Turn `Cache` into a real retrieval layer.
- Define a normalized schema for items and feeds instead of ad hoc dicts.
- Add indexes on `item_id`, `published_at`, `source`, and `category`.
- Keep raw feed payload fields that may be needed later, such as summary/content/authors/tags.
- Version the schema and add a migration path so stored data survives code upgrades.

6. Harden `Perceive`.
- Use a real HTTP client path with explicit timeout, retries, and a user agent if `feedparser` is not enough alone.
- Support conditional fetches with `ETag` and `Last-Modified` to reduce bandwidth and speed up polling.
- Handle per-feed failures without exiting the whole job.
- Normalize time handling:
  - convert all times to UTC for storage
  - convert to configured timezone only for presentation
  - compare “today” using the configured timezone, not host-local defaults

If you want, I can turn this into a stage-by-stage `present / shallow / absent` scorecard table next.