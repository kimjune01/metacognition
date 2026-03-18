# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-category Support**: Organizes feeds into categories, each with multiple source URLs
3. **Feed Configuration Management**: 
   - Maintains a user-editable `feeds.json` configuration file
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled feeds into existing user configuration
4. **Data Persistence**: Saves parsed feed entries to JSON files (one per category) in `~/.rreader/`
5. **Timestamp Handling**: 
   - Converts feed timestamps to a configured timezone (currently UTC+9)
   - Formats display dates (shows time only for today, date+time for older entries)
   - Uses timestamps for deduplication and sorting
6. **Duplicate Prevention**: Uses timestamp as ID to prevent duplicate entries when feeds overlap
7. **Author Display**: Configurable per-category to show either feed author or source name
8. **Sorted Output**: Entries sorted by timestamp in descending order (newest first)
9. **Optional Logging**: Can output progress information during feed fetching
10. **Selective Updates**: Can refresh a single category or all categories

## Triage

### Critical Gaps (Production Blockers)

1. **Error Handling is Broken**: The `sys.exit()` call in the exception handler will crash the entire process when any single feed fails, despite being in an error handler
2. **No Request Timeouts**: Feed parsing can hang indefinitely on slow/unresponsive servers
3. **No Data Directory Initialization Check**: The `feeds.json` file is expected in `~/.rreader/` but directory creation happens after `FEEDS_FILE_NAME` is defined

### High Priority (Functional Issues)

4. **ID Collision Risk**: Using timestamp-only as ID means multiple articles published in the same second will overwrite each other
5. **No Validation**: No schema validation for the feeds.json structure or parsed feed data
6. **Missing Bundled feeds.json**: Code references a bundled `feeds.json` but it's not included in the provided code
7. **No Rate Limiting**: Could hammer RSS servers with rapid requests, risking IP bans
8. **Silent Failures**: Individual feed parse errors are swallowed with bare `except:` clauses

### Medium Priority (User Experience)

9. **No Progress Feedback**: Without `log=True`, users have no idea if the system is working or frozen
10. **No Stale Data Detection**: No mechanism to identify outdated cached feeds or trigger refreshes
11. **No Feed Metadata**: Doesn't store feed-level information (description, update frequency, last successful fetch)
12. **Timezone Hardcoded**: TIMEZONE is hardcoded to UTC+9 rather than being configurable

### Low Priority (Polish & Maintenance)

13. **No Async Support**: Sequential feed fetching is slow for many feeds
14. **No Incremental Updates**: Always fetches full feeds rather than checking for new items only
15. **No Entry Limits**: Could accumulate unlimited entries, causing performance issues
16. **No Logging Framework**: Uses print statements rather than proper logging
17. **No Tests**: No unit tests or integration tests present

## Plan

### 1. Fix Error Handling (Critical)

**Current Problem**: `sys.exit()` kills the entire process when one feed fails.

**Changes Needed**:
```python
# In get_feed_from_rss function, replace:
except:
    sys.exit(" - Failed\n" if log else 0)

# With:
except Exception as e:
    if log:
        sys.stderr.write(f" - Failed: {str(e)}\n")
    continue  # Skip this feed and continue with others
```

### 2. Add Request Timeouts (Critical)

**Changes Needed**:
```python
# At top of do() function:
TIMEOUT_SECONDS = 30

# In the parse call:
d = feedparser.parse(url, timeout=TIMEOUT_SECONDS)
```

Additionally, wrap with a timeout mechanism since feedparser doesn't always respect timeouts:
```python
import signal

def timeout_handler(signum, frame):
    raise TimeoutError("Feed fetch timeout")

signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(TIMEOUT_SECONDS)
try:
    d = feedparser.parse(url)
finally:
    signal.alarm(0)
```

### 3. Fix Directory Initialization Order (Critical)

**Changes Needed**:
Move the directory creation code in `common.py` to execute before `FEEDS_FILE_NAME` is used:
```python
# In common.py, ensure this runs before FEEDS_FILE_NAME definition:
for d in p["pathkeys"]:
    if not os.path.exists(p[d]):
        os.makedirs(p[d], exist_ok=True)  # Use makedirs for safety

FEEDS_FILE_NAME = os.path.join(p["path_data"], "feeds.json")
```

### 4. Fix ID Collision Risk (High Priority)

