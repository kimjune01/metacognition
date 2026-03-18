# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Downloads and parses RSS/Atom feeds using the `feedparser` library from multiple sources defined in a JSON configuration file.

2. **Multi-Category Support**: Organizes feeds into categories, with each category containing multiple source URLs.

3. **Data Normalization**: Extracts standardized fields from feeds (title, URL, publication date, author/source, timestamp) and handles variations in feed formats (published_parsed vs updated_parsed).

4. **Time Formatting**: Converts UTC timestamps to a configurable timezone (defaulted to KST/UTC+9) and formats display times as either "HH:MM" for today's items or "MMM DD, HH:MM" for older items.

5. **Deduplication**: Uses timestamps as unique IDs to prevent duplicate entries from the same feed.

6. **Sorted Output**: Orders entries in reverse chronological order (newest first).

7. **JSON Storage**: Persists parsed feed data to category-specific JSON files in `~/.rreader/` directory.

8. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Copies bundled default feeds on first run
   - Merges new bundled categories into existing user configuration without overwriting

9. **Selective Updates**: Can update a single category or all categories via the `target_category` parameter.

10. **Optional Logging**: Provides console output for debugging when `log=True`.

## Triage

### Critical Gaps

1. **No Error Handling for Individual Feeds** (Priority: HIGH)
   - A single failed feed URL crashes the entire category update
   - Network timeouts are not handled
   - Malformed XML/RSS causes silent failures with broad `except` clauses

2. **No Rate Limiting or Politeness** (Priority: HIGH)
   - Hammers all feeds simultaneously without delays
   - No User-Agent header identification
   - Could get IP banned by feed providers

3. **No Data Validation** (Priority: HIGH)
   - Doesn't validate that required fields (title, link) exist before creating entries
   - Malformed feeds could produce corrupt JSON output
   - No schema validation for feeds.json configuration

4. **Timestamp Collision Handling** (Priority: MEDIUM-HIGH)
   - Uses timestamp as unique ID, but multiple articles can publish at the same second
   - Dictionary overwrites cause data loss when IDs collide

### Important Gaps

5. **No Caching Strategy** (Priority: MEDIUM)
   - Re-downloads entire feeds even if unchanged
   - No ETags or Last-Modified header support
   - Wastes bandwidth and server resources

6. **No Incremental Updates** (Priority: MEDIUM)
   - Always processes entire feed history
   - Doesn't track which items were previously seen
   - No concept of "mark as read"

7. **No Content Extraction** (Priority: MEDIUM)
   - Only stores title and link
   - Doesn't capture description/summary/content
   - No image or media attachment handling

8. **Limited Timezone Handling** (Priority: MEDIUM)
   - Hardcoded timezone in config
   - No user preference system
   - No timezone-aware display options

### Minor Gaps

9. **No Monitoring/Health Checks** (Priority: LOW)
   - No tracking of feed availability
   - No metrics on update success/failure rates
   - No alerts for consistently failing feeds

10. **No Retry Logic** (Priority: LOW)
    - Single-attempt failures are permanent until next run
    - No exponential backoff
    - No distinction between transient and permanent failures

11. **No Feed Autodiscovery** (Priority: LOW)
    - User must manually enter feed URLs
    - Can't provide website URL and find RSS/Atom link

12. **Poor Testability** (Priority: LOW)
    - No dependency injection
    - File I/O coupled with business logic
    - No mock/stub infrastructure

## Plan

### 1. Error Handling for Individual Feeds

**Changes needed:**
- Replace broad `except:` clauses with specific exception types
- Wrap each feed fetch in a try-except block that logs the error and continues
- Add timeout parameter to `feedparser.parse()` (requires updating to pass timeout to underlying urllib)
- Return error status alongside success data

```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            
            # Add timeout support
            d = feedparser.parse(url, request_headers={'User-Agent': 'rreader/1.0'})
            
            if d.bozo and log:
                sys.stderr.write(f" - Warning: {d.bozo_exception}\n")
            
            if log:
                sys.stdout.write(" - Done\n")
                
        except (urllib.error.URLError, socket.timeout) as e:
            error_msg = f"Failed to fetch {url}: {e}"
            errors.append({"source": source, "url": url, "error": str(e)})
            if log:
                sys.stderr.write(f" - Error: {e}\n")
            continue
        except Exception as e:
            error_msg = f"Unexpected error for {url}: {e}"
            errors.append({"source": source, "url": url, "error": str(e)})
            if log:
                sys.stderr.write(f" - Unexpected error: {e}\n")
            continue
```

### 2. Rate Limiting and Politeness

**Changes needed:**
- Add configurable delay between feed fetches
- Set proper User-Agent header
- Add to configuration file as global settings

