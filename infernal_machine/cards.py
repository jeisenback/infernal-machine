"""Card data and sources that pull card definitions from outside the engine."""

from __future__ import annotations

import gzip
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Protocol


class CardNotFound(LookupError):
    pass


@dataclass(frozen=True)
class Card:
    name: str
    mana_cost: str = ""
    cmc: float = 0.0
    type_line: str = ""
    oracle_text: str = ""
    colors: tuple[str, ...] = ()
    power: str | None = None
    toughness: str | None = None
    loyalty: str | None = None
    color_identity: tuple[str, ...] = ()
    produced_mana: tuple[str, ...] = ()
    commander_legal: bool = True
    scryfall_id: str | None = None
    back: "Card | None" = None  # a modal double-faced card's land back face, which can be played instead (Pathways)

    @classmethod
    def from_scryfall(cls, data: dict) -> "Card":
        # Double-faced cards keep their rules text on the faces; use the front face.
        face = data["card_faces"][0] if "card_faces" in data and "oracle_text" not in data else data
        back = None
        produced = tuple(data.get("produced_mana", []))
        if data.get("layout") == "modal_dfc" and len(data.get("card_faces", [])) == 2:
            produced = _face_mana(face, produced)
            back_face = data["card_faces"][1]
            if "Land" in back_face.get("type_line", ""):
                back = cls(name=back_face["name"], type_line=back_face["type_line"],
                           oracle_text=back_face.get("oracle_text", ""),
                           color_identity=tuple(data.get("color_identity", [])),
                           produced_mana=_face_mana(back_face, tuple(data.get("produced_mana", []))),
                           commander_legal=data.get("legalities", {}).get("commander") == "legal",
                           scryfall_id=data.get("id"))
        return cls(
            name=data["name"],
            mana_cost=face.get("mana_cost", ""),
            cmc=float(data.get("cmc", 0)),
            type_line=face.get("type_line", data.get("type_line", "")),
            oracle_text=face.get("oracle_text", ""),
            colors=tuple(face.get("colors", data.get("colors", []))),
            power=face.get("power"),
            toughness=face.get("toughness"),
            loyalty=face.get("loyalty"),
            color_identity=tuple(data.get("color_identity", [])),
            produced_mana=produced,
            commander_legal=data.get("legalities", {}).get("commander") == "legal",
            scryfall_id=data.get("id"),
            back=back,
        )

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        tuples = {key: tuple(data.get(key, ())) for key in ("colors", "color_identity", "produced_mana")}
        back = cls.from_dict(data["back"]) if data.get("back") else None
        return cls(**{**data, **tuples, "back": back})

    def to_dict(self) -> dict:
        return asdict(self)


def _face_mana(face: dict, produced: tuple[str, ...]) -> tuple[str, ...]:
    """The mana one face of a double-faced land makes: the symbols in its "{T}: Add {G}." text, among the card's."""
    runs = re.findall(r"Add ((?:\{[WUBRGC]\})+)", face.get("oracle_text", ""))
    symbols = {symbol for run in runs for symbol in re.findall(r"[WUBRGC]", run)}
    return tuple(m for m in produced if m in symbols) if symbols else produced


_REMINDER = re.compile(r"\s*\([^)]*\)")


def has_keyword(card: Card, keyword: str) -> bool:
    """Whether a keyword line ("Flash", "Flying, hexproof", with or without reminder text) has `keyword`."""
    for line in card.oracle_text.splitlines():
        if keyword.lower() in _REMINDER.sub("", line).lower().split(", "):
            return True
    return False


class CardSource(Protocol):
    def get(self, name: str) -> Card: ...

    def get_many(self, names: Iterable[str]) -> dict[str, Card]: ...


HttpFn = Callable[[urllib.request.Request], dict]


def _urlopen_json(request: urllib.request.Request) -> dict:
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


