"""The game formats the engine can play and the deck rules of each (Comprehensive Rules 100.2, 903)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .cards import Deck
from .commander import copy_limit, deck_problems as commander_problems


@dataclass(frozen=True)
class Format:
    name: str
    life: int  # starting life (CR 103.4)
    min_deck: int  # cards in the main deck; Commander counts its commanders
    sideboard: int  # largest sideboard
    copy_limit: int  # copies of one card (basic lands and "any number" cards aside)
    commander: bool  # whether decks have commanders, a command zone and commander damage


COMMANDER = Format("commander", life=40, min_deck=100, sideboard=0, copy_limit=1, commander=True)
STANDARD = Format("standard", life=20, min_deck=60, sideboard=15, copy_limit=4, commander=False)
FORMATS = {fmt.name: fmt for fmt in (COMMANDER, STANDARD)}


def format_of(decks: list[Deck]) -> Format:
    """The format a table of decks is playing: Commander if they all have commanders, Standard if none does."""
    kinds = {bool(deck.commanders) for deck in decks}
    if len(kinds) > 1:
        raise ValueError("A table can't mix decks with commanders and decks without")
    return COMMANDER if kinds == {True} else STANDARD


def deck_problems(deck: Deck, fmt: Format) -> list[str]:
    """Every rule of `fmt` the deck breaks; an empty list means it is legal."""
    if fmt.commander:
        return commander_problems(deck)
    problems: list[str] = []
    if deck.commanders:
        problems.append(f"{fmt.name.capitalize()} decks have no commander")
    if len(deck.main) < fmt.min_deck:
        problems.append(f"Main deck has {len(deck.main)} cards; needs at least {fmt.min_deck}")
    if len(deck.sideboard) > fmt.sideboard:
        problems.append(f"Sideboard has {len(deck.sideboard)} cards; the limit is {fmt.sideboard}")
    counts = Counter(card.name for card in deck.main + deck.sideboard)  # the limit counts the sideboard too
    for card in {c.name: c for c in deck.main + deck.sideboard}.values():
        limit = copy_limit(card, fmt.copy_limit)
        if limit is not None and counts[card.name] > limit:
            problems.append(f"{card.name}: {counts[card.name]} copies, limit is {limit}")
        if not card.standard_legal:
            problems.append(f"{card.name} is not legal in {fmt.name.capitalize()}")
    return problems
