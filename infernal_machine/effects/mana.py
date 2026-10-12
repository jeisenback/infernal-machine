"""Mana abilities: what a permanent adds, with what restrictions and at what cost."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from ..cards import Card

from .common import _ANY_N, _N_FIXED, _SELF, _THRESHOLD, _number, rules_lines
from .outcomes import Condition, _condition


_TAP = r"\{T\}(, Sacrifice (?:CARDNAME|this (?:artifact|creature|permanent|land)))?(?:, (?:Sacrifice a Food|Mill a card))?: Add "  # group 1: sacrifice


# Each may end with "Activate only if <condition>." (Temple of the False God, Spire of Industry): that is always the
# last group of the match, None when it is absent.
_IF_TAIL = r"(?: Activate only if (.+)\.)?"


_ADD_SYMBOLS = re.compile(_TAP + r"((?:\{[WUBRGC]\})+)\." + _IF_TAIL)


_ADD_EITHER = re.compile(_TAP + r"\{([WUBRGC])\} or \{([WUBRGC])\}\." + _IF_TAIL)


# Arcane Sanctum, the Cragganwick-style tri-lands: three colors, one mana.
_ADD_THREE = re.compile(_TAP + r"\{([WUBRGC])\}, \{([WUBRGC])\}, or \{([WUBRGC])\}\." + _IF_TAIL)


_ADD_ANY = re.compile(_TAP + r"one mana of any color\." + _IF_TAIL)


_ADD_IDENTITY = re.compile(_TAP + r"one mana of any color in your commander's color identity\." + _IF_TAIL)


# Gilded Lotus. The engine keeps one option set per mana, so the three are chosen independently: auto-pay may spend
# them as different colors, which the card does not allow.
_ADD_ANY_N = re.compile(_TAP + r"(two|three|four|five) mana of any one color\." + _IF_TAIL)


# Relic of Sauron: two mana, each one of the listed colors (chosen independently, as with Gilded Lotus).
_ADD_COMBO = re.compile(_TAP + r"(two|three) mana in any combination of (\{[WUBRGC]\}(?:, \{[WUBRGC]\})*,? (?:and/or|or) \{[WUBRGC]\})\." + _IF_TAIL)


# Mox Amber: the colors of the permanents named, which the game works out when the mana is wanted.
_ADD_AMONG = re.compile(_TAP + r"one mana of any color among legendary creatures and planeswalkers you control\." + _IF_TAIL)


# Chrome Mox: the colors of the card exiled with it.
_ADD_IMPRINTED = re.compile(_TAP + r"one mana of any of the exiled card's colors\." + _IF_TAIL)


def mana_among_legendary(card: Card) -> bool:
    """Mox Amber: its mana is any color among the legendary creatures and planeswalkers its controller controls."""
    return any(_ADD_AMONG.fullmatch(line) for line in rules_lines(card))


def mana_of_imprinted(card: Card) -> bool:
    """Chrome Mox: its mana is any color of the card exiled with it."""
    return any(_ADD_IMPRINTED.fullmatch(line) for line in rules_lines(card))


# Study Hall, Path of Ancestry: a mana ability with a rider that triggers when the mana is spent on the right spell.
_SPENT_RIDER = re.compile(r"(.+\.) When (?:you spend this mana|that mana is spent) to cast "
                          r"(your commander|a creature spell that shares a creature type with your commander), "
                          r"scry (1|X, where X is the number of times it's been cast from the command zone this game)\.")


# Opal Palace: the rider puts counters on the commander as it enters instead.
_COUNTERS_RIDER = re.compile(r"(.+\.) If you spend this mana to cast your commander, it enters with a number of additional \+1/\+1 "
                             r"counters on it equal to the number of times it's been cast from the command zone this game\.")


# Urza's Tower, Mine and Power Plant: more mana when you control the other two.
_BONUS_RIDER = re.compile(r"(.+\.) If you control an? (.+?) and an? (.+?), add ((?:\{C\})+) instead\.")


def mana_bonus(card: Card) -> tuple[tuple[str, str], int] | None:
    """(the two permanents to control, how much mana the land makes then) for an Urza land, or None."""
    for line in rules_lines(card):
        if m := _BONUS_RIDER.fullmatch(line):
            return (m[2], m[3]), len(re.findall(r"\{C\}", m[4]))
    return None


@dataclass(frozen=True)
class ManaSpentTrigger:
    """ "When that mana is spent to cast <spell>, scry <n>." on a mana ability."""
    spell: str  # "commander" (your commander) or "shares_type_with_commander" (a creature spell sharing a type)
    scry: int | str  # a number, or "commander_casts": the times that commander has been cast from the command zone
    counters: bool = False  # Opal Palace: no scry; the commander enters with that many +1/+1 counters more


def mana_spent_trigger(card: Card) -> ManaSpentTrigger | None:
    for line in rules_lines(card):
        if _COUNTERS_RIDER.fullmatch(line):
            return ManaSpentTrigger("commander", 0, counters=True)
        if m := _SPENT_RIDER.fullmatch(line):
            return ManaSpentTrigger("commander" if m[2] == "your commander" else "shares_type_with_commander",
                                    1 if m[3] == "1" else "commander_casts")
    return None


# Troyan, Elementalist's Palette: "Spend this mana only ..." limits what the mana can pay for.
_RESTRICTIONS = {"Spend this mana only to cast spells with mana value 5 or greater or spells with {X} in their mana costs":
                 "big_or_x",
                 "Spend this mana only on costs that contain {X}": "x_cost",
                 "Spend this mana only to cast an instant or sorcery spell": "instant_or_sorcery",
                 "This mana can't be spent to cast spells from your hand": "not_from_hand"}  # Heartwood Crafter


_MANA_RESTRICTION = re.compile(" (" + "|".join(re.escape(k) for k in _RESTRICTIONS) + r")\.")


# Brass Infiniscope: a delayed trigger that the mana ability sets up.
_NEXT_X_RIDER = re.compile(r"(.+\.) When you next cast a spell with \{X\} in its mana cost this turn, you draw a card and gain "
                           r"half X life, rounded down\.")


def has_next_x_rider(card: Card) -> bool:
    """Brass Infiniscope: tapping it for mana makes "when you next cast a spell with {X} in its mana cost this turn, you draw a
    card and gain half X life, rounded down"."""
    return any(_NEXT_X_RIDER.fullmatch(line) for line in rules_lines(card))


