# Diagnostic Report: RSS Reader System

## Observations

This system is a **working RSS feed aggregator** with the following capabilities:

1. **Feed Parsing**: Downloads and parses RSS/Atom feeds using `feedparser`
2. **Multi-Category Support**: Organizes feeds into categories defined in `feeds.json`
3. **Data Persistence**: Caches parsed feed data as JSON files (`rss_{category}.json`) in `~/.rreader/`
4. **Time Handling**: Converts feed timestamps to Korean Standard Time (UTC+9) with human-friendly display
5. **Configuration Management**: 
   - Bootstraps initial config from bundled `feeds.json`
   - Preserves user customizations while adding new bundled categories on updates
6. **Flexible Author Display**: Can show feed source name or individual post authors per category
7. **Selective Updates**: Can refresh a single category or all categories
8. **Basic Error Handling**: Catches parse failures and missing timestamps

## Triage

### Critical Gaps (Production Blockers)

1. **No Error Recovery** - Silent failures lose data without user awareness
2. **Missing CLI/UI** - No way for users to interact with cached data
3. **No Logging Infrastructure** - Debug flag prints to stdout, nothing persists
4. **Unsafe File Operations** - Race conditions and corruption risks

### High Priority (User Experience)

5. **No Update Scheduling** - Manual refresh only, no automatic polling
6. **No Read/Unread Tracking** - Can't remember what user has seen
7. **Missing Feed Management** - Can't add/remove feeds without editing JSON
8. **No Network Resilience** - Doesn't handle timeouts, rate limits, or 429s

### Medium Priority (Polish)

9. **Duplicate Detection Issues** - Uses timestamp as ID, collisions likely
10. **No Content Caching** - Re-fetches full feeds even if unchanged (no ETag/Last-Modified)
11. **Limited Metadata** - Doesn't store descriptions, images, categories from feeds
12. **Hardcoded Timezone** - KST is baked in, not configurable

### Low Priority (Nice to Have)

13. **No Analytics** - Can't track feed health, update frequency, error rates
14. **No Import/Export** - Can't share feed lists in OPML format
15. **No Search** - Can't find articles by keyword across cached data

## Plan

### 1. Error Recovery
**Changes needed:**
- Wrap `feedparser.parse()` in try/except, catch `URLError`, `HTTPError`, `socket.timeout`
- Log failures to `~/.rreader/errors.log` with timestamp, feed URL, exception type
- Continue processing remaining feeds instead of `sys.exit()`
- Return partial results with error count in metadata
- Add retry logic with exponential backoff (3 attempts with 1s, 2s, 4s delays)

### 2. CLI/UI Layer
**Changes needed:**
- Create `cli.py` with commands:
  - `rreader list [category]` - show cached articles
  - `rreader refresh [category]` - update feeds
  - `rreader add <url> <category>` - add new feed
  - `rreader remove <url>` - remove feed
- Use `click` or `argparse` for command parsing
- Add `--format` flag for output (table, JSON, minimal)
- Pipe to pager for long lists (detect TTY, use `less` if available)

### 3. Logging Infrastructure
**Changes needed:**
- Replace `print` statements with `logging` module
- Create `~/.rreader/rreader.log` with rotation (keep 5 files × 10MB)
- Log levels: DEBUG for parsing details, INFO for successful updates, WARNING for recoverable errors, ERROR for failures
- Add `--verbose` flag to control console output
- Include: timestamp, level, category, feed URL, entry count

### 4. Safe File Operations
**Changes needed:**
- Write to temp file first: `rss_{category}.json.tmp`
- Use `os.fsync()` before rename to ensure disk write
- Atomic rename with `os.replace()` (overwrites atomically on POSIX)
- Add file locking with `fcntl.flock()` (Unix) / `msvcrt.locking()` (Windows)
- Validate JSON structure before writing (schema check)

### 5. Update Scheduling
**Changes needed:**
- Add `scheduler.py` with APScheduler or simple cron integration
- Store last update time per category in `feeds.json`: `"last_updated": 1234567890`
- Add `update_interval` per category (default 3600 seconds)
- Implement daemon mode: `rreader daemon start/stop/status`
- Use systemd timer (Linux) or launchd (macOS) for system integration
- Add `--daemon` flag to run persistent background process

