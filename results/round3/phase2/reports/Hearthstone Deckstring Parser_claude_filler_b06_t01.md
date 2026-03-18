# Diagnostic Report: Blizzard Deckstring Format Support

## Observations

This system implements a binary encoding/decoding protocol for Hearthstone deck codes (deckstrings). Current working capabilities:

1. **Bidirectional serialization**: Converts between base64-encoded deckstrings and structured deck objects
2. **Varint encoding**: Implements variable-length integer encoding for compact binary representation
3. **Multi-tier card storage**: Handles cards grouped by count (1×, 2×, n×) for space efficiency
4. **Hero support**: Encodes/decodes hero cards (currently enforces exactly 1 hero)
5. **Format tracking**: Preserves deck format type (Standard, Wild, etc.)
6. **Sideboard support**: Handles optional sideboard cards with owner tracking (likely for Duels/Arena formats)
7. **Sorting and normalization**: Maintains consistent ordering for cards and sideboards
8. **Object-oriented interface**: Provides `Deck` class with convenience methods

The encoding scheme uses:
- Version header (currently v1)
- Format type (enum)
- Hero list
- Three card sections (1-copy, 2-copy, n-copy)
- Optional sideboard flag and sections
- Base64 wrapper around binary protocol

## Triage

### Critical Gaps

1. **No error handling for malformed input** (Priority: HIGH)
   - `EOFError` for truncated streams is the only exception
   - No validation of card counts, DBF IDs, or structural constraints
   - Corrupt deckstrings could cause silent failures or wrong data

2. **Missing test coverage** (Priority: HIGH)
   - No unit tests visible
   - Critical for a binary protocol where off-by-one errors are catastrophic
   - Need round-trip tests, edge cases, malformed input handling

3. **No documentation** (Priority: MEDIUM)
   - Functions lack docstrings
   - Format specification not documented
   - No usage examples for consumers

### Important Gaps

4. **Inflexible hero count restriction** (Priority: MEDIUM)
   - Hard-coded `len(heroes) != 1` validation
   - Breaks if Blizzard adds multi-hero formats
   - Read path supports multiple heroes but write path rejects them

5. **No validation of business rules** (Priority: MEDIUM)
   - No deck size limits (30 cards typical)
   - No duplicate checking (except in sideboards, implicitly)
   - No format-specific card legality checks

6. **Type hints incomplete** (Priority: LOW)
   - Good use of type aliases but missing return types on some methods
   - `_read_varint` and `_write_varint` lack full annotations
   - No `IO[bytes]` specification (currently uses `IO` which accepts str or bytes)

### Minor Gaps

7. **No version negotiation strategy** (Priority: LOW)
   - Rejects any version != 1
   - Future versions will break existing code
   - Should support forward/backward compatibility

8. **Limited introspection** (Priority: LOW)
   - `Deck` class doesn't expose format as property
   - No method to get total card count
   - No validation of deck completeness

9. **Performance not optimized** (Priority: LOW)
   - Multiple sorts during encode/decode
   - Could cache sorted results
   - BytesIO could be replaced with bytearray for write path

## Plan

### 1. Add Comprehensive Error Handling

**Changes needed:**
- Create custom exception hierarchy:
  ```python
  class DeckstringError(ValueError): pass
  class InvalidDeckstringError(DeckstringError): pass
  class UnsupportedVersionError(DeckstringError): pass
  class ValidationError(DeckstringError): pass
  ```
- Wrap `parse_deckstring` in try-except to catch:
  - `base64.binascii.Error` → `InvalidDeckstringError`
  - Unexpected EOF → `InvalidDeckstringError`
  - Invalid varints (negative after decoding) → `InvalidDeckstringError`
- Add validation in `write_deckstring`:
  - Check card counts ≥ 1
  - Check DBF IDs ≥ 0
  - Check hero list not empty
  - Verify sideboard owners exist in deck

**Example:**
```python
def parse_deckstring(deckstring: str):
    try:
        decoded = base64.b64decode(deckstring)
    except Exception as e:
        raise InvalidDeckstringError(f"Invalid base64: {e}") from e
    
    try:
        # ... existing parse logic
        if version > DECKSTRING_VERSION:
            raise UnsupportedVersionError(
                f"Version {version} not supported (max: {DECKSTRING_VERSION})"
            )
    except EOFError as e:
        raise InvalidDeckstringError("Truncated deckstring") from e
```

### 2. Implement Test Suite

**Changes needed:**
- Create `tests/test_deckstring.py` with pytest
- Test categories:
  - **Round-trip tests**: Encode then decode equals original
  - **Known deckstrings**: Decode production deckstrings from Hearthstone
  - **Edge cases**: Empty sideboards, single card, 30× legendary
  - **Malformed input**: Truncated, invalid base64, wrong version
  - **Boundary values**: 0-count cards, negative IDs, missing heroes
- Add property-based tests with Hypothesis:
  ```python
  from hypothesis import given, strategies as st
  
  @given(st.lists(st.tuples(st.integers(1, 10000), st.integers(1, 2))))
  def test_roundtrip_cards(cards):
      deckstring = write_deckstring(cards, [7], FormatType.FT_STANDARD)
      decoded_cards, _, _, _ = parse_deckstring(deckstring)
      assert decoded_cards == sorted(cards)
  ```