**Changes Needed**:
Create unique IDs by combining timestamp with URL hash:
```python
import hashlib

# Replace:
entries = {
    "id": ts,
    # ...
}

# With:
url_hash = hashlib.md5(feed.link.encode()).hexdigest()[:8]
unique_id = f"{ts}_{url_hash}"
entries = {
    "id": unique_id,
    # ...
}
```

### 5. Add Configuration Validation (High Priority)

**Changes Needed**:
Add validation function after loading feeds.json:
```python
def validate_feeds_config(config):
    """Validate feeds.json structure"""
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    
    for category, data in config.items():
        if not isinstance(data, dict):
            raise ValueError(f"Category '{category}' must be a dictionary")
        if "feeds" not in data:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category '{category}' feeds must be a dictionary")
        
        for source, url in data["feeds"].items():
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL for {source}: {url}")
    
    return True

# After loading RSS:
with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
    validate_feeds_config(RSS)
```

### 6. Provide Default feeds.json (High Priority)

**Changes Needed**:
Create a `feeds.json` file in the package directory with example structure:
```json
{
    "tech": {
        "feeds": {
            "Hacker News": "https://news.ycombinator.com/rss",
            "TechCrunch": "https://techcrunch.com/feed/"
        },
        "show_author": false
    },
    "news": {
        "feeds": {
            "Reuters": "https://www.reutersagency.com/feed/"
        },
        "show_author": true
    }
}
```

### 7. Add Rate Limiting (High Priority)

**Changes Needed**:
```python
# At module level:
RATE_LIMIT_DELAY = 0.5  # seconds between requests

# In get_feed_from_rss, after parsing each feed:
for source, url in urls.items():
    try:
        # ... existing parse code ...
        time.sleep(RATE_LIMIT_DELAY)
```

### 8. Improve Error Reporting (High Priority)

**Changes Needed**:
Replace bare `except:` clauses with specific exception handling:
```python
# For feed parsing:
except (urllib.error.URLError, TimeoutError) as e:
    if log:
        sys.stderr.write(f" - Network error: {str(e)}\n")
    continue
except feedparser.FeedParserError as e:
    if log:
        sys.stderr.write(f" - Parse error: {str(e)}\n")
    continue

# For entry processing:
except (AttributeError, ValueError, TypeError) as e:
    if log:
        sys.stderr.write(f"Warning: Skipping malformed entry: {str(e)}\n")
    continue
```

### 9. Add Default Progress Feedback (Medium Priority)

**Changes Needed**:
Make logging default to True and add a quiet flag instead:
```python
def do(target_category=None, quiet=False):
    log = not quiet
    # Rest of function uses 'log' as before
```

### 10. Implement Stale Data Detection (Medium Priority)

**Changes Needed**:
Add cache age checking:
```python
def is_cache_stale(category, max_age_seconds=3600):
    """Check if cached feed data is older than max_age"""
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    
    if not os.path.exists(cache_file):
        return True
    
    try:
        with open(cache_file, "r") as f:
            data = json.load(f)
            age = int(time.time()) - data.get("created_at", 0)
            return age > max_age_seconds
    except:
        return True

# Use in do() function:
if not is_cache_stale(category):
    if log:
        print(f"Using cached data for {category}")
    continue
```

### 11. Make Timezone Configurable (Medium Priority)

**Changes Needed**:
```python
# In config.py:
import os

TIMEZONE_OFFSET = int(os.environ.get("RREADER_TZ_OFFSET", "9"))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET))
```

Or allow it in feeds.json with a global settings section.

### 12. Add Proper Logging (Low Priority)

**Changes Needed**:
```python
import logging

# At module level:
logger = logging.getLogger(__name__)

# Replace sys.stdout.write calls:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}: {str(e)}")
```

### 13. Implement Async Fetching (Low Priority)

**Changes Needed**:
Use `asyncio` and `aiohttp` for concurrent feed fetching:
```python
import asyncio
import aiohttp

async def fetch_feed_async(session, source, url):
    async with session.get(url, timeout=30) as response:
        content = await response.text()
        return source, feedparser.parse(content)

async def get_feeds_concurrent(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_feed_async(session, src, url) 
                for src, url in urls.items()]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

This would require significant refactoring but could reduce fetch times by 10-100x for multiple feeds.