# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, each with multiple feed sources defined in a `feeds.json` configuration file.

3. **Feed Configuration Management**: 
   - Copies a bundled default `feeds.json` if none exists
   - Merges new categories from bundled config into existing user config

4. **Data Normalization**: Extracts and standardizes feed entries with:
   - Title, URL, source name, publication date
   - Unix timestamp for sorting
   - Timezone conversion (UTC to configured timezone, defaults to KST/UTC+9)

5. **Time Formatting**: Displays time as "HH:MM" for today's entries, "MMM DD, HH:MM" for older entries.

6. **Duplicate Handling**: Uses timestamp as ID to deduplicate entries within a category.

7. **Output Generation**: Writes sorted JSON files (`rss_{category}.json`) containing all entries for each category.

8. **Optional Logging**: Can output progress information when `log=True`.

9. **Selective Updates**: Can update a single category or all categories.

## Triage

### Critical Gaps

1. **No Error Recovery**: System exits entirely on any feed fetch failure, preventing other feeds from being processed.

2. **ID Collision Handling**: Using timestamp as ID causes entries published in the same second to overwrite each other.

3. **Missing Data Directory Check**: The `feeds.json` file path depends on `p["path_data"]` which may not exist when first accessed.

### High Priority Gaps

4. **No HTTP Timeout Configuration**: Feed parsing can hang indefinitely on unresponsive servers.

5. **No Rate Limiting**: Fetches all feeds simultaneously, potentially triggering rate limits or being flagged as abusive.

6. **Bare Exception Handlers**: Multiple `except:` blocks catch all exceptions without logging what failed or why.

7. **Missing Feed Validation**: No check for malformed feed data or required fields in the JSON configuration.

8. **No Caching/Conditional Requests**: Re-fetches entire feeds every time, wasting bandwidth (no ETag/Last-Modified support).

### Medium Priority Gaps

9. **Hardcoded Timezone**: TIMEZONE is defined in code rather than user-configurable.

10. **No Entry Limit**: Stores all entries from all time, causing unbounded data growth.

11. **No User Feedback for Programmatic Use**: When `log=False`, silent failures provide no diagnostic information.

12. **Missing Feed Metadata**: Doesn't preserve feed description, categories, or other useful metadata.

13. **No Async Processing**: Sequential feed fetching is slow for many feeds.

### Low Priority Gaps

14. **No CLI Interface**: When run as main, accepts no command-line arguments for category selection or verbosity.

15. **No Data Migration**: No version handling for changes to the data format.

16. **Missing Type Hints**: No static type checking support.

## Plan

### 1. Error Recovery (Critical)
**Change**: Replace `sys.exit()` with proper exception handling that allows processing to continue.
```python
# Replace the try/except around feedparser.parse:
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
    except Exception as e:
        if log:
            sys.stderr.write(f" - Failed: {e}\n")
        continue  # Skip this feed and continue with others
```

### 2. ID Collision Handling (Critical)
**Change**: Create unique IDs by combining timestamp with a sequence number or hash.
```python
# Replace the entries dict creation:
entry_id = f"{ts}_{hash(feed.link)}"  # or use uuid
entries = {
    "id": entry_id,  # Changed from just ts
    # ... rest of fields
}
rslt[entry_id] = entries  # Use new ID as key
```

### 3. Data Directory Initialization (Critical)
**Change**: Ensure directory exists before accessing `FEEDS_FILE_NAME`.
```python
# At the top of do() function, add:
if not os.path.exists(p["path_data"]):
    os.makedirs(p["path_data"], exist_ok=True)
```

### 4. HTTP Timeout Configuration (High)
**Change**: Add timeout parameter to feedparser calls.
```python
# Modify feedparser.parse call:
d = feedparser.parse(url, timeout=30)  # 30 second timeout
```
Note: May need to use requests library wrapper if feedparser doesn't expose timeout directly.

### 5. Rate Limiting (High)
**Change**: Add delays between feed fetches.
```python
import time

for source, url in urls.items():
    # ... existing fetch code ...
    time.sleep(1)  # 1 second delay between feeds
```

