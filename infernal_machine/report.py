"""Which cards in a deck the engine can't fully play yet, grouped by what's missing.

Run it on a decklist file (cards are fetched from Scryfall and cached):

    python -m infernal_machine.report deck.txt
"""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from dataclasses import dataclass

from .analysis import is_land
from .cards import Card, Deck
from .effects import (activated_abilities, is_enters_with_counters, is_mana_ability, line_effects, rules_lines,
                      static_abilities, triggered_abilities)
from .mana import parse_cost

# Keywords the engine implements (combat.py, game.py).
SUPPORTED_KEYWORDS = {
    "flying", "reach", "vigilance", "haste", "defender", "menace", "trample", "first strike",
    "double strike", "deathtouch", "lifelink", "indestructible", "hexproof", "shroud", "flash",
}
# Lines that only matter when building the deck, which commander.py checks.
_DECKBUILDING = re.compile(
    r"(partner( with .+|—.+)?|friends forever|choose a background|doctor's companion"
    r"|CARDNAME can be your commander\.|A deck can have (any number of|up to \w+) cards named CARDNAME\.)",
    re.I,
)

# Rough buckets for unsupported lines, checked in order; they point at what to build next.
_CATEGORIES = [
    ("activated abilities", re.compile(r"^[^\"]*\{[^}]+\}[^\"]*:|^[−+]?\d+:|^\+\d+:|^0:")),
    ("triggers (the trigger or its effect)", re.compile(r"^(when|whenever|at the beginning|at end)", re.I)),
    ("tokens", re.compile(r"\btokens?\b", re.I)),
    ("+1/+1 and other counters", re.compile(r"\bcounters?\b(?! target)", re.I)),
    ("exile", re.compile(r"\bexile", re.I)),
    ("return to hand", re.compile(r"return .* to (its|their) owner's hand", re.I)),
    ("pump and static buffs", re.compile(r"get [+-]\d+/[+-]\d+|gets [+-]\d+/[+-]\d+", re.I)),
    ("enters tapped", re.compile(r"enters tapped", re.I)),
    # Keyword abilities, possibly with a cost or number: "Protection from red", "Ward {2}", "Evoke {2}{U}".
    ("other keywords", re.compile(r"^[a-z' ]+((\{[^}]+\})+|\d+)?(, [a-z' ]+((\{[^}]+\})+|\d+)?)*$", re.I)),
]


@dataclass
class CardReport:
    card: Card
    count: int
    problems: list[str]  # rules-text lines or costs the engine doesn't understand


def unsupported_lines(card: Card) -> list[str]:
    """What the engine can't do for this card: an empty list means it's fully playable."""
    problems = []
    if not is_land(card) and card.mana_cost and parse_cost(card.mana_cost) is None:
        problems.append(f"mana cost {card.mana_cost}")
    spell = "Instant" in card.type_line or "Sorcery" in card.type_line
    abilities = {a.text for a in triggered_abilities(card) + activated_abilities(card) + static_abilities(card)}
    for line in rules_lines(card):
        if _is_keyword_line(line) or _DECKBUILDING.fullmatch(line):
            continue
        if spell and line_effects(line) is not None:
            continue
        if not spell and (line in abilities or is_mana_ability(line) or is_enters_with_counters(line)):
            continue
        problems.append(line)
    return problems


def _is_keyword_line(line: str) -> bool:
    return all(part in SUPPORTED_KEYWORDS for part in line.lower().split(", "))


def category(line: str) -> str:
    if line.startswith("mana cost"):
        return "mana costs"
    for name, pattern in _CATEGORIES:
        if pattern.search(line):
            return name
    return "other rules text"


def deck_report(deck: Deck) -> list[CardReport]:
    counts: dict[str, int] = defaultdict(int)
    cards: dict[str, Card] = {}
    for card in deck.commanders + deck.main:
        counts[card.name] += 1
        cards[card.name] = card
    return [CardReport(card, counts[name], unsupported_lines(card)) for name, card in cards.items()]


def format_report(reports: list[CardReport]) -> str:
    total = sum(r.count for r in reports)
    playable = sum(r.count for r in reports if not r.problems)
    lines = [f"Fully playable: {playable}/{total} cards"]
    by_category: dict[str, list[str]] = defaultdict(list)
    for report in reports:
        for problem in report.problems:
            if report.card.name not in by_category[category(problem)]:
                by_category[category(problem)].append(report.card.name)
    if by_category:
        lines.append("\nMissing, by kind (most cards first):")
        for name, card_names in sorted(by_category.items(), key=lambda kv: -len(kv[1])):
            lines.append(f"  {name} ({len(card_names)}): {', '.join(sorted(card_names))}")
        lines.append("\nDetails:")
        for report in sorted(reports, key=lambda r: r.card.name):
            for problem in report.problems:
                lines.append(f"  {report.card.name}: {problem}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    from .cards import CachedSource, ScryfallSource, load_deck

    if len(argv) != 2:
        print("usage: python -m infernal_machine.report DECKLIST", file=sys.stderr)
        return 2
    with open(argv[1]) as f:
        deck = load_deck(f.read(), CachedSource(ScryfallSource(), ".cache/cards.json"))
    print(format_report(deck_report(deck)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
