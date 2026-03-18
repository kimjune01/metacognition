**Observations**

This system is a basic RSS ingester and snapshot writer.

It currently does these things:

- **Perceive: present.** It reads RSS/Atom feeds from configured URLs using `feedparser.parse(url)`.
- **Cache: shallow.** It transforms each feed item into a normalized dict with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`, then sorts entries by timestamp.
- **Filter: shallow.** It rejects some malformed items implicitly:
  - skips entries without `published_parsed` or `updated_parsed`
  - skips entries whose timestamp parsing fails
  - deduplicates only by timestamp because `rslt[entries["id"]] = entries`
- **Attend: shallow.** It applies one ranking rule: reverse sort by timestamp, newest first.
- **Remember: present but shallow.** It persists per-category snapshots to `~/.rreader/rss_<category>.json` and keeps feed configuration in `~/.rreader/feeds.json`.
- **Consolidate: absent.** Nothing in stored results affects future ingestion, filtering, ranking, or source handling.

Other working capabilities:

- Bootstraps a default `feeds.json` into the user data directory.
- Merges newly bundled categories into the user’s existing config.
- Supports fetching a single category or all categories.
- Optionally logs URL fetch progress.
- Supports choosing author display from either source name or feed author.
- Converts feed timestamps to a configured timezone before formatting display text.

**Triage**

Ranked by importance, the main gaps are:

1. **No reliable filtering or deduplication**
   - The first serious weakness is stage 3.
   - Deduping by timestamp is incorrect: different articles published in the same second can overwrite each other.
   - There is no URL validation, title validation, duplicate detection across runs, content sanity check, or source-level rejection policy.
   - In production this will cause dropped items, duplicate items, and low-quality entries.

2. **No durable item-level memory**
   - It writes only the latest snapshot for each category.
   - The system does not know what it has already seen, emitted, or failed on.
   - A production system needs persistent history, not just a regenerated view.

3. **No consolidation / learning loop**
   - The system never updates source trust, dedupe rules, ranking behavior, or retry behavior from past results.
   - It will behave the same forever, even if some feeds are noisy, broken, or redundant.

4. **Weak attention / ranking**
   - Ranking is just recency.
   - There is no diversity, source balancing, duplicate-cluster collapse, freshness decay policy, or category-specific prioritization.
   - In production, returning “everything in reverse chronological order” is usually not enough.

5. **Fragile error handling and observability**
   - Broad bare `except:` blocks hide failures.
   - One failed fetch can exit the process.
   - There is no structured logging, retry logic, timeout policy, metrics, or per-feed failure record.
   - Production systems need to fail partially, not opaquely.

6. **Storage and schema are too thin**
   - JSON snapshots are enough for a toy system, but not for querying, historical analysis, dedupe, or concurrent runs.
   - No versioned schema, no migration path, no atomic writes, no locking.

7. **Config and timezone handling are simplistic**
   - Timezone is hardcoded to KST despite the runtime environment potentially being elsewhere.
   - Feed config is assumed valid.
   - No per-feed options, disabled-state, polling intervals, auth, or source metadata.

8. **Input coverage is narrow**
   - It only uses feed metadata fields already exposed by the parser.
   - No support for feeds missing timestamps, no fallback identifiers, no extraction of summaries/content, and no support for other ingestion paths.

**Plan**

1. **Add real filtering and deduplication**
   - Introduce a stable item identity, in priority order:
     - feed-provided GUID/ID
     - canonicalized URL
     - hash of `(source, title, published time)`
   - Replace `id = ts` with a real unique key.
   - Add validation rules:
     - require non-empty title
     - require valid URL
     - reject entries older than a configured horizon if desired
     - reject malformed dates or impossible timestamps
   - Add duplicate detection:
     - within a run
     - across previous runs
     - near-duplicate title matching if feeds repost the same article
   - Record rejection reasons so developers can inspect what the filter is doing.

2. **Replace snapshot-only memory with durable history**
   - Persist items as records, not just one regenerated list.
   - Store at least:
     - stable item ID
     - category
     - source
     - raw feed metadata
     - first_seen_at
     - last_seen_at
     - published_at
     - fetch_run_id
     - status flags such as `accepted`, `rejected`, `emitted`
   - Keep the output snapshot as a derived artifact, not the primary store.
   - Use SQLite for a small production version; it is enough for indexing, uniqueness constraints, and historical queries.

3. **Add a consolidation loop**
   - Read historical outcomes before each run.
   - Update source and ranking behavior based on stored results:
     - suppress sources with repeated parse failures
     - down-rank feeds with high duplicate rates
     - learn preferred sources per category
     - track item engagement if that signal exists later
   - Start simple: source reliability score + duplicate rate + failure streak.
   - Make these adjustments explicit and inspectable rather than opaque ML.

4. **Improve attention / ranking**
   - Split filtering from ranking clearly.
   - After filtering, score items using multiple factors:
     - recency
     - source reliability
     - source diversity
     - duplicate-cluster representative choice
     - category-specific boost rules
   - Enforce diversity constraints so one source does not dominate.
   - Collapse near-duplicate entries into clusters and rank the cluster, then choose one representative item.

5. **Make fetch and parse failures recoverable**
   - Replace bare `except:` with specific exceptions.
   - Never `sys.exit` from inside per-feed processing.
   - Return structured per-feed results:
     - success/failure
     - item count
     - error type
     - latency
   - Add:
     - request timeout policy
     - retry with backoff for transient errors
     - warning logs for partial failures
     - run summary at the end
   - Keep processing other feeds even if one feed fails.

6. **Strengthen storage and writes**
   - If staying with JSON temporarily:
     - write to a temp file and atomically rename
     - add schema version
     - separate raw ingest data from rendered output
   - Prefer moving to SQLite with:
     - `items` table
     - `sources` table
     - `runs` table
     - indexes on `item_id`, `category`, `published_at`, `first_seen_at`
     - uniqueness constraint on stable item ID

7. **Harden configuration**
   - Validate `feeds.json` on load.
   - Support per-feed settings:
     - enabled/disabled
     - polling interval
     - timezone override if needed
     - author display preference
     - dedupe policy
   - Remove hardcoded timezone from code and load it from config or system settings.
   - Handle missing categories and malformed feed definitions gracefully.

8. **Expand ingestion robustness**
   - Preserve raw parser output or selected raw fields for debugging.
   - Add fallback behavior when feeds omit publish times:
     - use updated time
     - use first-seen time with a lower-confidence flag
   - Normalize URLs before storing.
   - Optionally capture summaries/content fields for later ranking and dedupe quality.

The highest-priority fix is the first shallow stage: **Filter**. Right now the system can ingest and store, but it cannot reliably decide what should count as a valid unique item. That is the first place to strengthen before adding smarter ranking or learning.