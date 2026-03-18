# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Fetching**: Downloads and parses RSS/Atom feeds from multiple sources using `feedparser`
2. **Multi-Category Support**: Organizes feeds into categories, each with multiple source URLs
3. **Feed Configuration**: Uses a `feeds.json` file in `~/.rreader/` for user-customizable feed sources
4. **Automatic Setup**: Copies bundled default feeds on first run, merges new categories from updates
5. **Timestamp Processing**: Normalizes feed timestamps to a configurable timezone (default: KST/UTC+9)
6. **Date Formatting**: Displays "HH:MM" for today's posts, "MMM DD, HH:MM" for older ones
7. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries within a category
8. **JSON Output**: Saves processed feeds to `~/.rreader/rss_{category}.json` with sorted entries
9. **Author Attribution**: Optional per-category author display from feed metadata or source name
10. **CLI Interface**: Can fetch all categories or a single target category with optional logging

## Triage

### Critical Gaps (Must Fix)

1. **Error Handling is Silent**: The `except: continue` blocks silently skip broken feeds or entries. Users won't know when feeds fail or why.

2. **No Cache Invalidation**: Cached JSON files have a `created_at` timestamp but nothing uses it. The system has no concept of "stale data."

3. **Duplicate ID Collisions**: Using Unix timestamp as ID means two posts published in the same second will collide (last one wins).

4. **No Network Timeout**: `feedparser.parse()` has no timeout configuration; a hanging server will block indefinitely.

5. **No User Feedback**: When run without `log=True`, the system provides zero progress indication, even for slow operations.

### High-Priority Gaps (Should Add)

6. **Missing CLI Entry Point**: No `if __name__ == "__main__"` argument parsing for category selection or logging flags from command line.

7. **No Feed Validation**: Doesn't check if `feeds.json` has valid structure before processing.

8. **No Retry Logic**: Transient network failures immediately fail a source instead of retrying.

9. **Inefficient Update Strategy**: Always fetches all feeds even if recently cached.

10. **No Content Sanitization**: Feed titles/content could contain malicious HTML or broken encoding.

### Medium-Priority Gaps (Nice to Have)

11. **No Incremental Updates**: Always overwrites entire category JSON; can't append new entries to existing cache.

12. **No Feed Metadata**: Doesn't store feed description, icon/logo, or last-modified headers.

13. **No Rate Limiting**: Could hammer servers if misconfigured with many feeds.

14. **No HTTP Header Control**: Doesn't send User-Agent or respect ETag/Last-Modified for efficient polling.

15. **No Entry Limit**: Could create massive JSON files if feeds have thousands of historical entries.

## Plan

### 1. Error Handling is Silent
**Change**: Replace bare `except:` with specific exceptions and logging
```python
# In get_feed_from_rss(), replace:
except:
    sys.exit(" - Failed\n" if log else 0)
# With:
except Exception as e:
    error_msg = f" - Failed: {type(e).__name__}: {str(e)}\n"
    if log:
        sys.stderr.write(error_msg)
    # Store error in result for UI display
    continue
```
**Add**: Error collection in result: `{"entries": [...], "errors": [{"source": "...", "error": "..."}]}`

### 2. No Cache Invalidation
**Change**: Add cache expiry check before reading cached files
```python
# In do(), add helper:
def is_cache_valid(cache_file, max_age_seconds=300):
    if not os.path.exists(cache_file):
        return False
    with open(cache_file) as f:
        data = json.load(f)
    age = int(time.time()) - data.get("created_at", 0)
    return age < max_age_seconds

# Skip fetch if cache valid:
if not force_refresh and is_cache_valid(cache_path):
    return
```

### 3. Duplicate ID Collisions
**Change**: Generate unique IDs by combining timestamp + hash of URL
```python
import hashlib

def make_entry_id(timestamp, url):
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{timestamp}_{url_hash}"

# Replace:
entries = {"id": ts, ...}
# With:
entries = {"id": make_entry_id(ts, feed.link), ...}
```

