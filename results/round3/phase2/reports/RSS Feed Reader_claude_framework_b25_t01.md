# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS feed fetching and parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from URLs defined in a JSON configuration file.

2. **Multi-category feed organization**: Supports organizing feeds into categories, each with multiple sources (URLs).

3. **Feed aggregation and deduplication**: Combines entries from multiple sources within a category, deduplicates by timestamp, and sorts in reverse chronological order.

4. **Time normalization**: Converts feed timestamps to a configurable timezone (currently Seoul/KST UTC+9) and formats them as human-readable strings.

5. **Persistent JSON storage**: Saves processed feeds as `rss_{category}.json` files in a data directory (`~/.rreader/`).

6. **Configuration management**: 
   - Maintains a `feeds.json` configuration file
   - Auto-copies bundled default feeds on first run
   - Merges new categories from bundled config into existing user config

7. **Selective or batch processing**: Can process a single category or all categories at once.

8. **Optional author display**: Supports per-category configuration to show feed author instead of source name.

9. **Logging capability**: Optional verbose output during feed fetching.

## Triage

### Critical Gaps

1. **Error handling is incomplete**
   - The try-except around `feedparser.parse()` exits the entire program on failure
   - Individual feed entry parsing failures are silently skipped
   - No retry logic for transient network errors
   - No timeout configuration for hanging requests

2. **No rate limiting or request throttling**
   - Will hammer all feed URLs simultaneously
   - No User-Agent header (some sites block default feedparser UA)
   - No respect for server-side rate limits or `Retry-After` headers

3. **Feed freshness tracking is broken**
   - The `created_at` timestamp is written but never read
   - No mechanism to avoid refetching unchanged feeds
   - No ETag or Last-Modified header support for conditional requests

### Important Gaps

4. **No data validation**
   - Doesn't validate feed JSON structure before writing
   - No schema validation for `feeds.json`
   - Malformed feed URLs will cause cryptic failures

5. **Collision handling is naive**
   - Uses timestamp as unique ID, but multiple entries can share the same second
   - Later entries silently overwrite earlier ones with same timestamp

6. **Limited observability**
   - No structured logging (just print statements)
   - No metrics on fetch success/failure rates
   - No feed health monitoring

7. **Configuration is fragile**
   - Changes to bundled `feeds.json` only merge new categories, never update existing ones
   - No migration system for config schema changes
   - No validation that URLs are well-formed

### Nice-to-Have Gaps

8. **No content extraction or cleaning**
   - Feed titles may contain HTML entities or malformed text
   - No truncation of excessively long titles
   - No extraction of summary/description fields

9. **Limited metadata**
   - Doesn't store feed-level metadata (update frequency, last fetch status)
   - No tracking of read/unread status
   - No tagging or filtering capabilities

10. **No asynchronous fetching**
    - Sequential HTTP requests make category updates slow
    - No parallelization across feeds

## Plan

### Critical Fixes

**1. Robust error handling**

```python
# Replace the bare try-except with:
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def fetch_feed_with_retry(url, timeout=10, max_retries=3):
    """Fetch feed with timeout and retry logic."""
    session = requests.Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    
    headers = {'User-Agent': 'RReader/1.0 (https://github.com/yourrepo)'}
    
    try:
        response = session.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()
        return feedparser.parse(response.content)
    except requests.exceptions.RequestException as e:
        # Log error but don't exit
        if log:
            sys.stdout.write(f" - Failed: {e}\n")
        return None

# In get_feed_from_rss(), skip None returns:
d = fetch_feed_with_retry(url, log=log)
if d is None:
    continue
```

**2. Rate limiting**

```python
import time
from threading import Lock

class RateLimiter:
    def __init__(self, calls_per_second=2):
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
        self.lock = Lock()
    
    def wait(self):
        with self.lock:
            elapsed = time.time() - self.last_call
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_call = time.time()

# Add to get_feed_from_rss():
limiter = RateLimiter(calls_per_second=2)
for source, url in urls.items():
    limiter.wait()
    # ... existing fetch logic
```

