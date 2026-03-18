# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Deckstring format, a compact binary encoding for Hearthstone deck lists. Current capabilities:

1. **Perceive**: Reads base64-encoded deckstrings via `parse_deckstring()` and `Deck.from_deckstring()`
2. **Cache**: Stores decoded deck data in structured form (`Deck` object with `cards`, `heroes`, `sideboards`, `format`)
3. **Filter**: Validates deckstring format (magic byte check, version check, format enum validation)
4. **Remember**: Persists deck state in the `Deck` object across method calls
5. **Encode/Decode**: Bidirectional conversion between deckstrings and structured data via varint encoding
6. **Sorting**: Normalizes card lists by ID and count for consistent output

The system successfully handles:
- Variable-length integer encoding/decoding
- Card grouping by count (1x, 2x, n×)
- Sideboard cards with ownership tracking
- Format type enum mapping

## Triage

### Critical gaps

**1. Attend stage is absent**
- No prioritization or ranking of cards
- No duplicate detection across main deck and sideboard
- No diversity enforcement or relevance scoring
- Impact: Users can't find "what matters most" in a deck

**2. Consolidate stage is absent**
- System processes identically every time
- No learning from parse history or error patterns
- No optimization of common deck patterns
- Impact: Can't improve performance or adapt to meta changes

**3. Filter stage is shallow**
- Only checks format compliance (version, magic byte, enum validity)
- Doesn't validate deck construction rules (card limits, format legality, total count)
- No card ID existence validation
- Impact: Invalid decks pass through silently

### Important gaps

**4. Error handling is fragile**
- `EOFError` in `_read_varint` but no recovery
- No partial parse capability
- ValueError messages lack context (which card failed?)
- No logging or telemetry

**5. No query interface**
- `get_dbf_id_list()` only returns sorted tuples
- Can't filter by mana cost, rarity, or card type
- No aggregation (total dust cost, curve analysis)
- No search by card name or text

**6. No metadata tracking**
- No timestamps (when was deck created/modified?)
- No provenance (where did this deckstring come from?)
- No validation checksums

## Plan

### To add Attend (priority 1)

**What to change:**
1. Add `Deck.get_curve()` method that returns mana cost distribution (requires external card database)
2. Add `Deck.get_duplicates()` to detect cards in both main deck and sideboard
3. Add `Deck.rank_by_importance(card_db, meta_stats)` that scores cards by:
   - Play rate in current meta
   - Win rate when drawn
   - Deck archetype centrality
4. Add `Deck.find_similar(other_deck)` using Jaccard similarity on card IDs

**Concrete implementation:**
```python
def rank_by_importance(self, card_db, meta_stats=None):
    """Return cards sorted by importance with scores."""
    scores = []
    for cardid, count in self.cards:
        score = 0.0
        # Base score: card count (higher = core card)
        score += count * 10
        # Meta score: how often card appears in winning decks
        if meta_stats:
            score += meta_stats.get(cardid, {}).get('win_rate', 0) * 100
        scores.append((cardid, count, score))
    return sorted(scores, key=lambda x: x[2], reverse=True)
```

### To deepen Filter (priority 2)

**What to change:**
1. Add deck construction validation in `Deck.__init__` or `from_deckstring`:
   - Check total card count (30 for Standard/Wild)
   - Enforce card limits (max 1 for Legendary, max 2 for others)
   - Validate hero/class restrictions
   - Check format legality (Standard vs Wild card pool)
2. Add `validate()` method that returns `(is_valid, errors: List[str])`
3. Create custom exception hierarchy: `InvalidDeckstringError`, `DeckConstructionError`

