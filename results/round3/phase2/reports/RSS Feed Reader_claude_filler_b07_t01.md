# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS/Atom feeds using the `feedparser` library from multiple sources defined in a JSON configuration file.

2. **Feed Configuration Management**: 
   - Stores feed sources in a `feeds.json` file organized by categories
   - Automatically creates user config from bundled defaults on first run
   - Merges new categories from bundled feeds into existing user configuration

3. **Data Extraction**: Extracts key feed entry fields including:
   - Publication timestamp (with fallback to updated time)
   - Title and URL
   - Source/author name
   - Formatted publication date

4. **Time Handling**: 
   - Converts feed timestamps to configured timezone (currently hardcoded to UTC+9/KST)
   - Formats dates as "HH:MM" for today's entries, "MMM DD, HH:MM" for older entries

5. **Data Storage**: 
   - Saves parsed feeds as JSON files (`rss_{category}.json`) in a data directory
   - Deduplicates entries by timestamp
   - Sorts entries by timestamp (newest first)
   - Stores creation timestamp for cache staleness checking

6. **Directory Management**: Automatically creates data directory (`~/.rreader/`) if it doesn't exist

7. **Selective Processing**: Can process either all feed categories or a single target category

8. **Basic Logging**: Optional console output during feed fetching

## Triage

### Critical Gaps

1. **Error Handling** - The system silently fails or exits on errors, providing no useful diagnostics or recovery
2. **Network Resilience** - No timeout configuration, retry logic, or connection pooling
3. **Configuration Validation** - No validation of feeds.json structure or URL formats

### Important Gaps

4. **Feed Refresh Strategy** - No intelligent caching; unclear when feeds should be re-fetched
5. **Rate Limiting** - No throttling between requests; could overwhelm servers or get blocked
6. **Logging Infrastructure** - Only basic stdout messages; no proper logging framework or levels
7. **User Interface** - No way to view or interact with fetched feeds
8. **Feed Management** - No CLI or API to add/remove/modify feeds

### Nice-to-Have Gaps

9. **Performance Optimization** - Sequential processing; no concurrency for multiple feeds
10. **Data Retention** - No cleanup of old feed data; storage grows indefinitely
11. **Feed Discovery** - No auto-detection of feed URLs from websites
12. **Content Processing** - No sanitization, summary extraction, or content cleaning
13. **Testing** - No unit tests, integration tests, or test fixtures
14. **Documentation** - No docstrings, usage examples, or API documentation

## Plan

### 1. Error Handling

**Changes needed:**
- Replace bare `except:` clauses with specific exception types
- Add try-except blocks around individual feed processing to prevent one failure from stopping all feeds
- Return error status codes and messages instead of `sys.exit()`
- Store failed feeds in the output JSON with error details

```python
# Replace:
except:
    sys.exit(" - Failed\n" if log else 0)

# With:
except (feedparser.CharacterEncodingOverride, feedparser.NonXMLContentType) as e:
    error_msg = f"Feed parse error: {str(e)}"
    if log:
        sys.stderr.write(f" - {error_msg}\n")
    # Add to error list in results
    continue
except requests.exceptions.RequestException as e:
    error_msg = f"Network error: {str(e)}"
    # Similar handling
```

### 2. Network Resilience

**Changes needed:**
- Add `requests` library with configurable timeouts
- Implement exponential backoff retry logic (3 retries with 1s, 2s, 4s delays)
- Add connection timeout (5s) and read timeout (30s) parameters
- Use requests Session for connection pooling

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def get_session():
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

# In get_feed_from_rss:
session = get_session()
response = session.get(url, timeout=(5, 30))
d = feedparser.parse(response.content)
```

### 3. Configuration Validation

**Changes needed:**
- Create a JSON schema for feeds.json structure
- Validate on load using `jsonschema` library
- Check URLs are well-formed with `urllib.parse`
- Provide clear error messages for malformed configurations

```python
from jsonschema import validate, ValidationError
import urllib.parse

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {"type": "object"},
                "show_author": {"type": "boolean"}
            }
        }
    }
}

def load_and_validate_feeds():
    with open(FEEDS_FILE_NAME, "r") as fp:
        feeds = json.load(fp)
    try:
        validate(instance=feeds, schema=FEEDS_SCHEMA)
    except ValidationError as e:
        raise ValueError(f"Invalid feeds.json: {e.message}")
    # Validate URLs
    for category, data in feeds.items():
        for source, url in data["feeds"].items():
            parsed = urllib.parse.urlparse(url)
            if not parsed.scheme in ['http', 'https']:
                raise ValueError(f"Invalid URL for {source}: {url}")
    return feeds
```

### 4. Feed Refresh Strategy

**Changes needed:**
- Add `ttl` (time-to-live) field to each category in feeds.json (default 3600 seconds)
- Check file modification time and `created_at` timestamp before fetching
- Skip fetch if data is fresh enough
- Add `--force` flag to override cache

```python
def should_refresh(category, ttl=3600):
    filepath = os.path.join(p["path_data"], f"rss_{category}.json")
    if not os.path.exists(filepath):
        return True
    with open(filepath, "r") as f:
        data = json.load(f)
    age = int(time.time()) - data.get("created_at", 0)
    return age > ttl

# In do():
if not force and not should_refresh(category, d.get("ttl", 3600)):
    continue