```python
# In config.py
REQUEST_DELAY_SECONDS = 1.0
USER_AGENT = "rreader/1.0 (+https://github.com/yourproject/rreader)"

# In get_feed_from_rss()
import time

for idx, (source, url) in enumerate(urls.items()):
    if idx > 0:  # Don't delay before first request
        time.sleep(REQUEST_DELAY_SECONDS)
    
    d = feedparser.parse(url, request_headers={'User-Agent': USER_AGENT})
```

### 3. Data Validation

**Changes needed:**
- Validate required fields before creating entry
- Add schema validation for feeds.json
- Sanitize/escape data to prevent JSON corruption

```python
for feed in d.entries:
    # Validate required fields
    if not hasattr(feed, 'link') or not feed.link:
        if log:
            sys.stderr.write(f"  Skipping entry without link\n")
        continue
    
    if not hasattr(feed, 'title') or not feed.title:
        if log:
            sys.stderr.write(f"  Skipping entry without title: {feed.link}\n")
        continue
    
    # Validate timestamp
    try:
        parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
        if not parsed_time:
            if log:
                sys.stderr.write(f"  Skipping entry without timestamp: {feed.link}\n")
            continue
        at = datetime.datetime(*parsed_time[:6])
    except (ValueError, TypeError) as e:
        if log:
            sys.stderr.write(f"  Invalid timestamp: {e}\n")
        continue
```

Add JSON schema validation:
```python
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"}
            },
            "required": ["feeds"]
        }
    }
}

# After loading feeds.json
try:
    jsonschema.validate(RSS, FEEDS_SCHEMA)
except jsonschema.ValidationError as e:
    sys.exit(f"Invalid feeds.json format: {e}")
```

### 4. Timestamp Collision Handling

**Changes needed:**
- Change ID strategy from timestamp-only to composite key
- Add sequence number or use feed GUID
- Handle collisions explicitly

```python
# Use feed's GUID if available, fall back to URL+timestamp
feed_id = getattr(feed, 'id', None) or f"{feed.link}#{ts}"

# Or create composite key
import hashlib
unique_string = f"{feed.link}|{ts}|{feed.title}"
feed_id = hashlib.sha256(unique_string.encode()).hexdigest()[:16]

entries = {
    "id": feed_id,
    "sourceName": author,
    # ... rest of fields
}

rslt[feed_id] = entries  # No more collision overwrites
```

### 5. Caching Strategy

**Changes needed:**
- Store ETags and Last-Modified headers
- Send conditional requests
- Skip parsing if server returns 304 Not Modified

```python
# Load cache metadata
cache_file = os.path.join(p["path_data"], f"cache_{category}.json")
cache = {}
if os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        cache = json.load(f)

headers = {'User-Agent': USER_AGENT}
if url in cache:
    if 'etag' in cache[url]:
        headers['If-None-Match'] = cache[url]['etag']
    if 'last-modified' in cache[url]:
        headers['If-Modified-Since'] = cache[url]['last-modified']

d = feedparser.parse(url, request_headers=headers)

# Check if content was modified
if d.status == 304:
    if log:
        sys.stdout.write(" - Not modified, using cache\n")
    continue

# Update cache
cache[url] = {
    'etag': d.get('etag'),
    'last-modified': d.get('modified'),
    'updated': int(time.time())
}

# Save cache at end
with open(cache_file, 'w') as f:
    json.dump(cache, f)
```

### 6. Incremental Updates

**Changes needed:**
- Track highest timestamp per feed
- Only process newer entries
- Maintain historical data file

```python
# Load previous state
state_file = os.path.join(p["path_data"], f"state_{category}.json")
last_timestamps = {}
if os.path.exists(state_file):
    with open(state_file, 'r') as f:
        last_timestamps = json.load(f)

last_ts = last_timestamps.get(source, 0)

for feed in d.entries:
    ts = int(time.mktime(parsed_time))
    
    # Skip already-seen entries
    if ts <= last_ts:
        continue
    
    # Process new entry
    # ...
    
    # Update max timestamp for this source
    last_timestamps[source] = max(last_timestamps.get(source, 0), ts)

# Save state
with open(state_file, 'w') as f:
    json.dump(last_timestamps, f)
```

### 7. Content Extraction

**Changes needed:**
- Extract description/summary field
- Handle content:encoded for full content
- Store media enclosures

```python
entries = {
    "id": feed_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', ''),
    "content": getattr(feed, 'content', [{}])[0].get('value', ''),
    "media": []
}

# Handle media enclosures
if hasattr(feed, 'enclosures'):
    for enclosure in feed.enclosures:
        entries["media"].append({
            "url": enclosure.get('href', ''),
            "type": enclosure.get('type', ''),
            "length": enclosure.get('length', 0)
        })
```

