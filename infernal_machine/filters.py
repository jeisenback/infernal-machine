"""One description of "which cards or permanents": a creature, a nonland permanent an opponent controls, a black creature, an
Elf, a creature card with mana value 3 or less, a noncreature spell, an Aura or Equipment.

Targets, mass effects, searches, graveyard returns, watching triggers and cost reductions all name a kind of card. They used to
read their kind strings with four functions of their own, which disagreed in small ways (one knew "black creature", another did
not). `parse_filter` reads the one grammar and `Filter.matches` applies it to a card, so every place that names a kind means the
same thing by the same words.

A filter is a list of alternatives ("artifact, creature, enchantment, or planeswalker" has four); a card matches if it matches any
one. An alternative says which words the card's type line needs ("creature", "Elf", "legendary"), which it must not have
("nonland", "non-Aura"), which colors, whether it is a token, how many colors it has and its mana value or power. A kind also
says whose it is ("you control", "an opponent controls") and what it is doing ("attacking", "tapped"): those depend on the game, so
the filter only carries them for the caller to check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

COLOR_LETTER = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
PERMANENT_TYPES = frozenset({"artifact", "battle", "creature", "enchantment", "land", "planeswalker"})
_CONTROLLERS = ((" an opponent controls", "opponent"), (" you don't control", "opponent"), (" you control", "you"), (" you own", "own"))
_STATES = ("attacking or blocking", "tapped", "untapped", "attacking")
_NOTHING_TO_CHECK = {"", "card", "spell", "cards", "spells"}


@dataclass(frozen=True)
class Alternative:
    """One way to match. Every condition that is set has to hold."""
    needs: tuple[str, ...] = ()  # type, supertype and subtype words the card must all have (lowercase)
    lacks: tuple[str, ...] = ()  # words it must have none of: "nonland", "nonlegendary", "nonbasic"
    lacks_subtype: tuple[str, ...] = ()  # subtypes it must have none of: "non-Aura", "non-Elf"
    colors: tuple[str, ...] = ()  # it is at least one of these colors
    lacks_colors: tuple[str, ...] = ()  # it is none of these colors: "nonblack"
    token: bool | None = None  # True: a token; False: not a token
    color_count: str = ""  # "mono" (exactly one color) or "multi" (two or more)
    historic: bool = False  # legendary, an artifact or a Saga
    permanent: bool = False  # a permanent type: a card in a library or graveyard has to have one to be a "permanent card"
    colorless: bool = False  # it has no color

    def matches(self, card) -> bool:
        words, subtypes = _words(card.type_line)
        if self.permanent and not (PERMANENT_TYPES & words):
            return False
        if any(word not in words for word in self.needs) or any(word in words for word in self.lacks):
            return False
        if any(word in subtypes for word in self.lacks_subtype):
            return False
        if self.colors and not any(color in card.colors for color in self.colors):
            return False
        if any(color in card.colors for color in self.lacks_colors):
            return False
        if self.token is not None and card.type_line.startswith("Token") != self.token:
            return False
        if self.color_count == "mono" and len(card.colors) != 1:
            return False
        if self.color_count == "multi" and len(card.colors) < 2:
            return False
        if self.colorless and card.colors:
            return False
        return not (self.historic and not ({"legendary", "artifact", "saga"} & words))


@dataclass(frozen=True)
class Filter:
    alternatives: tuple[Alternative, ...] = (Alternative(),)
    controller: str | None = None  # "you", "opponent" or "own": whose, for the caller to check
    state: str = ""  # "tapped", "untapped", "attacking" or "attacking or blocking": for the caller to check
    mana_value: tuple[str, int] | None = None  # ("<=", 3), (">=", 5), ("=", 2) or ("<", 2)
    power_at_most: int | None = None  # "creature card with power 2 or less"
    keyword: str = ""  # "creature spell with flying": a keyword printed on the card (Momo, Friendly Flier)

    def matches(self, card) -> bool:
        """Whether the card is of this kind, as far as the card itself says (not whose it is, or what it is doing)."""
        if self.keyword and not _has_printed_keyword(card, self.keyword):
            return False
        if self.mana_value is not None:
            op, value = self.mana_value
            if not ((op == "<=" and card.cmc <= value) or (op == ">=" and card.cmc >= value) or (op == "=" and card.cmc == value)
                    or (op == "<" and card.cmc < value)):
                return False
        if self.power_at_most is not None:
            power = card.power
            if power is None or not power.lstrip("-").isdigit() or int(power) > self.power_at_most:
                return False
        return any(alternative.matches(card) for alternative in self.alternatives)


@lru_cache(maxsize=4096)
def _words(type_line: str) -> tuple[frozenset[str], frozenset[str]]:
    """(every word of the type line, its subtypes) in lowercase."""
    head, _, tail = type_line.lower().partition("—")
    subtypes = frozenset(tail.split())
    return frozenset(head.split()) | subtypes, subtypes


_KEYWORD = re.compile(r" with (flying|flash|haste|trample|vigilance|lifelink|deathtouch|menace|reach|first strike|double strike|hexproof|"
                      r"indestructible|defender)$")


def _has_printed_keyword(card, keyword: str) -> bool:
    """Whether a keyword is printed on the card: a line of keywords ("Flying, vigilance, lifelink") holds it."""
    return any(keyword in (w.strip().lower() for w in line.split(",")) for line in card.oracle_text.splitlines())


_MANA_VALUE = re.compile(r" with mana value (\d+)(?: (or less|or greater))?$")
_POWER = re.compile(r" with power (\d+) or less$")
_BAR_VALUE = re.compile(r"\|(mv|p)(<=|>=|=|<)(\d+)$")
_SPLIT = re.compile(r",? or |, | and ")


@lru_cache(maxsize=None)
def parse_filter(text: str) -> Filter:
    """The filter a kind of card or permanent names. Words it does not know are creature types or other subtypes."""
    text = text.strip().lower()
    mana_value = None
    power_at_most = None
    if m := _BAR_VALUE.search(text):  # the search kinds: "creature|mv<=3", "creature|p<=2"
        if m[1] == "mv":
            mana_value = (m[2], int(m[3]))
        else:
            power_at_most = int(m[3])
        text = text[:m.start()]
    if m := _MANA_VALUE.search(text):
        mana_value = ({"or less": "<=", "or greater": ">="}.get(m[2], "="), int(m[1]))
        text = text[:m.start()]
    elif m := _POWER.search(text):
        power_at_most = int(m[1])
        text = text[:m.start()]
    keyword = ""
    if m := _KEYWORD.search(text):
        keyword, text = m[1], text[:m.start()]
    controller = None
    for suffix, who in _CONTROLLERS:
        if text.endswith(suffix):
            controller, text = who, text.removesuffix(suffix)
            break
    state = ""
    for word in _STATES:
        if text.startswith(word + " "):
            state, text = word, text.removeprefix(word + " ")
            break
    return Filter(_alternatives(text), controller, state, mana_value, power_at_most, keyword)


def _alternatives(text: str) -> tuple[Alternative, ...]:
    if text == "any":  # a creature or a planeswalker (the "any target" of a Lightning Bolt, without the players)
        return (Alternative(needs=("creature",)), Alternative(needs=("planeswalker",)))
    if text.startswith("any non-"):  # "any target that isn't a Dinosaur": a creature or planeswalker of another type (the players are added by the caller)
        other = text.removeprefix("any non-")
        return (Alternative(needs=("creature",), lacks_subtype=(other,)), Alternative(needs=("planeswalker",), lacks_subtype=(other,)))
    if "|" in text and not text.startswith("|"):  # "R|G": a red or green spell
        return tuple(a for part in text.split("|") for a in _alternatives(part))
    parts = [p for p in _SPLIT.split(text.replace(" spells", "").replace(" spell", "")) if p]
    found: list[Alternative] = []
    carried: list[str] = []  # adjectives with no noun yet: "noncreature, nonland permanent"
    for part in parts:
        words = part.split()
        if all(w.startswith("non") for w in words):
            carried += words
            continue
        found.append(_alternative(carried + words))
        carried = []
    if carried:
        found.append(_alternative(carried))
    return tuple(found) or (Alternative(),)


def _alternative(words: list[str]) -> Alternative:
    needs: list[str] = []
    lacks: list[str] = []
    lacks_subtype: list[str] = []
    colors: list[str] = []
    lacks_colors: list[str] = []
    token = None
    color_count = ""
    historic = False
    permanent = False
    colorless = False
    for word in words:
        if word in _NOTHING_TO_CHECK or word in ("expend", "any"):
            continue
        if word == "permanent":
            permanent = True
        elif word == "token":
            token = True
        elif word == "nontoken":
            token = False
        elif word in COLOR_LETTER:
            colors.append(COLOR_LETTER[word])
        elif word in ("w", "u", "b", "r", "g"):
            colors.append(word.upper())
        elif word == "multicolored":
            color_count = "multi"
        elif word == "colorless":
            colorless = True
        elif word == "monocolored":
            color_count = "mono"
        elif word == "historic":
            historic = True
        elif word.startswith("non-"):
            lacks_subtype.append(word[4:])
        elif word.startswith("non") and word[3:] in COLOR_LETTER:
            lacks_colors.append(COLOR_LETTER[word[3:]])
        elif word.startswith("non"):
            lacks.append(word[3:])
        else:
            needs.append(word)
    return Alternative(tuple(needs), tuple(lacks), tuple(lacks_subtype), tuple(colors), tuple(lacks_colors), token, color_count, historic, permanent,
                       colorless)


def matches(kind: str, card) -> bool:
    """Whether `card` is of the kind the text names."""
    return parse_filter(kind).matches(card)


def has_type(card, kind: str) -> bool:
    """Whether a card has a type or subtype: "creature", "Plains", "Snake", or one of several ("Swamp or Mountain")."""
    return parse_filter(kind).matches(card)
