# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS/Atom feeds using the `feedparser` library from multiple sources organized by category.

2. **Data Persistence**: Stores parsed feed entries as JSON files in a user data directory (`~/.rreader/`), one file per category (`rss_{category}.json`).

3. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file with feed sources organized by category
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled feeds into existing user configuration

4. **Entry Deduplication**: Uses timestamp as a unique identifier to prevent duplicate entries from the same source.

5. **Timestamp Normalization**: Converts feed timestamps to a configured timezone (currently KST/UTC+9) and formats them as human-readable strings (time-only for today, date+time for older entries).

6. **Author Attribution**: Supports per-category configuration for displaying feed-specific authors vs. source names.

7. **Sorting**: Orders entries by timestamp (newest first).

8. **Selective Updates**: Can update a single category or all categories via the `target_category` parameter.

9. **Optional Logging**: Provides progress feedback when the `log` parameter is enabled.

## Triage

### Critical Gaps (P0)
1. **No Error Handling for Individual Feeds**: Failed feeds cause silent failures or system exit, breaking batch updates
2. **No Data Validation**: Missing validation for feed structure, URL format, or JSON schema
3. **ID Collision Risk**: Using timestamp as ID can cause collisions for feeds published in the same second

### Important Gaps (P1)
4. **No Rate Limiting**: Could be blocked or banned by feed providers during rapid updates
5. **No Caching/Conditional Requests**: Downloads entire feeds even if unchanged (no ETag/Last-Modified support)
6. **No Stale Data Detection**: Old cached data persists indefinitely without indication of age
7. **Missing Feed Metadata**: Doesn't store feed-level information (description, last update time, error status)
8. **No Entry Content**: Only stores title/link/metadata, not the actual content/summary

### Nice-to-Have Gaps (P2)
9. **No Concurrent Fetching**: Sequential processing makes updates slow for many feeds
10. **Limited Date Handling**: Assumes today's date is in the configured timezone, may show wrong relative dates
11. **No Feed Discovery**: Cannot add feeds; requires manual JSON editing
12. **No Read/Unread Tracking**: Cannot mark entries as read
13. **No Entry Limits**: Unlimited storage growth without cleanup of old entries
14. **Hard-coded Timezone**: Timezone is not user-configurable
15. **Minimal CLI Interface**: No command-line arguments for common operations

## Plan

### P0 Fixes

**1. Robust Error Handling for Individual Feeds**
```python
# Change: Wrap feed processing in try-except per feed
for source, url in urls.items():
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        
        # Add validation
        if not hasattr(d, 'entries'):
            if log:
                sys.stdout.write(" - Invalid feed format\n")
            continue
            
        if log:
            sys.stdout.write(f" - Done ({len(d.entries)} entries)\n")
            
    except Exception as e:
        if log:
            sys.stdout.write(f" - Failed: {str(e)}\n")
        continue  # Don't exit, continue with next feed
```

**2. Data Validation**
```python
# Add at top of get_feed_from_rss:
def validate_url(url):
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.scheme in ('http', 'https') and parsed.netloc

# Before parsing:
if not validate_url(url):
    if log:
        sys.stdout.write(f" - Invalid URL: {url}\n")
    continue

# Add JSON schema validation when loading feeds.json:
def validate_feeds_config(data):
    if not isinstance(data, dict):
        raise ValueError("feeds.json must be a dict")
    for category, config in data.items():
        if 'feeds' not in config or not isinstance(config['feeds'], dict):
            raise ValueError(f"Category {category} missing 'feeds' dict")
    return True
```

**3. Fix ID Collision Risk**
```python
# Change ID generation to include source and use a counter for collisions:
id_base = f"{ts}_{source}"
counter = 0
while id_base in rslt:
    counter += 1
    id_base = f"{ts}_{source}_{counter}"

entries = {
    "id": id_base,  # Changed from just ts
    # ... rest unchanged
}
```

### P1 Improvements

