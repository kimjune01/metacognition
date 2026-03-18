# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements Blizzard's **deckstring format** for encoding and decoding Hearthstone deck compositions. Current working capabilities:

1. **Base64 decoding/encoding** of compressed deck data
2. **Varint serialization** for efficient integer storage (variable-length encoding)
3. **Bidirectional conversion**: deckstring ↔ structured deck representation
4. **Deck composition parsing**: extracts cards (with counts), heroes, and game format
5. **Sideboard support**: handles sideboard cards with ownership tracking (for game modes that support them)
6. **Count-based optimization**: separates cards into 1×, 2×, and N× buckets to minimize encoding size
7. **Sorting/normalization**: deterministic output ordering for cards and sideboards
8. **Type annotations**: partial typing with `List`, `Tuple`, `Optional`, `Sequence`
9. **Format validation**: checks deckstring version and format type enum

The code successfully handles the core use case: round-tripping deck data between human-readable card lists and compact deckstring format.

---

## Triage

### Critical gaps (blocks production use)

1. **No error recovery for malformed input** — invalid base64, truncated streams, or corrupted varints crash with cryptic exceptions
2. **Hero count hardcoded to 1** — raises `ValueError` for multi-hero formats (Duels, Twist), but these are valid in modern Hearthstone
3. **No input validation** — accepts negative card counts, invalid DBF IDs, or duplicate entries without checking
4. **Silent data loss** — if `data` has trailing bytes after parsing, they're ignored (could indicate corruption)

### High-priority gaps (affects reliability)

5. **No logging or diagnostics** — when parsing fails, you get a stack trace with no context about *which* deck or *where* in the binary stream
6. **Tight coupling to `FormatType` enum** — if Blizzard adds a new format, this code rejects valid deckstrings instead of gracefully handling unknowns
7. **No round-trip testing** — missing validation that `parse(write(deck)) == deck`
8. **Undocumented magic numbers** — `\0` header, version `1`, varint encoding rules are unexplained

### Medium-priority gaps (code quality)

9. **Incomplete type coverage** — `IO` is too generic (should be `IO[bytes]`); missing return type on `_write_varint`
10. **Inconsistent error types** — raises `ValueError`, `EOFError`, and implicit `KeyError` from enum lookup with no structure
11. **Mutable default argument** — `sideboards: Optional[SideboardList] = None` in `write_deckstring` is correct, but the pattern appears risky elsewhere
12. **No docstrings** — functions lack parameter descriptions and examples

### Low-priority gaps (polish)

13. **No CLI or usage examples** — developers must read source to understand how to use it
14. **Redundant sorting** — `cards.sort()` after already sorting sublists in `write_deckstring`
15. **Variable shadowing** — `list` used as variable name (line 94, 97, 99) shadows built-in

---

## Plan

### 1. Error recovery for malformed input
**Change**: Wrap `base64.b64decode` and varint reads in try/except blocks.  
**Specifics**:
- Add `try: decoded = base64.b64decode(deckstring)` with `except binascii.Error as e: raise ValueError("Invalid base64 in deckstring") from e`
- In `_read_varint`, catch `ord(c)` on empty string before `EOFError` check
- Add a custom exception `DeckstringParseError(ValueError)` with fields for context (e.g., `offset`, `section`)

### 2. Remove hero count restriction
**Change**: Delete lines 181–182 (`if len(heroes) != 1: raise ValueError...`).  
**Specifics**:
- Remove hardcoded check
- Add comment: `# Multiple heroes supported for Duels, Twist, etc.`
- Update tests to include 2-hero and 3-hero decks

### 3. Input validation
**Change**: Add a `validate_deck()` method to `Deck` class.  
**Specifics**:
```python
def validate_deck(self) -> None:
    for cardid, count in self.cards:
        if cardid < 1: raise ValueError(f"Invalid card ID {cardid}")
        if count < 1: raise ValueError(f"Invalid count {count} for card {cardid}")
    # Check for duplicates
    seen = set()
    for cardid, _ in self.cards:
        if cardid in seen: raise ValueError(f"Duplicate card {cardid}")
        seen.add(cardid)
```
- Call `validate_deck()` in `Deck.as_deckstring` property before encoding

### 4. Detect trailing data
**Change**: After parsing sideboards, check `data.tell() == len(decoded)`.  
**Specifics**:
```python
remaining = len(decoded) - data.tell()
if remaining > 0:
    raise ValueError(f"{remaining} unexpected bytes at end of deckstring")
```

