# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Uses `feedparser` to retrieve and parse RSS/Atom feeds from multiple sources
2. **Multi-Category Support**: Organizes feeds into categories, each containing multiple feed sources
3. **Time Handling**: Converts feed timestamps to local timezone (KST/UTC+9) with intelligent date formatting
4. **Data Persistence**: Stores parsed feed entries as JSON files in `~/.rreader/` directory
5. **Deduplication**: Uses timestamp-based IDs to prevent duplicate entries within a single fetch
6. **Configuration Management**: 
   - Bundles default `feeds.json` with the package
   - Copies bundled config to user directory on first run
   - Merges new categories from bundled config into existing user config
7. **Flexible Display**: Supports `show_author` flag per category to display either source name or article author
8. **Sorting**: Orders entries by timestamp (newest first)
9. **Selective Updates**: Can update all categories or target a specific category
10. **Basic Logging**: Optional progress output during feed fetching

## Triage

### Critical Gaps (Must-Have for Production)

1. **No Error Handling or Recovery**
   - Silent failures on network errors
   - No retry logic
   - Bare `except` clauses swallow all exceptions
   - Missing feed sources silently ignored

2. **No Validation or Sanitization**
   - Feed data not validated before storage
   - No HTML sanitization (XSS vulnerability if displayed in web context)
   - No URL validation
   - Malformed feeds could break the system

3. **Missing Concurrency/Performance**
   - Sequential feed fetching is slow (could take minutes for many feeds)
   - No timeout handling (hung connections block indefinitely)
   - No caching strategy for expensive operations

### High Priority (Should-Have)

4. **Insufficient Configuration Validation**
   - No schema validation for `feeds.json`
   - Missing feeds cause category failure
   - No validation of category structure

5. **Limited Observability**
   - No proper logging framework (uses print to stdout)
   - No metrics or monitoring
   - No audit trail of fetch operations
   - Can't diagnose why feeds fail

6. **Data Management Issues**
   - No maximum entry limit (files grow unbounded)
   - No cleanup of old entries
   - No compression or archival
   - No database option for larger deployments

7. **Authentication Not Supported**
   - Cannot handle authenticated feeds
   - No proxy support
   - No custom headers

### Medium Priority (Nice-to-Have)

8. **User Experience Limitations**
   - No CLI interface for common operations
   - Can't add/remove feeds without editing JSON
   - No feed health checking
   - No notification of new entries

9. **Testing Infrastructure**
   - No unit tests
   - No integration tests
   - No mocking for network operations

10. **Documentation**
    - No docstrings
    - No usage examples
    - No configuration guide

## Plan

### 1. Error Handling and Recovery

**Changes needed:**
```python
# Replace bare except clauses with specific exceptions
import requests
from requests.exceptions import RequestException, Timeout

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    failed_sources = []
    
    for source, url in urls.items():
        retry_count = 0
        max_retries = 3
        
        while retry_count < max_retries:
            try:
                if log:
                    sys.stdout.write(f"- {url} (attempt {retry_count + 1})")
                
                # Add timeout
                d = feedparser.parse(url, timeout=30)
                
                # Validate feed was actually retrieved
                if hasattr(d, 'bozo_exception'):
                    raise ValueError(f"Malformed feed: {d.bozo_exception}")
                
                if log:
                    sys.stdout.write(" - Done\n")
                break
                
            except (RequestException, Timeout) as e:
                retry_count += 1
                if retry_count >= max_retries:
                    failed_sources.append((source, url, str(e)))
                    if log:
                        sys.stdout.write(f" - Failed after {max_retries} attempts: {e}\n")
                else:
                    time.sleep(2 ** retry_count)  # Exponential backoff
            except Exception as e:
                failed_sources.append((source, url, str(e)))
                if log:
                    sys.stdout.write(f" - Failed: {e}\n")
                break
    
    # Store failed sources for reporting
    rslt["failed_sources"] = failed_sources
    return rslt
```

