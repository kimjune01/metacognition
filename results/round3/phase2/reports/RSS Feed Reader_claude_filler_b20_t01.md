# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds using the `feedparser` library from multiple sources defined in a JSON configuration file.

2. **Multi-Category Support**: Organizes feeds into categories, allowing users to fetch all categories or target a specific one via the `target_category` parameter.

3. **Data Normalization**: Extracts and normalizes feed entries into a consistent structure containing:
   - Unique ID (Unix timestamp)
   - Source name/author
   - Publication date (formatted as "HH:MM" for today, "Mon DD, HH:MM" otherwise)
   - Timestamp
   - URL
   - Title

4. **Timezone Handling**: Converts UTC timestamps to a configurable timezone (currently KST/UTC+9).

5. **Deduplication**: Uses timestamp-based dictionary keys to automatically deduplicate entries from the same source.

6. **Persistence**: Saves parsed feed data as JSON files (`rss_{category}.json`) in a user data directory (`~/.rreader/`).

7. **Configuration Management**: 
   - Creates data directory if it doesn't exist
   - Maintains a user-editable `feeds.json` configuration file
   - Merges new categories from bundled defaults without overwriting user customizations

8. **Logging**: Optional logging mode to show fetch progress and failures.

9. **Chronological Sorting**: Entries are sorted by timestamp in reverse order (newest first).

## Triage

### Critical Gaps (P0)

1. **No Error Handling Granularity**: Individual feed failures cause silent data loss. If one URL fails, that source is skipped without any recovery mechanism or notification.

2. **No Rate Limiting**: Multiple rapid requests to the same domain could trigger rate limiting or bans. No delay between requests.

3. **No Timeout Configuration**: Feed fetching can hang indefinitely on unresponsive servers.

4. **Missing Data Validation**: No validation that parsed entries contain required fields before accessing them. Malformed feeds could cause crashes beyond the basic try/except.

### High Priority Gaps (P1)

5. **No Caching/Conditional Requests**: Every execution re-fetches all feeds completely, wasting bandwidth. No use of ETags or Last-Modified headers.

6. **No Concurrency**: Feeds are fetched sequentially, making updates slow when monitoring many sources.

7. **No Content Sanitization**: Feed titles and content are stored raw without HTML sanitization, creating potential XSS vulnerabilities if displayed in a web interface.

8. **Insufficient Timestamp Fallback**: Only checks `published_parsed` and `updated_parsed`. Some feeds use other fields like `created` or `date`.

9. **No Feed Health Monitoring**: No tracking of which feeds consistently fail or return empty results.

10. **No User Agent String**: Requests don't identify the client, which some servers require or use for statistics.

### Medium Priority Gaps (P2)

11. **Limited Configuration Options**: Hardcoded values for:
    - Maximum entries per feed
    - Cache duration
    - Request timeout
    - Retry attempts

12. **No Entry Limit Management**: All entries from each fetch are stored, causing unbounded growth of JSON files over time.

13. **No Duplicate Detection Across Sources**: Same article from different feeds (common in aggregators) appears multiple times.

14. **Poor Date Handling Edge Cases**: 
    - No handling of future-dated entries (common with scheduled posts)
    - No timezone-aware comparison for "today"

15. **No Atomic File Writes**: JSON files are written directly, risking corruption if the process crashes mid-write.

16. **No Migration System**: When the bundled `feeds.json` schema changes, there's no migration path for user configurations.

### Low Priority Gaps (P3)

17. **No Statistics Collection**: No tracking of fetch success rates, entry counts, or performance metrics.

18. **No Feed Discovery**: No ability to automatically find feed URLs from website URLs.

19. **No OPML Import/Export**: Can't import/export feed lists in the standard OPML format.

20. **Weak Logging**: The log parameter only enables basic stdout messages, no proper logging levels or file output.

21. **No Description/Content Extraction**: Only extracts titles, not article summaries or full content.

## Plan

### For Critical Gaps

**1. Improve Error Handling**
```python
# Change the inner loop to:
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        
        d = feedparser.parse(url)
        
        # Check for HTTP errors
        if hasattr(d, 'status') and d.status >= 400:
            error_msg = f"HTTP {d.status}"
            if log:
                sys.stdout.write(f" - Failed: {error_msg}\n")
            # Store error in a separate errors list
            continue
            
        if log:
            sys.stdout.write(" - Done\n")
            
    except Exception as e:
        error_msg = str(e)
        if log:
            sys.stdout.write(f" - Failed: {error_msg}\n")
        # Log to error file: ~/.rreader/errors.log
        # Continue to next feed instead of exiting
        continue
```

