# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the **Blizzard Deckstring format** for encoding and decoding Hearthstone deck configurations. Current working capabilities:

1. **Deckstring Parsing** (`parse_deckstring`)
   - Decodes base64-encoded deck strings
   - Reads varint-encoded binary format
   - Extracts heroes, cards with counts, format type, and sideboards
   - Returns structured data: `(cards, heroes, format, sideboards)`

2. **Deckstring Writing** (`write_deckstring`)
   - Encodes deck data into Blizzard's binary format
   - Handles card count optimization (groups cards by 1x, 2x, Nx)
   - Supports optional sideboard data
   - Returns base64-encoded string

3. **Deck Class** (convenience wrapper)
   - Constructs from deckstring via `from_deckstring()`
   - Stores parsed components (cards, heroes, format, sideboards)
   - Provides `as_deckstring` property for re-encoding
   - Offers sorted access methods: `get_dbf_id_list()`, `get_sideboard_dbf_id_list()`

4. **Binary Encoding Utilities**
   - Varint read/write for compact integer encoding
   - Trisort optimization (groups cards by count for smaller encoding)

5. **Format Support**
   - Version 1 deckstring format
   - FormatType enum integration (Wild, Standard, etc.)
   - Sideboard support for game modes that use them

## Triage

### Critical Gaps

1. **No Validation** - No checks that deck follows game rules (30 cards, max 2x per card, class restrictions, format legality)
2. **No Error Context** - Parsing failures give minimal debug info (which byte offset failed, what was expected)
3. **No Card Database Integration** - Cannot resolve DBF IDs to card names/properties or validate card existence

### Important Gaps

4. **Incomplete Type Hints** - Return types use tuples instead of structured types (reduces type safety)
5. **No Deck Comparison** - Cannot diff decks, check equality, or compute similarities
6. **No Export Formats** - Only supports Blizzard format (no HSReplay, Hearthpwn, human-readable formats)
7. **No Deck Metadata** - Cannot attach deck name, author, description, archetype, or creation date

### Nice-to-Have Gaps

8. **No Deck Statistics** - Cannot compute mana curve, dust cost, class distribution
9. **No Mutation Methods** - `Deck` class is append-only (no `add_card()`, `remove_card()`, `replace_card()`)
10. **Limited Documentation** - Docstrings missing, format specification not documented
11. **No CLI/Examples** - No example usage or command-line tool for quick conversions

## Plan

### 1. Validation [Critical]

**What to add:**
- `Deck.validate()` method that checks:
  - Exactly 1 hero (already enforced in write, but not read)
  - 30 cards total for Standard/Wild (sum all counts)
  - Max 2 copies per card (except Legendaries: 1 copy)
  - Cards belong to hero's class or neutral
  - Cards legal in specified format
- Raise `DeckValidationError` with specific rule violated
- Add optional `strict=False` parameter to `from_deckstring()` to skip validation

