# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system currently implements the **Blizzard Deckstring format** for encoding and decoding Hearthstone deck configurations. Working capabilities:

1. **Decoding deckstrings** (`parse_deckstring`): Parses base64-encoded binary format into structured deck data
   - Extracts format type (Standard/Wild/etc)
   - Reads hero card IDs
   - Reads main deck cards with counts (1×, 2×, or n×)
   - Reads sideboard cards (introduced in later expansions)

2. **Encoding deckstrings** (`write_deckstring`): Converts deck data back to canonical string format
   - Groups cards by count for efficient encoding
   - Maintains sort order for deterministic output
   - Handles optional sideboard section

3. **Binary varint encoding**: Implements variable-length integer encoding/decoding (`_read_varint`, `_write_varint`)

4. **High-level Deck object** (`Deck` class): Provides OOP interface with:
   - `from_deckstring()` constructor
   - `as_deckstring` property for serialization
   - Accessor methods for sorted card lists

5. **Format validation**: Checks version (v1 only) and validates format type enum

## Triage

### Critical Gaps

1. **Error handling is minimal** – Production parsers need robust error reporting
   - Priority: **HIGH** – Users will share malformed deckstrings frequently

2. **No card database integration** – System works with DBF IDs but can't resolve to card names
   - Priority: **HIGH** – Numbers are meaningless without metadata lookup

3. **No deck validation rules** – Accepts invalid decks (wrong counts, illegal cards, etc)
   - Priority: **MEDIUM-HIGH** – Prevents user frustration from invalid decks

### Important Missing Features

4. **Multi-hero support incomplete** – Code enforces single hero (`if len(heroes) != 1`)
   - Priority: **MEDIUM** – Some formats (Duels, Arena) allow multiple heroes

5. **No deck metadata** – Missing deck name, archetype, creation date, etc.
   - Priority: **MEDIUM** – Essential for deck management UIs

6. **Limited format support** – `FormatType` enum not shown but likely incomplete
   - Priority: **MEDIUM** – New formats added regularly (Twist, etc)

### Quality-of-Life Issues

7. **No human-readable export** – Can't export to text format or deck sharing sites
   - Priority: **LOW-MEDIUM** – Users expect copy-paste friendly output

8. **No type hints on return tuples** – Return types like `Tuple[CardIncludeList, CardList, FormatType, SideboardList]` are hard to work with
   - Priority: **LOW-MEDIUM** – Developer experience issue

9. **No logging/debugging support** – Silent failures make troubleshooting hard
   - Priority: **LOW** – Nice-to-have for production

10. **Performance not optimized** – BytesIO and repeated sorts could be faster
    - Priority: **LOW** – Deckstrings are small (<1KB typically)

## Plan

### 1. Error Handling Enhancement

**Current problem**: Generic exceptions, no context on what failed where

**Changes needed**:
- Create custom exception hierarchy:
  ```python
  class DeckstringError(Exception): pass
  class InvalidDeckstringError(DeckstringError): pass
  class UnsupportedVersionError(DeckstringError): pass
  ```
- In `_read_varint`, wrap `EOFError` with byte offset context
- In `parse_deckstring`, catch base64 decode errors and wrap them
- Add position tracking to report "error at byte X" for debugging
- Return `Result[Deck, Error]` pattern or use detailed exception messages

### 2. Card Database Integration

**Current problem**: Only stores numeric DBF IDs, no card metadata

**Changes needed**:
- Add `CardDatabase` class that loads from JSON/SQLite:
  ```python
  class CardDatabase:
      def get_card(self, dbf_id: int) -> Optional[CardData]
      def validate_card(self, dbf_id: int, format: FormatType) -> bool
  ```
- Extend `Deck` class with:
  ```python
  def get_card_names(self, db: CardDatabase) -> List[Tuple[str, int]]
  def get_dust_cost(self, db: CardDatabase) -> int
  ```
- Add lazy loading option to avoid database overhead when not needed

### 3. Deck Validation

**Current problem**: Accepts decks that violate Hearthstone rules