@dataclass
class ScryfallSource:
    """Pulls cards from the Scryfall API (https://scryfall.com/docs/api).

    Scryfall asks clients to send a User-Agent and Accept header and to keep
    to roughly 10 requests per second, so calls are spaced by `min_interval`.
    """

    base_url: str = "https://api.scryfall.com"
    user_agent: str = "infernal-machine/0.1"
    min_interval: float = 0.1
    http: HttpFn = _urlopen_json
    _last_call: float = field(default=0.0, repr=False)

    COLLECTION_BATCH = 75  # Scryfall's limit per /cards/collection request

    def get(self, name: str) -> Card:
        query = urllib.parse.urlencode({"exact": name})
        try:
            data = self._call(f"/cards/named?{query}")
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise CardNotFound(name) from err
            raise
        return Card.from_scryfall(data)

    def get_many(self, names: Iterable[str]) -> dict[str, Card]:
        wanted = list(dict.fromkeys(names))
        found: dict[str, Card] = {}
        missing: list[str] = []
        for start in range(0, len(wanted), self.COLLECTION_BATCH):
            batch = wanted[start : start + self.COLLECTION_BATCH]
            # /cards/collection doesn't find "Fire // Ice", only "Fire", so send the front face.
            fronts = {n.split(" // ")[0].lower(): n for n in batch}
            body = {"identifiers": [{"name": front} for front in fronts]}
            data = self._call("/cards/collection", body)
            for card_data in data.get("data", []):
                card = Card.from_scryfall(card_data)
                found[card.name] = card
            missing += [fronts.get(ident["name"], ident["name"]) for ident in data.get("not_found", [])]
        if missing:
            raise CardNotFound(", ".join(missing))
        return _match_requested(wanted, found)

    def _call(self, path: str, body: dict | None = None) -> dict:
        wait = self.min_interval - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        headers = {"User-Agent": self.user_agent, "Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        request = urllib.request.Request(self.base_url + path, data=data, headers=headers)
        try:
            return self.http(request)
        finally:
            self._last_call = time.monotonic()


def _match_requested(wanted: list[str], found: dict[str, Card]) -> dict[str, Card]:
    """Key results by the names the caller asked for.

    Scryfall matches case-insensitively and returns full names for split and
    double-faced cards (e.g. "Fire // Ice"), so map requests back to results.
    """
    by_lower = {name.lower(): card for name, card in found.items()}
    for name, card in found.items():
        for part in name.split(" // "):
            by_lower.setdefault(part.lower(), card)
    result = {}
    for name in wanted:
        card = by_lower.get(name.lower())
        if card is None:
            raise CardNotFound(name)
        result[name] = card
    return result


class CachedSource:
    """Wraps another source with a JSON file cache so repeat lookups stay offline."""

    def __init__(self, source: CardSource, path: str | Path):
        self.source = source
        self.path = Path(path)
        self._cards: dict[str, Card] = {}
        if self.path.exists():
            raw = json.loads(self.path.read_text())
            self._cards = {key: Card.from_dict(value) for key, value in raw.items()}

    def get(self, name: str) -> Card:
        return self.get_many([name])[name]

    def get_many(self, names: Iterable[str]) -> dict[str, Card]:
        wanted = list(dict.fromkeys(names))
        missing = [n for n in wanted if n.lower() not in self._cards]
        if missing:
            for name, card in self.source.get_many(missing).items():
                self._cards[name.lower()] = card
            self._save()
        return {n: self._cards[n.lower()] for n in wanted}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {key: card.to_dict() for key, card in self._cards.items()}
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _download_jsonl(request: urllib.request.Request) -> list[dict]:
    """A gzipped JSON-lines file, which is how Scryfall serves its bulk data."""
    with urllib.request.urlopen(request, timeout=300) as response, gzip.open(response, "rt", encoding="utf-8") as lines:
        return [json.loads(line) for line in lines if line.strip()]


# Bulk-data layouts that aren't cards a deck can hold.
_NON_CARD_LAYOUTS = {"token", "double_faced_token", "emblem", "art_series", "vanguard", "scheme", "planar",
                     "augment", "host"}


class BulkSource:
    """Looks cards up in Scryfall's "Oracle Cards" bulk file instead of calling the API per card.

    The file (one entry per card, about 25 MB gzipped) is downloaded once, converted to a slim JSON file at `path`, and
    reused until it is `max_age_days` old. After that every lookup is offline.
    """

    def __init__(self, path: str | Path, max_age_days: float = 7.0, base_url: str = "https://api.scryfall.com",
                 user_agent: str = "infernal-machine/0.1", http: HttpFn = _urlopen_json,
                 download: Callable[[urllib.request.Request], list[dict]] = _download_jsonl):
        self.path = Path(path)
        self.max_age_days = max_age_days
        self.base_url = base_url
        self.user_agent = user_agent
        self.http = http
        self.download = download
        self._index: dict[str, Card] | None = None

    def get(self, name: str) -> Card:
        return self.get_many([name])[name]

    def get_many(self, names: Iterable[str]) -> dict[str, Card]:
        index = self._load()
        wanted = list(dict.fromkeys(names))
        missing = [n for n in wanted if n.lower() not in index]
        if missing:
            raise CardNotFound(", ".join(missing))
        return {n: index[n.lower()] for n in wanted}

    def refresh(self) -> int:
        """Download the bulk file now, replacing the saved copy. Returns how many cards it holds."""
        listing = self._request(self.http, f"{self.base_url}/bulk-data")
        entry = next((e for e in listing["data"] if e["type"] == "oracle_cards"), None)
        if entry is None:
            raise LookupError("Scryfall's bulk-data list has no oracle_cards file")
        data = self._request(self.download, entry["jsonl_download_uri"])
        cards = [Card.from_scryfall(d) for d in data if d.get("layout") not in _NON_CARD_LAYOUTS]
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({card.name: card.to_dict() for card in cards}))
        self._index = _name_index(cards)
        return len(cards)

    def _load(self) -> dict[str, Card]:
        if self._index is None:
            if not self.path.exists() or time.time() - self.path.stat().st_mtime > self.max_age_days * 86400:
                try:
                    self.refresh()
                except (OSError, LookupError):
                    if not self.path.exists():
                        raise  # no copy to fall back on
            if self._index is None:
                raw = json.loads(self.path.read_text())
                self._index = _name_index(Card.from_dict(value) for value in raw.values())
        return self._index

    def _request(self, send: Callable, url: str):
        return send(urllib.request.Request(url, headers={"User-Agent": self.user_agent, "Accept": "*/*"}))


