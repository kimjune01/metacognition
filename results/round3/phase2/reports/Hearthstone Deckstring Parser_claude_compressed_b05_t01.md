# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Hearthstone deckstring format, a compact binary encoding for deck configurations. Current working capabilities:

1. **Perceive**: Reads base64-encoded deckstrings via `parse_deckstring()` and decodes them into binary streams
2. **Cache**: Stores decoded data in structured form through the `Deck` class with typed fields (`cards`, `heroes`, `format`, `sideboards`)
3. **Filter**: Validates deckstring format (null byte header, version check, format type enum validation)
4. **Attend**: Not applicable—this is a serialization system, not a ranking/selection system
5. **Remember**: Not applicable—this is a stateless parser with no persistence layer
6. **Consolidate**: Not applicable—no learning or adaptation needed for a fixed binary format

The system successfully round-trips deckstrings: decode → manipulate → encode. It handles variable-length integer encoding (varint), three-tier card count bucketing (1x, 2x, n×), and optional sideboard sections.

## Triage

### Critical gaps (blocks production use):

1. **Error handling is shallow**: Filter stage exists but is brittle
   - Accepts malformed varints that cause `EOFError` 
   - No validation of card counts (could be 0 or negative)
   - No bounds checking on hero count beyond != 1
   - Unhandled trailing bytes after parse completion

2. **No validation against game rules**:
   - Missing deck size constraints (30 cards for constructed, 40 for other formats)
   - No uniqueness checks (can include same card 100 times)
   - No format-specific validation (Standard vs Wild card pools)
   - Sideboard owner IDs not validated against hero list

3. **Type hints incomplete**:
   - `IO` type is too generic (should be `IO[bytes]`)
   - Return type of `parse_deckstring` uses inline tuple syntax instead of clear type alias
   - Missing `__init__` parameter types on `Deck`

### Important gaps (reduce maintainability):

4. **No logging or observability**:
   - Silent failures possible (empty deckstring returns empty deck)
   - No way to debug partial parse failures
   - Performance characteristics unknown (varint reading is byte-by-byte)

5. **Limited API surface**:
   - No way to modify deck after creation (add/remove cards)
   - No card lookup by ID
   - No deck comparison or diff operations
   - No human-readable string representation (`__str__`, `__repr__`)

6. **No tests visible**:
   - Cannot verify correctness across edge cases
   - No regression protection
   - Round-trip encoding not proven

### Minor gaps (polish):

7. **Documentation sparse**:
   - Module docstring doesn't explain deckstring format
   - Functions lack parameter/return descriptions
   - No examples of valid deckstrings

8. **Python style inconsistencies**:
   - Variable named `list` shadows builtin (line 90, 92, 94)
   - `sort_key` lambda defined twice identically (lines 244, 257)
   - Type alias definitions at module level would improve readability

## Plan

### Fix 1: Strengthen error handling (Filter stage)

**Changes needed:**

```python
# In _read_varint():
- Add byte counter, raise ValueError if exceeds 10 bytes (max varint size)
- Catch EOFError and reraise as ValueError("Truncated deckstring")

# In parse_deckstring():
- After final read, check data.read(1) == b"" to reject trailing bytes
- Validate all counts > 0: if count <= 0: raise ValueError(f"Invalid count {count}")
- Check deck size bounds: if len(cards) < 1 or len(cards) > 100: raise ValueError()
- Validate sideboard owners exist in heroes list

# In write_deckstring():
- Validate inputs before encoding (positive counts, non-empty heroes, valid format enum)
```

### Fix 2: Add game rule validation (Filter stage)

**Changes needed:**

```python
# Create new validator module:
class DeckValidator:
    @staticmethod
    def validate_constructed(cards, format):
        total = sum(count for _, count in cards)
        if total != 30:
            raise ValueError(f"Constructed deck must have 30 cards, got {total}")
        
        # Check card count limits (2 for most, 1 for legendaries)
        # Requires card database integration
        
    @staticmethod  
    def validate_format(cards, format):
        # Check cards are legal in format (Standard/Wild/Classic)
        # Requires card database integration
        pass

# Integrate into Deck class:
def validate(self, card_db=None):
    """Validate deck against game rules. Requires card database for full checks."""
    DeckValidator.validate_constructed(self.cards, self.format)
    if card_db:
        DeckValidator.validate_format(self.cards, self.format)
```

### Fix 3: Complete type annotations

**Changes needed:**

```python
# At module level, add:
from typing import BinaryIO
CardList = List[int]
CardIncludeList = List[Tuple[int, int]]
SideboardList = List[Tuple[int, int, int]]

# Update signatures:
def _read_varint(stream: BinaryIO) -> int: ...
def _write_varint(stream: BinaryIO, i: int) -> int: ...

# Replace inline tuple with ParseResult:
from typing import NamedTuple
class ParseResult(NamedTuple):
    cards: CardIncludeList
    heroes: CardList  
    format: FormatType
    sideboards: SideboardList

def parse_deckstring(deckstring: str) -> ParseResult: ...
```