def _without_spent_rider(line: str) -> str:
    """The mana ability alone, without its "When that mana is spent ..." sentence or its spending restriction."""
    m = _SPENT_RIDER.fullmatch(line) or _NEXT_X_RIDER.fullmatch(line) or _COUNTERS_RIDER.fullmatch(line) or _BONUS_RIDER.fullmatch(line)
    line = _MANA_RESTRICTION.sub("", m[1] if m else line)
    # Eldrazi Spawn: "Sacrifice this token: Add {C}." reads like Treasure's "{T}, Sacrifice this permanent: Add {C}."
    return "{T}, Sacrifice this permanent: " + line.removeprefix("Sacrifice this token: ") if line.startswith("Sacrifice this token: Add ") else line


def mana_restriction(card: Card) -> str | None:
    """What the card's plain mana ability limits its mana to: "big_or_x" (spells of mana value 5 or more, or with {X} in
    their cost), "x_cost" (costs containing {X}) or "not_from_hand" (not spells cast from hand)."""
    line = _mana_line(card)
    m = _MANA_RESTRICTION.search(line) if line else None
    return _RESTRICTIONS[m[1]] if m else None


_EXTRA_COST = re.compile(r"\{T\}, (Sacrifice a Food|Mill a card): Add ")


def mana_extra_cost(card: Card) -> str | None:
    """"food" or "mill" when the card's mana ability costs a Food sacrifice (Gilded Goose) or a milled card (Millikin)."""
    line = _mana_line(card)
    m = _EXTRA_COST.match(line) if line else None
    return None if m is None else ("food" if m[1].startswith("Sacrifice") else "mill")


# Astral Cornucopia, Elementalist's Palette: one mana for each charge counter.
_CHARGE_MANA = re.compile(r"\{T\}: (Choose a color\. Add one mana of that color|Add \{C\}) for each charge counter on "
                          r"(?:CARDNAME|this [a-z]+)\.(?: Spend this mana only on costs that contain \{X\}\.)?")


def charge_mana(card: Card) -> tuple[frozenset[str], str | None] | None:
    """The types of the mana per charge counter this permanent makes when tapped, and its spending restriction."""
    for line in rules_lines(card):
        if m := _CHARGE_MANA.fullmatch(line):
            return (frozenset("WUBRG") if m[1].startswith("Choose") else frozenset("C"),
                    "x_cost" if "Spend" in line else None)
    return None


