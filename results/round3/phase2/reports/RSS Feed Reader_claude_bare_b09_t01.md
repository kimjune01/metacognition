# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library
2. **Multi-source Aggregation**: Handles multiple RSS feeds organized by categories from a JSON configuration file
3. **Data Persistence**: Stores parsed feed entries as JSON files in a user data directory (`~/.rreader/`)
4. **Time Handling**: Converts feed timestamps to a configured timezone (currently hardcoded to UTC+9/KST) and formats them for display
5. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries from the same source
6. **Configuration Management**: 
   - Copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration
   - Preserves user customizations while adding new defaults
7. **Flexible Execution**: Can refresh all feeds or target a specific category
8. **Author Attribution**: Configurable per-category author display (source name vs. feed author)
9. **Date Formatting**: Shows time-only for today's entries, full date for older entries

## Triage

### Critical Gaps (P0)
1. **No Error Handling**: Silent failures in feed fetching; `sys.exit(0)` on errors is problematic
2. **No Data Validation**: Missing validation for malformed feeds or JSON corruption
3. **No Logging Framework**: Basic stdout messages inadequate for debugging production issues

### Important Gaps (P1)
4. **Hardcoded Configuration**: Timezone and paths not user-configurable
5. **No Rate Limiting**: Could hammer RSS servers or get IP-blocked
6. **No Concurrency**: Sequential feed fetching is slow for many sources
7. **Missing CLI Interface**: No argument parsing for practical use
8. **No Update Scheduling**: Manual execution only; no cron/scheduler integration

### Enhancement Gaps (P2)
9. **No Feed Health Monitoring**: No tracking of failed feeds or stale data
10. **Limited Deduplication**: Timestamp-only IDs could collide; no URL-based dedup
11. **No Content Filtering**: No ability to filter by keywords or date ranges
12. **No Data Retention Policy**: Unlimited data accumulation
13. **No User Feedback**: No progress indication for long-running operations
14. **Missing Documentation**: No docstrings, README, or usage examples

## Plan

### P0 Fixes

**1. Error Handling**
```python
# Replace try/except blocks with proper error handling:
def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    failed_feeds = []
    
    for source, url in urls.items():
        try:
            if log:
                sys.stdout.write(f"- {url}")
            d = feedparser.parse(url)
            
            # Check for HTTP errors
            if hasattr(d, 'status') and d.status >= 400:
                raise Exception(f"HTTP {d.status}")
            
            # Check for parsing errors
            if d.bozo and not d.entries:
                raise Exception(f"Parse error: {d.bozo_exception}")
                
            if log:
                sys.stdout.write(" - Done\n")
        except Exception as e:
            error_msg = f"Failed to fetch {source} ({url}): {str(e)}\n"
            if log:
                sys.stderr.write(f" - {error_msg}")
            failed_feeds.append({'source': source, 'url': url, 'error': str(e)})
            continue  # Don't exit, continue with other feeds
    
    # Store failed feeds for monitoring
    if failed_feeds:
        rslt['_errors'] = failed_feeds
```

**2. Data Validation**
```python
def validate_feed_entry(feed):
    """Validate required fields exist and are properly formatted"""
    required_fields = ['link', 'title']
    for field in required_fields:
        if not hasattr(feed, field) or not getattr(feed, field):
            return False
    
    # Validate URL format
    if not feed.link.startswith(('http://', 'https://')):
        return False
    
    return True

# In the feed processing loop:
if not validate_feed_entry(feed):
    continue
```

**3. Logging Framework**
```python
import logging

# At module level:
logger = logging.getLogger('rreader')
handler = logging.FileHandler(os.path.join(p["path_data"], 'rreader.log'))
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Replace print/stdout calls:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {source}: {str(e)}", exc_info=True)
```

### P1 Fixes

**4. User-Configurable Settings**
```python
# Create config.json:
{
    "timezone_offset_hours": 9,
    "data_directory": "~/.rreader/",
    "max_entries_per_feed": 100,
    "request_timeout": 30
}

# Load in config.py:
def load_config():
    config_file = os.path.join(p["path_data"], "config.json")
    defaults = {"timezone_offset_hours": 9, "data_directory": "~/.rreader/"}
    
    if os.path.exists(config_file):
        with open(config_file) as f:
            return {**defaults, **json.load(f)}
    return defaults

CONFIG = load_config()
TIMEZONE = datetime.timezone(datetime.timedelta(hours=CONFIG['timezone_offset_hours']))
```

**5. Rate Limiting**
```python
import time
from functools import wraps

class RateLimiter:
    def __init__(self, calls_per_second=2):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
    
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            result = func(*args, **kwargs)
            self.last_call = time.time()
            return result
        return wrapper

@RateLimiter(calls_per_second=2)
def fetch_feed(url):
    return feedparser.parse(url)
```