**2. Add Rate Limiting**
```python
import time
from collections import defaultdict

# At module level:
_last_request_time = defaultdict(float)
_min_request_interval = 1.0  # seconds between requests to same domain

def _rate_limit(url):
    from urllib.parse import urlparse
    domain = urlparse(url).netloc
    elapsed = time.time() - _last_request_time[domain]
    if elapsed < _min_request_interval:
        time.sleep(_min_request_interval - elapsed)
    _last_request_time[domain] = time.time()

# Use before feedparser.parse():
_rate_limit(url)
d = feedparser.parse(url)
```

**3. Add Timeout Configuration**
```python
# In config.py, add:
FEED_TIMEOUT = 30  # seconds

# In the fetch function:
import socket
socket.setdefaulttimeout(FEED_TIMEOUT)

# Or better, pass to feedparser:
d = feedparser.parse(url, timeout=FEED_TIMEOUT)
```

**4. Strengthen Data Validation**
```python
# Before accessing feed attributes:
required_fields = ['link', 'title']
if not all(hasattr(feed, field) and getattr(feed, field) for field in required_fields):
    continue  # Skip malformed entries

# Sanitize title length:
title = feed.title[:500] if len(feed.title) > 500 else feed.title
```

### For High Priority Gaps

**5. Implement Caching with Conditional Requests**
```python
# Store ETags and Last-Modified per feed in cache.json:
# {
#   "url": {
#     "etag": "...",
#     "last_modified": "...",
#     "last_fetch": timestamp
#   }
# }

def load_cache():
    cache_file = os.path.join(p["path_data"], "cache.json")
    if os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            return json.load(f)
    return {}

def save_cache(cache):
    cache_file = os.path.join(p["path_data"], "cache.json")
    with open(cache_file, 'w') as f:
        json.dump(cache, f)

# When fetching:
cache = load_cache()
headers = {}
if url in cache:
    if 'etag' in cache[url]:
        headers['If-None-Match'] = cache[url]['etag']
    if 'last_modified' in cache[url]:
        headers['If-Modified-Since'] = cache[url]['last_modified']

d = feedparser.parse(url, request_headers=headers)

# Update cache after successful fetch:
if hasattr(d, 'etag'):
    cache.setdefault(url, {})['etag'] = d.etag
if hasattr(d, 'modified'):
    cache.setdefault(url, {})['last_modified'] = d.modified
save_cache(cache)
```

**6. Add Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, show_author, log):
    """Extract current feed-fetching logic into this function"""
    # Returns: (source, entries_dict, error_or_none)
    pass

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_source = {
            executor.submit(fetch_single_feed, source, url, show_author, log): source
            for source, url in urls.items()
        }
        
        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                source_name, entries, error = future.result(timeout=60)
                if error:
                    # Log error
                    continue
                rslt.update(entries)
            except Exception as e:
                # Log error for this source
                pass
    
    # Rest of function unchanged
```

**7. Sanitize HTML Content**
```python
import html
import re

def sanitize_text(text):
    """Remove HTML tags and decode entities"""
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html.unescape(text)
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# Apply to title:
entries = {
    "title": sanitize_text(feed.title),
    # ...
}
```

**8. Improve Timestamp Extraction**
```python
def get_entry_timestamp(feed):
    """Try multiple timestamp fields in priority order"""
    for field in ['published_parsed', 'updated_parsed', 'created_parsed', 'date_parsed']:
        parsed_time = getattr(feed, field, None)
        if parsed_time:
            return parsed_time
    return None

# Use it:
parsed_time = get_entry_timestamp(feed)
if not parsed_time:
    continue
```

**9. Add Feed Health Tracking**
```python
# In a separate health.json file, track:
# {
#   "url": {
#     "last_success": timestamp,
#     "last_failure": timestamp,
#     "failure_count": int,
#     "total_fetches": int
#   }
# }

# Update after each fetch attempt
# Alert user to feeds with >5 consecutive failures
```

**10. Set User Agent**
```python
# In config.py:
USER_AGENT = "rreader/1.0 (https://github.com/yourrepo/rreader)"

# When fetching:
d = feedparser.parse(url, agent=USER_AGENT)
```

### For Medium Priority Gaps

**11. Make Configuration Comprehensive**
```python
# In config.py, add:
CONFIG = {
    'max_entries_per_feed': 50,
    'max_age_days': 30,  # Don't store entries older than this
    'cache_duration_minutes': 30,
    'request_timeout': 30,
    'max_retries': 3,
    'retry_delay': 5,
    'concurrent_workers': 5,
    'user_agent': 'rreader/1.0',
}

