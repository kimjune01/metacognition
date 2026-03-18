# Diagnostic Report: Hearthstone Deckstring Library

## Observations

This system implements Blizzard's Hearthstone deckstring encoding/decoding format. Current working capabilities:

1. **Deckstring Parsing** - Decodes base64-encoded binary deckstrings into structured data containing:
   - Card lists with quantities (1x, 2x, or n copies)
   - Hero card IDs
   - Format type (Standard, Wild, etc.)
   - Sideboard cards (with ownership tracking)

2. **Deckstring Generation** - Encodes deck data back into the official deckstring format with proper varint encoding and trisort optimization (grouping cards by count)

3. **Binary Protocol Implementation** - Correctly implements:
   - Varint reading/writing for space-efficient integer encoding
   - Multi-section format (header → heroes → cards → sideboards)
   - Version and format validation
   - Optional sideboard support with ownership IDs

4. **Data Structures** - Provides `Deck` class with:
   - Factory method `from_deckstring()` for parsing
   - Property `as_deckstring` for encoding
   - Sorted accessors for cards and sideboards

5. **Card Organization** - `trisort_cards()` optimizes storage by grouping cards into 1x, 2x, and n-copy buckets

## Triage

### Critical Gaps
1. **No Error Recovery** - Parser has no tolerance for malformed input; will crash on corrupted deckstrings
2. **Missing Card Validation** - No checks that card IDs are valid, counts are legal (deck size limits), or heroes match format
3. **No Tests** - Zero test coverage for a binary protocol parser (high-risk)

### Important Gaps
4. **Limited Documentation** - No docstrings, usage examples, or explanation of the binary format
5. **Incomplete FormatType** - References `FormatType` enum but doesn't define it; imported from `.enums` (may not exist)
6. **No Deck Manipulation Methods** - Can't add/remove cards, change hero, or modify format after creation
7. **Weak Type Safety** - Uses raw tuples instead of dataclasses/NamedTuples; easy to confuse (cardid, count) vs (cardid, count, owner)

### Minor Gaps
8. **No Deck Metadata** - Missing name, class, creation date, or source tracking
9. **Limited Introspection** - No `__repr__`, `__eq__`, or card lookup by ID
10. **No Export Formats** - Can't convert to JSON, card names, or human-readable formats
11. **Hardcoded Constants** - Hero count check `if len(heroes) != 1` fails for future multi-hero formats

## Plan

### 1. Error Recovery
- **Change**: Wrap parser in try/except blocks with specific exceptions
  - Add `InvalidDeckstringError(ValueError)` for corrupt input
  - Add `UnsupportedVersionError(ValueError)` for version mismatches
  - Catch `EOFError` in `_read_varint` and convert to `InvalidDeckstringError`
- **Location**: New exception classes at top of file; wrap `parse_deckstring()` internals

### 2. Card Validation
- **Change**: Add `Deck.validate()` method that checks:
  - Deck size (typically 30 cards for constructed)
  - Card count limits (max 2 of non-legendary, 1 of legendary)
  - Hero matches format (requires external card database)
  - Valid FormatType enum value
- **Parameters**: Accept optional `card_db` parameter for ID validation
- **Return**: Raise `ValidationError` with specific message or return list of issues

### 3. Test Coverage
- **Create**: `tests/test_deckstring.py` with:
  - Round-trip tests (encode→decode→encode produces identical output)
  - Known deckstring fixtures from real decks
  - Malformed input tests (truncated, wrong version, invalid base64)
  - Edge cases (empty deck, max copies, sideboards)
- **Tools**: Use pytest with parametrize for multiple test cases

### 4. Documentation
- **Add**: Module-level docstring explaining:
  - What deckstrings are (Hearthstone deck sharing format)
  - Binary format specification (sections, varint encoding)
  - Usage example: `deck = Deck.from_deckstring("AAE...")`
- **Add**: Docstrings to all public methods with Args/Returns/Raises sections
- **Create**: `README.md` or `USAGE.md` with examples

### 5. FormatType Enum
- **Create**: `enums.py` with:
  ```python
  class FormatType(IntEnum):
      FT_UNKNOWN = 0
      FT_WILD = 1
      FT_STANDARD = 2
      FT_CLASSIC = 3
      # Add others as needed
  ```
- **Alternative**: Remove import and define inline if it's the only enum

### 6. Deck Manipulation
- **Add methods to `Deck` class**:
  - `add_card(card_id: int, count: int = 1) -> None`
  - `remove_card(card_id: int, count: int = 1) -> None`
  - `set_hero(hero_id: int) -> None`
  - `set_format(format: FormatType) -> None`
  - `add_sideboard_card(card_id: int, owner_id: int, count: int = 1) -> None`
- **Maintain invariants**: Keep cards sorted, merge duplicates

### 7. Type Safety
- **Change**: Replace tuples with typed structures:
  ```python
  @dataclass(frozen=True)
  class CardEntry:
      card_id: int
      count: int
  
  @dataclass(frozen=True)
  class SideboardEntry:
      card_id: int
      count: int
      owner_id: int
  ```
- **Update**: All type hints and method signatures to use these classes
- **Convert**: Input/output boundaries to maintain backward compatibility

### 8. Deck Metadata
- **Add fields to `Deck.__init__`**:
  ```python
  self.name: Optional[str] = None
  self.deck_class: Optional[int] = None  # Class ID
  self.created_at: Optional[datetime] = None
  ```
- **Note**: These don't serialize to deckstring (not part of format)

### 9. Introspection Methods
- **Add to `Deck`**:
  - `__repr__() -> str`: Returns `Deck(format=FT_STANDARD, cards=30, hero=...)`
  - `__eq__(other) -> bool`: Compares cards, heroes, format (ignores metadata)
  - `find_card(card_id: int) -> Optional[int]`: Returns count or None
  - `total_cards() -> int`: Sum of all card counts

### 10. Export Formats
- **Add methods**:
  - `to_dict() -> dict`: Returns JSON-serializable dict
  - `from_dict(data: dict) -> Deck`: Class method for JSON deserialization
  - `to_card_list(card_db) -> List[str]`: Returns human-readable card names (requires external DB)
- **Consider**: Separate `DeckSerializer` class if this grows complex

### 11. Remove Hardcoded Limits
- **Change**: Replace `if len(heroes) != 1: raise` with configurable validation
  ```python
  def write_deckstring(..., max_heroes: int = 1):
      if len(heroes) > max_heroes:
          raise ValueError(f"Too many heroes: {len(heroes)} > {max_heroes}")
  ```
- **Document**: Current Hearthstone limit is 1 but format supports multiple