### 2. Validation and Sanitization

**Changes needed:**
```python
import bleach
from urllib.parse import urlparse

def validate_url(url):
    """Validate URL is well-formed and uses allowed schemes."""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False

def sanitize_entry(feed):
    """Sanitize feed entry data."""
    allowed_tags = ['p', 'br', 'strong', 'em', 'a']
    allowed_attrs = {'a': ['href']}
    
    return {
        'title': bleach.clean(feed.title, tags=[], strip=True),
        'link': feed.link if validate_url(feed.link) else None,
        'summary': bleach.clean(
            getattr(feed, 'summary', ''),
            tags=allowed_tags,
            attributes=allowed_attrs,
            strip=True
        )
    }

# In get_feed_from_rss, validate before storing:
if not validate_url(url):
    if log:
        sys.stdout.write(f" - Invalid URL: {url}\n")
    continue

sanitized = sanitize_entry(feed)
if not sanitized['link']:
    continue  # Skip entries with invalid links
```

### 3. Concurrency and Performance

**Changes needed:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed
import functools

def fetch_single_feed(source, url, timeout=30):
    """Fetch a single feed with timeout."""
    try:
        return source, feedparser.parse(url), None
    except Exception as e:
        return source, None, e

def get_feed_from_rss(category, urls, show_author=False, log=False, max_workers=5):
    rslt = {}
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all feed fetches
        future_to_source = {
            executor.submit(fetch_single_feed, source, url): (source, url)
            for source, url in urls.items()
        }
        
        # Process as they complete
        for future in as_completed(future_to_source):
            source, url = future_to_source[future]
            source_name, feed_data, error = future.result()
            
            if error:
                if log:
                    sys.stdout.write(f"- {url} - Failed: {error}\n")
                continue
            
            # Process feed_data...
```

### 4. Configuration Validation

**Changes needed:**
```python
import jsonschema

FEEDS_SCHEMA = {
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

def load_and_validate_feeds():
    """Load feeds.json with validation."""
    with open(FEEDS_FILE_NAME, "r") as fp:
        feeds = json.load(fp)
    
    try:
        jsonschema.validate(instance=feeds, schema=FEEDS_SCHEMA)
        return feeds
    except jsonschema.ValidationError as e:
        raise ValueError(f"Invalid feeds.json: {e.message}")
```

### 5. Proper Logging

**Changes needed:**
```python
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(p["path_data"], "rreader.log")),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Replace sys.stdout.write calls:
logger.info(f"Fetching feed from {url}")
logger.error(f"Failed to fetch {url}: {e}")
logger.warning(f"Malformed entry in {source}, skipping")
```

### 6. Data Management

**Changes needed:**
```python
MAX_ENTRIES_PER_CATEGORY = 1000
MAX_AGE_DAYS = 30

def prune_old_entries(entries, max_entries=MAX_ENTRIES_PER_CATEGORY, max_age_days=MAX_AGE_DAYS):
    """Remove old entries to prevent unbounded growth."""
    cutoff_timestamp = int(time.time()) - (max_age_days * 86400)
    
    # Filter by age
    recent = [e for e in entries if e.get('timestamp', 0) > cutoff_timestamp]
    
    # Limit by count
    return recent[:max_entries]

# In get_feed_from_rss:
rslt["entries"] = prune_old_entries(rslt["entries"])
```

### 7. Authentication Support

**Changes needed:**
```python
def get_feed_from_rss(category, urls, auth_config=None, show_author=False, log=False):
    """
    auth_config: dict mapping source names to auth credentials
    Example: {"TechBlog": {"username": "user", "password": "pass"}}
    """
    for source, url in urls.items():
        headers = {}
        auth = None
        
        if auth_config and source in auth_config:
            creds = auth_config[source]
            if 'api_key' in creds:
                headers['Authorization'] = f"Bearer {creds['api_key']}"
            elif 'username' in creds and 'password' in creds:
                auth = (creds['username'], creds['password'])
        
        # Pass to feedparser (may need requests pre-fetch for complex auth)
