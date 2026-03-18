# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements Blizzard's deckstring format encoder/decoder for Hearthstone deck codes. Current working capabilities:

1. **Decoding**: Parses base64-encoded deckstrings into structured deck data
   - Extracts format type, heroes, main deck cards, and sideboard cards
   - Handles variable-length integer encoding (varint protocol)
   - Supports cards with counts of 1, 2, or N (optimized encoding)
   - Supports sideboard cards with owner associations

2. **Encoding**: Converts deck data structures back to deckstring format
   - Writes header (version 1, format type)
   - Encodes heroes and cards using varint compression
   - Maintains sorted order for deterministic output
   - Includes optional sideboard section

3. **Data Structures**: Provides `Deck` class wrapper
   - Factory method `from_deckstring()`
   - Property `as_deckstring` for encoding
   - Sorted access methods for cards and sideboards

4. **Protocol Support**: Implements binary format specification
   - Zero-byte header marker
   - Version negotiation (currently v1 only)
   - Tri-sorted card encoding (1x, 2x, Nx optimization)
   - Optional sideboard marker byte

## Triage

### Critical Gaps

1. **Error Handling** - No graceful handling of malformed input
   - Truncated deckstrings cause EOFError
   - Invalid base64 raises unhandled exceptions
   - No validation of card counts, hero counts, or format values beyond single-hero check
   - **Impact**: System crashes on bad user input

2. **Testing** - No test coverage visible
   - No unit tests for encode/decode roundtrips
   - No edge case testing (empty decks, maximum cards, invalid formats)
   - No regression tests for deckstring format changes
   - **Impact**: Cannot verify correctness or catch regressions

### High Priority Gaps

3. **Documentation** - Missing critical usage information
   - No docstrings on public functions
   - No examples of encoding/decoding
   - FormatType enum referenced but not defined in this file
   - Card ID (dbf_id) system not explained
   - **Impact**: Difficult to integrate or maintain

4. **Validation** - No business logic constraints enforced
   - Doesn't validate deck size limits (typically 30 cards in Hearthstone)
   - Doesn't check format-specific rules (e.g., Wild vs Standard legality)
   - Allows invalid hero counts (writes exactly 1, but reads N)
   - No validation that card IDs exist
   - **Impact**: Can create invalid decks

5. **Type Safety** - Incomplete type hints
   - Return type annotation uses old-style tuple syntax `-> (Tuple[...])`
   - Type aliases defined but not consistently used
   - No runtime validation of types
   - **Impact**: Poor IDE support, harder to catch bugs

### Medium Priority Gaps

6. **Multi-Hero Support** - Partial implementation
   - Reads N heroes but enforces exactly 1 hero on write
   - Comment suggests this is known limitation
   - **Impact**: Cannot encode dual-class or multi-hero decks

7. **Logging/Debugging** - No observability
   - Silent parsing failures in some code paths
   - No debug output for troubleshooting malformed decks
   - **Impact**: Hard to diagnose user issues

8. **Performance** - Inefficient operations
   - Multiple sorts on same data
   - BytesIO operations could be buffered better
   - No caching of encoded deckstrings
   - **Impact**: Minor, but noticeable for batch operations

### Low Priority Gaps

9. **Version Support** - Only supports v1
   - Hard-coded `DECKSTRING_VERSION = 1`
   - Would require code changes for v2 format
   - **Impact**: Future compatibility concern

10. **API Ergonomics** - Minor usability issues
    - `Deck` class mostly a thin wrapper, limited utility
    - Could support initialization with cards/heroes directly
    - No `__repr__` or `__eq__` for debugging
    - **Impact**: Slightly awkward to use

## Plan

### 1. Error Handling

**Changes needed:**
- Wrap `base64.b64decode()` in try-except for `binascii.Error`
- Add `try-except EOFError` around varint reads with context message
- Create custom exception classes:
  ```python
  class DeckstringError(Exception): pass
  class InvalidDeckstringFormat(DeckstringError): pass
  class UnsupportedVersion(DeckstringError): pass
  ```
- Add validation helper:
  ```python
  def _validate_card_count(count: int) -> None:
      if count < 1 or count > 255:
          raise InvalidDeckstringFormat(f"Invalid card count: {count}")
  ```
- Wrap all parsing logic in `parse_deckstring()` to catch and re-raise with context

### 2. Testing

