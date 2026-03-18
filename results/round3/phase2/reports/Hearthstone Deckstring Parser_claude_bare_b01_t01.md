# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Deckstring format encoder/decoder for Hearthstone deck codes. Current working capabilities:

1. **Binary Protocol Implementation** - Complete varint reading/writing for compact integer encoding
2. **Deckstring Parsing** - Decodes base64-encoded deck strings into structured data:
   - Version validation (currently supports version 1)
   - Format type extraction (Standard, Wild, etc.)
   - Hero card parsing (multiple heroes supported in parser, though validator restricts to 1)
   - Card list parsing with count grouping (1x, 2x, Nx optimization)
   - Sideboard parsing (optional section for card pools tied to specific cards)
3. **Deckstring Generation** - Encodes deck data back to deckstring format with proper sorting and grouping
4. **Deck Object Model** - `Deck` class provides convenience methods for:
   - Creating deck from deckstring
   - Exporting deck to deckstring
   - Retrieving sorted card/sideboard lists
5. **Card Organization** - `trisort_cards` groups cards by count for efficient encoding

## Triage

### Critical Gaps
1. **No Error Handling** - Parser fails silently or raises generic exceptions on malformed input
2. **No Input Validation** - Accepts invalid deck compositions (wrong card counts, invalid DBF IDs)
3. **Missing Documentation** - No docstrings, no usage examples, no format specification

### Important Gaps
4. **Incomplete Type Hints** - Return types use tuples instead of named types; `IO` type is too generic
5. **No Testing** - Zero test coverage for edge cases, malformed inputs, or round-trip encoding
6. **Hard-coded Constraints** - Single-hero validation in encoder but multi-hero support in parser creates inconsistency

### Nice-to-Have Gaps
7. **No Deck Validation** - Doesn't verify deck legality (30 cards, 2-copy limit, format restrictions)
8. **Limited Format Support** - Enum dependency not shown; unclear what formats are supported
9. **No Human-readable Export** - Can't display deck as card names, only DBF IDs
10. **Performance** - Repeated sorting; no caching of deckstring after generation

## Plan

### 1. Error Handling
**Changes needed:**
- Wrap `parse_deckstring` body in try-except to catch `EOFError`, `ValueError`, `base64.binascii.Error`
- Create custom exceptions: `InvalidDeckstringError`, `UnsupportedVersionError`, `CorruptedDataError`
- Add validation after parsing: check that data stream is fully consumed (`data.read(1) == b""`), catch truncated deckstrings
- In `_read_varint`, add maximum iteration limit (prevent infinite loop on corrupted data)

**Example:**
```python
class InvalidDeckstringError(ValueError):
    pass

def parse_deckstring(deckstring: str):
    try:
        decoded = base64.b64decode(deckstring, validate=True)
    except Exception as e:
        raise InvalidDeckstringError(f"Invalid base64: {e}")
    # ... rest of parsing with specific error messages
```

### 2. Input Validation
**Changes needed:**
- In `write_deckstring`, validate before encoding:
  - Check `cards` contains valid tuples `(int > 0, int > 0)`
  - Check `heroes` list contains valid DBF IDs
  - Check `sideboards` tuples are `(int > 0, int > 0, int > 0)`
- Add validation method to `Deck` class: `validate(strict=True)` that checks:
  - No duplicate card DBF IDs in main list
  - Sideboard owners reference cards in main deck
  - Counts are positive integers
- Optionally accept `max_copies` parameter to enforce game rules

**Example:**
```python
def validate_card_list(cards: CardIncludeList):
    seen_ids = set()
    for card_elem in cards:
        if len(card_elem) != 2:
            raise ValueError(f"Card must be (dbf_id, count), got {card_elem}")
        dbf_id, count = card_elem
        if dbf_id <= 0 or count <= 0:
            raise ValueError(f"Invalid card: dbf_id={dbf_id}, count={count}")
        if dbf_id in seen_ids:
            raise ValueError(f"Duplicate card {dbf_id}")
        seen_ids.add(dbf_id)
```

### 3. Documentation
**Changes needed:**
- Add module docstring explaining Blizzard deckstring format with links to specification
- Add docstrings to all functions with parameter descriptions and return types:
  - `parse_deckstring`: "Decodes a base64 deckstring into components. Returns (cards, heroes, format, sideboards)."
  - `write_deckstring`: "Encodes deck components into base64 deckstring format."
