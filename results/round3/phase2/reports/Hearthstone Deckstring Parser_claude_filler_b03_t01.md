# Diagnostic Report: Hearthstone Deckstring Encoder/Decoder

## Observations

This system implements the Blizzard Deckstring format, a compact binary encoding for Hearthstone deck lists. Current working capabilities:

1. **Binary Protocol Implementation**
   - Variable-length integer (varint) encoding/decoding for space-efficient storage
   - Base64 encoding/decoding for string representation
   - BytesIO stream-based reading/writing

2. **Deckstring Parsing**
   - Decodes base64 deckstrings into structured deck data
   - Extracts version, format type, heroes, main deck cards, and sideboards
   - Validates protocol version (expects version 1)
   - Supports card counts of 1x, 2x, and arbitrary N copies (tri-sorted by count)
   - Handles sideboard cards with owner associations

3. **Deckstring Generation**
   - Encodes deck data back to base64 deckstring format
   - Tri-sorts cards by count (1x/2x/Nx) for efficient encoding
   - Supports optional sideboard section
   - Maintains sorted order for canonical representation

4. **Deck Object Model**
   - `Deck` class with `from_deckstring()` factory method
   - Properties: cards, heroes, format, sideboards
   - `as_deckstring` property for serialization
   - Helper methods: `get_dbf_id_list()`, `get_sideboard_dbf_id_list()`

5. **Format Support**
   - References `FormatType` enum (imported but not shown)
   - Validates format types during parsing

## Triage

### Critical Gaps

1. **No Error Handling Beyond Parsing** - The system raises generic exceptions but doesn't handle recoverable errors or provide user-friendly messages for common failure modes.

2. **Missing Validation Logic** - No validation that deck composition follows game rules (card limits, format legality, hero class restrictions).

3. **No Tests** - Production code requires comprehensive test coverage for both parsing and encoding, especially for edge cases.

### Important Gaps

4. **Incomplete Type Annotations** - While type hints exist, the `IO` type is too generic; should be `IO[bytes]`. Return type annotations missing on some methods.

5. **No Logging or Debugging Support** - No instrumentation for troubleshooting malformed deckstrings in production.

6. **Missing Documentation** - No docstrings explaining the deckstring format, version compatibility, or usage examples.

7. **Hero Count Validation Too Strict** - Hardcoded check for exactly 1 hero (`if len(heroes) != 1`) may break for future game modes (Duos, Tavern Brawls).

### Minor Gaps

8. **No Deck Validation Methods** - Missing helpers like `is_valid()`, `get_total_cards()`, `get_dust_cost()`.

9. **Limited Sideboard API** - No methods to add/remove sideboard cards, query by owner, or validate sideboard rules.

10. **No Pretty Printing** - No human-readable string representation (`__str__`, `__repr__`).

11. **Performance Not Optimized** - Multiple sorts happen during encoding; could be optimized with single-pass sorting.

## Plan

### 1. Error Handling Beyond Parsing

**Changes needed:**
- Add custom exception hierarchy:
  ```python
  class DeckstringError(Exception): pass
  class InvalidDeckstringError(DeckstringError): pass
  class UnsupportedVersionError(DeckstringError): pass
  class InvalidFormatError(DeckstringError): pass
  ```
- Wrap `base64.b64decode()` to catch `binascii.Error` and raise `InvalidDeckstringError`
- Add try/except in `parse_deckstring()` to catch EOF gracefully
- Include partial deckstring in error messages for debugging (first 20 chars)

### 2. Validation Logic

**Changes needed:**
- Add `Deck.validate()` method that checks:
  - Total cards equals 30 (or game-mode-specific limit)
  - No more than 2 copies of non-legendary cards
  - No more than 1 copy of legendary cards
  - All cards valid for the specified format
  - Hero matches card class restrictions
- Require external card database dependency (dbf_id → card metadata)
- Add `validate_on_parse` parameter to `from_deckstring()` (default False for backward compatibility)
- Return `ValidationResult` object with errors and warnings lists

### 3. Test Coverage

**Changes needed:**
- Create `test_deckstring.py` with pytest
- Test cases needed:
  - Round-trip encoding/decoding (encode→decode→encode should be stable)
  - All card count categories (1x, 2x, Nx with n=3,4,5)
  - Empty sideboards vs missing sideboard flag
  - Invalid base64 input
  - Truncated deckstrings (EOF during parse)
  - Unsupported versions (0, 2, 255)
  - Invalid format types
  - Multiple heroes (should fail currently)
  - Known valid deckstrings from real decks
