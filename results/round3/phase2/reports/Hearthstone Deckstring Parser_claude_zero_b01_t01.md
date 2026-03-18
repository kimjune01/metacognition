# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Deckstring format parser for Hearthstone decks. Current working capabilities:

1. **Binary encoding/decoding** - Reads and writes variable-length integers (varint) following protobuf-style encoding
2. **Deckstring parsing** - Decodes base64-encoded deckstrings into structured data containing:
   - Card lists with counts (optimized storage for 1x, 2x, and N× cards)
   - Hero card IDs
   - Format type (Standard, Wild, etc.)
   - Sideboard cards (with ownership tracking)
3. **Deckstring generation** - Encodes deck data back into base64 deckstring format
4. **Data model** - `Deck` class with factory method, property accessors, and sorted output methods
5. **Tri-sorting optimization** - Separates cards by count (1/2/N) for efficient encoding
6. **Version handling** - Enforces deckstring version 1 format

## Triage

### Critical Gaps

1. **No error handling beyond EOFError and ValueError** - Production code needs comprehensive error recovery
2. **No validation logic** - Deck legality rules aren't enforced (card limits, format restrictions, hero-class matching)
3. **No card database integration** - Works only with numeric IDs; no human-readable card names or metadata
4. **No logging** - Debugging malformed deckstrings or encoding issues is difficult

### Important Gaps

5. **No type safety for card IDs** - Uses raw `int` instead of NewType or domain-specific validation
6. **No deck statistics** - Missing dust cost, mana curve, card type breakdown
7. **No multi-hero support** - Code explicitly rejects `len(heroes) != 1` but Duels/Tavern Brawl may need it
8. **No round-trip testing infrastructure** - Critical for ensuring encode/decode symmetry

### Minor Gaps

9. **No CLI or API interface** - Library-only; no standalone usage
10. **Type hints incomplete** - `IO` is too generic; should be `IO[bytes]`
11. **No documentation** - Missing docstrings for public API
12. **Hardcoded constraints** - Magic numbers (hero count check) should be constants

## Plan

### 1. Error Handling (Critical)
**Changes:**
- Wrap `base64.b64decode()` in try-except for `binascii.Error`
- Add custom exceptions: `InvalidDeckstringError`, `CorruptedDataError`, `UnsupportedVersionError`
- Add length validation before reading varints to prevent infinite loops on malformed data
- Validate card counts are positive and reasonable (e.g., ≤ 255)

**Example:**
```python
class DeckstringError(Exception): pass
class InvalidDeckstringError(DeckstringError): pass

def parse_deckstring(deckstring: str):
    try:
        decoded = base64.b64decode(deckstring, validate=True)
    except (binascii.Error, ValueError) as e:
        raise InvalidDeckstringError(f"Invalid base64: {e}")
    
    if len(decoded) < 3:
        raise InvalidDeckstringError("Deckstring too short")
```

### 2. Validation (Critical)
**Changes:**
- Add `Deck.is_valid(card_db: CardDatabase) -> Tuple[bool, List[str]]` method
- Implement rules: 30-card minimum (Standard/Wild), duplicate legendary check, format-banned cards
- Validate hero-class alignment (e.g., can't have Priest cards with Mage hero)
- Add `strict` parameter to `from_deckstring()` to optionally enforce validation

**Example:**
```python
def validate_deck_size(self) -> bool:
    total = sum(count for _, count in self.cards)
    return total >= 30

def validate_duplicates(self, card_db) -> List[str]:
    errors = []
    for cardid, count in self.cards:
        card = card_db.get(cardid)
        if card.rarity == Rarity.LEGENDARY and count > 1:
            errors.append(f"{card.name} is legendary (max 1)")
    return errors
```

### 3. Card Database Integration (Critical)
**Changes:**
- Create `CardDatabase` interface with `get(dbf_id: int) -> Card` method
- Add `Card` dataclass with fields: `dbf_id`, `name`, `cost`, `rarity`, `card_class`, `format_legality`
- Implement `Deck.to_human_readable() -> str` using card database
- Add `Deck.from_card_names(names: List[str], card_db) -> Deck` factory

**Example:**
```python
@dataclass
class Card:
    dbf_id: int
    name: str
    cost: int
    rarity: Rarity
    card_class: CardClass

def to_human_readable(self, card_db: CardDatabase) -> str:
    lines = []
    for cardid, count in self.cards:
        card = card_db.get(cardid)
        lines.append(f"{count}x {card.name}")
    return "\n".join(lines)
```

### 4. Logging (Critical)
**Changes:**
- Add `import logging` and logger instance: `logger = logging.getLogger(__name__)`
- Log debug messages for varint reads/writes during encode/decode
- Log warnings for unusual deck structures (>30 cards, unknown format types)
- Log info for successful parse with card/hero counts

### 5. Type Safety (Important)
**Changes:**
- Replace `IO` with `IO[bytes]` in varint functions
- Create `DbfId = NewType("DbfId", int)` and use throughout
- Add runtime validation: `def _validate_dbf_id(i: int) -> DbfId: assert i > 0`

### 6. Deck Statistics (Important)
**Changes:**
- Add `Deck.get_statistics(card_db) -> DeckStats` method
- Return dataclass with: `total_dust`, `mana_curve: Dict[int, int]`, `card_types: Dict[CardType, int]`

### 7. Multi-Hero Support (Important)
**Changes:**
- Remove `if len(heroes) != 1: raise ValueError` check
- Add `max_heroes` parameter to `write_deckstring()` with default=1
- Update tests to cover 2-hero and 3-hero scenarios (Duels)

### 8. Round-Trip Testing (Important)
**Changes:**
- Add `tests/test_roundtrip.py` with property-based testing (Hypothesis)
- Generate random valid decks, encode, decode, assert equality
- Test known deckstrings from live game (regression suite)

### 9. CLI Interface (Minor)
**Changes:**
- Create `deckstrings/cli.py` with `click` or `argparse`
- Commands: `decode <deckstring>`, `encode <card_list>`, `validate <deckstring>`
- Add `if __name__ == "__main__"` block

### 10. Documentation (Minor)
**Changes:**
- Add module docstring explaining Blizzard deckstring format with link to spec
- Add docstrings to all public methods following numpy/Google style
- Include examples in `Deck` class docstring

### 11. Type Hints Refinement (Minor)
**Changes:**
- Fix `IO` → `IO[bytes]` throughout
- Add `from __future__ import annotations` for forward references
- Run `mypy --strict` and fix all violations

### 12. Configuration Constants (Minor)
**Changes:**
- Create constants: `MAX_HERO_COUNT = 1`, `MIN_DECK_SIZE = 30`, `MAX_CARD_COUNT = 255`
- Extract magic numbers from conditionals and use named constants
- Add `DeckConstraints` dataclass for format-specific rules