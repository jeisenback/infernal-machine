"""Card data and sources that pull card definitions from outside the engine."""

from __future__ import annotations

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

    @classmethod
    def from_scryfall(cls, data: dict) -> "Card":
        # Double-faced cards keep their rules text on the faces; use the front face.
        face = data["card_faces"][0] if "card_faces" in data and "oracle_text" not in data else data
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
            produced_mana=tuple(data.get("produced_mana", [])),
            commander_legal=data.get("legalities", {}).get("commander") == "legal",
            scryfall_id=data.get("id"),
        )

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        tuples = {key: tuple(data.get(key, ())) for key in ("colors", "color_identity", "produced_mana")}
        return cls(**{**data, **tuples})

    def to_dict(self) -> dict:
        return asdict(self)


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
            body = {"identifiers": [{"name": n} for n in batch]}
            data = self._call("/cards/collection", body)
            for card_data in data.get("data", []):
                card = Card.from_scryfall(card_data)
                found[card.name] = card
            missing += [ident["name"] for ident in data.get("not_found", [])]
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
