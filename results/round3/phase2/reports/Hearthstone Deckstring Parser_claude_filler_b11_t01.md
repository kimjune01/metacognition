# Diagnostic Report: Blizzard Deckstring Format Support

## Observations

This system implements encoding and decoding functionality for Hearthstone deck strings, which are base64-encoded binary representations of deck compositions. Current working capabilities include:

1. **Varint I/O**: Implements variable-length integer encoding/decoding (`_read_varint`, `_write_varint`) for space-efficient binary serialization
2. **Deckstring parsing**: Decodes base64 deckstrings into structured data containing:
   - Card lists with DBF IDs and counts
   - Hero cards
   - Format type (Standard, Wild, etc.)
   - Sideboard cards (with owner references)
3. **Deckstring generation**: Encodes deck data back into base64 deckstring format
4. **Card list optimization**: Groups cards by count (1x, 2x, n×) using `trisort_cards` to minimize encoded size
5. **Deck object model**: Provides a `Deck` class with factory methods and property accessors
6. **Version handling**: Enforces deckstring version 1 format
7. **Sideboard support**: Handles optional sideboard cards with owner associations

## Triage

### Critical Gaps (Production Blockers)

1. **No validation** - The system accepts invalid deck compositions (wrong card counts for format, invalid hero/class combinations, banned cards)
2. **Silent error handling** - EOFError and ValueError are raised but not documented; malformed deckstrings crash rather than failing gracefully
3. **No logging** - Zero observability into parsing failures or edge cases
4. **Type hints incomplete** - Return type annotation syntax is malformed in `trisort_cards`

### High-Priority Gaps (Usability Issues)

5. **No card database integration** - Cannot validate DBF IDs or resolve card names
6. **Missing documentation** - No docstrings explaining deckstring format, usage examples, or API contracts
7. **No round-trip testing** - No verification that encode(decode(x)) == x
8. **Error messages lack context** - When parsing fails, no indication of which part of deckstring or what byte offset

### Medium-Priority Gaps (Quality of Life)

9. **No human-readable output** - Cannot print deck in readable format with card names
10. **Limited Deck class API** - Missing methods like `add_card()`, `remove_card()`, `get_card_count()`, `validate()`
11. **No format conversion** - Cannot upgrade/downgrade between deckstring versions
12. **Hardcoded hero constraint** - Raises error for != 1 hero but some formats allow multiple heroes

### Low-Priority Gaps (Nice to Have)

13. **No CLI interface** - Cannot use as standalone tool to decode/encode deckstrings
14. **No performance optimization** - BytesIO allocations could be reduced; no benchmarks
15. **No alternative serialization** - Cannot export to JSON, deck tracker formats, etc.

## Plan

### 1. Add validation (Critical)

**Changes needed:**
- Create `DeckValidator` class in new file `validation.py`
- Implement `validate_deck_composition()` method checking:
  - Card count limits (30 for Standard/Wild, varies for other formats)
  - Max copies per card (2 for normal, 1 for legendary, varies by format)
  - Format-specific rules (Standard year restrictions, banned cards)
- Add optional `validate: bool = True` parameter to `Deck.from_deckstring()`
- Raise `DeckValidationError` (new exception subclass) with detailed message listing all violations
- Add `Deck.validate()` method callable after construction

### 2. Implement error recovery (Critical)

**Changes needed:**
- Wrap `parse_deckstring()` body in try-except catching EOFError, ValueError, base64.binascii.Error
- Create custom exception hierarchy:
  ```python
  class DeckstringError(Exception): pass
  class InvalidDeckstringError(DeckstringError): pass
  class UnsupportedVersionError(DeckstringError): pass
  class CorruptedDeckstringError(DeckstringError): pass
  ```
- In exceptions, include: original deckstring (truncated), byte offset, expected vs actual values
- Add `strict: bool = True` parameter to allow lenient parsing that skips unknown sections

### 3. Add structured logging (Critical)

**Changes needed:**
- Add `import logging` and create module logger: `logger = logging.getLogger(__name__)`
- Log at DEBUG: each section parsed (heroes, cards x1/x2/xn, sideboards) with counts
- Log at WARNING: unrecognized format types, unusual card counts
- Log at ERROR: validation failures with deck composition details
- Add `__repr__()` methods to `Deck` class for logging

### 4. Fix type annotations (Critical)

**Changes needed:**
- Change line 92 return type from `-> (Tuple[...])` to `-> Tuple[Tuple[tuple, ...], Tuple[tuple, ...], Tuple[tuple, ...]]`
- More precisely: `-> Tuple[List[Tuple[int, int]], List[Tuple[int, int]], List[Tuple[int, int]]]` for main cards
- For sideboards version handling mixed 2-tuple and 3-tuple, use `Union[Tuple[int, int], Tuple[int, int, int]]`
- Add `from __future__ import annotations` for forward references

### 5. Integrate card database (High)