### 8. Timezone Configuration

**Changes needed:**
- Move timezone to feeds.json or separate config
- Allow per-user timezone preferences
- Support multiple display formats

```python
# In feeds.json, add global settings
{
    "_settings": {
        "timezone": "Asia/Seoul",
        "date_format": "%b %d, %H:%M"
    },
    "tech": { "feeds": {...} }
}

# Load timezone from config
import pytz
timezone_name = RSS.get('_settings', {}).get('timezone', 'UTC')
TIMEZONE = pytz.timezone(timezone_name)
```

### 9. Monitoring/Health Checks

**Changes needed:**
- Create metrics file tracking success/failure rates
- Record last successful update per feed
- Add health check endpoint or report

```python
metrics_file = os.path.join(p["path_data"], "metrics.json")
metrics = {"feeds": {}}

if os.path.exists(metrics_file):
    with open(metrics_file, 'r') as f:
        metrics = json.load(f)

# After each feed attempt
feed_key = f"{category}:{source}"
if feed_key not in metrics["feeds"]:
    metrics["feeds"][feed_key] = {
        "success_count": 0,
        "failure_count": 0,
        "last_success": None,
        "last_failure": None
    }

if successful:
    metrics["feeds"][feed_key]["success_count"] += 1
    metrics["feeds"][feed_key]["last_success"] = int(time.time())
else:
    metrics["feeds"][feed_key]["failure_count"] += 1
    metrics["feeds"][feed_key]["last_failure"] = int(time.time())
    metrics["feeds"][feed_key]["last_error"] = str(error)

# Save metrics
with open(metrics_file, 'w') as f:
    json.dump(metrics, f, indent=2)
```

### 10. Retry Logic

**Changes needed:**
- Implement exponential backoff for failed feeds
- Track retry attempts
- Distinguish temporary vs permanent failures

```python
from urllib.error import URLError, HTTPError

MAX_RETRIES = 3
BACKOFF_FACTOR = 2

for retry in range(MAX_RETRIES):
    try:
        d = feedparser.parse(url, request_headers=headers)
        break  # Success
    except HTTPError as e:
        if e.code in [404, 410]:  # Permanent failures
            if log:
                sys.stderr.write(f" - Permanent failure: {e.code}\n")
            break
        # Temporary failure, retry with backoff
        if retry < MAX_RETRIES - 1:
            sleep_time = BACKOFF_FACTOR ** retry
            if log:
                sys.stderr.write(f" - Retry {retry+1}/{MAX_RETRIES} after {sleep_time}s\n")
            time.sleep(sleep_time)
    except URLError as e:
        # Network error, retry
        if retry < MAX_RETRIES - 1:
            sleep_time = BACKOFF_FACTOR ** retry
            time.sleep(sleep_time)
```

### 11. Feed Autodiscovery

**Changes needed:**
- Add function to find RSS/Atom links in HTML
- Parse HTML link tags with rel="alternate"
- Provide helper command to discover feeds

```python
import requests
from bs4 import BeautifulSoup

def discover_feeds(website_url):
    """Find RSS/Atom feed URLs from a website."""
    try:
        response = requests.get(website_url, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        feeds = []
        for link in soup.find_all('link', type=['application/rss+xml', 
                                                  'application/atom+xml']):
            feed_url = link.get('href')
            if not feed_url.startswith('http'):
                from urllib.parse import urljoin
                feed_url = urljoin(website_url, feed_url)
            feeds.append({
                'url': feed_url,
                'title': link.get('title', 'Untitled Feed'),
                'type': link.get('type')
            })
        
        return feeds
    except Exception as e:
        return []
```

### 12. Testability Improvements

**Changes needed:**
- Extract file I/O into separate data access layer
- Create interfaces for external dependencies
- Add unit tests with mocked feeds

```python
# Create data access layer
class FeedDataStore:
    def __init__(self, data_path):
        self.data_path = data_path
    
    def save_category(self, category, data):
        with open(os.path.join(self.data_path, f"rss_{category}.json"), 'w') as f:
            json.dump(data, f, ensure_ascii=False)
    
    def load_category(self, category):
        # ... implementation

# Refactor main function
def get_feed_from_rss(category, urls, data_store, feed_parser=feedparser, 
                      show_author=False, log=False):
    # Now testable with mocks
    pass

# In tests
class MockFeedParser:
    def parse(self, url, **kwargs):
        return mock_feed_data

class MockDataStore:
    def __init__(self):
        self.saved_data = {}
    
    def save_category(self, category, data):
        self.saved_data[category] = data
```