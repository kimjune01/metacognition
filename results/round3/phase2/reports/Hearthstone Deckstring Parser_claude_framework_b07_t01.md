# Diagnostic Report: Hearthstone Deckstring Codec

## Observations

This system implements Blizzard's deckstring format for encoding and decoding Hearthstone deck configurations. Current working capabilities:

1. **Bidirectional codec**: Parses deckstrings to structured data and serializes structured data back to deckstrings
2. **Base64 encoding/decoding**: Handles the outer transport layer
3. **Varint compression**: Implements variable-length integer encoding for space efficiency
4. **Format version handling**: Checks for version 1 deckstrings
5. **Multi-hero support**: Reads/writes hero lists (though enforces single-hero constraint on write)
6. **Card deduplication**: Groups cards by count (1x, 2x, n×) to minimize encoded size
7. **Sideboard support**: Reads and writes sideboard cards with owner associations (for game modes like Duels)
8. **Format type tracking**: Preserves game format (Standard, Wild, Classic, etc.)
9. **Deck object abstraction**: Provides a `Deck` class with convenience methods

## Triage

### Critical gaps (blocks production use):

1. **No input validation**: Malformed deckstrings or invalid card data can cause crashes
2. **No error context**: Failures during parsing provide no position/offset information
3. **Silent truncation**: Unused bytes at end of deckstring are ignored without warning
4. **Type safety holes**: Uses raw tuples instead of structured types; easy to swap arguments

### Important gaps (degrade robustness):

5. **No logging**: Debugging production issues requires adding print statements
6. **Hardcoded constraints**: Single-hero limit is enforced inconsistently (read accepts N, write requires 1)
7. **No round-trip testing**: Code has no self-validation that encode(decode(x)) == x
8. **Missing documentation**: Function contracts unclear (what happens with empty decks? duplicate cards?)

### Nice-to-have improvements:

9. **No streaming support**: Must load entire deckstring into memory
10. **Inefficient sorting**: Sorts card lists multiple times during encoding
11. **No human-readable export**: Can't print deck as card names without external database
12. **No deck validation**: Accepts invalid decks (31 cards, 3× legendary, wrong format)

## Plan

### 1. Input validation (critical)

**File**: Add to both `parse_deckstring` and `write_deckstring`

**Changes**:
- `parse_deckstring:70-85`: After reading each card section, validate `card_id > 0` and `count > 0`
- `parse_deckstring:54`: After heroes section, validate `num_heroes > 0` and all `hero_id > 0`
- `write_deckstring:124`: Before encoding, validate no duplicate card IDs in main deck
- `write_deckstring:127`: Before encoding, validate no duplicate (card_id, owner) pairs in sideboards
- Add parameter validation: `if not deckstring or not isinstance(deckstring, str): raise ValueError`

### 2. Error context (critical)

**File**: Modify `_read_varint` and add wrapper

**Changes**:
- `_read_varint:19`: Add optional `context: str` parameter, include in EOFError message
- `parse_deckstring:45-90`: Wrap each `_read_varint` call with context: `_read_varint(data, context="num_heroes")`
- Create custom exception class:
  ```python
  class DeckstringParseError(ValueError):
      def __init__(self, msg: str, offset: int):
          super().__init__(f"{msg} at byte offset {offset}")
          self.offset = offset
  ```
- Track `data.tell()` position and include in all exceptions

### 3. Truncation detection (critical)

**File**: `parse_deckstring`

**Changes**:
- `parse_deckstring:104`: After parsing, check `remaining = len(decoded) - data.tell()`
- If `remaining > 0`, raise `DeckstringParseError(f"Deckstring has {remaining} unexpected trailing bytes", data.tell())`
- Make this configurable: add `strict: bool = True` parameter to allow legacy deckstrings

### 4. Type safety (critical)

**File**: Create new dataclasses at top of file

**Changes**:
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class CardEntry:
    dbf_id: int
    count: int
    
    def __post_init__(self):
        if self.count < 1: raise ValueError(f"Invalid count {self.count}")

@dataclass(frozen=True)
class SideboardEntry:
    dbf_id: int
    count: int
    owner_dbf_id: int