def mana_ability(card: Card, commander_identity: frozenset[str]) -> list[frozenset[str]] | None:
    """The mana a nonland permanent makes when tapped, one set of options per mana.

    Covers "{T}: Add {C}{C}." (Sol Ring), "{T}: Add {G}." (mana creatures),
    "{T}: Add {R} or {G}.", and "one mana of any color" (optionally limited
    to your commander's color identity), each optionally with "Sacrifice this
    artifact" in the cost (Treasure).
    """
    line = _mana_line(card)
    for rule in rules_lines(card):  # Ancient Tomb-style "{T}: Add {C}{C}. ... deals 2 damage to you."
        if m := _PAIN_MULTI.fullmatch(rule):
            return [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[1])]
    units = _mana_from_line(line, commander_identity) if line else None
    if pain := mana_pain(card):  # a Talisman's colored ability joins its colorless one as a single mana
        units = [units[0] | pain[0]] + units[1:] if units else [pain[0]]
    return units


_COUNTER_MANA = re.compile(r"Remove an? ([a-z]+) counter from (?:CARDNAME|this [a-z]+): Add one mana of any color\. "
                           r"Activate only once each turn\.")


def counter_mana(card: Card) -> str | None:
    """Mana Bloom: the counter its mana ability removes (it makes one mana of any color, once each turn)."""
    return next((m[1] for line in rules_lines(card) if (m := _COUNTER_MANA.fullmatch(line))), None)


_ADD_POWER = re.compile(_TAP + r"X mana of any one color, where X is this creature's power\." + _IF_TAIL)


def makes_mana_by_power(card: Card) -> bool:
    """Kami of Whispered Hopes: "{T}: Add X mana of any one color, where X is this creature's power." """
    return any(_ADD_POWER.fullmatch(line) for line in rules_lines(card))


def mana_ability_sacrifices(card: Card) -> bool:
    """Whether using the card's mana ability sacrifices it (Treasure)."""
    line = _mana_line(card)
    return bool(line and any((m := p.fullmatch(_without_spent_rider(line))) and m[1] for p in _MANA_PATTERNS))


def mana_ability_needs_no_tap(card: Card) -> bool:
    """Eldrazi Spawn: "Sacrifice this token: Add {C}." has no {T} in its cost, so summoning sickness does not stop a creature
    from using it."""
    line = _mana_line(card)
    return bool(line and "{T}" not in line.split(":")[0])


def _mana_match(line: str) -> re.Match | None:
    """The match of a plain "{T}: Add ..." line, unless its "Activate only if" condition isn't understood."""
    line = _without_spent_rider(line)
    worded = _CONDITION_WORD.match(line)
    line = line[worded.end():] if worded else line
    for pattern in _MANA_PATTERNS:
        if (m := pattern.fullmatch(line)) and (m.group(pattern.groups) is None or _condition(m.group(pattern.groups))):
            return m
    return None


_CONDITION_WORD = re.compile(r"(?:Metalcraft|Threshold|Hellbent|Delirium|Revolt|Ferocious) \u2014 ")  # the ability word of the "Activate only if" that follows


def _mana_line(card: Card) -> str | None:
    """The card's plain "{T}: Add ..." line (Signet-style lines are filter_mana_ability's)."""
    return next((line for line in rules_lines(card) if _mana_match(line)), None)


@dataclass(frozen=True)
class RestrictedMana:
    """Cavern of Souls, Unclaimed Territory, Delighted Halfling: a second mana ability for one mana of any color that can only
    be spent on some spells ("creature spell of the chosen type", "legendary spell"), and perhaps makes that spell uncounterable."""
    spell: str  # "chosen_creature" or "legendary"
    uncounterable: bool


_RESTRICTED_MANA = re.compile(r"\{T\}: Add one mana of any color\. Spend this mana only to cast "
                              r"(a creature spell of the chosen type|a legendary spell)(, and that spell can't be countered)?\.")


@lru_cache(maxsize=None)
def restricted_mana(card: Card) -> RestrictedMana | None:
    for line in rules_lines(card):
        if m := _RESTRICTED_MANA.fullmatch(line):
            return RestrictedMana("chosen_creature" if "chosen type" in m[1] else "legendary", bool(m[2]))
    return None


def is_restricted_mana_line(line: str) -> bool:
    return _RESTRICTED_MANA.fullmatch(line) is not None


