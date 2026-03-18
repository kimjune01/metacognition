# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Deckstring format encoder/decoder for Hearthstone deck codes. Current working capabilities:

1. **Binary varint I/O** - Reads and writes variable-length integers in protocol buffer style (`_read_varint`, `_write_varint`)
2. **Deckstring parsing** - Decodes base64-encoded deck strings into structured data (format, heroes, cards, sideboards)
3. **Deckstring serialization** - Encodes deck data back to base64 deckstring format
4. **Card list optimization** - Groups cards by count (×1, ×2, ×N) to minimize encoding size (`trisort_cards`)
5. **Sideboard support** - Handles optional sideboard cards with owner references (for game modes that use them)
6. **Format type awareness** - Preserves the game format (Wild, Standard, etc.) via enum
7. **Object-oriented interface** - Provides a `Deck` class with convenience methods (`from_deckstring`, `as_deckstring`, getter methods)

## Triage

### Critical Gaps
1. **No validation** - The system trusts all input without checking deck construction rules (class limits, duplicate legendaries, card counts, format legality)
2. **Missing error context** - Exceptions don't indicate where in the deckstring parsing failed or what the invalid data was
3. **No card metadata** - System only handles DBF IDs; can't translate to/from card names or validate card existence

### Important Gaps
4. **Incomplete type hints** - Return type on line 92 uses tuple syntax instead of `Tuple[...]`; missing hints on some functions
5. **No comprehensive tests** - Code has no visible test coverage for edge cases (empty decks, malformed strings, boundary values)
6. **Limited hero support** - Hard-coded check for exactly 1 hero (line 208), but multi-hero modes exist (Duels, Battlegrounds)

### Nice-to-Have Gaps
7. **No logging/debugging** - No way to trace parsing steps or inspect intermediate state
8. **Missing docstrings** - Functions lack documentation for parameters, return values, and expected format
9. **No round-trip verification** - No built-in way to verify encode(decode(x)) == x
10. **Inflexible sorting** - Hardcoded sort behavior; no option to preserve original card order

## Plan

### 1. Add Input Validation
**Location**: `parse_deckstring` function (lines 105-177)
- After decoding base64, check decoded length is at least 3 bytes before reading header
- After reading format, validate hero count is in range [0, 10] before loop
- Track total cards parsed; raise `ValueError` if count exceeds 30 (or format-specific limit)
- Add optional `validate_deck_rules` parameter that checks:
  - Card counts don't exceed format limits (2 for normal, unlimited for arena)
  - If card DB provided, verify legendary cards appear at most once
  
**Location**: `write_deckstring` function (lines 180-245)
- Validate `cards` parameter: each tuple is (int >= 0, int >= 1)
- Validate `sideboards` parameter: each tuple is (int >= 0, int >= 1, int >= 0)
- Check hero IDs are non-negative integers

### 2. Improve Error Messages
**Location**: Throughout parsing logic
- Change line 113: `raise ValueError("Invalid deckstring")` → `raise ValueError("Invalid deckstring: missing null header byte")`
- Change line 116: Add `f"at byte offset {data.tell()}"`
- Change line 120: `raise ValueError(f"Unsupported FormatType {format} (valid: {[f.value for f in FormatType]})")`
- In `_read_varint`, change line 23: `raise EOFError(f"Unexpected EOF at offset {stream.tell()} while reading varint")`
- Wrap entire `parse_deckstring` in try/except to catch `struct.error` or `binascii.Error` and reraise with deckstring prefix for debugging

### 3. Add Card Database Integration
**New file**: `card_db.py`
- Create `CardDatabase` class with methods:
  - `get_card(dbf_id: int) -> Optional[CardInfo]`
  - `find_card_by_name(name: str) -> Optional[int]` (returns DBF ID)
  - `is_legal_in_format(dbf_id: int, format: FormatType) -> bool`
- Define `CardInfo` dataclass with fields: `dbf_id`, `name`, `rarity`, `card_set`, `collectible`

**Update**: `Deck` class
- Add optional `card_db: Optional[CardDatabase]` parameter to `__init__`
- Add method `validate(self) -> List[str]` that returns list of rule violations
- Add method `get_card_names(self) -> List[Tuple[str, int]]` that converts DBF IDs to names

### 4. Fix Type Hints
**Location**: Line 92
- Change `def parse_deckstring(deckstring) -> (Tuple[CardIncludeList, CardList, FormatType, SideboardList]):`
- To: `def parse_deckstring(deckstring: str) -> Tuple[CardIncludeList, CardList, FormatType, SideboardList]:`

**Location**: Line 158
- Change `cards: CardIncludeList = []` typing to be consistent (already correct)

### 5. Add Comprehensive Tests
**New file**: `test_deckstring.py`
- Test valid deckstrings from each format (Standard, Wild, Classic, Twist)
- Test edge cases: empty deck, 30 same cards, max sideboards
- Test error cases: invalid base64, wrong version, truncated data, negative counts
- Test round-trip: `parse_deckstring(write_deckstring(...))` preserves data
- Use property-based testing (Hypothesis) to generate random valid decks

### 6. Relax Hero Count Restriction
**Location**: Line 208 in `write_deckstring`
- Change `if len(heroes) != 1:` to `if len(heroes) < 1:`
- Update error message: `"Deck must have at least one hero, got %i"`
- Add validation: `if len(heroes) > 10: raise ValueError("Too many heroes")`

### 7. Add Debug Logging
**Location**: Top of file
- `import logging; logger = logging.getLogger(__name__)`

**Location**: Throughout `parse_deckstring`
- After line 112: `logger.debug(f"Parsing deckstring version {version}, format {format}")`
- After line 126: `logger.debug(f"Parsed {num_heroes} heroes: {heroes}")`
- After line 156: `logger.debug(f"Parsed {len(cards)} cards")`
- After line 175: `logger.debug(f"Parsed {len(sideboards)} sideboard cards")`

### 8. Add Docstrings
**Location**: Each public function and class
- Follow Google or NumPy docstring style
- Example for `parse_deckstring`:
```python
"""
Decode a Hearthstone deckstring into its components.

Args:
    deckstring: Base64-encoded deck string from the game client

Returns:
    Tuple containing:
        - cards: List of (dbf_id, count) tuples
        - heroes: List of hero card DBF IDs  
        - format: Game format enum value
        - sideboards: List of (dbf_id, count, owner_dbf_id) tuples

Raises:
    ValueError: If deckstring is malformed or unsupported version
    EOFError: If deckstring is truncated
"""
```

### 9. Add Round-Trip Verification Method
**Location**: `Deck` class
```python
def verify_round_trip(self) -> bool:
    """Encode deck to string and decode back, verify equality."""
    deckstring = self.as_deckstring
    decoded = Deck.from_deckstring(deckstring)
    return (
        sorted(self.cards) == sorted(decoded.cards) and
        sorted(self.heroes) == sorted(decoded.heroes) and
        self.format == decoded.format and
        sorted(self.sideboards) == sorted(decoded.sideboards)
    )
```

### 10. Make Sorting Configurable
**Location**: `Deck` class methods
- Add parameter `sort: bool = True` to `get_dbf_id_list()` and `get_sideboard_dbf_id_list()`
- Only apply sorting if `sort=True`, otherwise return in original order
- Useful for preserving user's card order in deck builders