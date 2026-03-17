# ROUND3_SOURCES.md

Phase 0b selection log for the Round 3 metacognition experiment.

**Executor:** Claude Opus 4.6 via Claude Code CLI
**Date:** 2026-03-17
**Queries from Phase 0a:** Used verbatim, unedited.

---

## Summary

| Query | Accepted Repo | Stars | Reason |
|-------|--------------|-------|--------|
| 1. file organizer | NONE | - | All 20 results have < 5 stars (max 4) |
| 2. csv cleaner | NONE | - | All 20 results have 0-1 stars |
| 3. log parser | HearthSim/python-hearthstone | 263 | deckstrings.py module (251 lines) passes all criteria |
| 4. backup script | NONE | - | All 20 results have 0-4 stars |
| 5. note search | NONE | - | All 10 results have 0-3 stars |
| 6. json formatter | NONE | - | Two repos with >= 5 stars both exceed 300 lines |
| 7. duplicate finder | NONE | - | All 20 results have 0-2 stars |
| 8. folder watcher | NONE | - | All 11 results have 0-2 stars |
| 9. rss reader | rainygirl/rreader | 15 | get_rss.py (114 lines) + 2 helper modules (22 lines); feedparser strippable |
| 10. text extractor | NONE | - | One repo with >= 5 stars has heavy external deps and multi-file structure |

**Total accepted: 2 repos.** Per the decision tree: "Found 2 repos? GO MINIMAL."

**Observation:** The `--sort=updated` flag biases results toward very recently created/updated repos, most of which are brand-new projects with 0 stars. The 5-star quality threshold eliminates nearly all results. Across 191 total repos evaluated, only 6 had >= 5 stars, and 4 of those failed on other criteria (line count, external dependencies, multi-file structure).

---

## Query 1: file organizer

```
gh search repos "file organizer" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | xiaojiou176-org/file-organizer-governance | 0 | REJECT | < 5 stars |
| 2 | Hoppen1433/smart-file-organizer | 4 | REJECT | < 5 stars |
| 3 | Fazil3496/python-file-organizer | 0 | REJECT | < 5 stars |
| 4 | xwyuan-sg/FileOrganizer | 0 | REJECT | < 5 stars |
| 5 | apuy295/file-organizer-renamer | 0 | REJECT | < 5 stars |
| 6 | akira82-ai/file-organizer | 2 | REJECT | < 5 stars |
| 7 | VictorPedroza/files-organizer-py | 0 | REJECT | < 5 stars |
| 8 | furkankufrevi/file-organizer | 0 | REJECT | < 5 stars |
| 9 | philiprehberger/py-file-organizer | 1 | REJECT | < 5 stars |
| 10 | cse23-056MichelleKeitiretse/file-organizer | 0 | REJECT | < 5 stars |
| 11 | 1Akeno/FileAutoSorter | 2 | REJECT | < 5 stars |
| 12 | RaghavSharma-1109/python-file-organizer | 0 | REJECT | < 5 stars |
| 13 | H-Burnside/file-organizer | 0 | REJECT | < 5 stars |
| 14 | unjerrylchno/file-organizer | 0 | REJECT | < 5 stars |
| 15 | ncafengcu/file-organizer | 0 | REJECT | < 5 stars |
| 16 | mahdonfike5/file-organizer | 0 | REJECT | < 5 stars |
| 17 | vighteo/file-organizer | 0 | REJECT | < 5 stars |
| 18 | phanyage/file-organizer | 0 | REJECT | < 5 stars |
| 19 | EstebanDev411/fileforge | 1 | REJECT | < 5 stars |
| 20 | DiegoLibonati/File-Organizer-Program | 0 | REJECT | < 5 stars |

**Result: NO QUALIFYING REPO**

---

## Query 2: csv cleaner

```
gh search repos "csv cleaner" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | crkdev1989/csv-cleaner | 0 | REJECT | < 5 stars |
| 2 | Cellous/python-csv-cleaner | 0 | REJECT | < 5 stars |
| 3 | Tharana-Dev/CSV-Cleaner-Version1.0 | 0 | REJECT | < 5 stars |
| 4 | Tharana-Dev/CSV-Cleaner-Version-2.0 | 0 | REJECT | < 5 stars |
| 5 | BurhanuddinMustansir/csv-cleaner-cli | 0 | REJECT | < 5 stars |
| 6 | Warlord1986pl/Muse_CSV_Cleaner | 0 | REJECT | < 5 stars |
| 7 | ZADigitalSolutions/csv-cleaner-python | 0 | REJECT | < 5 stars |
| 8 | yankhoembekezani/csv-cleaner-pro | 0 | REJECT | < 5 stars |
| 9 | sabithismail/csv-cleaner | 0 | REJECT | < 5 stars |
| 10 | quickscript-tech/quickscript-csv-cleaner-report | 0 | REJECT | < 5 stars |
| 11 | lilybyt/csv-cleaner | 0 | REJECT | < 5 stars |
| 12 | rajansavani/csv-cleaner | 1 | REJECT | < 5 stars |
| 13 | juliana-albertyn/csv-cleaner | 0 | REJECT | < 5 stars |
| 14 | calwong88/csv-cleaner | 0 | REJECT | < 5 stars |
| 15 | DarkOracle10/CSV-Cleaner---Report-Generator | 1 | REJECT | < 5 stars |
| 16 | BroM1tch/CSV_Cleaner | 0 | REJECT | < 5 stars |
| 17 | FouniMaroua/agentic-csv-cleaner | 0 | REJECT | < 5 stars |
| 18 | kelvinmonye/csv-cleaner-deduper | 0 | REJECT | < 5 stars |
| 19 | Harley-Williamson/CSV-Cleaner | 0 | REJECT | < 5 stars |
| 20 | amirhosseimg/csv-cleaner-cli | 0 | REJECT | < 5 stars |

