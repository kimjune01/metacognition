# Round 3 Sources

Generated from Phase 0b evaluation. See `results/round3/phase0b/ROUND3_SOURCES.md` for full evaluation log.

---

## Problem: Hearthstone Deckstring Parser

- repo: https://github.com/HearthSim/python-hearthstone
- license: MIT
- commit: f9a220ac471f6aa7de1a55cfe050e54eeecc12bf
- source_file: results/round3/phase0b/sources/python-hearthstone-deckstrings.py

### Working Capabilities

1. Varint encoding/decoding: Reads and writes variable-length integers from byte streams (_read_varint, _write_varint)
2. Deckstring parsing: Decodes a base64 deckstring into structured data: card list (with counts), hero list, format type, and sideboards (parse_deckstring)
3. Deckstring writing: Encodes structured deck data back into a base64 deckstring (write_deckstring)
4. Tri-sort optimization: Groups cards into 1-copy, 2-copy, and n-copy buckets for compact encoding (trisort_cards)
5. Deck class: Object-oriented wrapper with from_deckstring classmethod and as_deckstring property for round-trip conversion
6. Sideboard support: Handles the sideboard extension to the deckstring format, including sideboard-owner associations
7. Version checking: Validates deckstring version header before parsing
8. Format type validation: Validates the game format (Wild, Standard, Classic, Twist) using an IntEnum

### Gap List

1. No input sanitization beyond version check. The parser does not validate that the decoded byte stream has the expected length. A truncated or corrupted deckstring will cause an unhandled EOFError from _read_varint mid-parse rather than a clean validation error.
2. No trailing-byte detection. After parsing all sections, the parser does not check whether unparsed bytes remain in the stream. A deckstring with extra trailing data would parse without error, silently ignoring the extra content.
3. No card-count validation. The parser accepts any card count, including zero or negative values. A production system would validate that card counts are positive integers within game rules (e.g., 1-2 for constructed, 1+ for arena).
4. No deck-size validation. Neither parse_deckstring nor write_deckstring checks the total number of cards in the deck. Hearthstone decks are 30 cards (constructed) or 40 (some formats). The parser accepts any count without warning.
5. No card-ID validation. Card IDs (DBF IDs) are parsed as raw integers with no check against a valid card database. A deckstring containing non-existent card IDs would parse successfully.
6. No human-readable output. The system returns raw integer tuples. There is no capability to resolve card IDs to card names, costs, classes, or any other metadata.
7. No format-version migration. The parser rejects any deckstring with a version other than 1. If Blizzard releases version 2 of the format, the parser will fail rather than attempting graceful degradation.
8. No logging or error context. When parsing fails (ValueError, EOFError), the error messages include the raw value but not the position in the byte stream or which section was being parsed.
9. No serialization to standard interchange formats. The Deck class has no to_dict(), to_json(), or __repr__ method. Inspecting or transmitting deck data requires manual attribute access.
10. No concurrent/batch processing. The module processes one deckstring at a time. A production system handling bulk imports would benefit from batch processing, streaming, or async support.

### Source Code

