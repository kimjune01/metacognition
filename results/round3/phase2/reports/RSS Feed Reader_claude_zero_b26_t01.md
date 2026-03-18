# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently provides the following working capabilities:

1. **RSS Feed Parsing**: Fetches and parses RSS feeds from multiple sources using the `feedparser` library.

2. **Multi-Category Support**: Organizes feeds into categories, with each category containing multiple feed sources.

3. **Feed Configuration Management**: 
   - Stores feed configurations in a JSON file (`feeds.json`)
   - Copies bundled default feeds on first run
   - Merges new categories from bundled feeds into user configuration

4. **Timestamp Handling**: Converts feed publication times to a configured timezone (currently KST/UTC+9) and formats them intelligently (showing "HH:MM" for today's items, "Mon DD, HH:MM" for older items).

5. **Data Persistence**: Saves parsed feed entries to JSON files (`rss_{category}.json`) in a data directory (`~/.rreader/`).

6. **Deduplication**: Uses timestamp as ID to prevent duplicate entries within a single fetch operation.

7. **Selective Updates**: Can update a specific category via `target_category` parameter or all categories.

8. **Optional Logging**: Provides progress output when `log=True`.

9. **Author Attribution**: Supports optional `show_author` flag per category to display feed author instead of source name.

## Triage

### Critical Gaps

1. **No Error Recovery**: The bare `except:` clause on line 25 calls `sys.exit()`, terminating the entire process if any single feed fails. In a multi-feed system, one broken URL kills everything.

2. **Missing Configuration Validation**: No validation that `feeds.json` has the expected structure. Malformed JSON or missing keys will crash with cryptic errors.

3. **Collision-Prone ID System**: Using timestamp as ID means multiple entries published in the same second overwrite each other (line 59: `rslt[entries["id"]] = entries`).

### High Priority Gaps

4. **No Rate Limiting**: Fetching many feeds rapidly could trigger rate limits or be seen as abusive behavior.

5. **No Caching Headers**: Ignores ETags and Last-Modified headers, wasting bandwidth by re-downloading unchanged feeds.

6. **No Timeout Configuration**: `feedparser.parse()` has no timeout, so hung connections can block indefinitely.

7. **Timezone Configuration Hardcoded**: `TIMEZONE` is hardcoded to KST; should be user-configurable.

8. **No Feed Metadata Stored**: Doesn't track when each feed was last successfully updated or preserve historical fetch status.

### Medium Priority Gaps

9. **Silent Timestamp Parsing Failures**: The `try/except` on line 37 silently skips entries with bad timestamps, providing no visibility into data loss.

10. **No Entry Limit**: Unbounded entry lists could cause memory issues with prolific feeds or initial fetches of feeds with long histories.

11. **No Stale Data Handling**: Old cached JSON files persist indefinitely with no indication they're outdated.

12. **Inconsistent Date Comparison**: Line 41 compares `at.date()` to `datetime.date.today()` without ensuring both are in the same timezone.

13. **No User Feedback on Success**: When `log=False`, the system provides no indication of success, failure counts, or entries retrieved.

### Low Priority Gaps

14. **No Feed Discovery**: Users must manually add feed URLs; no OPML import or feed auto-discovery.

15. **No Entry Content Storage**: Only stores title and link, not summary/description or content.

16. **Inefficient Bundled Feed Updates**: Always reads both files and merges, even when no updates exist.

## Plan

### For Gap #1 (Error Recovery)
**Changes needed:**
- Replace `except:` on line 24 with specific exception handling for `feedparser.parse()` errors
- Log the error with feed URL and continue to next feed instead of calling `sys.exit()`
- Track failed feeds and return/log a summary at the end
- Example pattern:
```python
failed_feeds = []
for source, url in urls.items():
    try:
        d = feedparser.parse(url)
        # ... process ...
    except Exception as e:
        failed_feeds.append((source, url, str(e)))
        if log:
            sys.stderr.write(f" - Failed: {e}\n")
        continue
```

### For Gap #2 (Configuration Validation)
**Changes needed:**
- Create a `validate_feeds_config(config)` function
- Check that config is a dict with string keys
- For each category, verify `feeds` key exists and is a dict
- Verify `show_author` is boolean if present
- Call validation after loading `feeds.json` (after line 88)
- Provide helpful error messages indicating which category/field is invalid

### For Gap #3 (ID Collision)
**Changes needed:**
- Change ID generation on line 48 from just timestamp to include uniqueness
- Options:
  - Use `f"{ts}_{hash(feed.link)}"` to include URL hash
  - Use `feed.id` if available, fallback to generated ID
  - Use counter: `f"{ts}_{source}_{idx}"`
- Update line 59 to use the new unique ID

### For Gap #4 (Rate Limiting)
**Changes needed:**
- Add `time.sleep()` between feed fetches in the loop (after line 26)
- Make sleep duration configurable, default to 1-2 seconds
- Add configuration to `feeds.json` like `"fetch_delay_seconds": 1.0`
- For category-specific fetching, shorter delay may be acceptable

### For Gap #5 (Caching Headers)
**Changes needed:**
- Store ETag and Last-Modified headers from previous fetch in metadata file
- Pass these headers to `feedparser.parse(url, etag=..., modified=...)`
- Check `d.status` - if 304 (Not Modified), skip processing and reuse cached data
- Save new ETag/Last-Modified values for next fetch
- Create metadata file: `rss_{category}_meta.json`

### For Gap #6 (Timeout Configuration)
**Changes needed:**
- Configure socket timeout before calling feedparser
- Add at module level before `get_feed_from_rss()`:
```python
import socket
socket.setdefaulttimeout(30)  # or make configurable
```
- Or use requests library with timeout, pass to feedparser

### For Gap #7 (Timezone Configuration)
**Changes needed:**
- Move TIMEZONE from `config.py` constant to user configuration
- Add `"timezone_offset_hours": 9` to `feeds.json` or separate config
- Parse at runtime: `datetime.timezone(datetime.timedelta(hours=config['timezone_offset_hours']))`
- Provide default fallback to UTC if not configured

### For Gap #8 (Feed Metadata)
**Changes needed:**
- Create metadata structure per category tracking:
  - Last successful fetch timestamp
  - Last error and timestamp
  - Entry count from last fetch
- Save to `rss_{category}_meta.json` alongside data file
- Include `created_at` as currently done, but add more fields

### For Gap #9 (Timestamp Parsing Visibility)
**Changes needed:**
- Add counter for skipped entries
- Log warnings when entries are skipped due to missing/invalid timestamps:
```python
if not parsed_time:
    if log:
        sys.stderr.write(f"  Warning: Skipping entry '{feed.title}' - no timestamp\n")
    continue
```
- Include skip count in return value or summary

### For Gap #10 (Entry Limit)
**Changes needed:**
- Add configuration parameter `"max_entries_per_category": 100`
- After sorting entries (line 66), slice the list: `rslt = rslt[:max_entries]`
- Make limit configurable per-category or global

### For Gap #11 (Stale Data Handling)
**Changes needed:**
- Add `created_at` timestamp check when reading cached files
- Display staleness indicator (e.g., "Last updated: 2 hours ago")
- Add configuration for maximum acceptable cache age
- Optionally auto-refresh if cache exceeds age threshold

### For Gap #12 (Date Comparison Timezone)
**Changes needed:**
- Line 41: Replace `datetime.date.today()` with `datetime.datetime.now(TIMEZONE).date()`
- This ensures both dates are in the configured timezone

### For Gap #13 (User Feedback)
**Changes needed:**
- Return statistics dictionary with counts:
  - Feeds attempted/succeeded/failed
  - Total entries fetched
  - Time taken
- When `log=True`, print summary at end
- When `log=False`, at minimum return this data for programmatic use

### For Gap #14 (Feed Discovery)
**Changes needed:**
- Add `add_feed(category, source_name, url)` function
- Add OPML import function: `import_opml(opml_file_path)`
- Use feedparser's or separate library's OPML parsing
- Add to feeds.json and save

### For Gap #15 (Entry Content Storage)
**Changes needed:**
- Add to entries dict (after line 59):
```python
"summary": getattr(feed, 'summary', ''),
"content": getattr(feed, 'content', [{}])[0].get('value', ''),
```
- Make this optional/configurable as it increases storage significantly

### For Gap #16 (Bundled Feed Updates)
**Changes needed:**
- Add version number to bundled `feeds.json`
- Track version in user's `feeds.json`
- Only perform merge if versions differ
- Or add `last_bundled_check` timestamp and check daily rather than every run