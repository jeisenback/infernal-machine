"""What it costs to cast or play: alternative and additional costs, kicker and its kin, cost reductions, cycling, suspend."""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass

from ..cards import Card

from .common import (
    _CANT_COUNTER,
    _COLOR_LETTER,
    _COLOR_NAMES,
    _MANA_SYMBOLS,
    _N,
    _N_FIXED,
    _number,
    _split_sentences,
    rules_lines,
)
from .outcomes import Condition, Draw, SearchForLands, _condition, _parse


_SUSPEND = re.compile(r"Suspend (\d+)—((?:\{[^}]+\})+)")


def suspend_of(card: Card) -> tuple[int, str] | None:
    """Suspend N—{cost}: (the time counters, the cost to exile it from your hand with them)."""
    return next(((int(m[1]), m[2]) for line in rules_lines(card) if (m := _SUSPEND.fullmatch(line))), None)


_STRIVE = re.compile(r"Strive \u2014 This spell costs ((?:\{[^}]+\})+) more to cast for each target beyond the first\.")


def strive_cost(card: Card) -> str | None:
    """Twinflame's "Strive": the mana added for each target beyond the first, or None."""
    return next((m[1] for line in rules_lines(card) if (m := _STRIVE.fullmatch(line))), None)


_CYCLING = re.compile(r"(Cycling|Basic landcycling|(?:Plains|Island|Swamp|Mountain|Forest)cycling)"
                      r"(?: ((?:\{\d+\}|\{[WUBRGC]\})+)|\u2014Pay (\d+) life\.?)")


_CYCLING_LAND_TYPES = {"plainscycling": "Plains", "islandcycling": "Island", "swampcycling": "Swamp",
                       "mountaincycling": "Mountain", "forestcycling": "Forest"}


def cycling(card: Card) -> tuple[str, str, tuple, int] | None:
    """A card's cycling: (its name, like "Forestcycling", the mana cost, what the ability does when it resolves,
    the life it costs instead of mana). Plain cycling draws a card; basic landcycling and Forestcycling-style abilities fetch a land to your hand."""
    for line in rules_lines(card):
        if m := _CYCLING.fullmatch(line):
            word = m[1]
            if word == "Cycling":
                effects: tuple = (Draw(1),)
            elif word == "Basic landcycling":
                effects = (SearchForLands(1, (), 0, False, True),)
            else:
                effects = (SearchForLands(1, (_CYCLING_LAND_TYPES[word.lower()],), 0, False, True),)
            return word, m[2] or "", effects, int(m[3] or 0)
    return None


def is_cycling_line(line: str) -> bool:
    return _CYCLING.fullmatch(line) is not None


@dataclass(frozen=True)
class AlternativeCost:
    """A way to cast a spell instead of paying its mana cost (CR 118.9)."""
    text: str  # how it's offered to the caster
    commander: bool = False  # "If you control a commander, ..."
    not_your_turn: bool = False  # "If it's not your turn, ..."
    life: int = 0
    exile_color: str | None = None  # exile a card of this color (a letter) from your hand
    mana_cost: str = ""  # an alternative cost that is mana ("Evoke {2}{U}", "Overload {6}{U}"), paid instead of the mana cost
    evoke: bool = False  # the creature is sacrificed when it enters
    overload: bool = False  # every "target" in the spell becomes "each"
    bestow: bool = False  # cast as an Aura spell with enchant creature
    dash: bool = False  # the creature has haste and returns to its owner's hand at the next end step (Ragavan)
    warp: bool = False  # exiled at the next end step, and castable from exile on a later turn


@dataclass(frozen=True)
class AdditionalCost:
    """"As an additional cost to cast this spell, ..." (CR 601.2b)."""
    sacrifice: str | None = None  # the kind of permanent: "creature", "artifact or creature", ...
    discard: bool = False
    life: int = 0
    life_x: bool = False  # "pay X life" (Toxic Deluge): X is chosen as the spell is cast
    sacrifice_x: bool = False  # "sacrifice X creatures" (Immoral Bargain): `sacrifice` is the kind, X of them
    mana: str = ""  # "pay {2}": mana added to the cost (only as one of `options`)
    options: tuple["AdditionalCost", ...] = ()  # "sacrifice an artifact or discard a card": pay one of these


