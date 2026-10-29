"""The combos a deck holds, from Commander Spellbook (https://commanderspellbook.com): issues #487 and #488.

    python -m infernal_machine.combos DECKLIST

One POST to Spellbook's `find-my-combos` per deck, answered from `.cache/combos.json` when the same list was asked before, so a repeat
run is offline and the answer is as current as the cache. The Brackets (brackets.py) raise a deck's floor by the combos it holds, by
Spellbook's bracket tag on each; `analyze` lists them, with whether the engine can play every piece.
"""

from __future__ import annotations

import functools
import io
import json
import os
import sys
import urllib.request
from collections import Counter
from dataclasses import asdict, dataclass

from .cards import Deck, HttpFn, _urlopen_json

BRACKET_TAGS = {"E": "Exhibition", "C": "Core", "O": "Oddball", "P": "Powerful", "S": "Spicy", "R": "Ruthless", "B": "Banned"}
# Spellbook's own conversion of its tags to the Commander Brackets (its search engine uses the same): a Ruthless combo is a two-card
# combo that wins early (not below Bracket 4), Powerful and Spicy are Bracket 3, Core and Oddball Bracket 2. A banned combo has none.
TAG_BRACKET = {"E": 1, "C": 2, "O": 2, "P": 3, "S": 3, "R": 4}
CACHE_FORMAT = 1  # bump when a Combo gains a field: an older cache is fetched again


@dataclass(frozen=True)
class Combo:
    id: str  # Spellbook's variant id, e.g. "742-1295"
    cards: tuple[str, ...]  # the deck's cards it uses
    requires: tuple[str, ...] = ()  # what else it needs, in Spellbook's words ("A creature with power 3 or greater")
    produces: tuple[str, ...] = ()  # what it does: "Exile your library", "Win the game", "Infinite colorless mana"
    tag: str = ""  # Spellbook's bracket tag, one of BRACKET_TAGS
    mana: str = ""  # the mana it needs, as Spellbook writes it: "{U}{U}{B}"
    popularity: int = 0  # how many of EDHREC's decks hold it

    @property
    def tag_name(self) -> str:
        return BRACKET_TAGS.get(self.tag, self.tag or "untagged")

    @property
    def bracket(self) -> int | None:
        """The lowest Bracket this combo may be played at, by Spellbook's tag; None when the tag says nothing (or the combo is banned)."""
        return TAG_BRACKET.get(self.tag)

    def label(self) -> str:
        return " + ".join(self.cards)


@dataclass
class ComboReport:
    identity: str  # the deck's color identity as Spellbook saw it
    included: list[Combo]  # the combos the deck holds
    almost: list[Combo]  # one card away, within the deck's identity


def _combo(variant: dict) -> Combo:
    return Combo(str(variant["id"]), tuple(str(u["card"]["name"]) for u in variant.get("uses", [])),
                 tuple(str(r["template"]["name"]) for r in variant.get("requires", [])),
                 tuple(str(p["feature"]["name"]) for p in variant.get("produces", [])),
                 str(variant.get("bracketTag") or ""), str(variant.get("manaNeeded") or ""), int(variant.get("popularity") or 0))


def _from_saved(saved: dict) -> Combo:
    return Combo(**{**saved, "cards": tuple(saved["cards"]), "requires": tuple(saved["requires"]), "produces": tuple(saved["produces"])})


@functools.lru_cache(maxsize=2)
def _read_decks(path: str, stamp: tuple[int, int]) -> dict:
    """The decks in the cache file at `path`, read once for as long as the file (its modification time and size: `stamp`) stays as it is."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("decks", {}) if data.get("format") == CACHE_FORMAT else {}


def deck_key(deck: Deck) -> str:
    """What Spellbook is asked about: the commanders and the main deck's names with their counts, in one order."""
    counts = Counter(c.name for c in deck.main)
    return " / ".join(sorted(c.name for c in deck.commanders)) + " || " + ", ".join(f"{n} x{counts[n]}" for n in sorted(counts))


