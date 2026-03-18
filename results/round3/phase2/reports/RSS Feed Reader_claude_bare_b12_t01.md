# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-Source Aggregation**: Processes multiple feed URLs organized by category
3. **Configuration Management**: 
   - Loads feed configurations from a JSON file (`feeds.json`)
   - Automatically copies bundled default feeds if user config doesn't exist
   - Merges new categories from bundled config into existing user config
4. **Data Normalization**: Extracts and standardizes feed entries with:
   - Unique ID (timestamp-based)
   - Source name/author
   - Publication date (formatted for display)
   - URL and title
5. **Time Handling**: Converts UTC timestamps to configured timezone (currently KST/UTC+9)
6. **Smart Date Formatting**: Shows time-only for today's entries, date+time for older entries
7. **Deduplication**: Uses timestamp-based dictionary keys to prevent duplicate entries
8. **Sorting**: Orders entries by timestamp (newest first)
9. **Persistence**: Saves processed feeds as JSON files (`rss_{category}.json`)
10. **Selective Processing**: Can process a single category or all categories
11. **Basic Logging**: Optional stdout logging for feed fetch operations

## Triage

### Critical Gaps
1. **No Error Recovery**: Failed feed fetches call `sys.exit()`, terminating entire process
2. **No Input Validation**: Missing validation for feed URLs, JSON structure, or timestamps
3. **ID Collision Risk**: Using integer timestamps as unique IDs guarantees collisions for feeds published in the same second

### High Priority
4. **No Rate Limiting**: Could overwhelm feed servers or trigger throttling/bans
5. **Missing Error Context**: Exception handling swallows all error details
6. **No Timeout Configuration**: Network requests can hang indefinitely
7. **Incomplete Logging**: No structured logging, file logging, or error tracking
8. **No Retry Logic**: Transient network failures cause permanent feed loss

### Medium Priority
9. **No Feed Validation**: Doesn't verify feed structure or required fields before processing
10. **Missing Metadata**: Doesn't store feed descriptions, images, or other rich content
11. **No Content Sanitization**: HTML in titles could cause rendering issues
12. **Hardcoded Configuration**: Timezone and paths partially hardcoded
13. **No Feed Health Monitoring**: Doesn't track feed availability or staleness

### Low Priority
14. **No Caching Strategy**: Re-fetches all feeds every time, wastes bandwidth
15. **No ETag/If-Modified-Since Support**: Doesn't use HTTP conditional requests
16. **Missing CLI Interface**: No argument parsing for operational control
17. **No Performance Metrics**: Can't measure fetch times or identify slow feeds

## Plan

### 1. Error Recovery (Critical)
**Change**: Replace `sys.exit()` with graceful error handling
```python
# Instead of:
except:
    sys.exit(" - Failed\n" if log else 0)

# Implement:
except Exception as e:
    if log:
        sys.stdout.write(f" - Failed: {str(e)}\n")
    continue  # Process remaining feeds
    # Log error details for later review
```
**Action**: Wrap each feed fetch in try-except, log errors, continue processing other feeds. Return partial results with error indicators.

### 2. Input Validation (Critical)
**Change**: Add validation functions before processing
```python
def validate_feed_config(config):
    """Validate feeds.json structure"""
    if not isinstance(config, dict):
        raise ValueError("Config must be dictionary")
    for category, data in config.items():
        if "feeds" not in data or not isinstance(data["feeds"], dict):
            raise ValueError(f"Category {category} missing 'feeds' dict")
        for name, url in data["feeds"].items():
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL for {name}: {url}")
    return True
```
**Action**: Validate JSON schema on load, URL formats, and feed entry structures before processing.

### 3. Fix ID Collisions (Critical)
**Change**: Generate truly unique IDs
```python
# Replace:
entries = {"id": ts, ...}

# With:
import hashlib
unique_id = hashlib.md5(f"{feed.link}{ts}".encode()).hexdigest()
entries = {"id": unique_id, "timestamp": ts, ...}
```
**Action**: Use combination of URL + timestamp hashed, or use feed GUID if available.