### 5. Add structured logging
**Change**: Import `logging` and add checkpoint logs.  
**Specifics**:
```python
logger = logging.getLogger(__name__)

# In parse_deckstring:
logger.debug(f"Parsing deckstring version={version}, format={format}")
logger.debug(f"Parsed {len(cards)} cards, {len(heroes)} heroes")
```
- Add offset tracking: `offset = data.tell()` before each section, include in error messages

### 6. Graceful format handling
**Change**: Replace `FormatType(format)` with try/except that defaults to `FT_UNKNOWN`.  
**Specifics**:
```python
try:
    format = FormatType(format)
except ValueError:
    logger.warning(f"Unknown format {format}, treating as FT_UNKNOWN")
    format = FormatType.FT_UNKNOWN
```
- Remove the `raise ValueError` for unsupported formats (line 173)

### 7. Round-trip testing
**Change**: Add `test_roundtrip()` in a new `test_deckstrings.py`.  
**Specifics**:
```python
def test_roundtrip():
    original = "AAECAa0GBq8E..."  # Known valid deckstring
    deck = Deck.from_deckstring(original)
    reconstructed = deck.as_deckstring
    assert reconstructed == original
```
- Include edge cases: empty decks, max counts, sideboards

### 8. Document magic numbers
**Change**: Add module-level constants and comments.  
**Specifics**:
```python
DECKSTRING_HEADER = b"\0"  # Reserved byte, always 0x00
DECKSTRING_VERSION = 1     # Current format version
SIDEBOARDS_PRESENT = b"\1" # Flag byte for sideboard section
```
- Replace inline `b"\0"` and `b"\1"` with named constants

### 9. Improve type annotations
**Change**: Use `IO[bytes]` instead of `IO`, add return types.  
**Specifics**:
```python
def _read_varint(stream: IO[bytes]) -> int: ...
def _write_varint(stream: IO[bytes], i: int) -> int: ...  # Returns bytes written
```
- Run `mypy --strict` and fix remaining issues

### 10. Standardize exception types
**Change**: Create exception hierarchy.  
**Specifics**:
```python
class DeckstringError(Exception): pass
class DeckstringParseError(DeckstringError): pass
class DeckstringValidationError(DeckstringError): pass
```
- Replace all `ValueError` raises in parsing with `DeckstringParseError`
- Use `DeckstringValidationError` for `validate_deck()` failures

### 11. Fix mutable defaults
**Change**: Already correct (`sideboards: Optional[SideboardList] = None`), but audit all function signatures.  
**Specifics**: No action needed if `None` is used consistently. Document the pattern in a comment.

### 12. Add docstrings
**Change**: Write Google-style docstrings for public functions.  
**Specifics**:
```python
def parse_deckstring(deckstring: str) -> Tuple[...]:
    """Parse a Hearthstone deckstring into structured components.
    
    Args:
        deckstring: Base64-encoded deck data (e.g., "AAECAa0GBq8E...")
    
    Returns:
        Tuple of (cards, heroes, format, sideboards)
        - cards: List of (dbf_id, count) tuples
        - heroes: List of hero dbf_ids
        - format: FormatType enum value
        - sideboards: List of (dbf_id, count, owner_dbf_id) tuples
    
    Raises:
        DeckstringParseError: If deckstring is malformed or unsupported
    """
```

### 13. Add CLI/examples
**Change**: Create `if __name__ == "__main__":` block.  
**Specifics**:
```python
if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: deckstrings.py <deckstring>")
        sys.exit(1)
    deck = Deck.from_deckstring(sys.argv[1])
    print(f"Format: {deck.format}")
    print(f"Heroes: {deck.heroes}")
    print(f"Cards: {deck.get_dbf_id_list()}")
```

### 14. Remove redundant sorting
**Change**: Delete `cards.sort()` on line 211 (already sorted by `trisort_cards` and subsequent loops).  
**Specifics**: Verify sort stability with tests, then remove.

### 15. Rename shadowing variables
**Change**: Replace `list = cards_x1` with `target_list = cards_x1` (lines 94–99).  
**Specifics**:
```python
if count == 1:
    target_list = cards_x1
elif count == 2:
    target_list = cards_x2
else:
    target_list = cards_xn
```

---

**Priority order for implementation**: 1 → 2 → 3 → 4 → 7 → 5 → 6 → 9 → 10 → 12 → 8 → 13 → 15 → 14 → 11.