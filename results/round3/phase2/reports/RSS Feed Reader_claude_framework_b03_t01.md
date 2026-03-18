# Diagnostic Report: RSS Feed Aggregator System

## Observations

This system is a working RSS feed aggregator that:

1. **Fetches and parses RSS feeds** from multiple sources using `feedparser`
2. **Manages feed configuration** via a JSON file (`feeds.json`) with category-based organization
3. **Handles feed initialization** by copying bundled defaults and merging new categories into user config
4. **Normalizes timestamps** across feeds, handling both `published_parsed` and `updated_parsed` fields
5. **Formats dates contextually** - shows time-only for today's entries, full date otherwise
6. **Supports author display control** per category via `show_author` flag
7. **Stores parsed results** as JSON files per category in `~/.rreader/`
8. **Deduplicates entries** by timestamp within a fetch cycle
9. **Sorts entries** chronologically (newest first)
10. **Supports selective updates** - can refresh a single category or all categories
11. **Has basic error handling** for failed fetches and missing timestamp fields

## Triage

### Critical Gaps

1. **No error recovery or retry logic** - A single network failure silently kills the entire fetch for that source (the try/except swallows errors without logging)

2. **No caching or conditional requests** - Every fetch downloads the entire feed, wasting bandwidth and hitting rate limits

3. **No duplicate detection across fetches** - The same entry will appear multiple times if you run this twice

4. **Silent data loss** - Duplicate timestamp IDs overwrite earlier entries (the `rslt[entries["id"]] = entries` pattern)

### Important Gaps

5. **No feed validation** - Malformed feeds or missing required fields can corrupt the output

6. **No concurrency** - Fetches happen serially, making updates slow for many feeds

7. **No monitoring** - Can't tell if feeds are stale, broken, or the system is working

8. **No entry limits** - A feed with 10,000 entries will store all 10,000

### Nice to Have

9. **No CLI interface** - The `log` parameter suggests interactive use but there's no argument parser

10. **Hardcoded timezone** - KST (UTC+9) is baked in, not configurable

11. **No feed management** - Can't add/remove feeds without editing JSON manually

12. **No HTML sanitization** - Feed titles could contain malicious HTML/JavaScript

## Plan

### 1. Error Recovery (Critical)

**Changes needed:**
- Replace bare `except:` at line 27 with specific exception types (`urllib.error.URLError`, `socket.timeout`)
- Add a retry mechanism with exponential backoff (3 attempts, 1s → 2s → 4s delays)
- Log failures to a `~/.rreader/errors.log` file with timestamp, URL, and exception message
- Continue processing remaining feeds after a failure instead of `sys.exit(0)`

**New code structure:**
```python
for attempt in range(3):
    try:
        d = feedparser.parse(url, timeout=10)
        break
    except (URLError, TimeoutError) as e:
        if attempt == 2:
            log_error(category, source, url, str(e))
            continue  # skip this source
        time.sleep(2 ** attempt)
```

### 2. HTTP Caching (Critical)

**Changes needed:**
- Store `ETag` and `Last-Modified` headers from each feed response
- Add them to the category JSON: `{"feeds": {...}, "cache": {"source": {"etag": "...", "modified": "..."}}}`
- Pass headers to `feedparser.parse()` via `request_headers` parameter
- Handle 304 Not Modified responses by skipping the parse step

**New storage format:**
```python
# In rss_{category}.json:
{
    "entries": [...],
    "created_at": 1234567890,
    "cache": {
        "HackerNews": {
            "etag": "\"abc123\"",
            "modified": "Mon, 17 Mar 2026 12:00:00 GMT"
        }
    }
}
```

### 3. Cross-Fetch Deduplication (Critical)

**Changes needed:**
- Before writing new entries, read existing `rss_{category}.json` file
- Build a set of existing entry IDs: `existing_ids = {e["id"] for e in old_data["entries"]}`
- Filter new entries: `new_entries = [e for e in rslt["entries"] if e["id"] not in existing_ids]`
- Merge and re-sort: `combined = old_data["entries"] + new_entries`, then sort by timestamp
- Add a `max_entries` config per category (default 1000) and trim older entries

### 4. Timestamp Collision Handling (Critical)

