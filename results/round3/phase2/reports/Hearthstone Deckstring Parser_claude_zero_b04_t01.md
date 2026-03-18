# Diagnostic Report: Hearthstone Deckstring Codec

## Observations

This system implements the Blizzard Deckstring format - a compact binary serialization format for Hearthstone deck configurations. Current working capabilities:

1. **Bidirectional encoding/decoding** - Converts between deckstrings (base64-encoded binary format) and structured data
2. **Varint compression** - Implements variable-length integer encoding for space efficiency
3. **Card list management** - Groups cards by count (1x, 2x, n×) for optimized serialization
4. **Hero tracking** - Stores hero card IDs (though currently limited to single-hero decks)
5. **Format metadata** - Preserves game format (Standard, Wild, etc.) via `FormatType` enum
6. **Sideboard support** - Handles sideboard cards with owner tracking (newer format feature)
7. **OOP interface** - Provides `Deck` class wrapper around functional serialization primitives
8. **Sorted output** - Maintains consistent ordering for cards and sideboards

The binary format uses:
- Zero-byte header + version varint + format varint
- Hero count + hero IDs
- Three sections for cards (1x, 2x, n×)
- Optional sideboard flag + three sideboard sections
- Base64 encoding for transport

## Triage

### Critical Gaps

1. **No validation** - Accepts malformed inputs without bounds checking (buffer overruns, negative counts, invalid card IDs)
2. **Missing error context** - Exceptions lack details about what failed and where
3. **No documentation** - No docstrings explaining format spec, parameters, or return values
4. **Hardcoded constraints** - Single-hero limitation (`len(heroes) != 1`) may not match game rules for all formats

### Important Gaps

5. **No logging** - Can't trace encoding/decoding operations for debugging
6. **Limited type hints** - Missing return type on `__init__`, inconsistent tuple annotations
7. **No tests referenced** - Code has no visible test coverage
8. **Inefficient sorting** - Sorts on every access to `get_dbf_id_list()` and `get_sideboard_dbf_id_list()` instead of maintaining sorted invariants

### Nice-to-Have Gaps

9. **No convenience methods** - Can't easily add/remove single cards, check deck legality, or convert to human-readable formats
10. **Minimal metadata exposure** - No card count totals, no deck hash/fingerprint
11. **No format validation** - Doesn't verify deck size limits (30 cards) or format-specific rules
12. **No performance optimization** - Could cache deckstring instead of regenerating on every `as_deckstring` call

## Plan

### 1. Add Input Validation

**What to change:**
- In `_read_varint()`: Add maximum byte limit (e.g., 10 bytes) to prevent DoS from malicious varints
- In `parse_deckstring()`: Validate `num_heroes`, `num_cards_x1`, etc. are reasonable (< 1000) before allocating
- In `parse_deckstring()`: Verify stream fully consumed after parsing (detect trailing garbage)
- In `write_deckstring()`: Check `heroes` is non-empty, `cards` contains valid IDs (> 0), counts are positive
- In `Deck.__init__()`: Add assertions for initial state invariants

**Example addition to `_read_varint()`:**
```python
def _read_varint(stream: IO) -> int:
    shift = 0
    result = 0
    bytes_read = 0
    max_bytes = 10  # 64-bit varint max
    
    while True:
        if bytes_read >= max_bytes:
            raise ValueError(f"Varint too long (>{max_bytes} bytes)")
        c = stream.read(1)
        # ... rest of function
```

### 2. Improve Error Messages

**What to change:**
- Catch specific exceptions in `parse_deckstring()` and wrap with context (e.g., "Failed parsing heroes section: ...")
- Add offset tracking to varint reader and include in errors
- Create custom exception classes: `DeckstringFormatError`, `DeckstringValidationError`

**Example:**
```python
class DeckstringFormatError(ValueError):
    def __init__(self, message: str, offset: Optional[int] = None):
        super().__init__(f"{message} at byte {offset}" if offset else message)
        self.offset = offset
```

### 3. Add Comprehensive Documentation

**What to change:**
- Add module docstring explaining Blizzard format spec and linking to official documentation
- Document each function with Google-style docstrings: parameters, returns, raises, examples
- Add inline comments for binary format layout in parse/write functions
- Create README with usage examples and format specification

