# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-source Aggregation**: Supports organizing feeds into categories, each containing multiple feed URLs
3. **Time Normalization**: Converts feed timestamps to a configurable timezone (default: UTC+9 Seoul)
4. **Deduplication**: Uses timestamp-based IDs to avoid duplicate entries within a category
5. **Data Persistence**: Stores parsed feed data as JSON files (one per category)
6. **Configuration Management**: 
   - Ships with bundled default feeds (`feeds.json`)
   - Copies defaults to user directory on first run
   - Auto-merges new categories from updates without overwriting user customizations
7. **Flexible Execution**: Can refresh all categories or target a specific category
8. **Author Attribution**: Configurable per-category to show feed source or original author
9. **Date Formatting**: Shows time-only for today's entries, date+time for older entries
10. **Sorted Output**: Entries sorted by timestamp (newest first)

## Triage

### Critical Gaps (Production Blockers)

1. **No Error Handling**: Silent failures in feed parsing could leave stale data
2. **No HTTP Timeout Configuration**: Can hang indefinitely on unresponsive feeds
3. **No Rate Limiting**: Could trigger rate limits or be seen as abusive
4. **No Logging Infrastructure**: Only optional stdout, no persistent logs
5. **Unsafe Exception Catching**: Bare `except:` clauses mask all errors including `KeyboardInterrupt`

### High Priority (User Experience Issues)

6. **No Feed Validation**: Accepts any URL without checking if it's actually RSS/Atom
7. **No Staleness Detection**: No way to know if feeds failed to update
8. **No Entry Limits**: Could create massive JSON files over time
9. **No Concurrent Fetching**: Fetches feeds serially, slow for many sources
10. **Collision-Prone ID Generation**: Uses timestamp as ID, but multiple entries can share timestamps

### Medium Priority (Operational Concerns)

11. **No User-Agent String**: Some servers block requests without proper identification
12. **No Conditional Requests**: Always downloads full feeds (no ETag/Last-Modified support)
13. **No Retry Logic**: Single attempt per feed, no backoff for transient failures
14. **No Configuration Validation**: Malformed `feeds.json` crashes the system
15. **No Metrics/Monitoring**: No visibility into success rates, latency, or feed health

### Low Priority (Nice to Have)

16. **No Content Sanitization**: Doesn't clean HTML/XSS risks in titles
17. **No OPML Import/Export**: Standard RSS format not supported
18. **Limited Date Parsing**: Relies on `feedparser`'s parsing without fallbacks
19. **No Archive/Cleanup Strategy**: Old JSON files accumulate indefinitely
20. **No CLI Interface**: Function parameters only, no command-line arguments

## Plan

### Critical Fixes

**1. Structured Error Handling**
```python
# Replace bare except with specific exceptions
try:
    d = feedparser.parse(url)
    if d.bozo:  # feedparser's error flag
        raise feedparser.ParseError(d.bozo_exception)
except (urllib.error.URLError, feedparser.ParseError) as e:
    if log:
        sys.stderr.write(f" - Failed: {e}\n")
    # Log to file, increment error counter
    continue  # Skip this feed, don't crash
except KeyboardInterrupt:
    raise  # Don't catch user interrupts
```

**2. HTTP Timeout Configuration**
```python
# In feedparser.parse() call
d = feedparser.parse(url, timeout=15)  # 15 second timeout

# Add to config.py
HTTP_TIMEOUT = 15
MAX_RETRIES = 3
```

**3. Rate Limiting**
```python
import time

# Add between feed fetches in loop
DELAY_BETWEEN_FEEDS = 1.0  # seconds
time.sleep(DELAY_BETWEEN_FEEDS)

# For same-domain feeds, group and add longer delays
```

**4. Proper Logging**
```python
import logging

# Replace print statements with logging
logging.basicConfig(
    filename=os.path.join(p["path_data"], "rreader.log"),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
logger.info(f"Fetching {url}")
logger.error(f"Failed to parse {url}: {e}")
```

**5. Specific Exception Handling**
```python
# Replace all bare except clauses
except feedparser.ParseError:
    # Handle parsing failures
except (urllib.error.URLError, urllib.error.HTTPError) as e:
    # Handle network failures
except KeyError:
    # Handle missing required fields
```

### High Priority Enhancements

**6. Feed Validation**
```python
def validate_feed(url):
    """Check if URL returns valid RSS/Atom"""
    try:
        d = feedparser.parse(url)
        if d.bozo and not d.entries:
            return False, d.bozo_exception
        if not d.entries:
            return False, "No entries found"
        return True, None
    except Exception as e:
        return False, str(e)
```

