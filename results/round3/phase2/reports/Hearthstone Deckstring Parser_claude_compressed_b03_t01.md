# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system decodes and encodes Hearthstone deck codes using Blizzard's deckstring format. Current working capabilities:

1. **Perceive**: Reads base64-encoded deckstrings via `parse_deckstring()` and `from_deckstring()`
2. **Cache**: Stores decoded data in `Deck` object with structured fields (cards, heroes, format, sideboards)
3. **Filter**: Basic validation exists:
   - Header byte must be `\0`
   - Version must match `DECKSTRING_VERSION` (1)
   - Format type must be valid `FormatType` enum value
   - Hero count validation (must be exactly 1)
4. **Remember**: State persists within `Deck` instance lifetime
5. **Bidirectional I/O**: Round-trip encoding/decoding works (`as_deckstring` property)
6. **Optimization**: Trisort algorithm groups cards by count (1x, 2x, n×) for efficient encoding

**Consolidate** and **Attend** stages are absent.

## Triage

### Critical gaps

1. **No error recovery** (shallow Filter) - System crashes on malformed input rather than reporting what went wrong
2. **No logging/observability** - Silent failures make debugging impossible in production
3. **No validation of business rules** (shallow Filter) - Accepts invalid decks (wrong card counts, invalid card IDs, format violations)
4. **Untested edge cases** - No handling for truncated streams, malformed varint sequences, or buffer overruns

### Important gaps

5. **No batch processing** (missing Attend) - Can't process multiple deckstrings, deduplicate, or rank by relevance
6. **No persistence layer** (shallow Remember) - Deck state only lives in memory
7. **No learning/adaptation** (missing Consolidate) - System never improves based on usage patterns

### Nice-to-have gaps

8. **Limited introspection** - No `__repr__`, `__eq__`, or human-readable deck summary
9. **No metadata** - Can't track deck name, creation date, win rate, popularity
10. **No format migration** - Can't upgrade old deckstrings if format changes

## Plan

### 1. Error recovery (Fix shallow Filter)

**Current problem**: `EOFError`, `ValueError` crash the process with cryptic messages.

**Required changes**:
- Create custom exception hierarchy:
  ```python
  class DeckstringError(Exception): pass
  class InvalidHeaderError(DeckstringError): pass
  class UnsupportedVersionError(DeckstringError): pass
  class TruncatedDataError(DeckstringError): pass
  ```
- Wrap `_read_varint()` to catch EOF and raise `TruncatedDataError` with byte offset
- Add context to all `ValueError` raises: include the invalid value and expected range
- Add `try/except` in `from_deckstring()` that catches decode errors and re-raises with the original deckstring for debugging

### 2. Logging/observability

**Current problem**: No visibility into what the system is doing.

**Required changes**:
- Add `import logging` and create module-level logger
- Log at INFO level: successful decode/encode with card count and format
- Log at WARNING level: deprecated format versions (if supporting legacy)
- Log at ERROR level: validation failures with full context
- Add optional `verbose` parameter to `Deck.from_deckstring()` for debug output

### 3. Business rule validation (Fix shallow Filter)

**Current problem**: System accepts structurally valid but game-invalid decks.

**Required changes**:
- Add `validate()` method to `Deck`:
  ```python
  def validate(self, card_db: CardDatabase) -> List[ValidationError]:
      errors = []
      # Check total card count (usually 30)
      # Check duplicate legendary cards
      # Check card IDs exist in card_db
      # Check cards are legal in deck.format
      # Check hero matches deck class
      return errors
  ```
- Create `CardDatabase` interface (accepts dict or callback) for card lookup
- Add `strict` parameter to `from_deckstring()`: if True, raise on validation failure; if False, populate `deck.validation_errors`

### 4. Edge case hardening

**Current problem**: Untested boundary conditions will cause production failures.