def mana_condition(card: Card) -> "Condition | None":
    """The "Activate only if ..." condition on the card's plain mana ability, if it has one."""
    line = _mana_line(card)
    m = _mana_match(line) if line else None
    text = m.group(m.re.groups) if m else None
    return _condition(text) if text else None


def mana_life_condition(card: Card) -> "Condition | None":
    """Spire of Industry: "{T}, Pay 1 life: Add one mana of any color. Activate only if you control an artifact." (only that line)."""
    text = next((m.group(m.re.groups) for rule in rules_lines(card) if (m := _PAY_LIFE_ANY.fullmatch(rule))), None)
    return _condition(text) if text else None


_MANA_PATTERNS = (_ADD_SYMBOLS, _ADD_EITHER, _ADD_THREE, _ADD_ANY, _ADD_IDENTITY, _ADD_ANY_N, _ADD_COMBO, _ADD_AMONG, _ADD_IMPRINTED)


_PAIN = re.compile(rf"\{{T\}}: Add \{{([WUBRGC])\}} or \{{([WUBRGC])\}}\. {_SELF} deals {_N_FIXED} damage to you\.", re.I)


# Ancient Tomb: two mana, and the damage is dealt once however much of it is used.
_PAIN_MULTI = re.compile(rf"\{{T\}}: Add ((?:\{{[WUBRGC]\}}){{2,}})\. {_SELF} deals {_N_FIXED} damage to you\.", re.I)


# City of Brass: the damage comes from the land becoming tapped.
_TAPPED_PAIN = re.compile(rf"Whenever {_SELF} becomes tapped, it deals {_N_FIXED} damage to you\.", re.I)


# Mana Confluence: paying life, not damage.
_PAY_LIFE_ANY = re.compile(rf"\{{T\}}, Pay {_N_FIXED} life: Add (one mana of any color|\{{([WUBRG])\}}(?: or \{{([WUBRG])\}})?)\.{_IF_TAIL}", re.I)


# Room of Refuge: one mana of the color chosen as it entered. A Thriving land or Gate also makes its own color.
_ADD_CHOSEN = re.compile(r"\{T\}: Add (?:\{([WUBRG])\} or )?one mana of the chosen color\.")


def chosen_color_mana(card: Card) -> tuple[str | None] | None:
    """(its own color or None,) for a land whose mana ability makes the chosen color; None for any other card."""
    return next(((m[1],) for line in rules_lines(card) if (m := _ADD_CHOSEN.fullmatch(line))), None)


# Vivid Crag: "{T}, Remove a charge counter from this land: Add one mana of any color." Hickory Woodlot: "{T}, Remove a
# depletion counter from this land: Add {G}{G}. If there are no depletion counters on this land, sacrifice it."
_REMOVE_COUNTER_MANA = re.compile(r"\{T\}, Remove an? ([a-z]+) counter from (?:CARDNAME|this land): Add "
                                  r"(one mana of any color|(?:\{[WUBRGC]\})+)\.( If there are no \1 counters on (?:CARDNAME|this land), sacrifice it\.)?")


# Hollow Trees, Fountain of Cho: any number of counters come off for that much mana.
_REMOVE_ANY_NUMBER_MANA = re.compile(r"\{T\}, Remove any number of ([a-z]+) counters from (?:CARDNAME|this land): "
                                     r"Add \{([WUBRGC])\} for each \1 counter removed this way\.")


@dataclass(frozen=True)
class CounterMana:
    counter: str  # the counter removed for the mana
    mana: tuple[frozenset[str], ...]  # one set of types per mana
    sacrifice_at_zero: bool  # the land is sacrificed when the last counter is gone
    each: bool = False  # one mana (`mana[0]`) per counter, and as many counters come off as the mana used


def counter_removal_mana(card: Card) -> CounterMana | None:
    """A land whose mana costs a counter (the Vivid lands, the depletion lands, the storage lands), or None."""
    for line in rules_lines(card):
        if m := _REMOVE_COUNTER_MANA.fullmatch(line):
            mana = (frozenset("WUBRG"),) if m[2].startswith("one") else tuple(frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[2]))
            return CounterMana(m[1], mana, m[3] is not None)
        if m := _REMOVE_ANY_NUMBER_MANA.fullmatch(line):
            return CounterMana(m[1], (frozenset(m[2]),), False, each=True)
    return None


