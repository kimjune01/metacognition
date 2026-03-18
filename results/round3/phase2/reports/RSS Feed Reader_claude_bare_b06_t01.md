# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Feed Management**: Supports organizing feeds into categories, with each category containing multiple feed sources.

3. **Feed Configuration System**: 
   - Maintains a `feeds.json` configuration file in `~/.rreader/`
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled config into user config on updates

4. **Data Normalization**: Extracts and normalizes feed entries with:
   - Unique timestamp-based IDs
   - Source name/author attribution
   - Publication dates (formatted as "HH:MM" for today, "MMM DD, HH:MM" for older)
   - URLs and titles
   - Timezone conversion (hardcoded to UTC+9/KST)

5. **Deduplication**: Uses timestamp as ID to prevent duplicate entries from the same source.

6. **Sorting**: Orders entries by timestamp (newest first).

7. **JSON Storage**: Persists parsed feeds as JSON files (`rss_{category}.json`) with metadata including creation timestamp.

8. **Selective Processing**: Can process a single category or all categories.

9. **Optional Logging**: Provides console output for feed fetching progress.

## Triage

### Critical Gaps (Production Blockers)

1. **Error Handling**: Bare `except` clauses and `sys.exit(0)` on failure silently swallow errors. Failed feeds break execution.

2. **Missing Dependencies**: Imports `feedparser` without documenting requirements or handling import failures gracefully.

3. **Timezone Configuration**: Hardcoded UTC+9 timezone; not configurable per-user.

4. **No Feed Validation**: Assumes `feeds.json` structure is correct; malformed JSON will crash.

### High Priority (Usability/Reliability)

5. **No Retry Logic**: Network failures permanently fail feed fetches with no retry mechanism.

6. **No Rate Limiting**: Rapid sequential requests could trigger rate limits or be considered abusive.

7. **No Cache Validation**: Always fetches full feeds; doesn't use ETags or Last-Modified headers.

8. **ID Collision Risk**: Using timestamp as ID can cause collisions if multiple entries published at same second.

9. **No Stale Data Handling**: Old cached feeds never expire or get marked as stale.

10. **Missing User Feedback**: No indication of how many feeds succeeded/failed or what data was retrieved.

### Medium Priority (Features/Maintainability)

11. **No Feed Management API**: Can't add/remove/update feeds without manually editing JSON.

12. **Limited Date Handling Fallback**: Only tries `published_parsed` then `updated_parsed`; some feeds use other fields.

13. **No Content Extraction**: Only saves title/link; doesn't preserve description, content, or enclosures.

14. **No Entry Limit**: Processes all entries; large feeds waste resources and storage.

15. **Hardcoded Paths**: Data directory location not configurable.

16. **No Concurrency**: Sequential processing; slow for many feeds.

### Low Priority (Nice to Have)

17. **No OPML Import/Export**: Can't easily migrate feeds from/to other readers.

18. **No Statistics**: Doesn't track fetch success rates, feed health, or update frequencies.

19. **Limited Metadata**: Doesn't store feed-level info (description, icon, last build date).

## Plan

### 1. Error Handling
**Changes needed:**
- Replace bare `except:` with specific exceptions (`feedparser.FeedParserException`, `requests.exceptions.RequestException`, etc.)
- Change `sys.exit(0)` to continue processing other feeds and accumulate errors
- Add error logging to capture which feeds failed and why
- Return a status object indicating success/failure counts

```python
errors = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        if d.bozo:  # feedparser error flag
            errors.append({"source": source, "error": str(d.bozo_exception)})
            continue
    except Exception as e:
        errors.append({"source": source, "error": str(e)})
        continue
```

### 2. Missing Dependencies
**Changes needed:**
- Create `requirements.txt` with `feedparser>=6.0.0`
- Add docstring documenting dependencies
- Consider adding import error messages suggesting `pip install`

### 3. Timezone Configuration
**Changes needed:**
- Move `TIMEZONE` to `feeds.json` as a top-level setting
- Add default of UTC if not specified
- Parse timezone string (e.g., "America/New_York") using `zoneinfo` or `pytz`

```python
import zoneinfo
tz_string = config.get("timezone", "UTC")
TIMEZONE = zoneinfo.ZoneInfo(tz_string)
```

### 4. Feed Validation
**Changes needed:**
- Add JSON schema validation for `feeds.json`
- Validate on load; provide clear error messages for malformed config
- Create a `validate_feeds_config()` function

```python
import jsonschema
schema = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"}
            }
        }
    }
}
```

### 5. Retry Logic
**Changes needed:**
- Add retry decorator or use `requests` with `urllib3.Retry`
- Implement exponential backoff (e.g., 1s, 2s, 4s delays)
- Make retry count configurable (default: 3)

```python
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

### 6. Rate Limiting
**Changes needed:**
- Add configurable delay between feed fetches (default: 1 second)
- Use `time.sleep()` between requests
- Consider per-domain rate limiting for feeds from same host

```python
import time
for source, url in urls.items():
    time.sleep(config.get("fetch_delay", 1.0))
    # ... fetch feed