### 6. Specific Exception Handling (High)
**Change**: Replace bare `except:` with specific exception types and logging.
```python
import logging

# Replace bare excepts with:
except (AttributeError, TypeError, ValueError) as e:
    if log:
        logging.warning(f"Failed to parse entry from {source}: {e}")
    continue
```

### 7. Feed Validation (High)
**Change**: Validate JSON structure when loading feeds.
```python
def validate_feeds_config(config):
    """Ensure config has required structure."""
    if not isinstance(config, dict):
        raise ValueError("Feeds config must be a dictionary")
    for category, data in config.items():
        if not isinstance(data, dict):
            raise ValueError(f"Category {category} must be a dict")
        if "feeds" not in data:
            raise ValueError(f"Category {category} missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category {category} 'feeds' must be dict")
    return True

# Use after loading RSS:
with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
    validate_feeds_config(RSS)
```

### 8. Caching Support (High)
**Change**: Store and use ETags/Last-Modified headers.
```python
# Add to each category's JSON output:
rslt = {
    "entries": rslt,
    "created_at": int(time.time()),
    "etags": {}  # Store per-feed ETags
}

# Modify fetch to use conditional requests:
# (Requires storing previous ETags and checking response)
```

### 9. Configurable Timezone (Medium)
**Change**: Move timezone to feeds.json or separate config file.
```python
# In feeds.json add:
{
    "_config": {
        "timezone_offset": 9  # hours from UTC
    },
    "category1": { ... }
}

# Load in config.py:
with open(FEEDS_FILE_NAME) as f:
    config = json.load(f)
    tz_offset = config.get("_config", {}).get("timezone_offset", 9)
    TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```

### 10. Entry Limits (Medium)
**Change**: Keep only recent entries (e.g., last 7 days or 100 items).
```python
# After sorting entries:
MAX_ENTRIES = 100
rslt = rslt[:MAX_ENTRIES]  # Keep only most recent
```

### 11. Return Error Information (Medium)
**Change**: Return success/failure statistics.
```python
def get_feed_from_rss(...):
    rslt = {}
    stats = {"succeeded": 0, "failed": 0, "errors": []}
    
    for source, url in urls.items():
        try:
            # ... fetch code ...
            stats["succeeded"] += 1
        except Exception as e:
            stats["failed"] += 1
            stats["errors"].append({"source": source, "error": str(e)})
    
    return rslt, stats  # Return both data and stats
```

### 12. Feed Metadata Preservation (Medium)
**Change**: Add feed-level information to output.
```python
rslt = {
    "entries": entries_list,
    "created_at": int(time.time()),
    "feed_info": {
        source: {
            "title": d.feed.get("title"),
            "description": d.feed.get("description"),
            "link": d.feed.get("link")
        }
        for source in urls.keys()
    }
}
```

### 13. Async Processing (Medium)
**Change**: Use asyncio with aiohttp for concurrent fetching.
```python
import asyncio
import aiohttp

async def fetch_feed(session, source, url):
    async with session.get(url, timeout=30) as response:
        content = await response.text()
        return feedparser.parse(content)

async def get_feed_from_rss_async(category, urls, ...):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_feed(session, src, url) for src, url in urls.items()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Process results...
```

### 14. CLI Interface (Low)
**Change**: Add argparse for command-line options.
```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Fetch RSS feeds")
    parser.add_argument("--category", help="Update specific category")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()
    
    do(target_category=args.category, log=args.verbose)
```

### 15. Data Migration (Low)
**Change**: Add version field and migration logic.
```python
DATA_VERSION = 1

def migrate_data(data, from_version):
    """Migrate data format between versions."""
    if from_version < 1:
        # Add any new required fields
        pass
    return data

# When reading data:
version = rslt.get("version", 0)
if version < DATA_VERSION:
    rslt = migrate_data(rslt, version)
```

### 16. Type Hints (Low)
**Change**: Add type annotations throughout.
```python
from typing import Dict, List, Optional, Any

def get_feed_from_rss(
    category: str,
    urls: Dict[str, str],
    show_author: bool = False,
    log: bool = False
) -> Dict[str, Any]:
    # ... function body
```