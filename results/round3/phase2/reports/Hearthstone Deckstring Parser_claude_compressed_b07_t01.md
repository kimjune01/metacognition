# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Deckstring format for encoding/decoding Hearthstone deck compositions. Current capabilities:

**Core encoding/decoding:**
- Parses base64-encoded deckstrings into structured deck data (cards, heroes, format, sideboards)
- Writes structured deck data back to deckstring format
- Handles varint encoding/decoding for compact integer representation
- Supports card counts: 1x, 2x, and n× (for game modes allowing duplicates)
- Supports sideboard cards (with owner references)
- Validates deckstring version (currently only v1)

**Data structures:**
- `Deck` class provides object-oriented interface with `from_deckstring()` constructor and `as_deckstring` property
- Methods to retrieve sorted card/sideboard lists by DBF ID
- Format type enumeration integration (`FormatType.FT_UNKNOWN`, etc.)

**Input validation:**
- Checks magic byte (0x00 header)
- Validates deckstring version
- Validates format type enum
- Enforces exactly 1 hero requirement

## Triage

### Critical gaps (blocks production use):

1. **No error handling for malformed input** - System raises bare exceptions on invalid data
2. **No input validation boundaries** - Accepts negative counts, invalid card IDs, oversized decks
3. **No tests** - Zero coverage means regression risk on any change
4. **Hero count hardcoded to 1** - Parses multiple heroes but rejects them on write

### Important gaps (quality/maintainability issues):

5. **No logging or debugging output** - Silent failures make troubleshooting impossible
6. **Type hints incomplete** - Return types mix tuple and type aliases inconsistently
7. **No documentation** - No docstrings explaining deckstring format or usage
8. **Magic numbers scattered** - `0x7f`, `0x80`, version numbers lack named constants

### Nice-to-have (usability improvements):

9. **No deck validation rules** - Doesn't check 30-card limit, duplicate restrictions, format legality
10. **No convenience methods** - Can't add/remove cards, compare decks, or export to other formats
11. **No performance optimization** - Sorts repeatedly; could cache sorted views

## Plan

### 1. Error handling (deckstring.py)

**Add custom exception hierarchy:**
```python
class DeckstringError(Exception): pass
class InvalidDeckstringError(DeckstringError): pass
class UnsupportedVersionError(DeckstringError): pass
```

**Wrap parsing with try/catch:**
- Catch `EOFError` from varint reads → raise `InvalidDeckstringError("Truncated deckstring")`
- Catch `base64.binascii.Error` → raise `InvalidDeckstringError("Invalid base64 encoding")`
- Add specific messages for each validation failure

### 2. Input validation (deckstring.py)

**In `parse_deckstring()`:**
- After reading card counts, validate `count > 0 and count <= 255`
- After reading card IDs, validate `card_id > 0`
- Validate sideboard owner IDs exist in heroes list

**In `write_deckstring()`:**
- Check `len(cards) <= 100` (reasonable upper bound)
- Validate all card tuples have correct length (2 for cards, 3 for sideboards)

### 3. Tests (new file: test_deckstring.py)

**Create test suite with:**
- Round-trip test: parse → write → parse produces identical data
- Known deckstring samples (from real Hearthstone decks)
- Edge cases: 1-card deck, 30-card deck, all 1× cards, all 2× cards
- Error cases: invalid base64, wrong version, malformed varint, empty input
- Sideboard tests: with/without sideboards, multiple sideboard owners

**Use pytest with parametrize for systematic coverage.**

### 4. Hero count flexibility (deckstring.py:147)

**Replace hardcoded check:**
```python
# Current:
if len(heroes) != 1:
    raise ValueError("Unsupported hero count %i" % (len(heroes)))

# Change to:
if len(heroes) == 0:
    raise ValueError("Deck must have at least one hero")
# Remove upper bound check entirely
```

**Rationale:** Tavern Brawls and future modes may allow multiple heroes.

### 5. Logging (deckstring.py)

**Add at module level:**
```python
import logging
logger = logging.getLogger(__name__)
```

**Log key events:**
- `logger.debug(f"Parsing deckstring version {version}, format {format}")` after header
- `logger.debug(f"Decoded {len(cards)} cards, {len(heroes)} heroes")` after parsing
- `logger.warning(f"Unknown format type {format}")` when format enum fails

### 6. Type consistency (deckstring.py)

**Standardize return annotations:**
- `parse_deckstring() -> Tuple[CardIncludeList, CardList, FormatType, SideboardList]` (already exists in comment, formalize)
- `trisort_cards() -> Tuple[List[tuple], List[tuple], List[tuple]]` → use specific tuple types
- Add `-> None` to `__init__` methods

### 7. Documentation (deckstring.py)

**Add module docstring:**
```python
"""
Hearthstone Deckstring encoding/decoding.

Deckstrings are base64-encoded binary formats containing:
- Header: version byte, format type
- Heroes: list of hero card DBF IDs  
- Cards: grouped by count (1×, 2×, n×) for compact encoding
- Sideboards: optional card pool with owner references

Example:
    deck = Deck.from_deckstring("AAECAa0G...")
    print(deck.cards)  # [(1234, 2), (5678, 1)]
"""
```

**Add docstrings to public methods with parameter descriptions and return types.**

### 8. Named constants (deckstring.py)

**Replace magic numbers:**
```python
VARINT_MASK = 0x7f
VARINT_CONTINUATION = 0x80
HEADER_MAGIC = b"\0"
SIDEBOARD_PRESENT = b"\1"
SIDEBOARD_ABSENT = b"\0"
```

**Use throughout `_read_varint()`, `_write_varint()`, parsing code.**

### 9. Deck validation (new method in Deck class)

**Add `validate(self, check_legality=False)` method:**
- Check total card count (typically 30 for Standard/Wild)
- Check duplicate limits (max 2× for non-legendary, 1× for legendary)
- If `check_legality=True`, verify cards are legal in specified format (requires card database integration)
- Return list of validation errors or empty list if valid

### 10. Convenience methods (Deck class)

**Add methods:**
- `add_card(dbf_id: int, count: int = 1)` - append or increment card
- `remove_card(dbf_id: int)` - remove card from deck
- `to_dict()` - export as JSON-serializable dict
- `__eq__` and `__hash__` - enable deck comparison and set operations
- `get_card_count(dbf_id: int) -> int` - lookup count for specific card

### 11. Performance optimization (Deck class)

**Cache sorted results:**
```python
def __init__(self):
    self._cards = []
    self._cards_sorted_cache = None

def get_dbf_id_list(self):
    if self._cards_sorted_cache is None:
        self._cards_sorted_cache = sorted(self.cards, key=lambda x: x[0])
    return self._cards_sorted_cache
```

**Invalidate cache on mutation (if add/remove methods added).**

---

**Priority order for implementation:** 1 → 3 → 2 → 4 → 5 → 7 (remaining can follow based on actual usage patterns).