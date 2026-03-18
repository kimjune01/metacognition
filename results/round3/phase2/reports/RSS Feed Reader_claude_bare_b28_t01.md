# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds using the `feedparser` library from multiple sources organized by category.

2. **Feed Configuration Management**: 
   - Loads feed sources from a `feeds.json` configuration file
   - Automatically copies bundled default feeds if user configuration doesn't exist
   - Merges new categories from bundled feeds into existing user configuration

3. **Data Normalization**: Extracts and standardizes feed entries with:
   - Unique ID (timestamp-based)
   - Source name (with optional author display)
   - Publication date (formatted relative to current date)
   - URL and title
   - Unix timestamp for sorting

4. **Timezone Handling**: Converts UTC timestamps to a configured timezone (KST/UTC+9).

5. **Output Generation**: 
   - Sorts entries by timestamp (newest first)
   - Outputs JSON files per category to `~/.rreader/` directory
   - Includes metadata (creation timestamp)

6. **Selective Processing**: Can process either all categories or a single target category.

7. **Directory Management**: Automatically creates data directory if it doesn't exist.

## Triage

### Critical Gaps

1. **No Error Handling for Individual Feeds** - When one feed fails, the entire process exits with `sys.exit()`, preventing other feeds from being processed.

2. **Silent Failures** - The `try/except` block around feed parsing swallows all exceptions without logging what went wrong.

3. **Missing Configuration Validation** - No validation that `feeds.json` has the expected structure before processing.

### High Priority Gaps

4. **No Logging Infrastructure** - The `log` parameter only controls stdout output; there's no persistent logging of errors, warnings, or processing statistics.

5. **Duplicate Entry Handling** - Using timestamp as ID means multiple entries published at the same second will overwrite each other.

6. **No Network Timeout Configuration** - Feed requests could hang indefinitely on slow/unresponsive servers.

7. **Missing Feed Metadata** - No tracking of last successful fetch time, error counts, or feed health status.

### Medium Priority Gaps

8. **No Rate Limiting** - Sequential requests without delays could overwhelm servers or trigger rate limits.

9. **No Caching/Conditional Requests** - Every run fetches complete feeds without using ETags or Last-Modified headers.

10. **Incomplete Date Parsing Fallback** - If both `published_parsed` and `updated_parsed` are missing, the entry is silently skipped.

11. **No Data Retention Policy** - Old JSON files accumulate without cleanup or archival.

12. **Hard-coded Timezone** - Timezone is in config but not easily changeable per user preference.

### Low Priority Gaps

13. **No Feed Discovery/Validation** - No way to test if a URL is a valid RSS/Atom feed before adding it.

14. **Missing CLI Interface** - No argument parsing for command-line usage (category selection, verbose mode, etc.).

15. **No Progress Indication** - For many feeds, users have no visibility into processing status.

16. **No HTML Sanitization** - Feed titles may contain unsafe HTML that isn't stripped.

## Plan

### 1. Fix Critical Error Handling

**Changes needed:**
- Replace `sys.exit()` in the feed parsing exception with a logged warning and `continue`
- Add specific exception handling with error messages:
```python
except Exception as e:
    error_msg = f"Failed to parse {url}: {str(e)}"
    if log:
        sys.stderr.write(f" - {error_msg}\n")
    # Log to file here
    continue
```

### 2. Implement Proper Logging

**Changes needed:**
- Add `import logging` and configure a logger at module level
- Create a rotating log file in `~/.rreader/rreader.log`
- Replace all `sys.stdout.write` and add structured logging:
```python
logger = logging.getLogger(__name__)
logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
```
- Log: start/end times, feed URLs, success/failure status, exception details

### 3. Fix Entry ID Collision

**Changes needed:**
- Generate unique IDs using a combination of timestamp and URL hash:
```python
import hashlib
entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
```
- Update the dictionary key to use this composite ID
- Keep timestamp as separate field for sorting

### 4. Add Configuration Validation

**Changes needed:**
- Create a validation function before processing:
```python
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must contain a JSON object")
    for category, data in config.items():
        if "feeds" not in data:
            raise ValueError(f"Category '{category}' missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category '{category}' feeds must be a dict")
    return True
```
- Call after loading JSON, catch and log exceptions

### 5. Add Network Timeout and Retry Logic

**Changes needed:**
- Configure feedparser timeout by setting socket default timeout:
```python
import socket
socket.setdefaulttimeout(30)  # 30 second timeout
```
- Add retry logic with exponential backoff:
```python
from time import sleep
MAX_RETRIES = 3
for attempt in range(MAX_RETRIES):
    try:
        d = feedparser.parse(url)
        if d.bozo == 0 or d.entries:  # Success
            break
    except Exception as e:
        if attempt == MAX_RETRIES - 1:
            logger.error(f"Failed after {MAX_RETRIES} attempts: {url}")
        else:
            sleep(2 ** attempt)  # 1s, 2s, 4s
```

### 6. Implement Feed Metadata Tracking

**Changes needed:**
- Create a `feed_status.json` file to track:
```json
{
  "category": {
    "source_url": {
      "last_success": timestamp,
      "last_attempt": timestamp,
      "consecutive_failures": 0,
      "total_entries_fetched": 0
    }
  }
}
```
- Update after each feed fetch
- Use to skip consistently failing feeds or alert on problems

### 7. Add Rate Limiting

**Changes needed:**
- Add configurable delay between feeds:
```python
FEED_DELAY_SECONDS = 1.0  # Add to config.py
# In the loop:
if log:
    sys.stdout.write(" - Done\n")
time.sleep(FEED_DELAY_SECONDS)
```

### 8. Implement Conditional Requests

**Changes needed:**
- Store ETags and Last-Modified headers in feed metadata
- Pass to feedparser:
```python
d = feedparser.parse(url, 
                     etag=stored_etag,
                     modified=stored_modified)
if d.status == 304:  # Not modified
    logger.info(f"Feed unchanged: {url}")
    continue
# Store new etag/modified values
```

### 9. Add Data Retention

**Changes needed:**
- Add configuration for retention policy:
```python
MAX_ENTRIES_PER_CATEGORY = 1000
MAX_AGE_DAYS = 30
```
- Before writing JSON, filter entries:
```python
cutoff_time = int(time.time()) - (MAX_AGE_DAYS * 86400)
rslt = [e for e in rslt if e["timestamp"] > cutoff_time][:MAX_ENTRIES_PER_CATEGORY]
```

### 10. Build CLI Interface

**Changes needed:**
- Add argparse to `if __name__ == "__main__"` block:
```python
import argparse
parser = argparse.ArgumentParser(description='RSS Feed Reader')
parser.add_argument('-c', '--category', help='Process single category')
parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
parser.add_argument('--list-categories', action='store_true', help='List available categories')
args = parser.parse_args()
```
- Implement list-categories option to show configured feeds

### 11. Add HTML Sanitization

**Changes needed:**
- Install and import `bleach` or use built-in html.parser:
```python
import html
# In entry processing:
"title": html.unescape(feed.title).strip()
```
- For more robust cleaning, use bleach to strip all HTML tags

### 12. Add Feed Health Monitoring

**Changes needed:**
- Create a `check_feeds()` function that validates URLs and reports status
- Add `--check` CLI flag to run diagnostics without fetching
- Output summary: total feeds, healthy, failing, last success times