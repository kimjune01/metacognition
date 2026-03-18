# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **Feed parsing**: Downloads and parses RSS/Atom feeds using `feedparser`, extracting entries with title, link, publication date, and author information.

2. **Multi-category organization**: Supports organizing feeds into categories defined in a `feeds.json` configuration file.

3. **Time normalization**: Converts feed timestamps to a configurable timezone (currently KST/UTC+9) and formats them as relative dates ("HH:MM" for today, "MMM DD, HH:MM" for older entries).

4. **Deduplication by timestamp**: Uses Unix timestamp as entry ID to prevent duplicate entries within a single fetch.

5. **Configuration management**: Automatically creates user configuration from bundled defaults and merges new categories from updates without overwriting user customization.

6. **JSON persistence**: Stores fetched entries as JSON files named `rss_{category}.json` with metadata including fetch timestamp.

7. **Sorted output**: Returns entries in reverse chronological order (newest first).

8. **Selective refresh**: Can refresh a single category or all categories via the `target_category` parameter.

9. **Optional author display**: Per-category setting to show feed-level author or source name.

10. **Graceful fallback**: Handles missing `published_parsed` by falling back to `updated_parsed`.

## Triage

### Critical gaps (blocking production use)

1. **No error isolation**: One bad feed URL kills the entire category fetch. A single malformed feed or network timeout prevents all other feeds in that category from updating.

2. **No rate limiting**: Hammers all feed URLs simultaneously without delays, risking IP bans from feed providers and violating robots.txt.

3. **No stale data handling**: Once written, JSON files are never cleaned. Deleted feeds leave orphaned entries indefinitely.

4. **Silent failures**: The try-except around feed parsing swallows all exceptions without logging what failed or why.

### High-priority gaps (needed for reliability)

5. **No cache control**: Re-downloads entire feeds on every run, ignoring HTTP ETags and Last-Modified headers that RSS was designed to support.

6. **No connection timeouts**: Network calls can hang indefinitely. The `feedparser.parse()` call has no timeout parameter.

7. **No incremental updates**: Every fetch rewrites the entire JSON file. On a crash mid-write, you lose all data for that category.

8. **No duplicate detection across runs**: The timestamp-based deduplication only works within a single fetch. If a feed updates an entry, you get duplicates.

### Medium-priority gaps (quality of life)

9. **No entry expiration**: The JSON files grow unbounded. Year-old entries remain forever.

10. **No user-configurable timezone**: Hardcoded to KST. Users in other regions see incorrect relative times.

11. **No concurrent fetching**: Categories are processed serially. With 10 categories of 5 feeds each, that's 50 sequential HTTP requests.

12. **No validation of feeds.json**: Malformed JSON or missing required keys cause cryptic errors at runtime.

### Low-priority gaps (polish)

13. **No feed health metrics**: No way to know which feeds are consistently failing or slow.

14. **No content sanitization**: Feed titles and descriptions are stored raw. HTML tags, scripts, or malformed Unicode could break consumers.

15. **No OPML import/export**: Standard RSS reader feature for migrating feed lists.

## Plan

### 1. Error isolation
**Change**: Wrap the inner loop (each feed URL) in its own try-except, not the entire category.
```python
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        # process entries...
    except Exception as e:
        logging.warning(f"Failed to fetch {source} ({url}): {e}")
        continue  # Don't let one bad feed kill the whole category
```

### 2. Rate limiting
**Change**: Add configurable delays between feed requests.
```python
import time
# In feeds.json schema, add per-category "request_delay_seconds": 1.0
for source, url in urls.items():
    time.sleep(d.get("request_delay_seconds", 1.0))
    # ... existing fetch logic
```

### 3. Stale data cleanup
**Change**: Before writing new JSON, filter out entries from URLs no longer in the config.
```python
# Load existing JSON
if os.path.exists(json_path):
    with open(json_path) as f:
        old_data = json.load(f)
    # Keep only entries whose sourceName is still in current urls
    valid_sources = set(urls.keys())
    old_entries = [e for e in old_data.get("entries", []) 
                   if e["sourceName"] in valid_sources]
else:
    old_entries = []
# Merge with new entries before deduplication
```

### 4. Explicit error logging
**Change**: Replace bare `except:` with specific exceptions and structured logging.
```python
import logging
logging.basicConfig(level=logging.INFO)

except feedparser.URLError as e:
    logging.error(f"Network error fetching {url}: {e}")
except feedparser.ParseError as e:
    logging.error(f"Parse error for {url}: {e}")
except Exception as e:
    logging.exception(f"Unexpected error processing {url}")
```

### 5. HTTP caching
**Change**: Pass ETag/Last-Modified headers to `feedparser` and skip processing if `304 Not Modified`.
```python
# Store ETags in a separate metadata file per category
etag_file = os.path.join(p["path_data"], f"rss_{category}_etags.json")
etags = json.load(open(etag_file)) if os.path.exists(etag_file) else {}

d = feedparser.parse(url, etag=etags.get(url, {}).get("etag"), 
                     modified=etags.get(url, {}).get("modified"))
if d.status == 304:
    continue  # No changes since last fetch

# After successful parse, save new ETag
etags[url] = {"etag": d.get("etag"), "modified": d.get("modified")}
json.dump(etags, open(etag_file, "w"))
```