_KICKER = re.compile(rf"(?:Multik|K)icker ({_MANA_SYMBOLS})(?: and/or ({_MANA_SYMBOLS}))?")


_KICKER_OTHER = re.compile(rf"Kicker\u2014(?:Sacrifice an? (creature|artifact|land|artifact or creature|permanent)"
                           rf"|(Discard a card)|Pay (?!X ){_N_FIXED} life)\.")


_BUYBACK = re.compile(rf"Buyback ({_MANA_SYMBOLS})")


_BUYBACK_OTHER = re.compile(rf"Buyback\u2014(?:Sacrifice an? (land)|Pay {_N_FIXED} life)\.")


_FREE_WITH_COMMANDER = re.compile(r"If you control a commander, you may cast this spell without paying its mana cost\.")


_PITCH = re.compile(rf"(If it's not your turn, )?(?i:you) may (?:pay {_N_FIXED} life and )?exile an? ({_COLOR_NAMES}) card "
                    r"from your hand rather than pay this spell's mana cost\.")


_ADDITIONAL = re.compile(rf"As an additional cost to cast this spell, (?:sacrifice an? (creature|artifact|land|artifact or "
                         rf"creature|permanent|green creature)|(discard a card)|pay {_N} life|sacrifice (X) (creatures|artifacts|lands|permanents))\.")


_ADDITIONAL_PART = (r"(?:sacrifice an? (artifact or creature|creature or planeswalker|creature or enchantment|creature or land|creature|artifact|land"
                    rf"|permanent|green creature)|(discard a card)|pay {_N_FIXED} life|pay ((?:\{{[^}}]+\}})+))")


_ADDITIONAL_EITHER = re.compile(rf"As an additional cost to cast this spell, ({_ADDITIONAL_PART}(?:(?:, or |, | or ){_ADDITIONAL_PART})+)\.")


_X_LIMIT = re.compile(r"X can't be greater than the number of players in the game\.")  # Open the Way


_ENTWINE = re.compile(r"Entwine ((?:\{[^}]+\})+)")


_ESCALATE = re.compile(r"Escalate ((?:\{[^}]+\})+)")  # "Escalate\u2014Discard a card." (a cost that isn't mana) isn't supported


_FLASHBACK = re.compile(r"Flashback ((?:\{[^}]+\})+)")


@dataclass(frozen=True)
class MorphCost:
    """What turning a face-down creature face up costs: mana, or (Morph\u2014Sacrifice another creature.) something else."""
    mana: str = ""
    sacrifice: str = ""  # a kind of permanent ("creature", "Mountain"); `another`: not the creature itself
    count: int = 1  # how many of them to sacrifice or return
    discard: str = ""  # "card" or a card type ("Zombie")
    reveal: str = ""  # a color letter: a card of that color in your hand
    bounce: str = ""  # a kind of permanent you control to return to its owner's hand
    life: int = 0


_GIFT = re.compile(r"Gift an? (card|Treasure|Food|tapped Fish|Octopus|extra turn)")


def gift_of(card: Card) -> str | None:
    """What the card's Gift gives an opponent if it is promised: "card", "Treasure", "Food", "tapped Fish", "Octopus" or "extra turn"."""
    return next((m[1] for line in rules_lines(card) if (m := _GIFT.fullmatch(line))), None)


_DISTURB = re.compile(r"Disturb ((?:\{[^}]+\})+)")


def disturb_of(card: Card) -> str | None:
    """The mana cost to cast the back face of a transforming card from the graveyard ("Disturb {1}{U}")."""
    return next((m[1] for line in rules_lines(card) if (m := _DISTURB.fullmatch(line))), None)


_FORETELL = re.compile(r"Foretell ((?:\{[^}]+\})+)")