def _name_index(cards: Iterable[Card]) -> dict[str, Card]:
    """Cards by lowercase full name, plus each face of a split or double-faced card ("Fire", "Ice", "Fire // Ice")."""
    cards = list(cards)
    index: dict[str, Card] = {}
    for card in cards:
        index[card.name.lower()] = card
    for position in (0, 1, 2):  # front faces first, so "Fire" is "Fire // Ice", not "Start // Fire"
        for card in cards:
            parts = card.name.split(" // ")
            if position < len(parts):
                index.setdefault(parts[position].lower(), card)
    return index


_DECK_LINE = re.compile(r"^(\d+)x?\s+(.+?)(?:\s+\([A-Z0-9]+\)\s*[^\s*]*)?$")
_MARKER = re.compile(r"\s*\*([A-Z]+)\*")  # Moxfield-style tags: *CMDR*, *F* (foil), *E* (etched)


@dataclass
class Decklist:
    """Card name -> count for each section of a decklist."""

    commanders: dict[str, int] = field(default_factory=dict)
    main: dict[str, int] = field(default_factory=dict)
    sideboard: dict[str, int] = field(default_factory=dict)


def parse_decklist(text: str) -> Decklist:
    """Parse an Arena/MTGO/Moxfield style decklist.

    Accepts lines like "4 Lightning Bolt", "4x Lightning Bolt",
    "4 Lightning Bolt (M11) 146" and "1 Atraxa, Praetors' Voice *CMDR*".
    "Commander", "Deck" and "Sideboard" headers switch sections; a blank line
    after main-deck cards starts the sideboard. "//" lines are comments.
    """
    deck = Decklist()
    sections = {"commander": deck.commanders, "deck": deck.main, "sideboard": deck.sideboard}
    current = deck.main
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            if current is deck.main and deck.main:
                current = deck.sideboard
            continue
        if line.startswith("//"):
            continue
        header = line.lower().rstrip(":")
        if header in sections:
            current = sections[header]
            continue
        markers = set(_MARKER.findall(line))
        match = _DECK_LINE.match(_MARKER.sub("", line))
        if not match:
            raise ValueError(f"Unrecognised decklist line: {raw!r}")
        count, name = int(match.group(1)), match.group(2).strip()
        target = deck.commanders if "CMDR" in markers else current
        target[name] = target.get(name, 0) + count
    return deck


@dataclass
class Deck:
    commanders: list[Card]
    main: list[Card]
    sideboard: list[Card]


def load_deck(text: str, source: CardSource) -> Deck:
    """Parse a decklist and pull every card from `source`, expanded by count."""
    parsed = parse_decklist(text)
    cards = source.get_many([*parsed.commanders, *parsed.main, *parsed.sideboard])
    expand = lambda counts: [cards[name] for name, n in counts.items() for _ in range(n)]
    return Deck(expand(parsed.commanders), expand(parsed.main), expand(parsed.sideboard))
