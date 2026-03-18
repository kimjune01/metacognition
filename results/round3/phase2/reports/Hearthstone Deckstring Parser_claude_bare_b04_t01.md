# Diagnostic Report: Hearthstone Deckstring Library

## Observations

This system implements **Blizzard's Deckstring format** for encoding and decoding Hearthstone deck configurations. Working capabilities:

1. **Bidirectional encoding/decoding** - Converts between human-readable deck lists and compact base64-encoded deckstrings
2. **Complete format support** - Handles all deckstring components:
   - Version header and format type (Standard, Wild, etc.)
   - Hero cards (with validation for single-hero requirement)
   - Main deck cards with arbitrary counts (1×, 2×, n×)
   - Sideboard cards (newer feature with owner tracking)
3. **Efficient encoding** - Uses varint compression to minimize deckstring size by grouping cards by count
4. **Data model** - Provides `Deck` class with methods for conversion and card list retrieval
5. **Sorting conventions** - Maintains consistent ordering (by DBF ID for main deck, by owner then ID for sideboards)

## Triage

### Critical (Blocks Production Use)

1. **No error handling for malformed input** - Silent failures or unclear exceptions on corrupted deckstrings
2. **No validation** - Accepts invalid deck configurations (duplicate cards, wrong counts, invalid DBF IDs)
3. **Type annotations incomplete** - Return type syntax errors (`(Tuple[...])` should be `->`)

### High (Quality/Reliability Issues)

4. **No test coverage** - No way to verify correctness or prevent regressions
5. **Hard-coded single hero constraint** - Fails for multi-hero formats (Duels, some Tavern Brawls) despite parsing multi-hero data
6. **No documentation** - Missing docstrings, usage examples, format specification reference

### Medium (Developer Experience)

7. **No card name resolution** - Works only with numeric DBF IDs, not human-readable card names
8. **Limited Deck class functionality** - Doesn't support deck manipulation (add/remove cards, validate counts)
9. **No CLI or import utilities** - Can't easily convert deckstrings from command line or files

### Low (Nice to Have)

10. **No performance optimization** - Could cache decoded results for repeated parsing
11. **Legacy Python 2 compatibility** - Uses `ord(c)` pattern instead of direct byte indexing

## Plan

### 1. Error Handling
**Changes:**
- Wrap `parse_deckstring()` in try/except to catch `EOFError`, `ValueError`, `base64.binascii.Error`
- Define custom exceptions: `InvalidDeckstringError`, `CorruptedDataError`, `UnsupportedVersionError`
- Add descriptive error messages: "Deckstring contains invalid base64" vs. "Unknown format"
- Validate base64 padding before decoding

**Files to modify:** `deckstrings.py` (add exception classes at top, wrap decode logic)

### 2. Validation
**Changes:**
- Add `validate()` method to `Deck` class that checks:
  - Card counts are positive integers
  - No duplicate card IDs in main deck
  - Hero list is non-empty
  - Sideboard owners reference valid hero DBF IDs
- Add optional `strict=True` parameter to `from_deckstring()` to validate on parse
- Optionally accept rules config (max copies per card, deck size limits) for format-specific validation

**Files to modify:** `deckstrings.py` (add `Deck.validate()`, call from `from_deckstring()`)

### 3. Fix Type Annotations
**Changes:**
- Line 39: Change `def parse_deckstring(deckstring) -> (Tuple[...])` to `-> Tuple[CardIncludeList, CardList, FormatType, SideboardList]:`
- Add type hints to parameters: `deckstring: str`
- Add return type to `Deck.__init__` as `-> None`

**Files to modify:** `deckstrings.py` (lines 39, 71, 88)

### 4. Test Coverage
**Changes:**
- Create `test_deckstrings.py` with:
  - Test round-trip encoding (deck → string → deck)
  - Test known deckstring examples from Blizzard documentation
  - Test edge cases (empty sideboards, n× cards, all three heroes)
  - Test error conditions (invalid base64, unsupported version, corrupted varint)
- Use `pytest` or `unittest` framework
- Add sample deckstrings as fixtures

**New file:** `test_deckstrings.py`

### 5. Multi-Hero Support
**Changes:**
- In `write_deckstring()` line 147, replace fixed validation:
  ```python
  # Before:
  if len(heroes) != 1:
      raise ValueError("Unsupported hero count %i" % (len(heroes)))
  
  # After:
  if not (1 <= len(heroes) <= 3):  # Most formats support 1-3 heroes
      raise ValueError("Hero count must be 1-3, got %i" % (len(heroes)))
  ```
- Add `max_heroes` parameter (default 3) for format-specific limits

**Files to modify:** `deckstrings.py` line 147-148

### 6. Documentation
**Changes:**
- Add module docstring explaining deckstring format, link to Blizzard spec
- Add docstrings to all functions with Args/Returns sections:
  ```python
  def parse_deckstring(deckstring: str) -> Tuple[...]:
      """Parse a Hearthstone deckstring into components.
      
      Args:
          deckstring: Base64-encoded deckstring (e.g., from deck sharing)
      
      Returns:
          Tuple of (cards, heroes, format, sideboards)
      
      Raises:
          InvalidDeckstringError: If deckstring is malformed
      """
  ```
- Add usage example in module docstring showing encode/decode workflow
- Document DBF ID concept with link to HearthstoneJSON

**Files to modify:** `deckstrings.py` (add docstrings throughout)

### 7. Card Name Resolution
**Changes:**
- Create optional integration with card database (e.g., HearthstoneJSON)
- Add `from_card_names()` constructor that accepts list of card names
- Add `get_card_names()` method that returns human-readable card list
- Make database dependency optional (ImportError fallback)

**New dependencies:** Add optional `hearthstone-data` or similar package
**Files to modify:** `deckstrings.py` (add name resolution methods), `requirements.txt`

### 8. Enhanced Deck Class
**Changes:**
- Add mutation methods:
  ```python
  def add_card(self, dbf_id: int, count: int = 1) -> None
  def remove_card(self, dbf_id: int) -> None
  def get_card_count(self, dbf_id: int) -> int
  def total_cards(self) -> int
  ```
- Add `__str__` and `__repr__` for debugging
- Add `copy()` method for safe duplication

**Files to modify:** `deckstrings.py` (expand `Deck` class)

### 9. CLI Utility
**Changes:**
- Create `cli.py` with argparse interface:
  ```
  deckstring decode <string>          # Print card list
  deckstring encode <cards.txt>       # Generate deckstring
  deckstring validate <string>        # Check validity
  ```
- Support reading from stdin or file
- Output formats: JSON, human-readable text, TSV

**New file:** `cli.py`, add entry point to `setup.py` or `pyproject.toml`

### 10. Performance Optimization
**Changes:**
- Add LRU cache to `parse_deckstring()`:
  ```python
  from functools import lru_cache
  
  @lru_cache(maxsize=128)
  def parse_deckstring(deckstring: str) -> Tuple[...]:
  ```
- Profile with large batch operations to identify bottlenecks
- Consider using `struct.pack` instead of manual varint for speed

**Files to modify:** `deckstrings.py` (add caching decorator)

### 11. Modernize Python 3
**Changes:**
- Line 24: Replace `i = ord(c)` with `i = c[0]` (bytes are already integers in Python 3)
- Update `BytesIO` usage to ensure consistent bytes/str handling
- Add `from __future__ import annotations` for cleaner type hints

**Files to modify:** `deckstrings.py` (lines 24, throughout)