**Result: NO QUALIFYING REPO**

---

## Query 3: log parser

```
gh search repos "log parser" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | rhuanssauro/zeek-mcp-server | 1 | REJECT | < 5 stars |
| 2 | Speed-boo3/soc-project | 0 | REJECT | < 5 stars |
| 3 | Nekizo/UnrealPythonLogParser | 0 | REJECT | < 5 stars |
| 4 | VoxCore84/draconic-bot | 0 | REJECT | < 5 stars |
| 5 | alex-cloudops/log-intelligence-engine | 0 | REJECT | < 5 stars |
| 6 | HearthSim/python-hearthstone | 263 | **ACCEPT** | See below |
| 7 | chinmayrozekar/SiliconSentry_Agentic_RAG_Log_Triage_System | 0 | - | Skipped (repo 6 accepted) |
| 8-20 | (remaining repos) | 0-1 | - | Skipped |

### Accepted: HearthSim/python-hearthstone

**Repo URL:** https://github.com/HearthSim/python-hearthstone
**License:** MIT
**Latest commit:** `f9a220ac471f6aa7de1a55cfe050e54eeecc12bf`
**Stars:** 263
**Source file:** `hearthstone/deckstrings.py` (251 lines)

#### What the system does

Encodes and decodes Hearthstone deck lists to and from Blizzard's compact base64 deckstring format, using variable-length integer (varint) encoding for card IDs and counts.

#### Working capabilities

1. **Varint encoding/decoding:** Reads and writes variable-length integers from byte streams (`_read_varint`, `_write_varint`)
2. **Deckstring parsing:** Decodes a base64 deckstring into structured data: card list (with counts), hero list, format type, and sideboards (`parse_deckstring`)
3. **Deckstring writing:** Encodes structured deck data back into a base64 deckstring (`write_deckstring`)
4. **Tri-sort optimization:** Groups cards into 1-copy, 2-copy, and n-copy buckets for compact encoding (`trisort_cards`)
5. **Deck class:** Object-oriented wrapper with `from_deckstring` classmethod and `as_deckstring` property for round-trip conversion
6. **Sideboard support:** Handles the sideboard extension to the deckstring format, including sideboard-owner associations
7. **Version checking:** Validates deckstring version header before parsing
8. **Format type validation:** Validates the game format (Wild, Standard, Classic, Twist) using an IntEnum

#### External dependencies and stripping

**Single dependency:** `from .enums import FormatType`

`FormatType` is a 5-value IntEnum:

```python
from enum import IntEnum

