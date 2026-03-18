# Diagnostic Report: Blizzard Deckstring Parser

## Observations

This system implements the Blizzard deckstring format, which encodes Hearthstone deck configurations into compact base64 strings. Currently working capabilities:

1. **Bidirectional conversion**: Parses deckstrings to structured data and serializes structured data back to deckstrings
2. **Varint encoding/decoding**: Implements variable-length integer encoding for space efficiency
3. **Card organization**: Groups cards by quantity (1x, 2x, n×) for optimized encoding
4. **Hero handling**: Reads and writes hero card IDs
5. **Format type support**: Encodes/decodes game format (Standard, Wild, Classic, etc.)
6. **Sideboard support**: Handles sideboard cards with owner references (likely for dual-class or transforming cards)
7. **Deck object wrapper**: Provides a `Deck` class with convenience methods for deckstring conversion and card list retrieval
8. **Sorting**: Maintains deterministic ordering of cards and sideboards by DBF ID

## Triage

### Critical (Production Blockers)

1. **No error handling for malformed input** - `parse_deckstring` will crash on truncated or corrupted data with unclear errors
2. **Missing validation** - No checks for valid card counts, duplicate cards, deck size limits, or format-specific rules
3. **No tests** - Zero test coverage despite handling binary parsing and encoding
4. **Hero count hardcoded to 1** - `write_deckstring` explicitly rejects multi-hero decks, but the parser supports them

### High (Robustness & Usability)

5. **No documentation** - Public API lacks docstrings explaining parameters, formats, or usage examples
6. **Unclear type annotations** - Type aliases are defined but their semantics aren't documented (what is a "DBF ID"?)
7. **Silent data truncation** - If extra data exists after parsing, it's ignored without warning
8. **No validation of FormatType** - Unknown format values are caught in parsing but not in writing
9. **Inconsistent error types** - Mix of `ValueError`, `EOFError`, and potential `TypeError` makes error handling difficult

### Medium (Polish & Maintainability)

10. **No logging** - Debugging production issues would be difficult without any instrumentation
11. **Duplicate sorting logic** - Card sorting appears in multiple places with slight variations
12. **Magic numbers** - `DECKSTRING_VERSION = 1` is the only named constant; others (0x7f, 0x80) are inline
13. **No size limits** - Unbounded varint reading could cause memory issues with malicious input
14. **Mutable default argument** - `sideboards: Optional[SideboardList] = None` pattern is correct, but `cards_x1: List = []` pattern in `trisort_cards` could bite if extended

### Low (Nice to Have)

15. **No deck building helpers** - No methods to add/remove cards, validate deck completeness, or check legality
16. **String representation** - `Deck` object has no `__str__` or `__repr__` for debugging
17. **No comparison operators** - Can't easily check if two decks are equivalent
18. **Performance not optimized** - Multiple list traversals and sorts could be consolidated

## Plan

### Critical Fixes

**1. Add comprehensive error handling to `parse_deckstring`**
- Wrap `_read_varint` calls in try-except to catch `EOFError` and re-raise as `ValueError` with context like "Incomplete deckstring: unexpected end while reading card count"
- Add try-except around `base64.b64decode` to catch `binascii.Error` and raise `ValueError("Invalid deckstring: not valid base64")`
- Validate stream position: after parsing, check if `data.tell() == len(decoded)` and warn if excess bytes exist

**2. Add validation logic**
- Create `validate_deck_cards(cards: CardIncludeList, format: FormatType) -> None` function
  - Check each card count is positive: `if count <= 0: raise ValueError(f"Invalid card count {count} for card {cardid}")`
  - Check no duplicate card IDs: use a set to track seen IDs
  - Check deck size: sum all counts, ensure between 30-30 for Standard (configurable by format)
- Call from `Deck.from_deckstring` after parsing
- Add parameter `validate: bool = True` to allow skipping validation when needed

**3. Add comprehensive test suite**
- Create `tests/test_deckstring.py` with pytest
- Test cases needed:
  - Round-trip encoding (parse → write → parse → compare)
  - Known valid deckstrings from Hearthstone (use real examples)
  - Malformed input: truncated strings, invalid base64, wrong version byte
  - Edge cases: empty deck, maximum card counts, all singletons vs all duplicates
  - Sideboard parsing and encoding
  - All FormatType values
- Use property-based testing (hypothesis) to generate random valid decks and verify round-trip

**4. Fix hero count restriction**
- Remove the hardcoded check in `write_deckstring`: delete the `if len(heroes) != 1: raise ValueError` block
- Add configurable validation instead: `validate_hero_count(heroes: CardList, format: FormatType)` that checks format-specific rules
- Document supported hero counts per format in docstrings

### High Priority Improvements

