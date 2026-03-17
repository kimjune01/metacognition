# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the **Blizzard Deckstring format** for encoding/decoding Hearthstone deck lists. Current working capabilities:

1. **Decoding deckstrings** from base64-encoded strings into structured deck data
   - Parses version, format type, heroes, cards (with counts), and sideboard cards
   - Handles variable-length integer encoding (varint) for compact representation
   - Supports three card count categories: 1x, 2x, and n× for optimization

2. **Encoding deckstrings** from deck components back to base64 strings
   - Serializes decks with the same format structure
   - Maintains sorting invariants for consistent encoding

3. **Deck object model** via the `Deck` class
   - Factory method `from_deckstring()` for construction
   - Property `as_deckstring` for serialization
   - Getter methods for sorted card/sideboard lists

4. **Format validation** 
   - Validates header byte and version number
   - Enforces exactly 1 hero per deck (Hearthstone constraint)

5. **Sideboard support**
   - Handles optional sideboard cards with owner references (for game modes that support them)

## Triage

### Critical Gaps

1. **No error handling for malformed input** - Production code will receive corrupted/tampered deckstrings
2. **No validation of deck legality** - Doesn't check card count limits, format restrictions, or valid card IDs
3. **No tests** - Complex binary format parser with zero test coverage

### Important Gaps

4. **Poor error messages** - Generic `ValueError` with minimal context
5. **No logging** - Impossible to debug issues in production
6. **Missing documentation** - No docstrings explaining the format, constraints, or usage
7. **Type hints incomplete** - Return type annotation uses deprecated tuple syntax; IO type too generic

### Minor Gaps

8. **Hard-coded single hero limit** - Comment suggests awareness but implementation is inflexible
9. **No card database integration** - Can't validate if card IDs exist or get card names
10. **No human-readable export** - Only supports binary format, not text deck lists

## Plan

### 1. Error Handling for Malformed Input

**Changes needed:**
- Wrap `base64.b64decode()` in try/except for `binascii.Error`
- Add bounds checking in `_read_varint()` to prevent infinite loops
- Validate that stream is fully consumed after parsing (detect trailing garbage)
- Add explicit checks for negative varints where inappropriate (counts, IDs)

```python
# In parse_deckstring()
try:
    decoded = base64.b64decode(deckstring, validate=True)
except base64.binascii.Error as e:
    raise ValueError(f"Invalid base64 encoding: {e}") from e

# In _read_varint()
if shift > 64:  # Prevent DoS via extremely large varints
    raise ValueError("Varint exceeds maximum size")
```

### 2. Deck Legality Validation

**Changes needed:**
- Create `DeckValidator` class with configurable rules
- Add validation for:
  - Max 2 copies per card (except specific legendary rule)
  - 30 cards total for Standard/Wild
  - Cards belong to hero class or neutral
  - Format-specific card bans/restrictions
- Make validation optional via `validate=True` parameter

```python
def parse_deckstring(..., validate: bool = False) -> ...:
    # ... existing parsing ...
    if validate:
        validator = DeckValidator(format)
        validator.validate_deck(cards, heroes)
    return cards, heroes, format, sideboards
```

### 3. Test Coverage

**Changes needed:**
- Create `tests/test_deckstring.py` with:
  - Round-trip tests (decode → encode → decode)
  - Known good deckstrings from real decks
  - Malformed input tests (truncated, invalid header, bad varints)
  - Edge cases (empty deck, max count cards, large sideboards)
  - Regression tests for any bugs found in production

### 4. Improved Error Messages

**Changes needed:**
- Create custom exception classes: `DeckstringError`, `InvalidFormatError`, `ValidationError`
- Include context in error messages: position in stream, expected vs actual values
- Add `__str__` methods that explain what went wrong

```python
class InvalidHeaderError(DeckstringError):
    def __init__(self, got: bytes):
        self.got = got
        super().__init__(f"Expected header byte 0x00, got {got.hex()}")
```

### 5. Logging

**Changes needed:**
- Add `import logging` and create module logger: `logger = logging.getLogger(__name__)`
- Log at DEBUG level: parsing progress, card counts, format detected
- Log at WARNING level: deprecated format versions, unusual deck configurations
- Log at ERROR level: validation failures (if not raising)

### 6. Documentation

**Changes needed:**
- Add module docstring explaining Blizzard deckstring format specification
- Add docstrings to all functions with:
  - Parameters (types and meaning)
  - Return values (structure and guarantees)
  - Exceptions raised
  - Examples
- Create `README.md` with usage examples

### 7. Type Hints Improvement

**Changes needed:**
- Replace `IO` with `BinaryIO` from `typing`
- Use `tuple[int, int]` instead of `Tuple[int, int]` (PEP 604, Python 3.10+)
- Add generic type parameter to `List`: already done but verify consistency
- Add return type to `Deck.__init__` as `None`

### 8. Flexible Hero Count

**Changes needed:**
- Remove hard-coded hero count check from `write_deckstring()`
- Add `max_heroes: Optional[int] = None` parameter for validation
- Support multi-hero formats (e.g., Duels, Tavern Brawl modes)

```python
def write_deckstring(..., max_heroes: Optional[int] = 1) -> str:
    if max_heroes is not None and len(heroes) > max_heroes:
        raise ValueError(f"Too many heroes: {len(heroes)} > {max_heroes}")
```

### 9. Card Database Integration

**Changes needed:**
- Create `CardDatabase` interface (abstract base class)
- Implement adapters for:
  - JSON file database
  - HearthstoneJSON API
  - SQLite local cache
- Add `validate_card_ids()` method using database
- Add `Deck.to_card_names()` for human-readable output

### 10. Human-Readable Export

**Changes needed:**
- Add `Deck.to_text()` method outputting format:
  ```
  ### Deck Name
  # Class: Mage
  # Format: Standard
  2x Frostbolt
  1x Fireball
  ...
  ```
- Add `Deck.from_text()` parser (requires card database for name → ID mapping)
- Support importing from popular deck sites (HSReplay, Hearthpwn formats)