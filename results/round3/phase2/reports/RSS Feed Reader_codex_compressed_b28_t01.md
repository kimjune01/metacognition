**Observations**

This system is an RSS fetch-and-store pipeline with basic category support.

- **Perceive: present.** It ingests data from external RSS URLs using `feedparser.parse(url)`. Feed URLs come from `feeds.json`, either bundled or copied into the user data directory on first run.
- **Cache: shallow.** It converts feed entries into a normalized in-memory dict with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`. It also sorts entries newest-first and writes them to `rss_<category>.json`.
- **Filter: shallow.** It rejects entries with no parseable published/updated time, and later deduplicates by integer timestamp because `rslt[entries["id"]] = entries` overwrites collisions. That is a very weak filter and an unsafe dedupe key.
- **Attend: shallow.** It ranks only by recency. There is no scoring beyond timestamp, no source balancing, and no redundancy suppression except accidental timestamp collision.
- **Remember: present but shallow.** It persists feed configuration and per-category output JSON to `~/.rreader/`. It can reuse the feed list and keep the latest fetched result on disk.
- **Consolidate: absent.** Nothing learned from prior runs changes future behavior. No source health tracking, no duplicate memory, no quality feedback, no adaptive ranking.

Other working capabilities:

- Bootstraps a user feed config by copying bundled defaults.
- Merges newly added bundled categories into an existing user config.
- Supports optional per-category author display.
- Handles all categories or one selected category.
- Converts feed timestamps into a fixed configured timezone.

**Triage**

Highest-priority gap is the first weak stage: **Cache**.

1. **Cache is too weak for reliable retrieval and comparison.**
   - Entries are stored as a flat list per run, not as a queryable index.
   - Deduplication uses `timestamp` as the ID, so unrelated articles published in the same second can overwrite each other.
   - There is no stable identity from entry GUID, URL, or content hash.
   - Result: the system cannot safely compare new vs old items, track updates, or support downstream selection well.

2. **Filter is missing production-grade validation and deduplication.**
   - It accepts almost everything with a timestamp.
   - No URL validation, title validation, duplicate suppression across runs, malformed feed handling, or stale-entry filtering.
   - Bare `except:` hides failures and can terminate the whole process.
   - Result: low-quality or duplicate items can pollute output, and failures are opaque.

3. **Attend is minimal and unsuitable for larger feeds.**
   - Selection is just reverse chronological order.
   - No cap per source, no diversity enforcement, no scoring by freshness/source priority, no handling of near-duplicate headlines.
   - Result: output quality degrades as volume grows.

4. **Remember exists, but only as last-run snapshots.**
   - It writes the current category output, but does not maintain durable article history, fetch metadata, source status, or incremental state.
   - Result: no notion of “already seen,” “new since last run,” or source reliability.

5. **Consolidate is absent.**
   - The system never updates rules or parameters based on past outcomes.
   - Result: it cannot improve ranking, blacklist bad sources, or tune fetch behavior.

6. **Operational robustness is far below production needs.**
   - No retries, timeouts, structured logging, metrics, tests, schema versioning, locking, or atomic writes.
   - Uses a hard-coded timezone comment/config mismatch model rather than per-user or per-feed handling.
   - Result: fragile in real deployments, especially under partial failure or concurrent runs.

**Plan**

1. **Fix Cache first**
   - Introduce a stable article identity.
   - Prefer feed GUID/`id`; fall back to canonicalized URL; last resort: hash of `(source, title, timestamp)`.
   - Store entries in a structured durable format keyed by article ID instead of timestamp.
   - Split storage into:
     - `feeds.json` for source config
     - `articles.json` or SQLite table for normalized article records
     - `fetch_runs.json` or table for run metadata
   - Add fields like `article_id`, `feed_category`, `feed_source`, `fetched_at`, `raw_published_at`, `normalized_url`, and `seen_count`.
   - If staying on JSON, maintain an index by ID plus per-category article lists. For production, move to SQLite.

2. **Build a real Filter stage**
   - Add explicit validation rules:
     - require non-empty title
     - require valid URL
     - require parseable timestamp or fallback rules
     - reject entries older than a configured horizon if desired
   - Add duplicate checks:
     - exact duplicate by stable article ID
     - near-duplicate by normalized title + source within a time window
   - Replace bare `except:` with specific exceptions and per-feed error handling.
   - Record rejected items with reasons for debugging.
   - Do not `sys.exit` inside the inner fetch loop; continue other feeds and return error summaries.

3. **Upgrade Attend into a real ranking step**
   - Separate “filter” from “ranking” in code.
   - Score items using explicit features, for example:
     - freshness
     - source priority
     - novelty
     - duplicate penalty
     - category-specific boosts
   - Enforce output constraints:
     - max items per source
     - max total items
     - near-duplicate suppression
   - Make ranking parameters configurable in the feed/category config.

4. **Strengthen Remember**
   - Persist article history across runs, not just the latest rendered list.
   - Track:
     - first seen time
     - last seen time
     - fetch success/failure per source
     - whether an item was already emitted
   - Write files atomically: write temp file then rename.
   - Add schema versioning so stored state can evolve safely.

5. **Add Consolidate**
   - Read historical state before fetching/ranking.
   - Use past runs to adapt:
     - lower trust or temporarily disable feeds with repeated parse failures
     - down-rank sources producing many duplicates
     - avoid re-emitting previously emitted items unless updated
   - Start simple: implement deterministic adaptive rules before anything ML-like.
   - Store these learned parameters in a separate state file or DB table.

6. **Harden operations**
   - Add network timeouts and retry/backoff around feed fetches.
   - Use structured logging instead of direct `stdout.write`.
   - Add tests for:
     - timestamp parsing
     - ID generation
     - deduplication
     - config bootstrap/merge
     - partial failure behavior
   - Add file locking or single-process protection if concurrent runs are possible.
   - Make timezone configurable per installation, ideally via settings rather than hard-coded constant.

If you want, I can turn this into a stage-by-stage checklist table (`present` / `absent` / `shallow`) or rewrite it as an engineering ticket list.