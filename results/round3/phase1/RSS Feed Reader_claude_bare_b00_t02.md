# Diagnostic Report: RSS Feed Aggregation System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds from multiple sources using `feedparser`
2. **Multi-Category Support**: Organizes feeds into categories, each with its own set of source URLs
3. **Feed Normalization**: Extracts and normalizes entry metadata (title, URL, publish date, author, timestamp)
4. **Timezone Handling**: Converts UTC timestamps to KST (Seoul, UTC+9) for display
5. **Smart Date Formatting**: Shows time only for today's entries, full date for older entries
6. **Deduplication**: Uses timestamp-based keys to prevent duplicate entries within a category
7. **JSON Caching**: Stores parsed feeds as `rss_{category}.json` files in `~/.rreader/`
8. **Feed Configuration Management**: Maintains `feeds.json` with bundled defaults and user customizations
9. **Configuration Merging**: Automatically adds new categories from bundled feeds without overwriting user feeds
10. **Per-Category Author Display**: Supports `show_author` flag to display feed author vs. source name
11. **Recency Sorting**: Orders entries by timestamp (newest first)

## Triage

### Critical Gaps (Blocking Production Use)

1. **No Error Recovery**: Silent failures and broad `except:` clauses hide problems
2. **No Rate Limiting**: Will trigger 429 errors or IP blocks with frequent polling
3. **No Stale Data Handling**: No TTL mechanism; unclear when to refresh vs. use cache
4. **No Concurrency**: Sequential fetching is slow with many feeds (10+ sources could take 30-60s)

### High Priority Gaps (Poor UX/Reliability)

5. **No HTTP Timeouts**: Hangs indefinitely on unresponsive feeds
6. **No Validation**: Malformed feed JSON or missing fields cause crashes
7. **No Retry Logic**: Transient network failures (DNS, connection resets) fail permanently
8. **No User Feedback**: `do()` returns data but provides no status to caller (except optional log mode)
9. **No Feed Health Monitoring**: Can't detect consistently failing feeds to alert user

### Medium Priority Gaps (Maintenance/Observability)

10. **Weak Logging**: Only `sys.stdout.write` in log mode; no levels, no persistent logs
11. **No Metrics**: Can't track fetch latency, failure rates, or feed freshness
12. **Hardcoded Timezone**: KST is baked in; non-Korean users must edit code
13. **No Content Sanitization**: HTML in titles/authors could break downstream display

### Low Priority Gaps (Nice-to-Have)

14. **No Incremental Updates**: Always fetches full feed even if only 1-2 new entries
15. **No Search/Filter**: Can't query cached feeds (by keyword, date range, source)
16. **No Feed Discovery**: User must manually find and add RSS URLs

## Plan