**Required changes**:
- In `_read_varint()`: add max iterations (prevent infinite loop on corrupted data)
- Add maximum card count check (prevent memory exhaustion from `num_cards_xn = 999999`)
- Add base64 decode validation: catch `binascii.Error` and raise `DeckstringError`
- Add empty deckstring check before decode
- Test suite with fixtures:
  - Truncated deckstrings at every byte offset
  - Oversized varint values
  - Empty hero/card sections
  - Invalid base64 characters

### 5. Batch processing (Add Attend stage)

**Current problem**: Can only process one deck at a time with no comparison or ranking.

**Required changes**:
- Create `DeckCollection` class:
  ```python
  class DeckCollection:
      def add(self, deck: Deck, metadata: dict = None) -> None: ...
      def deduplicate(self) -> List[Deck]: ...
      def rank_by_similarity(self, target: Deck) -> List[Tuple[Deck, float]]: ...
      def filter_by_format(self, format: FormatType) -> "DeckCollection": ...
  ```
- Implement deck fingerprinting: hash sorted card list for deduplication
- Add similarity metric: Jaccard index or card overlap percentage
- Add diversity filter: return top N decks with minimum similarity threshold

### 6. Persistence layer (Fix shallow Remember)

**Current problem**: Deck state evaporates when process ends.

**Required changes**:
- Add serialization methods:
  ```python
  def to_dict(self) -> dict: ...
  @classmethod
  def from_dict(cls, data: dict) -> "Deck": ...
  def save(self, path: Path) -> None: ...  # JSON format
  @classmethod
  def load(cls, path: Path) -> "Deck": ...
  ```
- Add `DeckRepository` interface for database backends:
  ```python
  class DeckRepository(Protocol):
      def save(self, deck: Deck, deck_id: str) -> None: ...
      def load(self, deck_id: str) -> Optional[Deck]: ...
      def query(self, format: FormatType) -> List[Deck]: ...
  ```
- Implement SQLite backend for local storage

### 7. Learning/adaptation (Add Consolidate stage)

**Current problem**: System never gets smarter based on what it sees.

**Required changes**:
- Add telemetry collection:
  ```python
  class DeckMetrics:
      parse_count: int
      error_rate: float
      common_formats: Counter[FormatType]
      average_card_count: float
  ```
- Add `MetricsCollector` that writes to disk on shutdown
- On startup, read metrics and:
  - Warn if parsing decks with rare formats (possible typosquatting)
  - Pre-allocate buffers based on `average_card_count`
  - Log if error rate is rising
- Add adaptive validation: if certain card IDs fail validation repeatedly, add to deny list

### 8. Introspection

**Current problem**: Hard to debug or inspect `Deck` objects.

**Required changes**:
- Add `__repr__()`: show format, hero, and card count
- Add `__eq__()` and `__hash__()`: enable set operations
- Add `summary()` method: return human-readable string with card names (requires card database)
- Add `diff()` method: compare two decks and return added/removed cards

### 9. Metadata support

**Current problem**: No way to attach context to decks.

**Required changes**:
- Add optional `metadata: dict` field to `Deck.__init__()`
- Preserve metadata through encode/decode cycle using JSON sidecar file
- Define standard metadata keys: `name`, `created_at`, `author`, `win_rate`, `archetype`

### 10. Format migration

**Current problem**: Breaking changes to deckstring format will brick old decks.

**Required changes**:
- Add `migrate()` function:
  ```python
  def migrate(deckstring: str, target_version: int) -> str:
      # Detect current version
      # Apply transformation pipeline
      # Re-encode at target version
  ```
- Maintain version-specific parsers: `parse_deckstring_v1()`, `parse_deckstring_v2()`
- Add deprecation warnings when parsing old versions
- Document breaking changes in migration guide

---

**Priority order for implementation**: 1, 2, 3, 4 are pre-launch blockers. 5, 6 are needed for multi-user production. 7, 9, 10 are post-launch improvements. 8 is developer quality-of-life.