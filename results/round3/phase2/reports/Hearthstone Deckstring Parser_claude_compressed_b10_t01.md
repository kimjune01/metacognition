# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system is a **Hearthstone deckstring encoder/decoder**. It implements Blizzard's binary format for sharing deck configurations.

**Working capabilities:**
1. **Perceive**: Reads base64-encoded deckstrings and parses binary data using varint encoding
2. **Cache**: Stores decoded data in structured format (cards, heroes, format, sideboards)
3. **Filter**: Validates deckstring version (must be v1) and rejects invalid formats
4. **Attend**: Organizes cards by count (1x, 2x, n×) for efficient encoding; sorts output consistently
5. **Remember**: Provides `Deck` object to hold state across operations

The bidirectional transform works: `deckstring → parse → Deck → encode → deckstring`

## Triage

**Missing stages (by priority):**

### 1. **Consolidate** (absent)
No learning or adaptation. The system processes identically every time.

**Impact**: High for production use. Can't improve from past decks, detect trends, or build user-specific models.

### 2. **Filter** (shallow)
Current filtering only checks:
- Format marker (must be `\0`)
- Version number (must be 1)

**Missing validations:**
- Card count limits (standard Hearthstone: 30 cards, some modes allow 40)
- Duplicate restrictions (max 2 copies per card, 1 for legendaries)
- Format legality (Wild vs Standard card pools)
- Hero class constraints (cards must match hero class or be neutral)
- Sideboard size limits
- Sideboard owner references (must point to valid cards in main deck)

**Impact**: Critical. Accepts invalid decks that would fail server validation.

### 3. **Attend** (shallow)
Current prioritization is purely structural (sorts by ID). 

**Missing capabilities:**
- Mana curve analysis
- Archetype detection (aggro/control/combo)
- Win rate metadata
- Dust cost calculation
- Collection ownership checking

**Impact**: Medium. Useful for deck builders but not required for basic encode/decode.

### 4. **Error handling** (shallow)
Only raises generic `ValueError` and `EOFError`. No recovery, logging, or diagnostics.

**Impact**: Medium. Makes debugging production issues difficult.

## Plan

### Gap 1: Add Consolidate stage

**Concrete changes:**

1. Create `DeckStats` class to track aggregated data:
   ```python
   class DeckStats:
       def __init__(self, storage_path: str):
           self.card_popularity: Dict[int, int] = {}  # dbf_id → count
           self.archetype_patterns: Dict[str, List[Set[int]]] = {}
           self.storage_path = storage_path
   ```

2. Add `Deck.record_to_stats(stats: DeckStats)` method to update popularity counters

3. Implement `DeckStats.load()` and `DeckStats.save()` for persistence (JSON or SQLite)

4. Add `Deck.get_recommendations(stats: DeckStats) -> List[int]` that suggests cards based on what commonly appears with current cards

### Gap 2: Strengthen Filter stage

**Concrete changes:**

1. Create validation module:
   ```python
   # validators.py
   from typing import List, Tuple
   from .enums import FormatType
   
   class DeckValidationError(ValueError):
       pass
   
   def validate_card_counts(cards: CardIncludeList, format: FormatType) -> None:
       total = sum(count for _, count in cards)
       if format == FormatType.FT_STANDARD and total != 30:
           raise DeckValidationError(f"Standard decks must have 30 cards, got {total}")
   
   def validate_duplicates(cards: CardIncludeList, card_db: CardDatabase) -> None:
       for dbf_id, count in cards:
           rarity = card_db.get_rarity(dbf_id)
           max_count = 1 if rarity == "LEGENDARY" else 2
           if count > max_count:
               raise DeckValidationError(f"Card {dbf_id} exceeds max count")
   
   def validate_sideboard_owners(sideboards: SideboardList, cards: CardIncludeList) -> None:
       card_ids = {dbf_id for dbf_id, _ in cards}
       for card_id, count, owner in sideboards:
           if owner not in card_ids:
               raise DeckValidationError(f"Sideboard owner {owner} not in main deck")
   ```

2. Add `strict` parameter to `parse_deckstring(deckstring, strict=True, card_db=None)`

3. Call validators after parsing if `strict=True`

### Gap 3: Enhance Attend stage

**Concrete changes:**

1. Add `Deck` methods for analysis:
   ```python
   def get_mana_curve(self, card_db: CardDatabase) -> Dict[int, int]:
       """Returns {mana_cost: count}"""
       curve = {}
       for dbf_id, count in self.cards:
           cost = card_db.get_cost(dbf_id)
           curve[cost] = curve.get(cost, 0) + count
       return curve
   
   def get_dust_cost(self, card_db: CardDatabase) -> Tuple[int, int]:
       """Returns (craft_cost, disenchant_value)"""
       craft = sum(card_db.get_craft_cost(id) * cnt for id, cnt in self.cards)
       dust = sum(card_db.get_dust_value(id) * cnt for id, cnt in self.cards)
       return craft, dust
   
   def detect_archetype(self, card_db: CardDatabase) -> str:
       """Returns archetype name based on card patterns"""
       # Use card tags/mechanics to classify
       pass
   ```

2. Add `CardDatabase` abstraction (interface for HearthstoneJSON or similar):
   ```python
   from abc import ABC, abstractmethod
   
   class CardDatabase(ABC):
       @abstractmethod
       def get_rarity(self, dbf_id: int) -> str: pass
       
       @abstractmethod
       def get_cost(self, dbf_id: int) -> int: pass
       
       @abstractmethod
       def get_craft_cost(self, dbf_id: int) -> int: pass
   ```

### Gap 4: Improve error handling

**Concrete changes:**

1. Create exception hierarchy:
   ```python
   class DeckstringError(Exception):
       """Base exception for deckstring operations"""
       pass
   
   class InvalidFormatError(DeckstringError):
       """Raised when deckstring format is invalid"""
       pass
   
   class UnsupportedVersionError(DeckstringError):
       """Raised when version is not supported"""
       pass
   ```

2. Replace generic exceptions in `parse_deckstring()`:
   ```python
   if data.read(1) != b"\0":
       raise InvalidFormatError("Missing magic byte at start of deckstring")
   
   version = _read_varint(data)
   if version != DECKSTRING_VERSION:
       raise UnsupportedVersionError(
           f"Version {version} not supported (expected {DECKSTRING_VERSION})"
       )
   ```

3. Add optional logging:
   ```python
   import logging
   
   logger = logging.getLogger(__name__)
   
   def parse_deckstring(...):
       logger.debug(f"Parsing deckstring of length {len(deckstring)}")
       # ... existing code ...
       logger.info(f"Parsed deck with {len(cards)} cards, {len(heroes)} heroes")
   ```