**Changes needed**:
- Implement `Deck.validate(db: CardDatabase) -> List[ValidationError]`:
  - Check total card count (typically 30)
  - Enforce card limits (max 1 legendary, max 2 others)
  - Verify hero class matches card classes
  - Check format legality (cards legal in Standard/Wild/etc)
  - Validate sideboard rules (correct owner IDs)
- Add `strict` parameter to `from_deckstring` to raise on invalid decks
- Return validation warnings separately from hard errors

### 4. Multi-Hero Support

**Current problem**: Hardcoded `if len(heroes) != 1` raises ValueError

**Changes needed**:
- Remove the single-hero constraint in `write_deckstring`
- Add format-aware validation:
  ```python
  def _validate_hero_count(heroes: List[int], format: FormatType):
      if format == FormatType.FT_STANDARD and len(heroes) != 1:
          raise ValueError("Standard requires exactly 1 hero")
      elif format == FormatType.FT_ARENA and len(heroes) > 3:
          raise ValueError("Arena allows max 3 heroes")
  ```
- Update `Deck` class to handle multi-hero deck codes properly

### 5. Deck Metadata Support

**Current problem**: No way to attach name, description, or timestamps

**Changes needed**:
- Extend `Deck` class with optional fields:
  ```python
  self.name: Optional[str] = None
  self.created_at: Optional[datetime] = None
  self.archetype: Optional[str] = None  # e.g., "Face Hunter"
  ```
- These don't go in deckstring (not part of Blizzard format) but stored separately
- Add JSON serialization for full deck metadata:
  ```python
  def to_json(self) -> dict
  @classmethod
  def from_json(cls, data: dict) -> "Deck"
  ```

### 6. Format Type Completeness

**Current problem**: `FormatType` enum not visible but likely outdated

**Changes needed**:
- Show/update `enums.py` to include all current formats:
  - `FT_STANDARD`, `FT_WILD`, `FT_CLASSIC`, `FT_TWIST`, `FT_CASUAL`
  - Game mode variants: `FT_ARENA`, `FT_BATTLEGROUNDS`, `FT_MERCENARIES`
- Add future-proofing: unknown format codes should warn but not fail
- Document which formats support sideboards

### 7. Human-Readable Export

**Current problem**: Only exports binary deckstring

**Changes needed**:
- Add `Deck.to_text(db: CardDatabase) -> str`:
  ```python
  # Format: 2× Fireball, 1× Archmage Antonidas
  ```
- Add `Deck.to_hsreplay_url(db: CardDatabase) -> str` for sharing
- Support parsing from text format: `Deck.from_text(text, db)`

### 8. Better Type Ergonomics

**Current problem**: Functions return unnamed tuples

**Changes needed**:
- Replace tuple returns with dataclasses:
  ```python
  @dataclass
  class ParsedDeck:
      cards: CardIncludeList
      heroes: CardList
      format: FormatType
      sideboards: SideboardList
  ```
- Use `NamedTuple` as lighter alternative if dataclasses too heavy
- Makes code self-documenting: `deck.cards` vs `deck[0]`

### 9. Logging Support

**Current problem**: No visibility into parsing/encoding process

**Changes needed**:
- Add Python `logging` module usage:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  
  # In parse_deckstring:
  logger.debug(f"Parsing deckstring version {version}, format {format}")
  logger.debug(f"Found {num_cards_x1} 1× cards, {num_cards_x2} 2× cards")
  ```
- Log warnings for unusual but valid decks (>30 cards, 0 heroes, etc)

### 10. Performance Optimization

**Current problem**: Multiple sorts, BytesIO overhead

**Changes needed** (only if profiling shows bottlenecks):
- Cache sorted card lists in `Deck` class
- Use `bytearray` instead of `BytesIO` for writing
- Avoid re-sorting if cards already sorted
- Add `__slots__` to `Deck` class for memory efficiency
- These optimizations likely premature given typical usage patterns

---

**Recommended implementation order**: 1 → 2 → 3 → 7 → 5 → 4 → 8 → 6 → 9 → 10