**Example for `parse_deckstring()`:**
```python
def parse_deckstring(deckstring: str) -> Tuple[CardIncludeList, CardList, FormatType, SideboardList]:
    """
    Decode a Blizzard deckstring into structured deck data.
    
    Args:
        deckstring: Base64-encoded binary deck representation
        
    Returns:
        4-tuple of (cards, heroes, format, sideboards) where:
        - cards: List of (card_dbf_id, count) tuples
        - heroes: List of hero card DBF IDs
        - format: Game format (Standard, Wild, etc.)
        - sideboards: List of (card_dbf_id, count, owner_dbf_id) tuples
        
    Raises:
        DeckstringFormatError: Invalid deckstring format
        DeckstringValidationError: Format correct but data invalid
        
    Example:
        >>> parse_deckstring("AAECAf0E...")
        ([(1, 2), (42, 1)], [637], <FormatType.FT_STANDARD: 2>, [])
    """
```

### 4. Relax Hero Constraint

**What to change:**
- In `write_deckstring()`: Change `if len(heroes) != 1` to `if not heroes: raise ValueError("At least one hero required")`
- Add validation for maximum heroes (likely 1-2 based on game modes)
- Document which formats support multiple heroes

### 5. Add Structured Logging

**What to change:**
- Import `logging` module
- Add logger = `logging.getLogger(__name__)` at module level
- Log at DEBUG level: "Parsing deckstring version X format Y", "Read N heroes", "Read N cards"
- Log at WARNING level for unusual but valid inputs (e.g., 10× of a card)

### 6. Complete Type Annotations

**What to change:**
- Add `-> None` to `Deck.__init__()`
- Replace `Tuple[...]` with more specific names for complex tuples (create TypeAliases)
- Use `TypeAlias` for `CardList`, `CardIncludeList`, `SideboardList` (already defined but could be proper TypeAliases)
- Add `from __future__ import annotations` for forward references

### 7. Add Test Suite

**What to change:**
- Create `tests/test_deckstrings.py` with pytest
- Test round-trip encoding (encode → decode → encode produces identical output)
- Test known deckstrings from real decks (regression tests)
- Test error cases (invalid base64, wrong version, truncated data, negative counts)
- Property-based testing with Hypothesis for random valid decks

### 8. Optimize Sorting

**What to change:**
- In `Deck.__init__()`: Initialize as `self.cards = SortedList()` (using `sortedcontainers` library)
- Or: Add `self._cards_sorted = True` flag, set to False on mutation, check in getters
- Cache computed deckstring: `self._deckstring_cache: Optional[str] = None`, invalidate on deck changes

### 9. Add Convenience Methods

**What to change to `Deck` class:**
```python
def add_card(self, card_id: int, count: int = 1) -> None:
    """Add or increment a card in the deck."""
    
def remove_card(self, card_id: int, count: int = 1) -> None:
    """Remove or decrement a card from the deck."""
    
def total_cards(self) -> int:
    """Return total card count (excluding heroes)."""
    
def to_dict(self) -> dict:
    """Export to JSON-serializable dictionary."""
    
def __str__(self) -> str:
    """Human-readable representation."""
    
def __eq__(self, other) -> bool:
    """Compare decks for equality."""
```

### 10. Add Deck Metadata

**What to change:**
- Add `deck_hash` property computing SHA256 of canonical deckstring
- Add `card_counts` property returning `{"1x": N, "2x": M, "n×": K}`
- Add `is_complete` property checking if deck meets minimum size

### 11. Add Format Validation

**What to change:**
- Create `DECK_SIZE_RULES = {FormatType.FT_STANDARD: (30, 30), ...}` mapping formats to (min, max) cards
- Add `validate(strict: bool = False) -> List[str]` method returning list of validation errors
- Check: deck size, card count limits (max 2× of non-legendary), format-specific bans

### 12. Add Caching

**What to change:**
- Add `_deckstring_cache` attribute to `Deck`
- Clear cache in `add_card()`, `remove_card()`, or any mutation
- Check cache in `as_deckstring` property before regenerating
- Use `functools.lru_cache` for pure functions like `trisort_cards()`