**Files to change:**
- Add `class DeckValidationError(ValueError)` 
- Add validation logic to `Deck.validate()` (requires card database - see #3)
- Call `validate()` in `from_deckstring()` if strict mode enabled

### 2. Error Context [Critical]

**What to add:**
- Wrap parsing in try/except to catch `EOFError`, `ValueError`, `struct.error`
- Include byte offset in error messages: `"Failed at byte 15: expected hero count"`
- Add `DeckstringParseError` exception with `.offset`, `.raw_data`, `.partial_result` attributes
- Log partial parse state before raising (heroes parsed, cards so far)

**Files to change:**
- Add exception class with context fields
- Modify `parse_deckstring()` to track `bytes_read` counter
- Wrap each `_read_varint()` section with descriptive error handling

### 3. Card Database Integration [Critical]

**What to add:**
- `CardDatabase` class or integration with HearthstoneJSON
- Lookup methods: `get_card_by_dbf_id(id)` → `{name, rarity, class, cost, ...}`
- Use for validation (check card existence, class matching, format legality)
- Optional: lazy-load database from JSON file or remote URL

**Files to change:**
- Create `cards.py` with database abstraction
- Modify `Deck.validate()` to use database
- Add optional `card_db` parameter to `Deck` constructor
- Update `get_dbf_id_list()` to optionally return enriched data with card names

### 4. Structured Return Types [Important]

**What to change:**
- Replace `CardIncludeList = List[Tuple[int, int]]` with `@dataclass class CardEntry`
- Replace `SideboardList` tuples with `@dataclass class SideboardEntry`
- Change `parse_deckstring()` return type from 4-tuple to structured object
- Update `Deck` to use these types internally

**Example:**
```python
@dataclass
class CardEntry:
    dbf_id: int
    count: int

@dataclass
class SideboardEntry:
    dbf_id: int
    count: int
    owner_dbf_id: int
```

### 5. Deck Comparison [Important]

**What to add:**
- `Deck.__eq__()` - exact equality (same cards, counts, hero, format)
- `Deck.similarity(other)` - float [0.0, 1.0] based on card overlap (Jaccard similarity)
- `Deck.diff(other)` - returns added/removed/changed cards
- `Deck.__hash__()` - for use in sets/dicts (hash sorted card list)

**Files to change:**
- Add methods to `Deck` class
- Consider normalizing sideboards for comparison

### 6. Export Formats [Important]

**What to add:**
- `Deck.to_text()` - human-readable format:
  ```
  ### Deck Name
  # Class: Hunter
  # Format: Standard
  # 2x Arcane Shot
  # 1x Rexxar
  ```
- `Deck.from_text()` - parse text format
- `Deck.to_json()` / `from_json()` for API interop
- Support HSReplay/Hearthpwn URL generation

**Files to change:**
- Add conversion methods to `Deck`
- Create `formats.py` for format-specific logic

### 7. Deck Metadata [Important]

**What to add:**
- Fields: `name: str`, `author: str`, `description: str`, `created_at: datetime`, `archetype: str`
- Store as JSON in separate file or database (not in deckstring itself)
- `Deck.metadata` property returning dict
- Optional: embed metadata in deckstring comment field (if format supports)

**Files to change:**
- Add optional metadata fields to `Deck.__init__()`
- Update serialization methods to handle metadata
- Metadata not encoded in deckstring (stored separately)

### 8. Deck Statistics [Nice-to-have]

**What to add:**
- `Deck.stats()` returning:
  - `mana_curve: List[int]` (count per mana cost 0-10+)
  - `dust_cost: int` (total crafting cost)
  - `class_distribution: Dict[str, int]` (neutral vs class cards)
  - `rarity_distribution: Dict[str, int]`
- Requires card database integration (gap #3)

**Files to change:**
- Add `Deck.stats()` method
- Depends on `CardDatabase` being available

### 9. Mutation Methods [Nice-to-have]

**What to add:**
- `Deck.add_card(dbf_id, count=1)` - adds or increments card
- `Deck.remove_card(dbf_id, count=1)` - decrements or removes card
- `Deck.replace_card(old_id, new_id, count=None)` - swap cards
- `Deck.clear()` - remove all cards
- Each method validates deck remains legal (optional)

**Files to change:**
- Add methods to `Deck` class
- Update internal `self.cards` list
- Invalidate cached `as_deckstring` if implemented

### 10. Documentation [Nice-to-have]

**What to add:**
- Module docstring explaining Blizzard deckstring format
- Docstrings for all public functions/methods
- Link to format specification (HearthSim wiki)
- Type hints for all parameters (already partially done)

**Files to change:**
- Add docstrings throughout
- Create `README.md` or `docs/` with format specification and examples

### 11. CLI & Examples [Nice-to-have]

**What to add:**
- CLI tool: `python -m deckstring decode <deckstring>`
- CLI tool: `python -m deckstring encode --cards 123,456 --hero 789`
- Example scripts in `examples/` directory
- Unit tests demonstrating usage patterns

**Files to change:**
- Create `__main__.py` for CLI entry point
- Add argparse-based interface
- Create `examples/` with sample decks and conversion scripts

---

**Priority Implementation Order:**
1. Error context (#2) - low-hanging fruit, high impact
2. Validation framework (#1) - critical for production use
3. Card database integration (#3) - enables validation and stats
4. Export formats (#6) - increases utility significantly
5. Structured types (#4) - improves maintainability
6. Remaining features as needed