# Diagnostic Report: RSS Reader System

## Observations

This system is a functional RSS feed reader with the following working capabilities:

1. **Feed Parsing**: Retrieves and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Timestamp Handling**: Extracts publication dates from feeds (trying both `published_parsed` and `updated_parsed`)
4. **Timezone Localization**: Converts UTC timestamps to a configured timezone (currently KST/UTC+9)
5. **Date Formatting**: Displays times as "HH:MM" for today's entries, "MMM DD, HH:MM" for older entries
6. **Deduplication**: Uses timestamp as unique ID to prevent duplicate entries within a category
7. **Persistence**: Saves parsed feeds to JSON files (`rss_{category}.json`) in user's home directory
8. **Configuration Management**: 
   - Bundles default feeds in `feeds.json` alongside the script
   - Copies to user directory on first run
   - Merges new bundled categories into existing user config
9. **Selective Updates**: Can update a single category or all categories
10. **Logging**: Optional progress output during feed fetching

## Triage

### Critical Gaps
1. **No Error Recovery** - Individual feed failures crash the entire category update
2. **Missing Feed Configuration** - The bundled `feeds.json` file is referenced but not provided
3. **No Caching/Rate Limiting** - Fetches all feeds on every run with no respect for server resources
4. **No Data Validation** - Malformed feed data can cause silent failures or corrupted output

### Important Gaps
5. **No Entry Age Management** - Old entries accumulate indefinitely, files grow unbounded
6. **Missing Read/Unread Tracking** - No way to mark entries as read or filter viewed content
7. **No Network Timeout Configuration** - Can hang indefinitely on slow/dead servers
8. **Limited Timezone Configuration** - Hardcoded to KST with no user override
9. **No Concurrent Fetching** - Sequential processing is slow for many feeds
10. **Poor Logging Infrastructure** - Boolean flag instead of proper logging levels

### Nice-to-Have Gaps
11. **No CLI Interface** - No command-line arguments for common operations
12. **Missing Entry Filtering** - Can't filter by date range, source, or keywords
13. **No Feed Health Monitoring** - No tracking of consistently failing feeds
14. **Limited Metadata** - Doesn't preserve descriptions, images, or tags from feeds
15. **No Export Functionality** - Can't export to other formats (OPML, HTML, etc.)

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Wrap `feedparser.parse()` in try-except block that catches all exceptions
- Continue processing remaining feeds in category when one fails
- Collect errors and report at end: `{"errors": [{"source": "X", "error": "message"}]}`
- Add to JSON output: `"failed_sources": ["source1", "source2"]`
- Change exit behavior: only exit on total failure (no feeds parsed), not individual failures

### 2. Provide Feed Configuration (Critical)
**Changes needed:**
- Create `feeds.json` file with structure:
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
- Document the expected structure in README or docstring

### 3. Implement Caching (Critical)
**Changes needed:**
- Add timestamp field `"last_fetched"` to each category's JSON output
- Add parameter `max_age_seconds` (default 900 = 15 minutes)
- Before fetching, check: `time.time() - rslt["created_at"] < max_age_seconds`
- If fresh, return cached data instead of fetching
- Add `force_refresh=False` parameter to override cache

### 4. Data Validation (Critical)
**Changes needed:**
- Validate required fields before adding entry:
```python
if not all([feed.get('link'), feed.get('title'), parsed_time]):
    continue  # Skip invalid entries
```
- Sanitize URLs: check they start with http/https
- Truncate excessively long titles (e.g., 500 char max)
- Handle missing `d.entries` gracefully: `for feed in getattr(d, 'entries', []):`

### 5. Entry Age Management (Important)
**Changes needed:**
- Add configuration: `MAX_ENTRY_AGE_DAYS = 7`
- Before saving, filter entries:
```python
cutoff = time.time() - (MAX_ENTRY_AGE_DAYS * 86400)
rslt["entries"] = [e for e in rslt["entries"] if e["timestamp"] > cutoff]
```
- Add to config file per-category: `"max_age_days": 7`

