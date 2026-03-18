# Diagnostic Report: Hearthstone Deckstring Library

## Observations

This system implements the Blizzard Deckstring format for encoding and decoding Hearthstone deck configurations. Current working capabilities:

1. **Binary encoding/decoding**: Reads and writes variable-length integers (varint) for space-efficient storage
2. **Deckstring parsing**: Decodes base64-encoded deckstrings into structured data (cards, heroes, format, sideboards)
3. **Deckstring generation**: Encodes deck configurations back into base64 deckstring format
4. **Card organization**: Tri-sorts cards by count (×1, ×2, ×N) for optimized encoding
5. **Sideboard support**: Handles sideboard cards with ownership tracking
6. **Format type handling**: Supports FormatType enum for game modes (Standard, Wild, etc.)
7. **OOP interface**: Provides `Deck` class with convenience methods (`from_deckstring`, `as_deckstring`, getters)
8. **Version control**: Implements versioning (currently v1) for forward compatibility

## Triage

### Critical Gaps (Production Blockers)
1. **No validation** - No verification of deck legality (card limits, deck size, hero class restrictions)
2. **No error handling** - Minimal exception handling; corrupt data could crash silently
3. **No tests** - Zero test coverage for a serialization library
4. **Missing enums.py** - Imports `FormatType` but file doesn't exist in provided code

### High Priority (Quality Issues)
5. **No documentation** - No docstrings, usage examples, or API documentation
6. **Type hints incomplete** - Return type annotations use tuples instead of proper types
7. **No logging** - Debugging corrupt deckstrings would be difficult
8. **Magic numbers** - Hardcoded values (e.g., `b"\0"`, `b"\1"`) lack explanation

### Medium Priority (Usability)
9. **Limited querying** - Can't filter cards by rarity, cost, class, etc.
10. **No card metadata** - Only stores DBF IDs, no names/costs/descriptions
11. **Inflexible hero validation** - Hardcoded single-hero requirement breaks multi-hero formats
12. **No export formats** - Can't convert to JSON, CSV, or human-readable text

### Low Priority (Nice-to-Have)
13. **Performance not optimized** - Multiple sorts could be reduced
14. **No versioning strategy** - Claims v1 support but no migration path for v2
15. **Incomplete sideboard API** - No methods to add/remove sideboard cards programmatically

## Plan

### 1. Add Validation (Critical)
**Changes needed:**
- Create `validate()` method in `Deck` class
- Check deck size (30 cards for Standard, up to 40 for some formats)
- Verify card count limits (max 2 per card, legendaries max 1)
- Validate hero/class restrictions (cards must match hero class + neutral)
- Add `strict` parameter to `from_deckstring()` to optionally skip validation
- Raise `InvalidDeckError` custom exception with descriptive messages

### 2. Robust Error Handling (Critical)
**Changes needed:**
- Add try-except blocks around `base64.b64decode()` with `InvalidDeckstringError`
- Handle `EOFError` from `_read_varint()` with clearer "truncated deckstring" message
- Add bounds checking for varints (prevent negative counts, overflow attacks)
- Validate format byte is in known `FormatType` range
- Add optional `skip_unknown_format` parameter for forward compatibility

### 3. Comprehensive Test Suite (Critical)
**Changes needed:**
- Create `tests/test_deckstring.py` with pytest
- Test cases: encoding/decoding round-trip, empty decks, max-size decks, sideboards
- Negative tests: corrupt base64, invalid format bytes, wrong version numbers
- Property-based tests: any valid deck should encode then decode identically
- Edge cases: 0-count cards, >2 count cards, multiple heroes

### 4. Create Missing Dependencies (Critical)
**Changes needed:**
- Create `enums.py` with `FormatType` IntEnum
- Define values: `FT_UNKNOWN = 0, FT_WILD = 1, FT_STANDARD = 2, FT_CLASSIC = 3, FT_TWIST = 4`
- Export from `__init__.py` for public API

### 5. Add Documentation (High)
**Changes needed:**
- Add module docstring explaining Blizzard deckstring format
- Document each public method with docstrings (Google or NumPy style)
- Create `README.md` with installation, quickstart, examples
- Add inline comments for non-obvious sections (varint encoding, tri-sorting algorithm)
- Link to official Blizzard deckstring spec if available

### 6. Fix Type Hints (High)
**Changes needed:**
- Replace `(Tuple[CardIncludeList, CardList, FormatType, SideboardList])` with proper return types
- Create `NamedTuple` or `@dataclass` for parsed deckstring results
- Add `from __future__ import annotations` for forward references
- Run `mypy --strict` and fix all type errors

### 7. Add Structured Logging (High)
**Changes needed:**
- Import Python's `logging` module
- Log warnings for unknown format types (forward compat)
- Log debug info: decoded byte lengths, card counts, parsing steps
- Add `logger = logging.getLogger(__name__)` at module level

### 8. Document Magic Constants (High)
**Changes needed:**
- Replace `b"\0"` with `DECKSTRING_HEADER = b"\0"` constant
- Replace `b"\1"` with `HAS_SIDEBOARDS_FLAG = b"\1"` constant
- Add comments explaining varint bit manipulation (`0x7f`, `0x80`)
- Extract `0x7f` and `0x80` as `VARINT_SEGMENT_BITS` and `VARINT_CONTINUE_BIT`

### 9. Add Card Querying (Medium)
**Changes needed:**
- Add `get_cards_by_cost(cost: int)` method (requires card database integration)
- Add `get_cards_by_rarity(rarity: Rarity)` method
- Add `get_total_dust_cost()` method
- Add optional `card_database` parameter to `Deck.__init__()` for metadata lookup

### 10. Integrate Card Metadata (Medium)
**Changes needed:**
- Add optional `CardDatabase` class to resolve DBF IDs → card objects
- Modify `Deck` to store `Card` objects with name, cost, rarity, text
- Add `dbf_id_only_mode` flag for backward compatibility
- Create `Card` dataclass with all relevant attributes

### 11. Relax Hero Validation (Medium)
**Changes needed:**
- Remove hardcoded `if len(heroes) != 1` check
- Add format-specific validation: Standard/Wild require 1, Tavern Brawl may allow multiple
- Move validation to separate `validate()` method (see #1)
- Add `allow_multiple_heroes` parameter

### 12. Add Export Formats (Medium)
**Changes needed:**
- Add `to_json()` method returning dict with card names, counts
- Add `to_human_readable()` returning multiline string "2x Fireball\n1x Alexstrasza"
- Add `from_json()` classmethod for round-trip serialization
- Consider `to_csv()` for spreadsheet export

### 13. Optimize Performance (Low)
**Changes needed:**
- Cache sorted results in `Deck` to avoid re-sorting on every access
- Replace multiple `sorted()` calls with single sort + split by count
- Profile with `cProfile` on large decks to identify bottlenecks
- Consider `__slots__` for `Deck` class if memory is concern

### 14. Version Migration Strategy (Low)
**Changes needed:**
- Add `DeckstringParser` abstract base class
- Implement `DeckstringV1Parser`, `DeckstringV2Parser` subclasses
- Add parser registry that dispatches by version byte
- Document version differences in migration guide

### 15. Improve Sideboard API (Low)
**Changes needed:**
- Add `add_sideboard_card(card_id: int, count: int, owner: int)` method
- Add `remove_sideboard_card(card_id: int, owner: int)` method
- Add `clear_sideboard()` method
- Add `get_sideboard_for_owner(owner: int)` method returning filtered list