# Diagnostic Report: Blizzard Deckstring Format Support

## Observations

This system provides encoding and decoding support for Hearthstone deck codes (deckstrings):

**Working Capabilities:**
1. **Decoding deckstrings** - Parses base64-encoded deck codes into structured data (cards, heroes, format, sideboards)
2. **Encoding deckstrings** - Converts deck data back into base64 deckstring format
3. **Varint I/O** - Implements variable-length integer encoding/decoding for compact binary representation
4. **Card organization** - Separates cards by count (1x, 2x, n×) for efficient encoding
5. **Sideboard support** - Handles optional sideboard cards with ownership tracking
6. **Format type awareness** - Tracks deck format (Standard, Wild, etc.) via FormatType enum
7. **Object-oriented interface** - Provides a `Deck` class with factory methods and properties
8. **Sorting utilities** - Maintains consistent card ordering for deterministic deckstring generation

## Triage

**Critical Gaps:**
1. **No error handling beyond basic validation** - Production code would fail ungracefully on malformed input
2. **Missing multi-hero support** - Hard-coded single hero requirement, but format supports multiple
3. **No card database integration** - Cannot validate card IDs or verify deck legality
4. **Incomplete type hints** - Return type annotations use tuples instead of clear types

**Important Gaps:**
5. **No deck validation logic** - Cannot check deck size limits, duplicate restrictions, or format legality
6. **Missing comprehensive tests** - No test suite visible to verify edge cases
7. **Undocumented public API** - Methods and classes lack docstrings
8. **No logging or diagnostics** - Silent failures make debugging difficult

**Nice-to-Have:**
9. **No human-readable representation** - Missing `__str__` or `__repr__` for debugging
10. **Limited deck manipulation methods** - Cannot add/remove cards through the interface
11. **No deckstring validation utilities** - Cannot pre-validate before attempting decode
12. **Performance not optimized** - BytesIO operations could be streamlined for high-throughput scenarios

## Plan

### 1. Error Handling (Critical)

**Changes needed:**
- Wrap `parse_deckstring` in try-except blocks for specific error types
- Create custom exception classes: `InvalidDeckstringError`, `UnsupportedVersionError`, `CorruptedDataError`
- Add bounds checking in `_read_varint` to prevent infinite loops on malformed data
- Validate card counts are positive integers
- Handle truncated deckstrings gracefully (catch `struct.error` and `EOFError`)

**Example:**
```python
class InvalidDeckstringError(ValueError):
    """Raised when deckstring format is invalid"""
    pass

def parse_deckstring(deckstring):
    try:
        decoded = base64.b64decode(deckstring)
    except Exception as e:
        raise InvalidDeckstringError(f"Invalid base64 encoding: {e}")
    # ... rest of parsing with specific error messages
```

### 2. Multi-Hero Support (Critical)

**Changes needed:**
- Remove the `if len(heroes) != 1` check in `write_deckstring`
- Add optional parameter `allow_multiple_heroes: bool = True` for backward compatibility
- Update docstrings to document multi-hero deck support
- Add validation that at least one hero exists

**Location:** `deckstrings.py:207-208`

### 3. Card Database Integration (Critical)

**Changes needed:**
- Create new module `card_db.py` with `CardDatabase` class
- Add method `Deck.validate(card_db: CardDatabase) -> List[str]` that returns validation errors
- Check: card IDs exist, format legality, class restrictions, deck size (30 cards standard)
- Implement card count limits (legendary = 1, others = 2 in most formats)

**New file structure:**
```python
class CardDatabase:
    def get_card(self, dbf_id: int) -> Optional[Card]:
        pass
    
    def is_legal_in_format(self, dbf_id: int, format: FormatType) -> bool:
        pass
```

### 4. Improve Type Hints (Critical)

**Changes needed:**
- Create `TypedDict` or `dataclass` for return values instead of bare tuples
- Replace `Tuple[CardIncludeList, CardList, FormatType, SideboardList]` with named type
- Add type hints to all private functions (`_read_varint`, `_write_varint`)
- Use `Protocol` for IO types instead of bare `IO`

**Example:**
```python
@dataclass
class ParsedDeck:
    cards: CardIncludeList
    heroes: CardList
    format: FormatType
    sideboards: SideboardList
```

### 5. Deck Validation (Important)

**Changes needed:**
- Add `Deck.is_valid(self) -> Tuple[bool, List[str]]` method
- Check deck size: typically 30 cards for constructed, 40 for Arena
- Verify card count constraints without database (structural validation)
- Validate sideboard ownership references valid cards in main deck
- Add `Deck.total_cards` property

### 6. Testing Suite (Important)

**Changes needed:**
- Create `tests/test_deckstrings.py`
- Test cases: roundtrip encoding, known good deckstrings, malformed input, edge cases
- Parametrized tests for different formats (Standard, Wild, Classic, Twist)
- Test sideboards with 0, 1, and many sideboard cards
- Fuzz testing with random binary data

**Minimum test coverage:**
- Valid deckstring roundtrip
- Empty sideboards
- All three card count buckets (1x, 2x, n×)
- Invalid base64, wrong version, unsupported format

### 7. Documentation (Important)

**Changes needed:**
- Add module-level docstring explaining Blizzard deckstring format
- Document `Deck` class with usage examples
- Add docstrings to `parse_deckstring` and `write_deckstring` with parameter descriptions
- Create `examples/` directory with sample code
- Document the binary format specification in comments

**Example module docstring:**
```python
"""
Hearthstone Deckstring Encoder/Decoder

Supports the Blizzard deckstring format for compact deck representation.
Deckstrings encode deck composition (cards, heroes, format) as base64 strings.

Example:
    >>> deck = Deck.from_deckstring("AAECAa...")
    >>> deck.heroes
    [7]
    >>> deck.cards[:3]
    [(1, 2), (42, 2), (100, 1)]
"""
```

### 8. Logging and Diagnostics (Important)

**Changes needed:**
- Add `import logging` and create module logger
- Log warnings for unusual but valid decks (>30 cards, unknown format codes)
- Debug logging for parse steps (header, heroes, cards, sideboards)
- Add optional `verbose` parameter to decode functions

### 9. Human-Readable Representation (Nice-to-Have)

**Changes needed:**
- Implement `Deck.__str__` showing card count summary
- Implement `Deck.__repr__` showing full details
- Add `Deck.to_dict()` for JSON serialization
- Add `Deck.from_dict()` factory method

**Example:**
```python
def __str__(self):
    return f"Deck(format={self.format.name}, cards={len(self.cards)}, heroes={self.heroes})"
```

### 10. Deck Manipulation Methods (Nice-to-Have)

**Changes needed:**
- Add `Deck.add_card(dbf_id: int, count: int = 1)`
- Add `Deck.remove_card(dbf_id: int, count: int = 1)`
- Add `Deck.clear()`
- Add `Deck.copy()` for creating modified versions
- Maintain sorted order automatically after modifications

### 11. Deckstring Validation Utilities (Nice-to-Have)

**Changes needed:**
- Add function `is_valid_deckstring(s: str) -> bool` that checks without parsing
- Check base64 validity, minimum length, header byte
- Add `get_deckstring_version(s: str) -> int` to peek version without full parse
- Useful for UI validation before expensive parsing

### 12. Performance Optimization (Nice-to-Have)

**Changes needed:**
- Profile with `cProfile` on large batches of deckstrings
- Consider using `array.array` instead of lists for numeric data
- Cache sorted card lists to avoid repeated sorting
- Use `io.BufferedWriter` for batch encoding operations
- Add optional C extension for varint encoding (10-100× speedup potential)