# Hollow Trees: "You may choose not to untap this land during your untap step."
_MAY_NOT_UNTAP = re.compile(r"You may choose not to untap (?:CARDNAME|this [a-z]+) during your untap step\.")


def may_skip_untap(card: Card) -> bool:
    return any(_MAY_NOT_UNTAP.fullmatch(line) for line in rules_lines(card))


def is_optional_untap_line(line: str) -> bool:
    return _MAY_NOT_UNTAP.fullmatch(line) is not None


def is_mana_ability(line: str) -> bool:
    line = _without_spent_rider(_THRESHOLD.sub(r"\2", line))
    return (_mana_match(line) is not None or _ADD_CHOSEN.fullmatch(line) is not None or _REMOVE_COUNTER_MANA.fullmatch(line) is not None or _REMOVE_ANY_NUMBER_MANA.fullmatch(line) is not None or _ADD_POWER.fullmatch(line) is not None
            or _COUNTER_MANA.fullmatch(line) is not None or _PER_COUNT.fullmatch(line) is not None
            or _CHARGE_MANA.fullmatch(line) is not None
            or _FILTER.fullmatch(line) is not None
            or _FILTER_ANY.fullmatch(line) is not None or _FILTER_LAND.fullmatch(line) is not None or _REFLECT.fullmatch(line) is not None
            or any(p.fullmatch(line) for p in (_PAIN, _PAIN_MULTI, _TAPPED_PAIN, _PAY_LIFE_ANY)))


def mana_pain(card: Card) -> tuple[frozenset[str], int] | None:
    """For painlands and Talismans ("{T}: Add {G} or {U}. This land deals 1 damage to you."): the types
    that cost damage when produced, and how much."""
    for line in rules_lines(card):
        if m := _PAIN.fullmatch(line):
            return frozenset((m[1], m[2])), _number(m[3])
        if m := _PAIN_MULTI.fullmatch(line):
            return frozenset(re.findall(r"[WUBRGC]", m[1])), _number(m[2])
        if m := _TAPPED_PAIN.fullmatch(line):  # every color it makes hurts
            return frozenset("WUBRGC"), _number(m[1])
    return None


_REFLECT = re.compile(r"\{T\}: Add one mana of any (color|type) that a land (an opponent controls|you control) could produce\.")


def reflected_mana(card: Card) -> tuple[bool, bool] | None:
    """Exotic Orchard ("... any color that a land an opponent controls could produce") and Reflecting Pool ("... any
    type that a land you control could produce"): (looks at opponents' lands, colorless counts), or None."""
    for line in rules_lines(card):
        if m := _REFLECT.fullmatch(line):
            return m[2] == "an opponent controls", m[1] == "type"
    return None


def mana_life_cost(card: Card) -> int:
    """Life paid each time a land is tapped for mana ("{T}, Pay 1 life: Add one mana of any color."), or 0."""
    return next((_number(m[1]) for line in rules_lines(card) if (m := _PAY_LIFE_ANY.fullmatch(line))), 0)


def mana_life_types(card: Card) -> frozenset[str]:
    """The mana a land with a life-cost mana ability makes: any color (Mana Confluence) or the listed ones (Horizon lands)."""
    for line in rules_lines(card):
        if m := _PAY_LIFE_ANY.fullmatch(line):
            return frozenset("WUBRG") if m[2].startswith("one") else frozenset(c for c in (m[3], m[4]) if c)
    return frozenset()


def mana_lines(card: Card) -> list[tuple[frozenset[str], "Condition | None"]] | None:
    """A land with several plain "{T}: Add {R}." lines, one of them with an "Activate only if" condition (the Verge lands: "{T}: Add
    {B}." and "{T}: Add {R}. Activate only if you control a Swamp or a Mountain."): each line's color and condition. None otherwise."""
    found = []
    for line in rules_lines(card):
        if (m := _ADD_SYMBOLS.fullmatch(line)) and len(re.findall(r"[WUBRGC]", m[2])) == 1:
            found.append((frozenset(m[2][1]), _condition(m[3]) if m[3] else None))
    return found if len(found) > 1 and any(condition for _, condition in found) else None