**Changes needed:**
- Change the ID strategy from `int(time.mktime())` (second precision) to microsecond precision
- Use `f"{ts}_{hash(feed.link)[:8]}"` to guarantee uniqueness even for simultaneous posts
- Update the sort key to split on `_` and sort numerically

**Code change:**
```python
# Replace line 48-50:
ts_micro = int(time.mktime(parsed_time) * 1_000_000)
link_hash = abs(hash(feed.link)) % 100_000_000
unique_id = f"{ts_micro}_{link_hash}"
```

### 5. Feed Validation (Important)

**Changes needed:**
- After `feedparser.parse()`, check `d.bozo` flag (indicates malformed XML)
- Verify required fields exist before accessing: `if not hasattr(feed, 'link') or not hasattr(feed, 'title'): continue`
- Add schema validation for the feeds.json file (use `jsonschema` library)
- Reject feeds with `d.status >= 400` or `d.status == 0` (network failure)

### 6. Concurrent Fetching (Important)

**Changes needed:**
- Replace the serial loop with `concurrent.futures.ThreadPoolExecutor`
- Process each source in parallel with max 10 workers (to respect server limits)
- Aggregate results after all futures complete

**New structure:**
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_one_source(source, url):
    # Move lines 22-64 into this function
    ...

with ThreadPoolExecutor(max_workers=10) as executor:
    futures = {executor.submit(fetch_one_source, s, u): s 
               for s, u in urls.items()}
    for future in as_completed(futures):
        source = futures[future]
        try:
            entries = future.result()
            rslt.update(entries)
        except Exception as e:
            log_error(category, source, str(e))
```

### 7. Health Monitoring (Important)

**Changes needed:**
- Write a `status.json` file tracking last successful fetch per source
- Include: `{"source": {"last_success": 1234567890, "last_error": null, "entry_count": 42}}`
- Add a `--check` CLI flag that reads this file and reports stale feeds (>24h old)
- Emit warnings if a feed returns zero entries after previously returning many

### 8. Entry Limits (Important)

**Changes needed:**
- Add `max_entries_per_feed` to the category config (default 100)
- Slice the parsed entries: `d.entries[:max_entries_per_feed]`
- Add `max_total_entries` to the category config (default 1000)
- After merging old + new, sort and slice: `rslt["entries"] = sorted(...)[:max_total_entries]`

### 9. CLI Interface (Nice to Have)

**Changes needed:**
- Add `argparse` to replace the bare `if __name__ == "__main__":` block
- Implement flags: `--category`, `--verbose`, `--check`, `--add-feed`, `--list`
- Make `log` parameter default to True when running as CLI, False when imported

**Example CLI:**
```python
parser = argparse.ArgumentParser()
parser.add_argument('--category', help='Update only this category')
parser.add_argument('--verbose', action='store_true')
parser.add_argument('--check', action='store_true', help='Show health status')
args = parser.parse_args()
do(target_category=args.category, log=args.verbose)
```

### 10. Timezone Configuration (Nice to Have)

**Changes needed:**
- Move `TIMEZONE` from `config.py` to the feeds.json per-category config
- Add a global `default_timezone` key in feeds.json (default "UTC+9")
- Parse timezone strings using `datetime.timezone(datetime.timedelta(hours=offset))`
- Fall back to system local timezone if parsing fails

### 11. Feed Management (Nice to Have)

**Changes needed:**
- Add `add_feed(category, name, url)` function that modifies feeds.json
- Add `remove_feed(category, name)` function
- Add `list_feeds()` function that prints current configuration
- Validate URLs before adding (check for HTTP 200 response)

### 12. HTML Sanitization (Nice to Have)

**Changes needed:**
- Install `bleach` library for HTML sanitization
- Sanitize `feed.title` before storing: `bleach.clean(feed.title, tags=[], strip=True)`
- Add a `sanitize_html` utility function used consistently
- Consider allowing safe tags like `<em>`, `<strong>` via config

---

**Priority order for implementation:**
1. Error recovery (prevents silent failures)
2. Cross-fetch deduplication (prevents database bloat)
3. Timestamp collision handling (prevents data loss)
4. HTTP caching (reduces bandwidth and rate limit issues)
5. Concurrent fetching (improves user experience)
6. Feed validation (improves reliability)
7. Entry limits (prevents runaway storage growth)
8. Health monitoring (enables operational visibility)
9. CLI interface, timezone config, feed management, HTML sanitization (polish)