```python
"""
Blizzard Deckstring format support
"""

import base64
from io import BytesIO
from typing import IO, List, Optional, Sequence, Tuple

from .enums import FormatType


DECKSTRING_VERSION = 1


CardList = List[int]
CardIncludeList = List[Tuple[int, int]]
SideboardList = List[Tuple[int, int, int]]


def _read_varint(stream: IO) -> int:
	shift = 0
	result = 0
	while True:
		c = stream.read(1)
		if c == "":
			raise EOFError("Unexpected EOF while reading varint")
		i = ord(c)
		result |= (i & 0x7f) << shift
		shift += 7
		if not (i & 0x80):
			break

	return result


def _write_varint(stream: IO, i: int) -> int:
	buf = b""
	while True:
		towrite = i & 0x7f
		i >>= 7
		if i:
			buf += bytes((towrite | 0x80, ))
		else:
			buf += bytes((towrite, ))
			break

	return stream.write(buf)


class Deck:
	@classmethod
	def from_deckstring(cls, deckstring: str) -> "Deck":
		instance = cls()
		(
			instance.cards,
			instance.heroes,
			instance.format,
			instance.sideboards,
		) = parse_deckstring(deckstring)
		return instance

	def __init__(self):
		self.cards: CardIncludeList = []
		self.sideboards: SideboardList = []
		self.heroes: CardList = []
		self.format: FormatType = FormatType.FT_UNKNOWN

	@property
	def as_deckstring(self) -> str:
		return write_deckstring(self.cards, self.heroes, self.format, self.sideboards)

	def get_dbf_id_list(self) -> CardIncludeList:
		return sorted(self.cards, key=lambda x: x[0])

	def get_sideboard_dbf_id_list(self) -> SideboardList:
		return sorted(self.sideboards, key=lambda x: x[0])


def trisort_cards(cards: Sequence[tuple]) -> Tuple[
	List[tuple], List[tuple], List[tuple]
]:
	cards_x1: List[tuple] = []
	cards_x2: List[tuple] = []
	cards_xn: List[tuple] = []

	for card_elem in cards:
		sideboard_owner = None
		if len(card_elem) == 3:
			# Sideboard
			cardid, count, sideboard_owner = card_elem
		else:
			cardid, count = card_elem

		if count == 1:
			list = cards_x1
		elif count == 2:
			list = cards_x2
		else:
			list = cards_xn

		if len(card_elem) == 3:
			list.append((cardid, count, sideboard_owner))
		else:
			list.append((cardid, count))

	return cards_x1, cards_x2, cards_xn


def parse_deckstring(deckstring) -> (
	Tuple[CardIncludeList, CardList, FormatType, SideboardList]
):
	decoded = base64.b64decode(deckstring)
	data = BytesIO(decoded)

	# Header section

	if data.read(1) != b"\0":
		raise ValueError("Invalid deckstring")

	version = _read_varint(data)
	if version != DECKSTRING_VERSION:
		raise ValueError("Unsupported deckstring version %r" % (version))

	format = _read_varint(data)
	try:
		format = FormatType(format)
	except ValueError:
		raise ValueError("Unsupported FormatType in deckstring %r" % (format))

	# Heroes section

	heroes: CardList = []
	num_heroes = _read_varint(data)
	for i in range(num_heroes):
		heroes.append(_read_varint(data))
	heroes.sort()

	# Cards section

	cards: CardIncludeList = []

	num_cards_x1 = _read_varint(data)
	for i in range(num_cards_x1):
		card_id = _read_varint(data)
		cards.append((card_id, 1))

	num_cards_x2 = _read_varint(data)
	for i in range(num_cards_x2):
		card_id = _read_varint(data)
		cards.append((card_id, 2))

	num_cards_xn = _read_varint(data)
	for i in range(num_cards_xn):
		card_id = _read_varint(data)
		count = _read_varint(data)
		cards.append((card_id, count))

	cards.sort()

	# Sideboards section

	sideboards = []

	has_sideboards = data.read(1) == b"\1"

	if has_sideboards:
		num_sideboards_x1 = _read_varint(data)
		for i in range(num_sideboards_x1):
			card_id = _read_varint(data)
			sideboard_owner = _read_varint(data)
			sideboards.append((card_id, 1, sideboard_owner))

		num_sideboards_x2 = _read_varint(data)
		for i in range(num_sideboards_x2):
			card_id = _read_varint(data)
			sideboard_owner = _read_varint(data)
			sideboards.append((card_id, 2, sideboard_owner))

		num_sideboards_xn = _read_varint(data)
		for i in range(num_sideboards_xn):
			card_id = _read_varint(data)
			count = _read_varint(data)
			sideboard_owner = _read_varint(data)
			sideboards.append((card_id, count, sideboard_owner))

	sideboards.sort(key=lambda x: (x[2], x[0]))

	return cards, heroes, format, sideboards


def write_deckstring(
	cards: CardIncludeList,
	heroes: CardList,
	format: FormatType,
	sideboards: Optional[SideboardList] = None,
) -> str:
	if sideboards is None:
		sideboards = []

	data = BytesIO()
	data.write(b"\0")
	_write_varint(data, DECKSTRING_VERSION)
	_write_varint(data, int(format))

	if len(heroes) != 1:
		raise ValueError("Unsupported hero count %i" % (len(heroes)))
	_write_varint(data, len(heroes))
	for hero in sorted(heroes):
		_write_varint(data, hero)

	cards_x1, cards_x2, cards_xn = trisort_cards(cards)

	sort_key = lambda x: x[0]

	for cardlist in sorted(cards_x1, key=sort_key), sorted(cards_x2, key=sort_key):
		_write_varint(data, len(cardlist))
		for cardid, _ in cardlist:
			_write_varint(data, cardid)

	_write_varint(data, len(cards_xn))
	for cardid, count in sorted(cards_xn, key=sort_key):
		_write_varint(data, cardid)
		_write_varint(data, count)

	if len(sideboards) > 0:
		data.write(b"\1")

		sideboards_x1, sideboards_x2, sideboards_xn = trisort_cards(sideboards)

		sb_sort_key = lambda x: (x[2], x[0])

		for cardlist in (
			sorted(sideboards_x1, key=sb_sort_key),
			sorted(sideboards_x2, key=sb_sort_key)
		):
			_write_varint(data, len(cardlist))
			for cardid, _, sideboard_owner in cardlist:
				_write_varint(data, cardid)
				_write_varint(data, sideboard_owner)

		_write_varint(data, len(sideboards_xn))
		for cardid, count, sideboard_owner in sorted(sideboards_xn, key=sb_sort_key):
			_write_varint(data, cardid)
			_write_varint(data, count)
			_write_varint(data, sideboard_owner)

	else:
		data.write(b"\0")

	encoded = base64.b64encode(data.getvalue())
	return encoded.decode("utf-8")
```