def foretell_of(card: Card) -> str | None:
    """The mana cost to cast the card from exile once it has been foretold ("Foretell {1}{U}")."""
    return next((m[1] for line in rules_lines(card) if (m := _FORETELL.fullmatch(line))), None)


_NINJUTSU = re.compile(r"(Commander ninjutsu|Ninjutsu) ((?:\{[^}]+\})+)")


def ninjutsu_of(card: Card) -> tuple[str, bool] | None:
    """The mana cost of the card's Ninjutsu, and whether it is "Commander ninjutsu" (usable from the command zone too)."""
    for line in rules_lines(card):
        if m := _NINJUTSU.fullmatch(line):
            return m[2], m[1] == "Commander ninjutsu"
    return None


_MORPH = re.compile(r"(Morph|Megamorph|Disguise) ((?:\{[^}]+\})+)")
_MORPH_OTHER = re.compile(rf"(Morph|Megamorph|Disguise)\u2014(.+?)\.?")
_MORPH_NOUN = r"((?-i:[A-Z][a-z]+?))s?"  # "Mountains", "Bird"
_MORPH_COSTS = [
    (re.compile(r"Sacrifice another creature"), lambda m: MorphCost(sacrifice="another creature")),
    (re.compile(rf"Sacrifice {_N_FIXED} {_MORPH_NOUN}"), lambda m: MorphCost(sacrifice=m[2], count=_number(m[1]))),
    (re.compile(rf"Reveal an? ({_COLOR_NAMES}) card in your hand"), lambda m: MorphCost(reveal=_COLOR_LETTER[m[1].lower()])),
    (re.compile(rf"Return {_N_FIXED} {_MORPH_NOUN} you control to (?:its|their) owner's hand"),
     lambda m: MorphCost(bounce=m[2], count=_number(m[1]))),
    (re.compile(r"Discard a card"), lambda m: MorphCost(discard="card")),
    (re.compile(r"Discard an? ((?-i:[A-Z][a-z]+)) card"), lambda m: MorphCost(discard=m[1])),
    (re.compile(rf"Pay {_N_FIXED} life"), lambda m: MorphCost(life=_number(m[1]))),
]


def _morph_line(line: str) -> tuple[str, MorphCost] | None:
    if m := _MORPH.fullmatch(line):
        return m[1], MorphCost(m[2])
    if m := _MORPH_OTHER.fullmatch(line):
        for pattern, build in _MORPH_COSTS:
            if found := pattern.fullmatch(m[2]):
                return m[1], build(found)
    return None


def morph_of(card: Card) -> tuple[str, MorphCost] | None:
    """(Morph, Megamorph or Disguise; what it costs to turn it face up) of a card that can be cast face down for {3}."""
    for line in rules_lines(card):
        if found := _morph_line(line):
            return found
    return None


_AFTERMATH = re.compile(r"Aftermath")  # the second half of a split card: cast only from the graveyard, then exiled


_FLASHBACK_LIFE = re.compile(r"Flashback\u2014((?:\{[^}]+\})+), Pay (\d+) life\.")  # Deep Analysis


_FROM_GRAVEYARD_BY_PAYING = re.compile(r"You may cast this card from your graveyard by paying ((?:\{[^}]+\})+) rather than paying "
                                       r"its mana cost\.")  # Raffine's Guidance


_RETRACE = re.compile(r"Retrace")


_BESTOW = re.compile(r"Bestow ((?:\{[^}]+\})+)")


_ENCORE = re.compile(r"Encore ((?:\{[^}]+\})+)")


_UNEARTH = re.compile(r"Unearth ((?:\{[^}]+\})+)")


_MADNESS = re.compile(r"Madness ((?:\{[^}]+\})+)")


def bestow_aura(card: Card) -> Card:
    """The card as it is while a bestow spell or an Aura permanent: an Aura with enchant creature, not a creature."""
    return dataclasses.replace(card, type_line="Enchantment " + chr(0x2014) + " Aura", oracle_text=card.oracle_text + chr(10) + "Enchant creature")