### 1. Error Recovery
**Changes needed:**
- Replace bare `except:` at line 26 with `except Exception as e:` and log specific error
- Replace bare `except:` at line 47 with handling for `AttributeError` (missing time fields)
- Add feed-level error tracking: wrap feed processing in try/except, store `{"error": str(e), "failed_at": timestamp}` in output JSON for failed sources
- Return partial results when some feeds fail (don't exit early)

### 2. Rate Limiting
**Changes needed:**
- Add `requests.Session()` with `HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1))`
- Add `time.sleep(0.5)` between feed fetches to limit to ~2 requests/second
- Store `last_fetch_time` per feed in `feeds.json`; skip fetch if `< 15 minutes` since last attempt
- Add configurable `min_fetch_interval_seconds` to feed config (default: 900)

### 3. Stale Data Handling
**Changes needed:**
- Add `cache_ttl_seconds` field to category config in `feeds.json` (default: 1800)
- In `do()`, check `created_at` timestamp in cached JSON; skip fetch if `< cache_ttl_seconds` old
- Add `force_refresh=False` parameter to `do()` to bypass cache
- Return `{"entries": [...], "created_at": ts, "cache_hit": bool}` to indicate freshness

### 4. Concurrency
**Changes needed:**
- Replace sequential loop with `concurrent.futures.ThreadPoolExecutor(max_workers=5)`
- Wrap each `feedparser.parse(url)` call in a function that returns `(source, result_or_error)`
- Collect results with `executor.map()` or `as_completed()`
- Aggregate results into single `rslt` dict after all threads complete

### 5. HTTP Timeouts
**Changes needed:**
- Replace `feedparser.parse(url)` with `feedparser.parse(url, timeout=10)`
- Note: `feedparser` doesn't natively support timeout; must patch `urllib` or use `requests` with timeout then pass response to `feedparser.parse(response.text)`
- Wrap in `signal.alarm(15)` (Unix) or `threading.Timer` (cross-platform) as fallback

### 6. Validation
**Changes needed:**
- Add JSON schema validation for `feeds.json` on load (check required keys: category name, "feeds" dict)
- Add null checks: `if not d.entries: continue`
- Validate required fields before access: `if not hasattr(feed, 'link') or not hasattr(feed, 'title'): continue`
- Add `try/except JSONDecodeError` when reading cached JSON files

### 7. Retry Logic
**Changes needed:**
- Use `urllib3.Retry` with `status_forcelist=[429, 500, 502, 503, 504]`
- Add exponential backoff: `backoff_factor=2` → retries at 0s, 2s, 4s
- Add per-feed `failed_attempts` counter in cache; after 3 consecutive failures, mark feed as "degraded" and alert

### 8. User Feedback
**Changes needed:**
- Return structured status: `{"success": int, "failed": int, "skipped": int, "errors": [{"source": str, "error": str}]}`
- Add progress callback parameter: `do(..., progress_fn=None)` that calls `progress_fn(current, total, source_name)`
- Emit events for: fetch start, fetch complete, parse error, cache hit

### 9. Feed Health Monitoring
**Changes needed:**
- Add `health_status` field per feed in cache: `{"status": "healthy|degraded|failing", "last_success": ts, "consecutive_failures": int}`
- Update health on each fetch attempt
- Mark as "failing" after 5 consecutive failures
- Add `get_feed_health()` function that returns summary: `{"healthy": 10, "degraded": 2, "failing": 1}`

### 10. Logging
**Changes needed:**
- Replace `sys.stdout.write` with `logging` module
- Add log levels: `logger.info(f"Fetching {url}")`, `logger.error(f"Failed: {e}")`
- Configure file handler: `logging.FileHandler(p['path_data'] + 'rreader.log')`
- Add structured logging (JSON format) for programmatic analysis

### 11. Metrics
**Changes needed:**
- Add `metrics.json` file tracking: `{"fetch_count": int, "avg_latency_ms": float, "error_rate": float}`
- Record per-fetch timing: `start = time.time(); ...; latency = time.time() - start`
- Update rolling averages after each fetch
- Expose `get_metrics()` function for dashboard/monitoring

### 12. Timezone Configuration
**Changes needed:**
- Move `TIMEZONE` from `config.py` to `feeds.json` as top-level config: `{"timezone_offset_hours": 9, "categories": {...}}`
- Parse as: `TIMEZONE = datetime.timezone(datetime.timedelta(hours=config['timezone_offset_hours']))`
- Fallback to UTC if not specified

### 13. Content Sanitization
**Changes needed:**
- Add `import html` and call `html.unescape(feed.title)` to decode entities
- Use `bleach.clean(text, tags=[], strip=True)` to remove HTML tags from titles/authors
- Truncate excessively long titles: `title[:200] + '...' if len(title) > 200 else title`

### 14. Incremental Updates
**Changes needed:**
- Store `last_entry_timestamp` per feed in cache
- Pass `If-Modified-Since` header using stored `last_fetch_time`
- Check HTTP 304 response; if unchanged, return cached data without parsing
- Only process entries with `timestamp > last_entry_timestamp`

### 15. Search/Filter
**Changes needed:**
- Add `search_feeds(query, category=None, start_date=None, end_date=None)` function
- Load all cached JSON files, filter entries by: title contains query (case-insensitive), timestamp in range, category matches
- Return sorted merged results across categories

### 16. Feed Discovery
**Changes needed:**
- Add `discover_feed(url)` function that scrapes HTML for `<link rel="alternate" type="application/rss+xml">`
- Use `requests.get(url)` + `BeautifulSoup` to find feed links
- Return list of discovered feed URLs with titles
- Add `add_feed(category, source_name, feed_url)` helper that updates `feeds.json`