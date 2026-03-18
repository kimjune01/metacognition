# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed reader with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-category Support**: Organizes feeds into categories, processing either a single target category or all categories
3. **Data Persistence**: Stores parsed feed entries as JSON files (one per category) in `~/.rreader/`
4. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Auto-copies bundled default feeds if user configuration doesn't exist
   - Merges new categories from bundled feeds into existing user configuration
5. **Timestamp Handling**: 
   - Converts feed timestamps to configured timezone (hardcoded to UTC+9/KST)
   - Formats dates as "HH:MM" for today's entries, "MMM DD, HH:MM" for older entries
6. **Duplicate Handling**: Uses timestamp as ID to deduplicate entries from multiple feeds
7. **Entry Sorting**: Sorts entries by timestamp in reverse chronological order
8. **Author Display**: Configurable per-category option to show feed author vs. source name
9. **Logging**: Optional progress logging during feed fetching

## Triage

### Critical Gaps
1. **Error Handling** - Silent failures mask feed fetch problems and data corruption issues
2. **Missing Bundled Feeds File** - Code references `feeds.json` that doesn't exist in the codebase
3. **ID Collision Bug** - Using timestamps as IDs causes data loss when multiple entries share the same second

### High Priority Gaps
4. **No Rate Limiting** - Could trigger 429 errors or IP bans from feed providers
5. **No Timeout Configuration** - Feed fetches can hang indefinitely
6. **No Feed Validation** - Missing required fields cause silent skips without logging
7. **No Cache/Conditional Requests** - Wastes bandwidth by re-downloading unchanged feeds
8. **Hardcoded Timezone** - Should be configurable per user

### Medium Priority Gaps
9. **No Entry Limit** - JSON files grow unbounded over time
10. **No Data Migration Strategy** - Schema changes will break existing installations
11. **No Retry Logic** - Transient network errors cause permanent data gaps
12. **Resource Cleanup** - No connection pooling or proper resource management

### Low Priority Gaps
13. **No Progress Indicators** - Users don't know how long updates will take
14. **No Feed Health Monitoring** - Can't identify consistently failing feeds
15. **No Content Sanitization** - Malicious HTML in titles/descriptions could cause issues

## Plan

### 1. Error Handling
**Changes needed:**
- Replace bare `except:` clauses with specific exception types
- Log all errors with feed URL, exception type, and message
- Continue processing other feeds when one fails
- Add error counts to output JSON for UI display
```python
except (URLError, HTTPError) as e:
    error_msg = f"Network error for {url}: {str(e)}"
    if log:
        sys.stderr.write(f" - {error_msg}\n")
    # Store in errors list, don't exit
except Exception as e:
    error_msg = f"Parse error for {url}: {str(e)}"
    if log:
        sys.stderr.write(f" - {error_msg}\n")
```

### 2. Missing Bundled Feeds File
**Changes needed:**
- Create `feeds.json` example file in the repository with structure:
```json
{
  "tech": {
    "feeds": {
      "HackerNews": "https://news.ycombinator.com/rss",
      "TechCrunch": "https://techcrunch.com/feed/"
    },
    "show_author": false
  }
}
```
- Add fallback to create empty feeds dict if neither file exists
- Document the expected schema in README

### 3. ID Collision Bug
**Changes needed:**
- Change ID generation to include feed URL hash:
```python
import hashlib
feed_hash = hashlib.md5(feed.link.encode()).hexdigest()[:8]
entries = {
    "id": f"{ts}_{feed_hash}",
    # ... rest of fields
}
```
- Update sorting to handle string IDs: `sorted(rslt.items(), key=lambda x: x[1]['timestamp'], reverse=True)`

### 4. Rate Limiting
**Changes needed:**
- Add configurable delay between feed fetches:
```python
FETCH_DELAY_SECONDS = 1.0  # in config.py
# In get_feed_from_rss loop:
for i, (source, url) in enumerate(urls.items()):
    if i > 0:
        time.sleep(FETCH_DELAY_SECONDS)
```
- Add per-domain rate limiting using `collections.defaultdict` to track last fetch time per domain

### 5. Timeout Configuration
**Changes needed:**
- Add timeout parameter to feedparser:
```python
FEED_TIMEOUT_SECONDS = 30  # in config.py
d = feedparser.parse(url, timeout=FEED_TIMEOUT_SECONDS)
```

### 6. Feed Validation
**Changes needed:**
- Add explicit field validation with logging:
```python
required_fields = ['link', 'title']
if not all(hasattr(feed, field) for field in required_fields):
    if log:
        sys.stderr.write(f" - Skipping entry missing required fields\n")
    continue
```

### 7. Cache/Conditional Requests
**Changes needed:**
- Store ETags and Last-Modified headers per feed
- Pass them in subsequent requests:
```python
# Store in feeds.json per URL:
"cache": {"etag": "...", "modified": "..."}
# Pass to feedparser:
d = feedparser.parse(url, etag=cached_etag, modified=cached_modified)
if d.status == 304:  # Not modified
    # Use cached entries
```

### 8. Configurable Timezone
**Changes needed:**
- Move TIMEZONE to user-editable config:
```python
# In feeds.json:
"settings": {
    "timezone_offset_hours": 9
}
# Load and use:
tz_offset = user_config.get("settings", {}).get("timezone_offset_hours", 0)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```

### 9. Entry Limit
**Changes needed:**
- Add MAX_ENTRIES_PER_CATEGORY to config (default: 100)
- Truncate after sorting:
```python
rslt = rslt[:MAX_ENTRIES_PER_CATEGORY]
```

### 10. Data Migration
**Changes needed:**
- Add version number to JSON output:
```python
rslt = {
    "version": 1,
    "entries": rslt,
    "created_at": int(time.time())
}
```
- Add migration function that checks version and transforms old data

### 11. Retry Logic
**Changes needed:**
- Add retry decorator with exponential backoff:
```python
from urllib.error import URLError
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        d = feedparser.parse(url)
        break
    except URLError as e:
        if attempt == MAX_RETRIES - 1:
            raise
        time.sleep(2 ** attempt)
```

### 12. Resource Cleanup
**Changes needed:**
- Use context managers for file operations (already done)
- Add connection pooling via `urllib3` or `requests` library
- Set maximum concurrent connections

### 13. Progress Indicators
**Changes needed:**
- Add total feed count and current progress:
```python
total = len(urls)
for i, (source, url) in enumerate(urls.items(), 1):
    if log:
        sys.stdout.write(f"[{i}/{total}] {url}")
```

### 14. Feed Health Monitoring
**Changes needed:**
- Track consecutive failures per feed in persistent state
- Add "last_success" timestamp to each feed in config
- Report unhealthy feeds (e.g., 5+ consecutive failures)

### 15. Content Sanitization
**Changes needed:**
- Use `bleach` or `html` library to escape HTML in titles:
```python
import html
entries = {
    "title": html.escape(feed.title),
}
```