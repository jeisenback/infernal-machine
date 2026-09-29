"""Commander format deck rules (Comprehensive Rules 903)."""

from __future__ import annotations

import re
from collections import Counter

from .cards import Card, Deck

DECK_SIZE = 100

_NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_COPY_LIMIT = re.compile(r"A deck can have (any number of|up to (\w+)) cards named")
_REMINDER = re.compile(r"\s*\([^)]*\)")


def _rules_lines(card: Card) -> list[str]:
    return [_REMINDER.sub("", line).strip() for line in card.oracle_text.splitlines()]


def _partner_keyword(card: Card) -> str | None:
    for line in _rules_lines(card):
        if line.startswith("Partner") or line == "Friends forever":
            return line
    return None


def can_be_commander(card: Card) -> bool:
    legendary_creature = "Legendary" in card.type_line and "Creature" in card.type_line
    return legendary_creature or "can be your commander" in card.oracle_text


def valid_pair(a: Card, b: Card) -> bool:
    """Whether two cards may share the command zone (partner, background, doctor's companion)."""
    for first, second in ((a, b), (b, a)):
        if "Choose a Background" in _rules_lines(first) and "Background" in second.type_line:
            return True
        if "Doctor's companion" in _rules_lines(first) and "Time Lord Doctor" in second.type_line:
            return True
    ka, kb = _partner_keyword(a), _partner_keyword(b)
    if ka is None or kb is None:
        return False
    if ka.startswith("Partner with ") or kb.startswith("Partner with "):
        return ka == f"Partner with {b.name}" and kb == f"Partner with {a.name}"
    # Plain "Partner", "Friends forever" and "Partner—<group>" pair only with the same keyword.
    return ka == kb


def copy_limit(card: Card) -> int | None:
    """How many copies a Commander deck may run; None means unlimited."""
    if "Basic" in card.type_line:
        return None
    match = _COPY_LIMIT.search(card.oracle_text)
    if not match:
        return 1
    if match.group(2) is None:
        return None
    return _NUMBERS.get(match.group(2), 1)


def deck_problems(deck: Deck) -> list[str]:
    """Return every Commander rule the deck breaks; an empty list means it's legal."""
    problems: list[str] = []
    commanders = deck.commanders
    cards = commanders + deck.main

    if len(cards) != DECK_SIZE:
        problems.append(f"Deck has {len(cards)} cards including commanders; needs exactly {DECK_SIZE}")

    if len(commanders) == 1:
        if not can_be_commander(commanders[0]):
            problems.append(f"{commanders[0].name} can't be your commander")
    elif len(commanders) == 2:
        a, b = commanders
        if not valid_pair(a, b):
            problems.append(f"{a.name} and {b.name} can't be commanders together")
        else:
            problems += [f"{c.name} can't be your commander" for c in commanders if not _pair_member_ok(c)]
    else:
        problems.append(f"Deck has {len(commanders)} commanders; needs 1, or 2 that can pair")

    counts = Counter(card.name for card in cards)
    identity = {color for c in commanders for color in c.color_identity}
    for card in {c.name: c for c in cards}.values():
        limit = copy_limit(card)
        if limit is not None and counts[card.name] > limit:
            problems.append(f"{card.name}: {counts[card.name]} copies, limit is {limit}")
        outside = set(card.color_identity) - identity
        if outside:
            problems.append(f"{card.name} is outside the commander's color identity ({''.join(sorted(outside))})")
        if not card.commander_legal:
            problems.append(f"{card.name} is not legal in Commander")
    return problems


def _pair_member_ok(card: Card) -> bool:
    # A Background is only a commander alongside a "Choose a Background" creature,
    # which valid_pair has already confirmed.
    return can_be_commander(card) or "Background" in card.type_line
