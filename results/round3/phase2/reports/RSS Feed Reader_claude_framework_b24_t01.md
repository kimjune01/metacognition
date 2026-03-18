# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing**: Downloads and parses RSS/Atom feeds using `feedparser`, handling both `published_parsed` and `updated_parsed` timestamps.

2. **Multi-source aggregation**: Reads feed URLs from a JSON configuration file (`feeds.json`) organized by categories, each containing multiple sources.

3. **Data normalization**: Converts heterogeneous RSS entries into a uniform structure with `id`, `sourceName`, `pubDate`, `timestamp`, `url`, and `title`.

4. **Deduplication**: Uses timestamp as primary key to prevent duplicate entries from the same feed.

5. **Time localization**: Converts UTC timestamps to a configured timezone (KST/UTC+9) with human-readable formatting (today: "HH:MM", older: "MMM DD, HH:MM").

6. **Persistent storage**: Writes aggregated feeds to category-specific JSON files (`rss_{category}.json`) in `~/.rreader/`.

7. **Configuration management**: Automatically copies bundled `feeds.json` on first run and merges new categories from updates without overwriting user modifications.

8. **Selective updates**: Supports refreshing a single category via `target_category` parameter or all categories when called without arguments.

9. **Optional logging**: Provides progress output when `log=True`.

10. **Graceful degradation**: Continues processing remaining feeds if one fails (catches exceptions per-feed and per-entry).

---

## Triage

### Critical Gaps

1. **No error handling for write operations** (Severity: High)
   - File writes can fail silently due to permissions, disk space, or corruption
   - No atomic writes; partial JSON can be left on disk

2. **Missing feed validation** (Severity: High)
   - Malformed URLs accepted without validation
   - No SSL certificate verification settings
   - No timeout configuration for network requests

3. **No rate limiting** (Severity: High)
   - Consecutive requests to the same domain can trigger 429/blocking
   - No User-Agent header set (some feeds block default feedparser UA)

### Important Gaps

4. **Timestamp collision handling** (Severity: Medium)
   - Two entries with identical second-precision timestamps overwrite each other
   - RSS feeds from high-volume sources (Twitter bridges, news sites) commonly have multiple entries per second

5. **No cache invalidation strategy** (Severity: Medium)
   - `created_at` timestamp written but never read
   - Old data never expires; stale feeds persist indefinitely

6. **Limited error reporting** (Severity: Medium)
   - `sys.exit(0)` on parse failure hides the error
   - No logging of which feeds failed or why
   - Silent `continue` on timestamp parsing errors loses data

7. **Configuration drift detection** (Severity: Medium)
   - Updates to bundled feeds only add categories, never update URLs within existing categories
   - No mechanism to notify users of upstream feed URL changes

### Minor Gaps

8. **No entry content preservation** (Severity: Low)
   - Only stores title/link; `summary`/`content` fields discarded
   - No media attachment handling (podcasts, images)

9. **Inflexible timezone configuration** (Severity: Low)
   - Hardcoded to KST; changing requires code modification
   - No per-category timezone support

10. **No retry logic** (Severity: Low)
    - Transient network failures cause permanent data loss for that refresh cycle

---

## Plan

### 1. Error Handling for Write Operations

**Change**: Wrap file writes in try-except, use atomic writes via temp file + rename.

```python
def safe_write_json(filepath, data):
    temp_path = filepath + '.tmp'
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(temp_path, filepath)  # Atomic on POSIX
    except (IOError, OSError) as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise Exception(f"Failed to write {filepath}: {e}")
```

Replace all `json.dumps()` + `f.write()` calls with `safe_write_json()`.

---

### 2. Feed Validation

**Change**: Add URL validation and HTTP configuration.

```python
import urllib.parse
from urllib.request import Request

def validate_feed_url(url):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f"Invalid scheme: {url}")
    return url

def fetch_feed(url, timeout=30):
    validate_feed_url(url)
    headers = {'User-Agent': 'rreader/1.0 (feedparser)'}
    req = Request(url, headers=headers)
    return feedparser.parse(req, request_headers=headers, timeout=timeout)
```

Replace `feedparser.parse(url)` with `fetch_feed(url)`.

---

### 3. Rate Limiting

**Change**: Track request times per domain, enforce minimum delay.

