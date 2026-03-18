# Diagnostic Report: RSS Feed Reader System

## Observations

This system currently implements a basic RSS feed aggregator with the following working capabilities:

1. **Perceive**: Fetches RSS feeds from URLs defined in a JSON configuration file using `feedparser`
2. **Cache**: Parses feed entries and extracts structured data (title, link, timestamp, author, publication date)
3. **Filter**: Applies minimal filtering by discarding entries without parseable timestamps
4. **Attend**: Sorts entries by timestamp (newest first) and deduplicates by using timestamp as ID
5. **Remember**: Persists aggregated feeds to JSON files (`rss_{category}.json`) with timestamp metadata
6. **Configuration management**: Copies bundled feeds, merges new categories into user config
7. **Time localization**: Converts UTC timestamps to configured timezone (KST/UTC+9)
8. **Category-based organization**: Processes feeds in groups with per-category author display settings

## Triage

### Critical gaps (blocking production use)

1. **Filter is shallow** - Only checks for timestamp presence, doesn't validate feed quality, detect malformed content, or handle duplicates across runs
2. **Consolidate is absent** - No learning mechanism. System never improves based on past results or adapts to feed behavior
3. **Error handling is incomplete** - Bare `except:` clauses swallow errors silently; partial failures corrupt state

### Important gaps (limit reliability)

4. **Attend is shallow** - Deduplication by timestamp fails when multiple entries share the same second; no diversity enforcement across sources
5. **Remember doesn't track history** - Each run overwrites previous results completely; no accumulation or change detection
6. **Perceive has no retry logic** - Network failures cause silent data loss with no recovery mechanism

### Quality gaps (technical debt)

7. **No rate limiting or politeness delays** - Could hammer feed servers or get blocked
8. **Timezone configuration is hardcoded** - Not user-configurable despite being application-level state
9. **No validation of feeds.json schema** - Malformed config causes runtime errors
10. **Logging is inconsistent** - Optional stdout writes mixed with exit codes; no structured logging

## Plan

### 1. Strengthen Filter (Critical)

**Current state**: Only `if not parsed_time: continue`

**Required changes**:
```python
# Add to get_feed_from_rss before the main loop
seen_urls = set()  # Deduplicate by URL across entries
quality_filters = {
    'max_title_length': 500,
    'required_fields': ['link', 'title'],
    'blocked_domains': []  # Load from config
}

# In the feed processing loop
# Validate required fields
if not all(hasattr(feed, field) for field in quality_filters['required_fields']):
    continue

# Deduplicate by URL
if feed.link in seen_urls:
    continue
seen_urls.add(feed.link)

# Length validation
if len(feed.title) > quality_filters['max_title_length']:
    continue

# Domain blocking
from urllib.parse import urlparse
if urlparse(feed.link).netloc in quality_filters['blocked_domains']:
    continue
```

**Add persistence of seen URLs**:
```python
# Load seen URLs from previous run
seen_file = os.path.join(p["path_data"], f"seen_{category}.json")
if os.path.exists(seen_file):
    with open(seen_file, 'r') as f:
        seen_urls = set(json.load(f).get('urls', []))

# After processing, save URLs from last 7 days
recent_urls = [e['url'] for e in rslt['entries'] 
               if time.time() - e['timestamp'] < 7*24*3600]
with open(seen_file, 'w') as f:
    json.dump({'urls': recent_urls}, f)
```

### 2. Implement Consolidate (Critical)

**Add learning mechanism**:
```python
# Create analytics file structure
analytics_file = os.path.join(p["path_data"], f"analytics_{category}.json")

def update_analytics(category, entries):
    """Track feed reliability and update fetch strategy"""
    if os.path.exists(analytics_file):
        with open(analytics_file, 'r') as f:
            analytics = json.load(f)
    else:
        analytics = {'sources': {}, 'last_updated': 0}
    
    # Track per-source metrics
    for entry in entries:
        source = entry['sourceName']
        if source not in analytics['sources']:
            analytics['sources'][source] = {
                'fetch_count': 0,
                'entry_count': 0,
                'last_entry_time': 0,
                'error_count': 0,
                'avg_entries_per_fetch': 0
            }
        
        stats = analytics['sources'][source]
        stats['entry_count'] += 1
        stats['last_entry_time'] = max(stats['last_entry_time'], 
                                       entry['timestamp'])
    
    analytics['last_updated'] = int(time.time())
    
    with open(analytics_file, 'w') as f:
        json.dump(analytics, f, indent=2)
    
    return analytics

# Use analytics to adjust behavior
def get_fetch_priority(analytics):
    """Sources with recent activity get fetched first"""
    priorities = {}
    current_time = time.time()
    for source, stats in analytics.get('sources', {}).items():
        recency = current_time - stats['last_entry_time']
        reliability = stats['entry_count'] / max(stats['fetch_count'], 1)
        priorities[source] = reliability / (1 + recency / 3600)  # Decay over hours
    return priorities
```

**Call in main flow**:
```python
# Before fetching
if os.path.exists(analytics_file):
    with open(analytics_file) as f:
        analytics = json.load(f)
    priorities = get_fetch_priority(analytics)
    # Sort URLs by priority before fetching
    urls = dict(sorted(urls.items(), 
                      key=lambda x: priorities.get(x[0], 0), 
                      reverse=True))

# After processing
update_analytics(category, rslt['entries'])
```

### 3. Fix Error Handling (Critical)

