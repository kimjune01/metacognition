# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Deckstring format for Hearthstone deck encoding/decoding. Current working capabilities:

1. **Binary Encoding/Decoding**: Implements varint (variable-length integer) encoding for compact binary representation
2. **Deckstring Parsing**: Decodes base64-encoded deckstrings into structured deck data containing:
   - Cards with counts (organized by frequency: x1, x2, xN)
   - Heroes (deck class)
   - Format type (Standard, Wild, etc.)
   - Sideboard cards (for formats that support them)
3. **Deckstring Generation**: Encodes deck data back into deckstring format
4. **Deck Object Model**: Provides a `Deck` class with:
   - Factory method `from_deckstring()`
   - Property accessor `as_deckstring`
   - Sorting utilities for cards and sideboards
5. **Data Organization**: Groups cards by count (1x, 2x, N×) for efficient encoding
6. **Format Validation**: Checks version numbers and format types during parsing

## Triage

### Critical Gaps (Production Blockers)

1. **No Error Handling** - System fails hard on malformed input; no graceful degradation or user-friendly error messages
2. **Missing Validation** - No deck composition validation (card limits, format legality, duplicate checking)
3. **No Dependency on `enums.py`** - `FormatType` is imported but the module isn't shown; system won't run standalone
4. **Incomplete Type Hints** - Return type tuples aren't named; reduces maintainability

### High Priority (Quality/Usability Issues)

5. **No Logging** - Silent failures make debugging difficult in production
6. **No Tests** - No verification that encoding/decoding round-trips correctly
7. **Single Hero Hardcoded** - Code enforces exactly 1 hero but doesn't explain why or handle future multi-hero formats
8. **No Card Database Integration** - No way to validate card IDs or resolve them to card names
9. **No Documentation** - No docstrings explaining parameters, return values, or usage examples

### Medium Priority (Developer Experience)

10. **Inconsistent Naming** - `CardIncludeList` vs `CardList`, mixing `cardid`/`card_id`
11. **No CLI Interface** - Manual integration required; no standalone utility
12. **Magic Numbers** - `DECKSTRING_VERSION = 1` and format bytes not explained
13. **Mutable Default Arguments** - `sideboards: Optional[SideboardList] = None` pattern could bite users

### Low Priority (Polish)

14. **No Performance Optimization** - Multiple sorts, no caching for repeated operations
15. **Limited Format Support** - Comments suggest only certain formats support sideboards but no validation
16. **No Serialization Alternatives** - Only supports deckstring format, no JSON/dict export

## Plan

### Critical Fixes

**1. Add Comprehensive Error Handling**
```python
# Replace bare ValueError with custom exceptions
class DeckstringError(Exception): pass
class InvalidDeckstringError(DeckstringError): pass
class UnsupportedVersionError(DeckstringError): pass
class CorruptedDataError(DeckstringError): pass

# Wrap _read_varint EOFError in parse_deckstring:
try:
    version = _read_varint(data)
except EOFError:
    raise CorruptedDataError("Deckstring truncated during version read")

# Add try/except around base64.b64decode() for invalid input
# Add length checks after each read operation
```

**2. Implement Deck Validation**
```python
# Add to Deck class:
def validate(self, allow_invalid_format=False):
    """Validate deck composition rules"""
    # Check total card count (typically 30 for Hearthstone)
    total = sum(count for _, count in self.cards)
    if total != 30:
        raise ValidationError(f"Invalid card count: {total}, expected 30")
    
    # Check individual card limits (typically max 2, legendaries max 1)
    # Requires card database integration
    
    # Check format legality (Standard vs Wild card sets)
    # Requires card database integration
    
    # Check hero matches card class restrictions
```

**3. Create/Bundle `enums.py`**
```python
# Create enums.py with:
from enum import IntEnum

class FormatType(IntEnum):
    FT_UNKNOWN = 0
    FT_WILD = 1
    FT_STANDARD = 2
    FT_CLASSIC = 3
    FT_TWIST = 4
    # Add others as discovered from Hearthstone API
```

