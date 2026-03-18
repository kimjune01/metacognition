# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard deckstring format parser for Hearthstone decks. Working capabilities:

1. **Bidirectional encoding**: Converts between binary deckstring format (base64-encoded) and structured deck data
2. **Varint serialization**: Custom variable-length integer encoding for compact representation
3. **Card quantity optimization**: Groups cards by count (1x, 2x, n×) to minimize encoding size
4. **Format type support**: Tracks deck format (Standard, Wild, etc.) via `FormatType` enum
5. **Hero tracking**: Stores and validates hero card(s) for the deck
6. **Sideboard support**: Handles optional sideboard cards with ownership tracking (added in later deckstring versions)
7. **OOP interface**: `Deck` class provides convenient access to parsing/serialization
8. **Sorted output**: Returns cards and sideboards in deterministic sorted order

The core functionality works: you can parse a deckstring from Hearthstone, inspect its contents, modify it, and serialize it back.

## Triage

**Critical gaps:**

1. **No error handling for malformed input** - Parser will crash on truncated/corrupted deckstrings rather than reporting meaningful errors
2. **No validation** - Accepts invalid decks (wrong card counts, invalid format/hero combinations, etc.)
3. **No tests** - Zero test coverage for a parser dealing with binary data

**Important gaps:**

4. **Missing FormatType enum definition** - Code imports but doesn't define it; breaks without external dependency
5. **Hardcoded hero count** - `write_deckstring` enforces exactly 1 hero, but Tavern Brawls and future formats may need different rules
6. **No card database integration** - Can't validate card IDs or look up card names/properties
7. **Limited documentation** - Missing docstrings, no usage examples, unclear what DBF IDs are

**Minor gaps:**

8. **Type hints incomplete** - `BytesIO` return types missing, `IO` is too generic
9. **No convenience methods** - Can't add/remove cards, can't diff two decks, can't export to other formats
10. **Performance not optimized** - Multiple sorts, no caching of parsed data

## Plan

### 1. Error handling for malformed input

**Changes needed:**
- Wrap `parse_deckstring` in try/except blocks catching `EOFError`, `ValueError`, `base64.binascii.Error`
- Create custom exception classes: `InvalidDeckstringError`, `UnsupportedVersionError`, `CorruptedDataError`
- Add context to errors (e.g., "Failed at byte position 15 while reading card count")
- Validate base64 string before decoding (check character set, padding)
- Add length checks before reading varints (don't read past end of stream)

**Example:**
```python
class DeckstringError(Exception):
    pass

class InvalidDeckstringError(DeckstringError):
    pass

def parse_deckstring(deckstring):
    try:
        decoded = base64.b64decode(deckstring, validate=True)
    except Exception as e:
        raise InvalidDeckstringError(f"Invalid base64: {e}")
    # ... continue with safer parsing
```

### 2. Deck validation

**Changes needed:**
- Add `Deck.validate()` method that checks:
  - Total card count matches format rules (30 for Constructed, 40 for Twist, etc.)
  - Card quantities follow format rules (max 2 copies for most formats, 1 for Legendary)
  - Hero matches deck class restrictions
  - All card IDs are valid (if card database is available)
- Add optional `strict` parameter to `from_deckstring()` to auto-validate on parse
- Return validation result object listing all violations, not just first error

**Example:**
```python
class ValidationResult:
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

def validate(self) -> ValidationResult:
    result = ValidationResult()
    total = sum(count for _, count in self.cards)
    if total != 30:
        result.errors.append(f"Deck has {total} cards, expected 30")
    # ... more checks
    return result
```

### 3. Add comprehensive tests

**Changes needed:**
- Create `tests/test_deckstring.py` with pytest
- Test valid deckstrings (Standard, Wild, with/without sideboards)
- Test edge cases (empty deck, single card, maximum quantities)
- Test error cases (corrupted base64, unsupported version, truncated data)
- Test round-trip (parse → serialize → parse should match)
- Use real deckstrings from Hearthstone as fixtures
- Add property-based tests with Hypothesis (generate random valid decks, verify round-trip)

### 4. Define FormatType enum

**Changes needed:**
- Either include enum definition in this file or make import optional
- Add these known values (from Hearthstone's format constants):
  ```python
  class FormatType(IntEnum):
      FT_UNKNOWN = 0
      FT_WILD = 1
      FT_STANDARD = 2
      FT_CLASSIC = 3
      FT_TWIST = 4
  ```
- Handle unknown format values gracefully (warn but continue parsing)

### 5. Flexible hero count handling

**Changes needed:**
- Remove hardcoded `len(heroes) != 1` check in `write_deckstring`
- Add optional `validate_heroes` parameter (default True for backwards compatibility)
- Document which formats allow multiple heroes (Tavern Brawls, Duels)

**Change:**
```python
def write_deckstring(
    cards: CardIncludeList,
    heroes: CardList,
    format: FormatType,
    sideboards: Optional[SideboardList] = None,
    validate_heroes: bool = True,
) -> str:
    if validate_heroes and len(heroes) != 1:
        raise ValueError("Standard decks require exactly 1 hero")
```

### 6. Card database integration

**Changes needed:**
- Create `CardDatabase` class that loads from JSON (e.g., HearthstoneJSON format)
- Add `Deck.set_card_database(db)` class method
- Modify `validate()` to check card IDs against database if available
- Add `Deck.get_card_name(dbf_id)` helper
- Make database optional (deck parser works standalone, validation enhanced with DB)

### 7. Improve documentation

**Changes needed:**
- Add module-level docstring explaining deckstring format
- Add docstrings to all public functions/methods with:
  - Purpose
  - Parameters (with types and constraints)
  - Return values
  - Exceptions raised
  - Example usage
- Add README.md with:
  - Installation instructions
  - Quick start example
  - Link to deckstring format specification
  - Explanation of DBF IDs (Hearthstone's internal card database format)

### 8. Complete type hints

**Changes needed:**
- Replace `IO` with `BinaryIO` from `typing`
- Add return type to `_write_varint`: `-> int`
- Use `TypeAlias` for complex types:
  ```python
  from typing import TypeAlias
  CardList: TypeAlias = List[int]
  CardIncludeList: TypeAlias = List[Tuple[int, int]]
  SideboardList: TypeAlias = List[Tuple[int, int, int]]
  ```
- Run `mypy --strict` and fix any issues

### 9. Add convenience methods

**Changes needed:**
- Add to `Deck` class:
  - `add_card(dbf_id: int, count: int = 1)` - add or increase card count
  - `remove_card(dbf_id: int, count: int = 1)` - remove or decrease card count
  - `copy()` - deep copy of deck
  - `to_dict()` - JSON-serializable representation
  - `from_dict(data)` - reconstruct from dict
  - `diff(other: Deck)` - return cards added/removed between two decks
  - `__eq__`, `__repr__` for comparison and debugging

### 10. Performance optimization

**Changes needed:**
- Cache `get_dbf_id_list()` result, invalidate on modification
- Sort once in `parse_deckstring`, avoid resorting in getters
- Pre-allocate BytesIO with estimated size in `write_deckstring`
- Profile with real-world workloads before optimizing further (this may not matter)

**Priority order for implementation:** 1 → 4 → 3 → 2 → 5 → 7 → 8 → 6 → 9 → 10