**4. Add Rate Limiting**
```python
import time

# Add at module level:
RATE_LIMIT_DELAY = 0.5  # seconds between requests

# In get_feed_from_rss loop:
for i, (source, url) in enumerate(urls.items()):
    if i > 0:  # Don't delay first request
        time.sleep(RATE_LIMIT_DELAY)
    # ... existing code
```

**5. Implement Conditional Requests**
```python
# Store ETags and Last-Modified headers:
# Add to entries dict structure:
{
    "entries": [...],
    "created_at": int(time.time()),
    "etag": d.get('etag'),  # Add this
    "last_modified": d.get('modified')  # Add this
}

# Before parsing, load previous data and use headers:
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
headers = {}
if os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        old_data = json.load(f)
        if 'etag' in old_data:
            headers['If-None-Match'] = old_data['etag']
        if 'last_modified' in old_data:
            headers['If-Modified-Since'] = old_data['last_modified']

d = feedparser.parse(url, etag=headers.get('If-None-Match'), 
                     modified=headers.get('If-Modified-Since'))

if d.status == 304:  # Not modified
    continue
```

**6. Add Stale Data Warning**
```python
# Add staleness check in output:
MAX_AGE_HOURS = 24

rslt = {
    "entries": rslt, 
    "created_at": int(time.time()),
    "is_stale": False  # Add this field
}

# Before writing, check age:
if os.path.exists(cache_file):
    with open(cache_file, 'r') as f:
        old = json.load(f)
        age_hours = (time.time() - old.get('created_at', 0)) / 3600
        rslt['is_stale'] = age_hours > MAX_AGE_HOURS
```

**7. Store Feed Metadata**
```python
# Add feed-level metadata structure:
rslt = {
    "entries": entries_list,
    "created_at": int(time.time()),
    "feeds_status": {  # New field
        source: {
            "last_success": int(time.time()),
            "last_error": None,
            "entry_count": len([e for e in entries_list if e['sourceName'] == source]),
            "feed_title": d.feed.get('title', source),
            "feed_link": d.feed.get('link', url)
        } for source in urls.keys()
    }
}
```

**8. Store Entry Content**
```python
# Add to entries dict:
entries = {
    "id": ts,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', ''),  # Add this
    "content": feed.get('content', [{}])[0].get('value', '') if hasattr(feed, 'content') else ''  # Add this
}
```

### P2 Enhancements

**9. Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    """Extract single feed fetch into separate function"""
    # Move existing feed fetch logic here
    pass

# In get_feed_from_rss:
with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(fetch_single_feed, src, url, log): src 
               for src, url in urls.items()}
    
    for future in as_completed(futures):
        source = futures[future]
        try:
            feed_data = future.result()
            rslt.update(feed_data)
        except Exception as e:
            if log:
                print(f"Feed {source} failed: {e}")
```

**10. Fix Date Handling**
```python
# Replace datetime.date.today() with timezone-aware version:
today = datetime.datetime.now(TIMEZONE).date()
pubDate = at.strftime(
    "%H:%M" if at.date() == today else "%b %d, %H:%M"
)
```

**11. Add CLI for Feed Management**
```python
# Add argparse support:
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('--category', help='Update specific category')
    parser.add_argument('--add-feed', nargs=3, metavar=('CATEGORY', 'NAME', 'URL'),
                       help='Add a new feed')
    parser.add_argument('--list', action='store_true', help='List all categories')
    parser.add_argument('--verbose', action='store_true', help='Enable logging')
    
    args = parser.parse_args()
    
    if args.add_feed:
        # Implement feed addition logic
        pass
    elif args.list:
        # List categories
        pass
    else:
        do(target_category=args.category, log=args.verbose)
```

**13. Implement Entry Limits**
```python
# Add after sorting entries:
MAX_ENTRIES_PER_CATEGORY = 500
MAX_AGE_DAYS = 30

entries_list = [val for key, val in sorted(rslt.items(), reverse=True)]

# Filter by age and count
cutoff_time = time.time() - (MAX_AGE_DAYS * 86400)
entries_list = [e for e in entries_list if e['timestamp'] > cutoff_time]
entries_list = entries_list[:MAX_ENTRIES_PER_CATEGORY]
```