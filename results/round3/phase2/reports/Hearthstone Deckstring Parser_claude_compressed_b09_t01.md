# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Deckstring format for Hearthstone deck encoding/decoding. Current working capabilities:

1. **Perceive**: Reads base64-encoded deckstrings via `from_deckstring()` and `parse_deckstring()`
2. **Cache**: Stores decoded deck data in normalized structures (cards list, heroes list, format enum, sideboards list)
3. **Filter**: Basic validation exists (version check, format enum validation, hero count validation)
4. **Attend**: Sorts cards and sideboards by DBF ID; trisorts cards by count (×1, ×2, ×n) for efficient encoding
5. **Remember**: Persists deck state in `Deck` object across method calls

The system successfully handles:
- Varint encoding/decoding (compact integer representation)
- Round-trip conversion (deckstring → object → deckstring)
- Sideboard cards (optional 3-tuple format)
- Multiple deck formats (Wild, Standard, etc.)

## Triage

### Critical gaps (blocking production use)
1. **Filter is shallow**: Validation catches format errors but not semantic errors (invalid card counts, duplicate cards, illegal deck compositions)
2. **Consolidate is absent**: No learning or adaptation capability
3. **Error handling is incomplete**: No context in error messages, no recovery paths

### Important gaps (reduce robustness)
4. **Cache lacks querying**: No methods to search cards by attributes, check deck legality, or compute deck stats
5. **Perceive has no telemetry**: Silent failures possible (e.g., trailing bytes ignored)
6. **Remember has no persistence**: Deck object only lives in memory

### Nice-to-have gaps (improve usability)
7. **No human-readable formats**: Can't export to text list or JSON
8. **No deck metadata**: Missing name, author, creation date, description
9. **No card database integration**: Uses raw DBF IDs with no card name resolution

## Plan

### 1. Strengthen Filter (semantic validation)

**What to change:**
- Add `validate()` method to `Deck` class that checks:
  - Total card count (must be 30 for Standard/Wild)
  - Card count limits (max 2 copies, 1 for legendaries)
  - No duplicate DBF IDs in main deck
  - Format-specific restrictions (banned cards, allowed sets)
- Create custom exception types: `InvalidDeckException`, `InvalidCardCountException`, `BannedCardException`
- Call `validate()` automatically in `from_deckstring()` with optional `strict=True` parameter

**Example:**
```python
def validate(self, card_db: Optional[CardDatabase] = None) -> None:
    total = sum(count for _, count in self.cards)
    if total != 30:
        raise InvalidDeckException(f"Deck has {total} cards, expected 30")
    
    seen = set()
    for cardid, count in self.cards:
        if cardid in seen:
            raise InvalidDeckException(f"Duplicate card {cardid}")
        seen.add(cardid)
        if card_db and card_db.is_legendary(cardid) and count > 1:
            raise InvalidCardCountException(f"Legendary {cardid} has {count} copies")
```

### 2. Add Consolidate (learning layer)

**What to change:**
- Create `DeckAnalyzer` class that reads stored decks and updates heuristics
- Track deck winrates, popularity, meta archetypes
- Generate recommendations: "Similar decks have X instead of Y"
- Store analysis results in separate file (JSON/SQLite)

**Example:**
```python
class DeckAnalyzer:
    def analyze_collection(self, decks: List[Deck]) -> DeckStats:
        """Read stored decks and compute meta statistics."""
        pass
    
    def suggest_improvements(self, deck: Deck) -> List[CardSwap]:
        """Use historical data to recommend card changes."""
        pass
```

### 3. Improve error messages

**What to change:**
- Add position tracking to varint reader (line/offset)
- Include partial decode state in exceptions
- Add `__str__` to exceptions showing what was parsed successfully

**Example:**
```python
class DecodeError(ValueError):
    def __init__(self, msg: str, position: int, partial_state: dict):
        super().__init__(f"{msg} at byte {position}")
        self.position = position
        self.partial_state = partial_state
```

### 4. Expand Cache with queries

**What to change:**
- Add methods to `Deck`: `get_cards_by_mana()`, `count_minions()`, `get_curve()`
- Add `__contains__` for card lookup: `if cardid in deck:`
- Add memoization for expensive computations

**Example:**
```python
def get_mana_curve(self, card_db: CardDatabase) -> List[int]:
    """Returns [count_at_0, count_at_1, ..., count_at_10+]."""
    curve = [0] * 11
    for cardid, count in self.cards:
        cost = card_db.get_cost(cardid)
        curve[min(cost, 10)] += count
    return curve
```

### 5. Add telemetry to Perceive

**What to change:**
- Log warnings for trailing bytes after parse completes
- Track decode metrics (time, size, format version)
- Add debug mode that dumps intermediate parse state

**Example:**
```python
def parse_deckstring(deckstring, debug=False) -> Tuple[...]:
    data = BytesIO(decoded)
    if debug:
        print(f"Decoding {len(decoded)} bytes")
    
    # ... existing parse logic ...
    
    remaining = len(data.read())
    if remaining > 0:
        warnings.warn(f"{remaining} trailing bytes ignored")
```

### 6. Add Remember persistence

**What to change:**
- Add `save_to_file(path)` and `load_from_file(path)` methods
- Support JSON format with optional metadata
- Add collection management: `DeckCollection` class with CRUD operations

**Example:**
```python
def to_json(self) -> str:
    return json.dumps({
        "deckstring": self.as_deckstring,
        "cards": self.cards,
        "heroes": self.heroes,
        "format": self.format.name,
        "metadata": {"created": datetime.now().isoformat()}
    })
```

### 7. Add human-readable export

**What to change:**
- Add `to_text(card_db)` method that outputs readable card list
- Support HDT (Hearthstone Deck Tracker) format
- Add `__str__` and `__repr__` for debugging

### 8. Add metadata fields

**What to change:**
- Add optional fields to `Deck.__init__`: name, author, created_at, description
- These don't serialize to deckstring (Blizzard format doesn't support them)
- Store separately when saving to JSON

### 9. Integrate card database

**What to change:**
- Create `CardDatabase` interface with methods: `get_name()`, `get_cost()`, `is_legendary()`, `get_set()`
- Accept optional `card_db` parameter in methods that need card data
- Don't bundle card data (too large), require external source

**Example:**
```python
class CardDatabase(Protocol):
    def get_name(self, dbf_id: int) -> str: ...
    def get_cost(self, dbf_id: int) -> int: ...
    def is_legendary(self, dbf_id: int) -> bool: ...
```

---

**Priority order for implementation:**
1. Semantic validation (#1) — prevents corrupted decks
2. Error context (#3) — essential for debugging
3. Cache queries (#4) — enables deck analysis features
4. Persistence (#6) — needed for any real application
5. Human formats (#7) — user-facing necessity
6. Card DB integration (#9) — blocks several other features
7. Metadata (#8) — polish
8. Telemetry (#5) — nice for monitoring
9. Consolidate (#2) — advanced feature, requires infrastructure