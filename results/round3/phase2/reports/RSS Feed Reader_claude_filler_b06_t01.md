# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds using the `feedparser` library from multiple sources.

2. **Multi-Category Support**: Organizes feeds into categories defined in a `feeds.json` configuration file.

3. **Feed Data Extraction**: Extracts key fields from feed entries:
   - Title
   - URL/Link
   - Publication/update timestamp
   - Source name/author

4. **Time Handling**: Converts feed timestamps to a configurable timezone (currently hardcoded to UTC+9/KST) and formats them for display.

5. **Data Persistence**: Saves parsed feed data as JSON files (one per category) in `~/.rreader/` directory.

6. **Configuration Management**: 
   - Creates data directory on first run
   - Copies bundled default `feeds.json` if user version doesn't exist
   - Merges new categories from bundled config into existing user config

7. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries from the same feed.

8. **Sorting**: Sorts feed entries by timestamp in reverse chronological order (newest first).

9. **Selective Updates**: Can update a single category or all categories based on function parameter.

10. **Author Display Toggle**: Supports optional author name display per category configuration.

## Triage

### Critical Gaps (Must Have for Production)

1. **Error Handling & Resilience** - Currently has minimal error handling; a single feed failure can crash the entire update process or fail silently.

2. **Logging System** - The `log` parameter only prints to stdout; no structured logging, no error tracking, no audit trail.

3. **Configuration Validation** - No validation of `feeds.json` structure; malformed JSON or missing required fields will cause crashes.

4. **Network Timeouts** - No timeout configuration for feed fetching; slow/hung servers can block indefinitely.

### High Priority (Should Have)

5. **Rate Limiting** - No delays between feed requests; could trigger rate limiting or be considered abusive by feed servers.

6. **HTTP Headers** - Missing User-Agent and other standard HTTP headers; some servers block requests without proper identification.

7. **Caching & Conditional Requests** - No support for ETags or Last-Modified headers; wastes bandwidth re-downloading unchanged feeds.

8. **Stale Data Handling** - No mechanism to detect or warn about feeds that haven't updated in a long time.

9. **Feed Health Monitoring** - No tracking of which feeds consistently fail or are slow.

10. **Timezone Configuration** - Timezone is hardcoded; should be user-configurable.

### Medium Priority (Nice to Have)

11. **Concurrent Fetching** - Fetches feeds sequentially; slow for many feeds (could use threading/asyncio).

12. **Entry Age Limits** - No filtering of very old entries; first run could import years of content.

13. **Data Retention Policy** - JSON files grow indefinitely; no cleanup of old entries.

14. **Feed Discovery** - No way to add new feeds from the UI; must manually edit JSON.

15. **Statistics & Metrics** - No tracking of fetch times, success rates, or entry counts.

16. **Atomic Writes** - Writes directly to target files; corruption possible if interrupted.

### Low Priority (Could Have)

17. **Content Sanitization** - Doesn't clean/validate HTML in titles or descriptions.

18. **Duplicate Detection Across Sources** - Same story from multiple sources appears multiple times.

19. **Feed Format Validation** - No checks for feed validity beyond feedparser's defaults.

20. **Incremental Updates** - Always processes entire feed; could optimize for partial updates.

## Plan

### 1. Error Handling & Resilience

**Changes needed:**
- Wrap feed parsing in try-except blocks that catch specific exceptions (network errors, parsing errors, timeout errors)
- Continue processing remaining feeds if one fails
- Collect errors during batch processing and report at end
- Add exponential backoff for failed feeds
- Implement a "quarantine" mechanism for repeatedly failing feeds

```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            # Add timeout parameter
            d = feedparser.parse(url, timeout=30)
            
            # Check for bozo (malformed feed)
            if d.bozo and not d.entries:
                errors.append((source, url, f"Malformed feed: {d.bozo_exception}"))
                continue
                
            # Process entries...
            
        except (urllib.error.URLError, socket.timeout) as e:
            errors.append((source, url, f"Network error: {e}"))
            continue
        except Exception as e:
            errors.append((source, url, f"Unexpected error: {e}"))
            continue
    
    # Log/return errors for monitoring
    if errors:
        error_file = os.path.join(p["path_data"], f"rss_{category}_errors.json")
        with open(error_file, 'w') as f:
            json.dump(errors, f, indent=2)
```

### 2. Logging System

**Changes needed:**
- Replace print statements with Python's `logging` module
- Configure log levels (DEBUG, INFO, WARNING, ERROR)
- Add file-based logging with rotation
- Include timestamps, category, and feed source in all log messages
- Add structured logging for machine parsing