class FormatType(IntEnum):
    FT_UNKNOWN = 0
    FT_WILD = 1
    FT_STANDARD = 2
    FT_CLASSIC = 3
    FT_TWIST = 4
```

**Stripping transformation:** Replace `from .enums import FormatType` with the 5-line IntEnum definition above. No other changes needed. All other imports (`base64`, `io.BytesIO`, `typing`) are Python stdlib.

#### Gaps (8 specific missing behaviors)

1. **No input sanitization beyond version check.** The parser does not validate that the decoded byte stream has the expected length. A truncated or corrupted deckstring that happens to start with the correct header will cause an unhandled `EOFError` from `_read_varint` mid-parse rather than a clean validation error.

2. **No trailing-byte detection.** After parsing all sections (header, heroes, cards, sideboards), the parser does not check whether unparsed bytes remain in the stream. A deckstring with extra trailing data would parse without error, silently ignoring the extra content.

3. **No card-count validation.** The parser accepts any card count, including zero or negative values (which varint encoding cannot produce, but a malformed byte sequence could). A production system would validate that card counts are positive integers within game rules (e.g., 1-2 for constructed, 1+ for arena).

4. **No deck-size validation.** Neither `parse_deckstring` nor `write_deckstring` checks the total number of cards in the deck. Hearthstone decks are 30 cards (constructed) or 40 (some formats). The parser accepts any count without warning.

5. **No card-ID validation.** Card IDs (DBF IDs) are parsed as raw integers with no check against a valid card database. A deckstring containing non-existent card IDs would parse successfully. A production system would validate IDs against a card database or at minimum check for negative/zero values.

6. **No human-readable output.** The system returns raw integer tuples. There is no capability to resolve card IDs to card names, costs, classes, or any other metadata. Round-trip from deckstring to human-readable deck list and back is not possible with this module alone.

7. **No format-version migration.** The parser rejects any deckstring with a version other than 1. If Blizzard releases version 2 of the format, the parser will fail rather than attempting graceful degradation or providing diagnostic information about what changed.

8. **No logging or error context.** When parsing fails (ValueError, EOFError), the error messages include the raw value that failed validation but not the position in the byte stream or which section was being parsed. Debugging a malformed deckstring requires manual binary inspection.

9. **No serialization to standard interchange formats.** The Deck class has no `to_dict()`, `to_json()`, or `__repr__` method. Inspecting or transmitting deck data requires manual attribute access.

10. **No concurrent/batch processing.** The module processes one deckstring at a time. A production system handling bulk imports (e.g., parsing thousands of deckstrings from a tournament database) would benefit from batch processing, streaming, or async support.

---

## Query 4: backup script

```
gh search repos "backup script" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | jszymanowski/github-backup | 0 | REJECT | < 5 stars |
| 2 | cheezzz/backup-scripts | 0 | REJECT | < 5 stars |
| 3 | djekl/docker-github-backup | 0 | REJECT | < 5 stars |
| 4 | simonbru/spotify-backup | 4 | REJECT | < 5 stars |
| 5 | Rufis72/backuplib | 0 | REJECT | < 5 stars |
| 6 | ajfite/server-backup-scripts | 0 | REJECT | < 5 stars |
| 7 | jeffersonraimon/TP-Link-Easy-Smart-Switch-Backup-Script | 0 | REJECT | < 5 stars |
| 8 | lampapps/jabs | 0 | REJECT | < 5 stars |
| 9 | jianwolf/photo-backup-scripts | 0 | REJECT | < 5 stars |
| 10 | CharafZohar-Dev/Python_Backup_Script- | 0 | REJECT | < 5 stars |
| 11 | DrSkippy/yet-another-python-backup-script | 0 | REJECT | < 5 stars |
| 12 | CHUKEPC/backup-script | 0 | REJECT | < 5 stars |
| 13 | gustrd/ssh-backup | 0 | REJECT | < 5 stars |
| 14 | kkyick2/plink_backup_script | 0 | REJECT | < 5 stars |
| 15 | ThalesMMS/Horos-Backup-Script | 0 | REJECT | < 5 stars |
| 16 | DMarkStorage/ZFS-Snapshot-Automation-CLI | 0 | REJECT | < 5 stars |
| 17 | Bookie212/File-Backup-Script | 0 | REJECT | < 5 stars |
| 18 | eblet/driveup | 0 | REJECT | < 5 stars |
| 19 | apuignav/backup | 0 | REJECT | < 5 stars |
| 20 | Colin-Fredericks/edx_backup_script | 0 | REJECT | < 5 stars |

