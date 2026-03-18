# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Hearthstone deckstring format — a compact binary encoding for deck configurations that uses base64-encoded varint streams.

**Working capabilities:**

1. **Perceive**: Accepts base64-encoded deckstrings via `parse_deckstring()` and decodes them into bytes
2. **Cache**: Parses binary data into structured tuples (card IDs, counts, sideboard owners) and stores them in the `Deck` object
3. **Filter**: Validates header byte (must be `\0`), version (must be `1`), and attempts to validate format enum
4. **Remember**: The `Deck` class persists parsed state across method calls with `.cards`, `.heroes`, `.format`, `.sideboards`

**What works well:**
- Bidirectional conversion (read and write deckstrings)
- Supports three count buckets (1x, 2x, n×) for compression efficiency
- Handles sideboards (optional feature for certain game modes)
- Clean separation between parsing logic and data model
- Sorting outputs for deterministic serialization

## Triage

### Critical gaps (blocks production use)

1. **No Filter for malformed data** — Parser accepts structurally valid but semantically nonsensical decks (e.g., 50 cards, invalid card IDs, wrong hero class)
2. **No Attend stage** — Cannot answer "what changed between these two decks?" or "show me just the legendaries"
3. **Silent failure modes** — EOFError is the only parse error; truncated data, oversized counts, and invalid format values fail ungracefully

### Important gaps (limits usefulness)

4. **No Consolidate stage** — System never learns from past decks (e.g., "this deckstring appears frequently" or "these IDs don't exist in the latest expansion")
5. **No validation against card database** — Card IDs and hero IDs are not checked against any canonical source
6. **Limited error context** — When parsing fails, you don't know *where* in the deckstring or *which* field caused the problem

### Nice-to-have gaps

7. **No human-readable output** — No method to render as "2× Fireblast, 1× Archmage Antonidas"
8. **No diff/comparison utilities** — Cannot compute deck similarity or detect tech card swaps
9. **No statistical queries** — Cannot answer "what's the average mana cost?" or "how many spells?"

## Plan

### 1. Add semantic validation (Filter stage)

**Current state:** Parser validates structure (version, header byte) but not content.

**Changes needed:**
```python
class DeckValidator:
    MAX_DECK_SIZE = 30  # Standard/Wild
    MAX_CARD_COPIES = 2  # Except for special cases
    
    @staticmethod
    def validate_deck(deck: Deck) -> List[str]:
        """Returns list of validation errors (empty if valid)"""
        errors = []
        
        # Check deck size
        total_cards = sum(count for _, count in deck.cards)
        if total_cards != DeckValidator.MAX_DECK_SIZE:
            errors.append(f"Deck has {total_cards} cards, expected 30")
        
        # Check duplicate limits
        for cardid, count in deck.cards:
            if count > DeckValidator.MAX_CARD_COPIES:
                errors.append(f"Card {cardid} has {count} copies, max is 2")
        
        # Check hero count
        if len(deck.heroes) != 1:
            errors.append(f"Deck has {len(deck.heroes)} heroes, expected 1")
        
        return errors
```

Call `validate_deck()` at end of `from_deckstring()` and raise `ValueError` if non-empty.

### 2. Add query/filtering interface (Attend stage)

**Current state:** System returns all cards with no ranking or selection.

**Changes needed:**
```python
class Deck:
    def filter_cards(self, predicate: Callable[[int, int], bool]) -> CardIncludeList:
        """Return cards matching predicate(cardid, count)"""
        return [(cid, cnt) for cid, cnt in self.cards if predicate(cid, cnt)]
    
    def get_unique_cards(self) -> List[int]:
        """Return sorted list of unique card IDs (attend to diversity)"""
        return sorted(set(cid for cid, _ in self.cards))
    
    def rank_by_count(self, desc: bool = True) -> CardIncludeList:
        """Sort cards by count (attend to frequency)"""
        return sorted(self.cards, key=lambda x: x[1], reverse=desc)
```

### 3. Enrich error messages with context

**Current state:** EOFError says "Unexpected EOF while reading varint" with no location info.

**Changes needed:**
```python
def _read_varint(stream: IO, context: str = "unknown") -> int:
    # ... existing logic ...
    if c == "":
        pos = stream.tell()
        raise EOFError(f"Unexpected EOF at byte {pos} while reading {context}")
```

