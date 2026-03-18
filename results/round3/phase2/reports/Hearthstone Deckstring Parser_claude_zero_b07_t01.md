# Diagnostic Report: Hearthstone Deckstring Encoder/Decoder

## Observations

This system implements the Blizzard Deckstring format for Hearthstone deck encoding/decoding. Current working capabilities:

1. **Binary encoding/decoding**: Reads and writes variable-length integers (varint) for compact binary representation
2. **Deckstring parsing**: Decodes base64-encoded deckstrings into structured deck data (cards, heroes, format, sideboards)
3. **Deckstring generation**: Encodes deck components back into base64 deckstring format
4. **Card organization**: Groups cards by count (1x, 2x, n×) for efficient encoding
5. **Sideboard support**: Handles Hearthstone's sideboard mechanic with owner tracking
6. **Format type handling**: References `FormatType` enum for game format (Standard/Wild/etc.)
7. **OOP interface**: Provides `Deck` class with convenience methods for common operations
8. **Sorting utilities**: Maintains canonical ordering for cards and sideboards

## Triage

### Critical Gaps

1. **No error recovery** - Malformed deckstrings or corrupted data cause crashes rather than graceful failures
2. **Missing validation** - No deck rule enforcement (card limits, format legality, hero class restrictions)
3. **No `enums.py` module** - `FormatType` import will fail; missing critical dependency

### Important Gaps

4. **Limited documentation** - No docstrings, usage examples, or format specification reference
5. **No testing** - Zero test coverage for parsing, encoding, edge cases
6. **Incomplete type hints** - Return type annotations use outdated tuple syntax instead of modern typing
7. **Magic numbers** - Hardcoded constants (0x7f, 0x80, version checks) lack explanation

### Nice-to-Have

8. **No deck manipulation API** - Can't easily add/remove cards after construction
9. **Limited introspection** - Missing methods for deck statistics (total cards, dust cost, etc.)
10. **Performance unoptimized** - Repeated sorting operations, inefficient BytesIO usage

## Plan

### 1. Error Recovery
**Changes needed:**
- Wrap `_read_varint` EOF handling in custom exception class `DeckstringParseError`
- Add try-catch in `parse_deckstring` with context about where parsing failed
- Validate base64 before decoding (catch `binascii.Error`)
- Add bounds checking for card counts and IDs
- Return `Result[Deck, Error]` pattern or raise specific exceptions with helpful messages

### 2. Validation Layer
**Changes needed:**
- Create `DeckValidator` class with methods:
  - `validate_card_count(cards, format)` - check 30-card limit, 2× legendary rule
  - `validate_hero_class(heroes, cards)` - ensure cards match hero class
  - `validate_format_legality(cards, format)` - check if cards are legal in format
- Add optional `strict` parameter to `Deck.from_deckstring()` to enable validation
- Require card database integration (HearthstoneJSON or similar) for full validation

### 3. Create enums.py Module
**Changes needed:**
- Create `enums.py` file in same directory with:
```python
from enum import IntEnum

class FormatType(IntEnum):
    FT_UNKNOWN = 0
    FT_WILD = 1
    FT_STANDARD = 2
    FT_CLASSIC = 3
    FT_TWIST = 4
```
- Add all known format types based on current Hearthstone game modes

### 4. Documentation
**Changes needed:**
- Add module-level docstring explaining Blizzard deckstring format with link to spec
- Add docstrings to all public methods with Args/Returns/Raises sections
- Create `examples/` directory with:
  - `basic_usage.py` - encoding/decoding example
  - `deck_manipulation.py` - building decks programmatically
  - `validation_example.py` - validating against game rules
- Add inline comments explaining varint encoding, trisort logic, sideboard format

### 5. Testing
**Changes needed:**
- Create `tests/test_deckstring.py` with pytest:
  - Test roundtrip encoding/decoding with known good deckstrings
  - Test each format type (Standard, Wild, Classic, Twist)
  - Test edge cases: empty sideboards, max count cards, single hero
  - Test error conditions: invalid base64, wrong version, EOF during parse
  - Test trisort with various card distributions
- Aim for >90% coverage

### 6. Modern Type Hints
**Changes needed:**
- Replace `Tuple[CardIncludeList, CardList, FormatType, SideboardList]` with explicit class or `NamedTuple`
- Use `tuple[int, int]` instead of `Tuple[int, int]` (Python 3.9+)
- Add `from __future__ import annotations` for forward references
- Replace `Sequence[tuple]` with specific types like `Sequence[CardTuple]`
- Run `mypy --strict` and fix all violations

### 7. Document Magic Numbers
**Changes needed:**
- Extract constants at module level:
```python
VARINT_CONTINUATION_BIT = 0x80
VARINT_VALUE_MASK = 0x7f
DECKSTRING_HEADER = b"\0"
SIDEBOARD_PRESENT = b"\1"
SIDEBOARD_ABSENT = b"\0"
```
- Add comment explaining varint encoding standard (Protocol Buffers Base 128)

### 8. Deck Manipulation API
**Changes needed:**
- Add methods to `Deck` class:
  - `add_card(dbf_id: int, count: int = 1) -> None`
  - `remove_card(dbf_id: int, count: int = 1) -> None`
  - `add_sideboard_card(dbf_id: int, owner: int, count: int = 1) -> None`
  - `clear() -> None`
  - `copy() -> Deck` - deep copy for deck variations
- Maintain internal consistency (re-sort after modifications)

### 9. Introspection Methods
**Changes needed:**
- Add to `Deck` class:
  - `total_cards() -> int` - sum of main deck card counts
  - `contains_card(dbf_id: int) -> bool`
  - `get_card_count(dbf_id: int) -> int`
  - `get_all_dbf_ids() -> Set[int]` - unique card IDs
  - `__repr__` and `__str__` for debugging

### 10. Performance Optimization
**Changes needed:**
- Cache sorted card lists in `Deck` class, invalidate on modification
- Use `io.BytesIO` buffer size hint: `BytesIO(len(cards) * 10)`
- Profile with `cProfile` on large deck collections
- Consider lazy sorting - only sort when encoding, not on every access
- Replace repeated tuple sorting with single sort + groupby operation