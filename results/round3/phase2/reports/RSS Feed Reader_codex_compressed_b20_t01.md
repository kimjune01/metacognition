**Observations**

This system is an RSS fetch-and-store pipeline.

It currently does these things:

- **Perceive: present.** It reads RSS/Atom feeds from URLs listed in `feeds.json` and ingests entries via `feedparser.parse(url)`.
- **Cache: shallow.** It converts feed items into a normalized dict with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`, then stores per-category results in `rss_<category>.json`.
- **Filter: shallow.** It drops entries that lack a parseable published/updated timestamp. It also collapses collisions by using the timestamp as the dict key, which incidentally deduplicates some items.
- **Attend: shallow.** It sorts surviving items by descending timestamp, so newer items come first.
- **Remember: present but limited.** It writes feed results to disk and preserves user feed configuration across runs, including merging in newly bundled categories.
- **Consolidate: absent.** Nothing in stored output affects future fetching, filtering, ranking, or configuration.

Other working capabilities:

- Initializes a local data directory at `~/.rreader/`.
- Seeds `feeds.json` from a bundled default if missing.
- Merges newly added bundled categories into an existing user `feeds.json`.
- Supports fetching either one category or all categories.
- Supports optional author display per category.
- Supports simple progress logging.
- Converts feed timestamps into a configured timezone before display formatting.

**Triage**

Ranked by importance:

1. **Filter is too weak and partly wrong.**
   - The first meaningful weak stage is **Filter**, so this is the highest-priority fix.
   - It only rejects items with missing/unparseable dates.
   - It does not validate required fields like `link` or `title`.
   - Deduplication is unsafe because `timestamp` is used as the item ID; two different posts published in the same second will overwrite each other.
   - Broad `except:` blocks hide malformed feeds and parser errors.

2. **Attend is too primitive.**
   - Ranking is just reverse chronological order.
   - There is no relevance scoring, source balancing, redundancy suppression, or per-category result limit.
   - Production output would get noisy fast.

3. **Remember is incomplete.**
   - Results are persisted, but the system does not retain item identity across runs in a useful way.
   - It overwrites each category snapshot instead of tracking seen items, fetch history, failures, or item state.
   - There is no durable metadata for incremental processing.

4. **Consolidate is entirely missing.**
   - The system never learns from past runs.
   - No adaptation of ranking, source trust, duplicate rules, or retry behavior.
   - No mechanism for promoting reliable feeds or suppressing consistently bad ones.

5. **Perceive lacks production ingestion robustness.**
   - No network timeout control, retry policy, user-agent configuration, rate limiting, or structured error handling.
   - A bad feed can terminate the whole process via `sys.exit`.
   - No monitoring around feed health.

6. **Cache is under-specified.**
   - The normalized schema is minimal and lossy.
   - It does not retain feed/category/source identifiers cleanly enough for downstream querying.
   - JSON files per category are workable for a toy system, but not for production querying, deduplication, or concurrency.

7. **Operational gaps outside the six stages.**
   - No tests.
   - No logging structure.
   - No config validation.
   - No atomic writes or file locking.
   - No schema versioning or migration path.

**Plan**

1. **Strengthen Filter**
   - Replace `timestamp` as the primary key with a stable item ID:
     - Prefer feed-provided `id`/`guid`.
     - Fallback to normalized `link`.
     - Final fallback to a hash of `(source, title, published_time)`.
   - Add explicit validation rules:
     - Require `title`, `link`, and a usable timestamp.
     - Reject malformed URLs.
     - Reject obviously stale or future-dated items outside a tolerance window.
   - Separate validation from parsing:
     - Build a `parse_entry(feed_entry, source)` function.
     - Build a `validate_entry(entry)` function returning either a normalized item or a rejection reason.
   - Replace bare `except:` with specific exceptions and record failures.

2. **Improve Attend**
   - Introduce a scoring step after filtering.
   - Rank using a composite score, for example:
     - recency
     - source priority
     - duplicate penalty
     - title similarity penalty
   - Add diversity controls:
     - max items per source in top N
     - collapse near-duplicate titles/links
   - Add configurable output limits per category.

3. **Upgrade Remember**
   - Persist more than the latest snapshot.
   - Add a durable store for:
     - known item IDs
     - first_seen / last_seen timestamps
     - fetch status per source
     - per-run metadata
   - At minimum, split storage into:
     - `feeds.json` for config
     - `items.jsonl` or SQLite table for items
     - `runs.jsonl` or table for fetch runs/errors
   - Avoid rewriting the whole category file as the only source of truth.

4. **Add Consolidate**
   - Read historical run/item data before fetching or ranking.
   - Use history to adjust behavior:
     - suppress items already seen
     - down-rank noisy sources
     - flag broken feeds for backoff
     - tune duplicate rules from prior collisions
   - Start with simple heuristics rather than ML:
     - source reliability score
     - per-source failure counters
     - seen-item suppression window

5. **Harden Perceive**
   - Wrap feed fetching in a dedicated fetch layer with:
     - timeout
     - retry with backoff
     - custom user agent
     - per-feed error isolation
   - Never call `sys.exit` from inside the fetch loop.
   - Return structured results such as `success`, `error_type`, `feed_url`, `items_seen`.
   - Continue processing other feeds when one fails.

6. **Make Cache production-grade**
   - Define a normalized schema explicitly:
     - `item_id`
     - `category`
     - `source`
     - `feed_url`
     - `title`
     - `url`
     - `published_at`
     - `fetched_at`
     - `author`
     - raw payload if needed
   - Move from ad hoc JSON objects to SQLite for indexing and querying.
   - Add indexes on `item_id`, `category`, `published_at`, and `source`.

7. **Fix operational reliability**
   - Use atomic writes for config/data files.
   - Add schema/version metadata to stored data.
   - Validate `feeds.json` structure on load.
   - Add tests for:
     - feed parsing
     - timestamp handling
     - deduplication
     - failure isolation
     - category merge behavior

The core diagnosis is: **Perceive works, Cache exists, but Filter is the first stage that is materially too weak.** That is the highest-leverage place to start. Once filtering and identity are fixed, ranking, persistence, and learning can be built on top of a stable pipeline.