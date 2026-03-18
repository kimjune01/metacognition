# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Deckstring format for encoding/decoding Hearthstone deck configurations. Current working capabilities:

1. **Bidirectional conversion**: Encodes deck data to base64 deckstrings and decodes deckstrings back to structured data
2. **Core data structures**: Handles cards (with counts), heroes, game format types, and sideboards
3. **Varint encoding/decoding**: Implements variable-length integer serialization for compact binary representation
4. **Count-based optimization**: Groups cards by count (1×, 2×, n×) to minimize encoding size
5. **Sideboard support**: Parses and writes sideboard cards with ownership tracking (likely for deck variants)
6. **OOP interface**: Provides a `Deck` class for convenient manipulation
7. **Format validation**: Checks deckstring header/version and validates format types

## Triage

### Critical Gaps

1. **Zero error handling context** — When parsing fails (corrupt deckstring, wrong version, buffer underrun), exceptions provide no actionable information about *where* or *why* the failure occurred.

2. **No input validation** — Accepts invalid card counts, negative IDs, duplicate cards, empty decks, or malformed sideboards without complaint.

3. **Untested against real data** — No test suite, examples, or fixtures demonstrating compatibility with actual Hearthstone deckstrings.

### Important Gaps

4. **Incomplete `Deck` class** — Cannot add/remove cards, modify heroes, or validate deck legality. Just a data container.

5. **Missing documentation** — No docstrings explaining format version semantics, what sideboards represent, or why trisort exists.

6. **Hard-coded constraints** — Enforces exactly 1 hero (line 157), breaking multi-hero modes or future format changes.

7. **No logging** — Silent failures during varint reads or format mismatches make debugging production issues impossible.

### Nice-to-Have Gaps

8. **Performance concerns** — Multiple sorting passes (lines 115, 151, 173-174) and list comprehensions could be optimized for large sideboards.

9. **Type safety erosion** — Uses raw tuples instead of typed dataclasses, making `(cardid, count)` vs `(cardid, count, owner)` error-prone.

10. **No CLI or examples** — Requires users to write their own scripts to test or use the library.

## Plan

### 1. Error Handling Context
**Changes needed:**
- Wrap varint reads in try/except, catching `EOFError` and `struct.error` to raise custom `DeckstringParseError(message, byte_offset, remaining_bytes)`
- Add position tracking to BytesIO stream: `current_section = "heroes"` before each block, include in exceptions
- In `parse_deckstring`, catch `base64.binascii.Error` and reraise with "Invalid base64 encoding" message
- Add format string to version mismatch: `f"Expected version {DECKSTRING_VERSION}, got {version}"`

### 2. Input Validation
**Changes needed:**
- In `write_deckstring`: Validate `cards` and `sideboards` are non-empty, card IDs > 0, counts >= 1, no duplicate (cardid, owner) pairs
- Add `max_cards` and `max_copies` parameters (defaults: 30 cards, 2 copies for constructed) with validation
- Validate `format` is a known `FormatType` enum before writing
- In `Deck.__init__`: Add optional `strict=True` parameter that validates deck legality on construction

### 3. Real-World Testing
**Changes needed:**
- Create `tests/test_deckstrings.py` with 10+ real deckstrings from https://hearthsim.info or Blizzard API
- Add parameterized tests: `@pytest.mark.parametrize("deckstring", REAL_DECKSTRINGS)`
- Test round-trip: `assert Deck.from_deckstring(s).as_deckstring == s`
- Add regression tests for known format edge cases (Wild/Standard, Tavern Brawl, Duels sideboards)

### 4. Complete Deck Class
**Changes needed:**
- Add `Deck.add_card(dbf_id: int, count: int = 1)` that updates or appends to `self.cards`
- Add `Deck.remove_card(dbf_id: int, count: int = 1)` that decrements or removes from list
- Add `Deck.set_hero(dbf_id: int)` that replaces `self.heroes`
- Add `Deck.validate()` method checking card count limits, hero class restrictions, format legality
- Add `__repr__` and `__eq__` for debugging and testing

### 5. Documentation
**Changes needed:**
- Add module docstring explaining deckstring format history, link to Blizzard documentation
- Add docstrings to `parse_deckstring` and `write_deckstring` with parameter descriptions and examples
- Document `trisort_cards` purpose: "Groups cards by count for encoding efficiency"
- Add inline comment at sideboard section: "Sideboards store variant cards for modes like Duels"
- Create `README.md` with quickstart example

### 6. Remove Hard-Coded Hero Constraint
**Changes needed:**
- Replace line 157 check `if len(heroes) != 1` with `if not (1 <= len(heroes) <= 2)` to support dual-class
- Add warning log (not exception) if `len(heroes) > 2` for forward compatibility
- Update tests to cover 0-hero, 1-hero, 2-hero cases
- Add `Deck.is_multi_class` property for convenience

### 7. Logging
**Changes needed:**
- Add `import logging; logger = logging.getLogger(__name__)` at module top
- Log at `DEBUG`: "Parsing deckstring version {version}, format {format}, {num_heroes} heroes"
- Log at `WARNING`: Non-fatal issues like unexpected sideboard structure
- Log at `ERROR`: Before raising exceptions in parsing
- Add `logger.debug(f"Encoded {len(cards)} cards, {len(sideboards)} sideboard cards")` in writer

### 8. Performance Optimization
**Changes needed:**
- Replace multiple `sorted()` calls with single sort + partition: `cards.sort(); x1 = [c for c in cards if c[1]==1]`
- Use `bisect` module for sorted insertion in `Deck.add_card` instead of append + sort
- Add `__slots__` to `Deck` class to reduce memory overhead
- Profile with `cProfile` on 1000-deck benchmark before/after changes

### 9. Type Safety
**Changes needed:**
- Define `@dataclass Card: dbf_id: int; count: int` and `@dataclass SideboardCard(Card): owner: int`
- Replace `CardIncludeList` and `SideboardList` type aliases with `List[Card]` and `List[SideboardCard]`
- Add `Deck.cards: List[Card]` annotation and convert tuples to dataclass instances in `from_deckstring`
- Run `mypy --strict` and fix revealed type errors

### 10. CLI and Examples
**Changes needed:**
- Create `__main__.py` with argparse: `python -m hearthstone.deckstrings decode <string>` and `encode <json>`
- Add `examples/parse_example.py` showing: load deckstring → print card list → modify → encode
- Add `examples/build_deck.py` showing: create Deck → add cards → export deckstring
- Include sample deckstrings in `examples/data/` for Standard/Wild/Duels formats