```python
from collections import defaultdict
from urllib.parse import urlparse

_last_request = defaultdict(float)
MIN_DELAY = 1.0  # seconds between requests to same domain

def rate_limited_fetch(url, timeout=30):
    domain = urlparse(url).netloc
    elapsed = time.time() - _last_request[domain]
    if elapsed < MIN_DELAY:
        time.sleep(MIN_DELAY - elapsed)
    
    _last_request[domain] = time.time()
    return fetch_feed(url, timeout)
```

Replace `fetch_feed()` calls with `rate_limited_fetch()`.

---

### 4. Timestamp Collision Handling

**Change**: Use composite key: timestamp + URL hash.

```python
import hashlib

def generate_entry_id(timestamp, url):
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{timestamp}_{url_hash}"

# In get_feed_from_rss():
entries["id"] = generate_entry_id(ts, feed.link)
```

Maintains chronological sorting while preventing collisions.

---

### 5. Cache Invalidation Strategy

**Change**: Check `created_at` on read; regenerate if stale.

```python
MAX_CACHE_AGE = 3600  # 1 hour in seconds

def load_cached_feed(category):
    filepath = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(filepath):
        return None
    
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    if time.time() - data.get('created_at', 0) > MAX_CACHE_AGE:
        return None  # Treat as cache miss
    
    return data
```

Add `load_cached_feed()` check before calling `get_feed_from_rss()`.

---

### 6. Error Reporting

**Change**: Replace `sys.exit(0)` with logged exceptions; collect errors.

```python
import logging

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    errors = []
    
    for source, url in urls.items():
        try:
            # ... fetch logic ...
        except Exception as e:
            msg = f"Failed to fetch {url}: {e}"
            logger.error(msg)
            errors.append({"source": source, "url": url, "error": str(e)})
            continue
    
    # ... existing code ...
    
    rslt["errors"] = errors  # Include in output JSON
    return rslt
```

Remove all `sys.exit()` calls; log instead.

---

### 7. Configuration Drift Detection

**Change**: Compare bundled vs. user feeds; notify on URL changes.

```python
def detect_feed_updates():
    with open(bundled_feeds_file) as f:
        bundled = json.load(f)
    with open(FEEDS_FILE_NAME) as f:
        user = json.load(f)
    
    updates = {}
    for cat, data in bundled.items():
        if cat not in user:
            continue
        for source, url in data['feeds'].items():
            if source in user[cat]['feeds'] and user[cat]['feeds'][source] != url:
                updates[f"{cat}/{source}"] = (user[cat]['feeds'][source], url)
    
    return updates  # Returns {key: (old_url, new_url)}
```

Call `detect_feed_updates()` on startup; log warnings for changed URLs.

---

### 8. Entry Content Preservation

**Change**: Add optional `content` and `media` fields.

```python
entries = {
    "id": generate_entry_id(ts, feed.link),
    "sourceName": author,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
    "summary": getattr(feed, 'summary', None),
    "content": getattr(feed, 'content', [{}])[0].get('value', None),
    "media": [enc.get('href') for enc in getattr(feed, 'enclosures', [])]
}
```

Filter out `None` values before writing JSON to keep size down.

---

### 9. Flexible Timezone Configuration

**Change**: Move timezone to `feeds.json` per-category or global.

```python
# In feeds.json:
{
    "_global": {"timezone": "Asia/Seoul"},
    "tech": {
        "feeds": {...},
        "timezone": "America/New_York"  # Optional override
    }
}

# In config.py:
from zoneinfo import ZoneInfo

def get_timezone(category_config, global_config):
    tz_name = category_config.get('timezone', global_config.get('timezone', 'UTC'))
    return ZoneInfo(tz_name)
```

Pass timezone to `get_feed_from_rss()` as parameter.

---

### 10. Retry Logic

**Change**: Add exponential backoff for transient failures.

```python
def fetch_with_retry(url, max_retries=3):
    for attempt in range(max_retries):
        try:
            return rate_limited_fetch(url)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = 2 ** attempt  # 1s, 2s, 4s
            logger.warning(f"Retry {attempt+1}/{max_retries} for {url} after {wait}s: {e}")
            time.sleep(wait)
```

Replace direct `rate_limited_fetch()` calls with `fetch_with_retry()`.