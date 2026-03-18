# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS feeds from multiple sources using feedparser
2. **Multi-Category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Data Storage**: Saves parsed feed entries as JSON files (one per category) in `~/.rreader/`
4. **Timestamp Handling**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
5. **Human-Readable Dates**: Formats dates as "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
6. **Configuration Management**: 
   - Uses a `feeds.json` configuration file
   - Copies bundled default feeds if user config doesn't exist
   - Merges new categories from bundled config into existing user config
7. **Deduplication**: Uses timestamp as ID to prevent duplicate entries (though collisions are possible)
8. **Sorting**: Orders entries by timestamp (newest first)
9. **Flexible Author Display**: Can show either source name or actual author per category
10. **CLI Interface**: Can update all feeds or target specific categories

## Triage

### Critical Gaps
1. **No Error Handling** - `sys.exit()` with status 0 on feed parse failure masks errors
2. **ID Collision Risk** - Using Unix timestamp as ID causes collisions for feeds published in the same second
3. **No Rate Limiting** - Could hammer RSS servers or get blocked
4. **Uncaught Exceptions** - Bare `except:` clauses hide real problems

### High Priority
5. **No Logging System** - Only optional stdout writes; no persistent logs or error tracking
6. **No Data Validation** - Missing feeds with malformed dates/titles/URLs could corrupt output
7. **No Feed Metadata** - Doesn't track last-updated time per feed for efficient polling
8. **No Entry Limit** - Memory issues possible with high-volume feeds
9. **No Network Timeout** - feedparser.parse() can hang indefinitely
10. **No Stale Data Detection** - Old entries never expire

### Medium Priority
11. **No User Feedback** - Silent failures; no progress indication without log=True
12. **Hardcoded Timezone** - Should be user-configurable
13. **No Incremental Updates** - Always fetches full feeds; wastes bandwidth
14. **Missing Feed Health Checks** - No tracking of consistently failing feeds
15. **No Content Sanitization** - Feed titles/content could contain malicious data

### Low Priority
16. **No Tests** - Zero test coverage
17. **No CLI Argument Parsing** - Limited interface for command-line use
18. **No Feed Discovery** - Manual URL entry only
19. **Missing Documentation** - No docstrings or usage guide

## Plan

### 1. Fix Error Handling (Critical)
```python
# Replace bare except with specific exceptions
except (urllib.error.URLError, socket.timeout) as e:
    error_msg = f"Failed to fetch {url}: {str(e)}"
    if log:
        sys.stderr.write(f" - {error_msg}\n")
    # Log to file and continue to next feed
    logging.error(error_msg)
    continue  # Don't exit, process other feeds
```

### 2. Fix ID Collision (Critical)
```python
# Use hash of URL + timestamp for unique ID
import hashlib
entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
entries = {
    "id": entry_id,
    "timestamp": ts,  # Keep for sorting
    # ... rest of fields
}
```

### 3. Add Rate Limiting (Critical)
```python
import time
from datetime import datetime, timedelta

# At module level
RATE_LIMIT = 1  # seconds between requests
last_request = {}

# In get_feed_from_rss
for source, url in urls.items():
    if url in last_request:
        elapsed = time.time() - last_request[url]
        if elapsed < RATE_LIMIT:
            time.sleep(RATE_LIMIT - elapsed)
    
    last_request[url] = time.time()
    # ... proceed with parse
```

### 4. Replace Bare Excepts (Critical)
```python
# Replace all `except:` with specific exceptions
try:
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        continue
    at = datetime.datetime(*parsed_time[:6]).replace(tzinfo=datetime.timezone.utc).astimezone(TIMEZONE)
except (TypeError, ValueError, AttributeError) as e:
    logging.warning(f"Invalid date for feed {feed.get('link', 'unknown')}: {e}")
    continue
```

