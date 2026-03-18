# Diagnostic Report: RSS Feed Reader

## Observations

This system currently performs the following functions:

1. **Perceives**: Fetches RSS feeds from configured URLs using `feedparser.parse()`
2. **Caches**: Stores parsed feed entries in memory as a dictionary, keyed by timestamp
3. **Filter (shallow)**: Skips entries without valid timestamps; deduplicates by timestamp (overwriting collisions)
4. **Attend (shallow)**: Sorts entries by timestamp (reverse chronological) before output
5. **Remember**: Persists results to JSON files (`rss_{category}.json`) with creation timestamp
6. **Consolidate**: Absent - no learning or adaptation occurs

The system reads RSS feeds from multiple sources, normalizes them into a consistent format, and writes sorted results to disk. It handles multiple feed categories and merges new bundled categories into user configuration.

## Triage

### Critical gaps (blocks production readiness):

1. **Filter is shallow** - Only validates timestamp presence; accepts duplicate content, broken links, malformed titles, or spam
2. **Attend is shallow** - Only sorts by time; no diversity enforcement, relevance scoring, or deduplication of substantially similar content
3. **Perceive has no error isolation** - Single feed failure with `sys.exit()` kills entire batch; no partial success
4. **Remember has no retention policy** - Files grow unbounded; no cleanup of old entries

### Important gaps (limits usefulness):

5. **Consolidate is absent** - No learning from user behavior, no feed quality scoring, no adaptive refresh rates
6. **Cache has no incremental update** - Re-fetches entire feeds every time; wastes bandwidth and time
7. **No observability** - Silent failures in timestamp parsing; no metrics on feed health

### Minor gaps (quality of life):

8. **Bare exception handlers** - `except:` catches everything including KeyboardInterrupt
9. **No concurrency** - Feeds fetched serially; slow when many sources configured
10. **Hardcoded timezone** - KST is hardcoded rather than configured

## Plan

### 1. Strengthen Filter (Critical)

**Current state**: Only checks `if not parsed_time: continue`

**Changes needed**:
- Add content validation: `if not feed.get('link') or not feed.get('title'): continue`
- Add URL validation: `from urllib.parse import urlparse; if not urlparse(feed.link).scheme: continue`
- Add content deduplication by URL: Track seen URLs in a set before adding to `rslt`
- Add length checks: `if len(feed.title) < 5 or len(feed.title) > 500: continue`
- Add domain blocklist support: Read from `config.BLOCKED_DOMAINS` and skip matching entries

**Code location**: Inside the `for feed in d.entries:` loop, before `entries = {`

---

### 2. Strengthen Attend (Critical)

**Current state**: Only `sorted(rslt.items(), reverse=True)` by timestamp

**Changes needed**:
- Add diversity filter: After sorting, iterate through results and skip entries from the same source if one appeared in the last N positions
- Add configurable limit: `rslt = rslt[:RSS[category].get('max_entries', 100)]`
- Add time window filter: Skip entries older than configured threshold (e.g., 30 days)
- Add source balancing: Ensure no single source dominates the output

**Code location**: Between `rslt = [val for key, val in sorted(...)]` and the final dictionary creation

**Example implementation**:
```python
# After sorting
seen_sources = {}
filtered = []
for entry in rslt:
    source = entry['sourceName']
    last_seen = seen_sources.get(source, -999)
    if len(filtered) - last_seen > 5:  # At least 5 entries between same source
        filtered.append(entry)
        seen_sources[source] = len(filtered) - 1
rslt = filtered[:100]  # Limit total entries
```

---

### 3. Add error isolation to Perceive (Critical)

**Current state**: `sys.exit()` on any feed failure

**Changes needed**:
- Replace `sys.exit()` with `continue` to skip failed feeds
- Add specific exception handling: `except (URLError, HTTPError, ParseError) as e:`
- Log failures to a separate file: `failed_feeds.json` with timestamp and error message
- Return partial results even if some feeds fail

**Code location**: Both try/except blocks in `get_feed_from_rss()`

**Example**:
```python
except Exception as e:
    if log:
        sys.stdout.write(f" - Failed: {str(e)}\n")
    # Log to file
    with open(os.path.join(p["path_data"], "errors.log"), "a") as ef:
        ef.write(f"{time.time()},{category},{source},{str(e)}\n")
    continue  # Skip this feed, process others
```

---

### 4. Add retention policy to Remember (Critical)

**Current state**: JSON files grow indefinitely

**Changes needed**:
- Before writing, load existing file if it exists
- Merge new entries with old entries by ID
- Trim entries older than configured retention (e.g., 30 days): `cutoff = time.time() - (30 * 86400)`
- Keep only most recent N entries per category: `entries[-1000:]`

