"""Which cards, permanents or players an effect names: target and mass-effect kinds read out of rules text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


from .common import _LAND_TYPE


def target_kind(effect: Any) -> str | None:
    """What an effect targets ("any", "creature", "spell", ...), or None."""
    return getattr(effect, "target", None)


# What an effect acts on, as its `binds` (issue #436): one value, or None for an effect that names its own targets (or none). It was six
# flags (uses_source, uses_subject, uses_player, uses_dead_*, follows_target) read by the resolver and by the trigger checks separately.
SOURCE = "source"  # the permanent whose ability this is ("put a +1/+1 counter on it")
SUBJECT = "subject"  # the permanent that set off a watching trigger ("... put a counter on it"), if it is still there
DEAD_SUBJECT = "dead_subject"  # ... even if it has left the battlefield ("When enchanted creature dies, return it ...")
SOURCE_AND_SUBJECT = "source_and_subject"  # both, as a pair (source, subject): "create a token that's a copy of it"
DEAD_SOURCE = "dead_source"  # the source after it left the battlefield (persist, undying)
PLAYER = "player"  # the player who set off a watching trigger ("... that player loses 2 life")
PREVIOUS_TARGET = "previous_target"  # the previous effect's target ("Its controller gains life ...")
BINDINGS = (SOURCE, SUBJECT, DEAD_SUBJECT, SOURCE_AND_SUBJECT, DEAD_SOURCE, PLAYER, PREVIOUS_TARGET)

# Which bindings need something of the ability's context that a plain trigger body does not have, for the checks in triggers.py.
CONTEXT_BINDINGS = frozenset({SOURCE, SUBJECT, PLAYER, PREVIOUS_TARGET})


def binding(effect: Any) -> str | None:
    """What an effect acts on besides its own targets: one of BINDINGS, or None."""
    return getattr(effect, "binds", None)


@dataclass(frozen=True)
class MassFilter:
    """Which of the permanents of an "all"/"each" effect are affected: "with flying", "without flying",
    "with power 4 or greater", "nonblack"."""
    keyword: str | None = None
    keyword_wanted: bool = True  # False: "without flying"
    stat: str | None = None  # "power" or "toughness"
    at_least: int | None = None  # "with power 4 or greater"
    at_most: "int | str | None" = None  # "with toughness 2 or less"; "X" is the X of the spell or ability
    color: str | None = None  # a color letter
    other_color: bool = False  # "nonblack": every one that isn't that color
    token: bool | None = None  # True: "creature tokens"; False: "nontoken creatures"
    legendary: bool | None = None  # "legendary creatures" / "nonlegendary"
    basic: bool | None = None  # "nonbasic lands"
    tapped: bool | None = None  # "tapped creatures" / "untapped"
    attacking: bool | None = None  # "attacking creatures" (Aetherize)
    has_type: str | None = None  # "artifact creatures": a card type it must have
    exclude: "MassFilter | None" = None  # "... except for artifact creatures": what is spared
    colors_are: str | None = None  # "that are one or more colors" / "colorless" / "multicolored" / "monocolored"
    enchanted: bool | None = None  # False: "that aren't enchanted" (Winds of Rath)


_LAND_TYPES = rf"({_LAND_TYPE}(?:, {_LAND_TYPE})*(?:,? or {_LAND_TYPE})?)"


_LAND_TYPES_PLURAL = rf"({_LAND_TYPE}(?:, {_LAND_TYPE})*(?:,? or {_LAND_TYPE})?) cards"


def _land_types(text: str) -> tuple[str, ...]:
    return tuple(t.capitalize() for t in re.findall(_LAND_TYPE, text, re.I))


_MANA_VALUE = r"(?: with mana value \d+(?: or less| or greater)?| with power \d+ or less)?"


_SUBTYPE_WORD = r"(?-i:[A-Z][a-z]+)"  # a creature type or other subtype, capitalized: "an Elf card", "a Dragon card"


_SUBTYPE_CARDS = "aura or equipment|aura|equipment|vehicle|saga|" + _SUBTYPE_WORD


_CARD_TYPE = (r"((?:(?:legendary creature|legendary|nonbasic land|noncreature, nonland|nonland permanent|artifact or creature|creature or planeswalker|creature|artifact|enchantment|land|permanent"
              rf"|instant or sorcery|instant|sorcery|{_SUBTYPE_CARDS}) )?card{_MANA_VALUE})")


_SEARCH_KIND = (r"(?:legendary creature|legendary|nonbasic land|creature|land|artifact|enchantment|planeswalker"
                rf"|instant or sorcery|instant|sorcery|artifact or enchantment|basic land|{_SUBTYPE_CARDS}|(?-i:[A-Z][a-z]+)(?: creature)?)")
_SEARCH_TYPE = rf"((?:{_SEARCH_KIND} )?card{_MANA_VALUE})"
_SEARCH_TYPES = rf"((?:{_SEARCH_KIND} )?cards{_MANA_VALUE})"  # the plural, for a search that finds several ("up to five Dragon cards")


_CARDS_PLURAL = (r"((?:(?:legendary creature|legendary|nonbasic land|creature|artifact|enchantment|land|permanent"
                 rf"|instant or sorcery|instant|sorcery|{_SUBTYPE_CARDS}) )?cards{_MANA_VALUE})")


_CARD_PHRASE = re.compile(r"(?:(.+?) )?card(?: with (?:mana value (\d+)(?: (or less|or greater))?|power (\d+) or less))?")


def _card_kind(phrase: str | None) -> str:
    """"creature card with mana value 3 or less" -> "creature|mv<=3"; "card" -> "card". The kind is what the
    game matches library and graveyard cards against."""
    m = _CARD_PHRASE.fullmatch(re.sub(r"\bcards\b", "card", (phrase or "card").lower(), count=1))
    assert m is not None
    kind = m[1] or "card"
    if m[2]:
        kind += "|mv" + {"or less": "<=", "or greater": ">="}.get(m[3], "=") + m[2]
    elif m[4]:
        kind += "|p<=" + m[4]  # Imperial Recruiter: a creature card with power 2 or less
    return kind


def _graveyard_kind(phrase: str | None, whose: str) -> str:
    return f"graveyard:{_card_kind(phrase)}:{whose}"
