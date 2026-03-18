# Diagnostic Report: RSS Feed Reader System

## Observations

This system fetches RSS feeds and stores them as JSON files. Current working capabilities:

1. **Perceive**: Reads RSS/Atom feeds from URLs using `feedparser`
2. **Cache**: Writes parsed entries to JSON files (`rss_{category}.json`) with timestamp-indexed structure
3. **Filter**: Performs minimal filtering—skips entries without parseable timestamps
4. **Attend**: Sorts entries by timestamp (newest first), deduplicates by timestamp-as-ID
5. **Remember**: Persists feed data to disk in the `.rreader/` directory
6. **Configuration management**: Merges bundled feeds with user feeds, preserving user customizations

The system processes multiple feed categories, normalizes timestamps to a configured timezone, and formats publication dates for display.

## Triage

### Critical gaps (breaks core use case):

1. **Consolidate is absent** — No backward pass. The system never learns which articles were read, clicked, or ignored. It re-fetches and re-processes identically every time.

2. **Attend is shallow** — Deduplication uses timestamp as ID, causing collisions when multiple articles publish in the same second. No diversity enforcement across sources. No quality ranking beyond recency.

3. **Filter is shallow** — Only rejects unparseable dates. Accepts duplicates across runs, malformed content, irrelevant articles, and spam.

### Important gaps (limits usefulness):

4. **Cache doesn't track provenance** — No record of what was fetched when. Can't tell if an entry is new or was seen before.

5. **Error handling is destructive** — Silent `sys.exit(0)` on fetch failure. Bare `except:` clauses swallow all errors including keyboard interrupts.

6. **No incremental updates** — Overwrites entire category file on each run. If a feed is temporarily down, all its previous entries vanish.

### Quality gaps (technical debt):

7. **No retry logic** — Network blips cause permanent data loss for that run.

8. **No rate limiting** — Could hammer servers or trigger rate limits when processing many feeds.

9. **No validation of stored data** — Doesn't verify JSON integrity before overwriting.

## Plan

### 1. Add Consolidate (backward pass)

**What to change:**

- Create a new file `rss_{category}_history.json` that tracks:
  ```json
  {
    "seen_ids": ["url1", "url2", ...],
    "clicked_ids": ["url3", ...],
    "last_update_per_source": {"source1": timestamp, ...}
  }
  ```

- Before writing new entries, load history and mark entries as `"is_new": true/false`

- Provide a mechanism (CLI command or function call) to record when URLs are clicked/read

- Use click history to boost sources that get engagement, demote sources that don't

**Files to modify:**
- `do()`: Load history at start, merge with new entries, write updated history
- Add new function: `mark_read(category, entry_id)`

### 2. Fix Attend (proper deduplication and ranking)

**What to change:**

- Replace timestamp-based ID with content hash:
  ```python
  import hashlib
  entry_id = hashlib.sha256(f"{feed.link}|{feed.title}".encode()).hexdigest()[:16]
  ```

- Add diversity ranking after time-sort:
  ```python
  def diversify(entries, max_per_source=3):
      source_counts = {}
      result = []
      for e in entries:
          count = source_counts.get(e['sourceName'], 0)
          if count < max_per_source:
              result.append(e)
              source_counts[e['sourceName']] = count + 1
      return result
  ```

- Apply before writing: `rslt["entries"] = diversify(rslt, max_per_source=3)`

**Files to modify:**
- `get_feed_from_rss()`: Change ID generation and add diversity pass

### 3. Strengthen Filter

**What to change:**

- Add quality checks before adding to `rslt`:
  ```python
  def should_accept(feed, seen_urls):
      if feed.link in seen_urls:
          return False  # Duplicate across runs
      if len(feed.title.strip()) < 10:
          return False  # Too short
      if not feed.link.startswith(('http://', 'https://')):
          return False  # Invalid URL
      # Add keyword filters from config
      return True
  ```

- Load seen URLs from history (links to gap #1)

- Add optional `"reject_keywords": [...]` to feed config

**Files to modify:**
- `get_feed_from_rss()`: Add validation before `entries = {...}`
- `feeds.json` schema: Add optional filtering rules per category

### 4. Track Cache provenance

**What to change:**

- Add metadata to each entry:
  ```python
  entries = {
      "id": entry_id,
      "first_seen": ts,  # When we first fetched it
      "last_seen": ts,   # Updated if seen again
      "fetch_count": 1,  # How many times appeared in feed
      # ... existing fields
  }
  ```

- When merging with history, update `last_seen` and `fetch_count` for duplicates

**Files to modify:**
- `get_feed_from_rss()`: Merge logic with historical data

### 5. Fix error handling

**What to change:**

- Replace bare `except:` with specific exceptions:
  ```python
  except (ConnectionError, TimeoutError, feedparser.ParseError) as e:
      if log:
          sys.stderr.write(f" - Failed: {e}\n")
      continue  # Process other feeds
  ```

- Remove `sys.exit(0)` — should continue with other feeds

- Add warnings for unparseable dates instead of silent continue

**Files to modify:**
- Both try/except blocks in `get_feed_from_rss()`

### 6. Implement incremental updates

**What to change:**

- Before overwriting, load existing file:
  ```python
  existing_file = os.path.join(p["path_data"], f"rss_{category}.json")
  if os.path.exists(existing_file):
      with open(existing_file, 'r') as f:
          old_data = json.load(f)
      # Merge old_data['entries'] with new rslt
  ```

- Keep entries from sources that failed this run

- Add `"last_successful_fetch"` per source in metadata

**Files to modify:**
- `get_feed_from_rss()`: Load and merge before write

### 7. Add retry logic

**What to change:**

- Wrap `feedparser.parse()`:
  ```python
  from time import sleep
  
  def fetch_with_retry(url, retries=3, delay=2):
      for attempt in range(retries):
          try:
              return feedparser.parse(url)
          except Exception as e:
              if attempt == retries - 1:
                  raise
              sleep(delay * (attempt + 1))
  ```

**Files to modify:**
- `get_feed_from_rss()`: Replace direct `feedparser.parse()` call

### 8. Add rate limiting

**What to change:**

- Add delay between fetches:
  ```python
  import time
  
  for source, url in urls.items():
      time.sleep(0.5)  # 500ms between requests
      # ... existing fetch logic
  ```

- Make configurable: `RSS[category].get("fetch_delay", 0.5)`

**Files to modify:**
- `get_feed_from_rss()`: Add sleep in loop

### 9. Validate before overwriting

**What to change:**

- Write to temporary file first:
  ```python
  temp_file = output_file + ".tmp"
  with open(temp_file, 'w', encoding='utf-8') as f:
      f.write(json.dumps(rslt, ensure_ascii=False))
  
  # Verify it's valid
  with open(temp_file, 'r') as f:
      json.load(f)  # Will raise if invalid
  
  # Atomic replace
  os.replace(temp_file, output_file)
  ```

**Files to modify:**
- `get_feed_from_rss()`: Replace direct write with temp-and-verify pattern

---

**Recommended implementation order**: 5 → 2 → 3 → 6 → 1 → 4 → 7 → 8 → 9

Fix error handling first (prevents data loss), then improve ranking and filtering (makes output useful), then add learning (makes it get better over time).