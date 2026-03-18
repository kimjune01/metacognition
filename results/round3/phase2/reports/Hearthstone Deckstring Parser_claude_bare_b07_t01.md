# Diagnostic Report: Blizzard Deckstring Parser

## Observations

This system provides a complete implementation of Blizzard's deckstring format for Hearthstone deck encoding/decoding. Currently working capabilities:

1. **Bidirectional conversion** - Decodes base64-encoded deckstrings into structured data and encodes deck data back to deckstring format
2. **Varint I/O** - Implements variable-length integer encoding/decoding for compact binary representation
3. **Multi-section parsing** - Handles all deckstring sections: header (version, format), heroes, main deck cards, and sideboards
4. **Card count optimization** - Groups cards by count (1×, 2×, n×) for efficient encoding
5. **Sideboard support** - Reads and writes sideboard cards with owner associations (newer format feature)
6. **Format validation** - Enforces version checks and format type enumeration
7. **Deck object abstraction** - Provides `Deck` class with convenience methods for deckstring conversion and sorted card lists

## Triage

Ranked gaps from critical to minor:

### Critical (Blocking Production Use)
1. **No error recovery** - EOF and decode errors provide minimal context; malformed deckstrings crash rather than fail gracefully
2. **Missing validation** - No enforcement of Hearthstone deck rules (30-card main deck, 2-copy legendary limit, format legality)
3. **Silent data corruption** - `trisort_cards` doesn't validate that input tuples have correct structure before unpacking

### High (Quality & Usability)
4. **Hardcoded hero count** - `write_deckstring` raises ValueError for anything other than exactly 1 hero, but format supports multiple heroes (parsed correctly)
5. **No card database integration** - Works with raw DBF IDs only; can't validate cards exist or provide human-readable names
6. **Missing documentation** - No docstrings, usage examples, or explanation of the deckstring format structure

### Medium (Developer Experience)
7. **Type hints incomplete** - Uses type aliases but doesn't enforce them (e.g., `sideboards` parameter accepts `None` but type system doesn't reflect Optional)
8. **No logging** - Debugging encoding/decoding issues requires adding print statements
9. **Sorting inconsistency** - Cards sorted in some places but not others; sideboard sort key duplicated

### Low (Nice to Have)
10. **No round-trip tests** - No way to verify encode→decode→encode produces identical output
11. **Performance unoptimized** - Multiple sorts, `BytesIO` overhead for small data
12. **Missing utility methods** - No deck comparison, card lookup by ID, or deck statistics helpers

## Plan

### 1. Error Recovery (Critical)
**Changes needed:**
- Wrap `parse_deckstring` in try-except blocks for `base64.b64decode`, `EOFError`, `ValueError`, and `IndexError`
- Add custom exception classes: `InvalidDeckstringError`, `UnsupportedVersionError`, `MalformedDataError`
- Include context in error messages: position in stream, expected vs actual data, partial deck state
- Add `validate_deckstring(s: str) -> Tuple[bool, Optional[str]]` that returns success + error message without raising

### 2. Deck Validation (Critical)
**Changes needed:**
- Add `Deck.validate(strict: bool = True) -> List[str]` method returning list of validation errors
- Check: total cards == 30 for constructed formats, <= 2 copies per non-legendary, hero matches format legality
- Add `card_database` parameter to validation (or global registry) to look up card rarity, set, and format legality
- Make `write_deckstring` optionally call validation before encoding (with `skip_validation=False` parameter)

### 3. Input Validation (Critical)
**Changes needed:**
- In `trisort_cards`, check `len(card_elem) in (2, 3)` before unpacking; raise `ValueError` with helpful message if wrong
- Validate all counts > 0 before encoding
- Check that heroes list is not empty before encoding
- Validate DBF IDs are positive integers

### 4. Multi-Hero Support (High)
**Changes needed:**
- Remove hardcoded `len(heroes) != 1` check in `write_deckstring`
- Add constant `MAX_HEROES = 10` with explanatory comment about format limits
- Validate hero count is between 1 and MAX_HEROES (warn but don't fail for multi-hero cases)
- Document which game modes use single vs multiple heroes

### 5. Card Database Integration (High)
**Changes needed:**
- Create `CardDatabase` protocol/interface with methods: `get_card(dbf_id: int) -> Optional[Card]`, `validate_deck(deck: Deck) -> bool`
- Add optional `card_db: Optional[CardDatabase]` parameter to `Deck.__init__` and `from_deckstring`
- Implement `Deck.get_card_names() -> List[Tuple[str, int]]` that returns human-readable card list
- Add example `CardDatabase` implementation using JSON file or SQLite cache

### 6. Documentation (High)
**Changes needed:**
- Add module-level docstring explaining deckstring format, use cases, and link to official Blizzard spec
- Add docstrings to all public functions/methods with parameters, return values, and raises clauses
- Create `examples/` directory with: basic encode/decode, validation, error handling, card database integration
- Document deckstring format in comments: byte layout, varint encoding, section structure

### 7. Type Hints (Medium)
**Changes needed:**
- Change `write_deckstring` signature: `sideboards: Optional[SideboardList] = None` → `sideboards: SideboardList = []` with note about mutable default
- Add return type to `_write_varint`: currently returns int (bytes written) but not documented
- Use `Sequence` instead of `List` for read-only parameters
- Add `typing_extensions.TypeAlias` for Python 3.9 compatibility

### 8. Logging (Medium)
**Changes needed:**
- Add `import logging; logger = logging.getLogger(__name__)` at module level
- Log at DEBUG: each varint read/written, section boundaries, card counts
- Log at INFO: successful parse/encode with card count summary
- Log at WARNING: format edge cases (multi-hero, >2 card copies, empty sideboards)

### 9. Sorting Consistency (Medium)
**Changes needed:**
- Extract `CARD_SORT_KEY = lambda x: x[0]` and `SIDEBOARD_SORT_KEY = lambda x: (x[2], x[0])` as module constants
- Apply sorting once in `Deck.__init__` or `from_deckstring` rather than in getters
- Document sort order: main deck by DBF ID, sideboards by owner then DBF ID

### 10. Testing Infrastructure (Low)
**Changes needed:**
- Add `tests/test_deckstring.py` with pytest fixtures for known valid deckstrings
- Test round-trip: `assert write_deckstring(*parse_deckstring(s)) == s` for various decks
- Test error cases: invalid base64, wrong version, truncated data, malformed varints
- Add property-based tests with Hypothesis: generate random valid decks, verify round-trip

### 11. Performance (Low)
**Changes needed:**
- Profile with `cProfile` on large deck collections to identify bottlenecks
- Consider `array.array` instead of list for card IDs if memory is concern
- Cache `Deck.as_deckstring` property (use `functools.cached_property` in Python 3.8+)
- Only sort when necessary; `trisort_cards` could bucket without sorting

### 12. Utility Methods (Low)
**Changes needed:**
- Add `Deck.__eq__` and `Deck.__hash__` for deck comparison (ignoring card order)
- Add `Deck.add_card(dbf_id: int, count: int = 1)` and `remove_card(dbf_id: int, count: int = 1)` for deck building
- Add `Deck.get_dust_cost()` and `Deck.get_mana_curve()` if card database is available
- Add `Deck.to_dict()` and `Deck.from_dict()` for JSON serialization