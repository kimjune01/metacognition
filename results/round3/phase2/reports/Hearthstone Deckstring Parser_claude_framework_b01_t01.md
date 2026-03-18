# Diagnostic Report: Hearthstone Deckstring Codec

## Observations

This system implements Blizzard's deckstring format encoder/decoder for Hearthstone deck sharing. Current working capabilities:

1. **Binary deserialization** (`parse_deckstring`): Decodes base64-encoded deckstrings into structured deck data using varint encoding
2. **Binary serialization** (`write_deckstring`): Encodes deck data back into base64 deckstrings
3. **Card organization**: Sorts cards into three buckets (1-count, 2-count, n-count) for compact encoding
4. **Sideboard support**: Handles optional sideboard cards with owner associations (post-2020 format extension)
5. **Format preservation**: Tracks deck format type (Wild, Standard, Classic, etc.)
6. **Hero tracking**: Stores hero card DBF IDs
7. **OOP wrapper** (`Deck` class): Provides object-oriented interface with bidirectional deckstring conversion

The codec correctly implements Blizzard's wire protocol: version byte, format enum, hero list, three card count buckets, optional sideboard flag with three more buckets.

## Triage

### Critical gaps

1. **No validation** - Accepts malformed data that would crash the game client
2. **No error context** - Generic exceptions make debugging impossible
3. **Silent data loss** - `heroes` length check raises ValueError but other constraints don't

### Important gaps

4. **Type hints incomplete** - Return tuple lacks proper typing, hurts IDE support
5. **No documentation** - Public API undocumented, binary format undocumented
6. **Test coverage absent** - No way to verify correctness or prevent regressions

### Nice-to-have gaps

7. **No round-trip verification** - Can't detect encoding bugs
8. **Inefficient sorting** - Re-sorts on every serialization call
9. **Magic numbers** - `b"\0"` and `b"\1"` lack semantic meaning

## Plan

### 1. Validation layer

**What:** Add `validate_deck()` function called from both parse and write paths

**Changes:**
- Check card counts are positive (reject `count < 1`)
- Verify total deck size (Standard = 30 cards, other formats may differ)
- Validate hero count matches format requirements (most formats = 1, Duels = multiple)
- Check DBF IDs are in valid range (positive integers)
- Verify sideboards only appear in supported formats

**Location:** New function at module level, called in `Deck.from_deckstring()` and `Deck.as_deckstring`

### 2. Error context

**What:** Replace generic exceptions with custom exception types carrying diagnostic data

**Changes:**
```python
class DeckstringError(Exception):
    pass

class DeckstringParseError(DeckstringError):
    def __init__(self, msg: str, offset: int, partial_data: dict):
        super().__init__(f"{msg} at byte {offset}")
        self.offset = offset
        self.partial_data = partial_data
```

**Replace:** All `ValueError` and `EOFError` raises with contextual subclasses
**Add:** Track `data.tell()` position at each parse step for offset reporting

### 3. Multi-hero support

**What:** Remove single-hero restriction

**Changes:**
- Delete `if len(heroes) != 1: raise ValueError` check in `write_deckstring`
- Add format-specific hero count validation to validation layer (Standard/Wild = 1, Duels = 2, etc.)

**Rationale:** The wire format already supports multiple heroes; artificial restriction breaks Duels/Battlegrounds

### 4. Type annotations

**What:** Complete type hints for all public surfaces

**Changes:**
```python
def parse_deckstring(deckstring: str) -> Tuple[CardIncludeList, CardList, FormatType, SideboardList]:
```

**Add:** `from __future__ import annotations` at top for forward references
**Tools:** Run `mypy --strict` to find remaining gaps

### 5. Documentation

**What:** Add docstrings to all public functions and classes

**Structure:**
```python
def parse_deckstring(deckstring: str) -> ...:
    """
    Decode a Hearthstone deckstring into structured components.
    
    Args:
        deckstring: Base64-encoded deck data (e.g., "AAECAa0GBg...")
    
    Returns:
        Tuple of (cards, heroes, format, sideboards)
        
    Raises:
        DeckstringParseError: If deckstring is malformed
        
    Example:
        >>> cards, heroes, fmt, sb = parse_deckstring("AAECAZ...")
        >>> print(f"Hero: {heroes[0]}, {len(cards)} cards")
    """
```

**Add:** Module docstring explaining binary format layout with byte diagrams

### 6. Test suite

**What:** Create `test_deckstring.py` with pytest

**Coverage:**
- Round-trip tests: `parse(write(deck)) == deck`
- Known good deckstrings from live game (regression tests)
- Malformed input tests (truncated, wrong version, invalid varint)
- Edge cases: 0-card deck, 100-card deck, n-count cards
- Sideboard presence/absence paths

**Location:** `tests/test_deckstring.py` with fixture deckstrings in `tests/fixtures/`

### 7. Round-trip verification

**What:** Add `verify_round_trip` optional parameter to Deck class

**Changes:**
```python
@property
def as_deckstring(self) -> str:
    encoded = write_deckstring(...)
    if self._verify_round_trip:
        decoded = parse_deckstring(encoded)
        assert decoded == (self.cards, self.heroes, self.format, self.sideboards)
    return encoded
```

**Use:** Enable in test mode, disable in production (performance cost)

### 8. Optimize sorting

**What:** Cache sorted card lists on Deck instance

**Changes:**
- Store pre-sorted lists as private attributes `_cards_sorted`, `_sideboards_sorted`
- Mark dirty on mutation with `_needs_resort` flag
- Lazy-sort only when `as_deckstring` called and dirty flag set

**Tradeoff:** Added complexity vs O(n log n) savings per serialization

### 9. Semantic constants

**What:** Replace magic bytes with named constants

**Changes:**
```python
DECKSTRING_HEADER = b"\0"
SIDEBOARD_PRESENT = b"\1"
SIDEBOARD_ABSENT = b"\0"
```

**Replace:** All `b"\0"` and `b"\1"` literals with these names
**Benefit:** Self-documenting code, single source of truth for protocol values