@dataclass
class SpellbookSource:
    """Pulls a deck's combos from Commander Spellbook's backend, keeping each answer in `cache_path` (None: no cache)."""

    base_url: str = "https://backend.commanderspellbook.com"
    user_agent: str = "infernal-machine/0.1"
    cache_path: str | None = ".cache/combos.json"
    http: HttpFn = _urlopen_json

    def find(self, deck: Deck) -> ComboReport:
        """The combos `deck` holds and the ones a card away. Raises OSError (urllib's URLError is one) when Spellbook can't be
        reached and the cache has no answer for this deck."""
        key = deck_key(deck)
        decks = self._load()
        saved = decks.get(key)
        if saved is None:
            results = self.http(self._request(deck)).get("results", {})
            saved = {"identity": str(results.get("identity", "")),
                     "included": [asdict(_combo(v)) for v in results.get("included", [])],
                     "almost": [asdict(_combo(v)) for v in results.get("almostIncluded", [])]}
            decks[key] = saved
            self._save(decks)
        return ComboReport(saved["identity"], [_from_saved(c) for c in saved["included"]], [_from_saved(c) for c in saved["almost"]])

    def cached(self, deck: Deck) -> ComboReport | None:
        """The combos `deck` holds if the cache already has an answer for it, else None. Never asks Spellbook and never writes: a bot
        looks its deck up while a game is being set up, so this must be cheap (the cache file is read once while it is unchanged)."""
        if self.cache_path is None or not os.path.exists(self.cache_path):
            return None
        stat = os.stat(self.cache_path)
        saved = _read_decks(self.cache_path, (stat.st_mtime_ns, stat.st_size)).get(deck_key(deck))
        if saved is None:
            return None
        return ComboReport(saved["identity"], [_from_saved(c) for c in saved["included"]], [_from_saved(c) for c in saved["almost"]])

    def _request(self, deck: Deck) -> urllib.request.Request:
        counts = Counter(c.name for c in deck.main)
        body = {"commanders": [{"card": c.name, "quantity": 1} for c in deck.commanders],
                "main": [{"card": name, "quantity": n} for name, n in sorted(counts.items())]}
        headers = {"User-Agent": self.user_agent, "Accept": "application/json", "Content-Type": "application/json"}
        return urllib.request.Request(self.base_url + "/find-my-combos/", data=json.dumps(body).encode(), headers=headers, method="POST")

    def _load(self) -> dict:
        if self.cache_path is None or not os.path.exists(self.cache_path):
            return {}
        with open(self.cache_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("decks", {}) if data.get("format") == CACHE_FORMAT else {}

    def _save(self, decks: dict) -> None:
        if self.cache_path is None:
            return
        os.makedirs(os.path.dirname(self.cache_path) or ".", exist_ok=True)
        partial = self.cache_path + ".tmp"  # written beside the file and renamed over it: a reader in another process (a bot's
        with open(partial, "w", encoding="utf-8") as f:  # `cached` during the tests) sees the old file or the new one, never an empty one
            json.dump({"format": CACHE_FORMAT, "decks": decks}, f)
        os.replace(partial, self.cache_path)


def format_combos(report: ComboReport, playable: dict[str, bool] | None = None) -> str:
    """The combos a deck holds as a text table; `playable` says, per card name, whether the engine plays it fully."""
    if not report.included:
        return "Commander Spellbook knows no combo among these cards."
    rows = [f"Combos the deck holds ({len(report.included)}, from Commander Spellbook):",
            f"{'cards':<52} {'produces':<40} {'mana':<14} {'tag':<10} {'decks':>7}  engine"]
    for combo in report.included:
        if playable is None:
            engine = ""
        else:
            blocked = [name for name in combo.cards if not playable.get(name, True)]
            engine = "plays" if not blocked else f"can't play {', '.join(blocked)}"
        needs = combo.label() + (f" (needs {', '.join(combo.requires)})" if combo.requires else "")
        rows.append(f"{needs:<52} {', '.join(combo.produces):<40} {combo.mana or '-':<14} {combo.tag_name:<10} {combo.popularity:>7}  {engine}")
    return "\n".join(rows)


def main(argv: list[str]) -> int:
    from .cards import BulkSource, load_deck

    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) != 2:
        print("usage: python -m infernal_machine.combos DECKLIST", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        deck = load_deck(f.read(), BulkSource(".cache/oracle_bulk.json"))
    try:
        report = SpellbookSource().find(deck)
    except OSError as error:
        print(f"Error: Commander Spellbook could not be reached and the cache has no answer for this deck ({error}).", file=sys.stderr)
        return 2
    print(format_combos(report))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