**3. Conditional fetching with ETags**

```python
# Extend the JSON storage to include fetch metadata:
rslt = {
    "entries": rslt,
    "created_at": int(time.time()),
    "etags": {},  # {url: etag_value}
    "last_modified": {}  # {url: last_modified_value}
}

# Before fetching, load previous metadata:
metadata_file = os.path.join(p["path_data"], f"rss_{category}.json")
previous_etags = {}
if os.path.exists(metadata_file):
    with open(metadata_file, 'r') as f:
        old_data = json.load(f)
        previous_etags = old_data.get("etags", {})

# Add conditional headers to fetch:
headers = {'User-Agent': '...'}
if url in previous_etags:
    headers['If-None-Match'] = previous_etags[url]

response = session.get(url, headers=headers, timeout=timeout)
if response.status_code == 304:
    # Not modified, reuse cached entries
    continue

# Save ETag for next fetch:
rslt["etags"][url] = response.headers.get('ETag', '')
```

### Important Fixes

**4. Configuration validation**

```python
import jsonschema

FEED_CONFIG_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {
                        ".*": {"type": "string", "format": "uri"}
                    }
                },
                "show_author": {"type": "boolean"}
            }
        }
    }
}

def load_and_validate_config(path):
    with open(path, 'r') as fp:
        config = json.load(fp)
    try:
        jsonschema.validate(config, FEED_CONFIG_SCHEMA)
        return config
    except jsonschema.ValidationError as e:
        sys.exit(f"Invalid feeds.json: {e.message}")
```

**5. Fix ID collisions**

```python
# Replace timestamp-only ID with composite key:
entry_id = f"{ts}_{hash(feed.link) % 10000:04d}"

# Or use a counter for same-second entries:
seen_ids = set()
for feed in d.entries:
    # ... existing parsing ...
    entry_id = ts
    counter = 0
    while entry_id in seen_ids:
        entry_id = f"{ts}_{counter}"
        counter += 1
    seen_ids.add(entry_id)
    entries["id"] = entry_id
```

**6. Structured logging**

```python
import logging

# Replace print statements with:
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('rreader')

# Usage:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}: {e}")
logger.debug(f"Parsed {len(d.entries)} entries from {source}")
```

**7. Config update strategy**

```python
# Add version field to feeds.json:
{
    "_version": 2,
    "tech": {"feeds": {...}}
}

# On load, compare versions and prompt for merge:
if bundled["_version"] > user.get("_version", 1):
    print("New feed configuration available. Update? (y/n)")
    if input().lower() == 'y':
        # Deep merge logic here
```

### Nice-to-Have Improvements

**8. Content cleaning**

```python
import html
import re

def clean_title(title):
    # Decode HTML entities
    title = html.unescape(title)
    # Remove extra whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    # Truncate if too long
    if len(title) > 200:
        title = title[:197] + '...'
    return title

entries["title"] = clean_title(feed.title)
```

**9. Feed metadata tracking**

```python
# Add to per-category JSON:
{
    "entries": [...],
    "metadata": {
        "last_fetch_time": timestamp,
        "last_fetch_status": "success|error",
        "feed_health": {
            url: {
                "consecutive_failures": 0,
                "last_success": timestamp,
                "avg_entry_count": 15
            }
        }
    }
}
```

**10. Async fetching**

```python
import asyncio
import aiohttp

async def fetch_all_feeds(urls):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_feed_async(session, url) for url in urls.values()]
        return await asyncio.gather(*tasks, return_exceptions=True)

# Replace the for-loop in get_feed_from_rss() with:
results = asyncio.run(fetch_all_feeds(urls))
```

---

**Priority order for implementation:**
1. Error handling (#1) – prevents catastrophic failures
2. Rate limiting (#2) – prevents being blocked by servers
3. Conditional fetching (#3) – reduces bandwidth and improves speed
4. Config validation (#4) – prevents silent misconfigurations
5. ID collisions (#5) – prevents data loss
6. Remaining items as time permits