# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements Blizzard's deckstring format for Hearthstone deck sharing:

**Working capabilities:**
1. **Perceive**: Reads base64-encoded deckstrings via `from_deckstring()` and decodes binary format
2. **Cache**: Stores parsed deck data in structured `Deck` object (cards, heroes, format, sideboards)
3. **Filter**: Validates deckstring format (zero-byte header, version check) and rejects invalid input
4. **Remember**: Provides serialization back to deckstring format via `as_deckstring` property
5. **Core parsing**: Handles variable-length integer encoding (varint), multiple card count buckets (1x, 2x, n×), and optional sideboard section
6. **Sorting utilities**: `trisort_cards()` organizes cards by count, `get_dbf_id_list()` returns sorted card lists

**What's notably absent:** Attend stage (no ranking/prioritization) and Consolidate stage (no learning/adaptation).

## Triage

### Critical gaps
1. **Error handling is brittle** — System raises generic exceptions with minimal context. Production needs: specific exception types, error recovery, partial parse capability
2. **No validation beyond format** — Filter stage only checks structure, not game rules. Missing: deck size limits, card legality for format, duplicate detection in heroes
3. **Attend stage completely missing** — No ranking, sorting, or selection logic for what matters. Needed for: deck analysis, meta relevance, power level assessment

### Important gaps
4. **No logging or observability** — Silent failures make debugging impossible in production
5. **Type hints incomplete** — `parse_deckstring` return type is malformed tuple syntax, `IO` type too generic
6. **No sideboard validation** — Sideboard owners can reference non-existent cards, counts unchecked
7. **Consolidate stage absent** — System never learns from processed decks (no statistics, no pattern detection)

### Nice-to-have gaps
8. **Limited metadata** — No deck name, player info, creation timestamp
9. **No card database integration** — DBF IDs are opaque integers; can't validate or enrich
10. **Performance not optimized** — Repeated sorts, no caching of encoded output

## Plan

### 1. Error handling (Critical)
**Changes needed:**
- Create custom exception hierarchy: `DeckstringError` base, `InvalidFormatError`, `UnsupportedVersionError`, `CorruptedDataError` subclasses
- In `parse_deckstring()`: wrap varint reads in try/except, add byte position tracking for error messages
- Add optional `strict=True` parameter — when False, return partial deck + list of warnings instead of raising
- Example: `raise InvalidFormatError(f"Expected zero byte at position 0, got {data.read(1)!r}")`

### 2. Game rule validation (Critical)
**Changes needed:**
- Add `validate()` method to `Deck` class with these checks:
  - Total card count == 30 (or format-specific limit)
  - No more than 2 copies per card (except specific cards like C'Thun)
  - Exactly 1 hero
  - Cards legal in specified format (requires card database)
- Create `DeckValidator` class with pluggable rulesets per format
- Call validation in `from_deckstring()` by default, add `validate=False` option to skip

### 3. Add Attend stage (Critical)
**Changes needed:**
- Implement `DeckAnalyzer` class with methods:
  - `get_mana_curve() -> Dict[int, int]` — histogram of card costs
  - `get_card_types() -> Dict[str, int]` — count by minion/spell/weapon
  - `rank_by_relevance(meta_data: dict) -> CardIncludeList` — sort cards by meta importance
  - `detect_archetype() -> str` — classify deck (aggro/control/combo)
- Add `Deck.get_priority_cards(limit: int = 10)` — return most important cards first
- Use existing `get_dbf_id_list()` as foundation, add secondary sort criteria

### 4. Logging and observability (Important)
**Changes needed:**
- Add `import logging` at top, create module logger: `logger = logging.getLogger(__name__)`
- Log at key points:
  - `parse_deckstring()` entry: `logger.info(f"Parsing deckstring (length={len(deckstring)})")`
  - After each section: `logger.debug(f"Parsed {len(cards)} cards, {len(heroes)} heroes")`
  - On errors: `logger.error(f"Failed to parse at byte {data.tell()}", exc_info=True)`
- Add optional `metrics` callback parameter for production instrumentation

### 5. Fix type hints (Important)
**Changes needed:**
- Change `parse_deckstring` return type from `(Tuple[...])` to `Tuple[CardIncludeList, CardList, FormatType, SideboardList]` (remove outer parens)
- Replace `IO` with `BinaryIO` from `typing` module
- Add `-> int` return type annotations to `_read_varint` and `_write_varint`
- Run `mypy --strict` to catch remaining issues

### 6. Sideboard validation (Important)
**Changes needed:**
- In `Deck.validate()`, add checks:
  - `sideboard_owner` must be a card ID that exists in main deck
  - Sideboard card count per owner <= format limit
  - No duplicate (card_id, owner) pairs
- Add `Deck.get_sideboard_for_card(card_id: int) -> List[Tuple[int, int]]` helper method

### 7. Add Consolidate stage (Important)
**Changes needed:**
- Create `DeckHistory` class that tracks:
  - Parsed decks in SQLite or JSON file
  - Frequency of card combinations
  - Common archetypes by format
- Implement `DeckHistory.update(deck: Deck)` — add deck to history
- Implement `DeckHistory.suggest_improvements(deck: Deck) -> List[str]` — use historical data to recommend substitutions
- Call automatically when `Deck.remember()` is invoked (new method to add)

### 8. Add metadata support (Nice-to-have)
**Changes needed:**
- Extend `Deck.__init__()` with optional fields: `name: Optional[str] = None`, `created_at: Optional[int] = None`
- These don't exist in deckstring format, so store separately
- Add `Deck.to_dict()` and `Deck.from_dict()` for JSON serialization with metadata
- Metadata goes in wrapper format, deckstring stays in `.as_deckstring`

### 9. Card database integration (Nice-to-have)
**Changes needed:**
- Create `CardDatabase` class that loads from HearthstoneJSON or local cache
- Add `Deck.resolve_cards(db: CardDatabase) -> List[Card]` — convert DBF IDs to rich `Card` objects with names, costs, text
- Use in validation: `db.is_legal(card_id, format)`
- Inject database via constructor: `Deck.from_deckstring(s, db=None)`

### 10. Performance optimization (Nice-to-have)
**Changes needed:**
- Cache `as_deckstring` result in `Deck._cached_deckstring: Optional[str]`, invalidate on mutation
- Remove redundant sorts: `get_dbf_id_list()` and `get_sideboard_dbf_id_list()` sort twice (once in trisort, once on return)
- Use `functools.lru_cache` on `parse_deckstring()` for repeated decks
- Benchmark with `pytest-benchmark` before/after

---

**Recommended implementation order:** 1 → 2 → 4 → 5 → 3 → 6 → rest. Fix error handling and validation first (makes system robust), add observability (makes debugging possible), fix types (makes development safer), then add intelligence layer.