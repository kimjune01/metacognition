# Diagnostic Report: RSS Feed Reader System

## Observations

This system is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Parsing**: Downloads and parses RSS feeds using `feedparser` library from multiple sources
2. **Multi-Category Support**: Organizes feeds into categories defined in a JSON configuration file
3. **Time Localization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9)
4. **Smart Time Display**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
5. **Deduplication**: Uses timestamp as ID to prevent duplicate entries within a category
6. **Data Persistence**: Saves parsed feeds as JSON files (`rss_{category}.json`)
7. **Configuration Management**: 
   - Copies bundled default feeds on first run
   - Merges new categories from bundled config into user config
   - Stores user config at `~/.rreader/feeds.json`
8. **Flexible Author Display**: Supports per-category toggle for showing feed author vs source name
9. **Selective Updates**: Can update a single category or all categories
10. **Logging**: Optional stdout logging of fetch progress

## Triage

### Critical Gaps
1. **No Error Recovery**: Exception handling is minimal and causes complete exits
2. **No Feed Validation**: Missing feeds file structure isn't validated
3. **Security Issues**: No URL validation or request timeouts

### High Priority Gaps
4. **No HTTP Configuration**: Missing user-agent, timeout, retry logic
5. **Collision-Prone IDs**: Using timestamp as ID will overwrite entries published at the same second
6. **No Caching Strategy**: Re-fetches all feeds every time, no conditional requests (ETags/Last-Modified)
7. **Missing Monitoring**: No way to track failed feeds, stale data, or update statistics

### Medium Priority Gaps
8. **No Rate Limiting**: Could hammer servers or hit API limits
9. **Limited Timezone Handling**: Hardcoded timezone, feeds without timezone info may break
10. **No Data Retention Policy**: Old entries accumulate indefinitely
11. **Synchronous Only**: Blocks on each feed sequentially (slow for many feeds)

### Low Priority Gaps
12. **No Feed Metadata**: Doesn't store feed descriptions, icons, or last-updated info
13. **Bare Exception Handling**: `except:` catches everything including KeyboardInterrupt
14. **No CLI Interface**: Can't easily run from command line with options
15. **Missing Tests**: No unit or integration tests

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Replace bare `except:` with specific exceptions (`feedparser.URLError`, `socket.timeout`, `ValueError`)
- In feed loop: catch per-feed errors, log them, continue to next feed instead of exiting
- Add a "failed_feeds" list to output JSON with error messages
- Example:
```python
failed_feeds = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        # ... process entries ...
    except Exception as e:
        failed_feeds.append({"source": source, "url": url, "error": str(e)})
        if log:
            sys.stderr.write(f"Failed to fetch {url}: {e}\n")
        continue
rslt["failed_feeds"] = failed_feeds
```

### 2. Feed Validation (Critical)
**Changes needed:**
- Add schema validation function for feeds.json structure
- Check required keys: categories must have "feeds" dict, optional "show_author" bool
- Validate URLs are well-formed (use `urllib.parse.urlparse`)
- Call validation after loading FEEDS_FILE_NAME, provide helpful error messages

### 3. Security (Critical)
**Changes needed:**
- Add timeout parameter to `feedparser.parse()`: `feedparser.parse(url, timeout=30)`
- Validate URLs match `http://` or `https://` schemes only
- Add max response size limit if feedparser supports it
- Consider URL allowlist for user-added feeds

### 4. HTTP Configuration (High)
**Changes needed:**
- Set custom user-agent: Configure feedparser with agent string
```python
feedparser.USER_AGENT = "rreader/1.0 (+https://github.com/yourrepo)"
```
- Add request timeout (see #3)
- Implement exponential backoff retry (3 attempts) using `time.sleep()`

### 5. Fix ID Collision (High)
**Changes needed:**
- Change ID generation to include feed URL hash:
```python
import hashlib
entry_id = f"{ts}_{hashlib.md5(feed.link.encode()).hexdigest()[:8]}"
```
- Or use feed's GUID if available: `feed.get('id', feed.link)`
- Update dictionary key usage to handle string IDs

### 6. Implement Caching (High)
**Changes needed:**
- Store ETag and Last-Modified headers from previous fetch
- Pass these in feedparser: `feedparser.parse(url, etag=saved_etag, modified=saved_modified)`
- Check `d.status` - if 304, skip processing (not modified)
- Store headers in separate `rss_{category}_cache.json` file

### 7. Monitoring/Statistics (High)
**Changes needed:**
- Add to output JSON:
```python
rslt["stats"] = {
    "total_feeds": len(urls),
    "successful_feeds": success_count,
    "total_entries": len(rslt["entries"]),
    "fetch_duration_seconds": fetch_time
}
```
- Log stats if `log=True`

### 8. Rate Limiting (Medium)
**Changes needed:**
- Add configurable delay between feeds: `time.sleep(0.5)` in feed loop
- Make configurable in feeds.json per-category: `"fetch_delay": 0.5`
- Consider domain-based rate limiting (group by domain)

### 9. Timezone Robustness (Medium)
**Changes needed:**
- Handle feeds without timezone: assume UTC if missing
- Add try/except around timezone conversion specifically
- Make timezone configurable per-feed or category in feeds.json

### 10. Data Retention (Medium)
**Changes needed:**
- Add configuration: `"max_age_days": 7` per category
- Filter entries before saving:
```python
cutoff = time.time() - (max_age_days * 86400)
rslt = [e for e in rslt if e["timestamp"] >= cutoff]
```

### 11. Async Fetching (Medium)
**Changes needed:**
- Add async version using `aiohttp` and `asyncio`
- Create `async def get_feed_from_rss_async()` variant
- Use `asyncio.gather()` to fetch all feeds concurrently
- Keep sync version as fallback

### 12. CLI Interface (Low)
**Changes needed:**
- Add argparse:
```python
parser = argparse.ArgumentParser()
parser.add_argument('--category', help='Update specific category')
parser.add_argument('--verbose', action='store_true')
```
- Move execution logic out of `if __name__ == "__main__"`

### 13. Feed Metadata (Low)
**Changes needed:**
- Store `d.feed.title`, `d.feed.description`, `d.feed.image` 
- Add to category JSON output for UI display

### 14. Replace Bare Exceptions (Low)
**Changes needed:**
- Replace all `except:` with `except Exception as e:`
- Add specific exception types where known
- Never catch `KeyboardInterrupt`, `SystemExit`

### 15. Add Tests (Low)
**Changes needed:**
- Create `tests/` directory with pytest
- Mock feedparser responses for unit tests
- Test: parsing, timezone conversion, deduplication, error handling
- Integration test with actual test RSS feed