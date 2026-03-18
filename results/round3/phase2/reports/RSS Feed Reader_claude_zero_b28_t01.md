# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-Category Support**: Organizes feeds into categories, each with multiple sources/URLs
3. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file in `~/.rreader/`
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration
4. **Time Handling**: Converts feed timestamps to a configurable timezone (default: UTC+9/KST)
5. **Data Persistence**: Saves parsed feeds as JSON files (`rss_{category}.json`) in the data directory
6. **Duplicate Handling**: Uses timestamps as IDs to deduplicate entries within a category
7. **Flexible Author Display**: Supports per-category configuration for showing feed author vs source name
8. **Sorting**: Orders entries by timestamp (newest first)
9. **Selective Updates**: Can update a single category or all categories
10. **Optional Logging**: Provides progress output when `log=True`

## Triage

### Critical Gaps (P0)
1. **Error Handling**: Bare `except` clauses and `sys.exit()` calls that terminate the entire program
2. **Collision on Duplicate Timestamps**: Multiple entries with the same timestamp overwrite each other
3. **No Entry Validation**: Missing feeds silently skip without notification

### High Priority (P1)
4. **No Cache/TTL Management**: No mechanism to prevent excessive feed fetching
5. **Network Timeout Handling**: No timeout configuration for hung connections
6. **Data Directory Creation**: Race condition if directory doesn't exist when writing files
7. **Configuration Validation**: No schema validation for `feeds.json`
8. **Atomic File Writes**: Risk of corrupted JSON files on write failure

### Medium Priority (P2)
9. **Limited Observability**: No structured logging or metrics
10. **No Rate Limiting**: Could hammer RSS servers
11. **HTML/Content Cleaning**: No sanitization of feed content
12. **Missing Feed Metadata**: Doesn't capture description, categories, or media
13. **No Incremental Updates**: Always refetches entire feed history

### Low Priority (P3)
14. **Hardcoded Timezone**: Should be configurable per-user
15. **No CLI Interface**: When run as main, accepts no arguments
16. **Today's Date Calculation**: Uses `datetime.date.today()` without timezone awareness
17. **No Feed Health Monitoring**: Doesn't track failed/stale feeds

## Plan

### 1. Error Handling (P0)
**Changes needed:**
- Replace `except:` on line 31 with specific exceptions: `except (URLError, HTTPError, socket.timeout) as e:`
- Remove `sys.exit()` call; instead log error and continue to next feed
- Add try-except around line 39 (feed iteration) to catch malformed entries
- Return error count from function for caller to handle
- Add exception logging with feed URL context

```python
except (urllib.error.URLError, http.client.HTTPException) as e:
    if log:
        sys.stderr.write(f" - Failed: {e}\n")
    continue  # Move to next source instead of exiting
```

### 2. Collision on Duplicate Timestamps (P0)
**Changes needed:**
- Change ID generation from `ts` to `f"{ts}_{source}_{hash(feed.link)[:8]}"`
- Or append a counter when collision detected: `f"{ts}_{collision_counter}"`
- Add collision detection and warning logging
- Alternative: Use feed's native GUID if available: `getattr(feed, 'id', None)`

```python
feed_id = getattr(feed, 'id', None) or f"{ts}_{source}_{abs(hash(feed.link)) % 10000}"
```

### 3. Entry Validation (P0)
**Changes needed:**
- Track failed feeds in a list
- After processing all feeds, write summary to log
- Add validation for required fields (title, link)
- Provide return value indicating success/partial success/failure

```python
failed_sources = []
success_count = 0
for source, url in urls.items():
    # ... existing code ...
    if not d.entries:
        failed_sources.append((source, "No entries found"))
```

### 4. Cache/TTL Management (P1)
**Changes needed:**
- Check file modification time before fetching
- Add TTL configuration per category (default: 15 minutes)
- Skip fetch if file exists and is fresh: `os.path.getmtime(filepath) + ttl > time.time()`
- Add `force_refresh` parameter to override cache

```python
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
ttl = d.get("ttl_seconds", 900)  # 15 min default
if os.path.exists(cache_file) and not force_refresh:
    if time.time() - os.path.getmtime(cache_file) < ttl:
        return  # Use cached version
```

### 5. Network Timeout Handling (P1)
**Changes needed:**
- Add timeout parameter to feedparser: `feedparser.parse(url, timeout=30)`
- Note: feedparser uses urllib internally; may need to configure via `socket.setdefaulttimeout()`
- Wrap in timeout-specific exception handling
- Make timeout configurable per feed in `feeds.json`

```python
import socket
socket.setdefaulttimeout(d.get("timeout_seconds", 30))
d = feedparser.parse(url)
```

### 6. Data Directory Creation Race Condition (P1)
**Changes needed:**
- Use `os.makedirs(p["path_data"], exist_ok=True)` instead of conditional check
- Apply to all path creation in common.py
- Add try-except around file writes with proper error messages