- Property-based tests with Hypothesis for fuzzing

### 4. Type Annotation Fixes

**Changes needed:**
- Change `IO` to `IO[bytes]` in `_read_varint` and `_write_varint`
- Add return types to all methods:
  ```python
  def get_dbf_id_list(self) -> CardIncludeList:
  def as_deckstring(self) -> str:
  ```
- Run mypy in strict mode and fix all warnings
- Consider using `Protocol` for stream types if supporting both BytesIO and file objects

### 5. Logging and Debugging

**Changes needed:**
- Add `logging` module at top: `logger = logging.getLogger(__name__)`
- Log at DEBUG level:
  - Start of parse with deckstring length
  - Each section parsed (version, format, heroes count, cards by type)
  - Start of encode with deck summary
- Log at WARNING level for unusual but valid conditions:
  - Format type not in known enums but still valid integer
  - More than 30 cards
  - Unusual card counts (>2 copies)

### 6. Documentation

**Changes needed:**
- Add module docstring explaining:
  - Deckstring format specification reference
  - Version compatibility
  - Basic usage example
- Add class docstring to `Deck`:
  ```python
  """Represents a Hearthstone deck with cards, heroes, format, and optional sideboards.
  
  Example:
      deck = Deck.from_deckstring("AAECAa0GBvgC...")
      print(deck.format)  # FormatType.FT_STANDARD
      cards = deck.get_dbf_id_list()
  """
  ```
- Add docstrings to `parse_deckstring()` and `write_deckstring()` explaining parameters and return values
- Add inline comments explaining varint encoding and tri-sorting rationale

### 7. Hero Count Flexibility

**Changes needed:**
- Remove hardcoded `if len(heroes) != 1:` check in `write_deckstring()`
- Add optional `max_heroes` parameter with default None (no limit)
- Change validation to:
  ```python
  if max_heroes is not None and len(heroes) > max_heroes:
      raise ValueError(f"Too many heroes: {len(heroes)} > {max_heroes}")
  if len(heroes) == 0:
      raise ValueError("At least one hero required")
  ```
- Document supported hero counts per game mode

### 8. Deck Validation Methods

**Changes needed:**
- Add to `Deck` class:
  ```python
  def is_valid(self, card_db: CardDatabase) -> bool:
      """Check if deck follows game rules."""
      
  def get_total_cards(self) -> int:
      """Return sum of all card counts."""
      return sum(count for _, count in self.cards)
      
  def get_dust_cost(self, card_db: CardDatabase) -> Tuple[int, int]:
      """Return (craft_cost, disenchant_value) in dust."""
  ```
- Requires `CardDatabase` interface definition

### 9. Sideboard API Enhancement

**Changes needed:**
- Add methods:
  ```python
  def get_sideboard_for_card(self, owner_dbf_id: int) -> List[Tuple[int, int]]:
      """Get sideboard cards for specific owner card."""
      return [(cid, cnt) for cid, cnt, owner in self.sideboards if owner == owner_dbf_id]
      
  def add_sideboard_card(self, card_id: int, count: int, owner_id: int) -> None:
      """Add card to sideboard for owner."""
      
  def remove_sideboard_card(self, card_id: int, owner_id: int) -> None:
      """Remove card from sideboard."""
  ```
- Add validation that owner cards exist in main deck

### 10. Pretty Printing

**Changes needed:**
- Add to `Deck` class:
  ```python
  def __repr__(self) -> str:
      return f"Deck(format={self.format.name}, heroes={self.heroes}, cards={len(self.cards)}, sideboards={len(self.sideboards)})"
      
  def __str__(self) -> str:
      return self.as_deckstring
      
  def to_text(self, card_db: CardDatabase) -> str:
      """Human-readable deck list with card names."""
      lines = [f"# Format: {self.format.name}"]
      lines.append(f"# Hero: {card_db.get_name(self.heroes[0])}")
      for card_id, count in sorted(self.cards, key=lambda x: card_db.get_name(x[0])):
          lines.append(f"{count}x {card_db.get_name(card_id)}")
      return "\n".join(lines)
  ```

### 11. Performance Optimization

**Changes needed:**
- Cache sorted lists to avoid re-sorting:
  ```python
  def _get_sorted_cards(self) -> Tuple[List, List, List]:
      if not hasattr(self, '_sorted_cache'):
          self._sorted_cache = trisort_cards(self.cards)
      return self._sorted_cache
  ```
- Invalidate cache when cards modified
- Profile with `cProfile` on 1000-deck encoding benchmark
- Consider using `bisect` for maintaining sorted order during insertion