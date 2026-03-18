# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements the Blizzard Deckstring format for encoding and decoding Hearthstone deck configurations. Current working capabilities:

1. **Decoding deckstrings** - Parses base64-encoded binary strings into structured deck data including:
   - Card lists with DBF IDs and counts (1x, 2x, or Nx)
   - Hero cards (currently supports exactly 1 hero)
   - Format type (Wild, Standard, etc.)
   - Sideboard cards with owner references

2. **Encoding deckstrings** - Converts deck data back into base64-encoded binary format

3. **Varint I/O** - Implements variable-length integer encoding/decoding for compact binary representation

4. **Card organization** - Sorts cards into three buckets (1x, 2x, Nx) for efficient encoding

5. **Deck object interface** - Provides a `Deck` class with:
   - Factory method `from_deckstring()`
   - Property `as_deckstring` for serialization
   - Getters for sorted card and sideboard lists

6. **Format validation** - Checks header bytes and version numbers, validates FormatType enum values

## Triage

### Critical Gaps

1. **No error recovery or validation** - The parser fails hard on malformed input without helpful diagnostics. Production systems need to handle corrupt data, truncated strings, and invalid card counts gracefully.

2. **Missing multi-hero support** - The code explicitly rejects decks with `!= 1` heroes, but Hearthstone has game modes (Duels, Arena variants) that use multiple heroes. The parser reads N heroes but the writer rejects anything but 1.

3. **No round-trip tests** - No verification that `parse_deckstring(write_deckstring(...))` produces identical output.

### Important Gaps

4. **Incomplete type hints** - The module uses some typing but inconsistently. Return type `(Tuple[...])` in `parse_deckstring` should be proper tuple syntax. Several internal functions lack hints.

5. **No card database integration** - The system works with raw DBF IDs but provides no way to resolve them to card names, validate card legality for formats, or check deck construction rules (30 card minimum, class restrictions, etc.).

6. **Limited documentation** - No docstrings explaining the binary format structure, no examples showing typical usage patterns.

7. **No handling of unknown future versions** - If deckstring version > 1 appears, the parser rejects it entirely rather than attempting forward compatibility.

### Minor Gaps

8. **Bare `except ValueError` clauses could mask bugs** - The format validation catches ValueError but doesn't distinguish between "unsupported format" vs "corrupted data".

9. **Inefficient sorting** - Multiple sorts happen during encoding (heroes, cards, sideboards) when one consolidated sort could suffice.

10. **No CLI or standalone utility** - No way to use this as a command-line tool for inspecting or converting deckstrings.

11. **Hardcoded magic values** - The `\0` and `\1` bytes for header/sideboard flags aren't named constants.

## Plan

### For Gap 1 (Error recovery)

**Changes needed:**
- Add custom exception classes: `InvalidDeckstringError`, `CorruptedDataError`, `UnsupportedVersionError`
- In `parse_deckstring()`, wrap each section in try/except blocks that provide context (e.g., "Failed while parsing heroes section at byte offset 5")
- Add validation after parsing: verify card counts are positive, check that the stream consumed all bytes (no trailing garbage)
- Add `strict=True` parameter to `from_deckstring()` - when False, skip invalid cards rather than failing the entire parse

**Example:**
```python
class InvalidDeckstringError(Exception):
    def __init__(self, message: str, offset: int):
        super().__init__(f"{message} at byte {offset}")
        self.offset = offset
```

### For Gap 2 (Multi-hero support)

**Changes needed:**
- In `write_deckstring()`, change the validation from:
  ```python
  if len(heroes) != 1:
      raise ValueError("Unsupported hero count %i" % (len(heroes)))
  ```
  to:
  ```python
  if not (1 <= len(heroes) <= 2):  # Or whatever the actual max is
      raise ValueError("Hero count must be 1-2, got %i" % (len(heroes)))
  ```
- Add a mode parameter or auto-detect based on hero count
- Update tests to cover 0-hero (maybe valid?), 1-hero, and 2-hero cases

### For Gap 3 (Round-trip testing)

**Changes needed:**
- Create new file `test_deckstring.py` with pytest fixtures:
  ```python
  @pytest.mark.parametrize("deckstring", [
      "AAECAf0ECowC...",  # Standard mage deck
      "AAECAZICHk...",    # Wild deck with sideboards
  ])
  def test_roundtrip(deckstring):
      cards, heroes, fmt, sideboards = parse_deckstring(deckstring)
      reconstructed = write_deckstring(cards, heroes, fmt, sideboards)
      assert reconstructed == deckstring
  ```
- Test edge cases: empty deck, max card counts, all three card count buckets