```python
os.makedirs(p["path_data"], exist_ok=True)
```

### 7. Configuration Validation (P1)
**Changes needed:**
- Add JSON schema validation using `jsonschema` library
- Validate structure: categories → feeds dict → URL strings
- Check for required keys: "feeds" in each category
- Provide helpful error messages for malformed config
- Validate URLs with regex or urllib.parse

```python
def validate_feeds_config(config):
    for category, data in config.items():
        if "feeds" not in data:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category '{category}' feeds must be a dict")
```

### 8. Atomic File Writes (P1)
**Changes needed:**
- Write to temporary file first: `f"{filename}.tmp"`
- Use `os.replace()` to atomically move temp file to target
- Ensure cleanup on exception with try-finally
- Use context manager pattern

```python
tmp_path = os.path.join(p["path_data"], f"rss_{category}.json.tmp")
final_path = os.path.join(p["path_data"], f"rss_{category}.json")
try:
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(rslt, ensure_ascii=False))
    os.replace(tmp_path, final_path)
except:
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    raise
```

### 9. Limited Observability (P2)
**Changes needed:**
- Replace `sys.stdout.write` with proper logging module
- Add log levels: DEBUG, INFO, WARNING, ERROR
- Log feed fetch duration, entry counts, errors
- Add optional JSON-structured logging for monitoring systems

```python
import logging
logger = logging.getLogger(__name__)

logger.info(f"Fetching {source} from {url}")
start = time.time()
d = feedparser.parse(url)
logger.info(f"Fetched {len(d.entries)} entries in {time.time()-start:.2f}s")
```

### 10. Rate Limiting (P2)
**Changes needed:**
- Add configurable delay between feed fetches: `time.sleep(delay)`
- Default: 1 second between sources
- Make configurable in feeds.json: `"rate_limit_seconds": 2`
- Consider per-domain rate limiting with dictionary tracking last fetch time

```python
last_fetch_by_domain = {}
domain = urllib.parse.urlparse(url).netloc
if domain in last_fetch_by_domain:
    elapsed = time.time() - last_fetch_by_domain[domain]
    if elapsed < rate_limit:
        time.sleep(rate_limit - elapsed)
```

### 11. HTML/Content Cleaning (P2)
**Changes needed:**
- Use `html.unescape()` on title and author fields
- Consider using `bleach` library to strip HTML tags
- Normalize whitespace with regex
- Truncate excessively long titles

```python
from html import unescape
title = unescape(feed.title).strip()
title = re.sub(r'\s+', ' ', title)  # Normalize whitespace
```

### 12. Missing Feed Metadata (P2)
**Changes needed:**
- Add `description` field: `feed.get('summary', '')`
- Add `categories` field: `feed.get('tags', [])`
- Add `media` field for enclosures/images
- Make inclusion configurable to avoid bloat

```python
entries = {
    # ... existing fields ...
    "description": getattr(feed, 'summary', '')[:500],
    "categories": [tag.term for tag in getattr(feed, 'tags', [])],
    "image": getattr(feed, 'media_thumbnail', [{}])[0].get('url'),
}
```

### 13. Incremental Updates (P2)
**Changes needed:**
- Store last fetch timestamp per category
- Pass `modified` or `etag` headers to feedparser for conditional GET
- Only write file if new entries exist
- Track per-feed last entry timestamp

```python
# Store in metadata
last_modified = rslt.get("last_modified")
etag = rslt.get("etag")
d = feedparser.parse(url, modified=last_modified, etag=etag)
if d.status == 304:  # Not modified
    continue
```

### 14. Hardcoded Timezone (P3)
**Changes needed:**
- Move TIMEZONE to user-editable config file or environment variable
- Add timezone string parsing: `pytz.timezone(config.get('timezone', 'UTC'))`
- Default to system timezone if not specified
- Validate timezone strings

### 15. No CLI Interface (P3)
**Changes needed:**
- Add argparse for command-line arguments
- Support: `--category`, `--verbose`, `--force-refresh`, `--config`
- Add `--list-categories` command
- Add `--validate-config` command

```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--category', help='Update specific category')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    do(target_category=args.category, log=args.verbose)
```

### 16. Today's Date Calculation (P3)
**Changes needed:**
- Replace `datetime.date.today()` with `datetime.datetime.now(TIMEZONE).date()`
- Ensures "today" is calculated in user's timezone, not system timezone

```python
today = datetime.datetime.now(TIMEZONE).date()
pubDate = at.strftime("%H:%M" if at.date() == today else "%b %d, %H:%M")
```

### 17. Feed Health Monitoring (P3)
**Changes needed:**
- Track consecutive failures per feed
- Store last successful fetch timestamp
- Mark feeds as "unhealthy" after N failures
- Add health status to output JSON
- Provide health report command

```python
health = {
    "last_success": timestamp,
    "consecutive_failures": 0,
    "last_error": None,
    "status": "healthy" | "degraded" | "failed"
}
```