**Changes needed:**
- Create `test_deckstring.py` with pytest
- Add fixtures for known-good deckstrings from Hearthstone client
- Test cases needed:
  - Roundtrip: encode(decode(x)) == x for various decks
  - Empty deck edge case
  - Single card deck
  - 30-card deck with 1x, 2x, and Nx cards
  - Deck with sideboards
  - Truncated deckstring (expect error)
  - Invalid base64 (expect error)
  - Unsupported version (expect error)
- Add property-based tests using Hypothesis for fuzzing

### 3. Documentation

**Changes needed:**
- Add module docstring with example:
  ```python
  """
  Blizzard Deckstring format support for Hearthstone.
  
  Example:
      >>> deck = Deck.from_deckstring("AAECAa0GBPsM...")
      >>> deck.heroes
      [7]
      >>> deck.format
      <FormatType.FT_STANDARD: 2>
  """
  ```
- Add docstrings to all public functions with Args/Returns/Raises sections
- Document varint format reference: "Uses protobuf-style varint encoding"
- Add inline comments for binary format structure in parse/write functions
- Create README.md with format specification overview

### 4. Validation

**Changes needed:**
- Add `validate()` method to `Deck` class:
  ```python
  def validate(self, strict: bool = False) -> List[str]:
      """Returns list of validation errors, empty if valid."""
      errors = []
      total_cards = sum(count for _, count in self.cards)
      if total_cards > 30:
          errors.append(f"Deck has {total_cards} cards, max 30")
      if strict:
          # Check format-specific rules, card legality, etc.
          pass
      return errors
  ```
- Add deck size check in `write_deckstring()` with optional `validate=True` param
- Validate hero count consistency: allow N heroes on both read and write
- Add optional `card_db` parameter to check card ID validity

### 5. Type Safety

**Changes needed:**
- Fix return type syntax:
  ```python
  # Old:
  def parse_deckstring(deckstring) -> (Tuple[...]):
  
  # New:
  def parse_deckstring(deckstring: str) -> tuple[CardIncludeList, CardList, FormatType, SideboardList]:
  ```
- Add type hints to all parameters
- Import `from typing import Protocol` and define card database protocol
- Run `mypy --strict` and fix all errors

### 6. Multi-Hero Support

**Changes needed:**
- Remove hero count validation in `write_deckstring()`:
  ```python
  # Delete this check:
  if len(heroes) != 1:
      raise ValueError(...)
  ```
- Update `Deck` class to accept multiple heroes in constructor
- Add comment documenting when multi-hero was introduced (game patch version)
- Test with dual-class decks from actual client

### 7. Logging/Debugging

**Changes needed:**
- Add optional logging:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  
  def parse_deckstring(...):
      logger.debug(f"Parsing deckstring: {deckstring[:20]}...")
      # ... existing code ...
      logger.debug(f"Decoded {len(cards)} cards, format={format}")
  ```
- Add `Deck.__repr__()`:
  ```python
  def __repr__(self) -> str:
      return f"<Deck heroes={self.heroes} cards={len(self.cards)} format={self.format}>"
  ```

### 8. Performance

**Changes needed:**
- Cache sorted results in `Deck`:
  ```python
  @functools.lru_cache(maxsize=1)
  def get_dbf_id_list(self) -> CardIncludeList:
      return sorted(self.cards, key=lambda x: x[0])
  ```
- Pre-allocate BytesIO with estimated size in `write_deckstring()`
- Avoid redundant sorts in `trisort_cards()` by sorting once at end
- Profile with `cProfile` on 10k deck encode/decode cycle

### 9. Version Support

**Changes needed:**
- Create version registry:
  ```python
  SUPPORTED_VERSIONS = {1: (parse_v1, write_v1)}
  
  def parse_deckstring(...):
      version = _read_varint(data)
      if version not in SUPPORTED_VERSIONS:
          raise UnsupportedVersion(f"Version {version} not supported")
      parser, _ = SUPPORTED_VERSIONS[version]
      return parser(data)
  ```
- Move current logic to `parse_v1()` and `write_v1()` functions
- Add extensibility for future format changes

### 10. API Ergonomics

**Changes needed:**
- Add `Deck.__init__()` parameters:
  ```python
  def __init__(
      self,
      cards: Optional[CardIncludeList] = None,
      heroes: Optional[CardList] = None,
      format: FormatType = FormatType.FT_UNKNOWN,
      sideboards: Optional[SideboardList] = None
  ):
      self.cards = cards or []
      self.heroes = heroes or []
      self.format = format
      self.sideboards = sideboards or []
  ```
- Add `Deck.__eq__()` for comparison
- Add convenience methods like `add_card()`, `remove_card()`, `get_card_count()`
- Consider builder pattern for complex deck construction