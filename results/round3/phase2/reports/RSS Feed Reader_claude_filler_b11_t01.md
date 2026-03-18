# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-source aggregation**: Processes multiple feeds per category defined in a JSON configuration file
3. **Timestamp normalization**: Converts feed publication times to a configurable timezone (currently KST/UTC+9)
4. **Data persistence**: Saves aggregated feed entries to JSON files per category (`rss_{category}.json`)
5. **Deduplication**: Uses timestamps as IDs to avoid duplicate entries from the same feed
6. **Time-based sorting**: Orders entries by publication time (newest first)
7. **Human-readable dates**: Formats dates as "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
8. **Configuration management**: 
   - Stores feed sources in `~/.rreader/feeds.json`
   - Auto-creates data directory on first run
   - Merges bundled default feeds with user configuration
9. **Selective updates**: Can update a single category or all categories
10. **Optional author display**: Per-category flag to show feed author vs. source name
11. **Logging support**: Optional progress output during feed fetching

## Triage

### Critical Gaps (Blocks Production Use)

1. **No error handling granularity**: Bare `except` blocks swallow all exceptions; system fails silently or exits completely
2. **No retry logic**: Network failures cause permanent data loss for that update cycle
3. **No rate limiting**: Could overwhelm feed sources or trigger rate limits
4. **No feed validation**: Malformed feeds or missing fields cause silent failures
5. **Security vulnerabilities**: No URL validation, timeout limits, or size restrictions

### High Priority (Significantly Limits Functionality)

6. **No concurrency**: Sequential feed fetching is extremely slow for many feeds
7. **No incremental updates**: Re-downloads entire feeds even for unchanged content
8. **No data expiration**: Old entries accumulate indefinitely
9. **No health monitoring**: No way to detect stale/broken feeds
10. **No user feedback mechanisms**: UI has no error visibility beyond optional logs

### Medium Priority (Quality of Life)

11. **Configuration format limitations**: No feed metadata (update frequency, priority, tags)
12. **No content extraction**: Only stores titles/links, not descriptions or content
13. **Rigid timezone handling**: Hardcoded timezone instead of user-configurable
14. **No backup/recovery**: Data corruption causes permanent loss
15. **Limited duplicate detection**: Only by exact timestamp; doesn't handle feed ID updates

### Low Priority (Nice to Have)

16. **No analytics**: No tracking of read/unread, popularity, or feed quality metrics
17. **No search capability**: Must browse JSON files manually
18. **No export formats**: Only JSON output
19. **No feed discovery**: Must manually add feed URLs
20. **No internationalization**: English-only date formats

## Plan

### 1. Error Handling Granularity

**Current problem**: `except:` at lines 37 and 49 catch all exceptions including KeyboardInterrupt and system errors.

**Changes needed**:
```python
# Replace bare excepts with specific exceptions
try:
    d = feedparser.parse(url)
except (urllib.error.URLError, http.client.HTTPException, socket.timeout) as e:
    if log:
        sys.stderr.write(f" - Network error: {e}\n")
    continue  # Skip this feed, continue with others
except Exception as e:
    if log:
        sys.stderr.write(f" - Parse error: {e}\n")
    continue

# For feed entry processing
try:
    parsed_time = getattr(feed, 'published_parsed', None) or ...
except (AttributeError, ValueError, TypeError) as e:
    if log:
        sys.stderr.write(f"Warning: Skipping malformed entry: {e}\n")
    continue
```

### 2. Retry Logic with Exponential Backoff

**Current problem**: Single network failure loses all data from that feed.

**Changes needed**:
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,  # Wait 0.5s, 1s, 2s between retries
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# In get_feed_from_rss:
session = create_session()
response = session.get(url, timeout=30)
d = feedparser.parse(response.content)
```

### 3. Rate Limiting

**Current problem**: Rapid-fire requests could get IP banned.

**Changes needed**:
```python
import time
from collections import defaultdict

class RateLimiter:
    def __init__(self, min_interval=1.0):  # Min 1 second between requests
        self.min_interval = min_interval
        self.last_request = defaultdict(float)
    
    def wait(self, domain):
        elapsed = time.time() - self.last_request[domain]
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_request[domain] = time.time()

# In get_feed_from_rss:
rate_limiter = RateLimiter(min_interval=2.0)
for source, url in urls.items():
    domain = urllib.parse.urlparse(url).netloc
    rate_limiter.wait(domain)
    # ... fetch feed
```

### 4. Feed Validation

**Current problem**: No checks for required fields or data sanity.

**Changes needed**:
```python
def validate_feed_entry(feed):
    """Returns (is_valid, sanitized_entry) tuple"""
    required_fields = ['link', 'title']
    
    for field in required_fields:
        if not hasattr(feed, field) or not getattr(feed, field):
            return False, None
    
    # Sanitize title (prevent XSS if displayed in web UI)
    import html
    title = html.escape(feed.title[:500])  # Limit length
    
    # Validate URL
    if not feed.link.startswith(('http://', 'https://')):
        return False, None
    
    return True, {'title': title, 'link': feed.link}

