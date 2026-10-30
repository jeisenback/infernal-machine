"""Which cards can lead a Pauper Commander deck (#527).

PDH Home Base's rules: "The commander must be an uncommon creature, vehicle, or spacecraft and does not need to be legendary", and "If a
card has been printed at a specific rarity, it is classified under that rarity. This classification is based on paper and MTGO
releases, excluding Arena." The format is "a variation of the original Commander format", so Commander's pairs carry over: two
uncommon partners, or an uncommon "Choose a Background" creature with an uncommon Background (the community guides say so too). The
card file keeps one printing of each card, so it can't say whether a card was ever printed at uncommon; Scryfall's search can (`r:uncommon` matches a card if any printing is uncommon). The names it returns are kept in a file
for a week, like the coverage audit's pools. Scryfall's `paupercommander` legality covers the other 99 (printed at common) and the
ban list.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request

from .cards import Card, HttpFn, _urlopen_json

SEARCH = "(t:creature or t:vehicle or t:spacecraft or t:background) r:uncommon (game:paper or game:mtgo)"
CACHE = os.path.join(".cache", "paupercommander_commanders.json")
_KINDS = ("Creature", "Vehicle", "Spacecraft")


def uncommon_commanders(path: str = CACHE, max_age_days: float = 7.0, http: HttpFn = _urlopen_json) -> frozenset[str]:
    """The names of the creatures, vehicles, spacecraft and Backgrounds with an uncommon printing in paper or on MTGO, from `path` if
    it is fresh and holds this search's answer, else from Scryfall's search (then saved there). Raises OSError when Scryfall can't be
    reached and there is no file, and ValueError if Scryfall ignored part of the search."""
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < max_age_days * 86400:
        with open(path, encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict) and saved.get("search") == SEARCH:
            return frozenset(saved["names"])
    url: str | None = "https://api.scryfall.com/cards/search?" + urllib.parse.urlencode({"q": SEARCH, "unique": "cards"})
    names: list[str] = []
    while url:
        page = http(urllib.request.Request(url, headers={"User-Agent": "infernal-machine/0.1", "Accept": "application/json"}))
        if page.get("warnings"):
            raise ValueError(f"Scryfall did not run the search for Pauper Commander's commanders: {' '.join(page['warnings'])}")
        names += [card["name"] for card in page["data"]]
        url = page.get("next_page")
        time.sleep(0.11)  # Scryfall asks for at most ten requests a second
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"search": SEARCH, "names": sorted(names)}, f)
    return frozenset(names)


def can_lead(card: Card, uncommon: frozenset[str], paired: bool = False) -> bool:
    """Whether `card` may be a Pauper Commander deck's commander: an uncommon creature, vehicle or spacecraft, legendary or not; and,
    as the second of a pair (`paired`: the pair itself is Commander's to judge, `commander.valid_pair`), an uncommon Background."""
    return card.name in uncommon and (any(kind in card.type_line for kind in _KINDS) or (paired and "Background" in card.type_line))
