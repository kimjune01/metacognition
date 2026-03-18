# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, each with multiple source URLs and configurable display options (e.g., `show_author` flag).

3. **Feed Management**: 
   - Copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user's custom feed configuration
   - Preserves user customizations while adding new defaults

4. **Timestamp Handling**: 
   - Converts feed timestamps to a configurable timezone (hardcoded to UTC+9/KST)
   - Formats display dates as either "HH:MM" (today) or "Mon DD, HH:MM" (other days)

5. **Data Persistence**: Saves parsed feeds as JSON files in `~/.rreader/` directory, one file per category (`rss_{category}.json`).

6. **Deduplication**: Uses timestamp as ID to prevent duplicate entries from the same second.

7. **Sorted Output**: Entries are sorted in reverse chronological order (newest first).

8. **Selective Processing**: Can process all categories or a single target category via the `target_category` parameter.

9. **Logging**: Optional logging flag to output progress to stdout.

## Triage

### Critical Gaps

1. **Error Handling is Inadequate**
   - Bare `except` clauses suppress all errors silently
   - Network failures don't retry or log properly
   - Individual feed failures abort entire category processing

2. **No Configuration Validation**
   - No schema validation for feeds.json
   - Missing/malformed feed URLs crash silently
   - No validation that categories exist when `target_category` is specified

3. **Missing Feed Configuration Structure**
   - The code references `feeds.json` but doesn't include example structure
   - No default feeds bundled in the code shown

### High Priority Gaps

4. **No Rate Limiting or Throttling**
   - Could hammer feed servers with rapid requests
   - No respect for HTTP 429 responses or Retry-After headers

5. **Timezone Configuration is Hardcoded**
   - UTC+9 timezone is not configurable per user
   - Should be in a configuration file, not code

6. **No Update Strategy**
   - Fetches all feeds every time, regardless of freshness
   - No caching based on TTL or Last-Modified headers
   - `created_at` timestamp stored but never checked

7. **Limited Metadata Extraction**
   - Only extracts title, link, author, and timestamp
   - Ignores description, categories, enclosures (podcast/media), and other useful fields

### Medium Priority Gaps

8. **No User Feedback for CLI Usage**
   - When run as `__main__`, provides no output unless `log=True`
   - No progress indication for long-running operations
   - No summary of feeds processed

9. **Collision Risk in Deduplication**
   - Using second-precision timestamps as IDs means entries published in the same second overwrite each other
   - Should use feed GUID or combine timestamp with URL hash

10. **No Data Retention Policy**
    - Old entries accumulate indefinitely
    - No mechanism to prune or archive old feeds

11. **Author Field Logic is Unclear**
    - Falls back to `source` (feed name) when `show_author=False`
    - Should perhaps just omit author field instead

### Low Priority Gaps

12. **No Test Coverage**
    - No unit tests for parsing, deduplication, or error cases
    - No fixtures for testing with mock feeds

13. **Import Pattern is Awkward**
    - Try/except import pattern for relative vs absolute imports suggests packaging issues
    - Inline code at bottom for `common.py` and `config.py` conflicts with imports

14. **No Monitoring/Observability**
    - No metrics on feed fetch success/failure rates
    - No alerting when feeds are consistently failing

## Plan

### 1. Fix Error Handling

**Changes needed:**
- Replace bare `except:` with specific exceptions: `except (urllib.error.URLError, feedparser.exceptions.FeedParserError) as e:`
- Log errors with details: `logging.error(f"Failed to parse {url}: {e}")`
- Continue processing other feeds when one fails instead of exiting
- Add a summary at the end showing which feeds succeeded/failed
- Return error status codes that can be checked by calling code

**Example:**
```python
errors = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
    except Exception as e:
        logging.error(f"Failed to fetch {source} ({url}): {e}")
        errors.append((source, str(e)))
        continue
# Return errors in result dict
```

### 2. Add Configuration Validation

**Changes needed:**
- Create a JSON schema for `feeds.json` structure
- Use `jsonschema` library to validate on load
- Validate URLs using `urllib.parse.urlparse()`
- Check that `target_category` exists in RSS dict before processing
- Provide helpful error messages when validation fails

**Example structure to document:**
```json
{
  "category_name": {
    "feeds": {
      "Source Name": "https://example.com/rss"
    },
    "show_author": false
  }
}
```

### 3. Create Example feeds.json

**Changes needed:**
- Add a `feeds.json.example` file to repository
- Include 2-3 sample categories with real RSS feeds
- Document the schema in README
- Have bundled_feeds_file point to this example

