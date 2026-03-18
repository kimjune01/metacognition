# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements Blizzard's deckstring encoding/decoding format for Hearthstone deck sharing. Current working capabilities:

1. **Perceive**: Reads base64-encoded deckstrings via `parse_deckstring()` - decodes binary format with varint encoding
2. **Cache**: Stores parsed data in `Deck` class with structured fields (`cards`, `heroes`, `format`, `sideboards`)
3. **Filter**: Basic format validation - checks magic byte (`\0`), version number, and FormatType enum membership
4. **Attend**: Sorts cards by count (1x, 2x, n×) for efficient encoding; sorts final outputs by card ID
5. **Remember**: Generates deckstrings from in-memory state via `write_deckstring()` and `Deck.as_deckstring`

**What's working well:**
- Bidirectional serialization (parse ↔ write)
- Efficient binary format with varint compression
- Support for standard and sideboard cards
- Clean separation between parsing logic and data structure

## Triage

### Critical gaps (blocks production use)

1. **No consolidation layer** - System processes identically every run. No learning from invalid decks, no statistics on card frequency, no optimization of encoding parameters
2. **Shallow filtering** - Only validates structure, not semantics. Accepts impossible decks (99x same card, invalid card IDs, wrong format/hero combinations)
3. **No error context** - When parsing fails, user gets ValueError with no hints about where corruption occurred or how to fix it
4. **Missing persistence** - `Deck.get_dbf_id_list()` methods suggest read-only queries, but no save/load for deck collections

### Important but not blocking

5. **Limited observability** - No logging, metrics, or debugging hooks. Can't trace why a deckstring was rejected
6. **Incomplete validation** - Version check exists but only supports v1. Future versions will break hard
7. **No canonicalization** - Same deck can have multiple valid deckstrings (different sort orders). No way to normalize for comparison

### Nice to have

8. **No high-level operations** - Missing deck diff, merge, card substitution, format conversion
9. **Type hints incomplete** - Uses `List[tuple]` instead of proper TypedDict for sideboard tuples
10. **No batch processing** - Processes one deck at a time; no API for bulk import/export

## Plan

### 1. Add consolidation (backward pass)

**What to build:**
```python
class DeckValidator:
    def __init__(self, cards_db: CardDatabase):
        self.stats = ValidationStats()  # Track rejection reasons
        self.cards_db = cards_db
    
    def learn_from_batch(self, decks: List[str]) -> ValidationReport:
        """Process many decks, update internal rules based on patterns."""
        # Accumulate: which card IDs appear? Which heroes with which formats?
        # Update: tighten validation rules, cache valid card/hero pairs
        # Return: summary of what was learned
```

**Files to change:**
- Create `validation.py` with `DeckValidator` class
- Add `CardDatabase` interface (even if stub initially)
- Update `parse_deckstring()` to accept optional validator

### 2. Strengthen filtering

**What to build:**
```python
def parse_deckstring(
    deckstring: str,
    validator: Optional[DeckValidator] = None
) -> Tuple[...]:
    # After basic structure parsing:
    if validator:
        validator.check_card_count(cards)  # Max 30 for standard
        validator.check_card_legality(cards, format)  # Wild vs Standard
        validator.check_hero_class(heroes, cards)  # Paladin can't have Fireball
        validator.check_duplicates(cards, format)  # Highlander rules
```

**Rules to implement:**
- Total card count limits (30 for constructed, 40 for Duels)
- Per-card count limits (1x in Highlander, 2x in standard, uncapped in Arena)
- Card legality for format (Standard set rotation)
- Hero/class restrictions (neutral + class cards only)

### 3. Add error context

**What to change in `deckstrings.py`:**
```python
# Replace bare ValueError with:
class DeckstringError(ValueError):
    def __init__(self, msg: str, byte_offset: int, context: bytes):
        self.byte_offset = byte_offset
        self.context = context
        super().__init__(f"{msg} at byte {byte_offset}: {context.hex()}")

# In _read_varint:
def _read_varint(stream: IO) -> int:
    offset = stream.tell()
    try:
        # ... existing logic
    except EOFError:
        stream.seek(offset)
        context = stream.read(16)
        raise DeckstringError("Unexpected EOF reading varint", offset, context)
```

**Also add:**
- Human-readable deck preview on parse failure
- Suggestion system ("Did you mean this card ID?")

### 4. Add persistence layer

**New module `storage.py`:**
```python
class DeckCollection:
    def __init__(self, path: Path):
        self.path = path
        self.index = {}  # deckstring -> metadata
    
    def save(self, deck: Deck, name: str, tags: List[str]):
        # Write to disk with metadata
        # Update index for fast lookup
    
    def load(self, name: str) -> Deck:
        # Read from disk, return Deck instance
    
    def query(self, format: FormatType, hero: int) -> List[Deck]:
        # Filter by attributes without loading all
```

**Storage format options:**
- SQLite for queryability (recommended)
- JSON lines for simplicity
- Pickle for speed (not human-readable)

### 5. Add logging and observability

**Changes to existing functions:**
```python
import logging
logger = logging.getLogger(__name__)

def parse_deckstring(deckstring: str) -> ...:
    logger.debug(f"Parsing deckstring length={len(deckstring)}")
    # ... after each section:
    logger.debug(f"Parsed heroes={heroes}, format={format}")
    logger.debug(f"Parsed {len(cards)} cards, {len(sideboards)} sideboard")
```

**Add metrics:**
- Parsing duration histogram
- Deck size distribution
- Most common heroes/formats
- Rejection reasons (requires validation layer first)

### 6. Handle version evolution

**Change in `parse_deckstring`:**
```python
version = _read_varint(data)
if version < 1 or version > 2:
    raise ValueError(f"Unsupported version {version}")

if version == 1:
    return _parse_v1(data, format)
elif version == 2:
    return _parse_v2(data, format)  # Future: new fields
```

**Add migration path:**
- `Deck.upgrade_to_v2()` method
- Backwards-compatible writer that detects required version

### 7. Add canonicalization

**New method:**
```python
def canonicalize_deckstring(deckstring: str) -> str:
    """Return normalized form for deduplication."""
    cards, heroes, fmt, sideboards = parse_deckstring(deckstring)
    # Ensure deterministic sort (already done)
    # Remove optional fields if empty
    return write_deckstring(cards, heroes, fmt, sideboards)

def deckstring_hash(deckstring: str) -> str:
    """Content-based hash for fast comparison."""
    canonical = canonicalize_deckstring(deckstring)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]
```

### 8-10. Future enhancements (lower priority)

**Deck operations** (`deck_ops.py`):
- `diff(deck1, deck2) -> CardDiff` - show added/removed cards
- `convert_format(deck, target_format)` - remove rotated cards, suggest replacements

**Type improvements**:
```python
from typing import TypedDict

class SideboardCard(TypedDict):
    card_id: int
    count: int
    owner_id: int

SideboardList = List[SideboardCard]
```

**Batch API**:
```python
def parse_many(deckstrings: Iterable[str], 
               max_workers: int = 4) -> Iterator[Result[Deck, Exception]]:
    # Parallel parsing with error isolation
```

---

**Recommended implementation order:**
1. Error context (#3) - improves debugging immediately
2. Persistence (#4) - enables real usage
3. Validation (#2) - prevents bad data
4. Consolidation (#1) - makes validation smarter over time
5. Everything else as needed