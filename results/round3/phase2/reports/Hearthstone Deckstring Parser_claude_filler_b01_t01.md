# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements a parser and encoder for Blizzard's Hearthstone deckstring format. Current working capabilities:

1. **Deckstring Decoding**: Parses base64-encoded binary deckstrings into structured deck data
   - Reads header with version and format type
   - Extracts hero card(s)
   - Parses main deck cards grouped by count (1x, 2x, n×)
   - Parses optional sideboard cards with owner references
   - Handles variable-length integer encoding (varint)

2. **Deckstring Encoding**: Converts deck data back into deckstring format
   - Writes binary format with proper varint encoding
   - Sorts and groups cards by count for optimal encoding
   - Handles sideboard sections with conditional writing
   - Base64 encodes the binary output

3. **Deck Object Model**: Provides a `Deck` class that:
   - Constructs from deckstrings via `from_deckstring()`
   - Exports to deckstrings via `as_deckstring` property
   - Stores cards, heroes, format type, and sideboards
   - Provides sorted accessor methods for DBF IDs

4. **Data Structure Management**: 
   - Tri-sorts cards into 1×, 2×, and n× groups for efficient encoding
   - Maintains proper sorting for deterministic output
   - Handles both main deck and sideboard card lists

## Triage

### Critical Gaps

1. **No Error Handling** - System fails silently or with generic exceptions
2. **No Validation** - Accepts invalid deck compositions without checking game rules
3. **No Tests** - Zero test coverage for parsing, encoding, or edge cases
4. **Missing Documentation** - No docstrings explaining parameters, return types, or format specification

### Important Gaps

5. **No Round-Trip Verification** - No guarantee that encode(decode(x)) == x
6. **Limited Type Safety** - Type hints exist but aren't comprehensive; no runtime validation
7. **No Logging** - Debugging issues requires modifying code
8. **Incomplete Format Support** - Hard-coded assumption of single hero (multi-hero formats exist)

### Nice-to-Have Gaps

9. **No Card Database Integration** - Cannot validate card IDs or fetch card metadata
10. **No Human-Readable Export** - Cannot display deck in text format
11. **No Import from Alternative Formats** - Only supports deckstring, not other deck formats
12. **Performance Not Optimized** - Uses BytesIO for small buffers; no benchmarking

## Plan

### 1. Add Error Handling

**Current state**: `ValueError` and `EOFError` raised with minimal context; truncated deckstrings cause unclear failures.

**Changes needed**:
- Create custom exception hierarchy:
  ```python
  class DeckstringError(Exception): pass
  class InvalidDeckstringFormat(DeckstringError): pass
  class UnsupportedVersion(DeckstringError): pass
  class TruncatedDeckstring(DeckstringError): pass
  ```
- Wrap base64 decode in try-except to catch `binascii.Error`
- Add context to all exceptions (e.g., "Expected format marker 0x00, got 0x{value:02x}")
- Handle partial reads in `_read_varint` with informative error messages
- Validate stream position matches expected length after parsing

### 2. Implement Deck Validation

**Current state**: Accepts any card counts and combinations; no game rule enforcement.

**Changes needed**:
- Add `validate()` method to `Deck` class that checks:
  - Hero count matches format requirements (1 for Standard, potentially more for Duels)
  - Total card count (30 for Standard, 40 for Twist, etc.)
  - Max copies per card (2 for most cards, 1 for Legendaries)
  - Cards legal in specified format
- Create validation rule classes for different format types
- Add optional strict/permissive validation modes
- Return validation result object with specific error messages per violation

### 3. Add Comprehensive Test Suite

**Current state**: No tests exist.

**Changes needed**:
- Create `tests/test_deckstring.py` with:
  - `test_parse_valid_deckstrings()`: 20+ real deckstrings from various formats
  - `test_parse_invalid_deckstrings()`: Malformed inputs, wrong versions, truncated data
  - `test_encode_roundtrip()`: Verify decode(encode(deck)) produces identical deck
  - `test_varint_encoding()`: Edge cases (0, 127, 128, 65535, large numbers)
  - `test_card_sorting()`: Verify deterministic output for same deck
  - `test_sideboard_handling()`: With/without sideboards, multiple owners
  - `test_error_messages()`: Verify exceptions contain useful context
- Add property-based tests using hypothesis for fuzzing
- Achieve >95% code coverage
- Add performance benchmarks for common operations

### 4. Add Complete Documentation

**Current state**: Module docstring only; no function/class documentation.

**Changes needed**:
- Add docstrings to all public functions/classes following numpy style:
  ```python
  def parse_deckstring(deckstring: str) -> Tuple[...]:
      """Parse a Hearthstone deckstring into components.
      
      Parameters
      ----------
      deckstring : str
          Base64-encoded deckstring (e.g., "AAECAa0G...")
          
      Returns
      -------
      cards : list of (int, int)
          Card DBF IDs with counts
      heroes : list of int
          Hero card DBF IDs
      format : FormatType
          Game format enum value
      sideboards : list of (int, int, int)
          Sideboard cards with counts and owner IDs
          
      Raises
      ------
      InvalidDeckstringFormat
          If deckstring cannot be decoded or has wrong header
      """
  ```
- Add module-level documentation explaining the binary format specification
- Create examples in docstrings showing common usage patterns
- Document the varint encoding scheme
- Add README.md with quick start guide

### 5. Implement Round-Trip Verification

**Current state**: No mechanism to verify encoding correctness.

