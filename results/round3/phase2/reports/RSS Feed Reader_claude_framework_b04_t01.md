# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed parsing and aggregation**: Downloads and parses multiple RSS/Atom feeds using `feedparser`, extracting title, link, publication date, and author information.

2. **Multi-category support**: Organizes feeds into categories defined in a JSON configuration file (`feeds.json`).

3. **Timestamp normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9) and formats them as relative time strings ("HH:MM" for today, "Mon DD, HH:MM" otherwise).

4. **Deduplication by timestamp**: Uses timestamp as ID to prevent duplicate entries from the same feed within a single fetch cycle.

5. **Persistent storage**: Saves aggregated results to per-category JSON files (`rss_{category}.json`) in `~/.rreader/`.

6. **Configuration management**: 
   - Bundles default feeds in the package
   - Copies bundled config to user directory on first run
   - Merges new categories from bundled config into existing user config

7. **Optional per-category author display**: Configurable `show_author` flag to show feed source name vs. entry author.

8. **Sorted output**: Entries sorted by timestamp (newest first).

9. **Command-line interface**: Can update all categories or target a specific one.

## Triage

### Critical Gaps

1. **No error recovery or logging** (Severity: High)
   - Silent failures in individual feeds break the entire fetch
   - No visibility into which feeds succeeded/failed
   - No retry mechanism for transient failures

2. **Missing data validation** (Severity: High)
   - No validation of feed JSON structure
   - No handling of malformed URLs
   - No sanitization of feed content (potential XSS if rendered in HTML)

3. **No rate limiting or politeness** (Severity: High)
   - Hammers all feeds simultaneously
   - No User-Agent header
   - No respect for HTTP cache headers or ETags
   - Could trigger rate limits or bans

4. **Duplicate detection is flawed** (Severity: Medium)
   - Only deduplicates within a single fetch using timestamp as ID
   - Feeds with same publication timestamp collide
   - Across-fetch duplicates accumulate in storage

### Important Missing Features

5. **No incremental updates** (Severity: Medium)
   - Re-fetches all entries every time
   - No tracking of "last seen" entry
   - Wastes bandwidth and processing

6. **No feed health monitoring** (Severity: Medium)
   - Doesn't track consecutive failures
   - Doesn't mark feeds as defunct
   - No stale data detection

7. **Inadequate timezone handling** (Severity: Low)
   - Hardcoded KST timezone
   - Falls back silently when timezone parsing fails
   - No handling of timezone-naive timestamps

8. **Poor concurrency** (Severity: Low)
   - Sequential processing is slow for many feeds
   - No async/parallel fetching

### Operational Gaps

9. **No metrics or observability** (Severity: Medium)
   - Can't track fetch latency
   - Can't measure feed reliability
   - No alerting capability

10. **Missing CLI conveniences** (Severity: Low)
    - No `--dry-run` mode
    - No `--verbose` flag separate from logging
    - No way to list categories without fetching

## Plan

### 1. Error Recovery and Logging

**Changes needed:**

```python
import logging
from typing import Dict, List, Optional

# Add to do() function:
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def fetch_feed_with_retry(url: str, max_retries: int = 3) -> Optional[feedparser.FeedParserDict]:
    """Fetch a single feed with exponential backoff."""
    for attempt in range(max_retries):
        try:
            logger.info(f"Fetching {url} (attempt {attempt + 1})")
            d = feedparser.parse(url)
            if d.bozo:  # feedparser's error flag
                logger.warning(f"Feed parse warning for {url}: {d.bozo_exception}")
            return d
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # exponential backoff
    return None

# In get_feed_from_rss(), replace feedparser.parse() with:
d = fetch_feed_with_retry(url)
if d is None:
    logger.error(f"All retries failed for {source}: {url}")
    continue  # Skip this feed but continue with others
```

### 2. Data Validation

**Changes needed:**

