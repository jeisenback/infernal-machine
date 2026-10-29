"""Companions (Comprehensive Rules 702.139): a card kept outside the game that can be put into the hand for {3}.

A deck names its companion in a `Companion` section (`Deck.companion`). The card says what the deck must be like ("Companion — Each
permanent card in your starting deck has mana value 2 or less."); `companion_problems` checks the ten companions the card file knows by
their wording, and reports any other condition as one it cannot check rather than passing it. The starting deck is the commanders and the
main deck. In the game (`game.py`) the companion is put into the hand once, for {3}, at any time its owner could cast a sorcery.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable

from .analysis import is_land
from .cards import Card

COST = "{3}"  # to put the companion into the hand
_REMINDER = re.compile(r"\s*\([^)]*\)")
_SYMBOL = re.compile(r"\{[^}]+\}")
KAHEERA_TYPES = {"Cat", "Elemental", "Nightmare", "Dinosaur", "Beast"}


def companion_condition(card: Card) -> str | None:
    """The deckbuilding condition on a card's companion line, or None if it has no companion ability."""
    for line in card.oracle_text.splitlines():
        head, dash, rest = _REMINDER.sub("", line).strip().partition("—")
        if head.strip() == "Companion" and dash:
            return rest.strip()
    return None


def _types(card: Card) -> set[str]:
    return set(card.type_line.partition("—")[0].split())


def _subtypes(card: Card) -> set[str]:
    return set(card.type_line.partition("—")[2].split())


def _permanent(card: Card) -> bool:
    return not (_types(card) & {"Instant", "Sorcery"})


def _has_activated_ability(card: Card) -> bool:
    """A land (it taps for mana) or a card with a line of the form "cost: effect" outside quotation marks."""
    if is_land(card):
        return True
    for line in card.oracle_text.splitlines():
        text = re.sub(r'"[^"]*"', "", _REMINDER.sub("", line))
        if re.match(r"^[^:]{1,100}: ", text.strip()):
            return True
    return False


def _names(cards: list[Card], what: Callable[[Card], bool], limit: int = 4) -> list[str]:
    found = [c.name for c in cards if what(c)]
    return sorted(set(found))[:limit] + (["..."] if len(set(found)) > limit else [])


# Each: (the condition's wording, a check returning the cards that break it, and the text for the problem)
def _even(cards, minimum): return _names(cards, lambda c: int(c.cmc) % 2 == 1)
def _odd(cards, minimum): return _names(cards, lambda c: not is_land(c) and int(c.cmc) % 2 == 0)
def _jegantha(cards, minimum): return _names(cards, lambda c: any(n > 1 for n in Counter(_SYMBOL.findall(c.mana_cost)).values()))
def _kaheera(cards, minimum): return _names(cards, lambda c: "Creature" in _types(c) and not (_subtypes(c) & KAHEERA_TYPES))
def _keruga(cards, minimum): return _names(cards, lambda c: not is_land(c) and int(c.cmc) < 3)
def _lurrus(cards, minimum): return _names(cards, lambda c: _permanent(c) and int(c.cmc) > 2)
def _zirda(cards, minimum): return _names(cards, lambda c: _permanent(c) and not _has_activated_ability(c))


def _lutri(cards, minimum):
    counts = Counter(c.name for c in cards if not is_land(c))
    return sorted(name for name, n in counts.items() if n > 1)[:4]


def _umori(cards, minimum):
    nonland = [c for c in cards if not is_land(c)]
    if not nonland or set.intersection(*(_types(c) for c in nonland)):
        return []
    return ["no card type is shared by every nonland card"]


def _yorion(cards, minimum):
    return [] if len(cards) >= minimum + 20 else [f"{len(cards)} cards, needs {minimum + 20}"]


CONDITIONS: dict[str, Callable] = {
    "Your starting deck contains only cards with even mana values.": _even,
    "No card in your starting deck has more than one of the same mana symbol in its mana cost.": _jegantha,
    "Each creature card in your starting deck is a Cat, Elemental, Nightmare, Dinosaur, or Beast card.": _kaheera,
    "Your starting deck contains only cards with mana value 3 or greater and land cards.": _keruga,
    "Each permanent card in your starting deck has mana value 2 or less.": _lurrus,
    "Each nonland card in your starting deck has a different name.": _lutri,
    "Your starting deck contains only cards with odd mana values and land cards.": _odd,
    "Each nonland card in your starting deck shares a card type.": _umori,
    "Your starting deck contains at least twenty cards more than the minimum deck size.": _yorion,
    "Each permanent card in your starting deck has an activated ability.": _zirda,
}


def companion_problems(deck, minimum: int, commander_format: bool, legality: str, label: str) -> list[str]:
    """What is wrong with a deck's companion, if it has one: the card has no companion ability, the starting deck breaks its condition
    (or the condition is one this does not check), or, in a commander format, it is outside the commanders' color identity, in the deck
    already, or not legal in the format (`legality` is the `Format.legality` a card needs, `Card.legal_in`). `minimum` is the format's minimum deck size."""
    card = deck.companion
    if card is None:
        return []
    condition = companion_condition(card)
    if condition is None:
        return [f"{card.name} doesn't have the companion ability"]
    problems = []
    check = CONDITIONS.get(condition)
    if check is None:
        problems.append(f"{card.name}: this tool does not check its companion condition ({condition})")
    elif offenders := check(deck.commanders + deck.main, minimum):
        problems.append(f"The deck doesn't meet {card.name}'s companion condition ({condition[:-1]}): {', '.join(offenders)}")
    if commander_format:
        identity = {color for c in deck.commanders for color in c.color_identity}
        if outside := set(card.color_identity) - identity:
            problems.append(f"{card.name} is outside the commander's color identity ({''.join(sorted(outside))})")
        if any(c.name == card.name for c in deck.commanders + deck.main):
            problems.append(f"{card.name} is the companion and also in the deck (singleton)")
        if not card.legal_in(legality):
            problems.append(f"{card.name} is not legal in {label}")
    return problems