def madness_cost(card: Card) -> str | None:
    """Madness {cost}: when the card is discarded it goes to exile, and its owner may cast it for this cost."""
    return next((m[1] for line in rules_lines(card) if (m := _MADNESS.fullmatch(line))), None)


def unearth_cost(card: Card) -> str | None:
    """Unearth {cost}: from the graveyard to the battlefield with haste, exiled at the next end step (a mana cost only)."""
    return next((m[1] for line in rules_lines(card) if (m := _UNEARTH.fullmatch(line))), None)


def encore_cost(card: Card) -> str | None:
    """Encore {cost}: from the graveyard, for each opponent a token copy attacks that opponent this turn."""
    return next((m[1] for line in rules_lines(card) if (m := _ENCORE.fullmatch(line))), None)


_ESCAPE = re.compile(r"Escape\u2014((?:\{[^}]+\})+), Exile (a|one|two|three|four|five|six) other cards? from your graveyard\.")


_TWO_COLOR_REDUCTION = re.compile(rf"Each spell you cast that's ({_COLOR_NAMES}) or ({_COLOR_NAMES}) costs \{{(\d+)\}} less to cast\.", re.I)


_REDUCTION = re.compile(rf"(?:({_COLOR_NAMES}|creature|artifact|enchantment|noncreature|instant and sorcery|Aura and Equipment|Aura) )?spells "
                        r"you cast( that target a creature)? cost \{(\d+)\} less to cast\.", re.I)


def kicker_costs(card: Card) -> tuple[str, ...]:
    """The mana kicker costs: one for "Kicker {1}{U}" or "Multikicker {1}{G}", two for "Kicker {R} and/or {W}",
    none if there's no kicker or it isn't mana."""
    for line in rules_lines(card):
        if m := _KICKER.fullmatch(line):
            return tuple(cost for cost in m.groups() if cost)
    return ()


def kicker_other_cost(card: Card) -> AdditionalCost | None:
    """A kicker cost that isn't mana: "Kicker—Sacrifice a land.", "Kicker—Discard a card.", "Kicker—Pay 3 life." """
    for line in rules_lines(card):
        if m := _KICKER_OTHER.fullmatch(line):
            return AdditionalCost(sacrifice=m[1], discard=bool(m[2]), life=_number(m[3]) if m[3] else 0)
    return None


def buyback_cost(card: Card) -> str | None:
    """The mana cost from "Buyback {3}": pay it as an additional cost and the spell returns to your hand as it resolves."""
    return next((m[1] for line in rules_lines(card) if (m := _BUYBACK.fullmatch(line))), None)


def buyback_other_cost(card: Card) -> AdditionalCost | None:
    """A buyback cost that isn't mana: "Buyback\u2014Sacrifice a land." or "Buyback\u2014Pay 4 life." """
    for line in rules_lines(card):
        if m := _BUYBACK_OTHER.fullmatch(line):
            return AdditionalCost(sacrifice=m[1], life=_number(m[2]) if m[2] else 0)
    return None


def entwine_cost(card: Card) -> str | None:
    """The mana cost from "Entwine {2}": pay it to choose all the modes of a modal spell."""
    return next((m[1] for line in rules_lines(card) if (m := _ENTWINE.fullmatch(line))), None)


def escalate_cost(card: Card) -> str | None:
    """The mana cost from "Escalate {1}": pay it for each mode chosen beyond the first."""
    return next((m[1] for line in rules_lines(card) if (m := _ESCALATE.fullmatch(line))), None)


def is_multikicker(card: Card) -> bool:
    """Multikicker: the kicker cost can be paid any number of times (CR 702.33c)."""
    return any(line.startswith("Multikicker ") and _KICKER.fullmatch(line) for line in rules_lines(card))


_DEVOUR = re.compile(r"Devour (\d+)")


_REPLICATE = re.compile(r"Replicate ((?:\{[^}]+\})+)")


_AFFINITY = re.compile(r"Affinity for ([a-z]+?)s?")