Update all call sites: `_read_varint(data, "hero count")`, `_read_varint(data, "card ID in x1 section")`, etc.

### 4. Add statistics/aggregation (deeper Attend)

**Current state:** No analytical queries available.

**Changes needed:**
```python
class Deck:
    def get_card_count(self) -> int:
        """Total cards in deck"""
        return sum(count for _, count in self.cards)
    
    def get_dust_cost(self, card_db: Dict[int, CardData]) -> int:
        """Total crafting cost (requires external card database)"""
        return sum(card_db[cid].dust * cnt for cid, cnt in self.cards)
    
    def contains_card(self, cardid: int) -> bool:
        """Check if specific card is in deck"""
        return any(cid == cardid for cid, _ in self.cards)
```

### 5. Add card database integration (better Filter + Attend)

**Current state:** Card IDs are opaque integers with no metadata.

**Changes needed:**
```python
from typing import Protocol

class CardDatabase(Protocol):
    def exists(self, cardid: int) -> bool: ...
    def get_name(self, cardid: int) -> str: ...
    def is_valid_hero(self, heroid: int) -> bool: ...

class Deck:
    def __init__(self, card_db: Optional[CardDatabase] = None):
        # ... existing fields ...
        self.card_db = card_db
    
    @classmethod
    def from_deckstring(cls, deckstring: str, card_db: Optional[CardDatabase] = None):
        instance = cls(card_db=card_db)
        # ... parse ...
        if instance.card_db:
            instance._validate_with_db()
        return instance
    
    def _validate_with_db(self):
        for cid, _ in self.cards:
            if not self.card_db.exists(cid):
                raise ValueError(f"Unknown card ID {cid}")
        # Similar for heroes
```

### 6. Add diff/comparison (Attend across multiple decks)

**Current state:** No cross-deck operations.

**Changes needed:**
```python
def deck_diff(deck_a: Deck, deck_b: Deck) -> Tuple[CardIncludeList, CardIncludeList]:
    """Returns (cards_only_in_a, cards_only_in_b)"""
    set_a = {cid for cid, _ in deck_a.cards}
    set_b = {cid for cid, _ in deck_b.cards}
    
    only_a = [(cid, cnt) for cid, cnt in deck_a.cards if cid not in set_b]
    only_b = [(cid, cnt) for cid, cnt in deck_b.cards if cid not in set_a]
    
    return only_a, only_b
```

### 7. Add usage tracking (Consolidate stage)

**Current state:** System has no memory of past operations.

**Changes needed:**
```python
class DeckCache:
    """Persistent storage for deck metadata"""
    def __init__(self, db_path: str):
        self.db = sqlite3.connect(db_path)
        self._init_schema()
    
    def record_parse(self, deckstring: str, success: bool):
        """Log that this deckstring was parsed"""
        # Store timestamp, hash, success/failure
    
    def get_popular_cards(self, limit: int = 10) -> List[Tuple[int, int]]:
        """Return most common cards across all cached decks"""
        # Aggregate across stored decks
    
    def has_seen(self, deckstring: str) -> bool:
        """Check if this exact deckstring was parsed before"""
        # Deduplication
```

Add optional `DeckCache` parameter to `parse_deckstring()`. When present, log every parse and use cached results for validation (e.g., "card ID 999999 has never appeared in any deck").

### 8. Add human-readable output

**Current state:** Can only see card IDs, not names.

**Changes needed:**
```python
class Deck:
    def to_string(self, card_db: Optional[CardDatabase] = None) -> str:
        """Format deck as human-readable list"""
        if not card_db:
            return "\n".join(f"{cnt}× Card {cid}" for cid, cnt in self.cards)
        
        lines = []
        for cid, cnt in sorted(self.cards):
            name = card_db.get_name(cid)
            lines.append(f"{cnt}× {name}")
        return "\n".join(lines)
```

---

**Priority order for implementation:**
1. Semantic validation (#1) — prevents garbage in
2. Error context (#3) — makes debugging possible
3. Card database integration (#5) — enables all other features
4. Query interface (#2) — makes system actually useful
5. Statistics (#4), Diff (#6), Human output (#8) — quality of life
6. Usage tracking (#7) — learning/optimization layer