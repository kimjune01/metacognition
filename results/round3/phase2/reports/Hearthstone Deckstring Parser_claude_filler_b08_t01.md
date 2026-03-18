# Diagnostic Report: Hearthstone Deckstring Parser

## Observations

This system implements Blizzard's deckstring format for encoding and decoding Hearthstone deck compositions. Current working capabilities:

1. **Bidirectional Encoding/Decoding**
   - Parses base64-encoded deckstrings into structured deck data
   - Serializes deck objects back into deckstring format
   - Maintains format version compatibility (version 1)

2. **Varint Protocol Implementation**
   - Reads/writes variable-length integers for compact binary representation
   - Handles standard protobuf-style varint encoding (7-bit chunks with continuation bit)

3. **Complete Data Model Support**
   - Card lists with quantities (1x, 2x, or n copies)
   - Hero cards (with validation for single hero)
   - Format types (Wild, Standard, etc.)
   - Sideboard cards (for game modes that support them)

4. **Efficient Storage Optimization**
   - Groups cards by count (1x, 2x, nx) to minimize encoding size
   - Sorts cards for deterministic output
   - Separates sideboard cards by owner for multiplayer formats

5. **Deck Class Interface**
   - Factory method for creating Deck instances from deckstrings
   - Property accessor for deckstring serialization
   - Methods to retrieve sorted card/sideboard lists

## Triage

### Critical Gaps

1. **Error Handling & Validation** (Severity: High)
   - No validation of card IDs or quantities beyond basic format checks
   - Limited error messages (e.g., generic "Invalid deckstring")
   - No handling of corrupted/truncated data beyond EOF detection
   - Missing validation for deck construction rules (card limits, format legality)

2. **Type Safety** (Severity: High)
   - Type hints present but incomplete (IO type is too generic)
   - No runtime validation of tuple structures in card lists
   - Return type annotations use tuples instead of named structures

3. **Documentation** (Severity: Medium)
   - No docstrings for public API methods
   - No usage examples
   - Undocumented deckstring format specification
   - Missing explanation of sideboard owner semantics

### Important Gaps

4. **Testing Infrastructure** (Severity: Medium)
   - No unit tests for encoding/decoding round-trips
   - No test cases for edge cases (empty decks, maximum counts, corrupted data)
   - No fuzzing or property-based tests

5. **Logging & Observability** (Severity: Medium)
   - No logging of parse errors or warnings
   - No debug mode for inspecting binary data
   - No metrics for tracking decode failures in production

6. **API Ergonomics** (Severity: Low)
   - Deck class requires manual population of fields after instantiation
   - No builder pattern or validation in `__init__`
   - No `__repr__` or `__str__` for debugging
   - No equality operators for deck comparison

### Minor Gaps

7. **Performance Considerations** (Severity: Low)
   - BytesIO creates unnecessary copies for small data
   - No caching of parsed results
   - Repeated sorting operations could be optimized

8. **Python Best Practices** (Severity: Low)
   - Missing `__all__` export list
   - No package-level imports structure
   - Inconsistent naming (tuple unpacking in parse vs separate returns)

## Plan

### 1. Error Handling & Validation

**Changes needed:**

- **File: deckstring.py, function: `parse_deckstring`**
  - Add try/except blocks around base64 decode with specific `binascii.Error` handling
  - Raise `ValueError` with descriptive messages (e.g., "Invalid base64 encoding in deckstring")
  - After reading all sections, verify stream is fully consumed (`data.read(1) == b""`)
  - Add optional `strict=True` parameter to enable deck rule validation

- **File: deckstring.py, new function: `validate_deck`**
  - Create validation function that checks:
    - Card counts don't exceed format limits (typically 2x for non-legendaries)
    - Total card count matches format requirements (30 for Standard)
    - Format-specific restrictions (class cards, banned cards)
  - Return `Tuple[bool, List[str]]` with validation status and error messages

- **File: deckstring.py, function: `_read_varint`**
  - Add maximum byte limit (e.g., 10 bytes) to prevent infinite loops on corrupted data
  - Raise `ValueError("Varint exceeds maximum length")` if limit exceeded

### 2. Type Safety

**Changes needed:**

- **File: deckstring.py, add dataclasses:**
  ```python
  from dataclasses import dataclass
  from typing import List
  
  @dataclass
  class CardEntry:
      dbf_id: int
      count: int
  
  @dataclass
  class SideboardEntry:
      dbf_id: int
      count: int
      owner_id: int
  
  @dataclass
  class DeckContents:
      cards: List[CardEntry]
      heroes: List[int]
      format: FormatType
      sideboards: List[SideboardEntry]
  ```

- **File: deckstring.py, function: `parse_deckstring`**
  - Change return type from tuples to `DeckContents`
  - Convert card tuples to `CardEntry`/`SideboardEntry` objects during parsing

- **File: deckstring.py, class: `Deck`**
  - Replace list-of-tuples with list-of-dataclass fields
  - Update `from_deckstring` to use structured types

### 3. Documentation

**Changes needed:**