_STORM_LIKE = re.compile(r"(Storm|Gravestorm)")


def devour(card: Card) -> int:
    """Devour N: as it enters you may sacrifice creatures; it enters with N +1/+1 counters for each. 0 if it has none."""
    for line in rules_lines(card):
        if m := _DEVOUR.fullmatch(line):
            return int(m[1])
    return 0


def replicate_cost(card: Card) -> str | None:
    for line in rules_lines(card):
        if m := _REPLICATE.fullmatch(line):
            return m[1]
    return None


def affinity_for(card: Card) -> str | None:
    """Affinity for planeswalkers: costs {1} less for each planeswalker you control ("planeswalker")."""
    for line in rules_lines(card):
        if m := _AFFINITY.fullmatch(line):
            return m[1]
    return None


def storm_kind(card: Card) -> str | None:
    """"storm" or "gravestorm" for a spell that copies itself when cast."""
    for line in rules_lines(card):
        if m := _STORM_LIKE.fullmatch(line):
            return m[1].lower()
    return None


def is_cast_keyword_line(line: str) -> bool:
    """Replicate, Storm, Gravestorm, Affinity and Devour lines: rules the game applies itself."""
    return any(p.fullmatch(line) for p in (_DEVOUR, _REPLICATE, _AFFINITY, _STORM_LIKE))


_ECHO = re.compile(r"Echo ((?:\{[^}]+\})+)")


def echo_cost(card: Card) -> str | None:
    """Karmic Guide: the mana to pay at your next upkeep after it comes under your control, or sacrifice it."""
    for line in rules_lines(card):
        if m := _ECHO.fullmatch(line):
            return m[1]
    return None


def is_echo_line(line: str) -> bool:
    return _ECHO.fullmatch(line) is not None


_CUMULATIVE_UPKEEP = re.compile(r"Cumulative upkeep ((?:\{[^}]+\})+)")


def cumulative_upkeep(card: Card) -> str | None:
    """Mystic Remora: the mana to pay for each age counter at the beginning of your upkeep, or None."""
    for line in rules_lines(card):
        if m := _CUMULATIVE_UPKEEP.fullmatch(line):
            return m[1]
    return None


def is_cumulative_upkeep_line(line: str) -> bool:
    return _CUMULATIVE_UPKEEP.fullmatch(line) is not None


_EVOKE = re.compile(r"Evoke ((?:\{[^}]+\})+)")


_DASH = re.compile(r"Dash ((?:\{[^}]+\})+)")


_WARP = re.compile(r"Warp ((?:\{[^}]+\})+)")


_OVERLOAD = re.compile(r"Overload ((?:\{[^}]+\})+)")


def overloaded_effects(card: Card) -> list | None:
    """What an overloaded spell does: the same text with every "target" read as "each" (Cyclonic Rift), or None if
    the card has no Overload or that text isn't understood."""
    if not any(_OVERLOAD.fullmatch(line) for line in rules_lines(card)):
        return None
    lines = [line for line in rules_lines(card) if not is_casting_cost_line(line)]
    return _parse(_split_sentences(re.sub(r"\b([Tt])arget\b", lambda m: "Each" if m[1] == "T" else "each", "\n".join(lines))))


def is_overload_line(line: str) -> bool:
    return _OVERLOAD.fullmatch(line) is not None


