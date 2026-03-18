# Diagnostic Report: RSS Feed Reader System

## Observations

This system implements an RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS feeds from multiple sources using `feedparser`
2. **Multi-Category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Data Persistence**: Stores parsed feed entries as JSON files (one per category) in `~/.rreader/`
4. **Time Localization**: Converts UTC timestamps to a configured timezone (KST/UTC+9)
5. **Smart Date Formatting**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older entries
6. **Configuration Management**: 
   - Copies bundled `feeds.json` if user config doesn't exist
   - Merges new categories from bundled config into existing user config
7. **Duplicate Handling**: Uses timestamp as ID to deduplicate entries across sources
8. **Flexible Author Display**: Can show source name or feed author per category
9. **Selective Updates**: Can refresh a single category or all categories
10. **Optional Logging**: Progress output can be enabled/disabled

## Triage

### Critical Gaps (Must Fix)

1. **Silent Error Handling**: Bare `except` clauses swallow all exceptions, making debugging impossible
2. **Data Loss on Duplicate Timestamps**: Using timestamp as ID causes entries published in the same second to overwrite each other
3. **Exit on Single Feed Failure**: `sys.exit()` in feed parsing terminates the entire process if one feed fails

### High Priority (Production Blockers)

4. **No Error Recovery**: Failed feeds aren't retried or logged for later inspection
5. **Missing Feed Validation**: No check for malformed `feeds.json` structure
6. **No Stale Data Handling**: Old cached data persists indefinitely with no expiration
7. **Timezone Hardcoded**: `TIMEZONE` is fixed to KST with no configuration option
8. **No Rate Limiting**: Could hammer feed servers with rapid requests

### Medium Priority (Quality Issues)

9. **No Network Timeout**: `feedparser.parse()` can hang indefinitely
10. **Missing Feed Metadata**: Doesn't store feed description, image, or other useful fields
11. **No Update Tracking**: Can't tell which feeds were updated vs failed vs unchanged
12. **Poor Logging**: `sys.stdout.write` instead of proper logging framework
13. **No Entry Limits**: Could store unlimited entries, bloating JSON files

### Low Priority (Nice to Have)

14. **No CLI Interface**: `target_category` only usable programmatically
15. **No Read/Unread Tracking**: No persistence of user interaction state
16. **No Feed Health Monitoring**: No tracking of feed reliability or update frequency
17. **No Parallel Fetching**: Sequential processing is slow for many feeds

## Plan

### Critical Fixes

**1. Proper Exception Handling**
```python
# Replace bare except clauses with specific handling:
except feedparser.exceptions.ParseError as e:
    error_msg = f"Failed to parse {url}: {e}"
    if log:
        sys.stderr.write(f" - {error_msg}\n")
    # Log to error file and continue
    continue
except requests.exceptions.RequestException as e:
    # Handle network errors
except Exception as e:
    # Log unexpected errors with full traceback
    import traceback
    traceback.print_exc()
```

**2. Fix Duplicate ID Issue**
```python
# Create unique ID combining timestamp and URL hash:
import hashlib
entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
entries = {
    "id": entry_id,
    # ... rest of fields
}
rslt[entries["id"]] = entries
```

**3. Remove sys.exit, Use Continue**
```python
# In feed parsing loop:
except Exception as e:
    if log:
        sys.stderr.write(f" - Failed: {e}\n")
    continue  # Process remaining feeds instead of exiting
```

### High Priority Enhancements

**4. Error Recovery and Logging**
```python
# Add error tracking:
errors = []
for source, url in urls.items():
    try:
        # ... parsing logic
    except Exception as e:
        errors.append({"source": source, "url": url, "error": str(e)})
        
# Write error log:
if errors:
    error_file = os.path.join(p["path_data"], f"rss_{category}_errors.json")
    with open(error_file, "w") as f:
        json.dump({"timestamp": int(time.time()), "errors": errors}, f)
```

**5. Feed Validation**
```python
# At start of do():
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    for cat, data in config.items():
        if "feeds" not in data or not isinstance(data["feeds"], dict):
            raise ValueError(f"Category {cat} missing 'feeds' dict")
    return True

validate_feeds_config(RSS)
```

**6. Stale Data Expiration**
```python
# Add max_age parameter and filter old entries:
MAX_ENTRY_AGE_DAYS = 30
now = int(time.time())
cutoff = now - (MAX_ENTRY_AGE_DAYS * 86400)
rslt = [val for key, val in sorted(rslt.items(), reverse=True) 
        if val["timestamp"] > cutoff]
```

**7. Configurable Timezone**
```python
# In config.py:
TIMEZONE_OFFSET = int(os.getenv("RREADER_TZ_OFFSET", "9"))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET))
```

**8. Rate Limiting**
```python
# Add delay between feeds:
import time
FEED_FETCH_DELAY = 0.5  # seconds

for source, url in urls.items():
    time.sleep(FEED_FETCH_DELAY)
    # ... fetch feed
```

### Medium Priority Improvements

**9. Network Timeouts**
```python
# Configure feedparser timeout:
import socket
socket.setdefaulttimeout(30)  # 30 second timeout
# Or use requests with feedparser:
import requests
response = requests.get(url, timeout=30)
d = feedparser.parse(response.content)
```

**10. Rich Feed Metadata**
```python
# Add to entries dict:
entries = {
    # ... existing fields
    "description": getattr(feed, "summary", "")[:500],  # Truncate
    "image": getattr(feed, "media_thumbnail", [{}])[0].get("url", ""),
    "categories": [tag.term for tag in getattr(feed, "tags", [])],
}
```

**11. Update Status Tracking**
```python
# Return status dictionary:
status = {
    "category": category,
    "total_feeds": len(urls),
    "successful": 0,
    "failed": 0,
    "new_entries": len(rslt["entries"]),
    "timestamp": int(time.time())
}
# Save to rss_{category}_status.json
```

**12. Proper Logging Framework**
```python
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Replace sys.stdout.write with:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}: {e}")
```

**13. Entry Limits**
```python
MAX_ENTRIES_PER_CATEGORY = 500
rslt = rslt[:MAX_ENTRIES_PER_CATEGORY]  # After sorting
```

### Low Priority Features

**14. CLI Interface**
```python
# Add argparse:
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", help="Update specific category")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    do(target_category=args.category, log=args.verbose)
```

**15. Read/Unread State**
```python
# Add read_state.json tracking:
# { "entry_id": {"read": true, "timestamp": 123456} }
# Update on user interaction, filter in UI
```

**16. Feed Health Monitoring**
```python
# Track per-feed statistics:
feed_stats = {
    "url": url,
    "last_success": timestamp,
    "last_failure": timestamp,
    "success_count": 0,
    "failure_count": 0,
    "avg_entries": 0
}
```

**17. Parallel Fetching**
```python
from concurrent.futures import ThreadPoolExecutor
def fetch_single_feed(source, url):
    # ... parsing logic
    return entries

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(fetch_single_feed, s, u) 
               for s, u in urls.items()]
    results = [f.result() for f in futures]
```