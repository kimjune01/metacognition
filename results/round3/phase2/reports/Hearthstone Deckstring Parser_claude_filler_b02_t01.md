# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements Blizzard's proprietary deckstring encoding format for Hearthstone deck serialization. Current working capabilities:

1. **Binary varint I/O** - Reads and writes variable-length integers using protocol buffer-style encoding (7 bits data + 1 continuation bit per byte)

2. **Deckstring parsing** - Decodes base64-encoded binary deckstrings into structured deck data:
   - Format version validation (currently supports version 1)
   - Game format type (Standard/Wild/etc.)
   - Hero card IDs
   - Main deck cards with counts
   - Sideboard cards (owner + count associations)

3. **Deckstring generation** - Encodes deck data back to base64 deckstring format with optimized storage:
   - Cards grouped by count (1x, 2x, n×) to minimize bytes
   - Sorted output for canonical representation

4. **Deck object model** - `Deck` class provides:
   - Factory method `from_deckstring()`
   - Property accessor `as_deckstring`
   - Sorted accessors for cards and sideboards

5. **Sideboard support** - Handles the sideboard extension to the format (optional trailing section with owner associations)

## Triage

### Critical Gaps

1. **No error recovery or validation** - Parser accepts malformed input silently or crashes with unclear errors
   - Impact: Production crashes, unclear user feedback
   - Missing: Card count limits, duplicate detection, deck size validation

2. **Zero documentation** - No docstrings, format specification, or usage examples
   - Impact: Integration errors, maintenance burden
   - Missing: Module/class/method docstrings, specification reference

3. **No testing** - No unit tests, integration tests, or test fixtures
   - Impact: Regression risk, refactoring paralysis
   - Missing: Test suite covering parse/write round-trips, edge cases, error conditions

### Important Gaps

4. **Limited error messages** - Generic ValueErrors with minimal context
   - Impact: Debugging difficulty, poor UX
   - Missing: Specific exception types, line numbers, invalid value details

5. **Type hints incomplete** - Some type annotations present but inconsistent
   - Impact: IDE support degraded, type checking limited
   - Missing: Return type for `__init__`, IO parameter specificity

6. **No logging** - Silent operation with no observability
   - Impact: Production debugging difficulty
   - Missing: Debug/info level logging for parse stages

### Nice-to-Have Gaps

7. **No deck validation rules** - Doesn't enforce Hearthstone game rules
   - Impact: Invalid decks can be encoded
   - Missing: Class card restrictions, legendary limits, format legality

8. **No human-readable representation** - Can't pretty-print decks
   - Impact: Debugging inconvenience
   - Missing: `__str__`, `__repr__` methods

9. **Inefficient repeated sorting** - Sorts cards multiple times during write
   - Impact: Minor performance overhead
   - Missing: Single sort with stable partitioning

## Plan

### 1. Add comprehensive validation

**Changes needed:**
- In `parse_deckstring()`, after reading cards section:
  ```python
  if len(cards) < 1:
      raise DeckstringFormatError("Deck must contain at least 1 card")
  if len(cards) > 30:  # Standard deck limit
      raise DeckstringFormatError(f"Deck contains {len(cards)} cards, maximum is 30")
  
  card_ids = [card[0] for card in cards]
  if len(card_ids) != len(set(card_ids)):
      raise DeckstringFormatError("Deck contains duplicate card entries")
  ```

- In `write_deckstring()`, validate before encoding:
  ```python
  if not cards:
      raise ValueError("Cannot encode empty deck")
  if not heroes:
      raise ValueError("Deck must specify at least one hero")
  if any(count < 1 for _, count in cards):
      raise ValueError("Card counts must be positive")
  ```

### 2. Create exception hierarchy

**Changes needed:**
- Add new file `exceptions.py`:
  ```python
  class DeckstringError(Exception):
      """Base exception for deckstring operations"""
      pass
  
  class DeckstringFormatError(DeckstringError):
      """Raised when deckstring format is invalid"""
      pass
  
  class DeckstringVersionError(DeckstringError):
      """Raised when deckstring version is unsupported"""
      def __init__(self, version: int):
          super().__init__(f"Unsupported deckstring version {version}")
          self.version = version
  ```

- Replace all `ValueError` raises with specific exception types
- Add context to error messages with position/offset information

### 3. Add comprehensive docstrings

**Changes needed:**
- Module-level docstring:
  ```python
  """
  Blizzard Deckstring format support for Hearthstone.
  
  Implements the binary deckstring format used by Hearthstone to encode
  deck lists as short base64 strings for sharing. Format specification:
  https://hearthsim.info/docs/deckstrings/
  
  Basic usage:
      >>> deck = Deck.from_deckstring("AAECAa0GBo...")
      >>> print(deck.heroes)
      [813]
      >>> print(deck.as_deckstring)
      "AAECAa0GBo..."
  """
  ```