### 5. Implement Logging System (High)
```python
import logging

# At module level
logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Replace sys.stdout.write calls
logging.info(f"Fetching {url}")
logging.error(f"Failed to fetch {url}: {str(e)}")
```

### 6. Add Data Validation (High)
```python
def validate_entry(feed):
    """Validate required fields exist and are reasonable."""
    required = ['link', 'title']
    for field in required:
        if not hasattr(feed, field) or not getattr(feed, field):
            return False
    
    # Validate URL format
    if not feed.link.startswith(('http://', 'https://')):
        return False
    
    # Validate title length
    if len(feed.title) > 500:
        return False
    
    return True

# In loop
if not validate_entry(feed):
    logging.warning(f"Invalid entry from {source}, skipping")
    continue
```

### 7. Track Feed Metadata (High)
```python
# Store metadata alongside entries
metadata = {
    "last_updated": int(time.time()),
    "feed_status": {
        source: {
            "last_success": ts,
            "last_error": None,
            "consecutive_failures": 0
        } for source in urls.keys()
    }
}

# Save with entries
rslt = {
    "entries": rslt_list,
    "created_at": int(time.time()),
    "metadata": metadata
}
```

### 8. Limit Entry Count (High)
```python
# After sorting, before saving
MAX_ENTRIES_PER_CATEGORY = 1000
rslt_list = [val for key, val in sorted(rslt.items(), reverse=True)][:MAX_ENTRIES_PER_CATEGORY]
```

### 9. Add Network Timeout (High)
```python
# Set timeout for feedparser
import socket
socket.setdefaulttimeout(30)  # 30 second timeout

# Or use requests with feedparser
import requests
response = requests.get(url, timeout=30)
d = feedparser.parse(response.content)
```

### 10. Implement Stale Data Cleanup (High)
```python
# Filter out entries older than N days
MAX_AGE_DAYS = 30
cutoff = int(time.time()) - (MAX_AGE_DAYS * 86400)
rslt = {k: v for k, v in rslt.items() if v["timestamp"] > cutoff}
```

### 11. Add User Feedback (Medium)
```python
def update_progress(current, total, source):
    """Show progress bar or status."""
    if sys.stdout.isatty():
        percent = (current / total) * 100
        sys.stdout.write(f"\r[{current}/{total}] {percent:.1f}% - {source}")
        sys.stdout.flush()
```

### 12. Make Timezone Configurable (Medium)
```python
# In feeds.json add timezone field
{
    "category_name": {
        "feeds": {...},
        "timezone_offset": 9  # hours from UTC
    }
}

# Read and apply
tz_offset = d.get("timezone_offset", 0)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```

### 13. Add Incremental Updates (Medium)
```python
# Use If-Modified-Since HTTP header
headers = {}
last_modified = metadata.get("last_modified")
if last_modified:
    headers["If-Modified-Since"] = last_modified

response = requests.get(url, headers=headers, timeout=30)
if response.status_code == 304:
    # Not modified, skip parsing
    continue
```

### 14. Implement Feed Health Tracking (Medium)
```python
# Track failures per feed
if source in metadata["feed_status"]:
    if success:
        metadata["feed_status"][source]["consecutive_failures"] = 0
        metadata["feed_status"][source]["last_success"] = time.time()
    else:
        metadata["feed_status"][source]["consecutive_failures"] += 1
        metadata["feed_status"][source]["last_error"] = time.time()
        
# Warn about persistently failing feeds
if metadata["feed_status"][source]["consecutive_failures"] > 5:
    logging.warning(f"Feed {source} has failed 5+ times consecutively")
```

### 15. Sanitize Content (Medium)
```python
import html
import re

def sanitize_text(text, max_length=500):
    """Remove HTML tags and limit length."""
    text = html.unescape(text)
    text = re.sub(r'<[^>]+>', '', text)  # Strip HTML tags
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    return text[:max_length]

# Apply to title
entries["title"] = sanitize_text(feed.title)
```