# Use in loop:
is_valid, sanitized = validate_feed_entry(feed)
if not is_valid:
    continue
```

### 5. Security Hardening

**Current problem**: No protection against malicious feeds or SSRF attacks.

**Changes needed**:
```python
import validators
import ipaddress
from urllib.parse import urlparse

BLOCKED_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),    # localhost
    ipaddress.ip_network('10.0.0.0/8'),      # private
    ipaddress.ip_network('172.16.0.0/12'),   # private
    ipaddress.ip_network('192.168.0.0/16'),  # private
]

def validate_url(url):
    if not validators.url(url):
        return False
    
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        return False
    
    # Prevent SSRF attacks
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        for network in BLOCKED_NETWORKS:
            if ip in network:
                return False
    except:
        return False
    
    return True

# Add timeouts and size limits:
response = session.get(url, timeout=30, stream=True)
MAX_FEED_SIZE = 10 * 1024 * 1024  # 10MB
if int(response.headers.get('content-length', 0)) > MAX_FEED_SIZE:
    raise ValueError("Feed too large")
```

### 6. Concurrent Feed Fetching

**Current problem**: Sequential fetching takes N×fetch_time for N feeds.

**Changes needed**:
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def fetch_single_feed(source, url, show_author, log):
    """Extract single feed logic into separate function"""
    try:
        # ... existing fetch logic
        return feed_entries
    except Exception as e:
        if log:
            sys.stderr.write(f"Failed {source}: {e}\n")
        return []

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    lock = threading.Lock()
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_source = {
            executor.submit(fetch_single_feed, src, url, show_author, log): src
            for src, url in urls.items()
        }
        
        for future in as_completed(future_to_source):
            entries = future.result()
            with lock:
                for entry in entries:
                    rslt[entry["id"]] = entry
    
    # ... rest of existing logic
```

### 7. Incremental Updates with ETag/Last-Modified

**Current problem**: Re-downloads unchanged feeds, wasting bandwidth.

**Changes needed**:
```python
def load_feed_metadata(category):
    """Load stored ETags and Last-Modified headers"""
    metadata_file = os.path.join(p["path_data"], f"metadata_{category}.json")
    if os.path.exists(metadata_file):
        with open(metadata_file) as f:
            return json.load(f)
    return {}

def save_feed_metadata(category, metadata):
    metadata_file = os.path.join(p["path_data"], f"metadata_{category}.json")
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f)

# In fetch:
metadata = load_feed_metadata(category)
headers = {}
if source in metadata:
    if 'etag' in metadata[source]:
        headers['If-None-Match'] = metadata[source]['etag']
    if 'last_modified' in metadata[source]:
        headers['If-Modified-Since'] = metadata[source]['last_modified']

response = session.get(url, headers=headers, timeout=30)
if response.status_code == 304:
    # Not modified, skip parsing
    return existing_entries

# Save new metadata
metadata[source] = {
    'etag': response.headers.get('ETag'),
    'last_modified': response.headers.get('Last-Modified'),
}
save_feed_metadata(category, metadata)
```

### 8. Data Expiration Policy

**Current problem**: JSON files grow unbounded.

**Changes needed**:
```python
def cleanup_old_entries(entries, max_age_days=30, max_entries=1000):
    """Remove entries older than max_age_days or keep only max_entries newest"""
    cutoff_timestamp = int(time.time()) - (max_age_days * 86400)
    
    # Filter by age
    recent = [e for e in entries if e['timestamp'] >= cutoff_timestamp]
    
    # Limit total count
    if len(recent) > max_entries:
        recent = sorted(recent, key=lambda x: x['timestamp'], reverse=True)[:max_entries]
    
    return recent

# Apply before saving:
rslt["entries"] = cleanup_old_entries(rslt["entries"])
```

### 9. Feed Health Monitoring

**Current problem**: No way to detect broken feeds.

**Changes needed**:
```python
def update_feed_health(category, source, success, error_msg=None):
    """Track feed reliability"""
    health_file = os.path.join(p["path_data"], f"health_{category}.json")
    
    if os.path.exists(health_file):
        with open(health_file) as f:
            health = json.load(f)
    else:
        health = {}
    
    if source not in health:
        health[source] = {
            'success_count': 0,
            'failure_count': 0,
            'last_success': None,
            'last_failure': None,
            'consecutive_failures': 0,
        }
    
    if success:
        health[source]['success_count'] += 1
        health[source]['last_success'] = int(time.time())
        health[source]['consecutive_failures'] = 0
    else:
        health[source]['failure_count'] += 1
        health[source]['last_failure'] = int(time.time())
        health[source]['consecutive_failures'] += 1
        health[source]['last_error'] = error_msg
    
    with open(health_file, 'w') as f:
        json.dump(health, f, indent=2)
    
    # Alert if feed consistently failing
    if health[source]['consecutive_failures'] >= 5:
        sys.stderr.write(f"WARNING: Feed {source} has failed 5 times in a row\n")

# Call after each fetch attempt
```