# Allow user overrides in ~/.rreader/config.json
```

**12. Implement Entry Limit**
```python
# When saving results:
entries = rslt["entries"][:CONFIG['max_entries_per_feed']]

# Filter by age:
cutoff = time.time() - (CONFIG['max_age_days'] * 86400)
entries = [e for e in entries if e['timestamp'] > cutoff]
```

**13. Add Cross-Source Deduplication**
```python
import hashlib

def generate_content_hash(entry):
    """Create hash from normalized URL and title"""
    content = f"{entry['url']}|{entry['title'].lower().strip()}"
    return hashlib.md5(content.encode()).hexdigest()

# When building rslt:
seen_hashes = set()
for entry in all_entries:
    content_hash = generate_content_hash(entry)
    if content_hash in seen_hashes:
        continue
    seen_hashes.add(content_hash)
    rslt[entry['id']] = entry
```

**14. Fix Date Handling**
```python
def is_today(timestamp, timezone):
    """Check if timestamp is today in the given timezone"""
    dt = datetime.datetime.fromtimestamp(timestamp, tz=timezone)
    now = datetime.datetime.now(tz=timezone)
    return dt.date() == now.date()

# Filter future dates:
if ts > time.time() + 86400:  # More than 1 day in future
    ts = int(time.time())  # Use current time instead
```

**15. Implement Atomic Writes**
```python
import tempfile

def atomic_write(filepath, content):
    """Write to temp file, then rename"""
    dir_path = os.path.dirname(filepath)
    with tempfile.NamedTemporaryFile(
        mode='w', 
        dir=dir_path, 
        delete=False,
        encoding='utf-8'
    ) as tf:
        tf.write(content)
        temp_name = tf.name
    
    # Atomic rename
    os.replace(temp_name, filepath)

# Use it:
atomic_write(
    os.path.join(p["path_data"], f"rss_{category}.json"),
    json.dumps(rslt, ensure_ascii=False)
)
```

**16. Add Schema Versioning**
```python
# In feeds.json:
{
    "_schema_version": 2,
    "categories": { ... }
}

# Migration function:
def migrate_feeds_config(config):
    version = config.get('_schema_version', 1)
    
    if version == 1:
        # Wrap existing structure
        config = {
            '_schema_version': 2,
            'categories': config
        }
    
    return config
```

### For Low Priority Gaps

**17. Add Statistics Tracking**
```python
# Create stats.json with:
# {
#   "last_run": timestamp,
#   "total_feeds": int,
#   "total_entries": int,
#   "successful_fetches": int,
#   "failed_fetches": int,
#   "average_fetch_time": float
# }

# Update after each run
```

**18. Implement Feed Discovery**
```python
def discover_feed(url):
    """Find RSS/Atom feed URL from a webpage URL"""
    import requests
    from bs4 import BeautifulSoup
    
    resp = requests.get(url, timeout=10)
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    # Look for <link rel="alternate" type="application/rss+xml">
    for link in soup.find_all('link', rel='alternate'):
        if 'rss' in link.get('type', '').lower():
            return link.get('href')
    
    return None
```

**19. Add OPML Support**
```python
def export_opml(feeds_dict, output_path):
    """Export feeds to OPML format"""
    # Use xml.etree.ElementTree to build OPML structure
    pass

def import_opml(opml_path):
    """Parse OPML and return feeds dictionary"""
    # Parse OPML and extract feed URLs
    pass
```

**20. Implement Proper Logging**
```python
import logging

def setup_logging(log_level='INFO'):
    logger = logging.getLogger('rreader')
    logger.setLevel(getattr(logging, log_level))
    
    # File handler
    fh = logging.FileHandler(
        os.path.join(p["path_data"], 'rreader.log')
    )
    fh.setLevel(logging.DEBUG)
    
    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    
    logger.addHandler(fh)
    logger.addHandler(ch)
    
    return logger

# Use throughout:
logger = setup_logging()
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}: {error}")
```

**21. Extract Content/Description**
```python
# In entry creation:
entries = {
    "id": ts,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": sanitize_text(feed.title),
    "description": sanitize_text(
        getattr(feed, 'summary', '') or 
        getattr(feed, 'description', '') or 
        ''
    )[:1000],  # Limit length
}
```