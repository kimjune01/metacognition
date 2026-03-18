# Diagnostic Report: Hearthstone Deckstring Library

## Observations

This system implements the Blizzard deckstring format encoder/decoder for Hearthstone deck lists. Current working capabilities:

1. **Deckstring Parsing** - Decodes base64-encoded deckstrings into structured deck data including cards, heroes, format type, and sideboards
2. **Deckstring Generation** - Encodes deck data back into the standard deckstring format
3. **Varint I/O** - Implements variable-length integer encoding/decoding for compact binary representation
4. **Card Organization** - Tri-sorts cards by count (1x, 2x, n×) for efficient encoding
5. **Sideboard Support** - Handles sideboard cards with owner references (added in later deckstring versions)
6. **Format Validation** - Checks deckstring version (v1) and format type enum
7. **Deck Class API** - Provides OOP interface with `from_deckstring()` constructor and `as_deckstring` property
8. **Sorted Output** - Returns cards and sideboards in sorted order by DBF ID

## Triage

### Critical Gaps (Blocks Production Use)

1. **No Error Recovery** - Parser fails catastrophically on malformed input with generic exceptions
2. **Missing Input Validation** - No checks for logical constraints (deck size limits, card count limits, duplicate cards)
3. **No Documentation** - Zero docstrings; public API is undocumented
4. **Untested** - No test suite visible; unclear if edge cases work correctly

### Important Gaps (Limits Usability)

5. **Hero Validation is Half-Implemented** - Code enforces exactly 1 hero but comments "Heroes section" suggesting multi-hero was considered; unclear if this is correct for all formats
6. **No Card Database Integration** - Works only with DBF IDs; no way to work with card names or validate IDs exist
7. **Limited Type Hints** - Missing generic types on methods; `IO` is too broad (should be `IO[bytes]`)
8. **No Logging** - Silent failures or successes; difficult to debug issues

### Minor Gaps (Nice-to-Have)

9. **No CLI Interface** - Library only; no command-line tool for quick encoding/decoding
10. **No String Representation** - `Deck.__repr__()` not implemented; difficult to inspect in REPL
11. **Immutability Not Enforced** - Deck properties are mutable lists; callers can corrupt state
12. **No Version Migration** - Only supports v1; no forward compatibility mechanism

## Plan

### 1. Error Recovery (Critical)

**Changes needed:**
- Replace generic `ValueError` with custom exception hierarchy: `DeckstringError` (base), `InvalidFormatError`, `CorruptedDataError`, `UnsupportedVersionError`
- In `parse_deckstring()`, wrap base64 decode in try/except and raise `InvalidFormatError` with user-friendly message
- In varint readers, catch EOFError and reraise as `CorruptedDataError` with offset information
- Add bounds checking in loops (e.g., verify card counts are positive)

### 2. Input Validation (Critical)

**Changes needed:**
- Create `validate_deck()` function that checks:
  - Total card count (standard: 30, some formats: 40)
  - Per-card limits (standard: 2×, legendaries: 1×)
  - Valid format/hero combinations
- Call validator in `Deck.__init__()` and `from_deckstring()` with optional `strict=True` parameter
- In `write_deckstring()`, validate before encoding:
  - Heroes list not empty
  - Card DBF IDs are positive integers
  - Counts are positive

### 3. Documentation (Critical)

**Changes needed:**
- Add module docstring explaining deckstring format and Blizzard's specification
- Document every public method and class with parameters, return types, and examples:
  ```python
  def from_deckstring(cls, deckstring: str) -> "Deck":
      """Parse a Hearthstone deckstring into a Deck object.
      
      Args:
          deckstring: Base64-encoded deck string (e.g., "AAECAa0GBg...")
          
      Returns:
          Deck instance with parsed cards, heroes, and format
          
      Raises:
          InvalidFormatError: If deckstring is not valid base64
          UnsupportedVersionError: If version != 1
      """
  ```
- Add usage examples to README

### 4. Test Suite (Critical)

**Changes needed:**
- Create `tests/test_deckstring.py` with pytest
- Add test cases for:
  - Round-trip encoding (decode → encode → decode produces same result)
  - Known good deckstrings from official Blizzard sources
  - Malformed input (truncated, invalid base64, wrong version)
  - Edge cases (empty sideboards, maximum card counts, all formats)
  - Varint boundary values (0, 127, 128, 16383, etc.)

### 5. Hero Validation (Important)

**Changes needed:**
- Research current deckstring spec for multi-hero formats (Tavern Brawl, Duels)
- Replace hardcoded `if len(heroes) != 1` check with format-aware validation:
  ```python
  HERO_LIMITS = {
      FormatType.FT_STANDARD: 1,
      FormatType.FT_WILD: 1,
      FormatType.FT_TWIST: 1,
      FormatType.FT_CLASSIC: 1,
      # Add multi-hero formats if they exist
  }
  ```
- Add validation in `write_deckstring()` using lookup table

### 6. Card Database Integration (Important)

**Changes needed:**
- Add optional `CardDatabase` class that maps DBF ID ↔ card name
- Add `Deck.get_card_names(db: CardDatabase) -> List[str]` method
- Add alternate constructor `Deck.from_card_names(names, hero, format, db)`
- Keep DBF ID as internal representation but expose name-based API

### 7. Type Hints (Important)

**Changes needed:**
- Change `IO` to `IO[bytes]` in varint functions
- Add TypeVar for generic deck iteration:
  ```python
  from typing import TypeVar, Generic
  T = TypeVar('T')
  ```
- Use `Sequence` instead of `List` for read-only parameters
- Add `@overload` for functions with optional parameters

### 8. Logging (Important)

**Changes needed:**
- Add `import logging` and create logger: `logger = logging.getLogger(__name__)`
- Log at DEBUG level for parsing steps: "Read 15 cards (5×1, 8×2, 2×n)"
- Log at WARNING for suspicious data: "Unusual card count: 7×Archmage (DBF 1234)"
- Log at INFO for successful operations: "Decoded deckstring: Standard Mage (30 cards)"

### 9. CLI Interface (Minor)

**Changes needed:**
- Create `__main__.py` with argparse:
  ```bash
  python -m deckstring decode "AAECAa0G..."
  python -m deckstring encode --cards cards.txt --hero 637 --format 2
  ```
- Support stdin/stdout for piping
- Add `--json` flag for structured output

### 10. String Representation (Minor)

**Changes needed:**
- Implement `__repr__()`: `Deck(format=FT_STANDARD, heroes=[637], cards=30, sideboards=0)`
- Implement `__str__()` with human-readable format showing card counts

### 11. Immutability (Minor)

**Changes needed:**
- Make `cards`, `heroes`, `sideboards` return copies: `return self._cards.copy()`
- Document that returned lists are snapshots
- Consider making `Deck` frozen dataclass in Python 3.10+

### 12. Version Migration (Minor)

**Changes needed:**
- Add `SUPPORTED_VERSIONS = [1]` constant
- In parser, check `if version not in SUPPORTED_VERSIONS` before detailed error
- Add placeholder for v2 parser: `_parse_v2()` with NotImplementedError
- Document how to extend for future versions in developer guide