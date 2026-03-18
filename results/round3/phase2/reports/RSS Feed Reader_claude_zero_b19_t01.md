# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed reader with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-category Support**: Organizes feeds into categories, with each category containing multiple source URLs
3. **Configuration Management**: 
   - Copies bundled default feeds on first run
   - Merges new categories from bundled feeds into existing user configuration
   - Stores user feeds in `~/.rreader/feeds.json`
4. **Entry Processing**: Extracts key metadata (title, link, author, publication date, timestamp) from each feed entry
5. **Timestamp Handling**: Converts publication times to a configurable timezone (currently KST/UTC+9)
6. **Date Formatting**: Displays times as "HH:MM" for today's entries, "Mon DD, HH:MM" for older entries
7. **Deduplication**: Uses timestamp as ID to handle duplicate entries across multiple fetches
8. **Data Persistence**: Saves processed feeds as JSON files (`rss_{category}.json`) in the data directory
9. **Sorting**: Orders entries by timestamp (newest first)
10. **Selective Updates**: Can update a single category or all categories
11. **Optional Logging**: Progress indication for feed downloads

## Triage

### Critical Gaps
1. **Error Handling** - Silent failures and system exits make debugging impossible and cause premature termination
2. **ID Collision Handling** - Timestamp-based IDs will overwrite entries published in the same second
3. **Missing Configuration Validation** - No validation that feeds.json has correct structure

### High Priority Gaps
4. **No Retry Logic** - Network failures immediately fail without retry attempts
5. **Rate Limiting** - No throttling between requests; risks being blocked by feed providers
6. **Stale Data Detection** - No mechanism to warn users when feeds haven't updated in unusual timeframes
7. **Feed Validation** - No verification that parsed feeds contain valid data

### Medium Priority Gaps
8. **Limited Logging Infrastructure** - Binary log flag is insufficient for production debugging
9. **No Configuration for Timezone** - Hardcoded timezone prevents use in other regions
10. **Missing HTTP Headers** - No User-Agent or proper HTTP client configuration
11. **No Incremental Updates** - Always fetches all entries, even if already processed

### Low Priority Gaps
12. **No Progress Indication** - When logging is off, user has no feedback during long operations
13. **No Entry Limit** - Could accumulate unlimited entries over time
14. **Hardcoded Paths** - Limited flexibility in deployment scenarios

## Plan

### 1. Error Handling
**Changes needed:**
- Replace bare `except:` with specific exception types (`feedparser.exceptions`, `urllib.error.URLError`, `json.JSONDecodeError`)
- Remove `sys.exit()` calls; instead log errors and continue processing other feeds
- Accumulate errors and return/log summary at end
- Add try-except around file operations with proper error messages

```python
errors = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        if d.bozo:  # feedparser's error flag
            errors.append(f"{source}: {d.bozo_exception}")
            continue
    except (URLError, TimeoutError) as e:
        errors.append(f"{source}: Network error - {e}")
        continue
```

### 2. ID Collision Handling
**Changes needed:**
- Change ID strategy to combine timestamp with feed GUID or hash of (timestamp + link + title)
- Modify the dictionary key in `get_feed_from_rss()`:

```python
unique_id = f"{ts}_{hash(feed.get('id', feed.link))}"
entries = {
    "id": unique_id,
    # ... rest of fields
}
rslt[entries["id"]] = entries
```

### 3. Configuration Validation
**Changes needed:**
- Add a validation function that checks feeds.json structure:

```python
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    for category, data in config.items():
        if not isinstance(data, dict) or 'feeds' not in data:
            raise ValueError(f"Category {category} missing 'feeds' key")
        if not isinstance(data['feeds'], dict):
            raise ValueError(f"Category {category} 'feeds' must be a dictionary")
    return True
```

### 4. Retry Logic
**Changes needed:**
- Add retry decorator or implement exponential backoff:

```python
from urllib.error import URLError
import time

def fetch_with_retry(url, max_retries=3, backoff=2):
    for attempt in range(max_retries):
        try:
            return feedparser.parse(url)
        except (URLError, TimeoutError) as e:
            if attempt == max_retries - 1:
                raise
            time.sleep(backoff ** attempt)
```

### 5. Rate Limiting
**Changes needed:**
- Add delay between feed requests:

```python
import time

for i, (source, url) in enumerate(urls.items()):
    if i > 0:
        time.sleep(1)  # 1 second between requests
    # ... fetch feed
```

### 6. Stale Data Detection
**Changes needed:**
- Store and check last successful update time:
- Add `last_updated` to each category's JSON output
- Compare against threshold (e.g., 24 hours for news feeds)

```python
rslt = {
    "entries": rslt,
    "created_at": int(time.time()),
    "last_entry_time": max((e['timestamp'] for e in rslt), default=0),
    "feed_count": len(urls)
}
```

### 7. Feed Validation
**Changes needed:**
- Check that parsed feed has entries and required fields:

```python
if not d.entries:
    errors.append(f"{source}: No entries found")
    continue
if d.bozo and not d.entries:  # Malformed and empty
    errors.append(f"{source}: Malformed feed")
    continue
```

### 8. Logging Infrastructure
**Changes needed:**
- Replace binary `log` flag with Python's `logging` module:

```python
import logging

logger = logging.getLogger(__name__)

def do(target_category=None, log_level=logging.INFO):
    logging.basicConfig(level=log_level)
    logger.info(f"Fetching {url}")
    logger.error(f"Failed to fetch {url}: {e}")
```

### 9. Configurable Timezone
**Changes needed:**
- Move TIMEZONE to feeds.json or separate config file:
- Add timezone parameter to `do()` function:

```python
def do(target_category=None, timezone=None, log=False):
    tz = timezone or TIMEZONE
    # use tz instead of TIMEZONE in datetime operations
```

### 10. HTTP Headers
**Changes needed:**
- Configure feedparser with proper headers:

```python
import feedparser

# Set User-Agent globally
feedparser.USER_AGENT = "rreader/1.0 (+https://example.com/rreader)"

# Or per-request:
d = feedparser.parse(url, agent="rreader/1.0")
```

### 11. Incremental Updates
**Changes needed:**
- Load existing entries from JSON file
- Compare timestamps and only add newer entries:

```python
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
existing_ids = set()
if os.path.exists(existing_file):
    with open(existing_file) as f:
        existing = json.load(f)
        existing_ids = {e['id'] for e in existing['entries']}
        
# Only add new entries
if entries["id"] not in existing_ids:
    rslt[entries["id"]] = entries
```

### 12. Progress Indication
**Changes needed:**
- Add progress bar or status output even when detailed logging is off:

```python
from tqdm import tqdm  # or simple counter

for i, (source, url) in enumerate(tqdm(urls.items(), disable=not log)):
    # ... process feed
```

### 13. Entry Limit
**Changes needed:**
- Add configuration for max entries per category:
- Trim old entries before saving:

```python
MAX_ENTRIES = 1000
rslt = [val for key, val in sorted(rslt.items(), reverse=True)][:MAX_ENTRIES]
```

### 14. Configurable Paths
**Changes needed:**
- Accept data directory as environment variable or parameter:

```python
DATA_DIR = os.getenv('RREADER_DATA_DIR', str(Path.home()) + "/.rreader/")
p = {"path_data": DATA_DIR}
```