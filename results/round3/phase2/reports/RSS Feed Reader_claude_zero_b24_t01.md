# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS feeds from multiple sources using `feedparser`
2. **Multi-category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Time Localization**: Converts UTC timestamps to a configured timezone (currently KST/UTC+9)
4. **Smart Time Display**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
5. **Data Persistence**: Saves parsed feeds as JSON files (one per category) in `~/.rreader/`
6. **Configuration Management**: 
   - Copies bundled default feeds on first run
   - Merges new categories from bundled config into user config on updates
7. **Flexible Author Display**: Configurable per-category to show either feed source name or article author
8. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries within a category
9. **Sorted Output**: Entries sorted by timestamp (newest first)
10. **Optional Logging**: Can display progress during feed fetching

## Triage

### Critical Gaps
1. **Error Handling Catastrophe** - The bare `except:` on line 29 calls `sys.exit()`, which kills the entire process if any single feed fails
2. **No Retry Logic** - Network failures or temporary RSS issues cause immediate failure
3. **ID Collision Risk** - Using timestamp as ID means multiple articles published in the same second will overwrite each other

### High Priority
4. **No Data Validation** - Missing feeds, malformed entries, or corrupt JSON files will crash the system
5. **No Rate Limiting** - Could hammer feed servers and get banned
6. **Silent Failures** - The second try/except (line 36) silently drops entries with no logging
7. **No Timeout Configuration** - Feed requests could hang indefinitely
8. **Stale Data Handling** - No mechanism to indicate when cached data is too old

### Medium Priority
9. **No Incremental Updates** - Always fetches all feeds; wastes bandwidth for high-frequency updates
10. **No Concurrency** - Sequential feed fetching is slow with many sources
11. **No Feed Health Monitoring** - No tracking of which feeds consistently fail
12. **Timezone Hardcoded** - Should be user-configurable

### Low Priority
13. **No CLI Interface** - Can't easily refresh specific categories or view status
14. **No Content Sanitization** - Feed titles/content might contain malicious HTML
15. **No Feed Metadata** - Doesn't store feed description, icon, or last update time

## Plan

### 1. Error Handling Catastrophe
**Change**: Replace lines 27-30
```python
# BEFORE:
except:
    sys.exit(" - Failed\n" if log else 0)

# AFTER:
except Exception as e:
    if log:
        sys.stdout.write(f" - Failed: {e}\n")
    continue  # Skip this feed, continue with others
```

### 2. No Retry Logic
**Change**: Add retry wrapper at top of file
```python
import time
from functools import wraps

def retry_with_backoff(max_attempts=3, initial_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(initial_delay * (2 ** attempt))
            return None
        return wrapper
    return decorator

# Apply to feedparser.parse call:
@retry_with_backoff(max_attempts=3)
def fetch_feed(url):
    return feedparser.parse(url)
```

### 3. ID Collision Risk
**Change**: Modify lines 52-53
```python
# BEFORE:
entries = {"id": ts, ...}

# AFTER:
import hashlib
unique_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
entries = {"id": unique_id, ...}
```

### 4. No Data Validation
**Change**: Add validation function and apply it
```python
def validate_feed_entry(feed):
    """Returns True if feed has minimum required fields"""
    return (
        hasattr(feed, 'link') and feed.link and
        hasattr(feed, 'title') and feed.title and
        (hasattr(feed, 'published_parsed') or hasattr(feed, 'updated_parsed'))
    )

# Apply before line 36:
if not validate_feed_entry(feed):
    continue
```

### 5. No Rate Limiting
**Change**: Add rate limiter class
```python
class RateLimiter:
    def __init__(self, min_interval=1.0):
        self.min_interval = min_interval
        self.last_call = 0
    
    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()

# In get_feed_from_rss:
limiter = RateLimiter(min_interval=1.0)
for source, url in urls.items():
    limiter.wait()
    # ... existing code
```

### 6. Silent Failures
**Change**: Replace bare except at line 36
```python
# BEFORE:
except:
    continue

# AFTER:
except Exception as e:
    if log:
        sys.stderr.write(f"  Warning: Skipped entry from {source}: {e}\n")
    continue
```

### 7. No Timeout Configuration
**Change**: Modify feedparser call
```python
# Add to config.py:
FEED_TIMEOUT = 30  # seconds

# Modify parse call (feedparser respects socket timeout):
import socket
old_timeout = socket.getdefaulttimeout()
socket.setdefaulttimeout(FEED_TIMEOUT)
d = feedparser.parse(url)
socket.setdefaulttimeout(old_timeout)
```

### 8. Stale Data Handling
**Change**: Add freshness indicator to output
```python
# In do() function, after reading cached file:
def is_stale(created_at, max_age_hours=24):
    return (time.time() - created_at) > (max_age_hours * 3600)

# Add to rslt dict:
rslt = {
    "entries": rslt,
    "created_at": int(time.time()),
    "is_stale": False  # Will be checked by reader
}
```

### 9. No Incremental Updates
**Change**: Add conditional fetching logic
```python
# Before get_feed_from_rss, check cache age:
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        cached = json.load(f)
    if (time.time() - cached['created_at']) < 300:  # 5 min cache
        return cached
```

### 10. No Concurrency
**Change**: Use ThreadPoolExecutor for parallel fetching
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    # Extract inner loop logic here
    pass

# In get_feed_from_rss:
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u, log): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        try:
            entries = future.result()
            rslt.update(entries)
        except Exception as e:
            if log:
                print(f"Feed failed: {e}")
```

### 11. No Feed Health Monitoring
**Change**: Add health tracking file
```python
# Create feed_health.json structure:
{
  "feeds": {
    "source_name": {
      "last_success": timestamp,
      "last_failure": timestamp,
      "consecutive_failures": 0,
      "total_fetches": 100,
      "success_rate": 0.95
    }
  }
}

# Update after each fetch attempt
```

### 12. Timezone Hardcoded
**Change**: Move to user config
```python
# In feeds.json, add:
{
  "_settings": {
    "timezone_offset_hours": 9
  },
  "categories": { ... }
}

# Load dynamically:
TIMEZONE = datetime.timezone(
    datetime.timedelta(hours=RSS.get('_settings', {}).get('timezone_offset_hours', 0))
)
```