**Result: NO QUALIFYING REPO**

---

## Query 5: note search

```
gh search repos "note search" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | Danilosouzax/jobtracker-fullstack | 1 | REJECT | < 5 stars |
| 2 | Eternal0404/passsafe-pro-app | 0 | REJECT | < 5 stars |
| 3 | banti9021/AI-Note-Search-App-Streamlit- | 0 | REJECT | < 5 stars |
| 4 | JrGkOG/HearYourPaper | 3 | REJECT | < 5 stars |
| 5 | Laberintic/note-search | 0 | REJECT | < 5 stars |
| 6 | mvleest-code/UL-JoplinNoteSearch | 2 | REJECT | < 5 stars |
| 7 | Am1rX/OpenStreetMap-Note-Search-Scripts | 2 | REJECT | < 5 stars |
| 8 | guriandoro/pmm_v2_release_notes_search | 0 | REJECT | < 5 stars |
| 9 | WilliamQx/Note_Search | 0 | REJECT | < 5 stars |
| 10 | ankitaSawrav/notely-note-taking | 0 | REJECT | < 5 stars |

Note: Only 10 results returned for this query.

**Result: NO QUALIFYING REPO**

---

## Query 6: json formatter

```
gh search repos "json formatter" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | madcuzbad123/dotenv-to-json | 0 | REJECT | < 5 stars |
| 2 | andres221-star/crunchbase-any-search-results-scraper | 0 | REJECT | < 5 stars |
| 3 | soumyadeb-git/Fetch-Py | 1 | REJECT | < 5 stars |
| 4 | kannanvk1997/TgMongoBot | 2 | REJECT | < 5 stars |
| 5 | galafis/data-quality-framework-great-expectations | 1 | REJECT | < 5 stars |
| 6 | yoarikso/cpdvbible | 1 | REJECT | < 5 stars |
| 7 | MarcMcIntosh/python-json-formater | 0 | REJECT | < 5 stars |
| 8 | vertex-ai-automations/pylogshield | 0 | REJECT | < 5 stars |
| 9 | FronkonGames/Steam-Games-Scraper | 144 | REJECT | Core logic (SteamGamesScraper.py) is 604 lines, exceeds 300-line limit |
| 10 | Chhabijha1712/telemetry-converter | 0 | REJECT | < 5 stars |
| 11 | julienc91/hltv-ranking | 0 | REJECT | < 5 stars |
| 12 | EricLuceroGonzalez/Panama-Political-Division | 1 | REJECT | < 5 stars |
| 13 | davidleonstr/dirscanner | 1 | REJECT | < 5 stars |
| 14 | VoxHash/BrowserBookmarkChecker | 1 | REJECT | < 5 stars |
| 15 | Octomany/cisbenchmarkconverter | 80 | REJECT | Core logic (cis_benchmark_converter.py) is 436 lines, exceeds 300-line limit; also depends on pdfplumber, openpyxl, tqdm |
| 16 | HOCG-Fan-Portal-Site/Cards_Collector | 0 | REJECT | < 5 stars |
| 17 | vesper-astrena/jsonkit | 0 | REJECT | < 5 stars |
| 18 | klich3/rocket-store-lcoal-memories-python | 0 | REJECT | < 5 stars |
| 19 | Nsomnia/lmarena-chat-reconstrucer-from-json | 0 | REJECT | < 5 stars |
| 20 | cykruss/dynojson | 0 | REJECT | < 5 stars |

