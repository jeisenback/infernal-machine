"""Model a Commander deck from the card pool: the commander's colors, some cards you name, the rest by how played each card is (#475).

    python tools/model_deck.py examples/decks/modelled.json [--pool .cache/commander_pool.json] [--out examples/decks]

The spec is a list of {"name": FILE, "commanders": [...], "core": [...]}. For each, the deck is the commander (or the pair), then the
`core` cards that exist, are Commander-legal and fit the colors, then the most played cards of those colors (Scryfall's EDHREC rank, one
copy each), 36 lands in all: the most played nonbasic lands of the colors, then basics split by the colored symbols of the spells.

This is a *model* of a typical deck, not a list anyone played: the same idea as the audit's modelled deck, and for the same job, aiming
the coverage work at cards that decks actually run. Real lists (examples/decks/*_edhrec_average.txt) are better; these exist so the
tracked decks cover more commanders than anyone has exported. It reads the card pool only (offline) and is deterministic for a pool.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

COLORS = "WUBRG"
BASICS = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
SKIPPED_LAYOUTS = {"token", "double_faced_token", "emblem", "art_series", "vanguard", "scheme", "plane", "phenomenon", "planar"}
LANDS = 36
NONBASIC_LANDS = 12


def rank_of(card: dict) -> float:
    rank = card.get("edhrec_rank")
    return rank if isinstance(rank, int) else float("inf")


def usable(card: dict) -> bool:
    return card.get("layout") not in SKIPPED_LAYOUTS and card.get("legalities", {}).get("commander") == "legal"


def model(pool: dict[str, dict], commanders: list[str], core: list[str]) -> tuple[list[str], list[str], list[str]]:
    """(the main deck's card names, one copy each plus the basics repeated, the commanders, the core cards left out and why)."""
    chosen = [pool[name] for name in commanders]
    identity = {c for card in chosen for c in card.get("color_identity", [])}
    taken = set(commanders)

    def fits(card: dict) -> bool:
        return usable(card) and set(card.get("color_identity", [])) <= identity and card["name"] not in taken

    left_out = []
    spells: list[str] = []
    lands: list[str] = []
    for name in core:
        card = pool.get(name)
        if card is None:
            left_out.append(f"{name} (not in the Commander pool: banned, renamed or misspelled)")
        elif not usable(card):
            left_out.append(f"{name} (not Commander-legal)")
        elif not fits(card):
            left_out.append(f"{name} (outside the commander's colors)")
        elif "Land" in card["type_line"]:
            lands.append(name)
        elif name not in spells:
            spells.append(name)
    seated = set(spells) | set(lands) | taken
    by_rank = sorted((card for card in pool.values() if fits(card) and card["name"] not in seated), key=lambda card: (rank_of(card), card["name"]))
    total = 100 - len(commanders)
    for card in by_rank:
        if "Land" in card["type_line"]:
            if len(lands) < NONBASIC_LANDS and "Basic" not in card["type_line"]:
                lands.append(card["name"])
        elif len(spells) < total - LANDS:
            spells.append(card["name"])
    pips = {c: 0 for c in COLORS if c in identity}
    for name in spells:
        for symbol in re.findall(r"\{([WUBRG])\}", pool[name].get("mana_cost") or ""):
            if symbol in pips:
                pips[symbol] += 1
    for card in chosen:
        for symbol in re.findall(r"\{([WUBRG])\}", card.get("mana_cost") or ""):
            if symbol in pips:
                pips[symbol] += 1
    basics_needed = total - len(spells) - len(lands)
    basics: list[str] = []
    if pips:
        weight = sum(pips.values()) or len(pips)
        quotas = {c: basics_needed * (pips[c] or 1) // (weight if sum(pips.values()) else len(pips)) for c in pips}
        order = sorted(pips, key=lambda c: (-pips[c], c))
        while sum(quotas.values()) < basics_needed:
            for c in order:
                if sum(quotas.values()) < basics_needed:
                    quotas[c] += 1
        for c in order:
            basics += [BASICS[c]] * quotas[c]
    else:
        basics = ["Wastes"] * basics_needed
    return spells + lands + basics, list(commanders), left_out


def decklist(commanders: list[str], main: list[str]) -> str:
    counts: dict[str, int] = {}
    for name in main:
        counts[name] = counts.get(name, 0) + 1
    lines = ["Commander", *(f"1 {name}" for name in commanders), "", "Deck", *(f"{n} {name}" for name, n in counts.items())]
    return "\n".join(lines) + "\n"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec")
    parser.add_argument("--pool", default=".cache/commander_pool.json")
    parser.add_argument("--out", default="examples/decks")
    args = parser.parse_args(argv)
    with open(args.pool, encoding="utf-8") as f:
        pool = {d["name"]: d for d in json.load(f)}
    with open(args.spec, encoding="utf-8") as f:
        specs = json.load(f)
    for spec in specs:
        missing = [name for name in spec["commanders"] if name not in pool]
        if missing:
            print(f"{spec['name']}: no such commander in the pool: {', '.join(missing)}", file=sys.stderr)
            return 2
        main_deck, commanders, left_out = model(pool, spec["commanders"], spec.get("core", []))
        path = os.path.join(args.out, spec["name"] + ".txt")
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(decklist(commanders, main_deck))
        print(f"{path}: {len(main_deck) + len(commanders)} cards" + "".join(f"\n  left out: {why}" for why in left_out))
    return 0


if __name__ == "__main__":
    if isinstance(sys.stdout, __import__("io").TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv[1:]))
