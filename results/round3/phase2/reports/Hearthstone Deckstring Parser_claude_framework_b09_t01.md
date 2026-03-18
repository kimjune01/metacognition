# Diagnostic Report: Hearthstone Deckstring Codec

## Observations

This system implements the Blizzard Deckstring format for Hearthstone deck encoding/decoding. Current working capabilities:

1. **Base64 decoding** of deckstrings into structured card lists
2. **Varint encoding/decoding** for compact integer representation
3. **Card count trisort** - groups cards by count (1x, 2x, n×) for efficient encoding
4. **Hero ID storage** - records which hero(s) the deck uses
5. **Format type tracking** - stores Standard/Wild/other format metadata via `FormatType` enum
6. **Sideboard support** - parses and writes sideboard cards (card_id, count, owner)
7. **Round-trip encoding** - can parse a deckstring, modify it via `Deck` class, and re-encode
8. **Sorted output** - maintains deterministic card ordering for consistent deckstrings

The codec correctly handles:
- Version header (currently v1)
- Multiple card count buckets (optimization for 1x/2x cards)
- Optional sideboard section (marker byte `\0` or `\1`)
- Varint streaming for arbitrary-sized integers

## Triage

### Critical gaps

1. **No error recovery** - Malformed deckstrings raise generic exceptions (`ValueError`, `EOFError`) with minimal context
2. **Hardcoded hero count constraint** - `write_deckstring` enforces exactly 1 hero; multi-hero formats fail
3. **No validation** - No checks for invalid card IDs, negative counts, duplicate cards, or deck size limits

### Important gaps

4. **Missing type hints in key functions** - `parse_deckstring` and `write_deckstring` use tuple syntax in docstrings instead of proper `TypeAlias` declarations
5. **No logging** - Silent failures during parsing make debugging production issues difficult
6. **No performance metrics** - No way to detect slow varint decoding on malicious input
7. **Incomplete `FormatType` enum** - References external enum without defining fallback behavior

### Nice-to-have gaps

8. **No human-readable export** - Can't generate a text card list (e.g., "2× Fireball\n1× Archmage Antonidas")
9. **No deck validation** - Doesn't verify Standard/Wild legality, class restrictions, or duplicate legendaries
10. **Limited sideboard semantics** - `sideboard_owner` is an opaque integer; no mapping to card names/meanings

## Plan

### 1. Error recovery (Critical)
**Change:** Wrap parsing logic in descriptive exception types.
```python
class DeckstringError(Exception): pass
class InvalidHeaderError(DeckstringError): pass
class UnsupportedVersionError(DeckstringError): pass

# In parse_deckstring:
if data.read(1) != b"\0":
    raise InvalidHeaderError(f"Expected null header, got {data.read(1)!r}")

if version != DECKSTRING_VERSION:
    raise UnsupportedVersionError(
        f"Version {version} not supported (expected {DECKSTRING_VERSION})"
    )
```
**Impact:** Clients can catch specific errors and handle version mismatches gracefully.

---

### 2. Multi-hero support (Critical)
**Change:** Remove the hardcoded `len(heroes) != 1` check in `write_deckstring`.
```python
# Before:
if len(heroes) != 1:
    raise ValueError("Unsupported hero count %i" % (len(heroes)))

# After:
if len(heroes) == 0:
    raise ValueError("Deck must have at least one hero")
# (Allow any positive hero count)
```
**Impact:** Enables Tavern Brawl, Duels, and future multi-hero formats.

---

### 3. Input validation (Critical)
**Change:** Add validation functions called during parsing and encoding.
```python
def _validate_card_list(cards: CardIncludeList):
    seen = set()
    for card_id, count in cards:
        if card_id <= 0:
            raise ValueError(f"Invalid card ID {card_id}")
        if count <= 0:
            raise ValueError(f"Invalid count {count} for card {card_id}")
        if card_id in seen:
            raise ValueError(f"Duplicate card {card_id}")
        seen.add(card_id)

# Call in parse_deckstring after building card list
_validate_card_list(cards)
```
**Impact:** Prevents corrupt data from entering the system; fails fast on bad input.

---

### 4. Type aliases (Important)
**Change:** Define type aliases at module level for clarity.
```python
from typing import TypeAlias

CardList: TypeAlias = List[int]
CardIncludeList: TypeAlias = List[Tuple[int, int]]  # (dbf_id, count)
SideboardList: TypeAlias = List[Tuple[int, int, int]]  # (dbf_id, count, owner)

# Update function signatures:
def parse_deckstring(deckstring: str) -> Tuple[
    CardIncludeList, CardList, FormatType, SideboardList
]: ...
```
**Impact:** Improves IDE autocomplete and catches type errors during development.

---

### 5. Logging (Important)
**Change:** Add structured logging at key decision points.
```python
import logging

logger = logging.getLogger(__name__)

# In parse_deckstring:
logger.debug(f"Parsing deckstring version {version}, format {format}")
logger.debug(f"Found {num_heroes} heroes, {len(cards)} cards")

# In _read_varint:
if c == "":
    logger.error(f"EOF while reading varint at position {stream.tell()}")
```
**Impact:** Enables post-mortem debugging of production parsing failures.

---

### 6. Performance monitoring (Important)
**Change:** Add limits to varint decoding to prevent DoS.
```python
MAX_VARINT_BYTES = 10  # 64-bit int needs at most 10 bytes

def _read_varint(stream: IO) -> int:
    shift = 0
    result = 0
    bytes_read = 0
    while True:
        bytes_read += 1
        if bytes_read > MAX_VARINT_BYTES:
            raise ValueError("Varint too large (possible attack)")
        # ... rest of logic
```
**Impact:** Prevents malicious deckstrings from hanging the parser.

---

### 7. FormatType fallback (Important)
**Change:** Handle unknown format types gracefully.
```python
try:
    format = FormatType(format)
except ValueError:
    logger.warning(f"Unknown format {format}, defaulting to FT_UNKNOWN")
    format = FormatType.FT_UNKNOWN
```
**Impact:** Allows parsing deckstrings from newer game versions without crashing.

---

### 8. Human-readable export (Nice-to-have)
**Change:** Add a method to `Deck` that generates text output.
```python
# Requires a card database lookup (not provided in this code)
def as_text(self, card_db: dict) -> str:
    """Returns deck as '2× Fireball\\n1× Archmage' format"""
    lines = []
    for card_id, count in self.get_dbf_id_list():
        name = card_db.get(card_id, f"Unknown({card_id})")
        lines.append(f"{count}× {name}")
    return "\n".join(lines)
```
**Impact:** Enables user-facing deck display without external tools.

---

### 9. Deck validation (Nice-to-have)
**Change:** Add optional validation against game rules.
```python
def validate_for_format(self, card_db: dict, format: FormatType) -> List[str]:
    """Returns list of rule violations (empty if legal)"""
    errors = []
    total_cards = sum(count for _, count in self.cards)
    if total_cards != 30:
        errors.append(f"Deck has {total_cards} cards (expected 30)")
    # Check Standard rotation, duplicate legendaries, etc.
    return errors
```
**Impact:** Catches deck-building errors before submitting to game server.

---

### 10. Sideboard semantics (Nice-to-have)
**Change:** Add an enum or dataclass for sideboard owners.
```python
@dataclass
class SideboardCard:
    card_id: int
    count: int
    owner_card_id: int  # The card that "owns" this sideboard entry

# Update SideboardList type:
SideboardList: TypeAlias = List[SideboardCard]
```
**Impact:** Makes sideboard logic self-documenting; easier to validate owner relationships.