- Add class docstring to `Deck` with usage example:
  ```python
  """
  Example:
      deck = Deck.from_deckstring("AAECAa0GBu0F...")
      print(deck.format)  # FormatType.FT_STANDARD
      print(deck.cards)   # [(1234, 2), (5678, 1), ...]
  """
  ```
- Document deckstring format structure in comments (header, hero section, cards section, sideboard section)

### 4. Type Hints Improvement
**Changes needed:**
- Replace raw tuples with `NamedTuple` or `dataclass`:
  ```python
  from typing import NamedTuple
  
  class CardEntry(NamedTuple):
      dbf_id: int
      count: int
  
  class SideboardEntry(NamedTuple):
      dbf_id: int
      count: int
      owner_id: int
  ```
- Change `IO` to `IO[bytes]` for binary streams
- Replace return tuple in `parse_deckstring` with `NamedTuple` result class:
  ```python
  class ParsedDeck(NamedTuple):
      cards: List[CardEntry]
      heroes: CardList
      format: FormatType
      sideboards: List[SideboardEntry]
  ```

### 5. Testing
**Changes needed:**
- Create `test_deckstring.py` with pytest fixtures
- Add unit tests for:
  - Varint encoding/decoding edge cases (0, 127, 128, large numbers)
  - Round-trip: encode then decode produces identical deck
  - Known deckstring examples from Hearthstone
  - Malformed input (truncated, wrong version, invalid base64)
  - Empty deck, single card, max cards
  - Sideboard encoding/decoding
- Add property-based testing with `hypothesis` for random valid decks

### 6. Constraint Consistency
**Changes needed:**
- Remove hard-coded hero count check from `write_deckstring`, or make it configurable:
  ```python
  def write_deckstring(
      cards: CardIncludeList,
      heroes: CardList,
      format: FormatType,
      sideboards: Optional[SideboardList] = None,
      validate_hero_count: bool = True,
  ) -> str:
      if validate_hero_count and len(heroes) != 1:
          raise ValueError(...)
  ```
- Document when multi-hero is valid (e.g., Tavern Brawl modes)

### 7. Deck Validation
**Changes needed:**
- Add `Deck.is_legal(rules: DeckRules = None)` method that checks:
  - Total card count (typically 30 for constructed)
  - Max copies per card (typically 2, or 1 for Legendary)
  - Format-specific restrictions (Standard vs Wild card pool)
- Create `DeckRules` dataclass for configurable validation:
  ```python
  @dataclass
  class DeckRules:
      total_cards: int = 30
      max_copies: int = 2
      legendary_limit: int = 1
      allowed_classes: Optional[Set[int]] = None
  ```
- Requires card database integration to check rarity/class

### 8. Format Support Clarity
**Changes needed:**
- Include `enums.py` or document `FormatType` values inline:
  ```python
  class FormatType(IntEnum):
      FT_UNKNOWN = 0
      FT_WILD = 1
      FT_STANDARD = 2
      FT_CLASSIC = 3
      # ...
  ```
- Add `Deck.format_name` property for human-readable format string

### 9. Human-readable Export
**Changes needed:**
- Add optional card database parameter to `Deck.__str__`:
  ```python
  def __str__(self, card_db: Optional[CardDatabase] = None) -> str:
      if card_db:
          return "\n".join(f"{count}x {card_db.get_name(dbf_id)}" 
                          for dbf_id, count in self.cards)
      return f"Deck({len(self.cards)} cards)"
  ```
- Create separate `CardDatabase` abstraction (could load from JSON/SQLite)

### 10. Performance Optimization
**Changes needed:**
- Cache deckstring in `Deck` class:
  ```python
  def __init__(self):
      self._deckstring_cache: Optional[str] = None
      
  def _invalidate_cache(self):
      self._deckstring_cache = None
      
  @property
  def as_deckstring(self) -> str:
      if self._deckstring_cache is None:
          self._deckstring_cache = write_deckstring(...)
      return self._deckstring_cache
  ```
- Call `_invalidate_cache()` when cards/heroes/sideboards modified
- Pre-sort card lists in `__init__` if performance critical
- Consider `__slots__` on `Deck` class if creating many instances