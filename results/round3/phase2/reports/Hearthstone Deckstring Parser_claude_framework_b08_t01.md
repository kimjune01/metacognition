# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements Blizzard's deckstring format for Hearthstone deck encoding/decoding. Current working capabilities:

1. **Decoding deckstrings** - Parses base64-encoded deckstrings into structured deck data (cards, heroes, format, sideboards)
2. **Encoding deckstrings** - Serializes deck data back into the deckstring format
3. **Varint I/O** - Implements variable-length integer encoding/decoding for compact representation
4. **Card organization** - Separates cards by quantity (1x, 2x, n×) for efficient encoding
5. **Format type support** - Handles game format metadata (FT_UNKNOWN enum reference)
6. **Hero validation** - Enforces single-hero constraint during encoding
7. **Sideboard support** - Handles optional sideboard cards with owner tracking (version 1 format)
8. **Sorting utilities** - Provides sorted card lists via `get_dbf_id_list()` and `get_sideboard_dbf_id_list()`

The core encode/decode roundtrip works correctly for the specified format version (1).

---

## Triage

### Critical Gaps

1. **No error recovery** - Malformed deckstrings crash rather than returning useful errors
2. **Version lock-in** - Only supports version 1; newer versions will fail
3. **Missing validation** - No card count limits, duplicate detection, or format-specific rules

### Important Gaps

4. **No card database integration** - Cannot validate card IDs or resolve names
5. **Limited hero support** - Hard-coded single-hero requirement breaks Duels/multi-hero formats
6. **No type hints for returns** - `parse_deckstring` return type is unparseable by static analyzers
7. **Missing enums module** - `FormatType` import will fail without `enums.py`

### Nice-to-Have Gaps

8. **No CLI interface** - Pure library with no built-in encode/decode tool
9. **No documentation** - Missing docstrings for public API
10. **No logging** - Silent failures make debugging difficult

---

## Plan

### 1. Error Recovery (Critical)

**Current problem:** `EOFError`, `ValueError` exceptions expose implementation details. Binary corruption produces cryptic messages.

**Changes needed:**
- Create custom exception hierarchy: `DeckstringError` (base), `MalformedDeckstringError`, `UnsupportedVersionError`, `InvalidFormatError`
- Wrap `base64.b64decode()` to catch `binascii.Error` and re-raise as `MalformedDeckstringError`
- Add try/except in `parse_deckstring()` to wrap all decode failures with context about which section failed
- Return `Optional[Deck]` from `Deck.from_deckstring()` or make it handle exceptions gracefully

### 2. Version Flexibility (Critical)

**Current problem:** Hard reject on version ≠ 1 prevents forward compatibility.

**Changes needed:**
- Add `strict_version: bool = True` parameter to `parse_deckstring()`
- When `strict_version=False`, emit warning for unknown versions but attempt to parse
- Add version-specific parsing paths: `_parse_v1()`, `_parse_v2()`, etc.
- Store decoded version in `Deck.version` field
- Update `write_deckstring()` to support writing multiple versions

### 3. Deck Validation (Critical)

**Current problem:** Can encode impossible decks (400 legendaries, invalid card counts).

**Changes needed:**
- Add `Deck.validate(format: FormatType) -> List[str]` returning list of violations
- Check total card count (30 for Standard/Wild, 40 for Twist)
- Enforce legendary limit (1 copy max)
- Validate card count ≤ 2 for non-legendaries (except special cases)
- Add `strict: bool` parameter to `Deck.as_deckstring` to gate validation

### 4. Card Database Integration (Important)

**Current problem:** No way to convert "Fireball" → DBF ID or validate IDs exist.

**Changes needed:**
- Create `CardDatabase` class with methods: `get_card(dbf_id)`, `find_by_name(name)`, `is_valid_dbf_id(id)`
- Add optional `db: Optional[CardDatabase]` parameter to `Deck.validate()`
- Implement lazy-loading JSON card database (download from HearthstoneJSON API if missing)
- Add `Deck.from_cardnames(names: List[str], db: CardDatabase)` constructor

### 5. Multi-Hero Support (Important)

**Current problem:** Line 178 hard-rejects `len(heroes) != 1`.

**Changes needed:**
- Remove single-hero assertion
- Add `max_heroes` parameter based on format (1 for Standard, 2 for Duels, 10 for Tavern Brawls)
- Update validation to check hero count against format rules
- Test with multi-hero deckstrings from Arena/Duels

### 6. Type Hint Fixes (Important)

**Current problem:** Return type `(Tuple[CardIncludeList, CardList, FormatType, SideboardList])` is invalid syntax.

**Changes needed:**
```python
# Change line 101 from:
def parse_deckstring(deckstring) -> (
	Tuple[CardIncludeList, CardList, FormatType, SideboardList]
):

# To:
def parse_deckstring(deckstring: str) -> Tuple[
	CardIncludeList, CardList, FormatType, SideboardList
]:
```
Run `mypy` to catch remaining issues.

### 7. Enums Module (Important)

**Current problem:** `from .enums import FormatType` will fail on import.

**Changes needed:**
- Create `enums.py` with:
```python
from enum import IntEnum

class FormatType(IntEnum):
	FT_UNKNOWN = 0
	FT_WILD = 1
	FT_STANDARD = 2
	FT_CLASSIC = 3
	FT_TWIST = 4
```
- Add validation for new format types as Blizzard adds them

### 8. CLI Interface (Nice-to-Have)

**Current problem:** No way to use tool without writing Python code.

**Changes needed:**
- Add `__main__.py`:
```python
import argparse
import sys

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("deckstring", help="Deckstring to decode")
	parser.add_argument("--validate", action="store_true")
	# ... etc
```
- Support both decode (`deckstring` → JSON) and encode (JSON → `deckstring`)

### 9. Documentation (Nice-to-Have)

**Current problem:** No docstrings make API unclear.

**Changes needed:**
- Add module-level docstring explaining deckstring format
- Document each public method with Args/Returns/Raises sections
- Add usage examples in `Deck` class docstring
- Create `README.md` with quickstart guide

### 10. Logging (Nice-to-Have)

**Current problem:** Silent failures during parsing make debugging hard.

**Changes needed:**
- Add `import logging` and create logger: `logger = logging.getLogger(__name__)`
- Log at DEBUG level: version read, section transitions, card counts
- Log at WARNING level: version mismatches in non-strict mode
- Log at ERROR level before raising exceptions

---

**Priority order for implementation:** 1 → 7 → 3 → 2 → 4 → 5 → 9 → 8 → 10 → 6 (type hints can wait since code runs fine without them).