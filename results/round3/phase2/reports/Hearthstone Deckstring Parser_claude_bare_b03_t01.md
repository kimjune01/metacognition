# Diagnostic Report: Hearthstone Deckstring Library

## Observations

This system implements Blizzard's binary deckstring format for Hearthstone deck codes. Current working capabilities:

1. **Decoding deckstrings** - Parses base64-encoded deck codes into structured data containing:
   - Card lists with (dbf_id, count) tuples
   - Hero dbf_ids
   - Format type (Wild/Standard/Classic/Twist)
   - Sideboard cards (for Twist format)

2. **Encoding deckstrings** - Serializes deck data back into base64 deckstring format

3. **Varint I/O** - Implements variable-length integer encoding for compact binary representation

4. **Card sorting optimization** - Groups cards by count (1x, 2x, Nx) to minimize encoding size

5. **Deck object model** - Provides a `Deck` class with convenience methods for:
   - Creating decks from deckstrings
   - Generating deckstrings from deck data
   - Retrieving sorted card/sideboard lists

6. **Version handling** - Supports deckstring version 1 with header validation

7. **Sideboard support** - Full read/write support for sideboard cards with owner tracking

## Triage

### Critical Gaps

1. **No error handling for malformed data** - Parsing untrusted deckstrings can crash with unhelpful errors
2. **Missing validation** - No deck composition rules (30-card limit, max copies per card, format legality)
3. **No card database integration** - Cannot validate card IDs or translate dbf_ids to card names
4. **Empty deck handling unclear** - Behavior with 0 heroes or 0 cards undefined

### Important Gaps

5. **No human-readable representation** - Cannot display decks as card names or export to other formats
6. **Limited deck manipulation API** - Cannot easily add/remove cards, must manipulate lists directly
7. **No duplicate detection** - Adding the same card multiple times creates invalid state
8. **Missing deck metadata** - No support for deck name, author, description, archetype tags
9. **Type hints incomplete** - `IO` type doesn't specify `IO[bytes]`, missing return type for `__init__`

### Nice-to-Have Gaps

10. **No deck comparison/diff utilities** - Cannot compare two decks or detect changes
11. **No cost/rarity/class statistics** - Missing helper methods for deck analysis
12. **No format auto-detection** - Cannot infer format from card pool
13. **Performance not optimized** - Uses `BytesIO` for small buffers where `bytearray` might be faster
14. **No logging/debugging support** - Silent failures make troubleshooting difficult

## Plan

### 1. Add comprehensive error handling
```python
# In parse_deckstring()
try:
    decoded = base64.b64decode(deckstring)
except Exception as e:
    raise ValueError(f"Invalid base64 encoding: {e}") from e

# In _read_varint()
if c == b"":  # Fix: comparing bytes correctly
    raise EOFError(f"Unexpected EOF at position {stream.tell()}")

# Add length validation after parsing
if len(cards) == 0:
    raise ValueError("Deck must contain at least one card")
if len(heroes) == 0:
    raise ValueError("Deck must have at least one hero")
```

### 2. Add deck validation
```python
# Add to Deck class
def validate(self, allow_wild: bool = True) -> List[str]:
    """Returns list of validation errors, empty if valid."""
    errors = []
    
    total_cards = sum(count for _, count in self.cards)
    if total_cards != 30:
        errors.append(f"Deck has {total_cards} cards, must have 30")
    
    for card_id, count in self.cards:
        if count < 1:
            errors.append(f"Card {card_id} has invalid count {count}")
        if count > 2 and not self._is_legendary(card_id):
            errors.append(f"Card {card_id} exceeds max 2 copies")
    
    return errors

def is_valid(self) -> bool:
    return len(self.validate()) == 0
```