**7. Staleness Detection**
```python
# In output JSON
"metadata": {
    "created_at": int(time.time()),
    "last_successful_fetch": int(time.time()),
    "failed_feeds": ["http://dead-feed.com"],
    "entry_count": len(rslt["entries"])
}
```

**8. Entry Limits**
```python
# In config.py
MAX_ENTRIES_PER_CATEGORY = 100

# Before saving
rslt["entries"] = rslt["entries"][:MAX_ENTRIES_PER_CATEGORY]
```

**9. Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url):
    """Fetch one feed, return entries"""
    # Move existing logic here
    pass

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        try:
            entries = future.result(timeout=30)
            rslt.update(entries)
        except Exception as e:
            logger.error(f"Feed failed: {e}")
```

**10. Unique ID Generation**
```python
import hashlib

def generate_entry_id(feed):
    """Create unique ID from URL + timestamp + title"""
    unique_string = f"{feed.link}{feed.title}{parsed_time}"
    return hashlib.md5(unique_string.encode()).hexdigest()

# Replace: "id": ts
# With: "id": generate_entry_id(feed)
```

### Medium Priority Improvements

**11. User-Agent String**
```python
# In config.py
USER_AGENT = "RReader/1.0 (+https://github.com/yourproject)"

# When parsing
d = feedparser.parse(url, agent=USER_AGENT)
```

**12. Conditional Requests**
```python
# Store ETags and Last-Modified per feed
feed_cache = load_feed_cache()  # {url: {"etag": ..., "modified": ...}}

d = feedparser.parse(
    url,
    etag=feed_cache.get(url, {}).get("etag"),
    modified=feed_cache.get(url, {}).get("modified")
)

if d.status == 304:  # Not Modified
    # Use cached data
    pass
else:
    # Update cache with d.etag, d.modified
    save_feed_cache(url, d.etag, d.modified)
```

**13. Retry Logic**
```python
from time import sleep

def fetch_with_retry(url, max_attempts=3):
    for attempt in range(max_attempts):
        try:
            return feedparser.parse(url, timeout=15)
        except Exception as e:
            if attempt < max_attempts - 1:
                sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
```

**14. Configuration Validation**
```python
def validate_feeds_config(config):
    """Validate feeds.json structure"""
    if not isinstance(config, dict):
        raise ValueError("Config must be a dictionary")
    
    for category, data in config.items():
        if "feeds" not in data:
            raise ValueError(f"Category {category} missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category {category} 'feeds' must be dict")
        for name, url in data["feeds"].items():
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"Invalid URL: {url}")

# Call before processing
validate_feeds_config(RSS)
```

**15. Metrics Collection**
```python
metrics = {
    "fetch_start": time.time(),
    "feeds_attempted": 0,
    "feeds_succeeded": 0,
    "feeds_failed": 0,
    "total_entries": 0,
    "errors": []
}

# Increment throughout process
# Save to metrics.json for monitoring
```

### Low Priority Additions

**16. Content Sanitization**
```python
import bleach

def sanitize_text(text):
    """Remove HTML tags and dangerous content"""
    return bleach.clean(text, tags=[], strip=True)

entries["title"] = sanitize_text(feed.title)
```

**17. OPML Support**
```python
def import_opml(opml_file):
    """Import feeds from OPML file"""
    # Parse OPML XML
    # Extract feed URLs
    # Add to feeds.json
    pass

def export_opml(category):
    """Export category to OPML"""
    # Generate OPML XML
    # Write to file
    pass
```

**18. Robust Date Parsing**
```python
from dateutil.parser import parse

def parse_date_flexible(feed):
    """Try multiple date fields and formats"""
    for field in ['published_parsed', 'updated_parsed', 'created_parsed']:
        if hasattr(feed, field):
            try:
                return getattr(feed, field)
            except:
                continue
    
    # Try parsing string dates
    for field in ['published', 'updated', 'created']:
        if hasattr(feed, field):
            try:
                return parse(getattr(feed, field)).timetuple()
            except:
                continue
    
    return None  # No valid date found
```

**19. Archive Strategy**
```python
# In config.py
ARCHIVE_AFTER_DAYS = 30
MAX_ARCHIVE_SIZE_MB = 100

def archive_old_entries():
    """Move entries older than threshold to archive"""
    # Check age of entries
    # Move to archive/YYYY-MM.json
    # Delete archives exceeding size limit
    pass
```

**20. CLI Interface**
```python
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('--category', help='Specific category to refresh')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    parser.add_argument('--validate', action='store_true', help='Validate all feeds')
    
    args = parser.parse_args()
    do(target_category=args.category, log=args.verbose)
```