---

## Problem: RSS Feed Reader

- repo: https://github.com/rainygirl/rreader
- license: MIT
- commit: a8dcd12aab0ce673582891a51514ab5247c0a300
- source_file: results/round3/phase0b/sources/rreader.py

### Working Capabilities

1. Multi-source RSS fetching: Iterates over a dictionary of {source_name: url} pairs, fetching and parsing each feed
2. Entry normalization: Extracts title, link, author, and publication timestamp from each feed entry into a uniform JSON structure
3. Timezone-aware date formatting: Converts UTC timestamps to a configured timezone (KST), formats as "HH:MM" for today's entries and "Mon DD, HH:MM" for older ones
4. Per-category output: Writes separate JSON files per category (e.g., rss_tech.json, rss_news.json)
5. Chronological sorting: Sorts entries by timestamp in reverse chronological order
6. Feeds configuration management: Reads feed URLs from a feeds.json config file, merges bundled defaults with user customizations
7. Author attribution: Optionally shows per-entry authors (configurable per category via show_author)
8. Selective category fetching: Can fetch a single category or all categories via the target_category parameter
9. Logging mode: Optional stdout progress logging during fetch

### Gap List

1. No HTTP error handling. feedparser.parse(url) silently absorbs HTTP errors (404, 500, timeout). The bare except at line 32 catches everything and calls sys.exit(), killing the entire process on the first failed feed rather than skipping it and continuing.
2. No feed validation. The code does not check whether the parsed feed contains valid data. An empty feed, a non-RSS URL, or a redirect to an HTML page would produce zero entries with no warning.
3. No deduplication across fetches. Each call overwrites the entire category JSON file. If two feeds in the same category contain the same article, both copies appear in the output. The id field uses the Unix timestamp, so entries published at the same second will collide.
4. No content extraction. Only title, link, author, and date are captured. The feed entry's description/summary, content body, categories/tags, enclosures (podcasts, images), and media elements are discarded.
5. No caching or conditional fetching. Every invocation fetches every feed from scratch. There is no ETag or Last-Modified header support, no If-Modified-Since requests, and no local cache.
6. No rate limiting or throttling. All feeds in a category are fetched sequentially with no delay between requests. A category with 20 feeds sends 20 requests in rapid succession.
7. No persistent state. The system writes output JSON but maintains no state about what has been seen before. There is no read/unread tracking, no "last fetched" timestamp per feed, and no way to show only new entries since the last run.
8. No error recovery or retry. A single network failure terminates the entire process (sys.exit()). There is no retry logic, no exponential backoff, and no partial-success handling.
9. No feed discovery or OPML import/export. Feeds must be manually added to feeds.json. There is no auto-discovery from website URLs, no OPML import for migrating from other readers, and no OPML export.
10. No output format flexibility. Output is hardcoded to JSON files in a specific structure. There is no support for rendering to HTML, terminal display, email digest, or any other presentation format.