### 3. Integrate card database
```python
# Add optional dependency on HearthstoneJSON or similar
class Deck:
    def __init__(self, card_db: Optional[CardDatabase] = None):
        self.card_db = card_db
        # ... existing fields
    
    def get_card_name(self, dbf_id: int) -> str:
        if not self.card_db:
            return f"[Card {dbf_id}]"
        return self.card_db.get_card(dbf_id).name
    
    def __str__(self) -> str:
        if not self.card_db:
            return f"Deck({len(self.cards)} cards)"
        lines = [f"# {self.get_card_name(self.heroes[0])}"]
        for card_id, count in self.get_dbf_id_list():
            name = self.get_card_name(card_id)
            lines.append(f"{count}x {name}")
        return "\n".join(lines)
```

### 4. Handle empty/minimal decks
```python
# In write_deckstring()
if len(heroes) == 0:
    raise ValueError("Cannot encode deck with no heroes")
# Allow 0 cards for "empty deck" use case, but document behavior

# Add factory methods
@classmethod
def empty(cls, hero_id: int, format: FormatType) -> "Deck":
    """Create empty deck for the given hero."""
    instance = cls()
    instance.heroes = [hero_id]
    instance.format = format
    return instance
```

### 5. Add human-readable export
```python
# Add to Deck class
def to_dict(self) -> dict:
    return {
        "format": self.format.name,
        "heroes": self.heroes,
        "cards": [{"id": cid, "count": cnt} for cid, cnt in self.cards],
        "sideboards": [
            {"id": cid, "count": cnt, "owner": own} 
            for cid, cnt, own in self.sideboards
        ],
    }

@classmethod
def from_dict(cls, data: dict) -> "Deck":
    # Reverse of to_dict for JSON serialization
    pass
```

### 6. Add deck manipulation API
```python
# Add to Deck class
def add_card(self, card_id: int, count: int = 1):
    """Add copies of a card, updating existing entry if present."""
    for i, (cid, cnt) in enumerate(self.cards):
        if cid == card_id:
            self.cards[i] = (cid, cnt + count)
            return
    self.cards.append((card_id, count))

def remove_card(self, card_id: int, count: int = 1):
    """Remove copies of a card, removing entry if count reaches 0."""
    for i, (cid, cnt) in enumerate(self.cards):
        if cid == card_id:
            new_count = cnt - count
            if new_count <= 0:
                del self.cards[i]
            else:
                self.cards[i] = (cid, new_count)
            return
    raise ValueError(f"Card {card_id} not in deck")

def normalize(self):
    """Merge duplicate entries, remove invalid counts."""
    # Group by card_id and sum counts
    # Remove entries with count <= 0
```

### 7. Add duplicate detection
```python
# Call in add_card() before appending, or add to validate()
def _has_duplicates(self) -> bool:
    seen = set()
    for card_id, _ in self.cards:
        if card_id in seen:
            return True
        seen.add(card_id)
    return False
```

### 8. Add deck metadata support
```python
# Extend Deck class with optional metadata
# Note: Not part of deckstring format, only for in-memory representation
class Deck:
    def __init__(self):
        # ... existing fields
        self.name: str = ""
        self.archetype: Optional[str] = None
        self.created_at: Optional[datetime] = None
        
    # Metadata not included in deckstring encoding
    # Store separately if persistence needed
```

### 9. Fix type hints
```python
from typing import BinaryIO

def _read_varint(stream: BinaryIO) -> int:
    # ...

def _write_varint(stream: BinaryIO, i: int) -> int:
    # ...

class Deck:
    def __init__(self) -> None:
        # ...
```

### 10-14. Lower priority enhancements
```python
# 10. Deck comparison
def diff(self, other: "Deck") -> Tuple[CardIncludeList, CardIncludeList]:
    """Returns (added, removed) card lists."""
    # Compare self.cards vs other.cards
    pass

# 11. Statistics
def mana_curve(self) -> List[int]:
    """Returns card count per mana cost [0-10+]."""
    pass

# 12. Format detection
@classmethod
def infer_format(cls, cards: CardIncludeList, card_db: CardDatabase) -> FormatType:
    # Check rotation, banned lists
    pass

# 13. Performance (low priority - profile first)
# Replace BytesIO with bytearray if benchmarking shows benefit

# 14. Logging
import logging
logger = logging.getLogger(__name__)
# Add logger.debug() calls at key parsing steps
```