### 6. Read/Unread Tracking (Important)
**Changes needed:**
- Add `"read": false` field to each entry in JSON
- Create separate file `rss_state.json` mapping entry IDs to read status
- Add function `mark_read(category, entry_ids)` that updates state file
- When loading, merge state into entries: `entry["read"] = state.get(entry_id, False)`
- Add CLI command or API to mark entries read

### 7. Network Timeout Configuration (Important)
**Changes needed:**
- Install timeout support: `pip install requests` (feedparser uses it)
- Configure at module level:
```python
import socket
socket.setdefaulttimeout(30)  # 30 second timeout
```
- Or pass to feedparser: Research if feedparser.parse accepts timeout parameter
- Make configurable: `NETWORK_TIMEOUT_SECONDS = 30` in config.py

### 8. Configurable Timezone (Important)
**Changes needed:**
- Change config.py:
```python
TIMEZONE_OFFSET_HOURS = int(os.getenv('RREADER_TZ_OFFSET', '9'))
TIMEZONE = datetime.timezone(datetime.timedelta(hours=TIMEZONE_OFFSET_HOURS))
```
- Add to feeds.json: `"_settings": {"timezone_offset": 9}`
- Prioritize: environment variable > feeds.json > default

### 9. Concurrent Fetching (Important)
**Changes needed:**
- Add import: `from concurrent.futures import ThreadPoolExecutor, as_completed`
- Replace loop in `get_feed_from_rss`:
```python
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, source, url): source 
               for source, url in urls.items()}
    for future in as_completed(futures):
        result = future.result()  # Handle errors here
```
- Extract single-feed logic into `fetch_single_feed(source, url)` function

### 10. Proper Logging (Important)
**Changes needed:**
- Replace `log` parameter with standard logging:
```python
import logging
logger = logging.getLogger(__name__)
```
- Replace print statements: `logger.info(f"Fetching {url}")`
- Configure in main: `logging.basicConfig(level=logging.INFO)`
- Add levels: DEBUG for verbose, INFO for normal, WARNING for errors

### 11. CLI Interface (Nice-to-have)
**Changes needed:**
- Add import: `import argparse`
- In `if __name__ == "__main__":` block:
```python
parser = argparse.ArgumentParser(description='RSS Reader')
parser.add_argument('--category', help='Update specific category')
parser.add_argument('--force', action='store_true', help='Force refresh')
parser.add_argument('--verbose', action='store_true', help='Verbose output')
args = parser.parse_args()
do(target_category=args.category, log=args.verbose)
```

### 12. Entry Filtering (Nice-to-have)
**Changes needed:**
- Add function `filter_entries(entries, **kwargs)` that accepts:
  - `since_timestamp`: only entries after this time
  - `sources`: list of source names to include
  - `keywords`: list of keywords to search in title
- Return filtered list
- Use in reading interface, not during fetch

### 13. Feed Health Monitoring (Nice-to-have)
**Changes needed:**
- Create `feed_health.json` tracking per-feed statistics:
```json
{
  "source_name": {
    "last_success": 1234567890,
    "last_failure": 1234567800,
    "consecutive_failures": 2,
    "total_fetches": 100
  }
}
```
- Update after each fetch attempt
- Alert when `consecutive_failures > 3`

### 14. Extended Metadata (Nice-to-have)
**Changes needed:**
- Expand entries dictionary:
```python
entries = {
    # ... existing fields ...
    "description": getattr(feed, 'summary', '')[:500],  # Truncated
    "image": getattr(feed, 'media_thumbnail', [{}])[0].get('url'),
    "tags": [tag.term for tag in getattr(feed, 'tags', [])]
}
```
- Make optional via config: `"include_extended_metadata": true`

### 15. Export Functionality (Nice-to-have)
**Changes needed:**
- Add function `export_opml(output_file)` that reads feeds.json and generates OPML:
```python
def export_opml(output_file):
    with open(FEEDS_FILE_NAME) as f:
        feeds = json.load(f)
    # Build OPML XML structure
    # Write to output_file
```
- Add CLI command: `--export-opml feeds.opml`
- Similarly for HTML export with styled output