# Diagnostic Report: RSS Feed Reader

## Observations

This system is an RSS feed aggregator that:

1. **Perceives:** Fetches RSS feeds from URLs using `feedparser`
2. **Cache:** Parses feeds and extracts entries with metadata (title, link, timestamp, author)
3. **Filter:** Implicitly filters entries without valid timestamps (skips entries missing `published_parsed` or `updated_parsed`)
4. **Attend:** Sorts entries by timestamp (descending) and deduplicates by ID (timestamp collision handling via dict)
5. **Remember:** Persists parsed feeds to JSON files (`rss_{category}.json`) with creation timestamp
6. **Consolidate:** Absent - no learning or adaptation mechanism

Current working capabilities:
- Multi-category feed management
- Timezone-aware timestamp conversion (UTC → KST)
- User feed configuration with fallback to bundled defaults
- Time-based deduplication (uses timestamp as ID)
- Chronological presentation (newest first)

## Triage

### Critical Gaps

**1. Consolidate stage is completely missing**
- **Impact:** System cannot learn from user behavior, adapt to feed quality, or optimize over time
- **Priority:** High - this is the only completely absent stage

**2. Filter stage is too shallow**
- **Impact:** Accepts malformed entries, duplicate content, spam, dead links
- **Priority:** High - affects data quality directly

**3. Attend stage lacks true prioritization**
- **Impact:** No relevance ranking, no diversity enforcement, no user preference application
- **Priority:** Medium - sorting by time is minimal but functional

### Important Missing Features

**4. Error handling is inadequate**
- **Impact:** Silent failures, no retry logic, bare except clauses mask problems
- **Priority:** High - affects reliability

**5. No incremental updates**
- **Impact:** Refetches all feeds every run, wastes bandwidth, stresses sources
- **Priority:** Medium - affects scalability and politeness

**6. Remember stage doesn't track read/unread state**
- **Impact:** Users can't mark items as read or track consumption
- **Priority:** Medium - affects usability

**7. No feed health monitoring**
- **Impact:** Can't detect stale feeds, removed sources, or degraded quality
- **Priority:** Low - operational concern

## Plan

### 1. Add Consolidate Stage (Learning Loop)

**Create a feedback collection system:**
```python
# New file: feedback.py
def record_click(category, entry_id, clicked_at):
    """Log when user clicks an entry"""
    feedback_file = os.path.join(p["path_data"], "feedback.json")
    # Append click event with timestamp

def record_dismiss(category, entry_id):
    """Log when user hides/dismisses an entry"""
    # Track negative feedback

def update_source_weights(category):
    """Analyze feedback and adjust source priorities"""
    # Calculate CTR per source
    # Update weights in feeds.json
    # Sources with higher engagement get priority
```

**Modify `get_feed_from_rss` to apply learned weights:**
```python
def get_feed_from_rss(category, urls, show_author=False, log=False):
    # Load source weights
    weights = load_source_weights(category)
    
    # After collecting entries, apply weighted ranking
    for entry in rslt.values():
        source_weight = weights.get(entry['sourceName'], 1.0)
        entry['score'] = entry['timestamp'] * source_weight
    
    # Sort by score instead of just timestamp
    rslt = [val for key, val in sorted(rslt.items(), 
            key=lambda x: x[1]['score'], reverse=True)]
```

### 2. Strengthen Filter Stage

**Add comprehensive validation:**
```python
def validate_entry(entry, seen_urls, seen_titles):
    """Return True if entry should be kept"""
    
    # Check required fields
    if not all([entry.get('link'), entry.get('title')]):
        return False
    
    # URL validation
    if not entry['link'].startswith(('http://', 'https://')):
        return False
    
    # Deduplication by URL
    if entry['link'] in seen_urls:
        return False
    seen_urls.add(entry['link'])
    
    # Near-duplicate detection by title
    normalized_title = entry['title'].lower().strip()
    if normalized_title in seen_titles:
        return False
    seen_titles.add(normalized_title)
    
    # Content quality checks
    if len(entry['title']) < 10:  # Too short
        return False
    if entry['title'].count('🔥') > 3:  # Spam indicators
        return False
    
    return True
```