**Code location**: In `get_feed_from_rss()`, before `with open(...) as f:`

**Example**:
```python
output_file = os.path.join(p["path_data"], f"rss_{category}.json")
if os.path.exists(output_file):
    with open(output_file, "r") as f:
        existing = json.load(f)
    # Merge and dedupe
    all_entries = {e['id']: e for e in existing.get('entries', [])}
    all_entries.update({e['id']: e for e in rslt})
    rslt = list(all_entries.values())
    
# Apply retention
cutoff = int(time.time()) - (30 * 86400)
rslt = [e for e in rslt if e['timestamp'] > cutoff]
rslt.sort(key=lambda x: x['timestamp'], reverse=True)
rslt = rslt[:1000]  # Keep most recent 1000
```

---

### 5. Implement Consolidate (Important)

**Current state**: Absent

**Changes needed**:
- Create `feed_stats.json` to track per-feed metrics (fetch count, error count, average entries)
- After each fetch, update stats for each source
- Use stats to adjust fetch frequency: Reduce refresh rate for consistently empty/failing feeds
- Track click-through or read indicators (requires UI integration) to boost quality sources

**Code location**: New function `update_feed_stats()` called at end of `get_feed_from_rss()`

**Example**:
```python
def update_feed_stats(category, source, success, entry_count):
    stats_file = os.path.join(p["path_data"], "feed_stats.json")
    stats = {}
    if os.path.exists(stats_file):
        with open(stats_file, "r") as f:
            stats = json.load(f)
    
    key = f"{category}:{source}"
    if key not in stats:
        stats[key] = {"fetches": 0, "errors": 0, "total_entries": 0, "last_fetch": 0}
    
    stats[key]["fetches"] += 1
    stats[key]["errors"] += 0 if success else 1
    stats[key]["total_entries"] += entry_count
    stats[key]["last_fetch"] = int(time.time())
    
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)
```

---

### 6. Add incremental updates to Cache (Important)

**Current state**: Full refetch every time

**Changes needed**:
- Store `last_modified` and `etag` headers from feed responses
- Pass these headers in subsequent requests via `feedparser.parse(url, etag=..., modified=...)`
- Skip processing if feed returns 304 Not Modified
- Store last fetch timestamp per feed and skip if fetched recently

**Code location**: Before `d = feedparser.parse(url)`

**Example**:
```python
cache_file = os.path.join(p["path_data"], f"cache_{category}_{source}.json")
headers = {}
if os.path.exists(cache_file):
    with open(cache_file, "r") as f:
        cache = json.load(f)
    headers = {"etag": cache.get("etag"), "modified": cache.get("modified")}
    if time.time() - cache.get("last_fetch", 0) < 300:  # 5 min minimum
        continue

d = feedparser.parse(url, **headers)
if d.status == 304:  # Not modified
    continue

# After successful parse, save headers
with open(cache_file, "w") as f:
    json.dump({
        "etag": d.get("etag"),
        "modified": d.get("modified"),
        "last_fetch": time.time()
    }, f)
```

---

### 7. Add observability (Important)

**Changes needed**:
- Replace bare `except:` with `except Exception as e:` and log the exception
- Add structured logging with timestamps: `logging.info(f"Fetched {len(rslt)} entries from {category}")`
- Track metrics: feeds attempted, succeeded, failed, entries found, processing time
- Write metrics to `metrics.json` for monitoring

**Code location**: Throughout, especially in exception handlers

---

### 8. Fix exception handling (Minor)

**Changes needed**:
- Replace all `except:` with specific exceptions
- First block: `except (URLError, HTTPError, xml.parsers.expat.ExpatError) as e:`
- Second block: `except (AttributeError, KeyError, ValueError, TypeError) as e:`
- Allow KeyboardInterrupt to propagate

**Code location**: Both try/except blocks

---

### 9. Add concurrency (Minor)

**Changes needed**:
- Use `concurrent.futures.ThreadPoolExecutor` to fetch feeds in parallel
- Wrap `feedparser.parse()` call in a function that returns `(source, result_dict)`
- Collect results and merge into `rslt` dictionary
- Add configurable worker count: `max_workers=min(10, len(urls))`

**Code location**: Inside `get_feed_from_rss()`, replacing the `for source, url in urls.items():` loop

---

### 10. Make timezone configurable (Minor)

**Changes needed**:
- Move `TIMEZONE` definition to `feeds.json` as optional per-user setting
- Default to UTC if not specified
- Parse timezone string (e.g., "UTC+9") into `datetime.timezone` object

**Code location**: In `config.py` and feed loading logic