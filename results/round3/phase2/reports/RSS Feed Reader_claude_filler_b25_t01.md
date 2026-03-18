# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS feeds from multiple sources
2. **Multi-source Aggregation**: Supports organizing feeds into categories, with multiple URLs per category
3. **Time Normalization**: Converts feed timestamps to a configurable timezone (currently UTC+9/KST)
4. **Deduplication**: Uses timestamp as ID to prevent duplicate entries from the same feed
5. **Sorting**: Orders entries by timestamp in descending order (newest first)
6. **Data Persistence**: Stores parsed feeds as JSON files in `~/.rreader/` directory
7. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file
   - Bundles default feeds with the application
   - Merges new bundled categories into user config without overwriting
8. **Flexible Formatting**: Displays time as "HH:MM" for today's entries, "Mon DD, HH:MM" for older ones
9. **Optional Author Display**: Supports per-category toggle for showing feed author vs source name
10. **Selective Updates**: Can update a single category or all categories
11. **Basic Logging**: Optional stdout logging of fetch progress

## Triage

### Critical Gaps (Must-Have for Production)

1. **Error Handling**: Minimal error recovery; single feed failure during category processing isn't isolated
2. **Network Resilience**: No timeout configuration, retry logic, or rate limiting
3. **Security**: No validation of feed content or URL sanitization; vulnerable to malicious feeds
4. **Data Validation**: No schema validation for stored JSON or feed configuration

### High Priority (Should-Have)

5. **Caching Strategy**: No cache expiration policy; stale data accumulates indefinitely
6. **Concurrency**: Sequential processing means slow feeds block the entire update
7. **Monitoring**: No metrics on feed health, fetch duration, or failure rates
8. **Configuration Validation**: Doesn't validate feeds.json structure before use

### Medium Priority (Nice-to-Have)

9. **Feed Metadata**: Doesn't store feed description, image, or other metadata
10. **Entry Content**: Only stores title/link, not article summaries or content
11. **User Feedback**: Limited progress indication for long-running operations
12. **Testing**: No test coverage visible in the codebase

### Low Priority (Future Enhancements)

13. **Entry Limits**: No mechanism to cap entries per feed or total storage
14. **Feed Discovery**: No auto-detection of RSS feeds from website URLs
15. **Update Scheduling**: No built-in scheduling; relies on external cron/scheduler

## Plan

### 1. Error Handling
**Changes needed:**
- Wrap each feed fetch in individual try-except blocks to isolate failures
- Log failed feeds with error details to a separate error log file
- Add a "status" field to each category result indicating success/partial/failure
- Continue processing remaining feeds when one fails
- Return aggregated error summary in the result

**Implementation:**
```python
failed_feeds = []
for source, url in urls.items():
    try:
        # existing parse logic
    except Exception as e:
        failed_feeds.append({"source": source, "url": url, "error": str(e)})
        if log:
            sys.stderr.write(f" - Failed: {e}\n")
        continue
```

### 2. Network Resilience
**Changes needed:**
- Add configurable timeout to feedparser (default 30 seconds)
- Implement exponential backoff retry (3 attempts with 1s, 2s, 4s delays)
- Add user-agent header to avoid bot blocking
- Implement connection pooling for better performance
- Add rate limiting between feeds from same domain

**Implementation:**
```python
import requests
from urllib.parse import urlparse
import tenacity

@tenacity.retry(
    stop=tenacity.stop_after_attempt(3),
    wait=tenacity.wait_exponential(multiplier=1, min=1, max=10),
    retry=tenacity.retry_if_exception_type((requests.Timeout, requests.ConnectionError))
)
def fetch_with_retry(url, timeout=30):
    return feedparser.parse(url, request_headers={'User-Agent': 'RReader/1.0'})
```

### 3. Security
**Changes needed:**
- Validate URLs are http/https before fetching
- Implement maximum feed size limit (e.g., 10MB)
- Sanitize HTML in titles using `bleach` or similar
- Add URL allowlist/blocklist capability in config
- Validate that feed URLs resolve to expected domains (prevent redirects to malicious sites)

**Implementation:**
```python
from urllib.parse import urlparse
import bleach

def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f"Invalid scheme: {parsed.scheme}")
    return url

def sanitize_title(title):
    return bleach.clean(title, tags=[], strip=True)
```

### 4. Data Validation
**Changes needed:**
- Create JSON schema files for feeds.json and output format
- Validate feeds.json on load using `jsonschema`
- Validate parsed feed data before storage
- Add version field to config for migration support
- Provide helpful error messages for malformed config

