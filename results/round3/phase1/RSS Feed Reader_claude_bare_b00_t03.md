# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a basic RSS feed aggregation pipeline with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS/Atom feeds using `feedparser` library
2. **Multi-source Aggregation**: Processes multiple feed URLs organized by categories from a JSON configuration file
3. **Timestamp Normalization**: Converts published/updated dates to a configurable timezone (currently hardcoded to UTC+9/KST)
4. **Human-readable Dates**: Formats timestamps as "HH:MM" for today or "MMM DD, HH:MM" for older entries
5. **Deduplication**: Uses timestamp as ID to avoid duplicate entries (with collision risk)
6. **Sorted Output**: Orders entries by timestamp (newest first) within each category
7. **JSON Persistence**: Saves processed feeds to `~/.rreader/rss_{category}.json`
8. **Configuration Management**: 
   - Copies bundled `feeds.json` template on first run
   - Merges new categories from bundled config into user config on updates
9. **Optional Author Display**: Supports per-category `show_author` flag to display feed author vs source name
10. **Selective Updates**: Can refresh a single category or all categories

## Triage

### Critical Gaps
1. **No Error Recovery**: Silent failures lose entire feeds; partial failures aren't reported
2. **No Rate Limiting**: Concurrent requests could trigger 429 responses or IP bans
3. **No Caching Strategy**: Re-fetches all feeds every run, wasting bandwidth and stressing servers
4. **Timestamp Collisions**: Using Unix timestamp as ID means multiple posts at the same second overwrite each other

### High Priority
5. **No HTTP Timeout Configuration**: Slow/hanging feeds block the entire refresh cycle
6. **Missing Content Extraction**: Only stores title/link, not feed description/summary
7. **No Feed Validation**: Doesn't verify feed health (404s, malformed XML, SSL errors)
8. **Hardcoded Timezone**: TIMEZONE should be user-configurable, not code-level constant
9. **No Logging Infrastructure**: `log=True` writes to stdout; no rotation, levels, or file output

### Medium Priority
10. **No Retry Logic**: Network blips cause permanent feed loss for that cycle
11. **Missing User-Agent**: Some feeds block feedparser's default UA
12. **No Feed Metadata**: Doesn't track last-modified, ETag for conditional requests
13. **No Entry Limits**: Large feeds consume unbounded memory/disk
14. **Synchronous I/O**: Blocks on each feed sequentially; no parallelization

### Low Priority
15. **No Data Migration**: Schema changes break existing JSON files
16. **Missing CLI Interface**: Can't easily trigger refreshes or add feeds from terminal
17. **No OPML Import/Export**: Standard feed format not supported
18. **No Read/Unread Tracking**: Can't mark entries as consumed

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Wrap `feedparser.parse()` in try-except to catch network/parse errors
- Log specific exception types (ConnectionError, Timeout, ParseError) with feed URL
- Continue processing remaining feeds instead of `sys.exit()`
- Add `"error": "reason"` field to category JSON when feeds fail
- Return success/failure summary: `{"fetched": 12, "failed": 3, "errors": [...]}`

**Example:**
```python
errors = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        if d.bozo:  # feedparser's error flag
            errors.append({"source": source, "error": str(d.bozo_exception)})
            continue
    except Exception as e:
        errors.append({"source": source, "error": str(e)})
        continue
```

### 2. Rate Limiting (Critical)
**Changes needed:**
- Add configurable delay between requests: `time.sleep(FEED_DELAY)` (default 0.5s)
- Implement token bucket or sliding window for per-domain limits
- Add `requests_per_minute` to feeds.json per category
- Track request timestamps per domain in memory

### 3. Conditional Requests & Caching (Critical)
**Changes needed:**
- Store `Last-Modified` and `ETag` headers per feed in `cache_{category}.json`
- Pass headers to feedparser: `feedparser.parse(url, etag=..., modified=...)`
- Check `d.status` == 304 (Not Modified) and skip processing
- Only write JSON if new entries exist
- Add `"last_checked"` and `"cache_hit"` fields to output

### 4. Unique Entry IDs (Critical)
**Changes needed:**
- Generate ID from hash: `hashlib.sha256(f"{feed.link}{ts}".encode()).hexdigest()[:16]`
- Or use feed's native GUID: `feed.id` (fallback to link+timestamp)
- Store entries in dict keyed by stable ID before deduplication

### 5. HTTP Timeout Configuration (High)
**Changes needed:**
- Add to feeds.json: `"timeout": 30`
- Pass to feedparser via requests session:
```python
import requests
session = requests.Session()
session.timeout = RSS[category].get("timeout", 30)
d = feedparser.parse(url, request_headers={'User-Agent': USER_AGENT}, session=session)
```

### 6. Content Extraction (High)
**Changes needed:**
- Add to entries dict:
```python
"summary": feed.get('summary', ''),
"content": feed.get('content', [{}])[0].get('value', ''),
"image": feed.get('media_thumbnail', [{}])[0].get('url', '')
```
- Sanitize HTML if storing content (use `bleach` library)

### 7. Feed Health Monitoring (High)
**Changes needed:**
- Track consecutive failures per feed: `failures.json` → `{"url": {"count": 3, "last_error": "..."}}`
- After 5 consecutive failures, mark feed as `"status": "degraded"`
- Add HTTP status code to error logging
- Implement exponential backoff for failing feeds

### 8. User-Configurable Timezone (High)
**Changes needed:**
- Add `"timezone": "Asia/Seoul"` to feeds.json root
- Replace hardcoded TIMEZONE with:
```python
import zoneinfo
tz_name = RSS.get("timezone", "UTC")
TIMEZONE = zoneinfo.ZoneInfo(tz_name)
```

### 9. Structured Logging (High)
**Changes needed:**
- Replace stdout writes with `logging` module:
```python
import logging
logging.basicConfig(filename=p["path_data"] + "rreader.log", 
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')
logger.info(f"Fetching {url}")
```
- Add log rotation with `RotatingFileHandler` (10MB, 5 backups)

### 10. Retry Logic (Medium)
**Changes needed:**
- Wrap fetch in retry decorator:
```python
from tenacity import retry, stop_after_attempt, wait_exponential
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
def fetch_feed(url):
    return feedparser.parse(url)
```

### 11. Custom User-Agent (Medium)
**Changes needed:**
- Add to feedparser.parse(): `agent="rreader/1.0 (+https://github.com/yourproject)"`
- Make UA configurable in feeds.json

### 12. Conditional Request Metadata (Medium)
**Changes needed:**
- Store per feed: `last_modified`, `etag`, `last_fetch_time` in `feed_metadata.json`
- Check `d.headers.get('last-modified')` and `d.headers.get('etag')` after parse

### 13. Entry Limits (Medium)
**Changes needed:**
- Add to feeds.json: `"max_entries": 100`
- Slice entries list: `rslt["entries"] = rslt["entries"][:max_entries]`
- Add `"total_entries"` field before truncation for user awareness

### 14. Parallel Fetching (Medium)
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor`:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_feed, url): source for source, url in urls.items()}
    for future in as_completed(futures):
        source = futures[future]
        try:
            result = future.result()
        except Exception as e:
            errors.append({source: str(e)})
```

### 15-18. Lower Priority Features
These require more significant architectural changes:
- **CLI**: Add `argparse` with subcommands: `rreader refresh`, `rreader add <url>`, `rreader list`
- **OPML**: Use `xml.etree.ElementTree` to parse `<outline>` tags
- **Read tracking**: Add `read_entries.json` with entry IDs, expose mark-read API
- **Migrations**: Version feeds.json schema, add migration scripts in `migrations/` directory