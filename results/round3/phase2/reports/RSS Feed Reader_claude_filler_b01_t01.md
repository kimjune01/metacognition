# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-source Aggregation**: Handles multiple feeds per category, defined in a `feeds.json` configuration file
3. **Deduplication**: Uses timestamp-based keys to avoid duplicate entries from the same source
4. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
5. **Relative Time Display**: Shows "HH:MM" for today's entries, "Mon DD, HH:MM" for older ones
6. **Author Handling**: Supports optional author display per category via `show_author` flag
7. **Data Persistence**: Saves parsed feeds as JSON files in `~/.rreader/` directory
8. **Configuration Management**: Automatically copies bundled `feeds.json` on first run and merges new categories from updates
9. **Sorted Output**: Entries sorted by timestamp (newest first)
10. **Selective Updates**: Can refresh a single category or all categories
11. **Basic Error Handling**: Catches exceptions during parsing with optional logging

## Triage

### Critical Gaps (Must-Have for Production)

1. **No Error Recovery** - System fails silently or exits entirely when feeds are unavailable
2. **No Validation** - Malformed JSON or feed data can crash the system
3. **No Rate Limiting** - Could overwhelm feed servers or get IP-banned
4. **No Caching Strategy** - Re-fetches all content even if feeds haven't updated
5. **Security Vulnerabilities** - No URL validation, timeout controls, or size limits

### High Priority (Needed for Reliability)

6. **No Retry Logic** - Transient network failures cause permanent data loss for that update cycle
7. **No Monitoring** - No way to know if feeds are consistently failing
8. **No Concurrency** - Sequential fetching makes updates slow with many feeds
9. **No Data Migration** - JSON schema changes will break existing installations
10. **Bare Except Clauses** - `except:` without specifying exception types masks bugs

### Medium Priority (Quality of Life)

11. **No Feed Metadata** - Doesn't store feed titles, descriptions, or icons
12. **No Entry Content** - Only stores title/link, not summaries or full content
13. **No Incremental Updates** - Always processes all entries, not just new ones
14. **Limited Date Handling** - Falls back to nothing if both `published_parsed` and `updated_parsed` are missing
15. **No Read/Unread Tracking** - Can't mark items as read or filter viewed content

### Low Priority (Nice to Have)

16. **No Search/Filter** - No way to search across entries or filter by keyword
17. **No OPML Import/Export** - Standard feed list format not supported
18. **No Feed Discovery** - Can't auto-detect feeds from website URLs
19. **Hardcoded Timezone** - Requires code change to use different timezone
20. **No Statistics** - No metrics on feed health, update frequency, or entry counts

## Plan

### Critical Gap Remediation

**1. Error Recovery**
- Wrap each feed fetch in individual try-except blocks (line 24-41)
- On failure, load previous cached data from JSON file if available
- Continue processing remaining feeds instead of exiting
- Log failures to a separate error log file with timestamp

**2. Validation**
- Add JSON schema validation for `feeds.json` using `jsonschema` library
- Validate URLs using `urllib.parse` before fetching
- Check that required fields (`link`, `title`) exist in feed entries before accessing
- Add type checking for timestamp fields before calling `time.mktime()`

**3. Rate Limiting**
- Add `time.sleep()` between feed requests (start with 0.5-1 second)
- Track last fetch time per feed in metadata file
- Implement exponential backoff for feeds that repeatedly fail
- Respect HTTP 429 responses and `Retry-After` headers

**4. Caching Strategy**
- Check `If-Modified-Since` and `ETag` headers before fetching
- Store HTTP caching headers in JSON metadata alongside entries
- Only re-parse and save if feed content has changed
- Implement configurable cache expiration (e.g., 15 minutes for news, 1 hour for blogs)

**5. Security**
- Add `timeout` parameter to `feedparser.parse()` (e.g., 30 seconds)
- Validate URLs match `http://` or `https://` schemes only
- Set maximum feed size limit using `Content-Length` header checks
- Sanitize HTML in titles/content to prevent XSS if displayed in web UI

### High Priority Improvements

**6. Retry Logic**
- Implement 3-retry pattern with exponential backoff (1s, 2s, 4s delays)
- Use `requests` library with session for connection pooling
- Distinguish between network errors (retry) vs. 404s (skip)
- Store retry count in metadata to detect chronically failing feeds

**7. Monitoring**
- Create `feed_health.json` tracking success/failure rates per feed
- Log update duration, entry count, and HTTP status codes
- Add warning when feed hasn't updated in expected window
- Implement optional webhook or email alerts for persistent failures

**8. Concurrency**
- Use `concurrent.futures.ThreadPoolExecutor` to fetch feeds in parallel
- Set reasonable worker count (e.g., 10 threads)
- Use `as_completed()` to process results as they arrive
- Add global timeout for entire update operation (e.g., 5 minutes)

**9. Data Migration**
- Add `version` field to all JSON files
- Create migration functions for each schema version change
- Check version on load and auto-migrate if needed
- Keep backup of old data during migration

**10. Specific Exception Handling**
- Replace `except:` on line 33 with `except Exception as e:`
- Catch specific exceptions: `URLError`, `HTTPError`, `ValueError` for time parsing
- Log exception type and message for debugging
- Replace `sys.exit()` on line 35 with graceful degradation

### Medium Priority Enhancements

**11. Feed Metadata**
- Add `feed.feed.title`, `feed.feed.subtitle`, `feed.feed.link` to category JSON
- Store feed icon/logo URL if provided
- Include last successful update timestamp per feed
- Add optional description field for user notes

**12. Entry Content**
- Store `feed.summary` or `feed.content[0].value` in entries
- Add `content_type` field (text/html)
- Truncate very long content (e.g., 5000 chars) to save space
- Make content storage optional per category via config flag

**13. Incremental Updates**
- Store highest timestamp per category in metadata
- Skip entries older than highest timestamp during parsing
- Keep configurable lookback window (e.g., 7 days) to avoid missing items
- Add "mark all as read" to update the high-water mark manually

**14. Robust Date Handling**
- Try fallback chain: `published_parsed` → `updated_parsed` → `created_parsed`
- If all fail, use current time with warning flag
- Add `date_reliable` boolean field to entries
- Validate parsed dates aren't in the future (clock skew detection)

**15. Read/Unread Tracking**
- Add `read_items.json` storing set of entry IDs marked as read
- Include `read` boolean in entry objects when loading
- Implement "mark as read" function taking entry ID
- Add "unread count" to category metadata

### Low Priority Features

**16. Search/Filter**
- Add function `search_entries(query, category=None)` using simple string matching
- Index entries by normalized title words for faster search
- Support filtering by date range, source, read status
- Return results in same JSON format as main feed

**17. OPML Support**
- Add `import_opml(file_path)` parsing XML outline structure
- Create `export_opml()` generating valid OPML 2.0 document
- Map OPML categories to system categories automatically
- Preserve folder structure in export

**18. Feed Discovery**
- Add `discover_feeds(url)` function using `<link>` tag parsing
- Check common feed locations: `/feed`, `/rss`, `/atom.xml`
- Use `feedparser` to validate discovered URLs
- Return list of candidate feeds with titles

**19. Configurable Timezone**
- Move `TIMEZONE` from `config.py` to `feeds.json` as setting
- Accept timezone strings like "America/New_York" using `pytz`
- Add `--timezone` CLI argument for one-off overrides
- Default to system timezone if not specified

**20. Statistics**
- Add `get_stats()` function returning feed/entry counts
- Calculate average entries per day per feed
- Track storage size of data directory
- Generate JSON report with health scores per feed (0-100 based on reliability)