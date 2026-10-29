"""The game formats the engine can play and the deck rules of each (Comprehensive Rules 100.2, 903).

Commander, Brawl, Duel Commander and Oathbreaker are the commander formats (a command zone, the tax; commander damage in all but Oathbreaker); Standard,
Pioneer, Modern, Legacy, Vintage and Pauper are the 60-card constructed ones, the same rules with a different pool of legal cards (and
Vintage's restricted list: one copy of those). A deck says which it is played in with `Deck.format` (`with_format`, or `--format` on the
tools); a deck that does not is Commander if it has a commander and Standard if it does not. Brawl, Duel Commander and Oathbreaker cannot be told from Commander by
their shape alone (Brawl and Oathbreaker are 60 cards, Duel Commander has Commander's 100), so they are always asked for by name.
"""

from __future__ import annotations

import dataclasses
from collections import Counter
from dataclasses import dataclass

from .cards import Card, Deck
from .commander import copy_limit, deck_problems as commander_problems
from .companion import companion_problems
from .oathbreaker import deck_problems as oathbreaker_problems


@dataclass(frozen=True)
class Format:
    name: str
    life: int  # starting life (CR 103.4)
    min_deck: int  # cards in the main deck; Commander counts its commanders
    sideboard: int  # largest sideboard
    copy_limit: int  # copies of one card (basic lands and "any number" cards aside)
    commander: bool  # whether decks have commanders, a command zone and commander damage
    commander_damage: int | None = 21  # damage from one commander that loses the game (CR 903.10a); None: there is no commander damage
    legality: str = ""  # which legality a card needs: Scryfall's name for the format ("commander", "standard", "duel", ...; `Card.legal_in`)
    multiplayer_life: int | None = None  # starting life with more than two players, if it differs from `life`
    title: str = ""  # how it is written

    def starting_life(self, players: int) -> int:
        return self.multiplayer_life if self.multiplayer_life is not None and players > 2 else self.life

    @property
    def label(self) -> str:
        return self.title or self.name.capitalize()


COMMANDER = Format("commander", life=40, min_deck=100, sideboard=0, copy_limit=1, commander=True, legality="commander")
STANDARD = Format("standard", life=20, min_deck=60, sideboard=15, copy_limit=4, commander=False, legality="standard")
BRAWL = Format("brawl", life=25, min_deck=60, sideboard=0, copy_limit=1, commander=True, legality="standard", multiplayer_life=30)  # 25 in a duel, 30 with more players
DUEL_COMMANDER = Format("duel", life=20, min_deck=100, sideboard=0, copy_limit=1, commander=True, commander_damage=15, legality="duel", title="Duel Commander")
OATHBREAKER = Format("oathbreaker", life=20, min_deck=60, sideboard=0, copy_limit=1, commander=True, commander_damage=None, legality="oathbreaker")
PIONEER, MODERN, LEGACY, VINTAGE, PAUPER = (  # Standard's rules (CR 100.2a), each with its own pool of legal cards
    dataclasses.replace(STANDARD, name=name, legality=name) for name in ("pioneer", "modern", "legacy", "vintage", "pauper"))
FORMATS = {fmt.name: fmt for fmt in (COMMANDER, STANDARD, BRAWL, DUEL_COMMANDER, OATHBREAKER, PIONEER, MODERN, LEGACY, VINTAGE, PAUPER)}


def with_format(deck: Deck, name: str | None) -> Deck:
    """`deck` played in the named format (the deck itself when no name is given)."""
    if not name:
        return deck
    if name not in FORMATS:
        raise ValueError(f"Unknown format {name!r} (known: {', '.join(FORMATS)})")
    return dataclasses.replace(deck, format=name)


@dataclass(frozen=True)
class HouseRules:
    """Cards a run plays although its format does not allow them (#528): those named, and with `banned` every card the format bans
    (not a card outside its pool, such as a silver-border card). The format's other rules still hold for them: copies, deck size,
    singleton, color identity."""
    names: frozenset[str] = frozenset()
    banned: bool = False

    def permits(self, card: Card, fmt: Format) -> bool:
        return card.name in self.names or (self.banned and fmt.legality in card.banned)

    def used(self, decks: list[Deck], fmt: Format) -> list[str]:
        """The cards of `decks` that are not legal in `fmt` and that these rules let in."""
        return sorted({card.name for deck in decks for card in _every_card(deck)
                       if not card.legal_in(fmt.legality) and self.permits(card, fmt)})

    def note(self, decks: list[Deck], fmt: Format) -> str:
        """What a report or a game says when it played such cards: its numbers are not those of a legal deck."""
        used = self.used(decks, fmt)
        return f"Includes cards not legal in {fmt.label}, played under house rules: {', '.join(used)}." if used else ""


