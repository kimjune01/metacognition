# Diagnostic Report: Blizzard Deckstring Format Support

## Observations

This system implements encoding and decoding for Hearthstone deck strings using Blizzard's deckstring format. Current working capabilities:

1. **Varint I/O**: Reads and writes variable-length integers using protocol buffer-style encoding (7 bits per byte with continuation bit)

2. **Deckstring Parsing**: Decodes base64-encoded deckstrings into structured deck data containing:
   - Format type (Wild, Standard, etc.)
   - Hero cards (DBF IDs)
   - Main deck cards with counts
   - Sideboard cards with counts and ownership

3. **Deckstring Generation**: Encodes deck data back into base64 deckstrings with optimized storage (cards grouped by count: 1x, 2x, or Nx)

4. **Deck Object Model**: Provides a `Deck` class with:
   - Factory method `from_deckstring()`
   - Property `as_deckstring` for serialization
   - Sorted accessor methods for cards and sideboards

5. **Card Organization**: `trisort_cards()` groups cards by count for efficient encoding

6. **Version Control**: Handles deckstring version field (currently v1 only)

---

## Triage

### Critical Gaps

1. **No Error Recovery**: Invalid data causes cryptic failures rather than actionable errors
2. **Missing Validation**: No bounds checking, duplicate detection, or format-specific rule validation
3. **Zero Documentation**: No docstrings, usage examples, or format specification
4. **Incomplete Type Hints**: Return tuple lacks proper TypedDict/NamedTuple structure

### Important Gaps

5. **No Multi-Hero Support**: Code rejects decks with ≠1 hero despite reading `num_heroes` dynamically
6. **No Round-Trip Testing**: Cannot verify encode(decode(x)) == x
7. **Missing Utilities**: No diff, merge, or card lookup helpers
8. **Incomplete Trailing Data Handling**: Doesn't verify EOF or warn about extra bytes

### Nice-to-Have Gaps

9. **No Performance Optimization**: Could cache decoded results or use faster base64 variants
10. **Limited Export Formats**: Only supports deckstring, not JSON/XML/human-readable
11. **No Logging**: Silent operation makes debugging difficult
12. **No CLI Interface**: Requires Python API usage for all operations

---

## Plan

### 1. Error Recovery
**File**: Throughout, especially `parse_deckstring()` and `write_deckstring()`

- Wrap `_read_varint()` in try-except to catch `EOFError` and raise `ValueError("Truncated deckstring at byte {position}")`
- Catch `base64.binascii.Error` in `parse_deckstring()` and raise `ValueError("Invalid base64 encoding")`
- Add `InvalidDeckstringError` exception class that preserves partial parse state for debugging
- In `write_deckstring()`, validate inputs before writing (non-negative IDs, counts ≥ 1)

### 2. Validation
**New file**: `validation.py` or inline in `Deck` class

- Add `Deck.validate()` method that checks:
  - Card counts are positive
  - No duplicate (card_id, sideboard_owner) pairs
  - Total card count meets format rules (30 for Standard, 40 for Twist)
  - Legendary cards have count ≤ 1
  - Hero class matches deck cards (requires external card database)
- Add `strict` parameter to `from_deckstring()` to enable validation on parse
- Add bounds check in `_read_varint()` to prevent integer overflow (cap at 2^32)

### 3. Documentation
**All files**

- Add module docstring explaining Hearthstone deckstring format with link to official spec
- Add docstrings to all functions with Args/Returns/Raises sections:
  ```python
  def parse_deckstring(deckstring: str) -> Tuple[...]:
      """Parse a Hearthstone deckstring into components.
      
      Args:
          deckstring: Base64-encoded deck string (e.g., "AAECAa0GBgiw...")
          
      Returns:
          Tuple of (cards, heroes, format, sideboards) where...
          
      Raises:
          ValueError: If deckstring is malformed or unsupported version
      """
  ```
- Add usage examples in module docstring showing encode/decode round-trip
- Add `README.md` with installation, quickstart, and format specification