### Source Code

```python
import datetime
import feedparser
import json
import os
import shutil
import sys
import time

try:
    from .common import p, FEEDS_FILE_NAME
    from .config import TIMEZONE
except ImportError:
    from rreader.common import p, FEEDS_FILE_NAME
    from rreader.config import TIMEZONE


def do(target_category=None, log=False):
    def get_feed_from_rss(category, urls, show_author=False, log=False):

        rslt = {}

        for source, url in urls.items():
            try:
                if log:
                    sys.stdout.write(f"- {url}")

                d = feedparser.parse(url)

                if log:
                    sys.stdout.write(" - Done\n")

            except:
                sys.exit(" - Failed\n" if log else 0)

            for feed in d.entries:

                try:
                    parsed_time = getattr(feed, 'published_parsed', None) or getattr(feed, 'updated_parsed', None)
                    if not parsed_time:
                        continue
                    at = (
                        datetime.datetime(*parsed_time[:6])
                        .replace(tzinfo=datetime.timezone.utc)
                        .astimezone(TIMEZONE)
                    )
                except:
                    continue

                pubDate = at.strftime(
                    "%H:%M" if at.date() == datetime.date.today() else "%b %d, %H:%M"
                )

                ts = int(time.mktime(parsed_time))

                author = source
                if show_author:
                    author = getattr(feed, 'author', None) or source

                entries = {
                    "id": ts,
                    "sourceName": author,
                    "pubDate": pubDate,
                    "timestamp": ts,
                    "url": feed.link,
                    "title": feed.title,
                }

                rslt[entries["id"]] = entries

        rslt = [val for key, val in sorted(rslt.items(), reverse=True)]

        rslt = {"entries": rslt, "created_at": int(time.time())}

        with open(
            os.path.join(p["path_data"], f"rss_{category}.json"), "w", encoding="utf-8"
        ) as f:
            f.write(json.dumps(rslt, ensure_ascii=False))

        return rslt

    bundled_feeds_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "feeds.json")

    if not os.path.isfile(FEEDS_FILE_NAME):
        shutil.copyfile(bundled_feeds_file, FEEDS_FILE_NAME)
    else:
        with open(bundled_feeds_file, "r") as fp:
            bundled = json.load(fp)
        with open(FEEDS_FILE_NAME, "r") as fp:
            user = json.load(fp)
        new_categories = {k: v for k, v in bundled.items() if k not in user}
        if new_categories:
            user.update(new_categories)
            with open(FEEDS_FILE_NAME, "w", encoding="utf-8") as fp:
                json.dump(user, fp, indent=4, ensure_ascii=False)

    with open(FEEDS_FILE_NAME, "r") as fp:
        RSS = json.load(fp)

    if target_category:
        return get_feed_from_rss(
            target_category,
            RSS[target_category]["feeds"],
            show_author=RSS[target_category].get("show_author", False),
            log=log,
        )

    for category, d in RSS.items():
        get_feed_from_rss(
            category, d["feeds"], show_author=d.get("show_author", False), log=log
        )


if __name__ == "__main__":
    do()

# --- Inlined from common.py ---
from pathlib import Path
import os

defaultdir = str(Path.home()) + "/"

p = {"pathkeys": ["path_data"], "path_data": defaultdir + ".rreader/"}


FEEDS_FILE_NAME = os.path.join(p["path_data"], "feeds.json")


for d in p["pathkeys"]:
    if not os.path.exists(p[d]):
        os.mkdir(p[d])

# --- Inlined from config.py ---
import datetime

# KST Seoul UTC+9

TIMEZONE = datetime.timezone(datetime.timedelta(hours=9))
```