**6. Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    """Fetch a single feed and return parsed entries"""
    try:
        if log:
            logger.info(f"Fetching {source} from {url}")
        d = feedparser.parse(url)
        return source, d, None
    except Exception as e:
        return source, None, str(e)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {
            executor.submit(fetch_single_feed, source, url, log): source 
            for source, url in urls.items()
        }
        
        for future in as_completed(futures):
            source, d, error = future.result()
            if error:
                logger.error(f"Failed {source}: {error}")
                continue
            
            # Process entries from d...
```

**7. CLI Interface**
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('-c', '--category', help='Update specific category only')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose logging')
    parser.add_argument('--list-categories', action='store_true', help='List available categories')
    parser.add_argument('--timeout', type=int, default=30, help='Request timeout in seconds')
    
    args = parser.parse_args()
    
    if args.list_categories:
        with open(FEEDS_FILE_NAME) as f:
            categories = json.load(f).keys()
        print("Available categories:", ', '.join(categories))
        return
    
    do(target_category=args.category, log=args.verbose)

if __name__ == "__main__":
    main()
```

**8. Scheduling Support**
```python
# Add a systemd timer file generator:
def generate_systemd_timer(interval_minutes=30):
    """Generate systemd service and timer files"""
    service = f"""[Unit]
Description=RSS Reader Update

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {os.path.abspath(__file__)}
"""
    
    timer = f"""[Unit]
Description=RSS Reader Update Timer

[Timer]
OnBootSec=5min
OnUnitActiveSec={interval_minutes}min

[Install]
WantedBy=timers.target
"""
    
    return service, timer
```

### P2 Enhancements

**9. Feed Health Monitoring**
```python
def update_feed_health(category, source, success, error_msg=None):
    """Track feed reliability"""
    health_file = os.path.join(p["path_data"], "feed_health.json")
    
    if os.path.exists(health_file):
        with open(health_file) as f:
            health = json.load(f)
    else:
        health = {}
    
    key = f"{category}:{source}"
    if key not in health:
        health[key] = {"attempts": 0, "failures": 0, "last_success": None, "last_error": None}
    
    health[key]["attempts"] += 1
    health[key]["last_attempt"] = int(time.time())
    
    if success:
        health[key]["last_success"] = int(time.time())
    else:
        health[key]["failures"] += 1
        health[key]["last_error"] = error_msg
    
    with open(health_file, 'w') as f:
        json.dump(health, f, indent=2)
```

**10. Better Deduplication**
```python
import hashlib

def generate_entry_id(feed):
    """Generate unique ID from URL and title"""
    unique_string = f"{feed.link}|{feed.title}"
    return hashlib.md5(unique_string.encode()).hexdigest()

# In the processing loop:
entry_id = generate_entry_id(feed)
if entry_id in rslt:
    continue  # Skip duplicates
```

**11. Content Filtering**
```python
def matches_filters(entry, filters):
    """Check if entry matches user-defined filters"""
    if 'keywords' in filters:
        text = f"{entry['title']} {entry.get('summary', '')}".lower()
        if not any(kw.lower() in text for kw in filters['keywords']):
            return False
    
    if 'min_date' in filters:
        if entry['timestamp'] < filters['min_date']:
            return False
    
    return True

# In feeds.json:
{
    "tech": {
        "feeds": {...},
        "filters": {
            "keywords": ["python", "AI"],
            "min_date": 1640000000
        }
    }
}
```

**12. Data Retention**
```python
def cleanup_old_entries(max_age_days=30, max_entries=1000):
    """Remove entries older than max_age_days or beyond max_entries"""
    cutoff = int(time.time()) - (max_age_days * 86400)
    
    for category_file in os.listdir(p["path_data"]):
        if not category_file.startswith("rss_"):
            continue
        
        filepath = os.path.join(p["path_data"], category_file)
        with open(filepath) as f:
            data = json.load(f)
        
        # Keep only recent entries
        data["entries"] = [
            e for e in data["entries"][:max_entries]
            if e["timestamp"] > cutoff
        ]
        
        with open(filepath, 'w') as f:
            json.dump(data, f, ensure_ascii=False)
```

**13. Progress Indication**
```python
from tqdm import tqdm

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    iterator = tqdm(urls.items(), desc=f"Fetching {category}") if log else urls.items()
    
    for source, url in iterator:
        # ... fetch logic
```

**14. Documentation**
```python
# Add module docstring:
"""
RSS Feed Reader (rreader)

A lightweight RSS feed aggregator that fetches, parses, and stores RSS feeds
organized by categories.

Usage:
    python -m rreader              # Update all feeds
    python -m rreader -c tech      # Update specific category
    python -m rreader --list-categories  # Show available categories

Configuration:
    Feeds are configured in ~/.rreader/feeds.json
    Settings are in ~/.rreader/config.json
"""

# Add function docstrings for all functions
```