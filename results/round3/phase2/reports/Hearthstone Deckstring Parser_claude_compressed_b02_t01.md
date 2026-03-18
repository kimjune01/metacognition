# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard deckstring format for Hearthstone deck encoding/decoding. Current working capabilities:

1. **Perceive**: Accepts base64-encoded deckstrings via `from_deckstring()` and decodes them into binary streams
2. **Cache**: Parses binary data into structured `Deck` objects with cards, heroes, format type, and sideboards stored as typed lists
3. **Filter**: Validates deckstring format (checks magic byte `\0`, version number), rejects unsupported versions and unknown format types
4. **Attend**: Provides sorted accessors (`get_dbf_id_list()`, `get_sideboard_dbf_id_list()`) that prioritize by card ID
5. **Remember**: N/A - this is a pure encoder/decoder library with no persistence layer

The codec is functionally complete for its domain: bidirectional conversion between deckstrings and structured data, with varint compression and support for the sideboards extension.

## Triage

### Critical gaps (blocking production use):

1. **Error handling is minimal** - EOF during varint read raises generic `EOFError`, but malformed data (truncated streams, out-of-bounds counts) can cause silent corruption or crashes
2. **No validation of semantic constraints** - accepts decks with 0 heroes, 100 copies of a card, or invalid card IDs without complaint
3. **No logging or debugging support** - when parsing fails, users get exceptions with no context about where in the stream or which field caused the problem

### Important gaps (reduce usability):

4. **No bulk operations** - can't compare decks, diff them, or batch-process collections
5. **Rigid hero requirement** - hardcoded `len(heroes) != 1` check fails for multi-hero formats or spectator decks
6. **Type hints incomplete** - return types use comments instead of annotations; no Protocol or ABC for extensibility

### Minor gaps (polish):

7. **No pretty-printing** - `Deck.__repr__()` returns memory address instead of human-readable summary
8. **Inconsistent naming** - `CardIncludeList` vs `SideboardList` conventions; `trisort_cards` returns tuple instead of named struct
9. **No examples or quickstart** - module docstring is a single line

## Plan

### 1. Error handling (critical)

**Change**: Wrap `parse_deckstring()` body in try/except and raise custom exceptions with context.

```python
class DeckstringError(ValueError):
    pass

def parse_deckstring(deckstring):
    try:
        decoded = base64.b64decode(deckstring)
    except Exception as e:
        raise DeckstringError(f"Invalid base64: {e}") from e
    
    # Before each _read_varint, check stream length
    # After reading counts, validate they're reasonable (<256)
    # Catch EOFError from varint reads and re-raise with field name
```

Add a `_safe_read_varint(stream, field_name)` wrapper that catches `EOFError` and reports which field failed.

### 2. Semantic validation (critical)

**Change**: Add a `validate()` method to `Deck` and call it in `from_deckstring()` by default (opt-out via flag).

```python
def validate(self, strict=True):
    if len(self.heroes) == 0:
        raise DeckstringError("Deck must have at least one hero")
    
    total_cards = sum(count for _, count in self.cards)
    if strict and total_cards != 30:  # Standard deck size
        raise DeckstringError(f"Expected 30 cards, got {total_cards}")
    
    for cardid, count in self.cards:
        if count > 2 and cardid not in LEGENDARY_EXCEPTIONS:
            # Would need a registry of card rarity
            pass  # Placeholder for "max 2 copies" rule
```

This requires either accepting a card database parameter or punting on rarity checks to the caller.

### 3. Logging and debug context (critical)

**Change**: Add `logging` module support and emit debug statements at parse milestones.

```python
import logging
logger = logging.getLogger(__name__)

def parse_deckstring(deckstring):
    logger.debug(f"Parsing deckstring length={len(deckstring)}")
    # ... after header ...
    logger.debug(f"Parsed header: version={version}, format={format}")
    # ... after each section ...
    logger.debug(f"Parsed {len(cards)} cards, {len(sideboards)} sideboard cards")
```

For failures, log the raw bytes around the failure point (hexdump of last 16 bytes read).

### 4. Bulk operations (important)

**Change**: Add `Deck.__eq__()`, `Deck.diff()`, and module-level `parse_many()`.

```python
def __eq__(self, other):
    return (
        self.format == other.format
        and self.heroes == other.heroes
        and sorted(self.cards) == sorted(other.cards)
        and sorted(self.sideboards) == sorted(other.sideboards)
    )

def diff(self, other):
    # Return (cards_added, cards_removed, sideboards_changed)
    pass
```

### 5. Relax hero requirement (important)

**Change**: Replace hardcoded check with format-specific validation.

```python
HERO_REQUIREMENTS = {
    FormatType.FT_STANDARD: (1, 1),  # (min, max)
    FormatType.FT_WILD: (1, 1),
    FormatType.FT_TAVERN_BRAWL: (1, 2),  # Example: some brawls allow 2
}

def write_deckstring(...):
    min_heroes, max_heroes = HERO_REQUIREMENTS.get(format, (1, 10))
    if not (min_heroes <= len(heroes) <= max_heroes):
        raise ValueError(f"Format {format} requires {min_heroes}-{max_heroes} heroes")
```

### 6. Modernize type hints (important)

**Change**: Convert all comment-style types to proper annotations, add `from __future__ import annotations` for forward refs.

```python
from __future__ import annotations
from typing import List, Tuple, Protocol

class DeckLike(Protocol):
    cards: CardIncludeList
    heroes: CardList
    # ...
```

### 7. Pretty-printing (minor)

**Change**: Add `__repr__()` and `__str__()` methods.

```python
def __repr__(self):
    return f"Deck(format={self.format.name}, heroes={self.heroes}, cards={len(self.cards)})"

def __str__(self):
    lines = [f"Format: {self.format.name}", f"Heroes: {self.heroes}"]
    lines.append(f"Cards ({len(self.cards)}):")
    for cardid, count in sorted(self.cards):
        lines.append(f"  {cardid} x{count}")
    return "\n".join(lines)
```

### 8. Naming consistency (minor)

**Change**: Use dataclasses for `trisort_cards()` return value.

```python
from dataclasses import dataclass

@dataclass
class SortedCards:
    x1: List[tuple]
    x2: List[tuple]
    xn: List[tuple]

def trisort_cards(cards: Sequence[tuple]) -> SortedCards:
    # ... existing logic ...
    return SortedCards(x1=cards_x1, x2=cards_x2, xn=cards_xn)
```

### 9. Documentation (minor)

**Change**: Expand module docstring with quickstart example.

```python
"""
Blizzard Deckstring format support

Example:
    >>> from hearthstone.deckstrings import Deck
    >>> deck = Deck.from_deckstring("AAECAa0GBvYC...")
    >>> print(f"Format: {deck.format}, Cards: {len(deck.cards)}")
    >>> deck.cards.append((12345, 1))  # Add a card
    >>> print(deck.as_deckstring)  # Encode back to string
"""
```

---

**Priority order for implementation**: 1, 2, 3 (errors/validation/logging) can be done in parallel as they touch different code paths. Then 4-6 (features). Finally 7-9 (polish). The system is usable now but unsafe for production until the critical gaps are closed.