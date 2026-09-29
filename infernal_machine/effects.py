"""Card effects: reading rules text into things the game does.

Rules text is matched sentence by sentence against known templates. A spell
gets effects only if every sentence is understood; otherwise it resolves with
no effect and the game reports it as unsupported, instead of doing part of
what the card says. Triggered abilities on permanents ("When this creature
enters, draw a card.") use the same templates for what they do.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable

from .cards import Card

if TYPE_CHECKING:
    from .game import Game, Seat

_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_N = r"(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
_REMINDER = re.compile(r"\s*\([^)]*\)")
_SELF = r"(?:CARDNAME|it|this (?:spell|creature|artifact|enchantment|land|planeswalker|permanent))"


def _count(word: str) -> int:
    return int(word) if word.isdigit() else _NUMBERS[word.lower()]


def _rules_text(card: Card) -> str:
    """Oracle text without reminder text, with the card's own name as CARDNAME.

    Legendary cards often call themselves by their short name ("Omnath" for
    "Omnath, Locus of Rage"), and double-faced cards by their front face's name.
    """
    text = _REMINDER.sub("", card.oracle_text)
    front = card.name.split(" // ")[0]
    for name in dict.fromkeys((card.name, front, front.split(",")[0])):
        text = text.replace(name, "CARDNAME")
    return text


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for line in text.splitlines() for s in re.split(r"(?<=\.)\s+", line) if s.strip()]


def target_kind(effect: Any) -> str | None:
    """What an effect targets ("any", "creature", "spell", ...), or None."""
    return getattr(effect, "target", None)


@dataclass(frozen=True)
class Draw:
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.draw(controller, self.count)


@dataclass(frozen=True)
class GainLife:
    amount: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.change_life(controller, self.amount)


@dataclass(frozen=True)
class OpponentsLoseLife:
    amount: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            game.change_life(seat, -self.amount)


@dataclass(frozen=True)
class Damage:
    amount: int
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.damage(target, self.amount)


@dataclass(frozen=True)
class Destroy:
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.destroy(target)


@dataclass(frozen=True)
class Counter:
    target: str = "spell"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.counter(target)


@dataclass(frozen=True)
class FetchBasicLand:
    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fetch_basic_land(controller)


_PERMANENT_KIND = r"(creature|artifact|enchantment|planeswalker|nonland permanent|permanent|artifact or enchantment|creature or planeswalker)"
_DAMAGE_KIND = r"(any target|target creature|target player|target creature or planeswalker|target player or planeswalker)"

_TEMPLATES: list[tuple[re.Pattern, Callable[[re.Match], Any]]] = [
    (re.compile(rf"draw {_N} cards?\.", re.I), lambda m: Draw(_count(m[1]))),
    (re.compile(rf"you gain {_N} life\.", re.I), lambda m: GainLife(_count(m[1]))),
    (re.compile(rf"each opponent loses {_N} life\.", re.I), lambda m: OpponentsLoseLife(_count(m[1]))),
    (re.compile(rf"{_SELF} deals {_N} damage to {_DAMAGE_KIND}\.", re.I),
     lambda m: Damage(_count(m[1]), "any" if m[2].lower() == "any target" else m[2].lower().removeprefix("target "))),
    (re.compile(rf"destroy target {_PERMANENT_KIND}\.", re.I), lambda m: Destroy(m[1].lower())),
    (re.compile(r"counter target spell\.", re.I), lambda m: Counter()),
    (re.compile(r"search your library for a basic land card, put it onto the battlefield tapped, then shuffle\.", re.I),
     lambda m: FetchBasicLand()),
]


def _parse(sentences: list[str]) -> list | None:
    effects = []
    for sentence in sentences:
        for pattern, build in _TEMPLATES:
            match = pattern.fullmatch(sentence)
            if match:
                effects.append(build(match))
                break
        else:
            return None
    return effects


def spell_effects(card: Card) -> list | None:
    """Effects of an instant or sorcery, in order; None if any sentence isn't understood."""
    return _parse(_split_sentences(_rules_text(card)))


@dataclass(frozen=True)
class TriggeredAbility:
    event: str  # one of TRIGGER_EVENTS
    effects: tuple
    optional: bool  # "you may ...": the controller chooses when it resolves
    text: str


_TRIGGERS = {
    "enters": re.compile(rf"When(?:ever)? {_SELF} enters(?: the battlefield)?, (.+)", re.I),
    "dies": re.compile(rf"When(?:ever)? {_SELF} dies, (.+)", re.I),
    "attacks": re.compile(rf"Whenever {_SELF} attacks, (.+)", re.I),
    "combat_damage_to_player": re.compile(rf"Whenever {_SELF} deals combat damage to a player, (.+)", re.I),
    "upkeep": re.compile(r"At the beginning of your upkeep, (.+)", re.I),
    "end_step": re.compile(r"At the beginning of your end step, (.+)", re.I),
}
TRIGGER_EVENTS = tuple(_TRIGGERS)


@lru_cache(maxsize=None)
def triggered_abilities(card: Card) -> tuple[TriggeredAbility, ...]:
    """The triggered abilities on a permanent whose effects are all understood."""
    abilities = []
    for line in _rules_text(card).splitlines():
        line = line.strip()
        for event, pattern in _TRIGGERS.items():
            match = pattern.fullmatch(line)
            if not match:
                continue
            rest = match[1]
            optional = rest.lower().startswith("you may ")
            if optional:
                rest = rest[len("you may "):]
            effects = _parse(_split_sentences(rest[:1].upper() + rest[1:]))
            if effects is not None:
                abilities.append(TriggeredAbility(event, tuple(effects), optional, line))
            break
    return tuple(abilities)


_ADD_SYMBOLS = re.compile(r"\{T\}: Add ((?:\{[WUBRGC]\})+)\.")
_ADD_EITHER = re.compile(r"\{T\}: Add \{([WUBRGC])\} or \{([WUBRGC])\}\.")
_ADD_ANY = re.compile(r"\{T\}: Add one mana of any color\.")
_ADD_IDENTITY = re.compile(r"\{T\}: Add one mana of any color in your commander's color identity\.")


def mana_ability(card: Card, commander_identity: frozenset[str]) -> list[frozenset[str]] | None:
    """The mana a nonland permanent makes when tapped, one set of options per mana.

    Covers "{T}: Add {C}{C}." (Sol Ring), "{T}: Add {G}." (mana creatures),
    "{T}: Add {R} or {G}.", and "one mana of any color" (optionally limited
    to your commander's color identity).
    """
    for line in _REMINDER.sub("", card.oracle_text).splitlines():
        line = line.strip()
        if m := _ADD_SYMBOLS.fullmatch(line):
            return [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[1])]
        if m := _ADD_EITHER.fullmatch(line):
            return [frozenset((m[1], m[2]))]
        if _ADD_ANY.fullmatch(line):
            return [frozenset("WUBRG")]
        if _ADD_IDENTITY.fullmatch(line):
            return [commander_identity] if commander_identity else None
    return None