### 4. No Network Timeout
**Change**: Configure feedparser with timeout via underlying library
```python
import socket
socket.setdefaulttimeout(10)  # Add at module level

# Or wrap parse call:
import signal
def timeout_handler(signum, frame):
    raise TimeoutError("Feed fetch timeout")
signal.signal(signal.SIGALRM, timeout_handler)
signal.alarm(10)
d = feedparser.parse(url)
signal.alarm(0)
```

### 5. No User Feedback
**Change**: Add progress output even when `log=False`
```python
def get_feed_from_rss(..., log=False):
    total = len(urls)
    for idx, (source, url) in enumerate(urls.items(), 1):
        sys.stdout.write(f"\r[{idx}/{total}] {source}...")
        sys.stdout.flush()
        # ... fetch logic ...
    sys.stdout.write("\r" + " " * 80 + "\r")  # Clear line
```

### 6. Missing CLI Entry Point
**Change**: Add argparse in `if __name__ == "__main__"` block at bottom of file
```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--category", help="Fetch specific category")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--force", action="store_true", help="Ignore cache")
    args = parser.parse_args()
    do(target_category=args.category, log=args.verbose, force_refresh=args.force)
```

### 7. No Feed Validation
**Change**: Add schema validation before processing
```python
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    for cat, data in config.items():
        if not isinstance(data, dict) or "feeds" not in data:
            raise ValueError(f"Category '{cat}' missing 'feeds' key")
        if not isinstance(data["feeds"], dict):
            raise ValueError(f"Category '{cat}' feeds must be a dict")
    return True

# In do(), after loading RSS:
validate_feeds_config(RSS)
```

### 8. No Retry Logic
**Change**: Add retry wrapper with exponential backoff
```python
from functools import wraps
import time

def retry(max_attempts=3, backoff=2):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(backoff ** attempt)
        return wrapper
    return decorator

@retry(max_attempts=3)
def fetch_feed(url):
    return feedparser.parse(url)

# Use: d = fetch_feed(url)
```

### 9. Inefficient Update Strategy
**Change**: Implement conditional fetching using cache age check (see #2)
**Add**: CLI flag `--max-age` to control cache freshness threshold

### 10. No Content Sanitization
**Change**: Add HTML sanitization for titles
```python
import html

# After extracting title:
entries["title"] = html.unescape(feed.title).strip()

# For security, consider bleach library:
# import bleach
# entries["title"] = bleach.clean(feed.title, tags=[], strip=True)
```

### 11. No Incremental Updates
**Change**: Load existing cache, merge new entries, limit total count
```python
def merge_entries(old_entries, new_entries, max_count=100):
    seen_urls = {e["url"] for e in new_entries}
    # Keep old entries not in new fetch
    merged = new_entries + [e for e in old_entries if e["url"] not in seen_urls]
    # Sort by timestamp desc, limit count
    merged.sort(key=lambda x: x["timestamp"], reverse=True)
    return merged[:max_count]
```

### 12. No Feed Metadata
**Change**: Extract and store feed-level info
```python
# After d = feedparser.parse(url):
feed_meta = {
    "title": d.feed.get("title", source),
    "description": d.feed.get("description", ""),
    "link": d.feed.get("link", ""),
    "icon": d.feed.get("icon", ""),
}
# Store per-source in result
```

### 13. No Rate Limiting
**Change**: Add sleep between requests
```python
import time

for source, url in urls.items():
    # ... fetch logic ...
    time.sleep(0.5)  # 500ms between feeds
```

### 14. No HTTP Header Control
**Change**: Feedparser respects these via custom request handling
```python
import urllib.request

def fetch_with_headers(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "rreader/1.0",
            "Accept": "application/rss+xml, application/xml",
        }
    )
    return feedparser.parse(request)
```

### 15. No Entry Limit
**Change**: Add max entries per feed and per category
```python
MAX_ENTRIES_PER_FEED = 50
MAX_ENTRIES_PER_CATEGORY = 200

# After processing d.entries:
for feed in d.entries[:MAX_ENTRIES_PER_FEED]:
    # ... process ...

# Before writing JSON:
rslt["entries"] = rslt["entries"][:MAX_ENTRIES_PER_CATEGORY]
```