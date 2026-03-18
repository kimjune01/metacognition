# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Downloads and parses RSS/Atom feeds using `feedparser`, extracting entries with titles, links, timestamps, and authors.

2. **Multi-source aggregation**: Reads feed sources from a JSON configuration file organized by categories, supporting multiple URLs per category.

3. **Time normalization**: Converts feed timestamps to a configurable timezone (default: UTC+9 Seoul) and formats them as either "HH:MM" (today) or "Mon DD, HH:MM" (other dates).

4. **Deduplication by timestamp**: Uses Unix timestamp as entry ID to prevent duplicates within a category.

5. **Sorted output**: Entries are sorted reverse-chronologically (newest first).

6. **Persistent storage**: Saves aggregated feeds as JSON files (one per category) in `~/.rreader/`.

7. **Configuration management**: Copies bundled default feeds on first run and merges new categories from updates without overwriting user customizations.

8. **Selective updates**: Can refresh a single category or all categories via the `target_category` parameter.

9. **Graceful fallback**: Handles missing `published_parsed` by falling back to `updated_parsed`, and missing authors by using source name.

## Triage

### Critical gaps (blocks production use):

1. **No error recovery**: A single failed feed fetch causes the entire program to exit (`sys.exit(0)`), preventing other feeds from updating.

2. **No rate limiting**: Rapid-fire requests to feed servers risk IP bans and violate respectful crawling norms.

3. **No caching headers**: Ignores `ETag` and `Last-Modified`, causing unnecessary bandwidth usage and server load.

4. **Silent failures**: The `except: continue` blocks swallow errors without logging what went wrong or which feeds failed.

### High-priority gaps (impacts reliability):

5. **No timeout handling**: Network requests can hang indefinitely if a server is unresponsive.

6. **No validation**: Accepts any JSON structure in `feeds.json`; malformed config will cause runtime crashes.

7. **Race conditions**: Concurrent executions could corrupt JSON files (no file locking).

8. **Memory unbounded**: Large feeds are loaded entirely into memory before processing.

### Medium-priority gaps (impacts usability):

9. **No incremental updates**: Every refresh re-downloads entire feeds, even if nothing changed.

10. **No entry limit**: Old entries accumulate forever in output files, eventually causing performance degradation.

11. **No feed health monitoring**: No way to detect chronically failing feeds or identify stale sources.

12. **Hardcoded paths**: The `~/.rreader/` directory and `feeds.json` filename aren't configurable.

### Low-priority gaps (nice-to-have):

13. **No HTTP compression**: Doesn't request `gzip`/`brotli` encoding to reduce bandwidth.

14. **No user-agent string**: Some servers block requests without proper identification.

15. **No entry content**: Only stores title/link, not the full entry description or content.

16. **No feed metadata**: Doesn't preserve feed-level info (description, icon, last build date).

## Plan

### 1. Error recovery (Critical #1)
**Change**: Replace `sys.exit(0)` with logging and continuation.
```python
import logging

for source, url in urls.items():
    try:
        d = feedparser.parse(url)
    except Exception as e:
        logging.error(f"Failed to fetch {url}: {e}")
        continue  # Process remaining feeds
```

### 2. Rate limiting (Critical #2)
**Change**: Add delays between requests.
```python
import time

for source, url in urls.items():
    time.sleep(1)  # 1-second delay between feeds
    d = feedparser.parse(url)
```

### 3. Caching headers (Critical #3)
**Change**: Store and use `ETag`/`Last-Modified` per feed.
```python
# In get_feed_from_rss(), before parsing:
cache_file = os.path.join(p["path_data"], f"cache_{category}_{source}.json")
etag, modified = None, None
if os.path.exists(cache_file):
    with open(cache_file) as f:
        cache = json.load(f)
        etag, modified = cache.get('etag'), cache.get('modified')

d = feedparser.parse(url, etag=etag, modified=modified)

if d.status == 304:  # Not modified
    continue

# After successful parse, save new cache:
with open(cache_file, 'w') as f:
    json.dump({'etag': d.get('etag'), 'modified': d.get('modified')}, f)
```

