# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Downloads and parses RSS/Atom feeds using the `feedparser` library from multiple sources organized by category.

2. **Feed Organization**: Manages feeds in a JSON configuration file (`feeds.json`) with support for:
   - Multiple categories of feeds
   - Multiple sources per category
   - Optional author display per category

3. **Time Handling**: Converts feed timestamps to a configurable timezone (currently hardcoded to UTC+9/KST) and formats them as:
   - "HH:MM" for today's entries
   - "MMM DD, HH:MM" for older entries

4. **Data Persistence**: Saves parsed feed entries to JSON files (`rss_{category}.json`) in `~/.rreader/` directory with:
   - Entries sorted by timestamp (newest first)
   - Metadata including creation time
   - Deduplication by timestamp

5. **Configuration Management**: 
   - Auto-creates data directory if missing
   - Copies bundled `feeds.json` template if user doesn't have one
   - Merges new categories from bundled config into existing user config

6. **Selective Updates**: Can refresh either all categories or a single target category.

7. **Basic Error Handling**: Try-catch blocks around feed parsing and timestamp extraction with silent failures.

## Triage

### Critical Gaps

1. **No Error Visibility**: Silent failures (`sys.exit(0)` on error) mean users never know when feeds fail to load. In production, 404s, network timeouts, and malformed XML should be logged and reported.

2. **Timestamp Collision**: Using timestamp as the entry ID (`"id": ts`) means two articles published in the same second will overwrite each other. This causes data loss.

3. **No Caching Strategy**: Every `do()` call re-downloads all feeds regardless of how recently they were fetched. This wastes bandwidth and risks rate-limiting.

4. **Hardcoded Timezone**: `TIMEZONE` is hardcoded to UTC+9. Production systems need user-configurable timezones.

### Important Gaps

5. **No Feed Validation**: Doesn't verify that `feeds.json` is well-formed JSON or that URLs are valid before attempting to fetch.

6. **Missing Feed Metadata**: Doesn't track:
   - Last successful fetch time per feed
   - Failure counts/history per source
   - Feed title or description from RSS metadata

7. **No Content Extraction**: Only saves title, URL, and metadata. Doesn't extract article summaries (`feed.summary`) or content, which users typically want.

8. **Synchronous Fetching**: Fetches feeds serially. With 10+ feeds, this is slow. Should fetch concurrently.

9. **No User Configuration for Refresh**: Hardcoded behavior—no way to set refresh intervals, max entries per feed, or entry retention policies.

### Nice-to-Have Gaps

10. **No Read/Unread Tracking**: Doesn't mark which entries the user has read.

11. **No Search/Filter**: Once feeds are saved, no built-in way to search by keyword or filter by source.

12. **Limited Date Parsing Fallbacks**: Only tries `published_parsed` and `updated_parsed`. Some feeds use other fields like `created_parsed` or custom fields.

## Plan

### 1. Error Visibility
**What to change:**
- Replace `sys.exit(0)` with proper logging using Python's `logging` module
- Add a return value indicating success/failure for each feed
- Create `~/.rreader/errors.log` to persist error history
- In the result JSON, add a `"status"` field per source: `{"status": "ok", "fetched_at": 1234567890}` or `{"status": "error", "error": "HTTP 404", "failed_at": 1234567890}`

**Concrete changes:**
```python
import logging
logging.basicConfig(filename=os.path.join(p["path_data"], "errors.log"))

# Replace try/except blocks:
except Exception as e:
    logging.error(f"Failed to fetch {url}: {str(e)}")
    # Continue to next feed instead of sys.exit
```

### 2. Timestamp Collision
**What to change:**
- Generate unique IDs by combining timestamp with a hash of the feed URL or GUID
- RSS feeds have `feed.id` or `feed.guid` fields that are meant to be unique—use these when available

**Concrete changes:**
```python
import hashlib

# In the loop:
unique_id = feed.get('id') or feed.get('guid') or f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
entries = {
    "id": unique_id,  # Use unique_id instead of ts
    "timestamp": ts,
    # ... rest of fields
}
rslt[entries["id"]] = entries
```

### 3. Caching Strategy
**What to change:**
- Check the creation timestamp in existing `rss_{category}.json` files
- Skip re-fetching if last fetch was within a configurable interval (e.g., 15 minutes)
- Add a `--force` flag to bypass cache

**Concrete changes:**
```python
CACHE_DURATION = 900  # 15 minutes in seconds

def get_feed_from_rss(category, urls, show_author=False, log=False, force_refresh=False):
    cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
    
    if not force_refresh and os.path.exists(cache_file):
        with open(cache_file, 'r') as f:
            cached = json.load(f)
            if time.time() - cached.get("created_at", 0) < CACHE_DURATION:
                if log:
                    print(f"Using cached data for {category}")
                return cached
    # ... proceed with fetch
```

### 4. Hardcoded Timezone
**What to change:**
- Add a `config.json` file in `~/.rreader/` with user settings
- Include a `timezone` field (default to system timezone if not specified)
- Load this at startup instead of importing a hardcoded value

**Concrete changes:**
```python
# In config.py:
import datetime
from zoneinfo import ZoneInfo

CONFIG_FILE = os.path.join(p["path_data"], "config.json")
DEFAULT_CONFIG = {"timezone": "UTC"}

if os.path.exists(CONFIG_FILE):
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
else:
    config = DEFAULT_CONFIG

TIMEZONE = ZoneInfo(config.get("timezone", "UTC"))
```