### For Gap 4 (Type hints)

**Changes needed:**
- Replace function signature:
  ```python
  def parse_deckstring(deckstring) -> (Tuple[...]):
  ```
  with:
  ```python
  def parse_deckstring(deckstring: str) -> Tuple[CardIncludeList, CardList, FormatType, SideboardList]:
  ```
- Add hints to `_read_varint(stream: IO[bytes]) -> int` (currently accepts text IO)
- Add return type to `trisort_cards() -> Tuple[List[tuple], List[tuple], List[tuple]]` - make the tuples more specific with TypedDict or use `Tuple[Tuple[int, int], ...]`

### For Gap 5 (Card database)

**Changes needed:**
- Create new module `cards.py` with:
  ```python
  @dataclass
  class CardDef:
      dbf_id: int
      name: str
      card_class: str
      cost: int
      # ... other fields
  
  class CardDatabase:
      def load_from_json(self, path: str) -> None: ...
      def get_card(self, dbf_id: int) -> Optional[CardDef]: ...
      def validate_deck(self, deck: Deck) -> List[str]: ...  # Returns validation errors
  ```
- Add optional `card_db` parameter to `Deck.__init__()` to enable validation
- Provide a method `Deck.get_card_names()` that returns human-readable card list

### For Gap 6 (Documentation)

**Changes needed:**
- Add module docstring explaining:
  - What deckstrings are and why they exist
  - Link to Blizzard's format specification (if public)
  - Example usage: `deck = Deck.from_deckstring("AAE...")`
- Add docstring to `parse_deckstring()` documenting the binary format:
  ```
  Binary format:
    - 1 byte: Reserved (always 0x00)
    - varint: Version (currently 1)
    - varint: Format enum value
    - varint: Number of heroes N, followed by N varints for hero DBF IDs
    - varint: Number of 1x cards, followed by card DBF IDs
    - varint: Number of 2x cards, followed by card DBF IDs
    - varint: Number of Nx cards, followed by (DBF ID, count) pairs
    - 1 byte: Has sideboards flag (0x00 or 0x01)
    - If has sideboards: similar structure with (DBF ID, count, owner) tuples
  ```

### For Gap 7 (Forward compatibility)

**Changes needed:**
- Change version check from hard rejection:
  ```python
  if version != DECKSTRING_VERSION:
      raise ValueError("Unsupported deckstring version %r" % (version))
  ```
  to version-aware parsing:
  ```python
  if version > DECKSTRING_VERSION:
      raise ValueError("Deckstring version %r is newer than supported %r" % 
                      (version, DECKSTRING_VERSION))
  elif version < DECKSTRING_VERSION:
      return _parse_legacy_version(data, version)
  ```

### For Gap 8 (Exception specificity)

**Changes needed:**
- Replace:
  ```python
  except ValueError:
      raise ValueError("Unsupported FormatType in deckstring %r" % (format))
  ```
  with:
  ```python
  except ValueError as e:
      if "is not a valid FormatType" in str(e):
          raise InvalidDeckstringError(f"Unknown format type {format}", data.tell())
      raise  # Re-raise unexpected ValueErrors
  ```

### For Gap 9 (Sort optimization)

**Changes needed:**
- In `write_deckstring()`, remove individual `sorted()` calls:
  ```python
  for hero in sorted(heroes):  # Remove sort here
      _write_varint(data, hero)
  ```
- Add single sort at the beginning:
  ```python
  heroes = sorted(heroes)
  cards = sorted(cards, key=lambda x: (x[1], x[0]))  # Sort by count, then ID
  ```

### For Gap 10 (CLI utility)

**Changes needed:**
- Add `__main__.py` or make module executable:
  ```python
  if __name__ == "__main__":
      import sys
      if len(sys.argv) < 2:
          print("Usage: python -m deckstrings <deckstring>")
          sys.exit(1)
      
      deck = Deck.from_deckstring(sys.argv[1])
      print(f"Format: {deck.format.name}")
      print(f"Heroes: {deck.heroes}")
      print(f"Cards ({len(deck.cards)}):")
      for dbf_id, count in deck.get_dbf_id_list():
          print(f"  {count}x {dbf_id}")
  ```

### For Gap 11 (Magic values)

**Changes needed:**
- At module level, add:
  ```python
  _DECKSTRING_HEADER = b"\0"
  _HAS_SIDEBOARDS_TRUE = b"\1"
  _HAS_SIDEBOARDS_FALSE = b"\0"
  ```
- Replace literals: `data.write(b"\0")` → `data.write(_DECKSTRING_HEADER)`