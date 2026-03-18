# Diagnostic Report: RSS Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Successfully fetches and parses RSS/Atom feeds using the `feedparser` library from multiple sources.

2. **Multi-Source Aggregation**: Handles multiple RSS feeds organized by categories, with each category containing multiple source URLs.

3. **Time Handling**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9) and formats them for display.

4. **Deduplication**: Uses timestamp-based IDs to deduplicate entries across multiple sources within the same category.

5. **Configuration Management**: 
   - Maintains a `feeds.json` configuration file in user's home directory
   - Automatically copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration

6. **Data Persistence**: Saves parsed feed data as JSON files (`rss_{category}.json`) in `~/.rreader/` directory.

7. **Flexible Operation Modes**: 
   - Can process all categories or a single target category
   - Optional logging output
   - Supports both module import and standalone execution

8. **Author Display**: Configurable per-category option to show feed author or source name.

## Triage

### Critical Gaps

1. **No Error Recovery**: Silent failures when feeds are unreachable or malformed
2. **No Rate Limiting**: Could hammer servers or get IP-banned with frequent updates
3. **No Data Validation**: Malformed JSON or missing required fields cause crashes

### High Priority Gaps

4. **No Caching Strategy**: Re-fetches all feeds every time, wasting bandwidth
5. **No Concurrent Fetching**: Sequential feed fetching is extremely slow
6. **No User Feedback**: Minimal progress indication during long operations
7. **No Feed Health Monitoring**: Can't identify consistently failing feeds

### Medium Priority Gaps

8. **No Configuration Validation**: Invalid feeds.json structure causes runtime failures
9. **No Content Filtering**: No way to filter by keywords, date ranges, or read/unread status
10. **No Update Detection**: Can't identify which entries are new since last fetch
11. **Hard-coded Timezone**: TIMEZONE constant not user-configurable

### Low Priority Gaps

12. **No Feed Discovery**: Can't auto-detect RSS feed URLs from website URLs
13. **No Export Functionality**: Can't export feeds to OPML or other formats
14. **No Analytics**: No metrics on feed update frequency or reliability
15. **Limited Documentation**: No docstrings or usage examples

## Plan

### Critical Fixes

**1. Error Recovery**
- Wrap feed parsing in try-except blocks that catch specific exceptions (`URLError`, `HTTPError`, `feedparser` exceptions)
- Log errors with feed URL and error type to a separate `errors.log` file
- Continue processing remaining feeds when one fails
- Return partial results with error metadata: `{"success": [...], "failed": [{"url": ..., "error": ...}]}`

**2. Rate Limiting**
- Add `time.sleep()` between feed fetches (configurable, default 1 second)
- Implement per-domain rate limiting using a dictionary tracking last request time per domain
- Add exponential backoff for failed requests (retry with 1s, 2s, 4s delays)
- Add `User-Agent` header to requests to be a good web citizen

**3. Data Validation**
- Create validation functions: `validate_feeds_json()`, `validate_feed_entry()`
- Check required fields exist before accessing: `feed.get('link')`, `feed.get('title')`
- Provide defaults for missing optional fields
- Use JSON schema validation library (e.g., `jsonschema`) for feeds.json structure

### High Priority Enhancements

**4. Caching Strategy**
- Store `ETag` and `Last-Modified` headers from feed responses in metadata file
- Send conditional GET requests using these headers
- Only parse and update when feed has actually changed
- Add `max_age` configuration per category (e.g., cache tech news for 10 minutes, blogs for 1 hour)

**5. Concurrent Fetching**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_feed_from_rss(category, urls, show_author=False, log=False):
    rslt = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_url = {
            executor.submit(fetch_single_feed, url, source): (source, url)
            for source, url in urls.items()
        }
        for future in as_completed(future_to_url):
            source, url = future_to_url[future]
            try:
                entries = future.result()
                rslt.update(entries)
            except Exception as e:
                log_error(url, e)
```

**6. User Feedback**
- Add progress bar using `tqdm` library: `for source in tqdm(urls, desc=f"Fetching {category}")`
- Print summary after completion: "Fetched X entries from Y/Z feeds (A failed)"
- Add verbosity levels: `-q` (quiet), `-v` (verbose), `-vv` (debug)

**7. Feed Health Monitoring**
- Create `feed_health.json` tracking: last successful fetch, consecutive failures, average entry count
- Flag feeds with >5 consecutive failures for user review
- Add `health_check()` function that reports problematic feeds

### Medium Priority Enhancements

**8. Configuration Validation**
```python
def validate_feeds_config(config):
    assert isinstance(config, dict), "Config must be dict"
    for category, data in config.items():
        assert "feeds" in data, f"Category {category} missing 'feeds'"
        assert isinstance(data["feeds"], dict), f"{category} feeds must be dict"
        for source, url in data["feeds"].items():
            assert url.startswith(("http://", "https://")), f"Invalid URL: {url}"
```

**9. Content Filtering**
- Add filter configuration per category: `{"keywords": [...], "exclude": [...], "since": "2024-01-01"}`
- Implement `matches_filter(entry, filter_config)` function
- Store read entry IDs in `read_entries.json`
- Add `--unread-only` command line flag

**10. Update Detection**
- Compare new entries against previous `rss_{category}.json` by ID
- Add `"new": true` flag to entries not in previous fetch
- Create separate `new_entries.json` summary file
- Add `--new-only` mode to return only new entries

**11. Configurable Timezone**
- Move TIMEZONE to feeds.json: `{"_settings": {"timezone": "+09:00"}}`
- Parse timezone string: `datetime.timezone(datetime.timedelta(hours=int(tz.split(':')[0])))`
- Fall back to UTC if invalid

### Low Priority Enhancements

**12. Feed Discovery**
```python
def discover_feed(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    links = soup.find_all('link', type=['application/rss+xml', 'application/atom+xml'])
    return [link.get('href') for link in links]
```

**13. Export Functionality**
- Implement `export_to_opml(feeds_config)` function
- Generate OPML XML with categories and feed URLs
- Add `--export opml` command line option

**14. Analytics**
- Track metrics: fetch duration, entry count per feed, update frequency
- Store in `analytics.json` with rolling 30-day window
- Add `--stats` command to display feed statistics

**15. Documentation**
- Add module docstring explaining purpose and usage
- Add function docstrings with parameter descriptions and return types
- Create README.md with examples: installation, configuration, CLI usage
- Add inline comments for complex logic (timestamp handling, deduplication)