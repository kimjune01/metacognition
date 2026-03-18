# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements Blizzard's Hearthstone deckstring format serialization and deserialization. Current working capabilities:

1. **Perceive**: Reads base64-encoded deckstrings via `parse_deckstring()`, decodes binary format with varint encoding
2. **Cache**: Stores parsed data in `Deck` object with normalized structure (cards, heroes, format, sideboards)
3. **Filter**: Validates basic format constraints:
   - Version check (must be DECKSTRING_VERSION = 1)
   - Format type validation against `FormatType` enum
   - Hero count validation (exactly 1 hero required)
   - Zero-byte header validation
4. **Remember**: Can serialize back to deckstring format via `write_deckstring()` and `Deck.as_deckstring`
5. **Utilities**: Card sorting by count (1x, 2x, nx buckets), sideboard support, DBF ID retrieval

**Missing stages**: 
- **Attend**: No prioritization, ranking, or selection logic
- **Consolidate**: No learning or adaptation based on past operations

## Triage

### Critical gaps (would cause production failures):

1. **Error handling is incomplete** - Many failure modes lack clear error messages or recovery paths
2. **No input sanitization beyond format checks** - Accepts structurally valid but semantically invalid decks
3. **No validation of game rules** - Card counts, deck size limits, format legality not enforced
4. **No logging or observability** - Silent failures, no debugging information

### Important gaps (would limit production utility):

5. **No semantic validation** - Doesn't verify cards exist, are legal in format, or follow deckbuilding rules
6. **No duplicate detection** - Can parse deck with same card listed multiple times
7. **No human-readable output** - Only encodes/decodes, doesn't display deck in readable form
8. **Type hints incomplete** - Return type for `parse_deckstring` uses tuple syntax instead of proper typing

### Nice-to-have gaps (polish for production):

9. **No deck comparison or diffing** - Can't tell what changed between two deckstrings
10. **No card database integration** - Works with IDs only, no card names or metadata
11. **No versioning strategy** - `DECKSTRING_VERSION` is hardcoded, future versions would break
12. **No performance optimization** - Repeated sorting, no caching of parsed results

## Plan

### Gap 1: Error handling
**Changes needed:**
- Wrap `base64.b64decode()` in try-except for `binascii.Error` with message "Invalid base64 encoding"
- Add bounds checking in varint reader (prevent infinite loop on malformed data)
- Add maximum deck size check (prevent DoS via huge varint values)
- Create custom exception hierarchy: `DeckstringError`, `InvalidFormatError`, `UnsupportedVersionError`
- Add position tracking in BytesIO to report where parsing failed

### Gap 2: Input sanitization
**Changes needed:**
- Add max length check for deckstring (e.g., 2KB limit) before decoding
- Validate card IDs are positive integers
- Validate counts are positive integers ≤ 100
- Ensure no EOF before all expected data is read (check `data.tell()` vs `len(decoded)`)
- Reject deckstrings with trailing garbage bytes

### Gap 3: Game rules validation
**Changes needed:**
- Add `validate()` method to `Deck` class with optional `strict=True` parameter
- Check deck size (typically 30 cards for constructed)
- Check card count limits (typically ≤2 per card, ≤1 for legendaries)
- Validate format constraints (e.g., Wild vs Standard card pool)
- Add `is_valid` property that caches validation result
- Accept optional `CardDatabase` parameter to enable rule checking

### Gap 4: Logging and observability
**Changes needed:**
- Add `import logging` and create module logger: `logger = logging.getLogger(__name__)`
- Log at DEBUG: "Parsing deckstring version X format Y"
- Log at INFO: "Parsed deck with N cards, M heroes"
- Log at WARNING: "Unusual deck structure detected: ..."
- Log at ERROR: All exceptions with partial state before failure
- Add optional `strict` parameter to enable raising vs logging validation failures

### Gap 5: Semantic validation
**Changes needed:**
- Create `CardDatabase` interface (abstract base class)
- Add `validate_card_exists(dbf_id: int) -> bool` method
- Add `validate_format_legal(dbf_id: int, format: FormatType) -> bool` method
- Add `get_card_rarity(dbf_id: int) -> Rarity` method for legendary checking
- Make `Deck.validate()` accept optional database to enable checks
- Return structured validation result: `ValidationResult(is_valid: bool, errors: List[str])`

### Gap 6: Duplicate detection
**Changes needed:**
- In `parse_deckstring()`, build a set to track seen card IDs
- Raise `DuplicateCardError` if same ID appears in multiple count buckets
- Add `deduplicate()` method to `Deck` that consolidates duplicate entries
- Add `has_duplicates()` property for checking without modifying

### Gap 7: Human-readable output
**Changes needed:**
- Add `__str__()` method to `Deck` returning formatted deck list
- Add `to_dict()` method returning JSON-serializable structure
- Add `to_text(card_db: Optional[CardDatabase] = None)` returning plain text with card names
- Format example: "### Deck Name\n# Class: Druid\n# Format: Standard\n# 2x (1) Acornbearer\n# 1x (2) Bonechewer Brawler"

### Gap 8: Type hints
**Changes needed:**
- Replace tuple syntax: `Tuple[CardIncludeList, CardList, FormatType, SideboardList]` with named tuple or dataclass
- Create `ParsedDeck` dataclass with explicit fields
- Add type hints to all function parameters and returns
- Run `mypy --strict` and resolve all issues
- Add `from __future__ import annotations` for forward references

### Gap 9: Deck comparison
**Changes needed:**
- Add `Deck.__eq__()` for equality checking (ignoring order)
- Add `Deck.diff(other: Deck) -> DeckDiff` returning added/removed/changed cards
- Create `DeckDiff` dataclass with `added`, `removed`, `modified` card lists
- Add `similarity_score(other: Deck) -> float` returning 0.0-1.0 based on card overlap

### Gap 10: Card database integration
**Changes needed:**
- Add optional dependency on HearthstoneJSON or similar card database
- Create `CardResolver` class to map DBF IDs to card metadata
- Add `enrich()` method to `Deck` that attaches card names, costs, rarities
- Cache resolved cards to avoid repeated lookups

### Gap 11: Versioning strategy
**Changes needed:**
- Create version registry: `SUPPORTED_VERSIONS = {1: parse_v1, 2: parse_v2, ...}`
- Refactor current code into `_parse_deckstring_v1()` and `_write_deckstring_v1()`
- Dispatch based on version in `parse_deckstring()`
- Add `convert_version(from_version: int, to_version: int)` migration function
- Document version differences in module docstring

### Gap 12: Performance optimization
**Changes needed:**
- Remove redundant sorting (cards already sorted during parse, don't re-sort)
- Add `@lru_cache` to `Deck.as_deckstring` with cache invalidation on modification
- Make `Deck` immutable (frozen dataclass) to enable safe caching
- Use `__slots__` to reduce memory overhead
- Batch varint operations instead of byte-by-byte reads

---

**Recommended implementation order**: Gaps 1-4 (critical), then 5-7 (important), then 8-12 (polish). Start with error handling and validation to prevent production incidents, then add usability features.