- **File: deckstring.py, module level:**
  - Add module docstring explaining deckstring format and use cases
  - Include example:
    ```python
    """
    Example:
        >>> deck = Deck.from_deckstring("AAECAQcG...")
        >>> print(deck.format)  # FormatType.FT_STANDARD
        >>> print(len(deck.cards))  # 30
        >>> deckstring = deck.as_deckstring
    """
    ```

- **File: deckstring.py, each public function:**
  - Add docstrings with Args, Returns, Raises sections
  - Document deckstring format specification in `parse_deckstring` docstring
  - Explain sideboard owner semantics (likely card DBF IDs that enable sideboard cards)

- **File: README.md (new):**
  - Create standalone documentation with format specification
  - Include visual diagram of binary layout
  - Provide integration examples

### 4. Testing Infrastructure

**Changes needed:**

- **File: test_deckstring.py (new):**
  - Add pytest test cases:
    - `test_encode_decode_roundtrip` - verify lossless encoding
    - `test_invalid_base64` - malformed input
    - `test_unsupported_version` - version != 1
    - `test_empty_deck` - zero cards/heroes
    - `test_large_counts` - cards with count > 2
    - `test_sideboard_parsing` - with and without sideboards
    - `test_known_deckstrings` - real examples from Hearthstone
  
- **File: conftest.py (new):**
  - Add pytest fixtures for common test decks
  - Provide helper to generate random valid decks

- **File: test_properties.py (new):**
  - Add hypothesis property-based tests:
    - Any valid deck should round-trip through encoding
    - Encoded size should not exceed reasonable bounds

### 5. Logging & Observability

**Changes needed:**

- **File: deckstring.py, add logging:**
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```

- **File: deckstring.py, function: `parse_deckstring`**
  - Add `logger.debug(f"Parsing deckstring version {version}, format {format}")` after header
  - Add `logger.warning(f"Unusual card count: {count} for card {card_id}")` for counts > 2
  - Add `logger.error(f"Failed to parse deckstring: {e}")` in exception handlers

- **File: deckstring.py, new function: `debug_deckstring`**
  - Create utility that pretty-prints binary structure:
    ```
    Header: version=1, format=FT_STANDARD
    Heroes: [7]
    Cards 1x: [1004, 1005, ...]
    Cards 2x: [1001, 1002, ...]
    ```

### 6. API Ergonomics

**Changes needed:**

- **File: deckstring.py, class: `Deck`**
  - Add `__init__` signature:
    ```python
    def __init__(
        self,
        cards: Optional[CardIncludeList] = None,
        heroes: Optional[CardList] = None,
        format: FormatType = FormatType.FT_UNKNOWN,
        sideboards: Optional[SideboardList] = None
    )
    ```
  
  - Add magic methods:
    ```python
    def __repr__(self) -> str:
        return f"Deck(format={self.format.name}, cards={len(self.cards)}, heroes={self.heroes})"
    
    def __eq__(self, other) -> bool:
        # Compare cards, heroes, format (order-independent for cards)
    ```

  - Add builder methods:
    ```python
    def add_card(self, dbf_id: int, count: int = 1) -> "Deck":
        """Add a card to the deck (fluent interface)."""
    
    def add_hero(self, dbf_id: int) -> "Deck":
        """Set the hero for this deck (fluent interface)."""
    ```

- **File: deckstring.py, class: `Deck`**
  - Add validation in setters or add `validate()` method
  - Raise `ValueError` if invariants violated (e.g., multiple heroes)

### 7. Performance Considerations

**Changes needed:**

- **File: deckstring.py, function: `parse_deckstring`**
  - Replace `BytesIO(decoded)` with manual index tracking for small strings:
    ```python
    idx = 0
    def read_varint_at(data: bytes, idx: int) -> Tuple[int, int]:
        # Returns (value, new_index)
    ```
  
- **File: deckstring.py, class: `Deck`**
  - Add `_deckstring_cache: Optional[str]` field
  - Invalidate cache when cards/heroes/format modified
  - Return cached value in `as_deckstring` if available

- **File: deckstring.py, function: `trisort_cards`**
  - Single-pass bucketing instead of sorting:
    ```python
    for card_elem in cards:
        # Direct append to appropriate list without intermediate sorting
    ```

### 8. Python Best Practices

**Changes needed:**

- **File: deckstring.py, top level:**
  - Add `__all__ = ["Deck", "parse_deckstring", "write_deckstring", "FormatType"]`
  - Consider moving to package structure:
    ```
    deckstring/
        __init__.py  # re-exports public API
        deck.py      # Deck class
        codec.py     # encode/decode functions
        varint.py    # varint implementation
    ```

- **File: deckstring.py, function: `parse_deckstring`**
  - Return named tuple or dataclass instead of tuple for clarity at call sites
  - Replace `Tuple[CardIncludeList, CardList, FormatType, SideboardList]` with `DeckContents`

- **File: deckstring.py, throughout:**
  - Add type: ignore comments where mypy/pyright complains
  - Run `ruff` or `black` for consistent formatting
  - Add `.python-version` and `pyproject.toml` for tool configuration