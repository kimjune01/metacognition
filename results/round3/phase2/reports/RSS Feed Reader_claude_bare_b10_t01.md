# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Aggregation**: Parses multiple RSS feeds from various sources using the `feedparser` library and consolidates entries.

2. **Feed Configuration Management**: 
   - Reads feed sources from a JSON configuration file (`feeds.json`)
   - Automatically copies bundled default feeds if user configuration doesn't exist
   - Merges new categories from bundled feeds into existing user configuration

3. **Data Extraction**: Extracts key metadata from RSS entries including:
   - Publication/update timestamps
   - Article titles and URLs
   - Source/author information
   - Normalized timestamps

4. **Time Localization**: Converts UTC timestamps to a configured timezone (KST/UTC+9) and formats them as either "HH:MM" (for today) or "MMM DD, HH:MM" (for other dates).

5. **Data Persistence**: Saves processed feeds as JSON files in `~/.rreader/` directory with format `rss_{category}.json`.

6. **Deduplication**: Uses timestamp as ID to prevent duplicate entries from the same feed source.

7. **Sorted Output**: Entries are sorted by timestamp in reverse chronological order (newest first).

8. **Selective Processing**: Can process either all feed categories or a single target category.

9. **Optional Logging**: Provides progress feedback when `log=True`.

## Triage

### Critical Gaps (P0 - System Stability)

1. **Silent Exception Handling**: Multiple bare `except:` clauses that exit or continue without logging errors
2. **No Error Recovery**: Failed feed fetches abort processing or skip silently
3. **No Input Validation**: Assumes feed data structure without validation
4. **Duplicate ID Collisions**: Using only timestamp as ID causes collisions when multiple articles publish simultaneously

### High Priority Gaps (P1 - Production Readiness)

5. **No Retry Logic**: Network failures permanently fail feed fetches
6. **No Rate Limiting**: Could hammer RSS servers or get blocked
7. **No Caching Strategy**: Re-fetches all feeds every time, ignoring HTTP caching headers
8. **Missing Configuration Validation**: No validation that `feeds.json` has correct structure
9. **No Concurrent Processing**: Feeds are fetched sequentially, causing slow performance
10. **No Metrics/Monitoring**: No way to track success rates, timing, or failures

### Medium Priority Gaps (P2 - Usability & Maintenance)

11. **No Feed Update Detection**: No mechanism to track what's new since last fetch
12. **Hardcoded Timezone**: Timezone is hardcoded rather than configurable per-user
13. **No Maximum Age Filter**: Old entries accumulate indefinitely
14. **No Content Sanitization**: HTML in titles/descriptions isn't sanitized
15. **Limited Logging**: Logging is binary (on/off) without levels (DEBUG, INFO, ERROR)
16. **No CLI Interface**: No argument parsing for command-line usage

### Low Priority Gaps (P3 - Nice to Have)

17. **No Feed Health Tracking**: No tracking of historically reliable vs. problematic feeds
18. **No OPML Import/Export**: Standard RSS format not supported
19. **No Read/Unread Tracking**: No user state management
20. **No Search Functionality**: Can't search across aggregated feeds

## Plan

### P0 Fixes

**1. Silent Exception Handling**
- Replace all bare `except:` with specific exception types
- Add proper logging with `logging` module instead of print statements
- Example for feed parsing:
```python
import logging
try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser error flag
        logging.error(f"Feed parse error for {url}: {d.bozo_exception}")
        continue
except (urllib.error.URLError, socket.timeout) as e:
    logging.error(f"Network error fetching {url}: {e}")
    continue
except Exception as e:
    logging.exception(f"Unexpected error parsing {url}")
    continue
```

**2. Error Recovery**
- Remove `sys.exit()` calls from error handlers
- Accumulate errors and return status summary
- Add a results structure: `{"success": [], "failed": [{"url": url, "error": str}]}`

**3. Input Validation**
- Add JSON schema validation for feeds.json:
```python
from jsonschema import validate, ValidationError

FEEDS_SCHEMA = {
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

# Validate after loading
validate(instance=RSS, schema=FEEDS_SCHEMA)
```

**4. Duplicate ID Collisions**
- Change ID generation to include URL hash:
```python
import hashlib
id_hash = hashlib.md5(f"{ts}:{feed.link}".encode()).hexdigest()[:8]
entries["id"] = f"{ts}_{id_hash}"
```

### P1 Fixes

**5. Retry Logic**
- Implement exponential backoff using `urllib3.util.retry` or `tenacity`:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), 
       wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_feed(url):
    return feedparser.parse(url)
```

**6. Rate Limiting**
- Add delays between requests:
```python
import time
FETCH_DELAY = 1.0  # seconds between requests

for source, url in urls.items():
    time.sleep(FETCH_DELAY)
    # ... fetch logic
```
- Consider using `ratelimit` library for more sophisticated limiting

**7. Caching Strategy**
- Implement ETags and Last-Modified headers:
```python
# Store previous ETags/Last-Modified in cache.json
cache_key = hashlib.md5(url.encode()).hexdigest()
cached = load_cache().get(cache_key, {})

d = feedparser.parse(url, 
                     etag=cached.get('etag'),
                     modified=cached.get('modified'))

if d.status == 304:  # Not modified
    continue

# Save new ETags
save_cache(cache_key, {'etag': d.etag, 'modified': d.modified})
```

**8. Configuration Validation**
- Validate feeds.json structure on load
- Check that URLs are valid: `urllib.parse.urlparse(url).scheme in ['http', 'https']`
- Provide helpful error messages for malformed configs

**9. Concurrent Processing**
- Use ThreadPoolExecutor for parallel fetching:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    # ... existing fetch logic
    return source, entries

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source, entries = future.result()
        rslt.update(entries)
```

**10. Metrics/Monitoring**
- Add structured logging with timing:
```python
import time
start = time.time()
# ... fetch operation
duration = time.time() - start
logging.info(f"Fetched {url} in {duration:.2f}s, {len(entries)} entries")
```
- Write summary statistics to file:
```python
stats = {
    "last_run": int(time.time()),
    "feeds_processed": successful_count,
    "feeds_failed": failed_count,
    "total_entries": entry_count
}
```

### P2 Fixes

**11. Feed Update Detection**
- Store previous entry IDs in state file
- Return only new entries: `new_entries = current_ids - previous_ids`

**12. Configurable Timezone**
- Move TIMEZONE to feeds.json or separate config:
```python
config = load_config()
TIMEZONE = datetime.timezone(datetime.timedelta(
    hours=config.get('timezone_offset', 9)
))
```

**13. Maximum Age Filter**
- Add configuration for max age (e.g., 7 days)
- Filter entries: `if (time.time() - ts) > MAX_AGE_SECONDS: continue`

**14. Content Sanitization**
- Use `bleach` or `html.escape` for titles:
```python
import html
entries["title"] = html.escape(feed.title)
```

**15. Structured Logging**
- Replace print statements with proper logging:
```python
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
```

**16. CLI Interface**
- Add argparse for proper CLI:
```python
import argparse
parser = argparse.ArgumentParser()
parser.add_argument('--category', help='Specific category to fetch')
parser.add_argument('--log-level', default='INFO')
parser.add_argument('--config', default=FEEDS_FILE_NAME)
args = parser.parse_args()
```

### P3 Fixes

**17-20**: These are feature additions rather than fixes. Each would require:
- Requirements gathering and design documentation
- Database or persistent state management (consider SQLite)
- API design for read/unread state
- Search indexing (potentially using SQLite FTS or external search)
- OPML parser/generator using xml.etree.ElementTree