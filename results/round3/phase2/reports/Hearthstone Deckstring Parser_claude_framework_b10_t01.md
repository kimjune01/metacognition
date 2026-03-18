# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Hearthstone deckstring format, a base64-encoded binary protocol for sharing deck configurations. Working capabilities:

1. **Varint encoding/decoding** - Variable-length integer serialization for compact binary representation
2. **Deckstring parsing** - Decodes base64 deckstrings into structured data (cards, heroes, format, sideboards)
3. **Deckstring writing** - Encodes deck data back into the official format
4. **Card organization** - Trisorts cards by count (1x, 2x, n×) for format optimization
5. **Sideboard support** - Handles the newer sideboard mechanic with owner tracking
6. **Format type tracking** - Records deck format (Standard, Wild, etc.)
7. **Object-oriented interface** - `Deck` class with `from_deckstring()` and `as_deckstring` property
8. **Sorting utilities** - `get_dbf_id_list()` and `get_sideboard_dbf_id_list()` for normalized output

The code correctly handles the binary protocol including header (version, format), heroes section, cards section (with count-based bucketing), and optional sideboards section.

## Triage

### Critical (prevents production use)
1. **No validation** - Accepts malformed input silently or crashes ungracefully
2. **No error context** - Generic exceptions don't identify which card/field failed
3. **Bytes/string confusion** - `data.read(1) != b"\0"` works but `== ""` string check in varint reader is wrong for binary streams

### High (limits utility)
4. **No card database integration** - Returns raw DBF IDs with no way to resolve to card names
5. **No deck validation rules** - Doesn't enforce Hearthstone deck construction rules (30 cards, 2-per-card limit except legendaries, class restrictions)
6. **Incomplete type hints** - `IO` is too generic (should be `IO[bytes]`), missing return type on `__init__`
7. **No round-trip testing** - Can't verify encode(decode(x)) == x

### Medium (quality/maintainability)
8. **Magic numbers** - `0x7f`, `0x80` lack explanation; format byte meanings undocumented
9. **Mutation anti-pattern** - `Deck.__init__()` creates mutable default lists
10. **Inconsistent sorting** - Cards sorted by ID, sideboards by owner then ID - no clear rationale
11. **No logging** - Silent processing makes debugging difficult

### Low (nice-to-have)
12. **No string representation** - `print(deck)` shows object address, not human-readable deck
13. **No deck statistics** - Total cards, dust cost, mana curve analysis
14. **No comparison operators** - Can't check `deck1 == deck2`

## Plan

### 1. Fix varint reader EOF handling
**File**: Line 19, `_read_varint()` function  
**Change**: Replace `if c == "":` with `if not c:` or `if len(c) == 0:`  
**Why**: Binary streams return `b''` (empty bytes), not empty string

### 2. Add input validation wrapper
**New function**: `_validate_deckstring(deckstring: str) -> None`  
**Location**: Before `base64.b64decode()` in `parse_deckstring()`  
**Checks**:
- String is not empty
- Contains only valid base64 characters
- Length is reasonable (< 10KB)
- Catches `base64.binascii.Error` and reraises as `ValueError("Invalid base64")`

### 3. Add deck construction validation
**New method**: `Deck.validate(card_db: Optional[dict] = None) -> List[str]`  
**Returns**: List of validation errors (empty if valid)  
**Checks**:
- Exactly 30 cards (sum of counts)
- No more than 2 of any card (except legendaries if card_db provided)
- All cards from same class or neutral (if card_db provided)
- Format-legal cards (if card_db provided)

### 4. Improve type hints
**Changes**:
- `IO` → `IO[bytes]` everywhere
- Add `-> None` to `Deck.__init__()`
- Change `CardList = List[int]` → `CardList = Sequence[int]` for immutability documentation
- Add generic types: `trisort_cards(cards: Sequence[tuple])` → `trisort_cards(cards: Sequence[Union[Tuple[int, int], Tuple[int, int, int]]])`

### 5. Add error context
**Pattern**: Wrap all `_read_varint()` calls in try-except  
**Example**:
```python
try:
    card_id = _read_varint(data)
except EOFError as e:
    raise ValueError(f"Truncated deckstring at card {i+1} of {num_cards_x1}") from e
```
**Locations**: All loops reading cards, heroes, sideboards

### 6. Fix mutable default
**Line 38**: `def __init__(self):`  
**Current**: Lists initialized as class attributes  
**Fix**: Already correct (lists assigned in `__init__` body) - no change needed (this is actually not a bug on review)

### 7. Add round-trip test
**New method**: `Deck.verify_round_trip(self) -> bool`  
**Logic**:
```python
reconstructed = Deck.from_deckstring(self.as_deckstring)
return (
    self.cards == reconstructed.cards and
    self.heroes == reconstructed.heroes and
    self.format == reconstructed.format and
    self.sideboards == reconstructed.sideboards
)
```

### 8. Document protocol format
**Add module docstring** with format specification:
```python
"""
Blizzard Deckstring format:

Byte 0: Reserved (0x00)
Varint: Version (currently 1)
Varint: Format type (1=Wild, 2=Standard, etc.)
Varint: Number of heroes
  [Varint: Hero DBF ID] × num_heroes
Varint: Number of 1-count cards
  [Varint: Card DBF ID] × count
Varint: Number of 2-count cards
  [Varint: Card DBF ID] × count
Varint: Number of n-count cards
  [Varint: Card DBF ID, Varint: Count] × count
Byte: Has sideboards (0x00 or 0x01)
If has sideboards:
  [Same structure as cards, but with extra Varint for owner DBF ID]
"""
```

### 9. Add `__repr__` and `__str__`
**Location**: `Deck` class  
**Implementation**:
```python
def __repr__(self) -> str:
    return f"Deck(cards={len(self.cards)}, heroes={self.heroes}, format={self.format.name})"

def __str__(self) -> str:
    lines = [f"Format: {self.format.name}", f"Hero: {self.heroes[0]}"]
    lines.append(f"Cards ({sum(c[1] for c in self.cards)}):")
    for dbf_id, count in sorted(self.cards):
        lines.append(f"  {count}× {dbf_id}")
    return "\n".join(lines)
```

### 10. Add comparison operators
**Location**: `Deck` class  
**Methods**: `__eq__`, `__hash__`  
**Implementation**:
```python
def __eq__(self, other) -> bool:
    if not isinstance(other, Deck):
        return NotImplemented
    return (
        self.cards == other.cards and
        self.heroes == other.heroes and
        self.format == other.format and
        self.sideboards == other.sideboards
    )

def __hash__(self) -> int:
    return hash((tuple(self.cards), tuple(self.heroes), self.format, tuple(self.sideboards)))
```

### 11. Add optional logging
**Pattern**: Use `logging` module  
**Add at module level**:
```python
import logging
logger = logging.getLogger(__name__)
```
**Key points to log** (at DEBUG level):
- "Decoding deckstring version {version}, format {format}"
- "Read {num_heroes} heroes: {heroes}"
- "Read {total} cards: {num_x1} singles, {num_x2} pairs, {num_xn} other"
- "Read {total} sideboard cards"