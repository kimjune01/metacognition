# Diagnostic Report: Hearthstone Deckstring Codec

## Observations

This system implements the Blizzard Deckstring format parser and encoder for Hearthstone deck codes. Current working capabilities:

1. **Decoding deckstrings** - Parses base64-encoded deck codes into structured data containing:
   - Card lists with counts (1x, 2x, or Nx copies)
   - Hero cards (currently enforced as single hero)
   - Format type (Wild, Standard, etc.)
   - Sideboard cards with owner associations

2. **Encoding deckstrings** - Converts deck data back to base64-encoded strings using the same format

3. **Varint I/O** - Implements variable-length integer encoding/decoding for compact binary representation

4. **Card organization** - Trisorts cards by count (1x, 2x, Nx) for optimal encoding

5. **Deck object model** - Provides a `Deck` class with convenience methods for working with deck data

6. **Format validation** - Validates format types against `FormatType` enum and version checking (expects version 1)

## Triage

### Critical Gaps

1. **No error handling for malformed input** - Production code needs resilient parsing with clear error messages for corrupted/invalid deckstrings
   - Severity: HIGH - Will crash on unexpected input

2. **Missing card validation** - No verification that card DBF IDs are valid or that deck composition meets game rules
   - Severity: HIGH - Will accept nonsensical decks

3. **No deck constraint validation** - Doesn't enforce deck size limits, card count restrictions, or format-specific rules
   - Severity: HIGH - Core game logic missing

### Important Gaps

4. **Limited multi-hero support** - Hardcoded to single hero (`len(heroes) != 1` raises), but reads multiple heroes from deckstring
   - Severity: MEDIUM - Blocks Duels/dual-class deck support

5. **No sideboard validation** - Accepts arbitrary sideboard configurations without checking game rules
   - Severity: MEDIUM - For modes that use sideboards

6. **Missing documentation** - No docstrings, usage examples, or format specification reference
   - Severity: MEDIUM - Developer experience issue

### Minor Gaps

7. **Type annotations incomplete** - Uses type aliases but not fully typed (e.g., `stream: IO` should be `IO[bytes]`)
   - Severity: LOW - Type checking won't catch IO mode errors

8. **No unit tests visible** - Can't verify correctness or prevent regressions
   - Severity: LOW - Test coverage concern (may exist elsewhere)

9. **Performance not optimized** - BytesIO operations could be batched, sorting happens multiple times
   - Severity: LOW - Unlikely bottleneck for typical usage

## Plan

### 1. Error Handling & Input Validation

**Changes needed:**
- Wrap `parse_deckstring` body in try/except to catch `EOFError`, `ValueError`, `base64.binascii.Error`
- Add custom exception class: `class InvalidDeckstringError(ValueError)`
- Validate input string is non-empty before base64 decode
- Check stream position after parsing - if not at EOF, raise error (trailing garbage)
- Add length sanity checks: `if num_cards_x1 > 1000: raise ValueError(...)`

### 2. Card and DBF ID Validation

**Changes needed:**
- Add dependency on card database (or accept optional validator callback)
- In `Deck.__init__`, add `card_db: Optional[CardDatabase] = None` parameter
- After parsing, iterate cards and validate: `if not card_db.is_valid_dbf_id(card_id): raise InvalidCardError(...)`
- Validate hero cards are actually hero type: `if not card_db.is_hero(hero_id): raise ValueError(...)`

### 3. Deck Constraint Validation

**Changes needed:**
- Add `Deck.validate()` method that checks:
  - Total card count matches format (30 for Standard/Wild, variable for other modes)
  - No more than 2 copies of non-legendary cards (or 1 for Highlander decks)
  - Cards are legal in the specified format
  - Hero class matches card class restrictions
- Make validation opt-in via `Deck.from_deckstring(deckstring, validate=False)`
- Return list of validation errors rather than raising (better UX)

### 4. Multi-Hero Support

**Changes needed:**
- Remove hard check: `if len(heroes) != 1: raise ValueError(...)`
- Replace with: `if not (1 <= len(heroes) <= 2): raise ValueError("Expected 1-2 heroes")`
- Add `Deck.is_dual_class` property
- Update validation logic to handle dual-class restrictions per format

### 5. Sideboard Validation

**Changes needed:**
- Add `Deck.validate_sideboards()` helper method
- Check sideboard owners are valid hero DBF IDs from the deck's hero list
- Enforce sideboard size limits per game mode (if applicable)
- Validate sideboard cards meet same format/class restrictions

### 6. Documentation

**Changes needed:**
- Add module docstring with format specification link: `https://hearthsim.info/docs/deckstrings/`
- Add docstrings to all public functions/methods:
  ```python
  def parse_deckstring(deckstring: str) -> Tuple[...]:
      """Parse a Hearthstone deckstring into components.
      
      Args:
          deckstring: Base64-encoded deck code
          
      Returns:
          Tuple of (cards, heroes, format, sideboards)
          
      Raises:
          InvalidDeckstringError: If deckstring is malformed
      """
  ```
- Add usage example in module docstring

### 7. Type Annotation Improvements

**Changes needed:**
- Fix IO types: `IO` → `IO[bytes]`
- Add `from __future__ import annotations` for forward references
- Add explicit return type to `__init__`: `def __init__(self) -> None:`
- Make type aliases more specific:
  ```python
  CardList = List[int]  # Hero DBF IDs
  CardIncludeList = List[Tuple[int, int]]  # (card_dbf_id, count)
  SideboardCard = Tuple[int, int, int]  # (card_dbf_id, count, owner_hero_dbf_id)
  SideboardList = List[SideboardCard]
  ```

### 8. Testing Infrastructure

**Changes needed:**
- Create `tests/test_deckstring.py`
- Add test cases for:
  - Valid deckstrings (Standard, Wild, with/without sideboards)
  - Round-trip encoding/decoding
  - Malformed input (invalid base64, wrong version, truncated data)
  - Edge cases (0 cards, maximum cards, Nx counts)
- Add property-based tests with `hypothesis` for fuzzing

### 9. Performance Optimization

**Changes needed:**
- Cache sorted results in `trisort_cards` if called multiple times
- Pre-allocate BytesIO with estimated size: `BytesIO(bytearray(estimated_size))`
- Consider lazy sorting: only sort when `as_deckstring` is called
- Profile with `cProfile` on large deck collections to identify real bottlenecks (only optimize if needed)