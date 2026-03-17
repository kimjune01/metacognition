# Diagnostic Report: Blizzard Deckstring Parser

## Observations

This system implements a codec for Hearthstone deck serialization using Blizzard's deckstring format. Current working capabilities:

1. **Deserialization** (`parse_deckstring`): Decodes base64-encoded deckstrings into structured deck data
   - Validates header (null byte) and version (currently version 1)
   - Extracts format type (Standard, Wild, etc.)
   - Parses hero cards with varint encoding
   - Parses main deck cards grouped by count (1x, 2x, n×)
   - Parses optional sideboard cards with owner references
   - Returns sorted card lists

2. **Serialization** (`write_deckstring`): Encodes deck data back into deckstring format
   - Writes header with version and format
   - Enforces single-hero constraint
   - Groups and sorts cards by count for space efficiency
   - Handles optional sideboard section
   - Base64 encodes the binary output

3. **Data Structures**:
   - `Deck` class with bidirectional deckstring conversion
   - Typed card list formats (CardList, CardIncludeList, SideboardList)
   - Varint encoding/decoding for compact integer representation

4. **Utilities**:
   - `trisort_cards`: Groups cards by count (1, 2, or n)
   - Sorted accessors for cards and sideboards by database ID

## Triage

### Critical Gaps (Production Blockers)

1. **No input validation** - System crashes on malformed input rather than providing actionable errors
2. **No error recovery** - Partial data loss on decode failure; no fallback behavior
3. **No tests** - Zero test coverage for a parser dealing with untrusted binary data
4. **Magic numbers** - Hard-coded hero count constraint (line 183) breaks with multi-hero formats

### High Priority (Data Integrity)

5. **No card database validation** - Accepts invalid card IDs that don't exist in Hearthstone
6. **No deck legality checking** - Doesn't enforce format rules (card limits, banned cards, class restrictions)
7. **Incomplete type annotations** - Return types use old-style tuple syntax; `IO` should be `IO[bytes]`
8. **Silent data truncation** - Reading beyond stream end in `_read_varint` gives generic `EOFError`

### Medium Priority (Usability)

9. **No logging or debugging** - Impossible to diagnose why a deckstring failed to parse
10. **No human-readable export** - Can't display deck contents without external card database
11. **Limited format support** - `FormatType` enum imported but not defined in this file
12. **No version migration** - If Blizzard releases v2 deckstrings, parser will reject them entirely

### Low Priority (Polish)

13. **Inconsistent naming** - `cardid` vs `card_id`, `cardlist` vs `card_list`
14. **No docstrings** - Public API lacks usage examples
15. **Redundant sorting** - Cards sorted multiple times (lines 115, 177, 186-190)

## Plan

### 1. Input Validation

**File**: Both parsing functions  
**Changes**:
- Add length checks before reading from stream: `if len(decoded) < 4: raise ValueError("Deckstring too short")`
- Validate hero count against known formats: Create `VALID_HERO_COUNTS = {1, 2}` constant for Standard/Duels
- Validate card counts: `if count < 1 or count > 99: raise ValueError(f"Invalid card count {count}")`
- Check for trailing data: After parsing, verify `data.read(1) == b""` to catch corrupted deckstrings

### 2. Error Recovery

**File**: `parse_deckstring`  
**Changes**:
- Wrap outer function in try/except: Catch `(EOFError, struct.error, ValueError)` and re-raise as custom `DeckstringDecodeError` with original deckstring attached
- Add partial decode mode: Optional parameter `strict=True`; when False, return whatever was successfully parsed plus a list of warnings
- Create `DeckstringDecodeError` exception class with `.partial_deck` and `.errors` attributes

### 3. Test Suite

**File**: New `test_deckstrings.py`  
**Changes**:
- Add roundtrip tests: 20+ known-good deckstrings from each format → parse → serialize → compare
- Add malformed input tests: Empty string, wrong version, truncated data, invalid base64, wrong hero count
- Add edge cases: Maximum card count (99×), empty deck, all sideboards, mixed counts
- Add property tests with Hypothesis: Generate random decks, verify roundtrip, verify sort stability

### 4. Remove Magic Numbers

**File**: `write_deckstring` line 183  
**Changes**:
- Replace `if len(heroes) != 1:` with format-aware validation:
  ```python
  expected_heroes = {FormatType.FT_STANDARD: 1, FormatType.FT_WILD: 1, 
                     FormatType.FT_CLASSIC: 1, FormatType.FT_TWIST: 1,
                     FormatType.FT_DUELS: 2}.get(format, 1)
  if len(heroes) != expected_heroes:
      raise ValueError(f"Format {format.name} requires {expected_heroes} heroes, got {len(heroes)}")
  ```

