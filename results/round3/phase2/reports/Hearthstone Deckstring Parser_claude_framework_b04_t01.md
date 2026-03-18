# Diagnostic Report: Blizzard Deckstring Format Support

## Observations

This system implements encoding and decoding for Hearthstone deck codes (deckstrings). Current working capabilities:

1. **Bidirectional conversion**: Parses base64-encoded deckstrings into structured data and serializes structured data back to deckstrings
2. **Variable-length integer encoding**: Custom varint implementation for compact binary representation
3. **Card organization**: Groups cards by count (1×, 2×, n×) for efficient storage
4. **Hero support**: Handles hero card selection (currently enforces exactly 1 hero)
5. **Format tracking**: Stores deck format type (Wild, Standard, Classic, etc.)
6. **Sideboard support**: Reads and writes sideboard cards with owner tracking (for dual-class decks)
7. **Deck class wrapper**: `Deck` object provides convenient interface with sorted retrieval methods

The code successfully handles:
- Version 1 deckstring format
- Single-hero decks
- Cards with counts 1, 2, or arbitrary n
- Optional sideboard section (backwards compatible)
- Proper sorting for canonical representation

## Triage

### Critical Gaps

1. **No error recovery**: EOF handling exists but most parsing failures raise generic exceptions without context
2. **No validation**: Card IDs, counts, and format values are not validated against known constraints
3. **Multi-hero limitation**: Code enforces single hero but format theoretically supports multiple (Tavern Brawls, special modes)

### Important Gaps

4. **No type hints for tuples**: `CardIncludeList`, `SideboardList` use bare tuples instead of dataclasses or NamedTuples
5. **No round-trip testing**: No verification that `parse(write(x)) == x`
6. **Silent data loss**: Invalid format types get replaced, sideboards get ignored on write if list is None vs empty
7. **No logging**: Debugging parsing failures requires adding print statements

### Nice-to-Have Gaps

8. **No docstrings**: Functions lack parameter descriptions and examples
9. **No CLI tool**: Cannot decode deckstrings from command line
10. **Hard-coded version check**: Will reject future deckstring versions instead of attempting compatibility
11. **Inefficient sorting**: Sorts on every `get_dbf_id_list()` call instead of maintaining sorted state

## Plan

### 1. Error Recovery (Critical)

**Current**: `raise ValueError("Invalid deckstring")` with no context  
**Change**: 
- Add `DeckstringError` exception class with `position` and `context` attributes
- Wrap each `_read_varint` with try/except that reports byte offset
- Add validation at each stage: "Expected format byte, got EOF at position 2"
- Include partial parse results in exception (already parsed heroes, format)

### 2. Validation (Critical)

**Current**: Accepts any integer as card ID, count, or format  
**Change**:
- Add `validate_card_count(count: int)` checking count ≥ 1 and count ≤ reasonable max (30 for mainboard, 10 for sideboard)
- Add optional `validate_dbf_id(card_id: int, known_cards: Set[int])` if card database provided
- Add format validation against `FormatType` enum values
- Add total deck size validation (30 cards for constructed, other limits for other modes)

### 3. Multi-Hero Support (Critical)

**Current**: `if len(heroes) != 1: raise ValueError`  
**Change**:
- Remove hard-coded check, replace with `if len(heroes) < 1: raise ValueError("Deck must have at least one hero")`
- Document which game modes use multiple heroes
- Add optional `max_heroes` parameter to `write_deckstring` for validation

### 4. Type Hints Improvement (Important)

**Current**: `CardIncludeList = List[Tuple[int, int]]`  
**Change**:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CardInclusion:
    dbf_id: int
    count: int

@dataclass(frozen=True) 
class SideboardCard:
    dbf_id: int
    count: int
    owner_dbf_id: int

CardIncludeList = List[CardInclusion]
SideboardList = List[SideboardCard]
```
Benefits: Named fields, immutability, better IDE support

### 5. Round-Trip Testing (Important)

**Current**: No verification  
**Change**:
- Add `verify_round_trip(deckstring: str) -> bool` helper
- Add property test: `assert deck.from_deckstring(deck.as_deckstring).cards == deck.cards`
- Add to test suite with known-good deckstrings from official sources

### 6. Data Loss Prevention (Important)

**Current**: `if sideboards is None:` vs `if len(sideboards) > 0:` inconsistency  
**Change**:
- Make `sideboards` parameter required, default to empty list in signature
- Add explicit `has_sideboards` property to `Deck` class
- Validate: if sideboards present, at least one hero must support sideboards

### 7. Logging (Important)

**Current**: No diagnostic output  
**Change**:
```python
import logging
logger = logging.getLogger(__name__)

# In parse_deckstring:
logger.debug(f"Parsing deckstring version {version}, format {format}")
logger.debug(f"Read {num_heroes} heroes: {heroes}")
logger.debug(f"Read {len(cards)} cards, {len(sideboards)} sideboard cards")
```

### 8. Documentation (Nice-to-Have)

**Current**: No docstrings  
**Change**: Add Google-style docstrings to all public functions:
```python
def parse_deckstring(deckstring: str) -> Tuple[...]:
    """Parse a Hearthstone deckstring into components.
    
    Args:
        deckstring: Base64-encoded deck code (e.g., "AAECAa0G...")
        
    Returns:
        Tuple of (cards, heroes, format, sideboards)
        
    Raises:
        DeckstringError: If deckstring is malformed or unsupported version
        
    Example:
        >>> cards, heroes, fmt, sb = parse_deckstring("AAECAa0G...")
    """
```

### 9. CLI Tool (Nice-to-Have)

**Current**: Library only  
**Change**: Add `__main__.py`:
```python
if __name__ == "__main__":
    import sys
    deckstring = sys.argv[1]
    deck = Deck.from_deckstring(deckstring)
    print(f"Format: {deck.format}")
    print(f"Heroes: {deck.heroes}")
    print(f"Cards ({len(deck.cards)}): {deck.cards}")
```

### 10. Version Compatibility (Nice-to-Have)

**Current**: `if version != DECKSTRING_VERSION: raise ValueError`  
**Change**:
- Change to `if version > DECKSTRING_VERSION: logger.warning(f"Future version {version}")`
- Attempt parse anyway (forward compatibility)
- Add version-specific parsing branches if/when version 2 arrives

### 11. Performance (Nice-to-Have)

**Current**: Sorts on every property access  
**Change**:
```python
def __init__(self):
    self._cards: CardIncludeList = []
    self._cards_sorted = True  # Track if needs re-sort

def add_card(self, card_id: int, count: int):
    self._cards.append((card_id, count))
    self._cards_sorted = False

@property
def cards_sorted(self):
    if not self._cards_sorted:
        self._cards.sort(key=lambda x: x[0])
        self._cards_sorted = True
    return self._cards
```

---

**Implementation Priority**: Address gaps 1–3 before production use. Gaps 4–7 improve maintainability. Gaps 8–11 improve developer experience but don't affect correctness.