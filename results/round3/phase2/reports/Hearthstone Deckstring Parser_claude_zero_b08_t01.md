# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system provides a complete **bidirectional codec** for Blizzard's proprietary deckstring format used in Hearthstone:

**Working capabilities:**
1. **Deserialization** - Parses base64-encoded deckstrings into structured data (cards, heroes, format, sideboards)
2. **Serialization** - Encodes deck data back into valid deckstring format
3. **Varint I/O** - Custom variable-length integer encoding/decoding for compact binary representation
4. **Card organization** - Trisorts cards by count (×1, ×2, ×N) for optimal encoding
5. **Sideboard support** - Handles optional sideboard cards with owner tracking (post-2020 feature)
6. **Format validation** - Validates deck format type (Standard, Wild, etc.) via enum
7. **Object-oriented interface** - `Deck` class provides clean API with `from_deckstring()` and `as_deckstring` property
8. **Data access helpers** - Methods to retrieve sorted card/sideboard lists by DBF ID

## Triage

### Critical gaps (Production blockers)
1. **Zero error handling** - No recovery from malformed input, truncated streams, or corrupted data
2. **No validation logic** - Accepts invalid deck compositions (wrong card counts, illegal cards for format)
3. **Missing test coverage** - No visible tests for edge cases, round-trip fidelity, or version compatibility

### High-priority gaps (Quality/usability issues)
4. **No documentation** - Missing docstrings, usage examples, and format specification reference
5. **Type hints incomplete** - Return types documented but internal functions lack full typing
6. **No logging** - Silent failures make debugging impossible in production
7. **Hard-coded hero count** - `if len(heroes) != 1` breaks for multi-hero formats or future extensions

### Medium-priority gaps (Nice-to-haves)
8. **No performance optimization** - Multiple sorts happen without caching
9. **Limited deck manipulation** - No methods to add/remove cards, merge decks, or calculate dust cost
10. **No format conversion** - Can't export to other formats (JSON, HearthSim XML, etc.)
11. **Enum dependency unclear** - `FormatType` imported but not defined in this module

## Plan

### 1. Error handling (Critical)
**Changes needed:**
- Wrap `parse_deckstring()` body in try-except to catch `EOFError`, `ValueError`, `base64.Error`
- Create custom exception hierarchy: `DeckstringError` (base), `InvalidDeckstringError`, `CorruptedDataError`, `UnsupportedVersionError`
- Add bounds checking: verify card counts > 0, hero IDs are valid DBF ranges
- Validate deckstring length before decoding (reject empty strings, impossibly short buffers)
- Handle trailing garbage bytes after parsing completes

### 2. Deck validation (Critical)
**Changes needed:**
- Add `validate()` method to `Deck` class that checks:
  - Total card count matches format rules (30 for Standard, 40 for Twist, etc.)
  - Card copy limits (max 2 for most cards, 1 for Legendaries)
  - Hero class matches card class restrictions
  - Format legality (no Wild cards in Standard decks)
- Accept optional `CardDatabase` parameter to cross-reference card metadata
- Return detailed validation result object (not just bool) with specific rule violations
- Add `strict` parameter to `from_deckstring()` to optionally validate during parsing

### 3. Test coverage (Critical)
**Changes needed:**
- Create `test_deckstring.py` with pytest fixtures for:
  - Known valid deckstrings from official Blizzard API
  - Round-trip tests (parse → encode → parse should be identical)
  - Edge cases: empty decks, max-size decks, all sideboards
  - Malformed input: truncated bytes, wrong version, invalid base64
  - Version upgrade scenarios (v1 → hypothetical v2)
- Add property-based tests with Hypothesis for fuzzing
- Measure code coverage, target 95%+

### 4. Documentation (High)
**Changes needed:**
- Add module-level docstring explaining deckstring format specification
- Document each function with:
  - Purpose and algorithm summary
  - Parameter types and constraints
  - Return value structure
  - Raises clauses for exceptions
  - Example usage
- Create `examples/` directory with common use cases:
  - Parsing a deckstring from clipboard
  - Building a deck programmatically
  - Modifying an existing deck
- Link to official Blizzard format documentation or HearthSim wiki

### 5. Complete type annotations (High)
**Changes needed:**
- Add return type hints to `_read_varint()` and `_write_varint()`
- Annotate `stream` parameters with `typing.BinaryIO` (more specific than `IO`)
- Use `TypeAlias` for complex types: `CardIncludeList`, `SideboardList`
- Add `@overload` signatures for functions with multiple valid call patterns
- Run mypy in strict mode and fix all warnings

### 6. Logging infrastructure (High)
**Changes needed:**
- Import `logging` module, create module-level logger
- Log at DEBUG level: varint reads/writes, card counts, encoding steps
- Log at INFO level: successful parse/encode operations with deck summaries
- Log at WARNING level: deprecated features, suspicious data patterns
- Log at ERROR level: parsing failures with hex dump of problematic bytes
- Make logging optional via module-level `enable_logging()` toggle

### 7. Remove hero count restriction (High)
**Changes needed:**
- Replace `if len(heroes) != 1: raise ValueError` with configurable validator
- Add `max_heroes` parameter to `write_deckstring()` (default 1 for backward compatibility)
- Update `Deck.as_deckstring` to respect multi-hero scenarios
- Document which Hearthstone game modes support multiple heroes (Duels, Battlegrounds)

### 8. Performance optimization (Medium)
**Changes needed:**
- Cache sorted card lists in `Deck` class, invalidate on mutation
- Use `tuple` instead of `list` for immutable card data (hashable, faster)
- Profile with `cProfile` on large deck collections (1000+ decks)
- Consider `__slots__` for `Deck` class to reduce memory overhead
- Benchmark against HearthSim's reference implementation

### 9. Deck manipulation methods (Medium)
**Changes needed:**
- Add to `Deck` class:
  - `add_card(dbf_id: int, count: int = 1) -> None`
  - `remove_card(dbf_id: int, count: int = 1) -> None`
  - `get_card_count(dbf_id: int) -> int`
  - `calculate_dust_cost(collection: CardDatabase) -> int`
  - `to_dict() -> dict` for JSON serialization
  - `__eq__()`, `__hash__()` for deck comparison
- Implement change tracking for undo/redo support

### 10. Format conversion (Medium)
**Changes needed:**
- Add `export_json()` method returning HearthSim JSON schema
- Add `export_hearthpwn()` for HearthPwn deck code format
- Create `from_json()` class method for import
- Support clipboard integration (detect format automatically)

### 11. Document enum dependency (Medium)
**Changes needed:**
- Either vendor `enums.py` in documentation or make it part of this module
- Add comments showing example `FormatType` values:
  ```python
  # FT_UNKNOWN = 0
  # FT_WILD = 1
  # FT_STANDARD = 2
  # FT_CLASSIC = 3
  # FT_TWIST = 4
  ```
- Consider replacing enum with `typing.Literal` for self-contained module

---

**Estimated effort:** 3-5 days for a senior developer to address critical + high-priority gaps. Medium-priority items could be deferred to v2.0.