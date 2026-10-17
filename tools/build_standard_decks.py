"""Build the Standard baseline decks of the saved gauntlet from the card file (issue #412).

    python tools/build_standard_decks.py [--out examples/gauntlet] [--bulk .cache/oracle_bulk.json] [--add]

These are *baselines*, not the decks anyone plays: one mono-colored deck per color, built by a fixed recipe from the cards the card file
marks Standard-legal and the engine plays completely (`report.unsupported_lines` empty), so that a Standard deck has something to play
against by default. They are only as current as the card file's legality data (a card's `standard_legal` comes from Scryfall when the file
was made), and `gauntlet --check` checks every saved deck against the deck rules and the engine again.

The recipe, per color C: 24 basic lands of C; 36 spells. The creatures are those of one color C (not legendary, no second face), with
mana value 1-5 and power at least 1, scored by `(power + toughness) / (mana value + 1)` plus half a point for each of flying, first
strike, deathtouch, lifelink, trample, haste, vigilance and menace; the removal are the instants and sorceries of color C that destroy
or deal damage to "target creature", cheapest first. The main deck takes four copies of the best seven creatures and of the best two
removal spells (fewer if there are not two; creatures fill the rest); the sideboard is fifteen cards: the next-best creatures and
removal, four copies each. Ties are broken by name, so the same card file gives the same decks.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.getcwd())

from infernal_machine.analysis import is_land  # noqa: E402
from infernal_machine.cards import BulkSource, Card  # noqa: E402
from infernal_machine.report import unsupported_lines  # noqa: E402

COLORS = {"W": ("White", "Plains"), "U": ("Blue", "Island"), "B": ("Black", "Swamp"), "R": ("Red", "Mountain"), "G": ("Green", "Forest")}
KEYWORDS = ("flying", "first strike", "deathtouch", "lifelink", "trample", "haste", "vigilance", "menace")
REMOVAL = re.compile(r"(?:destroy|deals? \d+ damage to) target (?:[\w-]+ )*creature", re.I)
LANDS, SPELLS, SIDEBOARD, COPIES, CREATURE_KINDS, REMOVAL_KINDS = 24, 36, 15, 4, 7, 2


def creature_score(card: Card) -> float:
    stats = (int(card.power) if (card.power or "").isdigit() else 0) + (int(card.toughness) if (card.toughness or "").isdigit() else 0)
    text = card.oracle_text.lower()
    return stats / (card.cmc + 1) + 0.5 * sum(word in text for word in KEYWORDS)


def candidates(cards: list[Card], color: str) -> tuple[list[Card], list[Card]]:
    """(creatures, removal spells) of one color that fit the recipe, best first."""
    playable = [c for c in cards if c.standard_legal and not is_land(c) and set(c.colors) == {color} and "Legendary" not in c.type_line
                and "//" not in c.name and not unsupported_lines(c)]
    creatures = [c for c in playable if "Creature" in c.type_line and 1 <= c.cmc <= 5 and (c.power or "").isdigit() and int(c.power) >= 1]
    removal = [c for c in playable if ("Instant" in c.type_line or "Sorcery" in c.type_line) and REMOVAL.search(c.oracle_text)]
    return (sorted(creatures, key=lambda c: (-creature_score(c), c.name)), sorted(removal, key=lambda c: (c.cmc, c.name)))


def build(cards: list[Card], color: str) -> tuple[list[Card], list[Card]]:
    """(the 36 spells, the 15 of the sideboard) for `color`, with every copy listed."""
    creatures, removal = candidates(cards, color)
    take_removal = removal[:REMOVAL_KINDS]
    take_creatures = creatures[:CREATURE_KINDS + REMOVAL_KINDS - len(take_removal)]
    main = [c for c in take_creatures + take_removal for _ in range(COPIES)]
    rest = creatures[len(take_creatures):] + removal[len(take_removal):]
    side: list[Card] = []
    for card in rest:
        side += [card] * min(COPIES, SIDEBOARD - len(side))
        if len(side) >= SIDEBOARD:
            break
    return main[:SPELLS], side


def write(path: str, color: str, main: list[Card], side: list[Card]) -> None:
    name, land = COLORS[color]
    lines = [f"// Standard baseline: mono-{name.lower()}. Built by tools/build_standard_decks.py from the card file; not a deck anyone plays.", "Deck",
             f"{LANDS} {land}"]
    for group in (main, side):
        counts: dict[str, int] = {}
        for card in group:
            counts[card.name] = counts.get(card.name, 0) + 1
        if group is side:
            lines += ["", "Sideboard"]
        lines += [f"{n} {card}" for card, n in counts.items()]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--out", default="examples/gauntlet")
    parser.add_argument("--bulk", default=".cache/oracle_bulk.json")
    parser.add_argument("--add", action="store_true", help="also save them in the gauntlet (examples/gauntlet.json)")
    args = parser.parse_args(argv)
    cards = list(BulkSource(args.bulk).all_cards()) if hasattr(BulkSource, "all_cards") else _all_cards(args.bulk)
    os.makedirs(args.out, exist_ok=True)
    for color, (name, _) in COLORS.items():
        spells, side = build(cards, color)
        path = os.path.join(args.out, f"standard_{name.lower()}.txt")
        write(path, color, spells, side)
        print(f"{path}: {len(spells)} spells ({len({c.name for c in spells})} kinds), sideboard {len(side)}")
        if args.add:
            from infernal_machine.gauntlet import add

            add(path, bulk=args.bulk, name=f"standard_{name.lower()}")
    return 0


def _all_cards(bulk: str) -> list[Card]:
    with open(bulk, encoding="utf-8") as f:
        return [Card.from_dict(d) for d in json.load(f)["cards"].values()]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
