# Diagnostic Report: Hearthstone Deckstring Implementation

## Observations

This system implements the Blizzard Deckstring format for Hearthstone deck encoding/decoding. Current working capabilities:

1. **Decoding deckstrings** - Parses base64-encoded deckstrings into structured deck data (cards, heroes, format, sideboards)
2. **Encoding deckstrings** - Serializes deck data back into base64-encoded deckstring format
3. **Varint I/O** - Reads and writes variable-length integers for compact binary representation
4. **Card organization** - Trisorts cards by count (×1, ×2, ×N) for efficient encoding
5. **Sideboard support** - Handles sideboard cards with ownership tracking (likely for game modes like Duels)
6. **Format validation** - Validates and preserves FormatType (Wild, Standard, etc.)
7. **Hero handling** - Encodes/decodes hero cards with validation (currently enforces single hero)
8. **Deck object interface** - Provides OOP wrapper with `Deck` class for convenient manipulation

## Triage

### Critical Gaps

1. **No error recovery** - Malformed deckstrings raise exceptions without graceful degradation
2. **Missing validation logic** - No deck legality checks (card limits, format restrictions, banned cards)
3. **Incomplete hero support** - Code enforces single hero but header suggests multi-hero support was planned
4. **No card database integration** - Works with raw DBF IDs; cannot validate card existence or retrieve metadata

### Important Gaps

5. **Limited format coverage** - `FormatType.FT_UNKNOWN` suggests incomplete enum; may not handle all game formats
6. **No duplicate detection** - Same card could appear in both main deck and counts, creating invalid states
7. **Missing round-trip verification** - No tests confirming encode(decode(x)) == x
8. **No convenience methods** - Cannot easily add/remove cards, count deck size, or filter by properties

### Minor Gaps

9. **Incomplete type hints** - Uses `tuple` instead of `Tuple[int, int]` in sort_key lambdas
10. **No logging** - Silent failures in parsing make debugging difficult
11. **Rigid hero validation** - Hard-coded single-hero requirement prevents multi-hero format support
12. **Missing documentation** - No docstrings explaining deckstring format specification

## Plan

### 1. Error Recovery (Critical)
**Change:** Wrap `parse_deckstring` in try/except blocks at each parsing stage. Return partial results with error details.
```python
def parse_deckstring(deckstring) -> Tuple[CardIncludeList, CardList, FormatType, SideboardList, Optional[str]]:
    try:
        decoded = base64.b64decode(deckstring)
    except Exception as e:
        return ([], [], FormatType.FT_UNKNOWN, [], f"Base64 decode failed: {e}")
    # Similar guards for varint reads, version checks, etc.
```

### 2. Validation Logic (Critical)
**Change:** Add `Deck.validate()` method that checks:
- Card counts ≤ max copies (typically 2, legendaries 1)
- Total deck size matches format requirements (30 for Standard)
- All cards legal in specified format
- Hero class matches card class restrictions

Requires external card database integration (see #4).

### 3. Multi-Hero Support (Critical)
**Change:** Remove hard-coded `if len(heroes) != 1` check in `write_deckstring`. Add `allow_multi_hero: bool` parameter defaulting to `False` for backward compatibility. Update validation to check hero count against format rules.

### 4. Card Database Integration (Critical)
**Change:** Add dependency on Hearthstone card database (HearthstoneJSON or similar). Create `CardDatabase` class with methods:
```python
class CardDatabase:
    def get_card(self, dbf_id: int) -> Optional[Card]
    def is_legal_in_format(self, dbf_id: int, format: FormatType) -> bool
    def get_max_copies(self, dbf_id: int) -> int  # 1 for legendary, 2 otherwise
```

### 5. Format Coverage (Important)
**Change:** Complete `FormatType` enum by cross-referencing with official Hearthstone API. Add variants for:
- `FT_CLASSIC`, `FT_TWIST`, `FT_DUELS`, `FT_ARENA`, `FT_BATTLEGROUNDS` (if applicable)
- Update parsing to handle unknown future formats gracefully

### 6. Duplicate Detection (Important)
**Change:** In `Deck.__init__`, add validation that checks for duplicate card IDs:
```python
def add_card(self, dbf_id: int, count: int = 1):
    existing = [c for c in self.cards if c[0] == dbf_id]
    if existing:
        raise ValueError(f"Card {dbf_id} already in deck")
    self.cards.append((dbf_id, count))
```

### 7. Round-Trip Verification (Important)
**Change:** Add `tests/test_deckstring.py` with:
```python
def test_roundtrip(known_deckstrings):
    for ds in known_deckstrings:
        deck = Deck.from_deckstring(ds)
        assert deck.as_deckstring == ds
```
Use real deckstrings from Hearthstone community sites as test fixtures.

### 8. Convenience Methods (Important)
**Change:** Add to `Deck` class:
```python
def add_card(self, dbf_id: int, count: int = 1)
def remove_card(self, dbf_id: int) -> bool
def get_deck_size(self) -> int
def get_cards_by_cost(self, cost: int) -> CardIncludeList  # Requires CardDatabase
def get_class(self) -> str  # Infer from hero
```

### 9. Type Hints (Minor)
**Change:** Update lambda type hints:
```python
sort_key: Callable[[Tuple[int, int]], int] = lambda x: x[0]
sb_sort_key: Callable[[Tuple[int, int, int]], Tuple[int, int]] = lambda x: (x[2], x[0])
```

### 10. Logging (Minor)
**Change:** Add `import logging` and emit warnings:
```python
if version != DECKSTRING_VERSION:
    logging.warning(f"Deckstring version {version} may not be fully supported")
```

### 11. Flexible Hero Validation (Minor)
**Change:** Replace hard error with configurable validation:
```python
def write_deckstring(..., strict: bool = True):
    if strict and len(heroes) != 1:
        raise ValueError(...)
    elif len(heroes) == 0:
        raise ValueError("At least one hero required")
```

### 12. Documentation (Minor)
**Change:** Add module docstring explaining deckstring format structure:
```python
"""
Hearthstone Deckstring format (version 1):
- Header: null byte + version varint + format varint
- Heroes: count varint + N hero DBF IDs
- Cards: grouped by count (×1, ×2, ×N) for compression
- Sideboards: optional, same structure as cards but with owner IDs
- Encoding: base64 of binary varint stream
"""
```
Add docstrings to `Deck`, `parse_deckstring`, `write_deckstring` explaining parameters and return values.