**4. Fix Type Hints**
```python
# Replace tuple return type in parse_deckstring:
from typing import NamedTuple

class ParsedDeck(NamedTuple):
    cards: CardIncludeList
    heroes: CardList
    format: FormatType
    sideboards: SideboardList

def parse_deckstring(deckstring: str) -> ParsedDeck:
    # ... existing code ...
    return ParsedDeck(cards, heroes, format, sideboards)
```

### High Priority

**5. Add Structured Logging**
```python
import logging
logger = logging.getLogger(__name__)

# In parse_deckstring:
logger.debug(f"Parsing deckstring of length {len(deckstring)}")
logger.debug(f"Version: {version}, Format: {format}, Heroes: {num_heroes}")
```

**6. Create Test Suite**
```python
# tests/test_deckstring.py
import pytest

def test_roundtrip():
    """Ensure encoding->decoding preserves data"""
    original = "AAECAa0GBu0F..."
    deck = Deck.from_deckstring(original)
    assert deck.as_deckstring == original

def test_invalid_base64():
    """Handle garbage input gracefully"""
    with pytest.raises(InvalidDeckstringError):
        Deck.from_deckstring("not!valid!base64")

# Add tests for edge cases: empty decks, max counts, sideboard variants
```

**7. Remove Hero Count Restriction**
```python
# Replace hardcoded check with configurable validation:
def __init__(self, min_heroes=1, max_heroes=1):
    self.min_heroes = min_heroes
    self.max_heroes = max_heroes
    # ...

def validate_heroes(self):
    count = len(self.heroes)
    if not (self.min_heroes <= count <= self.max_heroes):
        raise ValidationError(f"Hero count {count} outside range [{self.min_heroes}, {self.max_heroes}]")
```

**8. Integrate Card Database**
```python
# Add optional card resolver:
class Deck:
    def __init__(self, card_db: Optional[CardDatabase] = None):
        self.card_db = card_db
    
    def get_card_names(self) -> List[Tuple[str, int]]:
        """Resolve DBF IDs to card names"""
        if not self.card_db:
            raise ValueError("No card database configured")
        return [(self.card_db.get_name(id), count) for id, count in self.cards]
```

**9. Add Docstrings**
```python
class Deck:
    """
    Represents a Hearthstone deck with encoding/decoding support.
    
    Format: Blizzard deckstring v1 (base64-encoded varint binary)
    
    Example:
        >>> deck = Deck.from_deckstring("AAECAa0GBu0F...")
        >>> print(deck.format)
        FormatType.FT_STANDARD
        >>> print(len(deck.cards))
        30
    """
```

### Medium Priority

**10. Normalize Naming Conventions**
- Use `card_id` everywhere (not `cardid`)
- Rename `CardIncludeList` → `CardCountList` (clearer meaning)
- Use consistent `_x1`/`_x2`/`_xn` suffixes or rename to `_single`/`_double`/`_multi`

**11. Add CLI Interface**
```python
# cli.py
import argparse

def main():
    parser = argparse.ArgumentParser(description="Hearthstone deckstring utility")
    parser.add_argument("deckstring", help="Deckstring to decode")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    deck = Deck.from_deckstring(args.deckstring)
    # Output formatted result
```

**12. Document Protocol Constants**
```python
DECKSTRING_VERSION = 1  # Blizzard protocol version
HEADER_RESERVED = b"\0"  # Reserved byte (always 0x00)
SIDEBOARD_MARKER = b"\1"  # Indicates sideboard section present
NO_SIDEBOARD_MARKER = b"\0"  # Indicates no sideboard section
```

**13. Fix Mutable Defaults** - Already handled correctly with `if sideboards is None: sideboards = []`

### Low Priority

**14. Add Caching**
```python
from functools import cached_property

class Deck:
    @cached_property
    def as_deckstring(self) -> str:
        # Cached until cards/heroes/format/sideboards change
```

**15. Add Format-Specific Validation**
```python
def validate_sideboards(self):
    if self.sideboards and self.format not in (FormatType.FT_TWIST,):
        raise ValidationError(f"Format {self.format} does not support sideboards")
```

**16. Add Alternative Serialization**
```python
def to_dict(self) -> dict:
    return {
        "format": self.format.name,
        "heroes": self.heroes,
        "cards": [{"id": id, "count": count} for id, count in self.cards],
        "sideboards": [{"id": id, "count": count, "owner": owner} for id, count, owner in self.sideboards]
    }
```