### 3. Add Docstrings and Examples

**Changes needed:**
- Module-level docstring explaining the deckstring format
- Add docstrings to all public functions:
  ```python
  def parse_deckstring(deckstring: str) -> Tuple[CardIncludeList, CardList, FormatType, SideboardList]:
      """Parse a Hearthstone deckstring into structured components.
      
      Args:
          deckstring: Base64-encoded deck string (e.g., from deck code sharing)
      
      Returns:
          Tuple of (cards, heroes, format, sideboards):
          - cards: List of (dbf_id, count) tuples
          - heroes: List of hero DBF IDs
          - format: FormatType enum (Standard, Wild, etc.)
          - sideboards: List of (dbf_id, count, owner_dbf_id) tuples
      
      Raises:
          InvalidDeckstringError: If deckstring is malformed or truncated
          UnsupportedVersionError: If version is not supported
      
      Example:
          >>> cards, heroes, fmt, sb = parse_deckstring("AAECAf0EBMABobcC...")
          >>> print(f"Format: {fmt}, Hero: {heroes[0]}")
          Format: FT_STANDARD, Hero: 637
      """
  ```
- Add README.md with usage examples
- Document the binary format specification

### 4. Relax Hero Count Validation

**Changes needed:**
- Change `write_deckstring` validation:
  ```python
  # Old:
  if len(heroes) != 1:
      raise ValueError("Unsupported hero count %i" % (len(heroes)))
  
  # New:
  if len(heroes) == 0:
      raise ValidationError("Deck must have at least one hero")
  # Allow any positive number of heroes for future formats
  ```
- Add warning or deprecation notice if supporting future multi-hero modes
- Update tests to verify 1-hero, 2-hero, and n-hero cases work

### 5. Add Deck Validation

**Changes needed:**
- Add `validate()` method to `Deck` class:
  ```python
  def validate(self, strict: bool = True) -> List[str]:
      """Validate deck legality rules.
      
      Args:
          strict: If True, raise ValidationError. If False, return warnings.
      
      Returns:
          List of validation warning messages (empty if valid)
      
      Raises:
          ValidationError: If strict=True and deck is invalid
      """
      warnings = []
      
      total_cards = sum(count for _, count in self.cards)
      if total_cards != 30:
          warnings.append(f"Deck has {total_cards} cards (expected 30)")
      
      # Check for >2 copies of non-legendary cards
      # (requires card database lookup - may need to be optional)
      
      if strict and warnings:
          raise ValidationError("; ".join(warnings))
      return warnings
  ```
- Add optional card database integration for format legality
- Make validation pluggable for different game modes

### 6. Complete Type Annotations

**Changes needed:**
- Fix IO type hints:
  ```python
  def _read_varint(stream: IO[bytes]) -> int:
      # ... (change stream.read(1) to expect bytes)
  
  def _write_varint(stream: IO[bytes], i: int) -> int:
      # ... (already correct)
  ```
- Add return types to `Deck` methods:
  ```python
  def get_dbf_id_list(self) -> CardIncludeList: ...
  ```
- Run mypy in strict mode and fix all warnings
- Add py.typed marker file for PEP 561 compliance

### 7. Implement Version Tolerance

**Changes needed:**
- Support forward compatibility:
  ```python
  # In parse_deckstring:
  if version > DECKSTRING_VERSION:
      warnings.warn(
          f"Deckstring version {version} is newer than supported {DECKSTRING_VERSION}. "
          "Parsing may be incomplete.",
          FutureWarning
      )
      # Continue parsing rather than failing
  elif version < 1:
      raise UnsupportedVersionError(f"Version {version} too old")
  ```
- Add optional `version` parameter to `write_deckstring` for testing
- Document version compatibility policy
- Consider adding feature flags for version-specific behavior

### 8. Add Convenience Methods

**Changes needed:**
- Add properties to `Deck`:
  ```python
  @property
  def total_cards(self) -> int:
      return sum(count for _, count in self.cards)
  
  @property
  def is_complete(self) -> bool:
      return self.total_cards == 30 and len(self.heroes) >= 1
  
  def add_card(self, dbf_id: int, count: int = 1) -> None:
      # Update self.cards, maintaining sorted order
  
  def remove_card(self, dbf_id: int, count: int = 1) -> None:
      # Remove from self.cards
  ```
- Add `__str__` and `__repr__` for debugging:
  ```python
  def __repr__(self) -> str:
      return f"Deck(cards={len(self.cards)}, heroes={self.heroes}, format={self.format.name})"
  ```

### 9. Optimize Performance (If Needed)

**Changes needed:**
- Profile with realistic workloads first
- If sorting is a bottleneck:
  - Cache sorted results in `Deck` class
  - Use `bisect.insort` for maintaining sorted order
- If varint encoding is slow:
  - Consider Cython or C extension
  - Batch write operations
- If memory is constrained:
  - Replace BytesIO with pre-allocated bytearray
  - Use generators for large deck collections

**Measurement approach:**
```python
import timeit

def benchmark():
    deckstring = "AAECAf0EBMABobcC..."  # Real production deckstring
    return timeit.timeit(
        lambda: parse_deckstring(deckstring),
        number=10000
    )
```
Only optimize if parsing takes >100μs per operation (unlikely bottleneck for typical use).