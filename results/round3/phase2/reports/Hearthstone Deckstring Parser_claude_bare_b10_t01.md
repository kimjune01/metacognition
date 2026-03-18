# Diagnostic Report: Blizzard Deckstring Parser

## Observations

This system implements a binary serialization format for Hearthstone deck codes. Its working capabilities include:

1. **Deckstring Parsing** - Decodes base64-encoded binary deckstrings into structured deck data containing:
   - Card lists with card IDs and counts
   - Hero cards
   - Format type (Wild, Standard, etc.)
   - Sideboard cards (with owner associations)

2. **Deckstring Writing** - Encodes deck data back into the compact deckstring format

3. **Varint Encoding/Decoding** - Implements variable-length integer encoding for space efficiency

4. **Card Organization** - Sorts and groups cards by count (1x, 2x, n×) for optimal encoding

5. **Object-Oriented Interface** - Provides a `Deck` class with:
   - Factory method from deckstring
   - Property accessor for deckstring serialization
   - Methods to retrieve sorted card/sideboard lists

6. **Format Validation** - Checks for valid deckstring headers and version numbers

## Triage

### Critical Gaps

1. **No Error Handling** - The system crashes on malformed input rather than providing useful error messages. Production systems need graceful degradation.

2. **Missing Format Type Definitions** - References `FormatType` enum that isn't defined in this file. The system is incomplete without knowing valid format values.

3. **No Documentation** - Zero docstrings on public API. Users can't discover how to use `Deck`, what card IDs mean, or what the tuple formats represent.

### Important Gaps

4. **No Validation Logic** - Doesn't verify deck legality (card count limits, format restrictions, valid hero/card combinations).

5. **Limited Test Coverage Implied** - No visible tests, assertions, or examples demonstrating correctness.

6. **Incomplete Type Hints** - Uses generic `List[int]` and tuples without descriptive type aliases. The difference between `(card_id, count)` and `(card_id, count, owner)` is unclear.

### Nice-to-Have Gaps

7. **No Pretty Printing** - Can't display a human-readable deck list (e.g., "2x Fireball, 1x Alexstrasza").

8. **No Mutation Methods** - Can't add/remove cards from a `Deck` instance after creation.

9. **Missing Utility Functions** - No helpers for common operations (deck cost curve, card count totals, format detection).

10. **No Backwards Compatibility Strategy** - If `DECKSTRING_VERSION` changes, old deckstrings become unreadable.

## Plan

### 1. Error Handling (Critical)

**Changes needed:**

- Wrap `base64.b64decode()` in try/except to catch invalid base64 with message: "Deckstring is not valid base64"
- Add bounds checking in varint reader: if stream ends unexpectedly, raise `ValueError("Truncated deckstring")`
- Validate card counts are positive: `if count < 1: raise ValueError(f"Invalid card count {count} for card {card_id}")`
- Add try/except around entire `parse_deckstring` with contextual error messages
- Create custom exception class `DeckstringError(ValueError)` for distinguishing from other errors

### 2. Format Type Definitions (Critical)

**Changes needed:**

- Create `enums.py` file with:
  ```python
  from enum import IntEnum
  
  class FormatType(IntEnum):
      FT_UNKNOWN = 0
      FT_WILD = 1
      FT_STANDARD = 2
      FT_CLASSIC = 3
  ```
- Document what each format means in docstring

### 3. Documentation (Critical)

**Changes needed:**

- Add module docstring explaining Blizzard's deckstring format with example
- Document `Deck` class with usage example:
  ```python
  """
  Represents a Hearthstone deck.
  
  Example:
      deck = Deck.from_deckstring("AAECAa0GBPsM...")
      print(deck.heroes)  # [637]
      print(deck.cards)   # [(1004, 2), (1363, 1), ...]
  """
  ```
- Add docstrings to all public methods explaining parameters and return types
- Document tuple formats: "Cards are (dbf_id, count), sideboards are (dbf_id, count, owner_card_dbf_id)"

### 4. Validation Logic (Important)

**Changes needed:**

- Add `STANDARD_DECK_SIZE = 30` constant
- Create `validate()` method on `Deck`:
  ```python
  def validate(self, check_legality: bool = False) -> List[str]:
      """Returns list of validation errors, empty if valid."""
      errors = []
      total = sum(count for _, count in self.cards)
      if total != STANDARD_DECK_SIZE:
          errors.append(f"Deck has {total} cards, expected {STANDARD_DECK_SIZE}")
      if not self.heroes:
          errors.append("Deck has no hero")
      # Add more checks if check_legality=True
      return errors
  ```

### 5. Type Hints Enhancement (Important)

**Changes needed:**

- Create type aliases at module level:
  ```python
  DbfId = int
  CardCount = int
  Card = Tuple[DbfId, CardCount]
  SideboardCard = Tuple[DbfId, CardCount, DbfId]  # last is owner card
  ```
- Update all signatures: `CardIncludeList = List[Card]`, etc.
- Add `from __future__ import annotations` for forward references

### 6. Pretty Printing (Nice-to-have)

**Changes needed:**

- Add dependency on card database or accept card name mapping as parameter
- Implement `__str__` on `Deck`:
  ```python
  def __str__(self, card_names: Optional[Dict[int, str]] = None) -> str:
      """Returns human-readable deck list."""
      lines = [f"# Hero: {self.heroes[0]}"]
      for dbf_id, count in sorted(self.cards, key=lambda x: x[1], reverse=True):
          name = card_names.get(dbf_id, f"Card#{dbf_id}") if card_names else str(dbf_id)
          lines.append(f"{count}x {name}")
      return "\n".join(lines)
  ```

### 7. Mutation Methods (Nice-to-have)

**Changes needed:**

- Add methods to `Deck` class:
  ```python
  def add_card(self, dbf_id: DbfId, count: CardCount = 1) -> None:
      """Add cards to deck, combining with existing copies."""
      
  def remove_card(self, dbf_id: DbfId, count: CardCount = 1) -> None:
      """Remove cards from deck."""
      
  def set_hero(self, dbf_id: DbfId) -> None:
      """Replace hero."""
  ```

### 8. Utility Functions (Nice-to-have)

**Changes needed:**

- Add to `Deck` class:
  ```python
  def total_cards(self) -> int:
      return sum(count for _, count in self.cards)
      
  def unique_cards(self) -> int:
      return len(self.cards)
      
  def contains_card(self, dbf_id: DbfId) -> bool:
      return any(card_id == dbf_id for card_id, _ in self.cards)
  ```

### 9. Version Compatibility (Nice-to-have)

**Changes needed:**

- Support reading multiple versions:
  ```python
  SUPPORTED_VERSIONS = {1, 2}  # if v2 ever exists
  
  if version not in SUPPORTED_VERSIONS:
      raise ValueError(f"Unsupported version {version}, expected {SUPPORTED_VERSIONS}")
  ```
- Add migration logic if format changes in future versions

### 10. Testing (Important)

**Changes needed:**

- Create `test_deckstring.py` with:
  - Known valid deckstrings as fixtures
  - Round-trip tests (parse → write → parse should be identical)
  - Error case tests (truncated, invalid base64, bad version)
  - Edge cases (empty sideboard, maximum card counts)