```

### 5. Rate Limiting

**Changes needed:**
- Add configurable delay between feed requests (default 1 second)
- Use `time.sleep()` between iterations
- Add per-domain rate limiting to avoid hammering single servers

```python
from collections import defaultdict
from time import sleep

last_request_time = defaultdict(float)
MIN_DELAY = 1.0  # seconds between requests to same domain

def rate_limited_fetch(url, session):
    domain = urllib.parse.urlparse(url).netloc
    elapsed = time.time() - last_request_time[domain]
    if elapsed < MIN_DELAY:
        sleep(MIN_DELAY - elapsed)
    response = session.get(url, timeout=(5, 30))
    last_request_time[domain] = time.time()
    return response
```

### 6. Logging Infrastructure

**Changes needed:**
- Replace print statements with Python's `logging` module
- Add log levels: DEBUG, INFO, WARNING, ERROR
- Configure file logging to `~/.rreader/rreader.log`
- Add `--verbose` and `--quiet` flags

```python
import logging

def setup_logging(verbose=False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = setup_logging()
# Replace sys.stdout.write() calls:
logger.info(f"Fetching {url}")
logger.error(f"Failed to fetch {url}: {error}")
```

### 7. User Interface

**Changes needed:**
- Add `list` command to display feeds in terminal
- Create `serve` command to run local web server showing feeds
- Implement basic TUI using `curses` or `rich` library
- Add JSON export functionality

```python
def list_feeds(category=None, limit=20):
    """Display feeds in terminal"""
    from rich.console import Console
    from rich.table import Table
    
    console = Console()
    categories = [category] if category else get_all_categories()
    
    for cat in categories:
        filepath = os.path.join(p["path_data"], f"rss_{cat}.json")
        with open(filepath, "r") as f:
            data = json.load(f)
        
        table = Table(title=f"{cat} Feeds")
        table.add_column("Time", style="cyan")
        table.add_column("Source", style="magenta")
        table.add_column("Title")
        
        for entry in data["entries"][:limit]:
            table.add_row(entry["pubDate"], entry["sourceName"], entry["title"])
        
        console.print(table)
```

### 8. Feed Management

**Changes needed:**
- Add CLI commands: `add`, `remove`, `edit`, `list-sources`
- Implement atomic writes to feeds.json to prevent corruption
- Add interactive mode for adding feeds

```python
import argparse

def add_feed(category, source_name, url):
    """Add a new feed to configuration"""
    feeds = load_and_validate_feeds()
    if category not in feeds:
        feeds[category] = {"feeds": {}, "show_author": False}
    feeds[category]["feeds"][source_name] = url
    
    # Atomic write
    temp_file = FEEDS_FILE_NAME + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as fp:
        json.dump(feeds, fp, indent=4, ensure_ascii=False)
    os.replace(temp_file, FEEDS_FILE_NAME)
    logger.info(f"Added {source_name} to {category}")

def main():
    parser = argparse.ArgumentParser(description="RSS Feed Reader")
    subparsers = parser.add_subparsers(dest="command")
    
    # fetch command
    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--category", help="Specific category to fetch")
    fetch.add_argument("--force", action="store_true", help="Force refresh")
    
    # add command
    add = subparsers.add_parser("add")
    add.add_argument("category")
    add.add_argument("source")
    add.add_argument("url")
    
    args = parser.parse_args()
    # Dispatch to appropriate function
```

### 9. Performance Optimization

**Changes needed:**
- Use `concurrent.futures.ThreadPoolExecutor` for parallel feed fetching
- Add `max_workers` configuration (default 5)
- Maintain thread safety in result aggregation

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_single_feed(source, url, show_author):
    """Fetch single feed - can be run in thread"""
    # Existing feedparser logic here
    return source, entries, errors

def get_feed_from_rss(category, urls, show_author=False, log=False, max_workers=5):
    rslt = {}
    errors = []
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_single_feed, src, url, show_author): src 
            for src, url in urls.items()
        }
        
        for future in as_completed(futures):
            source = futures[future]
            try:
                _, entries, errs = future.result()
                rslt.update(entries)
                errors.extend(errs)
            except Exception as e:
                logger.error(f"Failed to process {source}: {e}")
    # Continue with existing aggregation logic
```

### 10. Data Retention

**Changes needed:**
- Add `max_age_days` configuration per category (default 30 days)
- Implement cleanup function to remove old entries
- Add `max_entries` limit per category
- Run cleanup before writing new data

```python
def cleanup_old_entries(entries, max_age_days=30, max_entries=1000):
    """Remove entries older than max_age_days"""
    cutoff_time = time.time() - (max_age_days * 86400)
    filtered = [e for e in entries if e["timestamp"] > cutoff_time]
    return filtered[:max_entries]  # Also enforce count limit

# In get_feed_from_rss before writing:
rslt["entries"] = cleanup_old_entries(
    rslt["entries"],
    max_age_days=RSS[category].get("max_age_days", 30),
    max_entries=RSS[category].get("max_entries", 1000)
)
```

### 11-14. Additional Enhancements

These lower-priority items would follow similar patterns:

- **Feed Discovery**: Add `feedfinder3` library integration with `discover` command
- **Content Processing**: Use `bleach` for HTML sanitization, `readability` for content extraction
- **Testing**: Create `tests/` directory with pytest fixtures, use `responses` library to mock HTTP
- **Documentation**: Add docstrings following Google style, create `README.md` with examples, use Sphinx for API docs