```python
import logging
from logging.handlers import RotatingFileHandler

# Setup at module level
log_file = os.path.join(p["path_data"], "rreader.log")
handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = logging.getLogger('rreader')
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Usage in functions
logger.info(f"Fetching feed: {url}")
logger.error(f"Failed to parse feed {url}: {e}", exc_info=True)
```

### 3. Configuration Validation

**Changes needed:**
- Add JSON schema validation using `jsonschema` library
- Validate on load and provide clear error messages
- Check for required fields: category names, feed URLs
- Validate URL format
- Provide example valid configuration in error messages

```python
from jsonschema import validate, ValidationError

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {
                        ".*": {"type": "string", "format": "uri"}
                    }
                },
                "show_author": {"type": "boolean"}
            }
        }
    }
}

def load_feeds_config():
    try:
        with open(FEEDS_FILE_NAME, "r") as fp:
            config = json.load(fp)
        validate(instance=config, schema=FEEDS_SCHEMA)
        return config
    except ValidationError as e:
        logger.error(f"Invalid feeds.json: {e.message}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Malformed JSON in feeds.json: {e}")
        sys.exit(1)
```

### 4. Network Timeouts

**Changes needed:**
- Add explicit timeout parameter to feedparser.parse()
- Make timeout configurable per feed or globally
- Add connection timeout separate from read timeout
- Handle timeout exceptions gracefully

```python
# In config.py
FEED_TIMEOUT = 30  # seconds
CONNECT_TIMEOUT = 10  # seconds

# In feed fetching code
import socket
socket.setdefaulttimeout(CONNECT_TIMEOUT)

d = feedparser.parse(url, timeout=FEED_TIMEOUT)
```

### 5. Rate Limiting

**Changes needed:**
- Add delay between feed requests (e.g., 1-2 seconds)
- Respect robots.txt if present
- Group feeds by domain and apply per-domain rate limits
- Add configurable rate limit settings

```python
import time
from urllib.parse import urlparse
from collections import defaultdict

last_fetch_times = defaultdict(float)
MIN_DELAY_PER_DOMAIN = 2  # seconds

def fetch_with_rate_limit(url):
    domain = urlparse(url).netloc
    elapsed = time.time() - last_fetch_times[domain]
    
    if elapsed < MIN_DELAY_PER_DOMAIN:
        time.sleep(MIN_DELAY_PER_DOMAIN - elapsed)
    
    result = feedparser.parse(url, timeout=FEED_TIMEOUT)
    last_fetch_times[domain] = time.time()
    
    return result
```

### 6. HTTP Headers

**Changes needed:**
- Add User-Agent header identifying the application
- Add Accept headers for RSS/Atom formats
- Include contact information in User-Agent for server admin communication
- Make headers configurable

```python
# In config.py
USER_AGENT = "RReader/1.0 (+https://github.com/yourrepo/rreader; contact@example.com)"
HTTP_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml'
}

# In feed fetching
d = feedparser.parse(url, timeout=FEED_TIMEOUT, agent=USER_AGENT)
```

### 7. Caching & Conditional Requests

**Changes needed:**
- Store ETag and Last-Modified headers from responses
- Send If-None-Match and If-Modified-Since on subsequent requests
- Handle 304 Not Modified responses
- Persist cache metadata to disk

```python
# Store in separate cache file
cache_file = os.path.join(p["path_data"], f"rss_{category}_cache.json")

def load_cache():
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            return json.load(f)
    return {}

def fetch_with_cache(url, cache_data):
    headers = HTTP_HEADERS.copy()
    
    if url in cache_data:
        if 'etag' in cache_data[url]:
            headers['If-None-Match'] = cache_data[url]['etag']
        if 'last_modified' in cache_data[url]:
            headers['If-Modified-Since'] = cache_data[url]['last_modified']
    
    # Use feedparser's response handler
    d = feedparser.parse(url, etag=cache_data.get(url, {}).get('etag'),
                        modified=cache_data.get(url, {}).get('last_modified'))
    
    # Update cache if not 304
    if d.status != 304:
        cache_data[url] = {
            'etag': d.get('etag'),
            'last_modified': d.get('modified'),
            'timestamp': time.time()
        }
    
    return d, cache_data
```

### 8. Stale Data Handling

**Changes needed:**
- Track last successful update time per feed
- Warn if feed hasn't updated in configurable period (e.g., 7 days)
- Mark feeds as potentially dead after longer period (e.g., 30 days)
- Display warnings in UI or logs

