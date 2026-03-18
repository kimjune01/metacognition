# Diagnostic Report: Blizzard Deckstring Format Support

## Observations

This system currently provides the following working capabilities:

1. **Bidirectional deckstring encoding/decoding** - Converts between Hearthstone deck representations and base64-encoded deckstrings using Blizzard's official format
2. **Varint serialization** - Implements variable-length integer encoding for compact binary representation
3. **Deck data structure** - `Deck` class that encapsulates cards, heroes, format type, and sideboards
4. **Trisort optimization** - Separates cards into 1x, 2x, and n-copy buckets to minimize encoded size
5. **Sideboard support** - Handles optional sideboard cards with owner associations (for game modes like Duels)
6. **Format type tracking** - Preserves deck format (Standard, Wild, Classic, etc.)
7. **Sorted output** - Maintains deterministic ordering for cards and sideboards
8. **Version handling** - Encodes/decodes with version number (currently v1)

## Triage

### Critical Gaps
1. **No error recovery or validation** - Invalid deckstrings crash rather than providing useful errors
2. **No card count constraints** - Doesn't enforce deck size limits (30 cards) or card copy limits (2 legendaries, etc.)
3. **No type hints on key functions** - `parse_deckstring` and `write_deckstring` lack return type annotations
4. **Silent data corruption** - Empty EOF check message in varint reader uses wrong comparison

### Important Gaps
5. **No tests** - Production code needs comprehensive test coverage
6. **Missing docstrings** - Public API lacks documentation for usage patterns
7. **No card ID validation** - Accepts negative or invalid DBF IDs without complaint
8. **Hard-coded hero count check** - `write_deckstring` rejects multi-hero decks (Tavern Brawl, etc.)
9. **No deckstring validation utility** - Can't check if a string is valid without parsing it

### Nice-to-Have Gaps
10. **No convenience methods** - Missing helpers like `add_card()`, `remove_card()`, `card_count()`
11. **No human-readable string representation** - `Deck.__repr__()` would aid debugging
12. **No deck comparison** - Can't check equality or difference between decks
13. **Inefficient sorting** - Sorts cards multiple times instead of once
14. **No card name support** - Only works with numeric DBF IDs

## Plan

### 1. Error Recovery and Validation
**Current:** `raise EOFError("Unexpected EOF while reading varint")` triggers on truncated data; invalid format values raise generic `ValueError`.

**Required changes:**
- Create custom exception hierarchy: `DeckstringError`, `InvalidVersionError`, `InvalidFormatError`, `TruncatedDeckstringError`
- Add try-except in `from_deckstring()` to catch `base64.binascii.Error` and raise `DeckstringError("Invalid base64 encoding")`
- Validate expected remaining bytes before reading (check `data.tell()` vs `len(decoded)`)
- Add bounds checking: verify format is in `FormatType` enum range before casting

### 2. Card Count Constraints
**Current:** Accepts decks with 100 copies of a single card or 0 total cards.

**Required changes:**
- Add `validate_deck_rules()` method to `Deck` class with parameters: `min_cards=30`, `max_cards=30`, `max_copies=2`, `max_legendary_copies=1`
- Require card rarity metadata (legendary status) - either passed as parameter or looked up from external card database
- Check total card count: `sum(count for _, count in self.cards) in range(min_cards, max_cards + 1)`
- Validate per-card limits: iterate cards, check legendary IDs against `max_legendary_copies`, others against `max_copies`
- Add optional `strict=True` parameter to `from_deckstring()` that calls validation

### 3. Type Hints on Key Functions
**Current:** Functions use comment-style type hints that aren't enforced.

**Required changes:**
```python
def parse_deckstring(deckstring: str) -> Tuple[CardIncludeList, CardList, FormatType, SideboardList]:
    ...

def write_deckstring(
    cards: CardIncludeList,
    heroes: CardList,
    format: FormatType,
    sideboards: Optional[SideboardList] = None,
) -> str:
    ...
```
- Move return type from comment to proper annotation on line 117
- Already correct on line 134

### 4. Silent Data Corruption Fix
**Current:** Line 29 checks `if c == ""` but `stream.read(1)` on BytesIO returns `b""` (bytes), not empty string.

**Required changes:**
- Change line 29 to: `if c == b"" or len(c) == 0:`
- Add test case: truncated deckstring should raise exception, not infinite loop or wrong value

### 5. Comprehensive Test Suite
**Current:** No tests exist.

**Required changes:**
- Create `test_deckstring.py` with pytest fixtures
- Test cases needed:
  - Valid deckstring round-trip (encode→decode→encode produces identical result)
  - Empty deck handling
  - Single hero, multiple heroes
  - Cards with 1x, 2x, arbitrary counts
  - Sideboards with various configurations
  - Invalid base64 input
  - Truncated data at each varint position
  - Unsupported version numbers
  - Unknown format types
  - Boundary values (max varint, 0 cards, 30 cards)

### 6. Missing Docstrings
**Current:** Only module-level docstring exists.