def alternative_costs(card: Card) -> list[AlternativeCost]:
    costs = []
    for line in rules_lines(card):
        if m := _EVOKE.fullmatch(line):
            costs.append(AlternativeCost(f"Evoke {m[1]}", mana_cost=m[1], evoke=True))
            continue
        if m := _DASH.fullmatch(line):
            costs.append(AlternativeCost(f"Dash {m[1]}", mana_cost=m[1], dash=True))
            continue
        if m := _WARP.fullmatch(line):
            costs.append(AlternativeCost(f"Warp {m[1]}", mana_cost=m[1], warp=True))
            continue
        if m := _OVERLOAD.fullmatch(line):
            if overloaded_effects(card):
                costs.append(AlternativeCost(f"Overload {m[1]}", mana_cost=m[1], overload=True))
            continue
        if m := _BESTOW.fullmatch(line):
            costs.append(AlternativeCost(f"Bestow {m[1]}", mana_cost=m[1], bestow=True))
            continue
        if _FREE_WITH_COMMANDER.fullmatch(line):
            costs.append(AlternativeCost("Cast without paying its mana cost", commander=True))
        elif m := _PITCH.fullmatch(line):
            life = _number(m[2]) if m[2] else 0
            text = f"Pay {life} life and exile a {m[3]} card" if life else f"Exile a {m[3]} card"
            costs.append(AlternativeCost(text, not_your_turn=bool(m[1]), life=life, exile_color=_COLOR_LETTER[m[3]]))
    return costs


@dataclass(frozen=True)
class GraveyardCast:
    """A way to cast a card from the graveyard: Flashback (then it is exiled) or Escape (exile other cards too)."""
    word: str  # "Flashback", "Escape", "Retrace" or "Aftermath"
    cost: str  # the mana cost to pay instead of the card's own
    exile: int = 0  # other cards to exile from the graveyard (Escape)
    exile_after: bool = False  # exile it instead of putting it in the graveyard when it leaves the stack (Flashback)
    discard_land: bool = False  # Retrace: discard a land card in addition to the cost
    life: int = 0  # "Flashback\u2014{1}{U}, Pay 3 life."


def graveyard_casts(card: Card) -> list[GraveyardCast]:
    found = []
    for line in rules_lines(card):
        if m := _FLASHBACK.fullmatch(line):
            found.append(GraveyardCast("Flashback", m[1], exile_after=True))
        elif m := _FLASHBACK_LIFE.fullmatch(line):
            found.append(GraveyardCast("Flashback", m[1], exile_after=True, life=int(m[2])))
        elif m := _FROM_GRAVEYARD_BY_PAYING.fullmatch(line):
            found.append(GraveyardCast("From the graveyard", m[1]))
        elif m := _ESCAPE.fullmatch(line):
            found.append(GraveyardCast("Escape", m[1], exile=_number(m[2])))
        elif _RETRACE.fullmatch(line):
            found.append(GraveyardCast("Retrace", card.mana_cost, discard_land=True))
        elif _AFTERMATH.fullmatch(line):
            found.append(GraveyardCast("Aftermath", card.mana_cost, exile_after=True))
    return found


def is_aftermath(card: Card) -> bool:
    """An Aftermath half can be cast only from the graveyard."""
    return any(cast.word == "Aftermath" for cast in graveyard_casts(card))


# Serra Paragon: one land or cheap permanent spell from the graveyard each turn; the permanent is exiled if it goes back.
_PARAGON = re.compile(r"Once during each of your turns, you may play a land from your graveyard or cast a permanent spell with "
                      r"mana value (\d+) or less from your graveyard\. If you do, it gains \"When this permanent is put into a "
                      r"graveyard from the battlefield, exile it and you gain (\d+) life\.\"")


def graveyard_permission(card: Card) -> tuple[int, int] | None:
    """Serra Paragon: (the most mana value of the permanent spell, the life gained when it goes to the graveyard)."""
    return next(((int(m[1]), int(m[2])) for line in rules_lines(card) if (m := _PARAGON.fullmatch(line))), None)


def is_graveyard_permission_line(line: str) -> bool:
    return _PARAGON.fullmatch(line) is not None


def additional_costs(card: Card) -> list[AdditionalCost]:
    costs = []
    for line in rules_lines(card):
        if m := _ADDITIONAL.fullmatch(line):
            life_x = (m[3] or "").upper() == "X"
            costs.append(AdditionalCost(sacrifice=m[1] or (m[5].removesuffix("s") if m[5] else None), discard=bool(m[2]),
                                        life=0 if life_x or not m[3] else _number(m[3]), life_x=life_x, sacrifice_x=bool(m[5])))
        elif m := _ADDITIONAL_EITHER.fullmatch(line):  # Demand Answers, Bitter Triumph, Redirect Lightning, Eaten Alive
            costs.append(AdditionalCost(options=tuple(
                AdditionalCost(sacrifice=part[0] or None, discard=bool(part[1]), life=_number(part[2]) if part[2] else 0, mana=part[3])
                for part in re.findall(_ADDITIONAL_PART, m[1]))))
    return costs