### 4. Logged failures (Critical #4)
**Change**: Replace all `except: continue` with specific exception logging.
```python
try:
    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
    if not parsed_time:
        logging.warning(f"No timestamp in entry: {feed.get('title', 'Unknown')}")
        continue
    # ... rest of parsing
except Exception as e:
    logging.error(f"Failed to parse entry {feed.get('link', 'Unknown')}: {e}")
    continue
```

### 5. Timeout handling (High #5)
**Change**: Set timeouts on HTTP requests.
```python
# feedparser doesn't expose timeout directly; use requests library:
import requests
from io import BytesIO

response = requests.get(url, timeout=10)
d = feedparser.parse(BytesIO(response.content))
```

### 6. Config validation (High #6)
**Change**: Add schema validation at startup.
```python
def validate_feeds_config(config):
    if not isinstance(config, dict):
        raise ValueError("feeds.json must be a dictionary")
    for category, data in config.items():
        if 'feeds' not in data or not isinstance(data['feeds'], dict):
            raise ValueError(f"Category {category} missing 'feeds' dict")
        for source, url in data['feeds'].items():
            if not url.startswith(('http://', 'https://')):
                raise ValueError(f"Invalid URL in {category}/{source}: {url}")

# Call before using RSS:
validate_feeds_config(RSS)
```

### 7. File locking (High #7)
**Change**: Use `fcntl` (Unix) or `msvcrt` (Windows) for exclusive locks.
```python
import fcntl

with open(output_file, 'w') as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    json.dump(rslt, f)
    fcntl.flock(f, fcntl.LOCK_UN)
```

### 8. Memory efficiency (High #8)
**Change**: Process entries as a stream instead of loading all into a dict.
```python
# Instead of rslt[entries["id"]] = entries:
entries_list = []
for feed in d.entries:
    # ... parse entry ...
    entries_list.append(entries)

entries_list.sort(key=lambda x: x['timestamp'], reverse=True)
```

### 9. Incremental updates (Medium #9)
**Change**: Load existing entries and merge new ones.
```python
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
existing_entries = {}
if os.path.exists(existing_file):
    with open(existing_file) as f:
        existing_entries = {e['id']: e for e in json.load(f)['entries']}

# Merge new entries:
for ts, entry in rslt.items():
    if ts not in existing_entries:
        existing_entries[ts] = entry
```

### 10. Entry limit (Medium #10)
**Change**: Cap stored entries per category.
```python
MAX_ENTRIES = 500
rslt = [val for key, val in sorted(rslt.items(), reverse=True)][:MAX_ENTRIES]
```

### 11. Feed health monitoring (Medium #11)
**Change**: Track failures and last-success timestamps.
```python
# Add to each category's JSON output:
{
    "entries": [...],
    "metadata": {
        "last_update": int(time.time()),
        "feed_status": {
            "source1": {"last_success": ts, "consecutive_failures": 0},
            "source2": {"last_success": ts, "consecutive_failures": 3}
        }
    }
}
```

### 12. Configurable paths (Medium #12)
**Change**: Accept environment variables or command-line arguments.
```python
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--data-dir', default=os.path.expanduser('~/.rreader/'))
args = parser.parse_args()
p["path_data"] = args.data_dir
```

### 13. HTTP compression (Low #13)
**Change**: Add `Accept-Encoding` header via requests library.
```python
response = requests.get(url, headers={'Accept-Encoding': 'gzip, deflate'})
```

### 14. User-agent string (Low #14)
**Change**: Set a descriptive User-Agent.
```python
USER_AGENT = 'RReader/1.0 (+https://github.com/yourproject)'
response = requests.get(url, headers={'User-Agent': USER_AGENT})
```

### 15. Entry content (Low #15)
**Change**: Extract and store `summary` or `content`.
```python
entries = {
    # ... existing fields ...
    "summary": feed.get('summary', ''),
    "content": feed.get('content', [{}])[0].get('value', '')
}
```

### 16. Feed metadata (Low #16)
**Change**: Store feed-level information.
```python
feed_metadata = {
    "title": d.feed.get('title'),
    "description": d.feed.get('description'),
    "link": d.feed.get('link'),
    "icon": d.feed.get('icon')
}
# Include in category JSON output
```