```python
from urllib.parse import urlparse
import html

def validate_feed_config(feeds: Dict) -> List[str]:
    """Validate feed configuration structure. Returns list of errors."""
    errors = []
    for category, data in feeds.items():
        if not isinstance(data, dict):
            errors.append(f"Category {category} must be a dict")
            continue
        if "feeds" not in data:
            errors.append(f"Category {category} missing 'feeds' key")
            continue
        for source, url in data["feeds"].items():
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                errors.append(f"Invalid URL for {source} in {category}: {url}")
    return errors

# Add to entry processing:
def sanitize_entry(entry: dict) -> dict:
    """Sanitize feed entry data."""
    entry["title"] = html.escape(entry["title"])
    # Validate URL
    parsed = urlparse(entry["url"])
    if not parsed.scheme:
        entry["url"] = "about:blank"
    return entry

# In get_feed_from_rss(), after building entries dict:
entries = sanitize_entry(entries)
```

### 3. Rate Limiting and HTTP Politeness

**Changes needed:**

```python
import requests
from time import sleep

def fetch_feed_politely(url: str, user_agent: str = "rreader/1.0") -> Optional[feedparser.FeedParserDict]:
    """Fetch with proper headers and cache support."""
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }
    
    # Load ETag/Last-Modified from cache if exists
    cache_file = os.path.join(p["path_data"], f"cache_{hash(url)}.json")
    cache = {}
    if os.path.exists(cache_file):
        with open(cache_file) as f:
            cache = json.load(f)
        if "etag" in cache:
            headers["If-None-Match"] = cache["etag"]
        if "last_modified" in cache:
            headers["If-Modified-Since"] = cache["last_modified"]
    
    response = requests.get(url, headers=headers, timeout=30)
    
    if response.status_code == 304:  # Not Modified
        logger.info(f"Feed unchanged: {url}")
        return None
    
    # Save cache headers
    if "etag" in response.headers:
        cache["etag"] = response.headers["etag"]
    if "last-modified" in response.headers:
        cache["last_modified"] = response.headers["last-modified"]
    with open(cache_file, "w") as f:
        json.dump(cache, f)
    
    sleep(0.5)  # Basic rate limiting
    
    return feedparser.parse(response.content)
```

### 4. Fix Duplicate Detection

**Changes needed:**

```python
import hashlib

def generate_entry_id(entry) -> str:
    """Generate stable ID from entry content."""
    # Use URL + title as unique identifier
    content = f"{entry.link}|{entry.title}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]

# In get_feed_from_rss(), replace:
# entries = {"id": ts, ...}
# with:
entries = {
    "id": generate_entry_id(feed),
    "timestamp": ts,
    # ...
}

# Load existing entries to check for duplicates:
existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
existing_ids = set()
if os.path.exists(existing_file):
    with open(existing_file) as f:
        existing_data = json.load(f)
        existing_ids = {e["id"] for e in existing_data.get("entries", [])}

# Skip if already seen:
if entries["id"] in existing_ids:
    continue
```

### 5. Incremental Updates

**Changes needed:**

```python
def get_last_fetch_time(category: str) -> Optional[int]:
    """Get timestamp of last successful fetch."""
    state_file = os.path.join(p["path_data"], f"state_{category}.json")
    if os.path.exists(state_file):
        with open(state_file) as f:
            return json.load(f).get("last_fetch")
    return None

def save_fetch_state(category: str, timestamp: int):
    """Save fetch state."""
    state_file = os.path.join(p["path_data"], f"state_{category}.json")
    with open(state_file, "w") as f:
        json.dump({"last_fetch": timestamp}, f)

# In get_feed_from_rss():
last_fetch = get_last_fetch_time(category)

# When processing entries:
if last_fetch and ts <= last_fetch:
    continue  # Skip older entries

# After successful fetch:
save_fetch_state(category, int(time.time()))
```

### 6. Feed Health Monitoring

**Changes needed:**

```python
def update_feed_health(source: str, success: bool):
    """Track feed reliability."""
    health_file = os.path.join(p["path_data"], "feed_health.json")
    health = {}
    if os.path.exists(health_file):
        with open(health_file) as f:
            health = json.load(f)
    
    if source not in health:
        health[source] = {"failures": 0, "last_success": None, "total_fetches": 0}
    
    health[source]["total_fetches"] += 1
    if success:
        health[source]["failures"] = 0
        health[source]["last_success"] = int(time.time())
    else:
        health[source]["failures"] += 1
    
    # Mark as defunct after 10 consecutive failures
    if health[source]["failures"] >= 10:
        health[source]["defunct"] = True
        logger.warning(f"Feed marked defunct: {source}")
    
    with open(health_file, "w") as f:
        json.dump(health, f, indent=2)

# Check before fetching:
def should_fetch_feed(source: str) -> bool:
    health_file = os.path.join(p["path_data"], "feed_health.json")
    if os.path.exists(health_file):
        with open(health_file) as f:
            health = json.load(f)
            return not health.get(source, {}).get("defunct", False)
    return True
```