### 4. Rate Limiting (High)
**Change**: Add throttling between requests
```python
import time

RATE_LIMIT_DELAY = 1.0  # seconds between requests

for source, url in urls.items():
    time.sleep(RATE_LIMIT_DELAY)
    # ... fetch feed
```
**Action**: Add configurable delay between feed fetches, implement per-domain rate limiting.

### 5. Add Error Context (High)
**Change**: Replace bare except clauses with specific exceptions
```python
except feedparser.ParseError as e:
    logger.error(f"Parse error for {url}: {e}")
except urllib.error.URLError as e:
    logger.error(f"Network error for {url}: {e}")
except Exception as e:
    logger.error(f"Unexpected error for {url}: {e}", exc_info=True)
```
**Action**: Catch specific exceptions, log full context including traceback.

### 6. Timeout Configuration (High)
**Change**: Add timeout to feedparser
```python
import socket
socket.setdefaulttimeout(30)  # 30 second timeout

# Or use requests with feedparser:
import requests
response = requests.get(url, timeout=30)
d = feedparser.parse(response.content)
```
**Action**: Set connection and read timeouts, make configurable.

### 7. Structured Logging (High)
**Change**: Replace print statements with logging module
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Usage:
logger.info(f"Fetching feed: {url}")
logger.error(f"Failed to fetch {url}", exc_info=True)
```
**Action**: Implement proper logging with levels, file rotation, and structured messages.

### 8. Retry Logic (High)
**Change**: Add retry decorator or loop
```python
from urllib.error import URLError
import time

def fetch_with_retry(url, max_retries=3, backoff=2):
    for attempt in range(max_retries):
        try:
            return feedparser.parse(url)
        except URLError as e:
            if attempt < max_retries - 1:
                time.sleep(backoff ** attempt)
                continue
            raise
```
**Action**: Implement exponential backoff retry for transient failures.

### 9. Feed Validation (Medium)
**Change**: Validate parsed feed structure
```python
def validate_feed_entry(feed):
    """Ensure feed has minimum required fields"""
    if not hasattr(feed, 'link') or not feed.link:
        return False
    if not hasattr(feed, 'title') or not feed.title:
        return False
    if not (hasattr(feed, 'published_parsed') or hasattr(feed, 'updated_parsed')):
        return False
    return True

# Use in loop:
if not validate_feed_entry(feed):
    logger.warning(f"Skipping invalid entry from {source}")
    continue
```
**Action**: Check for required fields before processing each entry.

### 10. Content Sanitization (Medium)
**Change**: Strip/escape HTML in titles and descriptions
```python
import html
from html.parser import HTMLParser

class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.fed = []
    def handle_data(self, d):
        self.fed.append(d)
    def get_data(self):
        return ''.join(self.fed)

def strip_html(text):
    s = MLStripper()
    s.feed(text)
    return s.get_data()

# Apply to entries:
"title": strip_html(feed.title),
```
**Action**: Sanitize all text fields from feeds before storage.

### 11. HTTP Conditional Requests (Low)
**Change**: Store and use ETags/Last-Modified headers
```python
# Store in feed metadata:
feed_metadata = {
    "etag": response.headers.get('ETag'),
    "last_modified": response.headers.get('Last-Modified')
}

# Use in next request:
headers = {}
if metadata.get('etag'):
    headers['If-None-Match'] = metadata['etag']
if metadata.get('last_modified'):
    headers['If-Modified-Since'] = metadata['last_modified']

response = requests.get(url, headers=headers, timeout=30)
if response.status_code == 304:
    # Not modified, use cached data
    pass
```
**Action**: Implement conditional GET requests to reduce bandwidth and server load.

### 12. CLI Interface (Low)
**Change**: Add argparse for command-line control
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('--category', help='Process specific category')
    parser.add_argument('--log', action='store_true', help='Enable logging')
    parser.add_argument('--config', help='Path to feeds.json')
    args = parser.parse_args()
    
    do(target_category=args.category, log=args.log)

if __name__ == "__main__":
    main()
```
**Action**: Add command-line argument parsing for operational flexibility.