### 4. Type Hints Improvement
**File**: Top of module

- Replace return tuple with `NamedTuple`:
  ```python
  class ParsedDeck(NamedTuple):
      cards: CardIncludeList
      heroes: CardList
      format: FormatType
      sideboards: SideboardList
  ```
- Update `parse_deckstring()` signature: `-> ParsedDeck`
- Update `Deck.from_deckstring()` to unpack named fields: `parsed.cards`, etc.

### 5. Multi-Hero Support
**File**: `write_deckstring()` lines 172-173, `Deck.__init__()` line 71

- Change validation from `if len(heroes) != 1` to `if not (1 <= len(heroes) <= 2)`
- Update error message: `"Hero count must be 1-2, got {len(heroes)}"`
- Note in docstring that multi-hero is for future Hearthstone modes (currently unused)

### 6. Round-Trip Testing
**New file**: `test_deckstring.py`

- Add `pytest` test suite with:
  - `test_roundtrip()`: Generate random valid decks, verify `parse(write(x)) == x`
  - `test_known_deckstrings()`: Parse real deckstrings from meta snapshots, verify properties
  - `test_malformed()`: Verify graceful error handling for truncated/invalid input
  - `test_edge_cases()`: Empty sideboard, 40-card deck, multiple heroes
- Add CI workflow (GitHub Actions) to run tests on PR

### 7. Utility Functions
**New file**: `utils.py`

- Add `deck_diff(deck1, deck2) -> Dict[str, List]` returning added/removed/changed cards
- Add `merge_decks(deck1, deck2, strategy="union"|"intersection") -> Deck`
- Add `get_card_name(dbf_id: int) -> str` using embedded/external card database
- Add `Deck.__str__()` to print human-readable card list with names and counts

### 8. Trailing Data Handling
**File**: `parse_deckstring()` after sideboard parsing

- Add after last read:
  ```python
  remaining = data.read()
  if remaining:
      import warnings
      warnings.warn(f"Deckstring has {len(remaining)} trailing bytes")
  ```
- Add `strict` parameter that raises `ValueError` on trailing data

### 9. Performance Optimization
**File**: `Deck` class

- Add `@functools.lru_cache` to `Deck.as_deckstring` if deck is immutable
- Make `Deck` frozen dataclass or add `__hash__`/`__eq__` for caching
- Profile with `cProfile` on large deck collections to identify bottlenecks
- Consider `base64.urlsafe_b64decode` if URL compatibility needed

### 10. Export Formats
**New file**: `export.py`

- Add `Deck.to_json() -> str` with schema:
  ```json
  {
    "format": "FT_STANDARD",
    "heroes": [12345],
    "cards": [{"id": 100, "count": 2}, ...],
    "sideboards": [...]
  }
  ```
- Add `Deck.to_text() -> str` with human-readable format:
  ```
  # Deck (Standard)
  # Hero: Jaina Proudmoore
  2x Frostbolt
  1x Archmage Antonidas
  ```
- Add `Deck.from_json()` and `Deck.from_text()` class methods

### 11. Logging
**File**: Throughout

- Add `import logging` and `logger = logging.getLogger(__name__)`
- Log at `DEBUG` level: "Parsing deckstring version {version}, format {format}"
- Log at `INFO` level: "Decoded {len(cards)} cards, {len(sideboards)} sideboard cards"
- Log at `WARNING` level for recoverable issues (trailing data, unusual hero count)

### 12. CLI Interface
**New file**: `__main__.py`

- Add `argparse` CLI with subcommands:
  - `decode <deckstring>`: Print deck as text
  - `encode <file.json>`: Generate deckstring from JSON
  - `validate <deckstring>`: Check deck validity
  - `diff <deckstring1> <deckstring2>`: Show differences
- Add entry point in `setup.py`: `console_scripts = ['deckstring=deckstring.__main__:main']`
- Support stdin for pipe workflows: `echo "AAE..." | deckstring decode`