```python
def check_feed_freshness(feed_data, cache_data, url):
    last_entry_time = max([e['timestamp'] for e in feed_data.get('entries', [])], default=0)
    now = time.time()
    
    age_days = (now - last_entry_time) / 86400
    
    if age_days > 30:
        logger.warning(f"Feed appears dead (no new entries in {age_days:.0f} days): {url}")
        return "dead"
    elif age_days > 7:
        logger.info(f"Feed stale (no new entries in {age_days:.0f} days): {url}")
        return "stale"
    
    return "active"
```

### 9. Feed Health Monitoring

**Changes needed:**
- Track success/failure counts per feed
- Record response times
- Store health metrics in separate file
- Provide health summary report
- Auto-disable feeds with high failure rates

```python
health_file = os.path.join(p["path_data"], "feed_health.json")

def update_feed_health(url, success, response_time, error=None):
    health = load_health_data()
    
    if url not in health:
        health[url] = {
            'success_count': 0,
            'failure_count': 0,
            'total_response_time': 0,
            'last_success': None,
            'last_failure': None,
            'recent_errors': []
        }
    
    if success:
        health[url]['success_count'] += 1
        health[url]['total_response_time'] += response_time
        health[url]['last_success'] = time.time()
    else:
        health[url]['failure_count'] += 1
        health[url]['last_failure'] = time.time()
        health[url]['recent_errors'].append({
            'timestamp': time.time(),
            'error': str(error)
        })
        # Keep only last 10 errors
        health[url]['recent_errors'] = health[url]['recent_errors'][-10:]
    
    save_health_data(health)
    
    # Check if feed should be disabled
    total = health[url]['success_count'] + health[url]['failure_count']
    if total > 10 and health[url]['failure_count'] / total > 0.8:
        logger.warning(f"Feed has 80%+ failure rate, consider disabling: {url}")
```

### 10. Timezone Configuration

**Changes needed:**
- Move timezone to user-editable config file
- Support timezone name strings (e.g., "America/New_York")
- Provide sensible default (system timezone)
- Validate timezone on load

```python
# In config file format (e.g., config.json)
{
    "timezone": "America/New_York",
    "feed_timeout": 30,
    ...
}

# In config.py
import pytz

def load_config():
    config_file = os.path.join(p["path_data"], "config.json")
    
    defaults = {
        "timezone": "UTC",
        "feed_timeout": 30,
        "rate_limit_delay": 2
    }
    
    if os.path.exists(config_file):
        with open(config_file) as f:
            user_config = json.load(f)
            defaults.update(user_config)
    
    try:
        TIMEZONE = pytz.timezone(defaults["timezone"])
    except pytz.exceptions.UnknownTimeZoneError:
        logger.error(f"Unknown timezone: {defaults['timezone']}, using UTC")
        TIMEZONE = pytz.UTC
    
    return defaults, TIMEZONE
```

### 11. Concurrent Fetching

**Changes needed:**
- Use ThreadPoolExecutor or asyncio for parallel fetching
- Limit concurrent connections per domain
- Set maximum total concurrent connections
- Handle thread-safety for shared data structures

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    def fetch_single_feed(source, url):
        try:
            d = fetch_with_rate_limit(url)
            entries = process_feed_entries(d, source, show_author)
            return source, entries, None
        except Exception as e:
            return source, None, e
    
    # Use up to 5 concurrent fetches
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(fetch_single_feed, source, url): (source, url)
            for source, url in urls.items()
        }
        
        for future in as_completed(future_to_url):
            source, entries, error = future.result()
            
            if error:
                logger.error(f"Failed to fetch {source}: {error}")
            else:
                rslt.update(entries)
    
    # Sort and save as before
    return format_and_save_results(rslt, category)
```

### 12. Entry Age Limits

**Changes needed:**
- Add max_age_days configuration parameter
- Filter out entries older than threshold
- Apply on initial import and ongoing updates
- Make configurable per category

```python
# In feeds.json
{
    "Technology": {
        "feeds": {...},
        "show_author": false,
        "max_age_days": 7
    }
}

# In processing
def filter_by_age(entries, max_age_days):
    if not max_age_days:
        return entries
    
    cutoff = time.time() - (max_age_days * 86400)
    return [e for e in entries if e['timestamp'] >= cutoff]