### 5. Card Database Integration

**File**: New optional parameter to Deck class  
**Changes**:
- Add `Deck.__init__(card_db: Optional[CardDatabase] = None)` parameter
- If `card_db` provided, validate card IDs on parse: `if cardid not in card_db: warnings.append(...)`
- Add `Deck.validate_legality()` method that checks format rules if database present
- Document that validation is opt-in for performance

### 6. Deck Legality

**File**: New `validate.py` module  
**Changes**:
- Create `validate_deck(deck: Deck, card_db: CardDatabase) -> List[str]` function
- Check rules: Class card restrictions, duplicate legendary limit, format bans, card count limits (30 for Standard)
- Return list of human-readable error strings: `["Deck contains 31 cards (max 30)", "Zilliax banned in Standard"]`

### 7. Improve Type Annotations

**File**: Function signatures throughout  
**Changes**:
- Change `IO` to `IO[bytes]` (lines 24, 38)
- Replace tuple return annotation `-> (Tuple[...])` with `-> Tuple[...]` (line 145)
- Add `from __future__ import annotations` for forward references
- Run `mypy --strict` and fix revealed issues

### 8. Better Error Messages

**File**: `_read_varint`  
**Changes**:
- Track bytes consumed: `bytes_read = []` before loop, append each byte
- On EOFError, show context: `raise EOFError(f"Unexpected EOF reading varint at offset {stream.tell()}, partial bytes: {bytes_read.hex()}")`
- Add offset tracking throughout parse: Pass `offset` parameter through all parse steps

### 9. Logging

**File**: Top of module  
**Changes**:
- Add `import logging; logger = logging.getLogger(__name__)`
- Log at DEBUG level: `logger.debug(f"Parsing deckstring version {version}, format {format}")`
- Log card counts: `logger.debug(f"Parsed {len(cards)} cards, {len(sideboards)} sideboard cards")`
- Log warnings: `logger.warning(f"Unknown card ID {cardid}")`

### 10. Human-Readable Export

**File**: New `Deck.to_dict()` method  
**Changes**:
```python
def to_dict(self, card_db: Optional[CardDatabase] = None) -> dict:
    return {
        "format": self.format.name,
        "heroes": [card_db.get_name(h) if card_db else h for h in self.heroes],
        "cards": [(card_db.get_name(c) if card_db else c, n) for c, n in self.cards],
        "sideboards": [...],
        "deckstring": self.as_deckstring
    }
```

### 11. Define FormatType

**File**: `enums.py` (create if doesn't exist)  
**Changes**:
- Define complete enum:
  ```python
  class FormatType(IntEnum):
      FT_UNKNOWN = 0
      FT_WILD = 1
      FT_STANDARD = 2
      FT_CLASSIC = 3
      FT_TWIST = 4
      FT_DUELS = 7
  ```
- Include in `__init__.py` exports

### 12. Version Migration

**File**: `parse_deckstring`  
**Changes**:
- Add `supported_versions: Set[int] = {1}` module constant
- Change version check to: `if version not in supported_versions: logger.warning(f"Unknown version {version}, attempting to parse"); # continue anyway`
- Add `Deck.deckstring_version: int` field to preserve original version
- Document forward compatibility: Ignore unknown trailing sections rather than failing

### 13. Naming Consistency

**File**: Throughout  
**Changes**:
- Standardize on snake_case: `cardid` → `card_id`, `cardlist` → `card_list`, `num_heroes` stays
- Run rename refactor: `git grep -l cardid | xargs sed -i 's/cardid/card_id/g'`
- Update variable names: `i` → `byte_value` (line 30), `c` → `byte_char` (line 27)

### 14. Documentation

**File**: All public functions and Deck class  
**Changes**:
- Add module docstring with example:
  ```python
  """
  Example:
      deck = Deck.from_deckstring("AAECAQcG...")
      print(deck.cards)  # [(1234, 2), (5678, 1)]
      print(deck.as_deckstring)  # "AAECAQcG..."
  """
  ```
- Add parameter descriptions in docstrings using Google style

### 15. Performance

**File**: `write_deckstring` and `trisort_cards`  
**Changes**:
- Cache sorted cards: `Deck._sorted_cards: Optional[CardIncludeList] = None`, invalidate on modification
- Single-pass trisort: Current version iterates full list 3× for append checks
- Remove redundant sorts: Sort once after trisort, not before and after