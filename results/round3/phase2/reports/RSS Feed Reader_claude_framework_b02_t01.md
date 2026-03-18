# Diagnostic Report: RSS Reader System

## Observations

This system currently provides:

1. **RSS feed parsing** via feedparser for multiple feed sources organized by category
2. **Feed configuration management** with automatic copying of bundled defaults and category merging when new defaults are added
3. **JSON output** with normalized feed entries containing:
   - Unique timestamp-based IDs
   - Source attribution
   - Human-readable publication dates (relative: "12:34" today, "Mar 17, 12:34" otherwise)
   - Original URLs and titles
4. **Time zone awareness** with KST (UTC+9) localization for publication dates
5. **Deduplication** by timestamp across multiple sources within a category
6. **Sorted output** (newest first) stored in per-category JSON files (`rss_{category}.json`)
7. **Flexible author display** with per-category `show_author` toggle to use feed author or source name
8. **Error tolerance** that continues processing when individual feeds fail
9. **Optional logging** to track fetch progress
10. **Command-line and programmatic interfaces** supporting single-category or bulk refresh

## Triage

### Critical gaps (production blockers)

1. **No error persistence or retry strategy** — Failed feeds disappear silently; no record of what's broken or how often
2. **No rate limiting or request headers** — Will get blocked by any feed with anti-scraping measures; no User-Agent, no conditional GET with ETag/Last-Modified
3. **Blocking I/O without timeout** — `feedparser.parse()` can hang indefinitely on slow/dead endpoints
4. **Silent exception swallowing** — Bare `except:` blocks (lines 35, 47) hide bugs and make debugging impossible

### High-priority gaps (degrades user experience)

5. **No staleness detection** — Old cached data stays forever; users can't tell if a feed is 5 minutes or 5 days stale
6. **No feed health monitoring** — No way to know if a feed is consistently failing, moved, or dead
7. **No content hashing** — Feeds that republish with new timestamps cause duplicate entries
8. **Hardcoded timezone** — KST baked in; unusable for users in other regions
9. **No concurrency** — Sequential processing makes bulk refresh slow (20 feeds × 3s each = 60s)

### Medium-priority gaps (polish and maintainability)

10. **No schema validation** — Malformed feeds.json can crash the system with no helpful error
11. **No command-line help** — No `--help`, no usage documentation
12. **Timestamp collision handling** — Two entries at the same second overwrite each other in the dedup dict (line 72)
13. **No feed metadata** — Can't track feed title, description, icon, or last-build-date
14. **No entry content** — Only stores title/link; no summary, content, or enclosures
15. **No incremental updates** — Always fetches full feeds; wastes bandwidth on unchanged entries

## Plan

### For critical gaps

**1. Error persistence and retry**
- Add `rss_{category}_errors.json` to store failed fetch attempts with timestamp, URL, error type, and count
- Implement exponential backoff: skip feeds with 3+ consecutive failures for N minutes (5, 10, 20...)
- Log HTTP status codes, timeouts, and parse errors separately
- Add `last_success` timestamp to each feed in feeds.json

**2. Rate limiting and HTTP best practices**
- Add `User-Agent: rreader/1.0 (+https://example.com/bot.html)` header to all requests
- Pass `etag` and `modified` from previous fetch to feedparser for conditional GET (already supported by library)
- Store ETags and Last-Modified in per-feed metadata file
- Add `time.sleep(0.5)` between fetches to same domain (extract domain, group by it)

**3. Timeout protection**
- Add `socket.setdefaulttimeout(10)` at module level or wrap feedparser.parse in threading.Timer pattern
- Alternatively, switch to requests + feedparser.parse(requests.get(url, timeout=10).content)

**4. Structured error handling**
Replace bare except blocks:
```python
except feedparser.exceptions.FeedParserError as e:
    log_error(category, url, f"Parse error: {e}")
except requests.exceptions.Timeout:
    log_error(category, url, "Timeout after 10s")
except Exception as e:
    log_error(category, url, f"Unexpected: {type(e).__name__}: {e}")
    raise  # Re-raise in development mode
```

### For high-priority gaps

**5. Staleness detection**
- Add `fetched_at` timestamp to each entry (distinct from `pubDate`)
- In UI/output, flag entries where `pubDate` is >7 days old and `fetched_at` is recent (republished old content)
- Add `created_at` comparison: if current time - `created_at` > 1 hour, show "Last updated: X minutes ago"

**6. Feed health monitoring**
- In feeds.json, add per-feed stats: `consecutive_failures`, `success_rate_7d`, `last_success`, `last_error`
- Show warning in UI for feeds with `consecutive_failures` > 2
- Add `rreader doctor` command to list broken feeds

**7. Content hashing for deduplication**
- Add `content_hash` field: `hashlib.sha256((feed.title + feed.link).encode()).hexdigest()[:16]`
- Use `content_hash` as primary key instead of timestamp
- Keep timestamp as secondary sort key

**8. Configurable timezone**
- Move `TIMEZONE` from config.py to feeds.json as `"timezone": "Asia/Seoul"`
- Add CLI flag `--timezone` to override
- Use `zoneinfo.ZoneInfo(timezone_str)` instead of hardcoded timedelta (Python 3.9+)

**9. Concurrent fetching**
- Replace sequential loop with `concurrent.futures.ThreadPoolExecutor(max_workers=5)`
- Wrap each `feedparser.parse` call in a submitted function
- Collect results, merge, sort, write once at the end

### For medium-priority gaps

**10. Schema validation**
Add at startup:
```python
required_keys = {"feeds": dict}
optional_keys = {"show_author": bool}
for category, config in RSS.items():
    assert isinstance(config.get("feeds"), dict), f"{category}: 'feeds' must be dict"
```

**11. CLI help**
- Add argparse with `--category`, `--log`, `--help` flags
- Include usage example: `rreader --category tech --log`

**12. Collision handling**
- Change dict key from `entries["id"]` to `f"{ts}_{hash(feed.link)}"` to prevent overwrites
- Sort by numeric timestamp extracted from key

**13. Feed-level metadata**
- Store `d.feed.title`, `d.feed.subtitle`, `d.feed.image.href` in `rss_{category}_meta.json`
- Use in UI to show feed icons and descriptions

**14. Entry content storage**
- Add `summary` field: `feed.get("summary", "")[:500]` (truncate to 500 chars)
- Add `content` field if available: `feed.get("content", [{}])[0].get("value", "")`
- Add `enclosures` for podcasts: `[e.href for e in feed.get("enclosures", [])]`

**15. Incremental updates**
- Store previous `rss_{category}.json` as `rss_{category}_prev.json`
- On fetch, load previous entries
- Merge new entries with previous (keep up to 1000 most recent, configurable)
- Only write if new entries exist (compare content hashes)

---

**Priority order for implementation:**
1. Critical #4 (error handling) — enables debugging everything else
2. Critical #3 (timeouts) — prevents hangs in production
3. Critical #2 (rate limiting) — prevents getting blocked
4. High #9 (concurrency) — most visible UX improvement
5. High #5 (staleness) — users need to trust the data