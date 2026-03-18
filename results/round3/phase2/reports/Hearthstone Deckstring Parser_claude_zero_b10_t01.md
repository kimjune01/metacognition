# Diagnostic Report: Hearthstone Deckstring Encoder/Decoder

## Observations

This system implements Blizzard's deckstring format for Hearthstone deck codes. Currently working capabilities:

1. **Decoding**: Parses base64-encoded deckstrings into structured deck data (cards, heroes, format, sideboards)
2. **Encoding**: Serializes deck data back into valid deckstring format
3. **Varint I/O**: Implements variable-length integer encoding/decoding for compact binary representation
4. **Card organization**: Trisorts cards by count (1x, 2x, n×) for optimized encoding
5. **Sideboard support**: Handles optional sideboard cards with owner relationships (newer format feature)
6. **Format validation**: Recognizes `FormatType` enum (Standard/Wild/etc.)
7. **OOP interface**: Provides `Deck` class with convenience methods (`from_deckstring`, `as_deckstring`, getters)

## Triage

### Critical Gaps
1. **No error handling for malformed input** - Production parsers must handle truncated/corrupted deckstrings gracefully
2. **Missing validation logic** - No enforcement of deck construction rules (30-card limit, duplicate limits, hero class restrictions)
3. **No type hints on core functions** - `parse_deckstring` return type is malformed syntax; `write_deckstring` parameters lack hints

### Important Gaps
4. **Incomplete `Deck` class** - No methods to add/remove cards, validate deck legality, or query card counts
5. **No logging/debugging support** - Silent failures make troubleshooting impossible
6. **Missing card database integration** - Cannot resolve DBF IDs to card names, verify legality, or handle rotation
7. **No tests** - Zero coverage for edge cases (empty decks, maximum card counts, invalid sideboards)

### Nice-to-Have Gaps
8. **No human-readable export** - Cannot generate deck lists in text format
9. **Limited documentation** - Module docstring exists but functions lack usage examples
10. **No CLI interface** - Users must write Python code to use this library

## Plan

### 1. Add comprehensive error handling
**Location**: `parse_deckstring()` function  
**Changes**:
- Wrap varint reads in try/except to catch `EOFError`, re-raise as `ValueError("Truncated deckstring")`
- Add check after final read: `if data.tell() < len(decoded): raise ValueError("Trailing bytes in deckstring")`
- Validate base64 decoding: catch `base64.binascii.Error` and re-raise as `ValueError("Invalid base64")`

### 2. Implement deck validation
**Location**: New method `Deck.validate()` and standalone function `validate_deck()`  
**Changes**:
- Check total card count: `sum(count for _, count in self.cards) <= 30`
- Validate duplicates for non-Highlander: `all(count <= 2 for _, count in self.cards if not is_legendary(card))`
- Add `is_legendary` parameter/lookup (requires card DB integration or external flag)
- Raise `ValueError` with specific message like `"Deck contains 32 cards, maximum is 30"`

### 3. Fix type hints
**Location**: Lines 106-107 (parse_deckstring), 127-132 (write_deckstring)  
**Changes**:
```python
def parse_deckstring(deckstring: str) -> Tuple[
    CardIncludeList, CardList, FormatType, SideboardList
]:
```
Add imports: `from typing import Tuple` (already present, verify usage)

### 4. Expand `Deck` class functionality
**Location**: `Deck` class body  
**Changes**:
- Add `add_card(self, dbf_id: int, count: int = 1) -> None` - appends or updates card count
- Add `remove_card(self, dbf_id: int) -> None` - removes card entirely
- Add `get_card_count(self, dbf_id: int) -> int` - returns 0 if not present
- Add `total_cards(self) -> int` property - sums all card counts
- Add `__repr__` and `__str__` for debugging

### 5. Add logging
**Location**: Top of file and critical paths  
**Changes**:
- Import: `import logging; logger = logging.getLogger(__name__)`
- Add debug logs: `logger.debug(f"Parsing deckstring version {version}, format {format}")`
- Log warnings: `logger.warning(f"Unusual card count {count} for card {card_id}")`

### 6. Integrate card database (optional dependency)
**Location**: New module `hearthstone/carddb.py` or use existing if available  
**Changes**:
- Create `CardDatabase` class that loads from HearthstoneJSON or similar
- Add methods: `get_card_name(dbf_id)`, `is_legendary(dbf_id)`, `get_class(dbf_id)`
- Make optional: `try: from .carddb import CardDatabase` with graceful fallback
- Update `Deck` with `to_string(self, card_db: Optional[CardDatabase] = None)` that prints human-readable list

### 7. Write test suite
**Location**: New file `tests/test_deckstring.py`  
**Changes**:
- Test valid deckstring roundtrip (decode → encode → decode, assert equality)
- Test invalid inputs: empty string, bad base64, truncated data, wrong version
- Test edge cases: 30-card deck, all 1× cards, all 2× cards, cards with count >2
- Test sideboard presence/absence flags
- Use known valid deckstrings from live game as fixtures

### 8. Add human-readable export
**Location**: New method `Deck.to_text()`  
**Changes**:
```python
def to_text(self, card_names: dict[int, str]) -> str:
    """Returns deck list like:
    # 1x Elven Archer
    # 2x Fireball
    """
    lines = [f"# {count}x {card_names.get(dbf_id, f'Unknown({dbf_id})')}"
             for dbf_id, count in self.get_dbf_id_list()]
    return "\n".join(lines)
```

### 9. Add docstrings with examples
**Location**: All public functions and `Deck` class  
**Changes**:
```python
def parse_deckstring(deckstring: str) -> ...:
    """
    Decode a Hearthstone deckstring into components.
    
    Args:
        deckstring: Base64-encoded deck code (e.g., "AAECAa0GBg...")
    
    Returns:
        Tuple of (cards, heroes, format, sideboards)
    
    Example:
        >>> cards, heroes, fmt, sb = parse_deckstring("AAECAa0GBg...")
        >>> print(f"Format: {fmt}, Hero: {heroes[0]}")
    
    Raises:
        ValueError: If deckstring is malformed or unsupported version
    """
```

### 10. Create CLI interface
**Location**: New file `hearthstone/cli.py` with `if __name__ == "__main__"` block  
**Changes**:
- Use `argparse` or `click` library
- Commands: `decode <deckstring>` (print JSON), `encode <json_file>` (output deckstring)
- Optional: `validate <deckstring>` (check legality), `export <deckstring>` (human-readable text)
- Entry point in `pyproject.toml` or `setup.py`: `console_scripts = ["hs-deck=hearthstone.cli:main"]`