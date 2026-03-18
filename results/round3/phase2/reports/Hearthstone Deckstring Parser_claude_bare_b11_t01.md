# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements a **Hearthstone deckstring encoder/decoder** that handles Blizzard's custom binary format for sharing deck configurations. Current working capabilities:

1. **Binary varint I/O** - Reads and writes variable-length integers using 7-bit encoding with continuation bits
2. **Base64 decoding** - Parses deckstrings from their standard base64-encoded format
3. **Complete deck structure parsing**:
   - Version and format type validation
   - Hero card extraction
   - Main deck cards (optimized by count: 1×, 2×, n×)
   - Sideboard cards with owner references
4. **Base64 encoding** - Serializes decks back to deckstring format
5. **Card organization** - Sorts and groups cards by inclusion count for optimal encoding
6. **Object-oriented interface** - `Deck` class with `from_deckstring()` factory and `as_deckstring` property
7. **Type hints** - Full type annotations for public API

## Triage

### Critical Gaps

1. **No error handling for malformed data** - Parsing can fail silently or with cryptic errors
   - Missing bounds checking on varint reads
   - No validation of card counts, hero counts, or format values
   - EOF handling only in `_read_varint`, not in fixed-byte reads

2. **No validation of deck legality** - Accepts structurally valid but game-invalid decks
   - No max deck size enforcement (30 cards standard)
   - No card count limits (2 copies for non-legendary)
   - No format-specific restrictions

3. **Incomplete sideboard support** - Sideboards exist but lack context
   - No documentation on what sideboards are used for
   - No validation of sideboard owner references

### Important Gaps

4. **No card/hero metadata integration** - Works with raw DBF IDs only
   - Cannot validate card IDs exist
   - Cannot resolve card names
   - Cannot check if heroes match deck class requirements

5. **Limited format type handling** - Enum exists but isn't leveraged
   - No format-specific validation rules
   - No human-readable format names

6. **No export formats** - Only deckstring I/O
   - Cannot export to JSON, YAML, or human-readable lists
   - No import from other formats

### Minor Gaps

7. **No logging or debugging support** - Binary parsing failures are opaque
8. **No round-trip testing utilities** - Cannot verify encode/decode fidelity
9. **Missing docstrings** - Public API lacks documentation
10. **No CLI interface** - Must be used as library only

## Plan

### 1. Add Comprehensive Error Handling

**File:** `deckstring.py`

**Changes needed:**

- Wrap `parse_deckstring()` in try/except to catch `EOFError`, `struct.error`, `ValueError`
- Add custom exception classes:
  ```python
  class DeckstringError(Exception): pass
  class InvalidDeckstring(DeckstringError): pass
  class UnsupportedVersion(DeckstringError): pass
  class MalformedData(DeckstringError): pass
  ```
- In `_read_varint()`, add counter to prevent infinite loops:
  ```python
  max_bytes = 10  # 64-bit int max
  if shift >= max_bytes * 7:
      raise MalformedData("Varint exceeds maximum length")
  ```
- In `parse_deckstring()`, validate data length before each `data.read()`:
  ```python
  remaining = len(decoded) - data.tell()
  if remaining < expected_bytes:
      raise MalformedData(f"Unexpected EOF at byte {data.tell()}")
  ```

### 2. Implement Deck Validation

**File:** `deckstring.py` (add new module `validation.py` if preferred)

**Changes needed:**

- Add `Deck.validate()` method that checks:
  ```python
  def validate(self, strict=True) -> List[str]:
      errors = []
      
      # Hero count
      if len(self.heroes) != 1:
          errors.append(f"Expected 1 hero, got {len(self.heroes)}")
      
      # Deck size (standard=30, arena=variable, etc.)
      total_cards = sum(count for _, count in self.cards)
      if strict and total_cards != 30:
          errors.append(f"Expected 30 cards, got {total_cards}")
      
      # Card count limits
      for card_id, count in self.cards:
          if count > 2 and not is_legendary(card_id):  # needs card DB
              errors.append(f"Card {card_id} exceeds copy limit")
      
      return errors
  ```
- Add `is_valid()` convenience method: `return len(self.validate()) == 0`
- Optionally auto-validate in `from_deckstring()` with `validate=True` parameter

### 3. Document Sideboard System

**File:** `deckstring.py`

**Changes needed:**

- Add module-level docstring explaining sideboards:
  ```python
  """
  Sideboards are used in specific Hearthstone formats (e.g., Duels) where
  certain cards enable additional card choices. The sideboard_owner field
  references the DBF ID of the card that "owns" the sideboard cards.
  """
  ```
- Add `Deck.get_sideboard_for_owner(owner_id: int)` method to query sideboards
- Document sideboard format in `SideboardList` type alias

### 4. Integrate Card Database

**File:** `cards.py` (new), update `deckstring.py`

**Changes needed:**

- Create card database interface:
  ```python
  class CardDatabase:
      def get_card(self, dbf_id: int) -> Optional[Card]:
          pass  # Load from JSON/DB
      
      def is_legendary(self, dbf_id: int) -> bool:
          card = self.get_card(dbf_id)
          return card and card.rarity == Rarity.LEGENDARY
  ```
- Add optional `card_db` parameter to `Deck.__init__()`
- Implement `Deck.get_card_names()` → `List[str]` using card DB
- Add `Deck.validate()` card ID existence checks when DB available

### 5. Add Human-Readable Export

**File:** `deckstring.py`

**Changes needed:**

- Add `Deck.to_dict()` method:
  ```python
  def to_dict(self, include_names=False) -> dict:
      return {
          "format": self.format.name,
          "heroes": self.heroes,
          "cards": [{"id": cid, "count": cnt} for cid, cnt in self.cards],
          "sideboards": [{"id": cid, "count": cnt, "owner": own} 
                        for cid, cnt, own in self.sideboards]
      }
  ```
- Add `Deck.from_dict(data: dict)` factory method
- Add `Deck.__str__()` for pretty-printing:
  ```python
  def __str__(self) -> str:
      lines = [f"Format: {self.format.name}"]
      lines.append(f"Hero: {self.heroes[0]}")
      lines.append("Cards:")
      for card_id, count in self.cards:
          lines.append(f"  {count}x {card_id}")
      return "\n".join(lines)
  ```

### 6. Add Round-Trip Testing

**File:** `test_deckstring.py` (new)

**Changes needed:**

- Create test fixtures with known-good deckstrings
- Test encode→decode→encode produces identical output:
  ```python
  def test_roundtrip():
      original = "AAECAa0GBo..."
      deck = Deck.from_deckstring(original)
      reencoded = deck.as_deckstring
      assert original == reencoded
  ```
- Test error cases (truncated data, invalid version, bad format)
- Fuzz test with random binary data

### 7. Add Logging

**File:** `deckstring.py`

**Changes needed:**

- Add `import logging` and create logger: `logger = logging.getLogger(__name__)`
- Log parse stages: `logger.debug(f"Parsed {num_heroes} heroes: {heroes}")`
- Log validation failures: `logger.warning(f"Deck validation failed: {errors}")`
- Add optional `debug=False` parameter to `parse_deckstring()`

### 8. Create CLI Interface

**File:** `__main__.py` (new)

**Changes needed:**

- Use `argparse` to handle subcommands:
  ```python
  parser.add_argument("command", choices=["decode", "encode", "validate"])
  parser.add_argument("deckstring", help="Deckstring to process")
  ```
- Implement commands:
  - `decode` → pretty-print deck contents
  - `encode` → read JSON, output deckstring
  - `validate` → check deck legality, exit 0/1
- Add `python -m deckstring decode AAE...` entry point