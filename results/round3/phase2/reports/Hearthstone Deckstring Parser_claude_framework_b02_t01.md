# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard deckstring format for Hearthstone decks. Working capabilities:

1. **Binary encoding/decoding**: Reads and writes variable-length integers (varint) to/from byte streams
2. **Deckstring parsing**: Decodes base64-encoded deckstrings into structured deck data
3. **Deckstring generation**: Encodes deck data (cards, heroes, format, sideboards) into base64 deckstrings
4. **Card organization**: Trisorts cards by count (1x, 2x, n×) for efficient encoding
5. **Sideboard support**: Parses and writes sideboard cards with owner references
6. **Format type handling**: Preserves deck format (Wild, Standard, etc.)
7. **OOP interface**: Provides `Deck` class with `from_deckstring()` factory and `as_deckstring` property
8. **Data access**: Exposes sorted card and sideboard lists via getter methods

## Triage

### Critical gaps

1. **No error recovery**: Parser fails hard on malformed input with generic exceptions
2. **No validation**: Accepts impossible deck states (0 heroes, negative counts, invalid format combinations)
3. **No documentation**: Zero docstrings explaining deckstring format, usage, or edge cases

### Important gaps

4. **Type hints incomplete**: `stream: IO` should be `IO[bytes]`; return types missing on many functions
5. **No logging**: Silent failures make debugging production issues impossible
6. **No tests**: Zero unit tests for encoding/decoding round-trips, edge cases, or error paths
7. **Hero count hardcoded**: `if len(heroes) != 1` blocks multi-hero formats that may exist

### Nice-to-have gaps

8. **No card name support**: Only works with dbf_ids; users often work with card names
9. **No deck validation rules**: Doesn't check 30-card limit, 2-copy limit (except legendaries), class restrictions
10. **No backward compatibility**: Version check rejects future versions instead of attempting best-effort parsing
11. **Performance**: Repeated sorting on every getter call; no caching
12. **No CLI/examples**: No way to test the code without writing Python

## Plan

### 1. Error recovery (Critical)

**Change**: Wrap parsing in try/except blocks with specific error types
```python
class DeckstringError(Exception): pass
class InvalidFormatError(DeckstringError): pass
class UnsupportedVersionError(DeckstringError): pass

def parse_deckstring(...):
    try:
        decoded = base64.b64decode(deckstring)
    except Exception as e:
        raise InvalidFormatError(f"Invalid base64: {e}")
    
    try:
        # parsing logic
    except EOFError:
        raise InvalidFormatError("Truncated deckstring")
    except struct.error:
        raise InvalidFormatError("Corrupt varint encoding")
```

### 2. Validation (Critical)

**Change**: Add validation methods to `Deck` class
```python
def validate(self) -> List[str]:
    """Returns list of validation errors, empty if valid"""
    errors = []
    if len(self.heroes) == 0:
        errors.append("Deck must have at least one hero")
    if len(self.heroes) > 1:
        errors.append("Multi-hero decks not yet supported")
    if not self.cards:
        errors.append("Deck must contain cards")
    if self.format == FormatType.FT_UNKNOWN:
        errors.append("Deck format must be specified")
    return errors
```

Call `validate()` in `from_deckstring()` and optionally in `as_deckstring` property.

### 3. Documentation (Critical)

**Change**: Add module docstring and docstrings to all public functions/classes
```python
def parse_deckstring(deckstring: str) -> Tuple[...]:
    """Parse a Hearthstone deckstring into structured components.
    
    Args:
        deckstring: Base64-encoded Blizzard deckstring format
        
    Returns:
        Tuple of (cards, heroes, format, sideboards) where:
        - cards: List of (dbf_id, count) tuples
        - heroes: List of hero dbf_ids
        - format: FormatType enum value
        - sideboards: List of (dbf_id, count, owner_dbf_id) tuples
        
    Raises:
        InvalidFormatError: If deckstring is malformed
        UnsupportedVersionError: If version != 1
    """
```

### 4. Type hints (Important)

