# Diagnostic Report: RSS Feed Reader System

## Observations

This is a functional RSS feed aggregator with the following working capabilities:

1. **Feed Fetching**: Parses multiple RSS feeds using `feedparser` and aggregates entries
2. **Multi-source Support**: Handles multiple feed sources per category from a JSON configuration
3. **Timezone Handling**: Converts UTC timestamps to KST (Seoul, UTC+9)
4. **Smart Date Display**: Shows "HH:MM" for today's entries, "MMM DD, HH:MM" for older ones
5. **Data Persistence**: Writes aggregated feeds to `~/.rreader/rss_{category}.json`
6. **Deduplication**: Uses timestamps as IDs to prevent duplicate entries
7. **Configuration Management**: Automatically merges bundled feeds with user feeds, preserving user customizations
8. **Author Display**: Supports configurable author display (source name vs. feed author)
9. **Selective Updates**: Can refresh a single category or all categories
10. **Fallback Parsing**: Tries both `published_parsed` and `updated_parsed` for timestamps

## Triage

### Critical Gaps
1. **No Error Recovery** - Single feed failure exits entire process
2. **No Feed Content** - Only stores metadata (title, URL, date); no article summaries or content
3. **No Read/Unread State** - Can't track which articles have been viewed
4. **No UI/Presentation Layer** - Only a data fetcher; no way to actually read the feeds

### Important Gaps
5. **No Rate Limiting** - Could hammer feed servers or get rate-limited
6. **No Cache Headers** - Ignores HTTP caching (`ETag`, `Last-Modified`), wastes bandwidth
7. **No Feed Health Monitoring** - Silent failures after initial load; no way to know if feeds are dead
8. **No Update Scheduling** - Manual refresh only; no background updates or intervals
9. **Silent Timestamp Failures** - Entries without parseable timestamps are dropped silently
10. **No Pagination/Limits** - Fetches entire feeds; could be memory-intensive for large feeds

### Nice-to-Have Gaps
11. **No Feed Discovery** - Can't auto-detect RSS feeds from website URLs
12. **No Import/Export** - Can't import OPML or export feeds for backup
13. **No Search** - Can't search across articles
14. **No Filtering** - Can't filter by keyword, source, or date range
15. **Hardcoded Timezone** - KST is hardcoded; not configurable per-user

## Plan

### 1. Error Recovery (Critical)
**Current**: `sys.exit()` on any feed failure kills entire update  
**Change**: Wrap each feed fetch in try-except, log failures, continue with remaining feeds
```python
failed_feeds = []
for source, url in urls.items():
    try:
        # existing parse logic
    except Exception as e:
        failed_feeds.append((source, url, str(e)))
        if log:
            sys.stderr.write(f"✗ {url} - {e}\n")
        continue  # not sys.exit()
```
**Return** failed feeds list for monitoring/retry

### 2. Feed Content Storage (Critical)
**Current**: Only stores `title`, `url`, `pubDate`, `timestamp`  
**Change**: Add `summary` and `content` fields to entries dict
```python
entries = {
    # ... existing fields ...
    "summary": getattr(feed, 'summary', ''),
    "content": feed.get('content', [{}])[0].get('value', ''),
}
```
**Note**: Store both; summary for list view, content for full article view

### 3. Read/Unread Tracking (Critical)
**Current**: No state tracking  
**Change**: Create separate `state_{category}.json` file per category
```python
# Structure: { "entry_id": {"read": bool, "starred": bool, "read_at": timestamp} }
```
Add functions: `mark_read(category, entry_id)`, `mark_unread()`, `get_unread_count()`

### 4. UI/Presentation Layer (Critical)
**Current**: Command-line data fetcher only  
**Options**:
- **TUI**: Use `rich` or `textual` for terminal UI (fastest MVP)
- **Web**: Flask/FastAPI server + HTML frontend
- **Desktop**: PyQt/Tkinter GUI

For TUI MVP, create `rreader/ui.py`:
```python
# Display categories → entries → article view
# Keybindings: j/k nav, enter open, m mark read, q quit
```

### 5. Rate Limiting (Important)
**Current**: Hammers all feeds immediately  
**Change**: Add delays between requests
```python
import time
for source, url in urls.items():
    # ... fetch logic ...
    time.sleep(0.5)  # 500ms between feeds
```
**Better**: Use `requests.Session()` with retry adapter that respects `Retry-After` headers

### 6. HTTP Cache Support (Important)
**Current**: Full re-fetch every time  
**Change**: Store and use `ETag` and `Last-Modified` headers
```python
# In rss_{category}.json, add per-feed:
{"etag": "...", "last_modified": "..."}

# In feedparser.parse():
d = feedparser.parse(url, 
                    etag=cached_etag,
                    modified=cached_last_modified)
if d.status == 304:  # Not Modified
    continue  # skip processing
```

### 7. Feed Health Monitoring (Important)
**Current**: Silent failures after initial load  
**Change**: Add `health_{category}.json` tracking:
```python
{
  "source_name": {
    "last_success": timestamp,
    "last_failure": timestamp,
    "consecutive_failures": int,
    "last_error": str
  }
}
```
Warn user if consecutive_failures > 3

### 8. Update Scheduling (Important)
**Current**: Manual `do()` calls only  
**Change**: Add daemon mode with configurable intervals
```python
def daemon(interval_minutes=15):
    while True:
        do(log=True)
        time.sleep(interval_minutes * 60)
```
**Better**: Use `schedule` library or systemd timer (Linux) / launchd (macOS)

### 9. Timestamp Failure Logging (Important)
**Current**: `continue` silently drops entries  
**Change**: Count and report entries without timestamps
```python
skipped = 0
for feed in d.entries:
    parsed_time = getattr(feed, 'published_parsed', None) or ...
    if not parsed_time:
        skipped += 1
        continue
if log and skipped > 0:
    sys.stderr.write(f"  ⚠ Skipped {skipped} entries (no timestamp)\n")
```

### 10. Pagination/Memory Limits (Important)
**Current**: Stores all entries indefinitely  
**Change**: Add retention policy to config
```python
# In feeds.json categories:
{"max_entries": 100, "max_age_days": 30}

# After sorting by timestamp, trim:
rslt = rslt[:max_entries]
cutoff = int(time.time()) - (max_age_days * 86400)
rslt = [e for e in rslt if e['timestamp'] > cutoff]
```

### 11. Feed Discovery (Nice-to-Have)
**Change**: Add `discover_feed(website_url)` function using BeautifulSoup
```python
# Look for <link rel="alternate" type="application/rss+xml">
# Try common paths: /feed, /rss, /atom.xml
```

### 12. OPML Import/Export (Nice-to-Have)
**Change**: Add `export_opml()` and `import_opml(file_path)` functions
```python
# Use xml.etree.ElementTree to parse/generate OPML
# Map <outline> elements to feeds.json structure
```

### 13. Search Functionality (Nice-to-Have)
**Change**: Add full-text search across all cached entries
```python
def search(query, category=None):
    # Load all rss_{category}.json files
    # Filter entries where query in (title + summary)
    # Return sorted by relevance/timestamp
```

### 14. Filtering (Nice-to-Have)
**Change**: Add filter params to data loading
```python
def load_entries(category, filters=None):
    # filters = {"source": "...", "after": ts, "before": ts, "unread": bool}
```

### 15. Configurable Timezone (Nice-to-Have)
**Current**: Hardcoded KST in `config.py`  
**Change**: Add to user config or detect from system
```python
# In feeds.json root:
{"timezone_offset": 9}  # hours from UTC

# Or use: datetime.datetime.now().astimezone().tzinfo
```