**Changes needed**:
- Add `verify_roundtrip()` static method to `Deck` class:
  ```python
  @staticmethod
  def verify_roundtrip(deckstring: str) -> bool:
      deck = Deck.from_deckstring(deckstring)
      roundtrip = deck.as_deckstring
      return deckstring == roundtrip
  ```
- Add optional `verify=True` parameter to `from_deckstring()` that automatically checks round-trip
- Create test corpus of real deckstrings and verify all round-trip correctly
- Handle cases where multiple valid encodings exist (order of equal-count cards)
- Add CI job that runs round-trip tests on all examples

### 6. Strengthen Type Safety

**Current state**: Type hints present but incomplete; no runtime validation.

**Changes needed**:
- Add type hints to all internal functions including `_read_varint` and `_write_varint`
- Use `TypedDict` for structured return values instead of raw tuples
- Add runtime type checking in `__init__` methods:
  ```python
  def __init__(self):
      self._cards: CardIncludeList = []
      
  @property
  def cards(self) -> CardIncludeList:
      return self._cards
      
  @cards.setter
  def cards(self, value: CardIncludeList) -> None:
      if not isinstance(value, list):
          raise TypeError("cards must be a list")
      # Additional validation...
      self._cards = value
  ```
- Use `Protocol` classes for IO streams instead of bare `IO` type
- Enable mypy strict mode and resolve all errors
- Consider using Pydantic models for structured data

### 7. Add Logging Support

**Current state**: No diagnostic output; debugging requires print statements.

**Changes needed**:
- Import Python logging module at top
- Add logger instance: `logger = logging.getLogger(__name__)`
- Add debug logs at key points:
  - "Parsing deckstring of length {len}" at parse start
  - "Read version={version}, format={format}" after header
  - "Parsed {count} heroes: {heroes}" after hero section
  - "Parsed {total} cards: {x1}×1, {x2}×2, {xn}×n" after cards
- Add info logs for validation failures
- Add trace logs for varint reads in verbose mode
- Document logging setup in README

### 8. Remove Hard-Coded Single Hero Assumption

**Current state**: Line 220 raises `ValueError` if `len(heroes) != 1`.

**Changes needed**:
- Remove the hard-coded check in `write_deckstring()`
- Add format-specific validation in `Deck.validate()` method:
  ```python
  def validate(self) -> ValidationResult:
      if self.format == FormatType.FT_STANDARD:
          if len(self.heroes) != 1:
              return ValidationResult(valid=False, 
                  errors=["Standard format requires exactly 1 hero"])
      elif self.format == FormatType.FT_TWIST:
          if len(self.heroes) != 2:
              return ValidationResult(valid=False,
                  errors=["Twist format requires exactly 2 heroes"])
  ```
- Update parsing logic to handle hero lists of any length
- Add test cases for multi-hero formats (Duels, Twist)
- Document hero count requirements per format in docstrings

### 9. Add Card Database Integration (Optional Enhancement)

**Current state**: Works only with integer card IDs; no card metadata.

**Changes needed**:
- Create optional `CardDatabase` class that loads from JSON/SQLite
- Add methods to `Deck` class:
  ```python
  def get_card_names(self, db: CardDatabase) -> List[str]:
      return [db.get_name(card_id) for card_id, _ in self.cards]
      
  def to_human_readable(self, db: CardDatabase) -> str:
      # Returns formatted deck list with card names
  ```
- Make database optional (don't break existing functionality)
- Add example showing how to integrate with HearthstoneJSON
- Document database schema requirements

### 10. Add Text Format Export

**Current state**: Only binary deckstring format supported.

**Changes needed**:
- Add `to_text()` method to `Deck` class:
  ```python
  def to_text(self, card_db: Optional[CardDatabase] = None) -> str:
      """Export deck as human-readable text.
      
      Format:
      # Deck: Aggro Demon Hunter
      # Format: Standard
      # Class: Demon Hunter
      # 
      # 2× (1) Card Name
      # 1× (3) Another Card
      """
  ```
- Support import from text format via `from_text()` class method
- Handle card names → DBF ID lookup (requires card database)
- Support popular text formats (Hearthstone in-game, HSReplay, etc.)
- Add configuration for format customization

### 11. Add Alternative Format Support

**Current state**: Only supports native deckstring format.

**Changes needed**:
- Create `DeckImporter` abstract base class with subclasses:
  - `DeckstringImporter` (current implementation)
  - `HSReplayImporter` (parse XML from HSReplay)
  - `HearthpwnImporter` (parse Hearthpwn URLs/IDs)
- Add factory method: `Deck.from_format(data, format_type='auto')`
- Auto-detect format based on input pattern (base64 vs XML vs URL)
- Maintain backward compatibility with existing `from_deckstring()`
- Document supported formats and provide examples

### 12. Optimize Performance

**Current state**: No performance measurement; potential inefficiencies.

**Changes needed**:
- Replace `BytesIO` with direct `bytearray` manipulation for encoding:
  ```python
  def _write_varint_to_buffer(buf: bytearray, i: int) -> None:
      # Append directly to bytearray instead of writing to stream
  ```
- Cache sorted card lists in `Deck` to avoid repeated sorting
- Profile with cProfile on large datasets (1000+ deckstrings)
- Add benchmark suite comparing different implementations
- Document performance characteristics in README
- Consider Cython extension for varint encoding if needed at scale
- Add performance regression tests to CI