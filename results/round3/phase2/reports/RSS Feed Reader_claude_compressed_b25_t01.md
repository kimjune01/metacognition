# Diagnostic Report: RSS Feed Reader

## Observations

This system currently:

1. **Perceives:** Fetches RSS/Atom feeds from URLs defined in a JSON configuration file
2. **Cache:** Parses feed entries and stores them as JSON files (one per category) in `~/.rreader/`
3. **Filter (shallow):** Skips entries without valid timestamps, silently continues on parse failures
4. **Attend (shallow):** Sorts entries by timestamp (newest first), uses timestamp as deduplication key
5. **Remember:** Persists results to disk as JSON files, maintains feed configuration across runs
6. **Consolidate:** Absent - no learning or adaptation occurs

**Current behavior:** A stateless RSS aggregator that overwrites its output on each run. It can handle multiple feed categories, normalizes timestamps to a configured timezone, and merges new bundled feeds into user configuration.

## Triage

### Critical gaps (blocks production use)

1. **Consolidate is absent** - No way to mark items as read, track user preferences, or learn from usage
2. **Filter is shallow** - No deduplication across runs, no quality checks, accepts duplicate entries with same timestamp
3. **Attend is shallow** - No diversity enforcement, no ranking beyond recency, timestamp collisions overwrite entries
4. **Error handling is destructive** - `sys.exit(0)` on parse failure silently suppresses all errors

### Important gaps (limits reliability)

5. **Perceive lacks observability** - Logging is optional and incomplete, no metrics on what was ingested
6. **Cache has no TTL** - Stale data persists forever, no expiration policy
7. **Remember has no integrity checks** - Corrupted JSON files will crash the system, no schema validation

### Nice-to-have gaps (polish)

8. **No incremental updates** - Always fetches entire feeds even if unchanged
9. **No rate limiting** - Could hammer feed servers or get blocked
10. **No concurrent fetching** - Processes feeds serially, slow for many sources

## Plan

### 1. Add Consolidate stage (critical)

**Goal:** Track read/unread state, enable user feedback to influence future rankings.

**Changes:**
- Create `rss_{category}_state.json` alongside each data file with structure:
  ```json
  {
    "read_ids": [123456, 123457],
    "starred_ids": [123458],
    "hidden_sources": ["SpammyBlog"]
  }
  ```
- Modify `get_feed_from_rss()` to load state file at start, filter out `read_ids` and `hidden_sources` before writing output
- Add CLI commands: `rreader mark-read <id>`, `rreader hide-source <name>`
- In `Attend` stage: boost starred sources, demote sources with high skip rate

### 2. Implement proper Filter stage (critical)

**Goal:** Prevent duplicates across runs, validate entry quality.

**Changes:**
- Before processing feeds, load existing `rss_{category}.json` and extract all seen IDs into a set
- Change ID generation from timestamp to `hash(feed.link)` to handle same-second publications
- Add validation rules:
  ```python
  def is_valid_entry(feed):
      if not getattr(feed, 'link', None):
          return False
      if not getattr(feed, 'title', '').strip():
          return False
      if len(feed.title) > 500:  # Likely spam
          return False
      return True
  ```
- Skip entries where `entries["id"]` already exists in seen set
- Count and log filtered entries: `"filtered": {"no_timestamp": 3, "duplicate": 12, "invalid": 1}`

### 3. Improve Attend stage (critical)

**Goal:** Diversify results, prevent source dominance, handle ID collisions.

**Changes:**
- Replace `rslt[entries["id"]] = entries` (dict keyed by timestamp) with:
  ```python
  rslt.append(entries)  # Keep as list
  ```
- After collecting all entries, deduplicate by URL:
  ```python
  seen_urls = set()
  deduped = []
  for entry in rslt:
      if entry["url"] not in seen_urls:
          seen_urls.add(entry["url"])
          deduped.append(entry)
  ```