### 6. Read/Unread Tracking
**Changes needed:**
- Create `~/.rreader/read_state.json`: `{"article_url": {"read": true, "read_at": ts}}`
- Add `is_read` boolean to each entry in output
- CLI commands: `rreader mark-read <url>`, `rreader mark-all-read [category]`
- Filter option: `rreader list --unread-only`
- Cleanup old entries (>90 days) to prevent unbounded growth

### 7. Feed Management
**Changes needed:**
- Implement `feeds.py` module with CRUD operations:
  - `add_feed(url, category, name=None)` - validate URL, test parse, update `feeds.json`
  - `remove_feed(url)` - find in all categories, remove, update JSON
  - `list_feeds(category=None)` - show all configured feeds
  - `rename_category(old, new)` - update feeds.json and data files
- Validate feed URLs before saving (try to fetch and parse)
- Backup `feeds.json` before modifications to `feeds.json.backup`

### 8. Network Resilience
**Changes needed:**
- Add `requests` library for better HTTP control (feedparser uses urllib)
- Set timeout: `feedparser.parse(url, request_headers={...}, timeout=30)`
- Implement exponential backoff: `time.sleep(min(2 ** attempt, 60))`
- Respect `Retry-After` header on 429/503 responses
- Add rate limiting: max 1 request/second per domain (track in memory)
- Use connection pooling to reuse TCP connections

### 9. Duplicate Detection
**Changes needed:**
- Change ID from timestamp to: `hashlib.sha256(feed.link.encode()).hexdigest()[:16]`
- Fall back to: `hash(feed.title + feed.link)` if URL missing
- Check for duplicates before adding to results dict
- Keep first occurrence (usually most recent)
- Store `first_seen` timestamp separately from `published` timestamp

### 10. Content Caching (HTTP Conditional Requests)
**Changes needed:**
- Store ETag and Last-Modified headers in `feeds.json` per feed URL
- Pass headers to feedparser: `feedparser.parse(url, etag=..., modified=...)`
- Check `feed.status` - if 304, reuse cached data from previous run
- Update headers only when receiving 200 response
- Saves bandwidth and reduces load on feed servers

### 11. Extended Metadata
**Changes needed:**
- Add to entries dict:
  - `"summary"`: `feed.get('summary', '')[:500]` - truncate for storage
  - `"image"`: extract from `feed.media_thumbnail` or `feed.enclosures`
  - `"tags"`: `feed.get('tags', [])` - category labels from feed
  - `"content"`: full HTML content from `feed.content[0].value` if available
- Make fields optional in output (add `--full` flag for CLI)
- Consider storage size impact (full content can be large)

### 12. Configurable Timezone
**Changes needed:**
- Add `timezone` field to `feeds.json` root or per category
- Parse with `pytz` or `zoneinfo` (Python 3.9+): `ZoneInfo(user_tz)`
- Default to system timezone if not specified: `datetime.datetime.now().astimezone().tzinfo`
- CLI command: `rreader config set timezone "America/New_York"`
- Validate timezone string against IANA database

### 13. Analytics
**Changes needed:**
- Create `~/.rreader/stats.json` with:
  - Per-feed: success count, failure count, avg parse time, last error
  - Per-category: total entries, update frequency, data size
- Update on each refresh operation
- CLI command: `rreader stats [category/feed]` - show health dashboard
- Track trends: entries per day over last 30 days

### 14. OPML Import/Export
**Changes needed:**
- Add `opml.py` module using `xml.etree.ElementTree`
- `export_opml()` - generate OPML from `feeds.json` with outline elements
- `import_opml(file_path)` - parse OPML, extract feed URLs and categories
- CLI: `rreader export feeds.opml`, `rreader import feeds.opml`
- Handle nested categories (OPML folders) - flatten or preserve hierarchy

### 15. Search Functionality
**Changes needed:**
- Add `search.py` with function: `search_entries(query, category=None, field='title')`
- Load all `rss_*.json` files into memory
- Filter by: title, author, URL (regex or substring match)
- Return sorted by relevance (keyword count) and timestamp
- CLI: `rreader search "python" --category tech --in title,summary`
- Consider indexing with SQLite FTS5 for large datasets (>10k articles)