NO_HOUSE_RULES = HouseRules()


def _every_card(deck: Deck) -> list[Card]:
    return [*deck.commanders, *deck.main, *deck.sideboard, *[c for c in (deck.companion, deck.signature_spell) if c is not None]]


def add_house_rules_arguments(parser) -> None:
    parser.add_argument("--allow", action="append", default=[], metavar="NAME",
                        help="house rules: play this card although the format does not allow it (repeat, or a comma list)")
    parser.add_argument("--allow-banned", action="store_true", help="house rules: play any card the format bans (not one outside its pool)")


def house_rules(args) -> HouseRules:
    """The house rules the command line asked for (`add_house_rules_arguments`)."""
    names = frozenset(name.strip() for given in args.allow for name in given.split(",") if name.strip())
    return HouseRules(names, args.allow_banned)


def add_format_argument(parser) -> None:
    """`--format`, and the house rules that go with it on every tool that takes it (#528)."""
    parser.add_argument("--format", choices=sorted(FORMATS), help="the format the decks are played in (default: Commander for decks with a commander, "
                                                                   "Standard for the rest; Brawl and Duel Commander must be asked for)")
    add_house_rules_arguments(parser)


def format_of(decks: list[Deck]) -> Format:
    """The format a table of decks is playing: the one the decks name, else Commander if they all have commanders and Standard if none does."""
    named = {deck.format for deck in decks if deck.format}
    if len(named) > 1:
        raise ValueError(f"A table can't mix formats ({', '.join(sorted(named))})")
    if named:
        fmt = FORMATS.get(next(iter(named)))
        if fmt is None:
            raise ValueError(f"Unknown format {next(iter(named))!r} (known: {', '.join(FORMATS)})")
        for deck in decks:
            if bool(deck.commanders) != fmt.commander:
                raise ValueError(f"{fmt.label} decks {'have a commander' if fmt.commander else 'have no commander'}")
        return fmt
    kinds = {bool(deck.commanders) for deck in decks}
    if len(kinds) > 1:
        raise ValueError("A table can't mix decks with commanders and decks without")
    return COMMANDER if kinds == {True} else STANDARD


def deck_problems(deck: Deck, fmt: Format, house: HouseRules = NO_HOUSE_RULES) -> list[str]:
    """Every rule of `fmt` the deck breaks; an empty list means it is legal. A card `house` lets in is not reported for its legality,
    and still counts for every other rule."""
    allow = frozenset(card.name for card in _every_card(deck) if house.permits(card, fmt))
    if fmt.name == "oathbreaker":
        return oathbreaker_problems(deck, fmt.min_deck, fmt.legality, fmt.label, allow)
    if fmt.commander:  # (a companion is outside the 100 cards)
        return (commander_problems(deck, fmt.min_deck, fmt.legality, fmt.label, planeswalkers=fmt.name == "brawl", allow=allow)
                + companion_problems(deck, fmt.min_deck, True, fmt.legality, fmt.label, allow))
    problems: list[str] = []
    if deck.commanders:
        problems.append(f"{fmt.label} decks have no commander")
    if len(deck.main) < fmt.min_deck:
        problems.append(f"Main deck has {len(deck.main)} cards; needs at least {fmt.min_deck}")
    kept = deck.sideboard + ([deck.companion] if deck.companion else [])  # the companion is one of the sideboard's fifteen
    if len(kept) > fmt.sideboard:
        problems.append(f"Sideboard has {len(kept)} cards{' (with the companion)' if deck.companion else ''}; the limit is {fmt.sideboard}")
    problems += companion_problems(deck, fmt.min_deck, False, fmt.legality, fmt.label, allow)
    counts = Counter(card.name for card in deck.main + kept)  # the limit counts the sideboard too
    for card in {c.name: c for c in deck.main + kept}.values():
        limit = 1 if fmt.legality in card.restricted else copy_limit(card, fmt.copy_limit)  # Vintage's restricted list: one copy
        if limit is not None and counts[card.name] > limit:
            problems.append(f"{card.name}: {counts[card.name]} copies, limit is {limit}{' (restricted)' if fmt.legality in card.restricted else ''}")
        if not card.legal_in(fmt.legality) and card.name not in allow:
            problems.append(f"{card.name} is not legal in {fmt.label}")
    return problems