- Add diversity ranking:
  ```python
  from collections import Counter
  source_counts = Counter()
  ranked = []
  for entry in sorted(deduped, key=lambda x: x["timestamp"], reverse=True):
      # Penalize overrepresented sources
      penalty = source_counts[entry["sourceName"]] * 0.1
      entry["sort_score"] = entry["timestamp"] - penalty
      source_counts[entry["sourceName"]] += 1
  ranked = sorted(deduped, key=lambda x: x["sort_score"], reverse=True)
  ```

### 4. Fix error handling (critical)

**Goal:** Graceful degradation, don't lose all data on single feed failure.

**Changes:**
- Replace `sys.exit(0)` with continue and logging:
  ```python
  except Exception as e:
      if log:
          sys.stdout.write(f" - Failed: {e}\n")
      continue  # Process other feeds
  ```
- Add `"errors": []` to output JSON tracking failed feeds:
  ```python
  rslt = {
      "entries": entries_list,
      "created_at": int(time.time()),
      "errors": [{"source": source, "url": url, "error": str(e)} for ...]
  }
  ```
- Validate `feedparser.parse()` result:
  ```python
  if d.bozo and not d.entries:  # Parse failed
      raise ValueError(f"Feed parse error: {d.bozo_exception}")
  ```

### 5. Add observability to Perceive (important)

**Goal:** Understand ingestion patterns, debug issues.

**Changes:**
- Make logging non-optional, write to `~/.rreader/fetch.log`
- Log metrics per category:
  ```python
  metrics = {
      "category": category,
      "feeds_attempted": len(urls),
      "feeds_succeeded": success_count,
      "entries_fetched": len(rslt),
      "duration_seconds": end_time - start_time
  }
  ```
- Add to output JSON: `"fetch_metadata": metrics`

### 6. Add Cache TTL (important)

**Goal:** Prevent serving stale data, free disk space.

**Changes:**
- At start of `do()`, scan data files:
  ```python
  for json_file in glob.glob(os.path.join(p["path_data"], "rss_*.json")):
      with open(json_file) as f:
          data = json.load(f)
      age_hours = (time.time() - data["created_at"]) / 3600
      if age_hours > 24:  # Configurable
          os.remove(json_file)
  ```
- Filter entries older than 30 days from output before writing

### 7. Add integrity checks to Remember (important)

**Goal:** Recover from corrupted state.

**Changes:**
- Wrap all `json.load()` calls:
  ```python
  def safe_load_json(path, default=None):
      try:
          with open(path) as f:
              return json.load(f)
      except (json.JSONDecodeError, FileNotFoundError):
          return default or {}
  ```
- Atomic writes using temp files:
  ```python
  temp_path = output_path + ".tmp"
  with open(temp_path, "w") as f:
      f.write(json.dumps(rslt))
  os.replace(temp_path, output_path)  # Atomic on POSIX
  ```

### 8. Add incremental updates (nice-to-have)

**Goal:** Reduce bandwidth, faster refreshes.

**Changes:**
- Store ETags and Last-Modified headers:
  ```python
  d = feedparser.parse(url, etag=cached_etag, modified=cached_modified)
  if d.status == 304:  # Not modified
      continue
  cache_headers[url] = {
      "etag": d.get("etag"),
      "modified": d.get("modified")
  }
  ```

### 9. Add rate limiting (nice-to-have)

**Goal:** Be a good citizen, avoid blocks.

**Changes:**
- Add delay between fetches:
  ```python
  time.sleep(1)  # After each feedparser.parse()
  ```
- Implement per-domain rate limiting with `collections.defaultdict` tracking last fetch time

### 10. Add concurrent fetching (nice-to-have)

**Goal:** Faster updates with many feeds.

**Changes:**
- Use `concurrent.futures.ThreadPoolExecutor`:
  ```python
  with ThreadPoolExecutor(max_workers=5) as executor:
      futures = {executor.submit(fetch_one_feed, src, url): src 
                 for src, url in urls.items()}
      for future in as_completed(futures):
          results.extend(future.result())
  ```