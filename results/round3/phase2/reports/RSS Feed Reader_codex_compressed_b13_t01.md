**Observations**

This system is a small RSS ingestion pipeline with basic persistence.

It currently does these things:

- **Perceive: present.** It reads RSS/Atom feeds from URLs defined in `feeds.json` and parses them with `feedparser.parse(url)`.
- **Cache: shallow.** It transforms feed entries into a normalized in-memory structure with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`. It also groups results per category and writes them to `rss_<category>.json`.
- **Filter: shallow.** It drops entries that do not have a usable published/updated timestamp and skips entries whose timestamp parsing fails.
- **Attend: shallow.** It sorts entries by timestamp descending, so newer items appear first.
- **Remember: present but limited.** It persists fetched results to disk under `~/.rreader/`, and it persists feed configuration by copying or merging a bundled `feeds.json`.
- **Consolidate: absent.** Nothing in stored results changes how future runs behave.

Other working capabilities:

- Bootstraps a default feed config if the user does not already have one.
- Merges newly bundled categories into an existing user config.
- Supports fetching one category or all categories.
- Optionally shows author names instead of source names.
- Stores a `created_at` timestamp for each category snapshot.

**Triage**

Highest-priority gaps, in order:

1. **No durable item identity or deduplication**
   - Entry `id` is just the Unix timestamp. Multiple posts published in the same second will collide and overwrite each other in `rslt`.
   - There is no cross-run deduplication, so every run rebuilds the full snapshot instead of maintaining a stable item store.
   - This is the biggest correctness issue because it can silently lose data.

2. **No real filtering or quality control**
   - The only effective filter is “has a parseable date.”
   - It does not reject malformed URLs, duplicate links, empty titles, stale items, or bad feeds.
   - In production, this will admit noisy or broken content.

3. **Attention is only recency sort**
   - The system returns everything that survived date parsing.
   - There is no ranking beyond newest-first, no per-source balancing, and no suppression of near-duplicate headlines.
   - This becomes a usability problem as feed volume grows.

4. **Persistence model is snapshot-only**
   - `rss_<category>.json` is overwritten on each run.
   - There is no append-only history, no stable database, no metadata about fetch status, and no way to tell what changed since the last run.
   - This makes auditing, incremental processing, and downstream features harder.

5. **No consolidation / learning loop**
   - Stored results are never used to improve filtering, ranking, source trust, or fetch strategy.
   - The pipeline behaves identically every time.

6. **Weak operational robustness**
   - Broad bare `except:` blocks hide failures.
   - A single parse failure can call `sys.exit(...)` inside the fetch loop.
   - There are no retries, timeouts under explicit control, structured logs, feed health metrics, or tests.
   - This is a production-readiness gap rather than a conceptual-stage gap, but it matters.

7. **Time handling is brittle**
   - Output formatting compares feed-local converted time to `datetime.date.today()` in the process local timezone, not the configured timezone.
   - `time.mktime(parsed_time)` interprets the tuple in local system time, which can skew timestamps.
   - `TIMEZONE` is hardcoded to KST.
   - This can produce inconsistent ordering and display.

8. **Config and storage are minimal**
   - The code assumes `~/.rreader/` can be created with `os.mkdir`.
   - No schema/versioning for stored JSON.
   - No validation of `feeds.json` structure.
   - No atomic writes, so files can be corrupted on interruption.

Using your checklist directly:

- **Perceive:** present
- **Cache:** shallow
- **Filter:** shallow
- **Attend:** shallow
- **Remember:** shallow-to-present
- **Consolidate:** absent

The **first materially shallow stage is Cache**, because the stored representation does not provide stable lookup, indexing, or safe identity. That is the highest-priority fix.

**Plan**

1. **Fix cache identity and indexing**
   - Replace `id = ts` with a stable identifier derived from feed entry data, preferably:
     - `feed.id` if available
     - else canonicalized `feed.link`
     - else hash of `(source, title, published timestamp)`
   - Store entries in a structure keyed by stable ID, not by timestamp.
   - Keep secondary indexes for:
     - `timestamp`
     - `source`
     - `category`
     - `url`
   - Change the persisted format from a flat snapshot to something like:
     ```json
     {
       "entries_by_id": {...},
       "order": [...],
       "created_at": ...,
       "schema_version": 1
     }
     ```

2. **Add real filtering**
   - Introduce explicit validation rules before persistence:
     - require non-empty title
     - require valid absolute URL
     - reject duplicate URL or duplicate stable ID
     - optionally reject items older than a retention window
   - Track per-entry rejection reasons for debugging.
   - Replace silent `continue` paths with counted outcomes such as `accepted`, `rejected_missing_date`, `rejected_duplicate`, `rejected_bad_url`.

3. **Upgrade attention/ranking**
   - Separate filtering from ranking.
   - Keep recency as one signal, but add:
     - source diversity caps
     - duplicate headline suppression
     - optional source priority weights
   - Expose ranking logic in one function so it can evolve without changing ingestion.
   - Return both the full accepted set and the ranked display set if needed.

4. **Replace snapshot overwrite with durable storage**
   - Keep a persistent item store across runs instead of rewriting the category as only “latest fetch result.”
   - Minimum viable approach:
     - load previous store
     - merge newly fetched items by stable ID
     - mark `first_seen_at` and `last_seen_at`
   - Better production approach:
     - move from JSON files to SQLite
     - create tables for `feeds`, `entries`, `fetch_runs`, and `entry_sources`
   - This enables incremental updates, history, and reliable querying.

5. **Implement consolidation**
   - Use stored run history to update future behavior.
   - Concrete first steps:
     - mark feeds with repeated failures and back off fetch frequency
     - learn duplicate patterns from prior runs
     - track source reliability and use it in ranking
     - persist user interactions if available and feed them back into ranking
   - Put this in an explicit backward-pass step after fetch completion.

6. **Harden error handling and observability**
   - Replace bare `except:` with targeted exceptions.
   - Never `sys.exit()` from inside the per-feed loop; record failure and continue with other feeds.
   - Add structured logging fields:
     - category
     - source
     - url
     - items_seen
     - items_accepted
     - error type
   - Add retry and timeout policy around feed fetches.
   - Add tests for:
     - malformed feed data
     - duplicate timestamps
     - missing dates
     - config merge behavior

7. **Correct time semantics**
   - Use UTC internally for timestamps.
   - Replace `time.mktime(parsed_time)` with a timezone-safe UTC conversion.
   - Compute “today” in the configured display timezone, not system local time.
   - Make timezone configurable by user or environment, not hardcoded in code.

8. **Harden config and file writes**
   - Validate `feeds.json` against an expected schema before use.
   - Use recursive directory creation (`os.makedirs(..., exist_ok=True)`).
   - Write JSON atomically via temp file + rename.
   - Add `schema_version` to persisted files so format changes are manageable.

If you want, I can also rewrite this into a tighter stage-by-stage matrix with `present / absent / shallow` and a single recommended next implementation milestone.