**5. Add comprehensive docstrings**
- Module-level docstring explaining Blizzard deckstring format, linking to official specification if available
- Add to `Deck` class:
  ```python
  """Represents a Hearthstone deck configuration.
  
  Attributes:
      cards: List of (dbf_id, count) tuples representing mainboard cards
      heroes: List of hero card DBF IDs (typically 1, sometimes 2 for dual-class)
      format: Game format (Standard=FT_STANDARD, Wild=FT_WILD, etc.)
      sideboards: List of (dbf_id, count, owner_id) tuples for sideboard cards
  """
  ```
- Document DBF ID concept: "DBF ID is Hearthstone's internal database ID for each card"

**6. Add type annotation documentation**
- Convert type aliases to `TypedDict` for better IDE support:
  ```python
  from typing import TypedDict
  class CardEntry(TypedDict):
      dbf_id: int
      count: int
  CardIncludeList = List[CardEntry]
  ```
- Or at minimum, add comments: `CardList = List[int]  # List of DBF IDs`

**7. Validate all remaining data consumed**
- At end of `parse_deckstring`, before returning:
  ```python
  remaining = data.read()
  if remaining:
      import warnings
      warnings.warn(f"Deckstring contained {len(remaining)} unexpected trailing bytes")
  ```

**8. Add FormatType validation to write path**
- In `write_deckstring`, before `_write_varint(data, int(format))`:
  ```python
  if not isinstance(format, FormatType):
      raise ValueError(f"Invalid format type: {format}")
  ```

**9. Create custom exception hierarchy**
- Define in new `exceptions.py`:
  ```python
  class DeckstringError(Exception): pass
  class InvalidDeckstringError(DeckstringError): pass
  class DeckValidationError(DeckstringError): pass
  class UnsupportedVersionError(DeckstringError): pass
  ```
- Update all raises to use appropriate exception type
- Allows callers to `except DeckstringError` to catch all library errors

### Medium Priority Polish

**10. Add structured logging**
- Add at module level: `import logging; logger = logging.getLogger(__name__)`
- Log at DEBUG level: "Parsing deckstring version {version}, format {format}, {num_heroes} heroes"
- Log at INFO level when validation warnings occur
- Add optional `verbose: bool` parameter to enable detailed logging

**11. Consolidate sorting logic**
- Extract common pattern into helper:
  ```python
  def _sort_cards_by_id(cards: Sequence[tuple], with_owner: bool = False) -> List[tuple]:
      key = (lambda x: (x[2], x[0])) if with_owner else (lambda x: x[0])
      return sorted(cards, key=key)
  ```
- Use throughout `write_deckstring`

**12. Extract magic numbers to named constants**
- Add at module level:
  ```python
  VARINT_CONTINUATION_BIT = 0x80
  VARINT_VALUE_MASK = 0x7f
  DECKSTRING_NULL_BYTE = b"\0"
  SIDEBOARD_PRESENT_BYTE = b"\1"
  SIDEBOARD_ABSENT_BYTE = b"\0"
  ```

**13. Add size limits to varint reading**
- Add parameter to `_read_varint(stream: IO, max_bytes: int = 10)` (10 bytes = 70-bit max)
- Track bytes read, raise `ValueError("Varint exceeds maximum size")` if exceeded
- Prevents infinite loops on malformed input

### Low Priority Enhancements

**15. Add deck building utilities**
- Add to `Deck` class:
  ```python
  def add_card(self, dbf_id: int, count: int = 1) -> None
  def remove_card(self, dbf_id: int, count: int = 1) -> None
  def get_card_count(self, dbf_id: int) -> int
  def total_cards(self) -> int
  def is_valid(self) -> Tuple[bool, List[str]]  # Returns (valid, errors)
  ```

**16. Implement string representations**
- Add to `Deck`:
  ```python
  def __repr__(self) -> str:
      return f"Deck(cards={len(self.cards)}, heroes={self.heroes}, format={self.format.name})"
  
  def __str__(self) -> str:
      return f"Deck: {self.total_cards()} cards, {len(self.heroes)} hero(es), {self.format.name}"
  ```

**17. Add comparison operators**
- Implement `__eq__` in `Deck`:
  ```python
  def __eq__(self, other) -> bool:
      if not isinstance(other, Deck):
          return NotImplemented
      return (
          sorted(self.cards) == sorted(other.cards) and
          sorted(self.heroes) == sorted(other.heroes) and
          self.format == other.format and
          sorted(self.sideboards) == sorted(other.sideboards)
      )
  ```

**18. Optimize performance**
- Cache sorted card lists in `Deck` to avoid re-sorting on each access
- Use `bisect` module for maintaining sorted order during insertion
- Profile `trisort_cards` - could use single pass with three accumulators instead of multiple iterations