**Required changes:**
- Add class docstring to `Deck`:
  ```python
  """Represents a Hearthstone deck with cards, heroes, format, and optional sideboards.
  
  Example:
      >>> deck = Deck.from_deckstring("AAECAa0GBgjFA...")
      >>> deck.cards
      [(1004, 2), (1363, 1), ...]
  """
  ```
- Document `parse_deckstring()`: parameters, return value structure, exceptions raised
- Document `write_deckstring()`: explain the encoding format compression
- Document varint functions with bit-packing explanation

### 7. Card ID Validation
**Current:** Negative DBF IDs and nonsense values (0, 2^31) are accepted.

**Required changes:**
- Add validation in `write_deckstring()` before encoding:
  ```python
  for cardid, count in cards:
      if cardid < 1:
          raise ValueError(f"Invalid card ID {cardid}: must be positive")
      if count < 1:
          raise ValueError(f"Invalid count {count} for card {cardid}: must be positive")
  ```
- Optionally accept a set of valid DBF IDs and check membership

### 8. Hero Count Flexibility
**Current:** Line 144 hardcoded `if len(heroes) != 1: raise ValueError`.

**Required changes:**
- Change to: `if len(heroes) < 1: raise ValueError("At least one hero required")`
- Add parameter `max_heroes: Optional[int] = None` to `write_deckstring()`
- Check `if max_heroes and len(heroes) > max_heroes:` for optional enforcement
- Update `Deck` to accept this parameter via `.as_deckstring` property (convert to method)

### 9. Deckstring Validation Utility
**Current:** Must catch exceptions to check validity.

**Required changes:**
- Add function:
  ```python
  def is_valid_deckstring(deckstring: str) -> bool:
      try:
          parse_deckstring(deckstring)
          return True
      except (DeckstringError, ValueError, EOFError):
          return False
  ```
- Add function with details:
  ```python
  def validate_deckstring(deckstring: str) -> Tuple[bool, Optional[str]]:
      """Returns (valid, error_message)"""
  ```

### 10. Convenience Methods
**Current:** Must manipulate `cards` list directly.

**Required changes:**
- Add to `Deck` class:
  ```python
  def add_card(self, dbf_id: int, count: int = 1) -> None:
      for i, (cid, cnt) in enumerate(self.cards):
          if cid == dbf_id:
              self.cards[i] = (cid, cnt + count)
              return
      self.cards.append((dbf_id, count))
  
  def remove_card(self, dbf_id: int, count: Optional[int] = None) -> None:
      # Remove count copies, or all if count is None
  
  def get_card_count(self, dbf_id: int) -> int:
      return next((cnt for cid, cnt in self.cards if cid == dbf_id), 0)
  
  def total_cards(self) -> int:
      return sum(count for _, count in self.cards)
  ```

### 11. Human-Readable String Representation
**Current:** `print(deck)` shows unhelpful memory address.

**Required changes:**
- Add to `Deck` class:
  ```python
  def __repr__(self) -> str:
      return f"Deck(cards={len(self.cards)}, heroes={self.heroes}, format={self.format.name})"
  
  def __str__(self) -> str:
      return f"Deck: {self.total_cards()} cards, Format: {self.format.name}, Hero(es): {self.heroes}"
  ```

### 12. Deck Comparison
**Current:** Cannot check if two decks are identical.

**Required changes:**
- Add to `Deck` class:
  ```python
  def __eq__(self, other: object) -> bool:
      if not isinstance(other, Deck):
          return NotImplemented
      return (
          sorted(self.cards) == sorted(other.cards) and
          sorted(self.heroes) == sorted(other.heroes) and
          self.format == other.format and
          sorted(self.sideboards) == sorted(other.sideboards)
      )
  
  def __hash__(self) -> int:
      return hash((tuple(sorted(self.cards)), tuple(sorted(self.heroes)), self.format, tuple(sorted(self.sideboards))))
  
  def diff(self, other: "Deck") -> dict:
      """Returns added/removed/changed cards"""
  ```

### 13. Inefficient Sorting
**Current:** `trisort_cards()` receives pre-sorted cards, then sorts again (lines 149-151, 161-162, 168).

**Required changes:**
- Remove sort operations from `write_deckstring()` - pass sorting responsibility to caller or do once at start:
  ```python
  all_sorted = sorted(cards, key=lambda x: x[0])
  cards_x1, cards_x2, cards_xn = trisort_cards(all_sorted)
  # Remove individual sorted() calls
  ```
- Or modify `trisort_cards()` to return pre-sorted lists so downstream sorts are no-ops

### 14. Card Name Support
**Current:** Only numeric IDs are usable; debugging requires external lookup.

**Required changes:**
- Add optional card database integration:
  ```python
  class Deck:
      def __init__(self, card_db: Optional[Dict[int, str]] = None):
          self.card_db = card_db
      
      def get_card_names(self) -> List[Tuple[str, int]]:
          if not self.card_db:
              raise ValueError("No card database provided")
          return [(self.card_db[cid], count) for cid, count in self.cards]
  ```
- Keep card DB optional to avoid tight coupling