### Fix 4: Add observability

**Changes needed:**

```python
import logging
logger = logging.getLogger(__name__)

# In parse_deckstring():
logger.debug("Parsing deckstring version=%d format=%s", version, format)
logger.debug("Read %d heroes, %d cards, %d sideboard cards", 
             len(heroes), len(cards), len(sideboards))

# In _read_varint():
# Add optional byte counter to detect suspicious varints
if bytes_read > 5:
    logger.warning("Varint required %d bytes (possible corruption)", bytes_read)
```

### Fix 5: Expand API surface

**Changes needed:**

```python
# Add to Deck class:
def add_card(self, card_id: int, count: int = 1) -> None:
    """Add or increment card count."""
    for i, (cid, cnt) in enumerate(self.cards):
        if cid == card_id:
            self.cards[i] = (cid, cnt + count)
            return
    self.cards.append((card_id, count))

def remove_card(self, card_id: int, count: int = 1) -> None:
    """Remove or decrement card count."""
    # Implementation here

def get_card_count(self, card_id: int) -> int:
    """Return count of specific card in deck."""
    return next((cnt for cid, cnt in self.cards if cid == card_id), 0)

def __repr__(self) -> str:
    return f"Deck(format={self.format.name}, cards={len(self.cards)}, heroes={self.heroes})"

def __eq__(self, other) -> bool:
    """Compare decks by content."""
    return (self.cards == other.cards and 
            self.heroes == other.heroes and
            self.format == other.format and
            self.sideboards == other.sideboards)
```

### Fix 6: Add comprehensive tests

**Create new test file `test_deckstring.py`:**

```python
import pytest
from hearthstone.deckstrings import Deck, parse_deckstring, write_deckstring

# Test valid deckstrings (need real examples from Hearthstone)
VALID_DECKSTRINGS = [
    "AAECAa0GBu0F1gr7DPoO...",  # Standard constructed
    "AAEBAQcG...",  # With sideboards
]

def test_roundtrip():
    for ds in VALID_DECKSTRINGS:
        deck = Deck.from_deckstring(ds)
        assert deck.as_deckstring == ds

def test_invalid_version():
    with pytest.raises(ValueError, match="Unsupported deckstring version"):
        parse_deckstring("AAEAAQ==")  # Version 0

def test_truncated():
    with pytest.raises(ValueError, match="Truncated"):
        parse_deckstring("AAE=")  # Incomplete

def test_negative_count():
    # Craft deckstring with negative varint, expect ValueError
    pass
```

### Fix 7: Improve documentation

**Changes needed:**

```python
"""
Hearthstone Deckstring Parser

Implements Blizzard's binary format for encoding deck configurations.
Format: base64(null_byte + version + format + heroes + cards + sideboards)

Example:
    >>> deck = Deck.from_deckstring("AAECAa0GBu0F1gr7DPoOkge...")
    >>> deck.heroes
    [813]
    >>> deck.cards
    [(192, 2), (315, 1), ...]
    >>> deck.as_deckstring
    "AAECAa0GBu0F1gr7DPoOkge..."

Format documentation: https://hearthsim.info/docs/deckstrings/
"""

def parse_deckstring(deckstring: str) -> ParseResult:
    """
    Decode a Hearthstone deckstring into structured components.
    
    Args:
        deckstring: Base64-encoded deck configuration string
        
    Returns:
        ParseResult with cards, heroes, format, and sideboards
        
    Raises:
        ValueError: If deckstring is invalid or unsupported version/format
        
    Example:
        >>> cards, heroes, fmt, sb = parse_deckstring("AAECAa0G...")
        >>> len(cards)
        30
    """
```

### Fix 8: Clean up style issues

**Changes needed:**

```python
# Line 90-94: Rename shadowing variable
if count == 1:
    target_list = cards_x1
elif count == 2:
    target_list = cards_x2
else:
    target_list = cards_xn
target_list.append(...)

# Line 244, 257: Define once at module level
_CARD_SORT_KEY = lambda x: x[0]
_SIDEBOARD_SORT_KEY = lambda x: (x[2], x[0])

# Use throughout:
for cardlist in sorted(cards_x1, key=_CARD_SORT_KEY), ...
```

**Priority order for implementation:**
1. Fix #1 (error handling) — blocks production safety
2. Fix #6 (tests) — proves correctness, enables refactoring  
3. Fix #3 (type hints) — improves maintainability
4. Fix #2 (game rules) — if this library is user-facing; otherwise defer
5. Fixes #4, #5, #7, #8 — polish as time permits