### 10. User Feedback System

**Current problem**: No status visibility in UI.

**Changes needed**:
```python
def create_status_file(category, status_data):
    """Create machine-readable status file for UI consumption"""
    status_file = os.path.join(p["path_data"], f"status_{category}.json")
    status_data['updated_at'] = int(time.time())
    with open(status_file, 'w') as f:
        json.dump(status_data, f)

# Track during update:
status = {
    'total_feeds': len(urls),
    'successful': 0,
    'failed': 0,
    'errors': [],
}

# After each feed:
if success:
    status['successful'] += 1
else:
    status['failed'] += 1
    status['errors'].append({'source': source, 'error': str(e)})

create_status_file(category, status)
```

### 11. Enhanced Configuration Format

**Current problem**: Limited metadata per feed.

**Changes needed**:
```python
# New feeds.json structure:
{
    "Technology": {
        "show_author": true,
        "update_interval": 3600,  # seconds
        "priority": "high",
        "feeds": {
            "TechCrunch": {
                "url": "https://techcrunch.com/feed/",
                "enabled": true,
                "tags": ["tech", "startups"],
                "custom_interval": 1800  # Override category default
            }
        }
    }
}

# Add migration function:
def migrate_config():
    """Convert old format to new format"""
    # ... handle backward compatibility
```

### 12. Content Extraction

**Current problem**: Missing article descriptions and content.

**Changes needed**:
```python
def extract_content(feed):
    """Extract description and content with fallbacks"""
    content = {
        'summary': '',
        'content': '',
    }
    
    # Try multiple fields for description
    for field in ['summary', 'description', 'subtitle']:
        if hasattr(feed, field):
            content['summary'] = getattr(feed, field)[:500]  # Limit length
            break
    
    # Try to get full content
    if hasattr(feed, 'content') and feed.content:
        content['content'] = feed.content[0].value[:5000]
    
    return content

# Add to entries dict:
entries.update(extract_content(feed))
```

### 13. Configurable Timezone

**Current problem**: Hardcoded KST timezone.

**Changes needed**:
```python
# In config.py:
import os
import pytz

# Allow environment variable override
TIMEZONE_NAME = os.environ.get('RREADER_TIMEZONE', 'Asia/Seoul')
try:
    TIMEZONE = pytz.timezone(TIMEZONE_NAME)
except pytz.exceptions.UnknownTimeZoneError:
    TIMEZONE = pytz.timezone('UTC')

# Or add to feeds.json:
{
    "settings": {
        "timezone": "America/New_York"
    }
}
```

### 14. Backup and Recovery

**Current problem**: No protection against data corruption.

**Changes needed**:
```python
import shutil
from datetime import datetime

def atomic_write(filepath, data):
    """Write with atomic rename to prevent corruption"""
    temp_file = filepath + '.tmp'
    backup_file = filepath + '.bak'
    
    # Write to temp file
    with open(temp_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Keep one backup
    if os.path.exists(filepath):
        shutil.copy2(filepath, backup_file)
    
    # Atomic rename
    shutil.move(temp_file, filepath)

def rotate_backups(category, keep=7):
    """Keep N days of backups"""
    backup_dir = os.path.join(p["path_data"], "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    dated_backup = os.path.join(
        backup_dir, 
        f"rss_{category}_{datetime.now().strftime('%Y%m%d')}.json"
    )
    
    current = os.path.join(p["path_data"], f"rss_{category}.json")
    if os.path.exists(current):
        shutil.copy2(current, dated_backup)
    
    # Clean old backups
    # ... implement rotation logic
```

### 15. Advanced Duplicate Detection

**Current problem**: Only detects duplicates by timestamp.

**Changes needed**:
```python
import hashlib

def generate_entry_hash(entry):
    """Create stable hash from entry content"""
    # Use URL + title as unique identifier
    content = f"{entry.get('link', '')}:{entry.get('title', '')}"
    return hashlib.md5(content.encode()).hexdigest()

def load_seen_hashes(category):
    """Load previously seen entry hashes"""
    hash_file = os.path.join(p["path_data"], f"hashes_{category}.json")
    if os.path.exists(hash_file):
        with open(hash_file) as f:
            return set(json.load(f))
    return set()

# Use in deduplication:
seen = load_seen_hashes(category)
entry_hash = generate_entry_hash(feed)
if entry_hash in seen:
    continue
seen.add(entry_hash)
```

Each of these changes can be implemented incrementally without breaking existing functionality. Priority should be given to Critical and High Priority items for production readiness.