**Result: NO QUALIFYING REPO**

---

## Query 7: duplicate finder

```
gh search repos "duplicate finder" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | philiprehberger/py-duplicate-finder | 1 | REJECT | < 5 stars |
| 2 | lemarcgagnon/DuplicateFinder | 0 | REJECT | < 5 stars |
| 3 | Jeffrin-dev/CleanSweep | 1 | REJECT | < 5 stars |
| 4 | MopicMP/simple-duplicate-finder | 0 | REJECT | < 5 stars |
| 5 | sabithismail/duplicate-finder | 0 | REJECT | < 5 stars |
| 6 | Brutus1066/kw-file-manager | 0 | REJECT | < 5 stars |
| 7 | MAliXCS/Duplicate-File-Remover-v1.3 | 1 | REJECT | < 5 stars |
| 8 | MopicMP/lite-duplicate-finder | 0 | REJECT | < 5 stars |
| 9 | mrblackman/PhotoDuplicateFinder | 2 | REJECT | < 5 stars |
| 10 | zman-six/photo-organizer | 1 | REJECT | < 5 stars |
| 11 | victorzambelli/FiveM-DuplicateFinder | 0 | REJECT | < 5 stars |
| 12 | ekomateas/image-duplicate-finder | 0 | REJECT | < 5 stars |
| 13 | kriskimmerle/dupecode | 0 | REJECT | < 5 stars |
| 14 | andrewmy/filedrift | 0 | REJECT | < 5 stars |
| 15 | Splatbasset/PhotoDuplicateFinder | 0 | REJECT | < 5 stars |
| 16 | DimitriosPournarkas/PyDuplicateFinder | 0 | REJECT | < 5 stars |
| 17 | woxili880409/filedup | 0 | REJECT | < 5 stars |
| 18 | degenerator3003/DuplicateFinder | 0 | REJECT | < 5 stars |
| 19 | morevna6/dupsy | 0 | REJECT | < 5 stars |
| 20 | laalaguer/video-duplicate-finder | 1 | REJECT | < 5 stars |

**Result: NO QUALIFYING REPO**

---

## Query 8: folder watcher

```
gh search repos "folder watcher" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | TakatoPhy/coldatom-imaging | 0 | REJECT | < 5 stars |
| 2 | MAliXCS/Fileorb_v1.0 | 2 | REJECT | < 5 stars |
| 3 | Enesozd1/watchdog-file-processor | 0 | REJECT | < 5 stars |
| 4 | iminierai-aig/pdf-to-markdown | 0 | REJECT | < 5 stars |
| 5 | stuskeer/FolderWatcher | 0 | REJECT | < 5 stars |
| 6 | SGK1ng/FolderWatcher | 0 | REJECT | < 5 stars |
| 7 | out0/auto_pdf_join | 0 | REJECT | < 5 stars |
| 8 | gciftci/FolderWatcher | 0 | REJECT | < 5 stars |
| 9 | LuisHenri/downloads-folder-watcher | 0 | REJECT | < 5 stars |
| 10 | mototoke/folder_watch | 0 | REJECT | < 5 stars |
| 11 | robmarkcole/HASS-folder-watcher | 1 | REJECT | < 5 stars; also archived |