- Class docstring for `Deck`:
  ```python
  """
  Represents a Hearthstone deck with cards, heroes, and format.
  
  Attributes:
      cards: List of (card_dbf_id, count) tuples for main deck
      heroes: List of hero card DBF IDs
      format: FormatType enum value (Wild, Standard, etc.)
      sideboards: List of (card_id, count, owner_id) tuples
  """
  ```

- Document all public functions with parameters, returns, raises sections

### 4. Build test suite

**Changes needed:**
- Create `test_deckstring.py`:
  ```python
  import pytest
  from .deckstring import Deck, parse_deckstring, write_deckstring
  
  # Known good deckstring from Blizzard
  SAMPLE_DECKSTRING = "AAECAa0GBo..."
  
  def test_parse_write_roundtrip():
      """Parsing and writing should be inverse operations"""
      cards, heroes, fmt, sideboards = parse_deckstring(SAMPLE_DECKSTRING)
      result = write_deckstring(cards, heroes, fmt, sideboards)
      assert result == SAMPLE_DECKSTRING
  
  def test_empty_deckstring_raises():
      with pytest.raises(ValueError):
          parse_deckstring("")
  
  def test_invalid_version_raises():
      # Construct deckstring with version 99
      bad_string = "AAL..."  # version byte != 1
      with pytest.raises(DeckstringVersionError):
          parse_deckstring(bad_string)
  ```

- Add tests for: edge cases (1-card decks, 30-card decks), sideboard handling, malformed input, varint edge cases

### 5. Improve type annotations

**Changes needed:**
- Fix `__init__` return type:
  ```python
  def __init__(self) -> None:
      self.cards: CardIncludeList = []
      # ...
  ```

- Specify IO type more precisely:
  ```python
  from typing import BinaryIO
  
  def _read_varint(stream: BinaryIO) -> int:
      # ...
  
  def _write_varint(stream: BinaryIO, i: int) -> int:
      # ...
  ```

- Add `Protocol` for duck-typed IO if needed for BytesIO compatibility

### 6. Add logging infrastructure

**Changes needed:**
- Import and configure logger:
  ```python
  import logging
  
  logger = logging.getLogger(__name__)
  ```

- Add strategic logging points:
  ```python
  def parse_deckstring(deckstring) -> ...:
      logger.debug(f"Parsing deckstring of length {len(deckstring)}")
      decoded = base64.b64decode(deckstring)
      logger.debug(f"Decoded to {len(decoded)} bytes")
      
      format = _read_varint(data)
      logger.debug(f"Format: {format}")
      # ...
  ```

### 7. Add human-readable output

**Changes needed:**
- Implement `__str__` and `__repr__`:
  ```python
  def __repr__(self) -> str:
      return f"Deck(heroes={self.heroes}, cards={len(self.cards)}, format={self.format.name})"
  
  def __str__(self) -> str:
      lines = [f"Format: {self.format.name}"]
      lines.append(f"Hero: {self.heroes[0]}")
      lines.append("Cards:")
      for card_id, count in sorted(self.cards):
          lines.append(f"  {count}× Card #{card_id}")
      return "\n".join(lines)
  ```

- Optionally add pretty-printing with card names if card database available

### 8. Optimize sorting performance

**Changes needed:**
- In `write_deckstring()`, sort once and partition:
  ```python
  # Sort all cards once by ID
  sorted_cards = sorted(cards, key=lambda x: x[0])
  
  # Partition by count in single pass
  cards_x1 = [(id, c) for id, c in sorted_cards if c == 1]
  cards_x2 = [(id, c) for id, c in sorted_cards if c == 2]
  cards_xn = [(id, c) for id, c in sorted_cards if c > 2]
  
  # Already sorted, no need to re-sort
  for cardlist in cards_x1, cards_x2:
      _write_varint(data, len(cardlist))
      for cardid, _ in cardlist:
          _write_varint(data, cardid)
  ```

- Similar optimization for sideboards section

### 9. Add optional game rules validation

**Changes needed:**
- Create `validation.py` module:
  ```python
  class DeckValidator:
      def __init__(self, card_database):
          self.card_db = card_database
      
      def validate_deck(self, deck: Deck) -> List[str]:
          """Returns list of validation errors, empty if valid"""
          errors = []
          
          # Check legendary limits
          for card_id, count in deck.cards:
              card = self.card_db.get(card_id)
              if card.rarity == Rarity.LEGENDARY and count > 1:
                  errors.append(f"Legendary card {card_id} has count {count}")
          
          # Check format legality
          # Check class restrictions
          # etc.
          
          return errors
  ```

- Make validation optional (requires external card database), expose via `Deck.validate()` method