```
- Replace `CardIncludeList = List[Tuple[int, int]]` with `List[CardEntry]`
- Replace `SideboardList = List[Tuple[int, int, int]]` with `List[SideboardEntry]`
- Update `trisort_cards` to accept and return these types
- Update all tuple unpacking to use attribute access

### 5. Logging (important)

**File**: Add at module level

**Changes**:
- Add `import logging` and `logger = logging.getLogger(__name__)`
- `parse_deckstring:50`: Log `logger.debug(f"Parsing deckstring version {version}, format {format}")`
- `parse_deckstring:104`: Log `logger.debug(f"Parsed deck: {len(cards)} cards, {len(sideboards)} sideboard cards")`
- `write_deckstring:160`: Log `logger.debug(f"Encoded deckstring: {len(cards)} cards, {len(heroes)} heroes")`

### 6. Consistent hero handling (important)

**File**: `write_deckstring`

**Changes**:
- `write_deckstring:118-120`: Remove the `if len(heroes) != 1` check
- Replace with: `if not 1 <= len(heroes) <= 10: raise ValueError(f"Hero count must be 1-10, got {len(heroes)}")`
- Document that multi-hero is forward-compatible but may not work in all game modes

### 7. Round-trip testing (important)

**File**: Create new `test_deckstring.py`

**Changes**:
```python
def test_roundtrip(deckstring: str):
    cards, heroes, fmt, sideboards = parse_deckstring(deckstring)
    reconstructed = write_deckstring(cards, heroes, fmt, sideboards)
    assert reconstructed == deckstring, f"Round-trip failed: {deckstring} != {reconstructed}"
```
- Add property-based tests with Hypothesis to generate random valid decks
- Add regression tests for known deckstrings from each format

### 8. Documentation (important)

**File**: Add docstrings to all functions

**Changes**:
- `parse_deckstring:41`: Add docstring describing return tuple, exceptions, example usage
- `write_deckstring:110`: Document parameter constraints (heroes length, card count > 0)
- `Deck` class: Add class docstring with usage example showing `.from_deckstring()` and `.as_deckstring`
- Add module-level docstring explaining deckstring format spec and linking to Blizzard documentation

### 9. Streaming support (nice-to-have)

**File**: Not needed for most use cases

**Rationale**: Deckstrings are <1KB; memory overhead is negligible. Skip unless processing millions of decks.

### 10. Sorting efficiency (nice-to-have)

**File**: `write_deckstring`

**Changes**:
- `write_deckstring:138-145`: The input `cards` is already sorted before calling `trisort_cards`, but then we sort again inside
- Modify `trisort_cards` to accept `presorted: bool` parameter
- If presorted, use single-pass bucketing without re-sorting

### 11. Human-readable export (nice-to-have)

**File**: Add method to `Deck` class

**Changes**:
```python
def to_decklist(self, card_db: Dict[int, str]) -> str:
    """Returns a human-readable decklist given a card database mapping DBF ID → name."""
    lines = ["# " + card_db.get(h, f"Unknown({h})") for h in self.heroes]
    for dbf_id, count in self.cards:
        name = card_db.get(dbf_id, f"Unknown({dbf_id})")
        lines.append(f"{count}x {name}")
    return "\n".join(lines)
```
- Leave card database loading to the caller (HearthstoneJSON, HSReplay API, etc.)

### 12. Deck validation (nice-to-have)

**File**: Add optional validator to `Deck` class

**Changes**:
```python
def validate(self, rules: "DeckRules") -> List[str]:
    """Returns list of validation errors (empty if valid)."""
    errors = []
    total = sum(count for _, count in self.cards)
    if total != rules.deck_size:
        errors.append(f"Deck has {total} cards, expected {rules.deck_size}")
    # Check rarity limits, format legality, etc.
    return errors
```
- Make this opt-in; parsing should accept any structurally valid deckstring even if it violates game rules
- Define `DeckRules` dataclass with format-specific constraints (Standard 30-card, Arena unlimited, etc.)

---

**Priority order**: Implement 1-4 before any production deployment (data corruption risks), then 5-8 for maintainability, then 9-12 as user needs dictate.