def x_limited_by_players(card: Card) -> bool:
    """Open the Way: "X can't be greater than the number of players in the game." """
    return any(_X_LIMIT.fullmatch(line) for line in rules_lines(card))


_CHOSEN_REDUCTION = re.compile(r"(Creature spells|Spells)( you cast)? of the chosen type cost \{(\d+)\} less to cast\.")


def chosen_cost_reductions(card: Card) -> list[tuple[bool, bool, int]]:
    """Herald's Horn, Urza's Incubator, Gathering Stone: spells of the creature type the permanent chose cost less, as
    (only creature spells, only the controller's spells, how much)."""
    return [(m[1] == "Creature spells", m[2] is not None, int(m[3]))
            for line in rules_lines(card) if (m := _CHOSEN_REDUCTION.fullmatch(line))]


def cost_reductions(card: Card) -> list[tuple[str, int]]:
    """Static "Green spells you cast cost {1} less to cast." abilities (Medallions): (what kind of spell, how much).
    The kind is a color letter, a card type ("creature", "noncreature", "instant and sorcery") or "spell"."""
    found = []
    for line in rules_lines(card):
        if m := _TWO_COLOR_REDUCTION.fullmatch(line):  # Goblin Anarchomancer: red or green spells
            found.append((f"{_COLOR_LETTER[m[1].lower()]}|{_COLOR_LETTER[m[2].lower()]}", int(m[3])))  # one reduction, however many colors
        elif m := _REDUCTION.fullmatch(line):
            kind = (m[1] or "spell").lower()
            found.append(("targets a creature" if m[2] else _COLOR_LETTER.get(kind, kind), int(m[3])))
    return found


_SPELL_KEYWORDS = re.compile(r"(?:Delve|Cascade|Devoid|Demonstrate|Convoke|Improvise|Split second|Rebound)(?:, (?:Delve|Cascade|Devoid|Demonstrate|Convoke|Improvise|Split second|Rebound))*")  # rules for casting, not effects


_SACRIFICE_FOR_COPIES = re.compile(r"As an additional cost to cast this spell, you may sacrifice one or more creatures\. When you do, copy "
                                   r"this spell for each creature sacrificed this way\.")


def copies_per_sacrifice(card: Card) -> bool:
    """Plumb the Forbidden: you may sacrifice creatures as you cast it, and it is copied for each."""
    return any(_SACRIFICE_FOR_COPIES.fullmatch(line) for line in rules_lines(card))


def is_casting_cost_line(line: str) -> bool:
    """Kicker, alternative and additional costs: rules for casting the spell rather than what it does."""
    return _morph_line(line) is not None or any(p.fullmatch(line) for p in (_GIFT, _DISTURB, _FORETELL, _NINJUTSU, _SACRIFICE_FOR_COPIES, _KICKER, _KICKER_OTHER, _FREE_WITH_COMMANDER, _PITCH, _ADDITIONAL, _ADDITIONAL_EITHER, _FLASHBACK, _RETRACE, _ENCORE, _UNEARTH, _MADNESS, _BUYBACK, _BUYBACK_OTHER, _BESTOW, _CANT_COUNTER, _SUSPEND, _ESCAPE, _AFTERMATH, _ENTWINE, _ESCALATE,
                                           _PER_REDUCTION, _CHOSEN_REDUCTION, _X_LIMIT, _EVOKE, _DASH, _WARP, _OVERLOAD, _SPELL_KEYWORDS, _REPLICATE, _STORM_LIKE,
                                           _AFFINITY, _STRIVE, _FLASHBACK_LIFE, _FROM_GRAVEYARD_BY_PAYING, _POWER_REDUCTION, _GREATEST_POWER_REDUCTION)) \
        or ((m := _IF_REDUCTION.fullmatch(line)) is not None and _condition(m[2]) is not None)