**Change**: Fix IO types and add missing return type hints
```python
from typing import IO, BinaryIO

def _read_varint(stream: BinaryIO) -> int: ...
def _write_varint(stream: BinaryIO, i: int) -> int: ...

def get_dbf_id_list(self) -> CardIncludeList: ...
def get_sideboard_dbf_id_list(self) -> SideboardList: ...
```

### 5. Logging (Important)

**Change**: Add logging module with debug output
```python
import logging
logger = logging.getLogger(__name__)

def parse_deckstring(deckstring):
    logger.debug(f"Parsing deckstring length={len(deckstring)}")
    # ... existing code ...
    logger.debug(f"Parsed {len(cards)} cards, {len(heroes)} heroes")
```

### 6. Tests (Important)

**Change**: Create `tests/test_deckstring.py` with pytest
```python
def test_roundtrip():
    original = "AAECAf0E..."  # known good deckstring
    deck = Deck.from_deckstring(original)
    assert deck.as_deckstring == original

def test_invalid_base64():
    with pytest.raises(InvalidFormatError):
        Deck.from_deckstring("not-base64!!!")

def test_truncated_data():
    with pytest.raises(InvalidFormatError):
        Deck.from_deckstring("AAECA==")  # valid base64 but truncated
```

### 7. Hero count flexibility (Important)

**Change**: Remove hardcoded check or make it configurable
```python
MAX_HEROES = 1  # module constant, can be overridden for future formats

def write_deckstring(..., max_heroes: int = MAX_HEROES):
    if len(heroes) > max_heroes:
        raise ValueError(f"Too many heroes: {len(heroes)} > {max_heroes}")
    # existing logic
```

### 8. Card name resolution (Nice-to-have)

**Change**: Add optional card database integration
```python
class Deck:
    def __init__(self, card_db: Optional['CardDatabase'] = None):
        self.card_db = card_db
    
    def add_card_by_name(self, name: str, count: int = 1):
        if not self.card_db:
            raise ValueError("Card database required for name lookup")
        dbf_id = self.card_db.get_id(name)
        self.cards.append((dbf_id, count))
```

### 9. Deck validation rules (Nice-to-have)

**Change**: Add game rules validation
```python
def validate_game_rules(self, card_db: 'CardDatabase') -> List[str]:
    errors = []
    total = sum(count for _, count in self.cards)
    if total != 30:
        errors.append(f"Deck must have 30 cards, has {total}")
    
    for dbf_id, count in self.cards:
        card = card_db.get(dbf_id)
        if card.rarity != 'LEGENDARY' and count > 2:
            errors.append(f"Non-legendary {card.name} has {count} copies")
    return errors
```

### 10. Version compatibility (Nice-to-have)

**Change**: Support forward compatibility with version check
```python
SUPPORTED_VERSIONS = {1}
COMPATIBLE_VERSIONS = {1, 2}  # versions we can partially parse

version = _read_varint(data)
if version not in COMPATIBLE_VERSIONS:
    raise UnsupportedVersionError(f"Version {version} not supported")
if version not in SUPPORTED_VERSIONS:
    logger.warning(f"Version {version} partially supported")
```

### 11. Performance (Nice-to-have)

**Change**: Cache sorted results
```python
class Deck:
    def __init__(self):
        # existing fields
        self._sorted_cards_cache = None
        self._sorted_sideboards_cache = None
    
    def get_dbf_id_list(self) -> CardIncludeList:
        if self._sorted_cards_cache is None:
            self._sorted_cards_cache = sorted(self.cards, key=lambda x: x[0])
        return self._sorted_cards_cache
```

Invalidate cache when `self.cards` is modified.

### 12. CLI/examples (Nice-to-have)

**Change**: Add `__main__.py` for testing
```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m deckstrings <deckstring>")
        sys.exit(1)
    
    deck = Deck.from_deckstring(sys.argv[1])
    print(f"Format: {deck.format.name}")
    print(f"Heroes: {deck.heroes}")
    print(f"Cards: {len(deck.cards)}")
    for dbf_id, count in deck.get_dbf_id_list():
        print(f"  {dbf_id} x{count}")
```