### 6. Connection timeouts
**Change**: Set socket timeout before calling `feedparser`.
```python
import socket
socket.setdefaulttimeout(30)  # 30-second timeout for all network ops
```

### 7. Atomic writes
**Change**: Write to a temporary file, then rename on success.
```python
import tempfile
temp_fd, temp_path = tempfile.mkstemp(dir=p["path_data"], suffix=".json")
with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
    f.write(json.dumps(rslt, ensure_ascii=False))
os.replace(temp_path, final_path)  # Atomic on POSIX
```

### 8. Cross-run deduplication
**Change**: Use content hash (title + URL) as the entry ID instead of timestamp.
```python
import hashlib
entry_id = hashlib.sha256(f"{feed.title}{feed.link}".encode()).hexdigest()[:16]
entries = {"id": entry_id, "timestamp": ts, ...}
```

### 9. Entry expiration
**Change**: Add max age to config and filter entries on load.
```python
# In feeds.json: "max_age_days": 30
max_age = d.get("max_age_days", 30) * 86400
cutoff = int(time.time()) - max_age
old_entries = [e for e in old_entries if e["timestamp"] > cutoff]
```

### 10. User-configurable timezone
**Change**: Move TIMEZONE to feeds.json, fall back to system timezone.
```python
# In config.py
import datetime
DEFAULT_TZ = datetime.datetime.now().astimezone().tzinfo

# In feeds.json root level: "timezone_offset_hours": 9
tz_offset = RSS.get("timezone_offset_hours", 0)
TIMEZONE = datetime.timezone(datetime.timedelta(hours=tz_offset))
```

### 11. Concurrent fetching
**Change**: Use `concurrent.futures.ThreadPoolExecutor` for parallel category processing.
```python
from concurrent.futures import ThreadPoolExecutor, as_completed

with ThreadPoolExecutor(max_workers=5) as executor:
    futures = {executor.submit(get_feed_from_rss, cat, d["feeds"], 
                               d.get("show_author", False), log): cat 
               for cat, d in RSS.items()}
    for future in as_completed(futures):
        category = futures[future]
        try:
            future.result()
        except Exception as e:
            logging.error(f"Category {category} failed: {e}")
```

### 12. Config validation
**Change**: Define a schema and validate on load.
```python
def validate_feeds_json(data):
    assert isinstance(data, dict), "Root must be object"
    for category, config in data.items():
        assert "feeds" in config, f"{category} missing 'feeds'"
        assert isinstance(config["feeds"], dict), f"{category}.feeds must be object"
        for source, url in config["feeds"].items():
            assert url.startswith("http"), f"Invalid URL for {source}: {url}"
    return data

RSS = validate_feeds_json(json.load(open(FEEDS_FILE_NAME)))
```

### 13. Feed health tracking
**Change**: Log response times and error counts to a metrics file.
```python
import time
metrics = {}
start = time.time()
try:
    d = feedparser.parse(url)
    metrics[url] = {"last_success": int(time.time()), 
                    "duration_ms": int((time.time() - start) * 1000)}
except Exception as e:
    metrics[url] = {"last_failure": int(time.time()), "error": str(e)}

# Append to metrics.json
```

### 14. Content sanitization
**Change**: Strip HTML and limit length for title/description.
```python
from html.parser import HTMLParser
class MLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.strict = False
        self.convert_charrefs = True
        self.text = []
    def handle_data(self, d):
        self.text.append(d)
    def get_data(self):
        return ''.join(self.text)

def strip_tags(html):
    s = MLStripper()
    s.feed(html)
    return s.get_data()

entries["title"] = strip_tags(feed.title)[:500]  # Max 500 chars
```

### 15. OPML support
**Change**: Add import/export functions.
```python
import xml.etree.ElementTree as ET

def export_opml(feeds_dict, output_path):
    opml = ET.Element("opml", version="2.0")
    body = ET.SubElement(opml, "body")
    for category, config in feeds_dict.items():
        outline = ET.SubElement(body, "outline", text=category)
        for source, url in config["feeds"].items():
            ET.SubElement(outline, "outline", type="rss", text=source, xmlUrl=url)
    ET.ElementTree(opml).write(output_path, encoding="utf-8", xml_declaration=True)

def import_opml(opml_path):
    tree = ET.parse(opml_path)
    feeds = {}
    for category_outline in tree.findall(".//body/outline"):
        category = category_outline.get("text")
        feeds[category] = {"feeds": {}}
        for feed_outline in category_outline.findall("outline[@type='rss']"):
            feeds[category]["feeds"][feed_outline.get("text")] = feed_outline.get("xmlUrl")
    return feeds
```