```

### 8. CLI Interface

**Changes needed:**
```python
import argparse

def main():
    parser = argparse.ArgumentParser(description='RSS Feed Reader')
    parser.add_argument('--category', help='Update specific category')
    parser.add_argument('--add-feed', nargs=3, metavar=('CATEGORY', 'NAME', 'URL'),
                       help='Add a new feed')
    parser.add_argument('--list-categories', action='store_true',
                       help='List all categories')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.add_feed:
        add_feed(args.add_feed[0], args.add_feed[1], args.add_feed[2])
    elif args.list_categories:
        list_categories()
    else:
        do(target_category=args.category, log=args.verbose)

def add_feed(category, name, url):
    """Add a feed to configuration."""
    with open(FEEDS_FILE_NAME, 'r') as fp:
        feeds = json.load(fp)
    
    if category not in feeds:
        feeds[category] = {"feeds": {}, "show_author": False}
    
    feeds[category]["feeds"][name] = url
    
    with open(FEEDS_FILE_NAME, 'w') as fp:
        json.dump(feeds, fp, indent=4, ensure_ascii=False)
    
    print(f"Added {name} to {category}")
```

### 9. Testing Infrastructure

**Changes needed:**
```python
# tests/test_feed_parser.py
import unittest
from unittest.mock import patch, MagicMock
import feedparser

class TestFeedParser(unittest.TestCase):
    
    @patch('feedparser.parse')
    def test_successful_feed_fetch(self, mock_parse):
        """Test successful feed parsing."""
        mock_entry = MagicMock()
        mock_entry.title = "Test Article"
        mock_entry.link = "https://example.com/article"
        mock_entry.published_parsed = time.gmtime()
        
        mock_parse.return_value.entries = [mock_entry]
        
        result = get_feed_from_rss('test', {'source': 'http://example.com/feed'})
        
        self.assertEqual(len(result['entries']), 1)
        self.assertEqual(result['entries'][0]['title'], 'Test Article')
    
    def test_invalid_url_handling(self):
        """Test handling of invalid URLs."""
        result = get_feed_from_rss('test', {'bad': 'not-a-url'})
        self.assertIn('failed_sources', result)
```

### 10. Documentation

**Changes needed:**
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    """
    Fetch and parse RSS feeds for a given category.
    
    Args:
        category (str): Category name for organizing feeds
        urls (dict): Mapping of source names to feed URLs
        show_author (bool): If True, display article author instead of source name
        log (bool): Enable progress logging to stdout
    
    Returns:
        dict: Parsed feed data with structure:
            {
                'entries': [
                    {
                        'id': int,
                        'sourceName': str,
                        'pubDate': str,
                        'timestamp': int,
                        'url': str,
                        'title': str
                    },
                    ...
                ],
                'created_at': int,
                'failed_sources': [(source, url, error), ...]
            }
    
    Raises:
        ValueError: If category configuration is invalid
    
    Example:
        >>> feeds = {'TechCrunch': 'https://techcrunch.com/feed/'}
        >>> result = get_feed_from_rss('tech', feeds, log=True)
        >>> print(f"Fetched {len(result['entries'])} articles")
    """
```

Add README.md:
```markdown
# RSS Reader

A Python-based RSS feed aggregator with category support.

## Installation
```bash
pip install -r requirements.txt
```

## Configuration
Edit `~/.rreader/feeds.json`:
```json
{
    "tech": {
        "feeds": {
            "TechCrunch": "https://techcrunch.com/feed/"
        },
        "show_author": false
    }
}
```

## Usage
```bash
# Update all feeds
python -m rreader.feed

# Update specific category
python -m rreader.feed --category tech

# Add a feed
python -m rreader.feed --add-feed tech "Hacker News" "https://news.ycombinator.com/rss"
```
```