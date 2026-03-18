**Observations**

This script is a small RSS ingester. In its current form, it does work for a narrow single-user case:

- It bootstraps a user feed config at `~/.rreader/feeds.json` from the bundled `feeds.json` if the user config does not exist, and it merges in any newly added bundled categories later ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L81), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L83), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L90)).
- It can refresh either one category or all configured categories through `do(target_category=None, log=False)` ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L17), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L99), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L107)).
- For each feed URL, it parses RSS/Atom entries with `feedparser.parse(url)` and walks `d.entries` ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L22), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L27), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L35)).
- It extracts `published_parsed` or `updated_parsed`, converts that timestamp into the configured timezone, and formats display time as either `HH:MM` for today or `Mon DD, HH:MM` otherwise ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L38), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L41), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L49)).
- It emits a normalized JSON payload per category with `entries` and `created_at`, saved to `~/.rreader/rss_<category>.json` ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L72), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L74)).
- It supports a simple `show_author` flag that swaps source name for feed author when present ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L55)).
- It creates the storage directory on startup and has a default timezone constant (`UTC+9`) ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L121), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L127), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L135)).

**Triage**

Ranked by importance:

1. **Reliability and fault isolation are not production-safe.** Any exception during one feed fetch exits the whole process via `sys.exit()`; broad `except:` blocks discard the actual failure reason; there is no timeout, retry, HTTP status handling, or malformed-feed handling ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L23), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L32), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L46)).
2. **The dedupe/keying logic loses data.** Entries are keyed only by `timestamp` seconds, so two different posts published in the same second overwrite each other. In a multi-feed category, collisions are very plausible ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L53), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L68)).
3. **Time handling is inconsistent.** `at` is converted into `TIMEZONE`, but “today” is checked with `datetime.date.today()` in the machine’s local timezone, and `time.mktime(parsed_time)` interprets the struct as local time rather than UTC. Output can shift depending on host timezone ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L44), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L50), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L53)).
4. **Input and config validation are missing.** Unknown `target_category`, malformed `feeds.json`, missing `feed.link`, missing `feed.title`, or wrong config shape all raise uncaught errors or silently skip data ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L59), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L64), [rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L101)).
5. **Writes are not atomic.** It writes JSON directly to the destination path. A crash or concurrent run can leave a truncated or partially written file ([rreader.py](/Users/junekim/Documents/metacognition/results/round3/phase0b/sources/rreader.py#L74)).
6. **Observability is too weak for operations.** Logging is just `stdout` text. There are no per-feed error records, fetch stats, counts, latencies, or structured logs.
7. **The design is hard to test and extend.** Fetching, parsing, formatting, config bootstrapping, and file I/O are tightly coupled inside one function. There are no tests, types, or interfaces for mocking network and filesystem behavior.
8. **Scaling behavior is primitive.** All feeds are fetched sequentially, with no conditional requests (`ETag`/`Last-Modified`), no incremental state, and no concurrency. That is acceptable for a hobby tool, not for a larger feed set.

**Plan**

1. **Fix reliability first.**
   - Replace `feedparser.parse(url)` as the network boundary with an explicit HTTP client.
   - Add request timeout, retry-with-backoff, status-code checks, and per-feed exception handling.
   - Remove `sys.exit()` from feed-level code; return a result object like `{entries, errors, stats}` and continue processing other feeds.
   - Check `feedparser` parse health explicitly, including malformed feeds.

2. **Fix entry identity and dedupe.**
   - Stop using epoch seconds as the primary key.
   - Build a stable ID from feed URL plus entry GUID, or link, or `(title, published, source)` fallback.
   - Keep `timestamp` only for sorting, not uniqueness.
   - Persist dedupe state if you need incremental refreshes later.

3. **Normalize time correctly.**
   - Use timezone-aware UTC conversion consistently.
   - Replace `time.mktime(parsed_time)` with UTC-safe conversion.
   - Replace `datetime.date.today()` with `datetime.datetime.now(TIMEZONE).date()`.
   - Move timezone from hardcoded `UTC+9` into config, with a sane default.

4. **Add schema validation at the boundaries.**
   - Validate `feeds.json` on load: category exists, `feeds` is a mapping, each URL is a string.
   - Validate entry fields before emission and provide defaults or explicit skips with error reporting.
   - Make `target_category` failure return a clear user error instead of a raw `KeyError`.

5. **Make writes safe.**
   - Write output to a temp file in the same directory, then atomically rename.
   - Consider a file lock if concurrent refreshes are possible.
   - Create directories with `os.makedirs(..., exist_ok=True)` instead of one-level `os.mkdir`.

6. **Add operational visibility.**
   - Replace ad hoc `stdout` writes with structured logging.
   - Record per-run metrics: feeds attempted, feeds failed, entries parsed, entries emitted, elapsed time.
   - Emit machine-readable error output so callers can alert or retry intelligently.

7. **Refactor for maintainability.**
   - Split into functions or modules: config load, feed fetch, feed parse, entry normalize, output write.
   - Pull `get_feed_from_rss` out of `do()` so it can be tested directly.
   - Add type hints and tests for timestamp conversion, dedupe behavior, config merge logic, and partial failure handling.

8. **Then improve scale/performance.**
   - Fetch feeds concurrently with bounded parallelism.
   - Cache `ETag` and `Last-Modified` per feed and send conditional requests.
   - Skip rewriting unchanged category files when content is identical.

If you want, I can turn this into a production-readiness checklist or a patch plan against the actual `rreader.py` file.