```

### 13. Data Retention Policy

**Changes needed:**
- Add max_entries or max_age configuration
- Trim old entries when saving
- Archive old data instead of deleting
- Provide cleanup utility

```python
def save_with_retention(data, category, max_entries=1000, max_age_days=30):
    # Trim by count
    if len(data['entries']) > max_entries:
        data['entries'] = data['entries'][:max_entries]
    
    # Trim by age
    cutoff = time.time() - (max_age_days * 86400)
    data['entries'] = [e for e in data['entries'] if e['timestamp'] >= cutoff]
    
    # Save current data
    output_file = os.path.join(p["path_data"], f"rss_{category}.json")
    
    # Atomic write using temp file
    temp_file = output_file + '.tmp'
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    os.replace(temp_file, output_file)
```

### 14. Feed Discovery

**Changes needed:**
- Add function to detect feed URLs from website URL
- Parse HTML for link rel="alternate" tags
- Validate discovered feeds
- Add CLI/API to append new feeds to config

```python
def discover_feeds(url):
    """Find RSS/Atom feeds linked from a webpage"""
    import requests
    from bs4 import BeautifulSoup
    
    response = requests.get(url, timeout=10, headers=HTTP_HEADERS)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    feeds = []
    for link in soup.find_all('link', type=['application/rss+xml', 
                                             'application/atom+xml']):
        href = link.get('href')
        if href:
            # Handle relative URLs
            if not href.startswith('http'):
                href = urljoin(url, href)
            feeds.append({
                'url': href,
                'title': link.get('title', 'Unknown')
            })
    
    return feeds

def add_feed_to_category(category, source_name, feed_url):
    """Add a new feed to configuration"""
    with open(FEEDS_FILE_NAME, 'r') as f:
        config = json.load(f)
    
    if category not in config:
        config[category] = {'feeds': {}, 'show_author': False}
    
    config[category]['feeds'][source_name] = feed_url
    
    with open(FEEDS_FILE_NAME, 'w') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
```

### 15. Statistics & Metrics

**Changes needed:**
- Track fetch duration per feed
- Count new entries per update
- Calculate average update frequency
- Store metrics time-series data
- Provide summary report function

```python
metrics_file = os.path.join(p["path_data"], "metrics.json")

def record_metrics(category, stats):
    """Record update statistics"""
    metrics = load_metrics()
    
    if category not in metrics:
        metrics[category] = []
    
    metrics[category].append({
        'timestamp': time.time(),
        'feeds_attempted': stats['attempted'],
        'feeds_successful': stats['successful'],
        'feeds_failed': stats['failed'],
        'new_entries': stats['new_entries'],
        'total_duration': stats['duration'],
        'avg_response_time': stats['avg_response_time']
    })
    
    # Keep last 100 updates
    metrics[category] = metrics[category][-100:]
    
    save_metrics(metrics)

def generate_report():
    """Generate human-readable statistics report"""
    metrics = load_metrics()
    health = load_health_data()
    
    report = []
    report.append("=== RReader Statistics ===\n")
    
    for category, updates in metrics.items():
        if not updates:
            continue
            
        recent = updates[-1]
        report.append(f"\nCategory: {category}")
        report.append(f"  Last update: {datetime.fromtimestamp(recent['timestamp'])}")
        report.append(f"  Success rate: {recent['feeds_successful']}/{recent['feeds_attempted']}")
        report.append(f"  New entries: {recent['new_entries']}")
        report.append(f"  Avg response time: {recent['avg_response_time']:.2f}s")
    
    return '\n'.join(report)
```

### 16. Atomic Writes

**Changes needed:**
- Write to temporary file first
- Use os.replace() for atomic move
- Handle write failures gracefully
- Keep backup of previous version

```python
def atomic_write_json(filepath, data):
    """Write JSON data atomically with backup"""
    # Create backup of existing file
    if os.path.exists(filepath):
        backup = filepath + '.bak'
        shutil.copy2(filepath, backup)
    
    # Write to temporary file
    temp_file = filepath + '.tmp'
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Atomic replace
        os.replace(temp_file, filepath)
        
        # Remove backup after successful write
        if os.path.exists(filepath + '.bak'):
            os.remove(filepath + '.bak')
            
    except Exception as e:
        # Restore from backup if write failed
        if os.path.exists(filepath + '.bak'):
            shutil.copy2(filepath + '.bak', filepath)
        
        if os.path.exists(temp_file):
            os.remove(temp_file)
        
        raise e
```

### 17-20. Lower Priority Items

For **Content Sanitization**: Use `bleach` library to sanitize HTML in titles and strip potentially malicious content.

For **Duplicate Detection**: Implement fuzzy matching on titles using Levenshtein distance or simhash for near-duplicate detection across sources.

For **Feed Format Validation**: Check for required RSS/Atom elements and warn about malformed feeds that feedparser accepts but may be incomplete.

For **Incremental Updates**: Store last fetch timestamp and only process entries newer than last fetch (requires feed-level tracking).