**Replace bare excepts**:
```python
import logging
logging.basicConfig(
    filename=os.path.join(p["path_data"], 'rreader.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# In get_feed_from_rss
for source, url in urls.items():
    try:
        logging.info(f"Fetching {source}: {url}")
        d = feedparser.parse(url)
        
        if d.bozo:  # feedparser error flag
            logging.warning(f"Feed parse warning for {source}: {d.bozo_exception}")
            
    except Exception as e:
        logging.error(f"Failed to fetch {source} ({url}): {e}")
        # Update analytics with error
        if 'analytics' in locals():
            analytics['sources'][source]['error_count'] += 1
        continue  # Don't exit, continue with other feeds

# Per-entry error handling
for feed in d.entries:
    try:
        # ... existing parsing logic ...
    except Exception as e:
        logging.warning(f"Skipping malformed entry from {source}: {e}")
        continue
```

### 4. Improve Attend with Better Deduplication (Important)

**Fix timestamp collision issue**:
```python
# Change ID generation to include URL hash
import hashlib

def generate_entry_id(timestamp, url):
    """Combine timestamp with URL hash for unique ID"""
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return f"{timestamp}_{url_hash}"

# In entry creation
entries = {
    "id": generate_entry_id(ts, feed.link),
    "timestamp": ts,
    # ... rest of fields
}

rslt[entries["id"]] = entries

# Sort by extracting timestamp from composite ID
rslt = [val for key, val in sorted(rslt.items(), 
        key=lambda x: x[1]['timestamp'], reverse=True)]
```

**Add diversity enforcement**:
```python
def enforce_diversity(entries, max_per_source=5):
    """Limit entries per source in final output"""
    source_counts = {}
    diverse_entries = []
    
    for entry in entries:
        source = entry['sourceName']
        count = source_counts.get(source, 0)
        
        if count < max_per_source:
            diverse_entries.append(entry)
            source_counts[source] = count + 1
    
    return diverse_entries

# Apply before saving
rslt["entries"] = enforce_diversity(rslt["entries"])
```

### 5. Implement Incremental Remember (Important)

**Track history instead of overwriting**:
```python
def save_with_history(category, new_entries, max_age_days=30):
    """Merge new entries with existing, pruning old ones"""
    output_file = os.path.join(p["path_data"], f"rss_{category}.json")
    
    existing_entries = []
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            existing_data = json.load(f)
            existing_entries = existing_data.get('entries', [])
    
    # Create map of existing entries by ID
    existing_map = {e['id']: e for e in existing_entries}
    
    # Merge: new entries override existing with same ID
    for entry in new_entries:
        existing_map[entry['id']] = entry
    
    # Prune entries older than max_age_days
    cutoff_time = time.time() - (max_age_days * 24 * 3600)
    merged = [e for e in existing_map.values() 
              if e['timestamp'] > cutoff_time]
    
    # Sort by timestamp
    merged.sort(key=lambda x: x['timestamp'], reverse=True)
    
    result = {
        "entries": merged,
        "created_at": int(time.time()),
        "entry_count": len(merged)
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    return result

# Replace the existing save logic
rslt = save_with_history(category, rslt)
```

### 6. Add Retry Logic to Perceive (Important)

**Implement exponential backoff**:
```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

def create_session():
    """Create requests session with retry logic"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,  # Wait 1, 2, 4 seconds
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

# Modify feedparser call
session = create_session()
try:
    response = session.get(url, timeout=10)
    d = feedparser.parse(response.content)
except requests.exceptions.RequestException as e:
    logging.error(f"Network error fetching {url}: {e}")
    continue
```

### 7. Add Rate Limiting (Quality)

**Implement politeness delays**:
```python
import time
from datetime import datetime

def polite_fetch(urls, min_delay=1.0):
    """Fetch URLs with delays between requests"""
    results = {}
    
    for i, (source, url) in enumerate(urls.items()):
        if i > 0:  # Don't delay first request
            time.sleep(min_delay)
        
        # ... fetch logic ...
        results[source] = d
    
    return results
```

### 8. Make Timezone Configurable (Quality)

**Move to user config**:
```python
# In feeds.json schema, add top-level config
{
    "config": {
        "timezone_offset_hours": 9,
        "max_entries_per_source": 5,
        "feed_max_age_days": 30
    },
    "categories": {
        "tech": {"feeds": {...}}
    }
}

# Load in code
with open(FEEDS_FILE_NAME, 'r') as fp:
    data = json.load(fp)
    config = data.get('config', {})
    RSS = data.get('categories', data)  # Backward compatible
    
TIMEZONE = datetime.timezone(
    datetime.timedelta(hours=config.get('timezone_offset_hours', 9))
)
```

### 9. Add Config Validation (Quality)

**Validate on load**:
```python
import jsonschema

FEEDS_SCHEMA = {
    "type": "object",
    "patternProperties": {
        ".*": {
            "type": "object",
            "required": ["feeds"],
            "properties": {
                "feeds": {
                    "type": "object",
                    "patternProperties": {
                        ".*": {"type": "string", "format": "uri"}
                    }
                },
                "show_author": {"type": "boolean"}
            }
        }
    }
}

def validate_feeds_config(config):
    try:
        jsonschema.validate(instance=config, schema=FEEDS_SCHEMA)
        return True, None
    except jsonschema.exceptions.ValidationError as e:
        return False, str(e)

# Use before processing
valid, error = validate_feeds_config(RSS)
if not valid:
    logging.error(f"Invalid feeds.json: {error}")
    sys.exit(1)
```

### 10. Implement Structured Logging (Quality)

**Replace print/stdout with logging**:
```python
# Remove log parameter, always use logging
def get_feed_from_rss(category, urls, show_author=False):
    # Replace sys.stdout.write with:
    logging.info(f"Fetching {source}: {url}")
    # ...
    logging.info(f"Processed {len(rslt['entries'])} entries for {category}")
```