def land_mana_units(card: Card) -> list[frozenset[str]] | None:
    """The mana a land makes in one tap when that's more than one ("{T}: Add {B}{G}.", Ancient Tomb's
    {C}{C}), one set per mana; None for the usual one mana, which comes from the card's data."""
    for line in rules_lines(card):
        m = _ADD_SYMBOLS.fullmatch(line) or _PAIN_MULTI.fullmatch(line)
        if m:
            symbols = re.findall(r"[WUBRGC]", m[2] if m.re is _ADD_SYMBOLS else m[1])
            return [frozenset(symbol) for symbol in symbols] if len(symbols) > 1 else None
    return None


def is_identity_mana_land(card: Card) -> bool:
    """Command Tower: a land that makes one mana of any color in your commander's color identity."""
    return "Land" in card.type_line and any(_ADD_IDENTITY.fullmatch(_without_spent_rider(line)) for line in rules_lines(card))


_FILTER = re.compile(r"((?:\{\d+\}|\{[WUBRGC]\}|\{[WUBRG]/[WUBRG]\})+), \{T\}: Add ((?:\{[WUBRGC]\})+)\.")


# Gaea's Cradle, Cabal Coffers, Elvish Archdruid: "{T}: Add {G} for each creature you control." (maybe with a mana cost)
_PER_COUNT = re.compile(r"(?:((?:\{\d+\}|\{[WUBRGC]\})+), )?\{T\}: Add \{([WUBRGC])\} for each ([A-Za-z]+) you control\.")


def mana_per_count(card: Card) -> tuple[str, str, str] | None:
    """(the mana it costs, '' if none; the color it makes; what it counts) for a "Add {G} for each creature you
    control" ability."""
    for line in rules_lines(card):
        if m := _PER_COUNT.fullmatch(_THRESHOLD.sub(r"\2", line)):
            return m[1] or "", m[2], m[3]
    return None


def mana_threshold(card: Card) -> int:
    """Evendo, Uthros: "12+ | {G}, {T}: Add {G} for each creature you control." works only with that many charge counters."""
    return next((int(m[1]) for line in rules_lines(card) if (m := _THRESHOLD.fullmatch(line)) and _PER_COUNT.fullmatch(m[2])), 0)


_FILTER_ANY = re.compile(r"((?:\{\d+\}|\{[WUBRGC]\})+), \{T\}: Add one mana of any color(?: in your commander's color identity)?\.")  # Hall of Oracles


# A filter land: "{W/B}, {T}: Add {W}{W}, {W}{B}, or {B}{B}." Two mana, each of either color.
_FILTER_LAND = re.compile(r"(\{[WUBRG]/[WUBRG]\}), \{T\}: Add \{([WUBRG])\}\{\2\}, \{\2\}\{([WUBRG])\}, or \{\3\}\{\3\}\.")


def filter_mana_ability(card: Card) -> tuple[str, list[frozenset[str]]] | None:
    """A mana ability that costs mana, like a Signet's "{1}, {T}: Add {W}{U}.":
    (the mana it costs, the mana it makes, one set per mana)."""
    for line in map(_without_spent_rider, rules_lines(card)):
        if m := _FILTER.fullmatch(line):
            return m[1], [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[2])]
        if m := _FILTER_ANY.fullmatch(line):
            return m[1], [frozenset("WUBRG")]
        if m := _FILTER_LAND.fullmatch(line):
            return m[1], [frozenset((m[2], m[3]))] * 2
    return None


def _mana_from_line(line: str, commander_identity: frozenset[str]) -> list[frozenset[str]] | None:
    line = _without_spent_rider(line)
    line = _CONDITION_WORD.sub("", line, count=1)
    if m := _ADD_SYMBOLS.fullmatch(line):
        return [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[2])]
    if m := _ADD_EITHER.fullmatch(line):
        return [frozenset((m[2], m[3]))]
    if m := _ADD_THREE.fullmatch(line):
        return [frozenset((m[2], m[3], m[4]))]
    if _ADD_ANY.fullmatch(line):
        return [frozenset("WUBRG")]
    if m := _ADD_ANY_N.fullmatch(line):
        return [frozenset("WUBRG")] * _ANY_N[m[2]]
    if m := _ADD_COMBO.fullmatch(line):
        return [frozenset(re.findall(r"[WUBRGC]", m[3]))] * _ANY_N[m[2]]
    if _ADD_AMONG.fullmatch(line) or _ADD_IMPRINTED.fullmatch(line):
        return [frozenset("WUBRG")]  # narrowed to the right colors by the game when the mana is wanted
    return [commander_identity] if commander_identity else None
