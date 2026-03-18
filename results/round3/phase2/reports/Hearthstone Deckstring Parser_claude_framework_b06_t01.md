# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Hearthstone deckstring encoding/decoding format. Current working capabilities:

1. **Decoding deckstrings** (`parse_deckstring`) - Converts base64-encoded deckstrings into structured data containing:
   - Card list with (dbf_id, count) tuples
   - Hero card IDs
   - Format type (Wild, Standard, etc.)
   - Sideboard cards (for formats that support them)

2. **Encoding deckstrings** (`write_deckstring`) - Serializes deck data back to base64 deckstring format

3. **Varint encoding/decoding** - Implements variable-length integer encoding for compact binary representation

4. **Card sorting optimization** (`trisort_cards`) - Groups cards by count (1×, 2×, n×) for efficient encoding

5. **OOP interface** (`Deck` class) - Provides convenient object-oriented access with:
   - `from_deckstring()` factory method
   - `as_deckstring` property
   - Sorted card/sideboard accessors

6. **Format type enumeration** - References `FormatType` enum for deck format validation

## Triage

### Critical Gaps

1. **No error handling for malformed input** - Empty strings, truncated data, or corrupted base64 will crash with obscure errors rather than user-friendly messages

2. **Missing type hints for complex types** - The `tuple` return type `(CardIncludeList, CardList, FormatType, SideboardList)` is not properly typed as `Tuple[...]`

3. **No validation of deck construction rules** - Doesn't verify card counts (max 2 per card, max 30 cards total, legendary limits, etc.)

4. **No tests** - Zero test coverage for a binary parsing library is a production blocker

### Important Gaps

5. **No sideboard owner validation** - Sideboards reference owner cards but don't verify the owner exists in the main deck

6. **Hardcoded hero count** - `write_deckstring` raises `ValueError` for multi-hero decks, but Tavern Brawls and other modes support this

7. **No documentation** - Docstrings missing for all public methods

8. **Incomplete `Deck` interface** - Missing common operations:
   - Add/remove cards
   - Validate deck legality
   - Export to other formats (JSON, text list)
   - Card search/filter methods

### Minor Gaps

9. **Import ordering** - `enums` module import may not exist; should be defined or documented

10. **Inconsistent sorting** - `cards.sort()` mutates in `parse_deckstring`, but uses `sorted()` in `write_deckstring`

11. **No logging** - Binary parsing failures would benefit from debug logging

12. **Magic numbers** - `b"\0"` and `b"\1"` lack named constants

## Plan

### For Critical Gaps

**1. Add comprehensive error handling**
- Wrap `base64.b64decode()` in try/except to catch `binascii.Error`
- Check for EOF during varint reads and raise `ValueError("Truncated deckstring")`
- Add validation at start: check decoded length > 0, first byte is `\0`
- Create custom exception class: `class InvalidDeckstringError(ValueError): pass`

**2. Fix type hints**
- Change `parse_deckstring` return type from `(Tuple[...])` to proper `Tuple[CardIncludeList, CardList, FormatType, SideboardList]`
- Add `-> bytes` to `_write_varint` and `-> int` to return statement
- Import `Tuple` from `typing` (already present)

**3. Add deck validation**
- Create `Deck.validate()` method that checks:
  - Total card count == 30 (or format-specific rules)
  - No card appears > 2 times (except for specific cards like Legendaries = 1)
  - All cards are legal in the specified format
- This requires card database integration (see gap #8 dependencies)

**4. Add test suite**
- Create `tests/test_deckstring.py` with pytest
- Test cases needed:
  - Valid deckstring round-trip (encode → decode → encode produces identical output)
  - Edge cases: 0 cards, 30 identical cards, all sideboards
  - Error cases: empty string, invalid base64, truncated varints, unsupported version
  - Known deckstrings from community (regression tests)

### For Important Gaps

**5. Validate sideboard owners**
- In `parse_deckstring`, after reading sideboards, verify each `sideboard_owner` appears in `cards` list:
  ```python
  card_ids = {card[0] for card in cards}
  for card_id, count, owner in sideboards:
      if owner not in card_ids:
          raise ValueError(f"Sideboard owner {owner} not in deck")
  ```

**6. Remove hero count restriction**
- Replace `if len(heroes) != 1: raise ValueError` with flexible loop
- Update header comment documenting multi-hero support

**7. Add docstrings**
- Every public method needs:
  - One-line summary
  - Args description with types
  - Returns description with type
  - Raises section for exceptions
  - Example usage in `Deck` class docstring

**8. Expand `Deck` interface**
- Add methods:
  - `add_card(dbf_id: int, count: int = 1) -> None`
  - `remove_card(dbf_id: int, count: int = 1) -> None`
  - `to_dict() -> dict` for JSON serialization
  - `total_cards() -> int` property
  - `is_valid() -> bool` that calls validate without raising
- Consider integrating hearthstone-data or creating `CardDatabase` class for lookups

### For Minor Gaps

**9. Document or bundle enums**
- Either: inline `FormatType` definition into this file, or
- Add comment: `# Requires: pip install hearthstone` and document dependency

**10. Standardize sorting approach**
- Remove `.sort()` mutations in `parse_deckstring`
- Use `sorted()` everywhere for functional style, or
- Document that parse modifies its internal lists

**11. Add logging**
- `import logging; logger = logging.getLogger(__name__)`
- Add `logger.debug(f"Decoded {len(decoded)} bytes")` after base64 decode
- Add `logger.debug(f"Read {num_cards_x1} single cards")` in parse loops

**12. Extract constants**
- At module level: `DECKSTRING_HEADER = b"\0"`, `SIDEBOARDS_PRESENT = b"\1"`, `SIDEBOARDS_ABSENT = b"\0"`
- Replace magic bytes with named constants throughout