### 7. Improved Timezone Handling

**Changes needed:**

```python
from dateutil import tz

# Replace hardcoded TIMEZONE with:
def get_user_timezone():
    """Detect user timezone or fall back to UTC."""
    try:
        return tz.tzlocal()
    except:
        logger.warning("Could not detect timezone, using UTC")
        return datetime.timezone.utc

TIMEZONE = get_user_timezone()

# When parsing timestamps:
def safe_parse_time(entry) -> Optional[int]:
    """Parse entry time with fallback."""
    parsed_time = getattr(entry, 'published_parsed', None) or getattr(entry, 'updated_parsed', None)
    if not parsed_time:
        return None
    try:
        return int(time.mktime(parsed_time))
    except (ValueError, OverflowError):
        logger.warning(f"Invalid timestamp in entry: {entry.get('title', 'unknown')}")
        return None
```

### 8. Add Concurrency

**Changes needed:**

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_all_feeds_parallel(urls: Dict[str, str], max_workers: int = 5) -> Dict:
    """Fetch multiple feeds in parallel."""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_source = {
            executor.submit(fetch_feed_politely, url): (source, url)
            for source, url in urls.items()
        }
        for future in as_completed(future_to_source):
            source, url = future_to_source[future]
            try:
                results[source] = future.result()
            except Exception as e:
                logger.error(f"Failed to fetch {source}: {e}")
    return results
```

### 9. Metrics and Observability

**Changes needed:**

```python
import json
from dataclasses import dataclass, asdict
from datetime import datetime

@dataclass
class FetchMetrics:
    category: str
    started_at: str
    duration_seconds: float
    feeds_attempted: int
    feeds_succeeded: int
    entries_new: int
    entries_duplicate: int
    errors: List[str]

def record_metrics(metrics: FetchMetrics):
    """Append metrics to log file."""
    metrics_file = os.path.join(p["path_data"], "metrics.jsonl")
    with open(metrics_file, "a") as f:
        f.write(json.dumps(asdict(metrics)) + "\n")

# Wrap get_feed_from_rss():
start = time.time()
metrics = FetchMetrics(
    category=category,
    started_at=datetime.now().isoformat(),
    duration_seconds=0,
    feeds_attempted=len(urls),
    feeds_succeeded=0,
    entries_new=0,
    entries_duplicate=0,
    errors=[]
)
# ... fetch logic ...
metrics.duration_seconds = time.time() - start
record_metrics(metrics)
```

### 10. CLI Improvements

**Changes needed:**

```python
import argparse

def main():
    parser = argparse.ArgumentParser(description="RSS feed aggregator")
    parser.add_argument("--category", help="Fetch specific category only")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fetched")
    parser.add_argument("--list-categories", action="store_true", help="List available categories")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.list_categories:
        with open(FEEDS_FILE_NAME) as f:
            categories = json.load(f).keys()
        print("\n".join(sorted(categories)))
        return
    
    if args.dry_run:
        logger.info("DRY RUN: No feeds will be fetched")
        # Show what would be done
        return
    
    do(target_category=args.category, log=args.verbose)

if __name__ == "__main__":
    main()
```

---

**Implementation Priority:**

1. Error recovery (#1) - prevents cascading failures
2. Rate limiting (#3) - prevents service disruption
3. Duplicate detection (#4) - prevents data corruption
4. Data validation (#2) - prevents security issues
5. Incremental updates (#5) - improves performance
6. Health monitoring (#6) - improves reliability
7. Metrics (#9) - enables debugging
8. CLI improvements (#10) - improves usability
9. Concurrency (#8) - improves performance
10. Timezone handling (#7) - improves correctness