# Diagnostic Report: Hearthstone Deckstring Library

## Observations

This system implements the Blizzard deckstring format for encoding and decoding Hearthstone deck lists. Current working capabilities:

1. **Bidirectional conversion**: Encodes deck data to base64 deckstrings and decodes deckstrings back to structured data
2. **Variable-length integer encoding**: Implements varint read/write for compact binary representation
3. **Multi-count card handling**: Supports cards appearing 1×, 2×, or N× times with optimized storage (separate lists for common counts)
4. **Hero support**: Handles hero cards (currently validates exactly 1 hero)
5. **Format tracking**: Records deck format type (Wild, Standard, etc.) via `FormatType` enum
6. **Sideboard support**: Implements the sideboard extension (cards owned by other cards, used in some game modes)
7. **Sorting and organization**: Provides sorted accessors (`get_dbf_id_list`, `get_sideboard_dbf_id_list`)
8. **OOP interface**: `Deck` class wraps the functional parse/write operations

## Triage

### Critical (blocks production use)
1. **No error handling** - Silent failures or crashes on malformed input
2. **Missing validation** - No constraints on deck legality (size, duplicates, format rules)
3. **No documentation** - Function signatures lack docstrings, no usage examples
4. **Undefined dependency** - `FormatType` enum is imported but not defined

### Important (limits usability)
5. **Rigid hero constraint** - Hardcoded single-hero requirement breaks multi-hero formats
6. **No card database integration** - Works with opaque DBF IDs, no card name resolution
7. **Limited Deck API** - No methods to add/remove cards, query deck properties, or validate
8. **No type safety at boundaries** - Returns raw tuples instead of typed objects

### Nice-to-have (improves developer experience)
9. **No test coverage** - No unit tests visible for edge cases
10. **Inefficient sorting** - Re-sorts on every accessor call instead of maintaining sorted state
11. **No logging** - Debugging malformed deckstrings is opaque
12. **Python 2 compatibility remnants** - Type hints present but I/O handling could be modernized

## Plan

### 1. Error Handling
**Changes needed:**
- Wrap `base64.b64decode()` in try/except to catch `binascii.Error` for invalid base64
- Add bounds checking in `_read_varint()` to prevent infinite loops on corrupted data (max 10 iterations → ~10 byte ints)
- Create custom exceptions: `InvalidDeckstringError`, `UnsupportedVersionError`, `CorruptedDataError`
- Add try/except in `Deck.from_deckstring()` to re-raise with context

### 2. Validation
**Changes needed:**
- Add `validate()` method to `Deck` class checking:
  - Total card count (typically 30 for Hearthstone)
  - Max copies per card (2 for normal, 1 for Legendary)
  - Format-specific rules (no Wild cards in Standard)
- Add optional `strict` parameter to `parse_deckstring()` to toggle validation
- Create `DeckValidationError` exception with detailed failure messages

### 3. Documentation
**Changes needed:**
- Add module-level docstring explaining deckstring format and usage examples
- Document each function with:
  - Parameter types and meanings (e.g., "cardid: int - DBF ID from Hearthstone card database")
  - Return value structure (explain tuple formats)
  - Possible exceptions raised
- Add inline comments explaining binary format (varint encoding, trisort optimization)
- Create `examples/` directory with encode/decode samples

### 4. Define FormatType Enum
**Changes needed:**
- Create `enums.py` file with:
  ```python
  from enum import IntEnum
  
  class FormatType(IntEnum):
      FT_UNKNOWN = 0
      FT_WILD = 1
      FT_STANDARD = 2
      FT_CLASSIC = 3
      FT_TWIST = 4
  ```
- Or remove import and inline it if this is the only enum needed

### 5. Flexible Hero Handling
**Changes needed:**
- Remove `if len(heroes) != 1` check in `write_deckstring()`
- Add optional parameter: `write_deckstring(..., max_heroes: Optional[int] = None)`
- Validate hero count against `max_heroes` if provided
- Update `Deck.__init__()` docstring to note multi-hero support

### 6. Card Database Integration
**Changes needed:**
- Add optional `CardDatabase` class to map DBF IDs ↔ card names/metadata
- Add methods to `Deck`:
  - `get_card_names()` - returns list of human-readable card names
  - `from_card_names(names: List[str], db: CardDatabase)` - alternate constructor
- Keep DBF ID handling as core format, make names an optional layer

### 7. Enhanced Deck API
**Changes needed:**
- Add mutation methods:
  - `add_card(card_id: int, count: int = 1)`
  - `remove_card(card_id: int, count: int = 1)`
  - `set_hero(hero_id: int)`
- Add query methods:
  - `total_cards() -> int`
  - `contains(card_id: int) -> bool`
  - `get_count(card_id: int) -> int`
- Add `__len__()`, `__contains__()`, `__repr__()` magic methods

### 8. Type Safety
**Changes needed:**
- Create dataclasses/NamedTuples:
  ```python
  @dataclass
  class CardEntry:
      dbf_id: int
      count: int
  
  @dataclass  
  class SideboardEntry:
      dbf_id: int
      count: int
      owner_id: int
  ```
- Update return types from raw tuples to typed objects
- Update `CardList`, `CardIncludeList`, `SideboardList` to use these types

### 9. Test Coverage
**Changes needed:**
- Create `test_deckstring.py` with pytest covering:
  - Round-trip encode/decode on valid decks
  - Malformed base64 handling
  - Varint edge cases (0, max int, overflow)
  - Empty decks, single-card decks, 30-card decks
  - Sideboard presence/absence
  - All FormatTypes
- Add CI integration (GitHub Actions) to run tests on commit

### 10. Optimize Sorting
**Changes needed:**
- Cache sorted results: add `_sorted_cards: Optional[CardIncludeList] = None` to `Deck`
- Invalidate cache in mutation methods
- Update accessors:
  ```python
  def get_dbf_id_list(self) -> CardIncludeList:
      if self._sorted_cards is None:
          self._sorted_cards = sorted(self.cards, key=lambda x: x[0])
      return self._sorted_cards
  ```

### 11. Logging
**Changes needed:**
- Add `import logging` and `logger = logging.getLogger(__name__)`
- Log parse steps at DEBUG level: "Read format type: 2", "Parsed 28 cards"
- Log warnings for suspicious data: "Non-standard deck size: 35 cards"
- Add `--verbose` flag to any CLI tools built on this

### 12. Modernize I/O
**Changes needed:**
- Change type hints from `IO` to `BinaryIO` for clarity
- Replace `stream.read(1) == ""` with `stream.read(1) == b""` (already correct for bytes)
- Add `from __future__ import annotations` for forward-compatible type hints
- Consider using `struct.pack/unpack` instead of manual byte manipulation in varint encoding