_X_DISCOUNT = re.compile(r"The first spell you cast with \{X\} in its mana cost each turn costs \{1\} less to cast for each "
                         r"\+1/\+1 counter on (?:CARDNAME|this creature)\.")


def is_x_discount_line(line: str) -> bool:
    return _X_DISCOUNT.fullmatch(line) is not None


def x_spell_discount(card: Card) -> bool:
    """Zimone, Infinite Analyst: its first X spell each turn costs {1} less for each +1/+1 counter on it."""
    return any(_X_DISCOUNT.fullmatch(line) for line in rules_lines(card))


_PER_REDUCTION = re.compile(r"This spell costs \{(\d+)\} less to cast for each "
                            r"(creature on the battlefield|instant and sorcery card in your graveyard)\.")


def self_cost_reduction(card: Card) -> tuple[int, str] | None:
    """Blasphemous Act: "This spell costs {1} less to cast for each creature on the battlefield." (how much each,
    what is counted: "creature" on the battlefield or "instant or sorcery" card in your graveyard)."""
    for line in rules_lines(card):
        if m := _PER_REDUCTION.fullmatch(line):
            return int(m[1]), "creature" if m[2].startswith("creature") else "instant or sorcery"
    return None


_IF_REDUCTION = re.compile(r"This spell costs \{(\d+)\} less to cast if (.+)\.")  # Mortality Spear


_POWER_REDUCTION = re.compile(r"This spell costs \{X\} less to cast, where X is the total power of creatures you control\.")


_GREATEST_POWER_REDUCTION = re.compile(r"This spell costs \{X\} less to cast, where X is the greatest power among creatures you control\.")


_GRANTED_AFFINITY = re.compile(r"(Enchantment|Aura) spells you cast have affinity for Auras\.")  # Pearl-Ear, Imperial Advisor


def conditional_cost_reduction(card: Card) -> tuple[int, Condition] | None:
    """Mortality Spear: "This spell costs {2} less to cast if you gained life this turn." (how much, and when)"""
    for line in rules_lines(card):
        if (m := _IF_REDUCTION.fullmatch(line)) and (condition := _condition(m[2])):
            return int(m[1]), condition
    return None


def reduced_by_total_power(card: Card) -> bool:
    """Volcanic Salvo: "This spell costs {X} less to cast, where X is the total power of creatures you control." """
    return any(_POWER_REDUCTION.fullmatch(line) for line in rules_lines(card))


def reduced_by_greatest_power(card: Card) -> bool:
    """The Great Henge: "This spell costs {X} less to cast, where X is the greatest power among creatures you control." """
    return any(_GREATEST_POWER_REDUCTION.fullmatch(line) for line in rules_lines(card))


def granted_affinity(card: Card) -> str | None:
    """Pearl-Ear: the kind of spell you cast that has affinity for Auras ("aura")."""
    return next((m[1].lower() for line in rules_lines(card) if (m := _GRANTED_AFFINITY.fullmatch(line))), None)


_NON_HAND_REDUCTION = re.compile(r"Spells you cast from anywhere other than your hand cost \{(\d)\} less to cast\.")


def non_hand_cost_reduction(card: Card) -> int:
    """Advanced Reconstruction's third level: spells you cast from anywhere other than your hand cost {2} less."""
    return sum(int(m[1]) for line in rules_lines(card) if (m := _NON_HAND_REDUCTION.fullmatch(line)))


def is_cost_reduction_line(line: str) -> bool:
    return any(p.fullmatch(line) for p in (_REDUCTION, _TWO_COLOR_REDUCTION, _PER_REDUCTION, _POWER_REDUCTION, _GRANTED_AFFINITY, _NON_HAND_REDUCTION)) \
        or (m := _IF_REDUCTION.fullmatch(line)) is not None and _condition(m[2]) is not None
