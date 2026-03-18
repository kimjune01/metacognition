# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Aggregation**: Parses multiple RSS feeds from different sources and consolidates them into a unified JSON format.

2. **Multi-Category Support**: Organizes feeds by category, allowing different groups of RSS sources to be managed separately.

3. **Feed Configuration Management**: 
   - Maintains a `feeds.json` configuration file in the user's home directory (`~/.rreader/`)
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled feeds into existing user configurations

4. **Time Zone Handling**: Converts feed timestamps to a configured timezone (currently KST/UTC+9) with human-readable date formatting.

5. **Duplicate Entry Prevention**: Uses timestamp-based IDs to deduplicate entries when multiple feeds contain the same article.

6. **Data Persistence**: Writes processed feeds to JSON files (`rss_{category}.json`) with creation timestamps for cache management.

7. **Selective or Batch Processing**: Can process a single category or all categories at once.

8. **Optional Author Display**: Per-category configuration to show feed author or source name.

9. **Logging Support**: Optional verbose output during feed fetching operations.

## Triage

### Critical Gaps (P0)
1. **No error handling for individual feeds** - One failing feed crashes processing or silently fails
2. **No validation of feeds.json structure** - Malformed configuration causes runtime errors
3. **Missing timeout configuration** - Slow/hung feeds can block indefinitely
4. **No duplicate entry handling within single feed** - Same ID overwrites without warning

### Important Gaps (P1)
5. **Hardcoded timezone** - Not configurable per-user
6. **No feed metadata storage** - Last successful fetch time, error counts not tracked
7. **No rate limiting** - Could hammer feed servers
8. **Bare except clauses** - Masks actual errors, makes debugging impossible
9. **No data directory initialization error handling** - mkdir can fail due to permissions

### Nice-to-Have Gaps (P2)
10. **No feed entry limits** - Could accumulate unbounded data
11. **No OPML import/export** - Standard RSS feature missing
12. **No conditional GET support** - Fetches entire feeds even when unchanged (no ETag/Last-Modified handling)
13. **No user agent string** - Some feeds may block or throttle
14. **Timestamp collision handling** - Entries published in same second overwrite each other
15. **No logging framework** - Uses print statements instead of proper logging

## Plan

### P0 Fixes

**1. Individual Feed Error Handling**
```python
# In get_feed_from_rss(), replace the try/except block:
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
        
        # Check for parsing errors
        if hasattr(d, 'bozo') and d.bozo:
            if log:
                sys.stderr.write(f" - Warning: {d.bozo_exception}\n")
            continue
            
    except Exception as e:
        if log:
            sys.stderr.write(f" - Failed: {str(e)}\n")
        continue  # Don't exit, continue with other feeds
```

**2. Configuration Validation**
```python
# Add after loading RSS from feeds.json:
def validate_feeds_config(config):
    """Validate feeds.json structure."""
    if not isinstance(config, dict):
        raise ValueError("feeds.json must contain a JSON object")
    
    for category, data in config.items():
        if not isinstance(data, dict):
            raise ValueError(f"Category '{category}' must be an object")
        if 'feeds' not in data:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(data['feeds'], dict):
            raise ValueError(f"Category '{category}' feeds must be an object")
        
    return True

# Use it:
with open(FEEDS_FILE_NAME, "r") as fp:
    RSS = json.load(fp)
    validate_feeds_config(RSS)
```

**3. Timeout Configuration**
```python
# Add at top of file:
FEED_TIMEOUT = 30  # seconds

# Modify parse call:
d = feedparser.parse(url, timeout=FEED_TIMEOUT)
```

**4. Duplicate Entry Handling**
```python
# Change from dict assignment to collision checking:
entry_id = f"{ts}_{hash(feed.link) % 10000}"  # Add URL hash to prevent collisions
entries = {
    "id": entry_id,
    # ... rest of fields
}

if entry_id in rslt:
    if log:
        sys.stderr.write(f"Warning: Duplicate entry ID {entry_id}\n")
else:
    rslt[entry_id] = entries
```

### P1 Fixes

**5. Configurable Timezone**
```python
# In config.py, load from environment or config file:
import os
TIMEZONE_HOURS = int(os.environ.get('RREADER_TIMEZONE', '9'))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_HOURS))

# Or add to feeds.json:
{
    "settings": {
        "timezone_offset": 9
    },
    "categories": { ... }
}
```

**6. Feed Metadata Storage**
```python
# Create a new metadata.json file:
metadata_structure = {
    "category_name": {
        "source_name": {
            "last_success": timestamp,
            "last_attempt": timestamp,
            "consecutive_failures": 0,
            "last_error": "error message"
        }
    }
}

# Update after each fetch attempt:
def update_feed_metadata(category, source, success, error=None):
    metadata_file = os.path.join(p["path_data"], "metadata.json")
    # Load, update, save metadata
```

**7. Rate Limiting**
```python
# Add between feed fetches:
import time
FEED_FETCH_DELAY = 1  # seconds between requests

for source, url in urls.items():
    time.sleep(FEED_FETCH_DELAY)
    # ... existing fetch code
```

**8. Specific Exception Handling**
```python
# Replace all bare except clauses:
except Exception as e:
    if log:
        sys.stderr.write(f"Error processing feed {source}: {type(e).__name__}: {str(e)}\n")
    continue
```

**9. Directory Creation Error Handling**
```python
# In common.py:
for d in p["pathkeys"]:
    if not os.path.exists(p[d]):
        try:
            os.makedirs(p[d], exist_ok=True)
        except OSError as e:
            sys.stderr.write(f"Cannot create directory {p[d]}: {e}\n")
            sys.exit(1)
```

### P2 Fixes

**10. Feed Entry Limits**
```python
# Add to configuration:
MAX_ENTRIES_PER_CATEGORY = 1000

# Apply when saving:
rslt = [val for key, val in sorted(rslt.items(), reverse=True)][:MAX_ENTRIES_PER_CATEGORY]
```

**11. OPML Import/Export**
```python
# Add new functions:
def export_opml(output_file):
    """Export feeds.json to OPML format."""
    # Build OPML XML structure from RSS dict
    
def import_opml(input_file):
    """Import OPML file and merge with existing feeds."""
    # Parse OPML, update feeds.json
```

**12. Conditional GET Support**
```python
# Store ETags and Last-Modified in metadata:
def get_feed_from_rss(...):
    # Load previous ETag/Last-Modified from metadata
    headers = {}
    if previous_etag:
        headers['If-None-Match'] = previous_etag
    if previous_modified:
        headers['If-Modified-Since'] = previous_modified
    
    d = feedparser.parse(url, etag=previous_etag, modified=previous_modified)
    
    if d.status == 304:  # Not Modified
        return cached_data
```

**13. User Agent String**
```python
# Add constant:
USER_AGENT = "rreader/1.0 (+https://github.com/yourname/rreader)"

# Pass to feedparser:
d = feedparser.parse(url, agent=USER_AGENT)
```

**14. Timestamp Collision Prevention**
```python
# Already addressed in P0 #4 above
```

**15. Proper Logging Framework**
```python
import logging

# Setup at module level:
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Replace all sys.stdout.write/sys.stderr.write:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}: {error}")
```