**Concrete implementation:**
```python
class DeckConstructionError(ValueError):
    pass

def validate(self, card_db) -> Tuple[bool, List[str]]:
    errors = []
    
    # Check card count
    total = sum(count for _, count in self.cards)
    if total != 30:
        errors.append(f"Deck has {total} cards, expected 30")
    
    # Check card limits
    for cardid, count in self.cards:
        card_data = card_db.get(cardid)
        if not card_data:
            errors.append(f"Unknown card ID {cardid}")
            continue
        max_count = 1 if card_data.rarity == 'LEGENDARY' else 2
        if count > max_count:
            errors.append(f"Card {cardid} has {count} copies, max {max_count}")
    
    return len(errors) == 0, errors
```

### To add Consolidate (priority 3)

**What to change:**
1. Create `DeckHistory` class that tracks parse operations:
   - Store parse timestamps, success/failure rates
   - Record frequent deck archetypes
   - Cache card co-occurrence patterns
2. Add `DeckHistory.suggest_corrections(deck)` that uses historical patterns to fix common errors
3. Add `DeckHistory.optimize_encoding()` that reorders cards for faster parsing based on access patterns

**Concrete implementation:**
```python
class DeckHistory:
    def __init__(self, storage_path):
        self.storage = storage_path
        self.parse_count = 0
        self.error_patterns = defaultdict(int)
        self.archetype_signatures = {}  # Map card sets to archetype names
    
    def record_parse(self, deck, success, error=None):
        self.parse_count += 1
        if not success and error:
            self.error_patterns[type(error).__name__] += 1
        # Learn archetype signatures
        card_set = frozenset(c[0] for c in deck.cards)
        self.archetype_signatures[card_set] = \
            self.archetype_signatures.get(card_set, 0) + 1
    
    def suggest_archetype(self, deck):
        """Return likely archetype based on card overlap."""
        card_set = frozenset(c[0] for c in deck.cards)
        best_match = None
        best_score = 0
        for known_set, count in self.archetype_signatures.items():
            overlap = len(card_set & known_set)
            score = overlap * count
            if score > best_score:
                best_score = score
                best_match = known_set
        return best_match
```

### To improve error handling (priority 4)

**What to change:**
1. Wrap `parse_deckstring` body in try/except with context
2. Add optional `strict=True` parameter to raise or return partial decks
3. Add logging throughout parse operations
4. Include byte offset in error messages

**Concrete implementation:**
```python
def parse_deckstring(deckstring, strict=True, logger=None):
    try:
        decoded = base64.b64decode(deckstring)
    except Exception as e:
        msg = f"Failed to decode base64: {e}"
        if logger:
            logger.error(msg)
        if strict:
            raise InvalidDeckstringError(msg) from e
        return [], [], FormatType.FT_UNKNOWN, []
    
    data = BytesIO(decoded)
    offset = 0
    
    try:
        # Track byte offset for error reporting
        # ... existing parse logic ...
    except EOFError as e:
        msg = f"Truncated deckstring at byte {data.tell()}"
        if logger:
            logger.error(msg)
        if strict:
            raise InvalidDeckstringError(msg) from e
        # Return partial deck
```

### To add query interface (priority 5)

**What to change:**
1. Add `Deck.filter_cards(predicate)` that takes a function
2. Add convenience methods: `get_by_cost(n)`, `get_by_rarity(r)`, `count_by_type()`
3. Add `Deck.stats(card_db)` that returns total dust, curve, class distribution

**Concrete implementation:**
```python
def filter_cards(self, predicate, card_db):
    """Filter cards using predicate function."""
    return [(cid, cnt) for cid, cnt in self.cards 
            if predicate(card_db[cid])]

def get_curve(self, card_db):
    """Return mana cost distribution."""
    curve = defaultdict(int)
    for cardid, count in self.cards:
        cost = card_db[cardid].get('cost', 0)
        curve[cost] += count
    return dict(sorted(curve.items()))
```

### To add metadata (priority 6)

**What to change:**
1. Add optional fields to `Deck`: `created_at`, `modified_at`, `source_url`, `checksum`
2. Modify `from_deckstring` to accept metadata kwargs
3. Add `Deck.to_json()` / `from_json()` for persistence with metadata
4. Calculate SHA256 of canonical deckstring as checksum