**Apply in feed parsing:**
```python
seen_urls = set()
seen_titles = set()

for feed in d.entries:
    entries = {...}  # Build entry dict
    
    if not validate_entry(entries, seen_urls, seen_titles):
        continue  # Skip invalid entries
    
    rslt[entries["id"]] = entries
```

### 3. Enhance Attend Stage

**Add diversity and relevance:**
```python
def rank_entries(entries, category_config):
    """Apply multi-factor ranking"""
    scored = []
    
    for entry in entries:
        score = 0
        
        # Recency (decaying)
        age_hours = (time.time() - entry['timestamp']) / 3600
        score += 100 * math.exp(-age_hours / 24)  # Decay over 24h
        
        # Source weight (from consolidation)
        score += entry.get('source_weight', 1.0) * 50
        
        # Diversity penalty (avoid source clustering)
        recent_from_source = count_recent_from_source(
            scored, entry['sourceName'], limit=3
        )
        score -= recent_from_source * 20
        
        scored.append((score, entry))
    
    return [e for _, e in sorted(scored, reverse=True)]
```

### 4. Improve Error Handling

**Replace bare excepts with specific handling:**
```python
import logging
from urllib.error import URLError
from socket import timeout

logging.basicConfig(filename=os.path.join(p["path_data"], "rreader.log"))

def fetch_with_retry(url, max_retries=3):
    """Fetch with exponential backoff"""
    for attempt in range(max_retries):
        try:
            return feedparser.parse(url)
        except (URLError, timeout) as e:
            logging.warning(f"Fetch failed for {url}: {e}, attempt {attempt+1}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logging.error(f"Failed permanently: {url}")
                return None
        except Exception as e:
            logging.error(f"Unexpected error for {url}: {e}")
            return None
```

### 5. Add Incremental Updates

**Track last fetch time per feed:**
```python
def load_fetch_state(category):
    """Load last successful fetch timestamps"""
    state_file = os.path.join(p["path_data"], f"state_{category}.json")
    if os.path.exists(state_file):
        with open(state_file) as f:
            return json.load(f)
    return {}

def should_fetch(source, state, min_interval=300):
    """Check if enough time has passed"""
    last_fetch = state.get(source, 0)
    return time.time() - last_fetch > min_interval

def update_fetch_state(category, source, timestamp):
    """Record successful fetch"""
    state = load_fetch_state(category)
    state[source] = timestamp
    state_file = os.path.join(p["path_data"], f"state_{category}.json")
    with open(state_file, 'w') as f:
        json.dump(state, f)
```

### 6. Add Read/Unread Tracking

**Extend Remember stage:**
```python
def mark_as_read(category, entry_ids):
    """Persist read state"""
    read_file = os.path.join(p["path_data"], f"read_{category}.json")
    read_set = load_read_set(read_file)
    read_set.update(entry_ids)
    with open(read_file, 'w') as f:
        json.dump(list(read_set), f)

def annotate_read_status(entries, category):
    """Add 'read' field to entries"""
    read_set = load_read_set(...)
    for entry in entries:
        entry['read'] = entry['id'] in read_set
    return entries
```

### 7. Add Feed Health Monitoring

**Track and report metrics:**
```python
def update_feed_health(category, source, success, entry_count):
    """Track feed reliability"""
    health_file = os.path.join(p["path_data"], "feed_health.json")
    health = load_health(health_file)
    
    if source not in health:
        health[source] = {
            'successes': 0, 'failures': 0, 
            'last_success': None, 'avg_entries': 0
        }
    
    if success:
        health[source]['successes'] += 1
        health[source]['last_success'] = time.time()
        # Update rolling average of entry count
    else:
        health[source]['failures'] += 1
    
    save_health(health_file, health)

def get_stale_feeds(max_age_days=7):
    """Identify feeds that haven't updated"""
    health = load_health(...)
    stale = []
    cutoff = time.time() - (max_age_days * 86400)
    for source, stats in health.items():
        if stats['last_success'] and stats['last_success'] < cutoff:
            stale.append(source)
    return stale
```