**Implementation:**
```python
import jsonschema

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

def load_validated_config(path):
    with open(path) as f:
        config = json.load(f)
    jsonschema.validate(config, FEEDS_SCHEMA)
    return config
```

### 5. Caching Strategy
**Changes needed:**
- Add TTL field to each category config (default 3600s)
- Check file modification time before re-fetching
- Add `--force` flag to bypass cache
- Implement conditional GET using ETags/Last-Modified headers
- Store HTTP cache headers in metadata

**Implementation:**
```python
def should_update(category, ttl):
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(cache_file):
        return True
    age = time.time() - os.path.getmtime(cache_file)
    return age > ttl

# In config:
"tech": {
    "feeds": {...},
    "ttl": 3600  # refresh every hour
}
```

### 6. Concurrency
**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel feed fetching
- Make worker count configurable (default 5)
- Add semaphore to limit concurrent requests per domain
- Aggregate results as they complete rather than waiting for all

**Implementation:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_feed(source, url):
    # existing fetch logic, returns (source, entries) or (source, None)
    pass

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_source = {
            executor.submit(fetch_feed, source, url): source 
            for source, url in urls.items()
        }
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                entries = future.result()
                if entries:
                    rslt.update(entries)
            except Exception as e:
                if log:
                    sys.stderr.write(f"Failed {source}: {e}\n")
```

### 7. Monitoring
**Changes needed:**
- Create a `stats_{category}.json` file with fetch metrics
- Track: last_success, last_failure, avg_fetch_time, entry_count, error_count
- Add `--stats` command to display health dashboard
- Log warnings for feeds that consistently fail
- Track feed velocity (entries per day) for anomaly detection

**Implementation:**
```python
stats = {
    "last_fetch": int(time.time()),
    "success": True,
    "duration_ms": 1234,
    "entries_fetched": 42,
    "errors": [],
    "history": [...]  # keep last 10 fetches
}
```

### 8. Configuration Validation
**Changes needed:**
- Validate feeds.json structure on startup
- Check that all URLs are parseable
- Warn about duplicate feed URLs across categories
- Validate timezone string against pytz/zoneinfo
- Provide `--validate-config` command

**Implementation:**
```python
def validate_config(config):
    errors = []
    seen_urls = {}
    for category, data in config.items():
        if not isinstance(data.get('feeds'), dict):
            errors.append(f"{category}: missing 'feeds' dict")
        for source, url in data['feeds'].items():
            try:
                validate_url(url)
            except ValueError as e:
                errors.append(f"{category}/{source}: {e}")
            if url in seen_urls:
                errors.append(f"Duplicate URL: {url} in {category} and {seen_urls[url]}")
            seen_urls[url] = category
    return errors
```

### 9. Feed Metadata
**Changes needed:**
- Store feed title, description, link, and image URL
- Add metadata section to output JSON
- Display metadata in UI/CLI
- Update metadata periodically (less frequently than entries)

**Implementation:**
```python
"metadata": {
    "feed_title": d.feed.get('title'),
    "feed_description": d.feed.get('description'),
    "feed_link": d.feed.get('link'),
    "feed_image": d.feed.get('image', {}).get('href')
}
```

### 10. Entry Content
**Changes needed:**
- Store `summary` field from feed entries
- Add `content` field if available (longer than summary)
- Sanitize HTML in content
- Make content storage optional (can be large)
- Add character limit for stored content

**Implementation:**
```python
entries = {
    # existing fields
    "summary": bleach.clean(feed.get('summary', '')[:1000]),
    "content": bleach.clean(feed.get('content', [{}])[0].get('value', '')[:5000]) if store_content else None
}
```

### 11. User Feedback
**Changes needed:**
- Add progress bar using `tqdm` for multi-feed updates
- Show "Fetching X/Y feeds" counter
- Display estimated time remaining
- Add `--quiet` flag to suppress all output
- Use logging levels (INFO, WARNING, ERROR) instead of print

**Implementation:**
```python
from tqdm import tqdm

for source, url in tqdm(urls.items(), desc=f"Fetching {category}"):
    # fetch logic
```

### 12. Testing
**Changes needed:**
- Add pytest test suite
- Mock feedparser responses for unit tests
- Test error conditions (timeout, malformed XML, etc.)
- Test timezone handling edge cases
- Add integration tests with test RSS feeds
- Test config migration logic

**Structure:**
```
tests/
  test_parsing.py
  test_storage.py
  test_config.py
  test_errors.py
  fixtures/
    sample_feed.xml
    malformed_feed.xml
```