### 4. Implement Rate Limiting

**Changes needed:**
- Add configurable delay between requests: `time.sleep(config.get('request_delay', 0.5))`
- Use `requests` library instead of feedparser's built-in fetching to access response headers
- Check for `Retry-After` header in 429 responses
- Implement exponential backoff for retries
- Add per-domain rate limiting to avoid overwhelming individual servers

### 5. Make Timezone Configurable

**Changes needed:**
- Move timezone to `feeds.json` or separate `config.json`: `{"timezone_offset": 9}`
- Load timezone from config: `TIMEZONE = datetime.timezone(datetime.timedelta(hours=config['timezone_offset']))`
- Default to UTC if not specified
- Validate offset is between -12 and +14

### 6. Implement Caching Strategy

**Changes needed:**
- Check `created_at` timestamp in existing JSON files
- Add TTL configuration per category: `"ttl_minutes": 30`
- Skip fetch if `(current_time - created_at) < ttl`
- Respect HTTP `Cache-Control` and `ETag` headers
- Implement conditional GET requests with `If-Modified-Since`

**Example:**
```python
cache_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(cache_file):
    with open(cache_file) as f:
        cached = json.load(f)
    age_minutes = (time.time() - cached['created_at']) / 60
    if age_minutes < ttl:
        return cached
```

### 7. Extract Additional Metadata

**Changes needed:**
- Add description/summary field: `"description": feed.get('summary', '')`
- Extract categories/tags: `"tags": [tag.term for tag in getattr(feed, 'tags', [])]`
- Extract enclosures for media: `"media": [enc.href for enc in getattr(feed, 'enclosures', [])]`
- Add these fields to the entries dict
- Make extraction configurable per category

### 8. Add User Feedback

**Changes needed:**
- Add logging configuration at module level
- Print summary when run as main: "Processed 5 categories, 127 entries"
- Show progress bar for multiple feeds using `tqdm` library
- Add `--verbose` flag to control output level
- Print feed counts per category

**Example:**
```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--category', help='Process specific category')
    parser.add_argument('--verbose', action='store_true')
    args = parser.parse_args()
    do(target_category=args.category, log=args.verbose)
```

### 9. Fix ID Collision Risk

**Changes needed:**
- Use feed's native GUID if available: `feed_id = getattr(feed, 'id', None)`
- Fall back to hash of URL + timestamp: `hashlib.md5(f"{feed.link}{ts}".encode()).hexdigest()`
- Change dict key from `entries["id"]` to unique composite key
- Keep timestamp for sorting but use GUID for deduplication

### 10. Implement Data Retention

**Changes needed:**
- Add `max_entries` configuration per category: `"max_entries": 1000`
- Prune entries list to max length before saving
- Add `max_age_days` option to delete entries older than threshold
- Implement archive function to move old entries to `archived/` subdirectory

**Example:**
```python
max_entries = RSS[category].get('max_entries', 1000)
rslt['entries'] = rslt['entries'][:max_entries]
```

### 11. Clarify Author Field Logic

**Changes needed:**
- When `show_author=True`, use `feed.author` if present, else omit field
- When `show_author=False`, omit author field entirely
- Change from using source name as fallback to making field optional

**Example:**
```python
entries = {
    "id": feed_id,
    "sourceName": source,
    "pubDate": pubDate,
    "timestamp": ts,
    "url": feed.link,
    "title": feed.title,
}
if show_author and hasattr(feed, 'author'):
    entries["author"] = feed.author
```

### 12. Add Test Coverage

**Changes needed:**
- Create `tests/` directory with `test_fetch.py`
- Use `pytest` framework
- Create mock RSS feed fixtures in `tests/fixtures/`
- Test parsing with `feedparser` mocked
- Test error handling, deduplication, timezone conversion
- Add CI/CD pipeline to run tests

### 13. Fix Import and Packaging

**Changes needed:**
- Remove try/except import pattern
- Create proper package structure with `__init__.py`
- Move inline code to actual `common.py` and `config.py` files
- Use consistent relative imports within package
- Add `setup.py` or `pyproject.toml` for installation
- Document installation: `pip install -e .`

### 14. Add Monitoring

**Changes needed:**
- Log metrics to file: feed fetch duration, success/failure counts
- Add `--stats` flag to show historical reliability per feed
- Store fetch history in `stats.json`: `{"feed_url": {"last_success": ts, "failure_count": 3}}`
- Implement warnings when feeds fail repeatedly
- Optional integration with monitoring services (StatsD, Prometheus)