### 5. Feed Validation
**What to change:**
- Add a validation function that checks `feeds.json` structure on load
- Validate that each category has a "feeds" dict
- Validate that URLs start with http:// or https://
- Print warnings for invalid entries but continue

**Concrete changes:**
```python
def validate_feeds_config(rss_config):
    valid = {}
    for category, data in rss_config.items():
        if not isinstance(data, dict) or 'feeds' not in data:
            logging.warning(f"Invalid category {category}: missing 'feeds' key")
            continue
        valid_feeds = {}
        for source, url in data['feeds'].items():
            if not url.startswith(('http://', 'https://')):
                logging.warning(f"Invalid URL for {source}: {url}")
                continue
            valid_feeds[source] = url
        if valid_feeds:
            valid[category] = {**data, 'feeds': valid_feeds}
    return valid

# After loading RSS dict:
RSS = validate_feeds_config(RSS)
```

### 6. Missing Feed Metadata
**What to change:**
- Save feed-level info (title, description, last updated) alongside entries
- Track per-source statistics: last fetch time, success/failure count

**Concrete changes:**
```python
rslt = {
    "feed_metadata": {
        "title": d.feed.get('title', category),
        "description": d.feed.get('description', ''),
        "last_fetched": int(time.time())
    },
    "entries": rslt,
    "created_at": int(time.time())
}
```

### 7. Content Extraction
**What to change:**
- Add `summary` and `content` fields to each entry
- Handle both `feed.summary` and `feed.content` (some feeds use one or both)

**Concrete changes:**
```python
entries = {
    "id": unique_id,
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": feed.get('summary', ''),
    "content": feed.get('content', [{}])[0].get('value', '') if 'content' in feed else ''
}
```

### 8. Synchronous Fetching
**What to change:**
- Use `concurrent.futures.ThreadPoolExecutor` to fetch feeds in parallel
- Limit concurrency to avoid overwhelming servers (e.g., max 5 concurrent)

**Concrete changes:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, log):
    try:
        if log:
            sys.stdout.write(f"- {url}")
        d = feedparser.parse(url)
        if log:
            sys.stdout.write(" - Done\n")
        return source, d, None
    except Exception as e:
        return source, None, str(e)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_single_feed, src, url, log): src 
                   for src, url in urls.items()}
        
        for future in as_completed(futures):
            source, d, error = future.result()
            if error:
                logging.error(f"Failed {source}: {error}")
                continue
            # ... process d.entries as before
```

### 9. User Configuration for Refresh
**What to change:**
- Extend `config.json` to include:
  - `refresh_interval_minutes`: cache duration
  - `max_entries_per_feed`: limit saved entries
  - `retention_days`: auto-delete entries older than N days

**Concrete changes:**
```python
DEFAULT_CONFIG = {
    "timezone": "UTC",
    "refresh_interval_minutes": 15,
    "max_entries_per_feed": 100,
    "retention_days": 30
}

# When saving entries:
max_entries = config.get("max_entries_per_feed", 100)
rslt["entries"] = rslt["entries"][:max_entries]

# Add pruning function:
def prune_old_entries(entries, retention_days):
    cutoff = time.time() - (retention_days * 86400)
    return [e for e in entries if e["timestamp"] >= cutoff]
```

### 10. Read/Unread Tracking
**What to change:**
- Add a `read_entries.json` file storing set of read entry IDs
- When displaying entries, mark which are unread
- Provide a function to mark entries as read

**Concrete changes:**
```python
READ_FILE = os.path.join(p["path_data"], "read_entries.json")

def load_read_entries():
    if os.path.exists(READ_FILE):
        with open(READ_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def mark_as_read(entry_id):
    read_entries = load_read_entries()
    read_entries.add(entry_id)
    with open(READ_FILE, 'w') as f:
        json.dump(list(read_entries), f)

# Add to entries:
read_entries = load_read_entries()
entries["is_read"] = entries["id"] in read_entries
```

### 11. Search/Filter
**What to change:**
- Add a `search(query, category=None)` function that loads all saved entries and filters by keyword in title/summary
- Return matching entries sorted by timestamp

**Concrete changes:**
```python
def search(query, category=None):
    results = []
    pattern = query.lower()
    
    categories = [category] if category else [c for c in RSS.keys()]
    
    for cat in categories:
        file_path = os.path.join(p["path_data"], f"rss_{cat}.json")
        if not os.path.exists(file_path):
            continue
        with open(file_path, 'r') as f:
            data = json.load(f)
            for entry in data.get("entries", []):
                if pattern in entry["title"].lower() or pattern in entry.get("summary", "").lower():
                    results.append(entry)
    
    return sorted(results, key=lambda x: x["timestamp"], reverse=True)
```

### 12. Extended Date Parsing Fallbacks
**What to change:**
- Try multiple timestamp fields in order of preference
- Fall back to current time if no valid timestamp found (with a warning)

**Concrete changes:**
```python
def extract_timestamp(feed):
    for field in ['published_parsed', 'updated_parsed', 'created_parsed']:
        parsed_time = getattr(feed, field, None)
        if parsed_time:
            try:
                return datetime.datetime(*parsed_time[:6])
            except:
                continue
    
    logging.warning(f"No valid timestamp for entry: {feed.get('title', 'Unknown')}")
    return datetime.datetime.now()  # Fallback

# Use in main loop:
at = extract_timestamp(feed).replace(tzinfo=datetime.timezone.utc).astimezone(TIMEZONE)
```