```

### 7. Cache Validation
**Changes needed:**
- Store ETags and Last-Modified headers from responses
- Send conditional requests using `If-None-Match`/`If-Modified-Since`
- Skip parsing if server returns 304 Not Modified

```python
# In get_feed_from_rss, load cached headers
cache_meta = load_cache_metadata(category)
headers = {}
if source in cache_meta:
    if 'etag' in cache_meta[source]:
        headers['If-None-Match'] = cache_meta[source]['etag']
# Pass headers to feedparser
```

### 8. ID Collision Risk
**Changes needed:**
- Change ID generation to `f"{ts}_{hash(feed.link)[:8]}"` for uniqueness
- Or use feed GUID if available: `feed.get('id', feed.link)`

```python
entry_id = feed.get('id') or f"{ts}_{hash(feed.link) % 100000000}"
```

### 9. Stale Data Handling
**Changes needed:**
- Add `max_age` configuration (default: 24 hours)
- Check `created_at` timestamp when loading cached data
- Display warning/indicator if data is stale
- Auto-refresh stale categories

```python
if time.time() - cached_data['created_at'] > config.get('max_age', 86400):
    # Mark as stale or trigger refresh
```

### 10. User Feedback
**Changes needed:**
- Return/print summary: "Fetched X feeds, Y entries, Z errors"
- Add progress indicator for batch operations
- Option for verbose mode showing per-feed statistics

```python
return {
    "entries": rslt,
    "created_at": int(time.time()),
    "stats": {
        "feeds_fetched": len(urls),
        "feeds_failed": len(errors),
        "total_entries": len(rslt),
        "errors": errors
    }
}
```

### 11. Feed Management API
**Changes needed:**
- Create functions: `add_feed(category, name, url)`, `remove_feed(category, name)`, `list_feeds()`
- Add CLI commands or interactive mode
- Validate URLs before adding

```python
def add_feed(category, name, url):
    with open(FEEDS_FILE_NAME, 'r') as f:
        feeds = json.load(f)
    if category not in feeds:
        feeds[category] = {"feeds": {}, "show_author": False}
    feeds[category]["feeds"][name] = url
    with open(FEEDS_FILE_NAME, 'w') as f:
        json.dump(feeds, f, indent=4)
```

### 12. Date Handling Fallback
**Changes needed:**
- Try multiple date fields in order: `published_parsed`, `updated_parsed`, `created_parsed`
- Parse date strings if parsed version unavailable
- Use current time as last resort with warning

```python
parsed_time = (getattr(feed, 'published_parsed', None) or 
               getattr(feed, 'updated_parsed', None) or
               getattr(feed, 'created_parsed', None))
```

### 13. Content Extraction
**Changes needed:**
- Add `description` and `content` fields to entries dict
- Store first enclosure (for podcasts/media)
- Make content storage optional to save space

```python
entries = {
    # ... existing fields
    "description": feed.get('summary', ''),
    "content": feed.get('content', [{}])[0].get('value', ''),
    "enclosure": feed.get('enclosures', [{}])[0].get('href', None)
}
```

### 14. Entry Limit
**Changes needed:**
- Add `max_entries_per_feed` config (default: 50)
- Slice entries list after sorting: `rslt[:max_entries]`

```python
max_entries = config.get('max_entries_per_feed', 50)
rslt = [val for key, val in sorted(rslt.items(), reverse=True)[:max_entries]]
```

### 15. Hardcoded Paths
**Changes needed:**
- Accept `data_dir` parameter in `do()` function
- Read from environment variable `RREADER_DATA_DIR`
- Add command-line argument for custom path

```python
data_dir = os.getenv('RREADER_DATA_DIR', str(Path.home()) + "/.rreader/")
p = {"path_data": data_dir}
```

### 16. Concurrency
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel fetching
- Limit workers (default: 5) to avoid overwhelming system
- Collect results and errors from all threads

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_feed, url): source 
               for source, url in urls.items()}
    for future in as_completed(futures):
        # process result
```

### 17. OPML Import/Export
**Changes needed:**
- Add `import_opml(filename)` function using XML parsing
- Add `export_opml(filename)` function generating OPML XML
- Map OPML categories to internal categories

```python
import xml.etree.ElementTree as ET

def import_opml(filename):
    tree = ET.parse(filename)
    for outline in tree.findall('.//outline[@type="rss"]'):
        category = outline.get('category', 'Imported')
        add_feed(category, outline.get('text'), outline.get('xmlUrl'))
```

### 18. Statistics
**Changes needed:**
- Create `stats.json` tracking per-feed metrics
- Record: last_fetch_time, last_success, failure_count, avg_entries
- Add `show_stats()` function for reporting

### 19. Feed Metadata
**Changes needed:**
- Store feed-level data in separate `feed_info_{category}.json`
- Extract: feed.feed.title, feed.feed.description, feed.feed.image
- Use for display/organization purposes