# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system currently provides a working implementation of Blizzard's deckstring format for Hearthstone:

**Working capabilities:**
1. **Deserialization** - Parses base64-encoded deckstrings into structured deck data (cards, heroes, format, sideboards)
2. **Serialization** - Encodes deck data back into valid deckstring format
3. **Varint I/O** - Correctly implements variable-length integer encoding/decoding for compact binary representation
4. **Card organization** - Sorts cards by count (1x, 2x, n×) for efficient encoding
5. **Sideboard support** - Handles optional sideboard cards with ownership tracking (newer Hearthstone feature)
6. **Format type awareness** - Tracks deck format (Standard, Wild, Classic, etc.)
7. **Hero handling** - Reads/writes hero cards with validation (requires exactly 1 hero)
8. **Object-oriented interface** - `Deck` class provides clean API with `from_deckstring()` and `as_deckstring` property
9. **Sorting utilities** - Methods to retrieve sorted card/sideboard lists by DBF ID

## Triage

**Critical gaps:**
1. **No error messages on invalid input** - EOF and ValueError exceptions provide minimal context for debugging
2. **No validation of card counts** - Doesn't enforce Hearthstone rules (max 2 copies of non-legendary, 1 of legendary, 30-card deck size)
3. **No tests** - Per TDD preference in CLAUDE.md, this should have been written test-first

**Important gaps:**
4. **No card database integration** - Uses raw DBF IDs instead of card names/metadata
5. **No deck validation rules** - Missing class restrictions, banned cards, format legality checks
6. **Incomplete type hints** - Return types use old-style tuples instead of `TypedDict` or dataclasses
7. **No CLI or usage examples** - Can't be used standalone

**Nice-to-have improvements:**
8. **No logging** - Silent failures make debugging difficult in production
9. **Magic numbers** - `0x7f`, `0x80` lack explanatory constants
10. **No deck comparison/diff utilities** - Can't easily compare two decks
11. **No human-readable export** - Can't convert to text/JSON formats
12. **Limited hero support** - Hard-coded to require exactly 1 hero (future-proofing for multi-hero modes?)

## Plan

### 1. Add comprehensive error messages
**Changes needed:**
- In `_read_varint()`: Include byte offset and partial result in EOFError
- In `parse_deckstring()`: Wrap base64 decode in try/except, report invalid characters
- Add context managers to track parsing state: `with ParsingContext("heroes section") as ctx:`
- Create custom exception hierarchy: `DeckstringError` → `InvalidHeaderError`, `InvalidCardDataError`, etc.

### 2. Implement Hearthstone rule validation
**Changes needed:**
- Add `validate()` method to `Deck` class
- Check total card count equals 30 (or format-specific limits)
- Validate card counts: non-legendary ≤ 2, legendary ≤ 1
- Require card database lookup to check rarity
- Return `ValidationResult` with list of violations, not just True/False

### 3. Add comprehensive test suite
**Changes needed:**
- Create `tests/test_deckstring.py` with pytest
- Test cases: valid deckstrings (with/without sideboards), malformed input, round-trip encoding
- Property-based tests with Hypothesis: generate random decks, verify serialize→deserialize identity
- Edge cases: empty decks, max-count cards, all formats
- Performance tests: large decks with sideboards

### 4. Integrate card database
**Changes needed:**
- Add `CardDatabase` class that loads from HearthstoneJSON or similar
- Extend `Deck` with `get_card_names()` method that resolves DBF IDs to card objects
- Cache database lookups for performance
- Handle missing cards gracefully (warn about unknown IDs from future patches)

### 5. Add deck validation rules
**Changes needed:**
- Create `DeckValidator` class with pluggable rule sets
- Implement `ClassRestrictionRule` - check cards match hero class or are neutral
- Implement `FormatLegalityRule` - verify cards are legal in specified format
- Implement `BannedCardRule` - check against format-specific ban lists
- Return detailed violation reports with card names and rule explanations

### 6. Modernize type hints
**Changes needed:**
- Replace `Tuple[CardIncludeList, CardList, FormatType, SideboardList]` with `ParseResult` dataclass
- Convert `CardList`, `CardIncludeList`, `SideboardList` to proper types:
  ```python
  @dataclass
  class Card:
      dbf_id: int
      count: int
      sideboard_owner: Optional[int] = None
  ```
- Add `TypedDict` for serialized formats or use Pydantic models

### 7. Add CLI interface
**Changes needed:**
- Create `__main__.py` with argparse/click
- Commands: `parse <deckstring>`, `create --cards "card1,card2"`, `validate <deckstring>`
- Output formats: JSON, human-readable text, deck tracker import formats
- Add `pyproject.toml` console_scripts entry point

### 8. Add structured logging
**Changes needed:**
- Use Python `logging` module with configurable levels
- Log key events: deck parsed (with card count), encoding started, validation failures
- Include deckstring prefix in logs (first 8 chars) for correlation
- Add `--debug` flag to CLI for verbose output

### 9. Add explanatory constants
**Changes needed:**
```python
VARINT_CONTINUATION_BIT = 0x80
VARINT_DATA_MASK = 0x7f
DECKSTRING_FORMAT_VERSION = 1  # rename from DECKSTRING_VERSION
REQUIRED_HERO_COUNT = 1
```

### 10. Add deck comparison utilities
**Changes needed:**
- Implement `Deck.__eq__()` and `__hash__()` for equality checks
- Add `Deck.diff(other: Deck) -> DeckDiff` that returns added/removed/changed cards
- Create `DeckDiff` dataclass with `added: List[Card]`, `removed: List[Card]`, `count_changed: List[Tuple[Card, int, int]]`

### 11. Add export formats
**Changes needed:**
- Add `Deck.to_json()` method with card names (requires card database)
- Add `Deck.to_text()` for human-readable format: "# Deck Name\n1x Card Name\n2x Another Card"
- Add `Deck.to_hsreplay_xml()` for deck tracker compatibility
- Add `from_json()` and `from_text()` class methods for round-trip support

### 12. Make hero count configurable
**Changes needed:**
- Remove hard-coded `if len(heroes) != 1` check
- Add `allowed_hero_counts: Set[int]` parameter to `write_deckstring()` with default `{1}`
- Document current Hearthstone requirement but allow flexibility for future game modes
- Add validation as separate opt-in check, not serialization requirement