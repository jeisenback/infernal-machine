"""Oathbreaker deck rules.

An Oathbreaker deck is 60 cards: a planeswalker (the Oathbreaker), a signature spell (an instant or sorcery) and 58 others. Both start in the
command zone, cost two more for each earlier cast from it, and may go back to it instead of the graveyard, exile, hand or library, as a
commander does. The signature spell can be cast only while its owner controls their Oathbreaker. Singleton; every card in the Oathbreaker's
color identity, and the signature spell too; there is no commander damage. In `Deck` the Oathbreaker is `commanders[0]` and the signature
spell is `signature_spell`; the game rules are in `game.py`, the deck rules here.
"""

from __future__ import annotations

from collections import Counter

from .cards import Deck
from .commander import copy_limit


def deck_problems(deck: Deck, size: int = 60, legality: str = "oathbreaker", label: str = "Oathbreaker", allow: frozenset[str] = frozenset()) -> list[str]:
    """Every Oathbreaker rule the deck breaks; an empty list means it is legal."""
    problems: list[str] = []
    signature = deck.signature_spell
    cards = deck.commanders + ([signature] if signature else []) + deck.main
    if len(cards) != size:
        problems.append(f"Deck has {len(cards)} cards including the Oathbreaker and the signature spell; needs exactly {size}")
    if len(deck.commanders) != 1:
        problems.append(f"Deck has {len(deck.commanders)} Oathbreakers; needs exactly 1")
    elif "Planeswalker" not in deck.commanders[0].type_line:
        problems.append(f"{deck.commanders[0].name} can't be your Oathbreaker (it is not a planeswalker)")
    if signature is None:
        problems.append("Deck has no signature spell")
    elif not any(kind in signature.type_line for kind in ("Instant", "Sorcery")):
        problems.append(f"{signature.name} can't be your signature spell (it is not an instant or sorcery)")
    identity = {color for c in deck.commanders for color in c.color_identity}
    counts = Counter(card.name for card in cards)
    for card in {c.name: c for c in cards}.values():
        limit = copy_limit(card)
        if limit is not None and counts[card.name] > limit:
            problems.append(f"{card.name}: {counts[card.name]} copies, limit is {limit}")
        if outside := set(card.color_identity) - identity:
            problems.append(f"{card.name} is outside the Oathbreaker's color identity ({''.join(sorted(outside))})")
        if not card.legal_in(legality) and card.name not in allow:  # `allow`: house rules (#528)
            problems.append(f"{card.name} is not legal in {label}")
    return problems