**Changes needed:**
- Create `CardDatabase` abstract base class with methods: `get_card(dbf_id: int) -> Optional[Card]`
- Create `Card` dataclass with fields: `dbf_id`, `name`, `cost`, `rarity`, `card_type`, `set`, `collectible`
- Modify `Deck` to accept optional `card_db: Optional[CardDatabase] = None` in constructor
- Add `Deck.get_card_names() -> List[str]` that uses card_db to resolve names
- Implement `JSONCardDatabase` that loads from hearthstonejson.com data file
- Add validation rules using card metadata (rarity for copy limits, set for format legality)

### 6. Write comprehensive documentation (High)

**Changes needed:**
- Add module docstring explaining deckstring format specification with examples
- Add docstrings to all public functions/methods following Google style:
  ```python
  def parse_deckstring(deckstring: str) -> ...:
      """Parse a Hearthstone deckstring into structured deck data.
      
      Args:
          deckstring: Base64-encoded deck string
          
      Returns:
          Tuple of (cards, heroes, format, sideboards)
          
      Raises:
          InvalidDeckstringError: If deckstring is malformed
          UnsupportedVersionError: If version != 1
      """
  ```
- Create `examples/` directory with:
  - `basic_usage.py` - decode/encode simple deck
  - `validation.py` - validate deck composition
  - `card_names.py` - print human-readable deck list

### 7. Add round-trip tests (High)

**Changes needed:**
- Create `tests/test_deckstring.py` with pytest
- Add `test_roundtrip_encoding()` with 20+ real deckstrings covering:
  - Standard/Wild formats
  - Different hero classes
  - Sideboards present/absent
  - Edge cases (singleton decks, 30x of same card)
- Verify: `parse_deckstring(write_deckstring(*parse_deckstring(x))) == parse_deckstring(x)`
- Add property-based tests using Hypothesis to generate random valid decks

### 8. Enhance error messages (High)

**Changes needed:**
- In `_read_varint()`, track byte offset in exception: `raise CorruptedDeckstringError(f"Unexpected EOF at byte {stream.tell()} while reading varint")`
- In `parse_deckstring()`, add context to each section:
  ```python
  try:
      num_heroes = _read_varint(data)
  except EOFError as e:
      raise CorruptedDeckstringError(f"Failed reading hero count") from e
  ```
- Include partial parse results in exception: "Successfully parsed 5 cards before failure"

### 9. Add human-readable output (Medium)

**Changes needed:**
- Add `Deck.to_string(card_db: CardDatabase) -> str` method returning:
  ```
  ### Deck Name
  # Class: Mage
  # Format: Standard
  
  # Spells (10)
  2x Fireball
  2x Frostbolt
  ...
  ```
- Add `Deck.to_dict() -> dict` for JSON serialization
- Implement `__str__()` to return short summary: "30-card Mage deck (Standard)"

### 10. Expand Deck API (Medium)

**Changes needed:**
- Add methods to `Deck` class:
  ```python
  def add_card(self, dbf_id: int, count: int = 1) -> None
  def remove_card(self, dbf_id: int, count: int = 1) -> None
  def get_card_count(self, dbf_id: int) -> int
  def total_cards(self) -> int
  def clear(self) -> None
  def copy(self) -> 'Deck'
  ```
- Add `__eq__()` and `__hash__()` for deck comparison
- Support iteration: `def __iter__(self) -> Iterator[Tuple[int, int]]`

### 11. Support version migration (Medium)

**Changes needed:**
- Add `DECKSTRING_VERSION_2` constant when/if new version emerges
- Modify `parse_deckstring()` to handle multiple versions with version-specific parsers
- Add `upgrade_deckstring(deckstring: str, target_version: int) -> str` function
- Maintain backward compatibility by defaulting writes to latest version

### 12. Relax hero constraint (Medium)

**Changes needed:**
- Change validation in `write_deckstring()`:
  ```python
  if not (1 <= len(heroes) <= 2):
      raise ValueError(f"Hero count must be 1-2, got {len(heroes)}")
  ```
- Add format-specific hero validation in DeckValidator
- Document which formats allow multiple heroes (Duels, Twist variants)

### 13. Create CLI tool (Low)

**Changes needed:**
- Create `cli.py` with Click or argparse:
  ```python
  # Usage: python -m hearthstone_deckstrings decode AAECAf0...
  #        python -m hearthstone_deckstrings encode deck.json
  ```
- Commands: `decode`, `encode`, `validate`, `convert`
- Add `__main__.py` for `python -m` invocation
- Support stdin/stdout piping for shell integration

### 14. Optimize performance (Low)

**Changes needed:**
- Profile with `cProfile` on large batch operations
- Replace BytesIO allocations with pre-allocated byte arrays where size is known
- Cache trisort results if encoding same deck multiple times
- Add benchmarks in `tests/benchmarks/` comparing against reference implementations

### 15. Support alternative formats (Low)

**Changes needed:**
- Add `Deck.to_json() -> str` and `Deck.from_json(json_str: str) -> Deck`
- Add exporters for:
  - Hearthstone Deck Tracker format
  - HSReplay.net API format
  - Arena drafting services
- Create `converters/` module with pluggable export backends