Note: Only 11 results returned for this query.

**Result: NO QUALIFYING REPO**

---

## Query 9: rss reader

```
gh search repos "rss reader" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | rainygirl/rreader | 15 | **ACCEPT** | See below |
| 2-20 | (remaining repos) | 0-7 | - | Skipped (repo 1 accepted) |

For completeness, had repo 1 been rejected:

| # | Repo | Stars | Notes |
|---|------|-------|-------|
| 2 | reuteras/miniflux-tui-py | 0 | Would reject: < 5 stars |
| 3 | janiosarmento/risos | 7 | Would reject: multi-file web app (FastAPI + Docker + Alembic), heavy external deps |
| 4 | rjrpaz/rss2t | 2 | Would reject: < 5 stars |
| 5 | AdrienLF/readr | 0 | Would reject: < 5 stars |
| 6 | wangluo1/rss-reader-skill | 1 | Would reject: < 5 stars |
| 7 | helebest/holo-rss-reader | 0 | Would reject: < 5 stars |
| 8 | Christian-Braga/rss-feeds | 2 | Would reject: < 5 stars |
| 9 | ai-and-history-collaboratory/rss-reader | 2 | Would reject: < 5 stars |
| 10 | Sadykov-Ildar/django_rss_reader | 0 | Would reject: < 5 stars |
| 11 | tcarmody/macreader | 0 | Would reject: < 5 stars |
| 12 | edleeman17/E-Ink-RSS-Reader | 3 | Would reject: < 5 stars |
| 13 | MopicMP/safe-rss-reader | 0 | Would reject: < 5 stars |
| 14 | MopicMP/rss-reader | 0 | Would reject: < 5 stars |
| 15 | NanshineLoong/RSS-reader | 1 | Would reject: < 5 stars |
| 16 | c4ffein/feed | 0 | Would reject: < 5 stars |

### Accepted: rainygirl/rreader

**Repo URL:** https://github.com/rainygirl/rreader
**License:** MIT
**Latest commit:** `a8dcd12aab0ce673582891a51514ab5247c0a300`
**Stars:** 15
**Source files:** `rreader-python/src/rreader/get_rss.py` (114 lines), `common.py` (14 lines), `config.py` (4 lines) -- 132 lines total

#### What the system does

Fetches RSS feeds from configured URLs, parses them into timestamped entries, and writes per-category JSON files to a local data directory.

#### Working capabilities

1. **Multi-source RSS fetching:** Iterates over a dictionary of {source_name: url} pairs, fetching and parsing each feed
2. **Entry normalization:** Extracts title, link, author, and publication timestamp from each feed entry into a uniform JSON structure
3. **Timezone-aware date formatting:** Converts UTC timestamps to a configured timezone (KST), formats as "HH:MM" for today's entries and "Mon DD, HH:MM" for older ones
4. **Per-category output:** Writes separate JSON files per category (e.g., `rss_tech.json`, `rss_news.json`)
5. **Chronological sorting:** Sorts entries by timestamp in reverse chronological order
6. **Feeds configuration management:** Reads feed URLs from a `feeds.json` config file, merges bundled defaults with user customizations
7. **Author attribution:** Optionally shows per-entry authors (configurable per category via `show_author`)
8. **Selective category fetching:** Can fetch a single category or all categories via the `target_category` parameter
9. **Logging mode:** Optional stdout progress logging during fetch

#### External dependencies and stripping

**External dependency:** `feedparser` (RSS/Atom feed parsing library)

**Stripping transformation:** Replace `feedparser.parse(url)` with stdlib equivalents:

1. `urllib.request.urlopen(url)` to fetch the XML content
2. `xml.etree.ElementTree.fromstring(response.read())` to parse the RSS XML
3. XPath queries for RSS 2.0 fields:
   - `channel/item` for entries (replaces `d.entries`)
   - `item/title` for `feed.title`
   - `item/link` for `feed.link`
   - `item/pubDate` for `feed.published_parsed` (parse with `email.utils.parsedate_to_datetime()`)
   - `item/author` or `item/dc:creator` for `feed.author`
4. Remove `getattr(feed, 'updated_parsed', None)` fallback (not available in stdlib XML parsing; use `pubDate` only)

**Internal module inlining:** Merge `common.py` (path setup) and `config.py` (timezone constant) directly into `get_rss.py`. Total combined: 132 lines, well under 300.

**Behavioral change from stripping:** The stripped version handles RSS 2.0 only (not Atom, RSS 1.0, or RDF). feedparser normalizes across all RSS/Atom versions; the stdlib replacement is RSS 2.0-specific. This is a documented, intentional reduction in scope.

#### Gaps (10 specific missing behaviors)

1. **No HTTP error handling.** `feedparser.parse(url)` silently absorbs HTTP errors (404, 500, timeout). The bare `except:` at line 32 catches everything and calls `sys.exit()`, killing the entire process on the first failed feed rather than skipping it and continuing.

2. **No feed validation.** The code does not check whether the parsed feed contains valid data. An empty feed, a non-RSS URL, or a redirect to an HTML page would produce zero entries with no warning.

3. **No deduplication across fetches.** Each call overwrites the entire category JSON file. If two feeds in the same category contain the same article (cross-posted or syndicated), both copies appear in the output. The `id` field uses the Unix timestamp, so entries published at the same second will collide.

4. **No content extraction.** Only title, link, author, and date are captured. The feed entry's description/summary, content body, categories/tags, enclosures (podcasts, images), and media elements are discarded.

5. **No caching or conditional fetching.** Every invocation fetches every feed from scratch. There is no ETag or Last-Modified header support, no If-Modified-Since requests, and no local cache. This wastes bandwidth and hits rate limits on feeds that update infrequently.

6. **No rate limiting or throttling.** All feeds in a category are fetched sequentially with no delay between requests. A category with 20 feeds sends 20 requests in rapid succession, which may trigger server-side rate limiting or IP blocking.

7. **No persistent state.** The system writes output JSON but maintains no state about what has been seen before. There is no read/unread tracking, no "last fetched" timestamp per feed, and no way to show only new entries since the last run.

8. **No error recovery or retry.** A single network failure terminates the entire process (`sys.exit()`). There is no retry logic, no exponential backoff, and no partial-success handling (e.g., writing results from successful feeds even if one fails).

9. **No feed discovery or OPML import/export.** Feeds must be manually added to `feeds.json`. There is no auto-discovery from website URLs (checking `<link rel="alternate">` tags), no OPML import for migrating from other readers, and no OPML export.

10. **No output format flexibility.** Output is hardcoded to JSON files in a specific structure. There is no support for rendering to HTML, terminal display, email digest, or any other presentation format. The date format is hardcoded and not configurable.

---

## Query 10: text extractor

```
gh search repos "text extractor" --language=python --license=mit --sort=updated --limit=20
```

### Repos evaluated (top-to-bottom)

| # | Repo | Stars | Decision | Reason |
|---|------|-------|----------|--------|
| 1 | ShlokDivyam1109/Text-Extractor | 0 | REJECT | < 5 stars |
| 2 | XXXVIIMMI/image-text-extractor | 0 | REJECT | < 5 stars |
| 3 | mamsss121/text_extractor | 0 | REJECT | < 5 stars |
| 4 | NoeFlandre/fineweb-legal | 1 | REJECT | < 5 stars |
| 5 | dkorbelainen/sniptext | 4 | REJECT | < 5 stars |
| 6 | chinosk6/umamusume-voice-text-extractor | 90 | REJECT | Multi-file architecture (voiceex package: voice_ex.py, database.py, downloader.py, resource.py, etc.); heavy external deps (PyQt5, UnityPy, pythonnet, pydantic, apsw_sqlite3mc, requests, colorama, rich) |
| 7 | Jashan024/Text-Extractor | 0 | REJECT | < 5 stars |
| 8 | Shishir2251/file-to-text-extractor | 0 | REJECT | < 5 stars |
| 9 | VintLin/pdf-text-extractor | 0 | REJECT | < 5 stars |
| 10 | supersokol/workua-resume-toolkit | 3 | REJECT | < 5 stars |
| 11 | Ravi-Wijerathne/Text_Extractor | 0 | REJECT | < 5 stars |
| 12 | kaundanyapureshubham-hub/scanned-pdf-text-extractorarjun | 0 | REJECT | < 5 stars |
| 13 | pachexyz/PDF-Text-Extractor | 0 | REJECT | < 5 stars |
| 14 | slfx77/psx_texture_extractor | 0 | REJECT | < 5 stars |
| 15 | akixu15-maker/ocr-text-extractor | 1 | REJECT | < 5 stars |
| 16 | chiavegatti/pdf-text-extractor | 0 | REJECT | < 5 stars |
| 17 | XiaoNiaoa/open.mp-text-extractor | 0 | REJECT | < 5 stars |
| 18 | victinyGitHub/nothingburger | 1 | REJECT | < 5 stars |
| 19 | sanyokkua/py_web_text_extractor | 0 | REJECT | < 5 stars |
| 20 | parten0/text_extractor_pro | 0 | REJECT | < 5 stars |

**Result: NO QUALIFYING REPO**

---

## Methodology Notes

### Search bias

The `--sort=updated` flag returns the most recently updated repos first. Most recently updated repos are disproportionately brand-new projects (created within the past 24-48 hours) with zero stars and minimal functionality. This creates a systematic mismatch with the >= 5 stars quality threshold: the sort order and the quality filter are in tension.

A `--sort=stars` flag would have returned more established repos but would have changed the pre-registered query.

### Interpretation of "core logic in a single file"

For HearthSim/python-hearthstone, the repo is a multi-module library. However, `deckstrings.py` is a self-contained module with independently testable functions, a dedicated test file (test_deckstrings.py, 311 lines), and only one trivially-strippable cross-module dependency (a 5-value IntEnum). The module was accepted as a "Python system that works but is incomplete" per the experimental directive.

### Interpretation of "strippable with documented transformation"

For rainygirl/rreader, the `feedparser` dependency was deemed strippable because the code uses only a narrow slice of feedparser's API (parse URL, iterate entries, access title/link/pubDate/author). Each call maps to a documented stdlib equivalent (urllib for HTTP, xml.etree for XML, email.utils for date parsing). The transformation reduces scope (RSS 2.0 only, no Atom) but preserves all behaviors the code actually uses.

### Star count distribution

Across all 191 repos evaluated from the 10 queries:
- 0 stars: 146 repos (76.4%)
- 1 star: 23 repos (12.0%)
- 2 stars: 10 repos (5.2%)
- 3 stars: 3 repos (1.6%)
- 4 stars: 3 repos (1.6%)
- 5+ stars: 6 repos (3.1%)

Of the 6 repos with >= 5 stars:
- HearthSim/python-hearthstone (263): ACCEPTED (deckstrings module)
- FronkonGames/Steam-Games-Scraper (144): REJECTED (604 lines)
- chinosk6/umamusume-voice-text-extractor (90): REJECTED (multi-file, heavy deps)
- Octomany/cisbenchmarkconverter (80): REJECTED (436 lines, external deps)
- rainygirl/rreader (15): ACCEPTED (feedparser strippable)
- janiosarmento/risos (7): REJECTED (multi-file web app)
