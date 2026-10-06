"""Card effects: reading rules text into things the game does.

Rules text is matched sentence by sentence against known templates. A spell
gets effects only if every sentence is understood; otherwise it resolves with
no effect and the game reports it as unsupported, instead of doing part of
what the card says. Triggered abilities on permanents ("When this creature
enters, draw a card.") use the same templates for what they do.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Callable

from .cards import Card
from .characteristics import Modifier

if TYPE_CHECKING:
    from .game import Game, Seat

_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_VOTE_PREFIX = r"(?:[A-Z][\w' -]* \u2014 )?"  # "Will of the council — ", "Council's dilemma — "
_N = r"(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+|X)"
_REMINDER = re.compile(r"\s*\([^)]*\)")
_SELF = (r"(?:CARDNAME|it|this (?:spell|creature|artifact|enchantment|land|planeswalker|permanent"
         r"|Aura|Equipment|Class|Vehicle|Saga))")


def _count(word: str) -> int | str:
    """A number from rules text; "X" stays "X" and the game fills it in (Game.amount)."""
    if word == "X":
        return "X"
    return int(word) if word.isdigit() else _NUMBERS[word.lower()]


def _rules_text(card: Card) -> str:
    """Oracle text without reminder text, with the card's own name as CARDNAME.

    Legendary cards often call themselves by their short name ("Omnath" for
    "Omnath, Locus of Rage"), and double-faced cards by their front face's name.
    """
    text = _REMINDER.sub("", card.oracle_text)
    front = card.name.split(" // ")[0]
    for name in dict.fromkeys((card.name, front, front.split(",")[0])):
        text = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", "CARDNAME", text)
    return text


def rules_lines(card: Card) -> list[str]:
    """The card's rules text, one ability per line, as the other functions here see it."""
    return [line.strip() for line in _rules_text(card).splitlines() if line.strip()]


def _split_sentences(text: str) -> list[str]:
    return [s.strip() for line in text.splitlines() for s in re.split(r"(?<=\.)\s+", line) if s.strip()]


def target_kind(effect: Any) -> str | None:
    """What an effect targets ("any", "creature", "spell", ...), or None."""
    return getattr(effect, "target", None)


def uses_source(effect: Any) -> bool:
    """Whether an effect acts on its ability's source ("put a +1/+1 counter on it")."""
    return getattr(effect, "uses_source", False)


def uses_subject(effect: Any) -> bool:
    """Whether an effect acts on the permanent that set off a watching trigger ("... put a counter on it")."""
    return getattr(effect, "uses_subject", False)


def uses_player(effect: Any) -> bool:
    """Whether an effect acts on the player who set off a watching trigger ("... that player loses 2 life")."""
    return getattr(effect, "uses_player", False)


def follows_target(effect: Any) -> bool:
    """Whether an effect acts on the previous effect's target ("Its controller gains life ...")."""
    return getattr(effect, "follows_target", False)


@dataclass(frozen=True)
class Draw:
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.draw(controller, game.amount(self.count))


@dataclass(frozen=True)
class GainLife:
    amount: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.change_life(controller, game.amount(self.amount))


@dataclass(frozen=True)
class OpponentsLoseLife:
    amount: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            game.change_life(seat, -game.amount(self.amount))


@dataclass(frozen=True)
class Damage:
    amount: int
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.damage(target, game.amount(self.amount))


@dataclass(frozen=True)
class Destroy:
    target: str
    another: bool = False  # "destroy another target ...": not the source itself
    no_regen: bool = False  # "It can't be regenerated."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.destroy(target, self.no_regen)


@dataclass(frozen=True)
class WardCounter:
    """The ward trigger of a permanent an opponent targeted: their spell or ability is countered
    unless they pay `cost`."""
    cost: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.resolve_ward(self.cost)


@dataclass(frozen=True)
class Counter:
    target: str = "spell"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.counter(target)


@dataclass(frozen=True)
class Exile:
    target: str
    another: bool = False  # "exile another target ...": not the source itself

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile(target)


@dataclass(frozen=True)
class ExileUntilLeaves:
    """Oblivion Ring, Banishing Light, Fiend Hunter: the target comes back when the source leaves the battlefield."""
    target: str
    another: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_until_leaves(target, game.resolving_source)


@dataclass(frozen=True)
class TargetDraw:
    count: int | str
    target: str = "player"  # "player" or "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.draw(target, game.amount(self.count))


@dataclass(frozen=True)
class TargetGainLife:
    amount: int | str
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(target, game.amount(self.amount))


@dataclass(frozen=True)
class TargetLoseLife:
    amount: int | str
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(target, -game.amount(self.amount))


@dataclass(frozen=True)
class Modal:
    """ "Choose one — • ... • ..." The caster picks between `min` and `max` of the modes when casting (Game
    flattens the chosen ones into the spell's effects); `texts` are the modes as printed."""
    min: int
    max: int
    modes: tuple[tuple, ...]  # the effects of each mode
    texts: tuple[str, ...]


_MODAL_COUNTS = {"one": (1, 1), "two": (2, 2), "three": (3, 3), "one or both": (1, 2), "one or more": (1, 0)}
_MODAL_HEADER = re.compile(r"Choose (one or both|one or more|one|two|three) \u2014", re.I)


def is_modal_header(line: str) -> bool:
    return _MODAL_HEADER.fullmatch(line) is not None


def mode_text(line: str) -> str:
    """A mode of a modal spell without its bullet."""
    return line[2:] if line.startswith("\u2022 ") else line


def _parse_modal(how: str, lines: list[str]) -> list | None:
    modes, texts = [], []
    for line in lines:
        if not line.startswith("\u2022 "):
            return None  # something other than modes (entwine, escalate, ...)
        effects = _parse(_split_sentences(mode_text(line)))
        if not effects:
            return None
        modes.append(tuple(effects))
        texts.append(mode_text(line))
    low, high = _MODAL_COUNTS[how]
    high = high or len(modes)
    return [Modal(low, high, tuple(modes), tuple(texts))] if len(modes) >= max(low, 1) else None


@dataclass(frozen=True)
class ExileGraveyard:
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_graveyard(target)


@dataclass(frozen=True)
class TargetControllerGainsLifeEqualToPower:
    """Swords to Plowshares: "Its controller gains life equal to its power." """
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.change_life(target.last_controller, max(0, target.last_power))


@dataclass(frozen=True)
class TargetControllerMayFetchBasicLand:
    """Path to Exile: "Its controller may search their library for a basic land card, ..." """
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.fetch_basic_land(target.last_controller, optional=True)


@dataclass(frozen=True)
class PutCounters:
    count: int
    counter: str  # "+1/+1" or "-1/-1"
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))


@dataclass(frozen=True)
class OnSubject:
    """A watching trigger's effect on "it": the permanent that set it off, not the ability's source."""
    inner: Any
    uses_subject = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        self.inner.resolve(game, controller, target)


@dataclass(frozen=True)
class OnPlayer:
    """A trigger's effect on "that player" / "they": the player whose action set it off."""
    inner: Any
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        self.inner.resolve(game, controller, target)


@dataclass(frozen=True)
class PutCountersOnEach:
    """ "Put a +1/+1 counter on each creature you control." """
    count: int
    counter: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line:
                game.put_counters(permanent, self.counter, game.amount(self.count))


@dataclass(frozen=True)
class PutCountersOnSource:
    """ "Whenever this creature attacks, put a +1/+1 counter on it." """
    count: int
    counter: str
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))


_COUNTER = r"([+\-\u2212]1/[+\-\u2212]1) counters?"


def _counter_name(text: str) -> str:
    return text.replace("\u2212", "-")


_ENTERS_WITH = re.compile(rf"{_SELF} enters with {_N} {_COUNTER} on it\.", re.I)
_IF_KICKED = re.compile(rf"if {_SELF} was kicked, ", re.I)
_ENTERS_PER_KICK = re.compile(rf"{_SELF} enters with an? {_COUNTER} on it for each time it was kicked\.", re.I)


def enters_with_counters(card: Card, kicked: int = 0) -> dict[str, int | str]:
    """Counters from "This creature enters with N (or X) +1/+1 counters on it.", plus, when `kicked` (the number
    of times), "If this creature was kicked, it enters with N +1/+1 counters on it." and multikicker's
    "... enters with a +1/+1 counter on it for each time it was kicked." """
    counters: dict[str, int | str] = {}
    for line in rules_lines(card):
        if kicked and (k := _IF_KICKED.match(line)):
            line = line[k.end():]
        if m := _ENTERS_WITH.fullmatch(line):
            name, count = _counter_name(m[2]), _count(m[1])
            counters[name] = count if count == "X" else counters.get(name, 0) + count
        elif kicked and (m := _ENTERS_PER_KICK.fullmatch(line)):
            name = _counter_name(m[1])
            counters[name] = counters.get(name, 0) + kicked
    return counters


def is_enters_with_counters(line: str) -> bool:
    if k := _IF_KICKED.match(line):
        line = line[k.end():]
    return _ENTERS_WITH.fullmatch(line) is not None or _ENTERS_PER_KICK.fullmatch(line) is not None


def _signed(text: str) -> int:
    return int(text.replace("\u2212", "-"))


_COLOR_NAMES = "white|blue|black|red|green"
_COLOR_LETTER = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
_PROT = (rf"protection from (?:{_COLOR_NAMES})(?:(?:, and |, | and )(?:from )?(?:{_COLOR_NAMES}))*")
PROTECTION = re.compile(_PROT, re.I)  # "protection from red", "protection from red and from blue"
_KW = rf"(?:{_PROT}|[a-z]+(?: [a-z]+)?)"  # one keyword


def _protection_keywords(text: str) -> frozenset[str]:
    """ "protection from red and from blue" -> {"protection from red", "protection from blue"}"""
    return frozenset(f"protection from {color.lower()}"
                     for m in PROTECTION.finditer(text) for color in re.findall(_COLOR_NAMES, m[0], re.I))


def _keyword_list(text: str) -> frozenset[str]:
    """ "flying", "flying and vigilance", "flying, vigilance, and trample" -> {"flying", ...}; a protection
    clause becomes one keyword per color ("protection from red")."""
    rest = PROTECTION.sub("", text)
    return _protection_keywords(text) | frozenset(w.strip().lower() for w in re.split(r",? and |, ", rest) if w.strip())


@lru_cache(maxsize=None)
def printed_protection(card: Card) -> frozenset[str]:
    """The colors (as letters) a card has protection from by its own keyword line, such as
    "Flying, protection from red and from blue". An ability that gives protection to something
    else ("Equipped creature has protection from red") doesn't count."""
    letters: set[str] = set()
    for line in rules_lines(card):
        if PROTECTION.search(line) and re.fullmatch(rf"{_KW}(?:, {_KW})*", line, re.I):
            letters.update(_COLOR_LETTER[kw.rsplit(" ", 1)[1]] for kw in _protection_keywords(line))
    return frozenset(letters)


_WARD = re.compile(r"(?:^|, )ward ((?:\{\d+\}|\{[WUBRGC]\})+)(?:,|$)", re.I)


def ward_cost(card: Card) -> str | None:
    """The mana cost of "Ward {2}" (other ward costs, like paying life, aren't supported), or None."""
    return next((m[1] for line in rules_lines(card) if (m := _WARD.search(line))), None)


def is_ward_line(text: str) -> bool:
    return re.fullmatch(r"ward (?:\{\d+\}|\{[WUBRGC]\})+", text, re.I) is not None


@dataclass(frozen=True)
class Pump:
    """ "Target creature gets +3/+3 (and gains trample) until end of turn." """
    modifier: Modifier
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.modify_until_end_of_turn(target, self.modifier)


@dataclass(frozen=True)
class PumpSource:
    """ "This creature gets +1/+0 until end of turn." """
    modifier: Modifier
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.modify_until_end_of_turn(target, self.modifier)


@dataclass(frozen=True)
class PumpEach:
    """ "Creatures you control get +3/+3 and gain trample until end of turn." Affects only the
    creatures there when it resolves (CR 611.2c)."""
    modifier: Modifier

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line:
                game.modify_until_end_of_turn(permanent, self.modifier)


_PT = r"([+\-\u2212]\d+)/([+\-\u2212]\d+)"
_KEYWORDS = rf"({_KW}(?:(?:,? and |, ){_KW})*)"
# "gets +3/+3", "gets +2/+0 and gains trample", "gains flying" (one or both parts), then "until end of turn."
_CHANGE = rf"(?:gets? {_PT}(?: and gains? {_KEYWORDS})?|gains? {_KEYWORDS}) until end of turn\."


def _modifier(m: re.Match, first: int) -> Modifier:
    p, t, keywords_with_pt, keywords_only = m.group(first, first + 1, first + 2, first + 3)
    keywords = keywords_with_pt or keywords_only
    return Modifier(_signed(p) if p else 0, _signed(t) if t else 0, _keyword_list(keywords) if keywords else frozenset())


@dataclass(frozen=True)
class StaticBuff:
    """ "(Other) (Elf) creatures you control get +1/+1 (and have flying)." while its source is on the battlefield."""
    modifier: Modifier
    other: bool  # "Other ...": not the source itself
    subtype: str | None  # "Elf" in "Other Elf creatures you control"
    text: str
    self_only: bool = False  # "CARDNAME gets +1/+1 as long as ...": only the source itself
    condition: "Condition | None" = None  # "As long as you control an artifact, ...": applies only while it holds


_AFFECTED = r"(?:(Other) )?(?:([A-Z][\w'-]*) )?[Cc]reatures you control"
_STATIC = re.compile(rf"{_AFFECTED} (?:get {_PT}(?: and have {_KEYWORDS})?|have {_KEYWORDS})\.")


_SELF_STATIC = re.compile(rf"{_SELF} (?:gets {_PT}(?: and has {_KEYWORDS})?|has {_KEYWORDS})\.", re.I)
_AS_LONG_AS_FIRST = re.compile(r"As long as (.+?), (.+\.)")
_AS_LONG_AS_LAST = re.compile(r"(.+?) as long as (.+)\.")


def _conditional(line: str) -> tuple[str, str] | None:
    """Split "As long as X, Y." or "Y as long as X." into (Y with its full stop, X)."""
    if m := _AS_LONG_AS_FIRST.fullmatch(line):
        return m[2], m[1]
    if m := _AS_LONG_AS_LAST.fullmatch(line):
        return m[1] + ".", m[2]
    return None


@lru_cache(maxsize=None)
def static_abilities(card: Card) -> tuple[StaticBuff, ...]:
    buffs = []
    for line in rules_lines(card):
        sentence, condition = line, None
        if split := _conditional(line):
            sentence, text = split
            if (condition := _condition(text)) is None:
                continue
        if m := _STATIC.fullmatch(sentence):
            buffs.append(StaticBuff(_modifier(m, 3), m[1] is not None, m[2], line, condition=condition))
        elif condition and (m := _SELF_STATIC.fullmatch(sentence)):  # unconditional ones would just be printed text
            buffs.append(StaticBuff(_modifier(m, 1), False, None, line, self_only=True, condition=condition))
    return tuple(buffs)


@dataclass(frozen=True)
class Attach:
    """Equip: attach the Equipment that made this ability to the target creature."""
    target: str = "creature you control"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.resolving_source is not None:
            game.attach(game.resolving_source, target)


@dataclass(frozen=True)
class AttachAura:
    """The targeting of an Aura spell. The game attaches the Aura as it enters (Game._resolve)."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


_EQUIP = re.compile(r"Equip ((?:\{\d+\}|\{[WUBRGC]\})+)")
_ENCHANT = re.compile(r"Enchant ((?:land|creature|artifact|enchantment|planeswalker|permanent|nonland permanent)"
                      r"(?: an opponent controls| you control)?)", re.I)


def equip_cost(card: Card) -> str | None:
    """The mana cost from "Equip {2}", or None (other equip costs aren't supported)."""
    return next((m[1] for line in rules_lines(card) if (m := _EQUIP.fullmatch(line))), None)


def aura_kind(card: Card) -> str | None:
    """What an Aura enchants ("creature", "creature you control", "land", ...), or None if it isn't an Aura."""
    if "Aura" not in card.type_line:
        return None
    return next((m[1].lower() for line in rules_lines(card) if (m := _ENCHANT.fullmatch(line))), None)


_REPLACE_ANY_GRAVEYARD = "If a card or token would be put into a graveyard from anywhere, exile it instead."
_REPLACE_OPPONENT_GRAVEYARD = "If a card would be put into an opponent's graveyard from anywhere, exile it instead."
_DOUBLE_TOKENS = ("If an effect would create one or more tokens under your control, it creates twice that many of "
                  "those tokens instead.")
_DOUBLE_COUNTERS = ("If an effect would put one or more counters on a permanent you control, it puts twice that many "
                    "of those counters instead.")
_PLUS_ONE_COUNTERS = ("If one or more +1/+1 counters would be put on a creature you control, that many plus one "
                      "+1/+1 counters are put on it instead.")
_EXTRA_TRIGGER = re.compile(r"If (an artifact or creature|a permanent) entering the battlefield causes a triggered "
                            r"ability of a permanent you control to trigger, that ability triggers an additional time\.")


@dataclass(frozen=True)
class Replacements:
    """What a permanent's static replacement effects do (CR 614), as the game applies them."""
    graveyard: str | None = None  # "any": cards go to exile instead of a graveyard; "opponent": only an opponent's
    tokens: int = 1  # how many times as many tokens its controller creates
    counters: int = 1  # how many times as many counters go on its controller's permanents
    plus_one: int = 0  # extra +1/+1 counters on its controller's creatures
    extra_trigger: str | None = None  # "artifact or creature" or "permanent": those entering trigger abilities twice


@lru_cache(maxsize=None)
def replacement_effects(card: Card) -> Replacements:
    found: dict[str, Any] = {}
    for line in rules_lines(card):
        if line == _REPLACE_ANY_GRAVEYARD:
            found["graveyard"] = "any"
        elif line == _REPLACE_OPPONENT_GRAVEYARD:
            found.setdefault("graveyard", "opponent")
        elif line == _DOUBLE_TOKENS:
            found["tokens"] = found.get("tokens", 1) * 2
        elif line == _DOUBLE_COUNTERS:
            found["counters"] = found.get("counters", 1) * 2
        elif line == _PLUS_ONE_COUNTERS:
            found["plus_one"] = found.get("plus_one", 0) + 1
        elif m := _EXTRA_TRIGGER.fullmatch(line):
            found["extra_trigger"] = m[1].removeprefix("an ").removeprefix("a ")
    return Replacements(**found)


def is_replacement_line(line: str) -> bool:
    return (line in (_REPLACE_ANY_GRAVEYARD, _REPLACE_OPPONENT_GRAVEYARD, _DOUBLE_TOKENS, _DOUBLE_COUNTERS,
                     _PLUS_ONE_COUNTERS) or _EXTRA_TRIGGER.fullmatch(line) is not None)


_CLONE = re.compile(r"You may have CARDNAME enter(?: the battlefield)? as a copy of "
                    r"(?:any (creature|artifact|enchantment|land) on the battlefield|a (creature) you control)\.")


def clone_kind(card: Card) -> tuple[str, bool] | None:
    """For Clone: what the card may enter as a copy of ("creature") and whether it must be one you control."""
    for line in rules_lines(card):
        if m := _CLONE.fullmatch(line):
            return (m[1] or m[2]), m[2] is not None
    return None


def is_clone_line(line: str) -> bool:
    return _CLONE.fullmatch(line) is not None


def is_enchant_line(line: str) -> bool:
    return _ENCHANT.fullmatch(line) is not None


@dataclass(frozen=True)
class AttachedBuff:
    """ "Equipped creature gets +1/+1 and has haste." / "Enchanted creature can't attack or block." """
    modifier: Modifier
    text: str


_ATTACHED = re.compile(rf"(?:Equipped|Enchanted) creature (?:gets {_PT}(?: and has {_KEYWORDS})?|has {_KEYWORDS}"
                       r"|can't attack or block)\.")
CANT_ATTACK, CANT_BLOCK = "can't attack", "can't block"  # pseudo-keywords, so combat can ask has_keyword


@lru_cache(maxsize=None)
def attached_abilities(card: Card) -> tuple[AttachedBuff, ...]:
    buffs = []
    for line in rules_lines(card):
        if m := _ATTACHED.fullmatch(line):
            if "can't attack or block" in line:
                modifier = Modifier(keywords=frozenset({CANT_ATTACK, CANT_BLOCK}))
            else:
                modifier = _modifier(m, 1)
            buffs.append(AttachedBuff(modifier, line))
    return tuple(buffs)


@dataclass(frozen=True)
class CreateTokens:
    count: int
    token: Card

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        token = self.token
        if "X" in (token.power, token.toughness):  # "an X/X ... token": its size is fixed as it's created
            token = dataclasses.replace(token, power=str(game.amount(token.power)),
                                        toughness=str(game.amount(token.toughness)))
        game.create_tokens(controller, token, game.amount(self.count))


@dataclass(frozen=True)
class CopyToken:
    """ "Create a token that's a copy of target creature you control." """
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            card = target.card
            if not card.type_line.startswith("Token"):
                card = dataclasses.replace(card, type_line="Token " + card.type_line)
            game.create_tokens(controller, card, 1)


POPULATE_PROMPT = "Populate: copy which token? "


@dataclass(frozen=True)
class Populate:
    """ "Populate": create a copy of a creature token you control (you choose which). """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        kinds = []
        for permanent in controller.battlefield:
            if permanent.card.type_line.startswith("Token") and "Creature" in permanent.card.type_line \
                    and permanent.card not in kinds:
                kinds.append(permanent.card)
        if kinds:
            pick = 0 if len(kinds) == 1 else controller.player.choose(
                POPULATE_PROMPT, [f"{c.name} {c.power}/{c.toughness}" for c in kinds])
            game.create_tokens(controller, kinds[pick], 1)


@dataclass(frozen=True)
class TargetControllerCreatesTokens:
    """Beast Within: "Its controller creates a 3/3 green Beast creature token." """
    count: int
    token: Card
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.create_tokens(target.last_controller, self.token, game.amount(self.count))


TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure",
                oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")
CLUE = Card(name="Clue", type_line="Token Artifact — Clue", oracle_text="{2}, Sacrifice this artifact: Draw a card.")
FOOD = Card(name="Food", type_line="Token Artifact — Food",
            oracle_text="{2}, {T}, Sacrifice this artifact: You gain 3 life.")
_NAMED_TOKENS = {"treasure": TREASURE, "clue": CLUE, "food": FOOD}
_COLOR_WORDS = {"white": "W", "blue": "U", "black": "B", "red": "R", "green": "G"}
_COLOR = r"(?:white|blue|black|red|green)"
_CREATURE_TOKEN = re.compile(
    rf"{_N} (\d+|X)/(\d+|X) (colorless|{_COLOR}(?:(?:,? and |, ){_COLOR})*) ((?:[A-Z][\w'-]* )+)(artifact )?"
    r"creature tokens?(?: with (?:([a-z ,]+?)(?:,? and |, |$))?(?:\"(.+)\")?)?"  # keywords and/or a quoted ability
)
_NAMED_TOKEN = re.compile(rf"(?i:{_N}) (Treasure|Clue|Food) tokens?")


def _token(spec: str) -> tuple[int, Card] | None:
    """Parse "a 1/1 white Soldier creature token with flying" or "two Treasure tokens"."""
    if m := _NAMED_TOKEN.fullmatch(spec):
        return _count(m[1]), _NAMED_TOKENS[m[2].lower()]
    m = _CREATURE_TOKEN.fullmatch(spec)
    if not m:
        return None
    count, power, toughness, colors, subtypes, artifact, keywords, quoted = m.groups()
    keyword_line = ""
    if keywords:
        words = [w.strip() for w in re.split(r",? and |, ", keywords) if w.strip()]
        keyword_line = ", ".join(words).capitalize()
    card = Card(
        name=subtypes.strip(),
        type_line=f"Token {'Artifact ' if artifact else ''}Creature — {subtypes.strip()}",
        oracle_text="\n".join(line for line in (keyword_line, quoted) if line),
        colors=tuple(_COLOR_WORDS[c] for c in re.findall(_COLOR, colors)),
        power=power,
        toughness=toughness,
    )
    if quoted and not _is_ability(card, quoted):
        return None  # a token ability we can't play: don't create a half-working token
    return _count(count), card


def _is_ability(card: Card, line: str) -> bool:
    """Whether `line` of `card`'s rules text is an ability we understand."""
    known = {a.text for a in (*triggered_abilities(card), *activated_abilities(card), *static_abilities(card))}
    return line in known or is_mana_ability(line)


def _create(m: re.Match, follows: bool) -> Any:
    parsed = _token(m[1] + '."' if m[2] else m[1])  # a quoted ability's own full stop comes before its closing quote
    if parsed is None:
        return None
    return (TargetControllerCreatesTokens if follows else CreateTokens)(*parsed)


@dataclass(frozen=True)
class MassFilter:
    """Which of the permanents of an "all"/"each" effect are affected: "with flying", "without flying",
    "with power 4 or greater", "nonblack"."""
    keyword: str | None = None
    keyword_wanted: bool = True  # False: "without flying"
    stat: str | None = None  # "power" or "toughness"
    at_least: int | None = None  # "with power 4 or greater"
    at_most: int | None = None  # "with toughness 2 or less"
    color: str | None = None  # a color letter
    other_color: bool = False  # "nonblack": every one that isn't that color


@dataclass(frozen=True)
class DestroyAll:
    """ "Destroy all creatures." Indestructible permanents survive; they all die together."""
    kind: str  # "creature", "artifact or enchantment", "creature you don't control", ...
    restriction: MassFilter | None = None  # "... with flying"
    no_regen: bool = False  # "They can't be regenerated."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.destroy_all(game.mass_targets(self.kind, controller, self.restriction), self.no_regen)


@dataclass(frozen=True)
class ExileAll:
    kind: str
    restriction: MassFilter | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_all(game.mass_targets(self.kind, controller, self.restriction))


@dataclass(frozen=True)
class CannotRegenerate:
    """ "They can't be regenerated." After a destroy effect it is folded into that effect (see _merge_no_regen);
    anywhere else there is nothing for it to stop."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class Regenerate:
    """ "Regenerate target creature." Gives it a shield: the next time it would be destroyed this turn, it is
    tapped, loses its damage and leaves combat instead."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.regenerate(target)


@dataclass(frozen=True)
class RegenerateSource:
    """ "{B}: Regenerate CARDNAME." """
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.regenerate(target)


@dataclass(frozen=True)
class RegenerateEach:
    """ "Regenerate each creature you control." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line:
                game.regenerate(permanent)


@dataclass(frozen=True)
class DamageEach:
    """ "This spell deals 2 damage to each creature (and each player)." Nothing is targeted."""
    amount: int | str
    creatures: str | None  # None, "all", or "opponents" (only creatures you don't control)
    players: str | None  # None, "opponents" or "all"
    restriction: MassFilter | None = None  # "each creature with flying"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        amount = game.amount(self.amount)
        if self.creatures:
            kind = "creature" if self.creatures == "all" else "creature you don't control"
            for permanent in game.mass_targets(kind, controller, self.restriction):
                game.damage(permanent, amount)
        if self.players:
            for seat in (game.live_seats() if self.players == "all" else game.opponents(controller)):
                game.damage(seat, amount)


@dataclass(frozen=True)
class Amount:
    """A number that depends on the game, worked out when the effect resolves: "its power",
    "the number of Auras you control", "the amount of life you gained this turn", ..."""
    kind: str  # see Game.evaluate
    what: str = ""  # a type ("Aura"), a counter ("+1/+1") or a spell kind ("instant or sorcery spell")


_AMOUNTS = [
    (re.compile(r"(?:its|this creature's|CARDNAME's) power", re.I), lambda m: Amount("source_power")),
    (re.compile(r"(?:the number of )?\+1/\+1 counters? on (?:it|this creature|CARDNAME)", re.I),
     lambda m: Amount("source_counters", "+1/+1")),
    (re.compile(r"(?:the number of )?creatures? on the battlefield", re.I), lambda m: Amount("on_battlefield", "creature")),
    (re.compile(r"the amount of life you gained this turn", re.I), lambda m: Amount("life_gained")),
    (re.compile(r"half your life total, rounded (down|up)", re.I), lambda m: Amount("half_life", m[1].lower())),
    (re.compile(r"(?:the number of )?spells? you've cast this turn", re.I), lambda m: Amount("spells_cast")),
    (re.compile(r"the greatest mana value among instant and sorcery spells you've cast this turn", re.I),
     lambda m: Amount("greatest_mana_value_cast", "instant or sorcery spell")),
    (re.compile(r"opponents?", re.I), lambda m: Amount("opponents")),
    (re.compile(r"(?:the number of )?([A-Za-z]+) you control", re.I), lambda m: Amount("you_control", _singular(m[1]))),
]


def _amount(text: str) -> Amount | None:
    for pattern, build in _AMOUNTS:
        if m := pattern.fullmatch(text):
            return build(m)
    return None


@dataclass(frozen=True)
class DefineX:
    """Sets X for the effects after it ("..., where X is the number of Auras you control.")."""
    amount: Amount

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.x_value = game.evaluate(self.amount, controller)


@dataclass(frozen=True)
class SacrificeCreature:
    """ "Sacrifice a creature." (you choose which) """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.sacrifice(controller)


@dataclass(frozen=True)
class EachSacrifices:
    """ "Each opponent sacrifices a creature." / "Each player sacrifices a land." """
    who: str  # "opponent" or "player"
    kind: str = "creature"  # "creature", "artifact", "enchantment", "land" or "permanent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "player" or seat is not controller:
                game.sacrifice(seat, self.kind)


@dataclass(frozen=True)
class TargetSacrifices:
    """ "Target player sacrifices a creature." (target is "player" or "opponent") """
    target: str
    kind: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.sacrifice(target, self.kind)


_MASS_KINDS = {"creatures": "creature", "artifacts": "artifact", "enchantments": "enchantment",
               "planeswalkers": "planeswalker", "lands": "land", "nonland permanents": "nonland permanent",
               "artifacts and enchantments": "artifact or enchantment",
               "creatures and planeswalkers": "creature or planeswalker"}
_MASS = (r"(artifacts and enchantments|creatures and planeswalkers|nonland permanents|creatures|artifacts"
         r"|enchantments|planeswalkers|lands)( you don't control| you control| an opponent controls)?")


def _mass_kind(m: re.Match) -> str:
    return _MASS_KINDS[m[1].lower()] + (m[2] or "")


_SACRIFICE_KIND = r"(creature|artifact|enchantment|land|permanent)"
_FIGHTER = r"(creature(?: you control| you don't control| an opponent controls)?)"
_MASS_KEYWORDS = (r"(?:flying|reach|trample|haste|vigilance|menace|deathtouch|lifelink|first strike|double strike"
                  r"|defender|indestructible|hexproof)")
_RESTRICTION = rf"(with (?:power|toughness) \d+ or (?:greater|less)|with {_MASS_KEYWORDS}|without {_MASS_KEYWORDS})"
_COLOR_ADJECTIVE = r"(?:(non)?(white|blue|black|red|green) )?"
_STAT_RESTRICTION = re.compile(r"with (power|toughness) (\d+) or (greater|less)")


# The same, with an optional color adjective before and "with flying" etc. after (destroy and exile only).
_MASS_NOUN = (r"(artifacts and enchantments|creatures and planeswalkers|nonland permanents|creatures|artifacts"
              r"|enchantments|planeswalkers|lands)")
_MASS_FILTERED = rf"{_COLOR_ADJECTIVE}{_MASS_NOUN}(?: {_RESTRICTION})?( you don't control| you control| an opponent controls)?"


def _mass_effect(cls: type, m: re.Match) -> Any:
    kind = _MASS_KINDS[m[3].lower()] + (m[5] or "")
    return cls(kind, _mass_filter(m[1], m[2], m[4]))




def _mass_filter(non: str | None, color: str | None, restriction: str | None) -> MassFilter | None:
    """The filter for an optional color adjective ("nonblack") and an optional "with ..." / "without ..." phrase."""
    fields: dict[str, Any] = {}
    if color:
        fields.update(color=_COLOR_WORDS[color.lower()], other_color=bool(non))
    if restriction:
        if m := _STAT_RESTRICTION.fullmatch(restriction.lower()):
            fields.update(stat=m[1], **{"at_least" if m[3] == "greater" else "at_most": int(m[2])})
        else:
            fields.update(keyword=restriction.lower().split(" ", 1)[1], keyword_wanted=restriction.lower().startswith("with "))
    return MassFilter(**fields) if fields else None


def _damage_each(m: re.Match) -> DamageEach | None:
    creatures = players = None
    if m[3] and not m[2].lower().startswith("creature"):
        return None  # "each opponent with flying" isn't a thing
    for part in (m[2].lower(), (m[4] or "").lower()):
        if part == "creature":
            creatures = "all"
        elif part == "creature you don't control":
            creatures = "opponents"
        elif part:
            players = "all" if part == "player" else "opponents"
    return DamageEach(_count(m[1]), creatures, players, _mass_filter(None, None, m[3]))


@dataclass(frozen=True)
class ReturnToHand:
    """Bounce: "Return target nonland permanent you don't control to its owner's hand." """
    target: str
    another: bool = False  # "Return another target creature ...": not the source itself
    optional_target: bool = False  # "Return up to one target creature ...": the target may be left out

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_to_hand(target)


@dataclass(frozen=True)
class ReturnAllToHand:
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_all_to_hand(game.mass_targets(self.kind, controller))


@dataclass(frozen=True)
class ReturnFromGraveyard:
    """ "Return target creature card from your graveyard to your hand / to the battlefield." """
    target: str  # "graveyard:<card type>:<yours|any>"
    to: str  # "hand" or "battlefield"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.return_from_graveyard(target, controller, self.to)


@dataclass(frozen=True)
class LoseLifeEqualToManaValue:
    """Reanimate: "You lose life equal to its mana value." (the card the previous effect put onto the battlefield)"""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(controller, -int(target.card.cmc))


@dataclass(frozen=True)
class ExileFromGraveyard:
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.exile_from_graveyard(target)


@dataclass(frozen=True)
class SearchLibrary:
    """ "Search your library for a creature card, put it into your hand, then shuffle." """
    card_type: str  # "card", "creature", "instant or sorcery", "basic land", ...
    to: str  # "hand", or "top" of the library after shuffling
    reveal: bool  # "reveal it": everyone sees which card

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tutor(controller, self.card_type, self.to, self.reveal)


@dataclass(frozen=True)
class LoseLife:
    amount: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.change_life(controller, -game.amount(self.amount))


@dataclass(frozen=True)
class SearchForLands:
    """Land ramp: "Search your library for up to two basic land cards, reveal those cards, put one onto
    the battlefield tapped and the other into your hand, then shuffle." (Cultivate)"""
    count: int  # up to this many
    subtypes: tuple[str, ...]  # () means basic lands; otherwise lands with one of these land types
    battlefield: int  # how many go onto the battlefield (the rest go to the hand)
    tapped: bool
    reveal: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.search_for_lands(controller, self.count, self.subtypes, self.battlefield, self.tapped, self.reveal)


RETURN_LAND_PROMPT = "Return which land to your hand? "


@dataclass(frozen=True)
class ReturnOwnLand:
    """Bounceland: "Return a land you control to its owner's hand." (you choose; it can be the land itself)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        lands = [p for p in controller.battlefield if "Land" in p.card.type_line]
        if lands:
            game.return_to_hand(lands[controller.player.choose(RETURN_LAND_PROMPT, [game.label(p) for p in lands])])


@dataclass(frozen=True)
class Scry:
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.scry(controller, game.amount(self.count))


@dataclass(frozen=True)
class AddMana:
    """Ritual: "Add {B}{B}{B}." The mana waits in its controller's pool until the step ends."""
    units: tuple[frozenset[str], ...]

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.add_mana(controller, self.units)


@dataclass(frozen=True)
class ExileAllGraveyards:
    """ "Exile all cards from all graveyards." (Rest in Peace) """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_all_graveyards()


@dataclass(frozen=True)
class CopySpell:
    """ "Copy target instant or sorcery spell. You may choose new targets for the copy." """
    target: str  # "instant or sorcery spell", optionally "... you control"
    new_targets: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.copy_spell(target, controller, self.new_targets)


@dataclass(frozen=True)
class NewTargets:
    """ "You may choose new targets for the copy." Only meaningful after a copy effect (_merge_copy folds it in)."""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class GainControl:
    """ "Gain control of target creature (until end of turn). (Untap that creature. It gains haste until end of
    turn.)" """
    target: str
    until_end_of_turn: bool = False
    untap: bool = False
    haste: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.gain_control(target, controller, until_eot=self.until_end_of_turn, untap=self.untap, haste=self.haste)


@dataclass(frozen=True)
class UntapThat:
    """ "Untap that creature." Only meaningful right after "Gain control of ...": _merge_control folds it in."""
    follows_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


_CONTROL_AURA = "You control enchanted creature."


def aura_controls(card: Card) -> bool:
    """Control Magic: an Aura that gives its controller control of the enchanted creature."""
    return "Aura" in card.type_line and _CONTROL_AURA in rules_lines(card)


def is_control_aura_line(line: str) -> bool:
    return line == _CONTROL_AURA


@dataclass(frozen=True)
class BecomeCreature:
    """Crewing a Vehicle: until end of turn it is an artifact creature."""
    uses_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.become_creature(target)


@dataclass(frozen=True)
class Proliferate:
    """ "Proliferate.": choose any permanents with counters; each gets one more counter of each kind it has."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.proliferate(controller)


@dataclass(frozen=True)
class FightFirst:
    """The first target of a fight ("Target creature you control ... fights ..."): remembered for the second."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = target


@dataclass(frozen=True)
class Fight:
    """The second target of a fight. Each deals damage equal to its power to the other; with `one_sided` only the
    first does ("Target creature you control deals damage equal to its power to target creature you don't control")."""
    target: str
    one_sided: bool = False
    another: bool = False  # "fights another target creature": not the first target

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        first = game.resolving_item.carried if game.resolving_item is not None else None
        if first is not None and target is not None and first is not target:
            game.fight(first, target, self.one_sided)


@dataclass(frozen=True)
class ReturnWithCounter:
    """Persist and undying: the creature that died comes back with a counter on it."""
    counter: str  # "-1/-1" (persist) or "+1/+1" (undying)
    uses_dead_source = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.return_with_counter(target, self.counter)


@dataclass(frozen=True)
class ExtraTurn:
    """ "Take an extra turn after this one." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.extra_turns.append(controller.index)


@dataclass(frozen=True)
class TargetExtraTurn:
    """ "Target player takes an extra turn after this one." """
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.extra_turns.append(target.index)


@dataclass(frozen=True)
class ExtraCombat:
    """ "After this phase, there is an additional combat phase (followed by an additional main phase)." """
    main: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.add_combat(self.main)


@dataclass(frozen=True)
class UntapCreatures:
    which: str  # "attacked": the creatures that attacked this turn; "yours": every creature you control

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in controller.battlefield:
            if "Creature" in permanent.card.type_line and (self.which == "yours" or permanent.attacked_turn == game.turn):
                permanent.tapped = False


@dataclass(frozen=True)
class BecomeMonarch:
    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.become_monarch(controller)


@dataclass(frozen=True)
class VoteStart:
    """ "Starting with you, each player votes for X or Y." (options), or for a nonland permanent (None). Only ever a
    step of a Vote or VoteToExile (see _merge_votes)."""
    options: tuple[str, str] | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone vote is never built")


@dataclass(frozen=True)
class VoteOutcome:
    """ "For each X vote, ..." (each) or "If X gets more votes [or the vote is tied], ..." (more): what happens."""
    kind: str  # "each" or "more"
    option: str
    effects: tuple
    tie: bool = False  # "or the vote is tied"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone vote outcome is never built")


@dataclass(frozen=True)
class ExileMostVoted:
    """ "Exile each permanent with the most votes or tied for most votes." Only ever the end of a permanent vote."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone exile of the most voted is never built")


@dataclass(frozen=True)
class Vote:
    """Each player votes for one of two words; the outcomes follow the votes (the effects need no target)."""
    options: tuple[str, str]
    outcomes: tuple[VoteOutcome, ...]

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        counts = dict(zip(self.options, game.vote(controller, list(self.options))))
        for outcome in self.outcomes:
            if outcome.kind == "each":
                times = counts[outcome.option]
            else:
                other = next(o for o in self.options if o != outcome.option)
                times = int(counts[outcome.option] > counts[other]
                            or (outcome.tie and counts[outcome.option] == counts[other]))
            for _ in range(times):
                for effect in outcome.effects:
                    effect.resolve(game, controller, None)


@dataclass(frozen=True)
class VoteToExile:
    """Council's Judgment."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.vote_to_exile(controller)


@dataclass(frozen=True)
class TakeInitiative:
    """ "You take the initiative." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.take_initiative(controller)


@dataclass(frozen=True)
class ThroneOfTheDeadThree:
    """The last room of the Undercity; the engine puts it on the stack itself."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.throne_of_the_dead_three(controller)


@dataclass(frozen=True)
class Goad:
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.goad(target, controller)


@dataclass(frozen=True)
class GoadAll:
    """ "Goad all creatures you don't control." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            for permanent in list(seat.battlefield):
                if "Creature" in permanent.card.type_line:
                    game.goad(permanent, controller)


@dataclass(frozen=True)
class UnlessPays:
    """ "Draw a card unless that player pays {1}": the effects happen unless the player who set the trigger off pays.
    Only for effects that need no target, so they run the same either way."""
    effects: tuple
    cost: str
    uses_player = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.pays_unless(target, self.cost, game.resolving_item.card):
            return
        for effect in self.effects:
            effect.resolve(game, controller, None)


@dataclass(frozen=True)
class LookAtTop:
    """ "Look at the top five cards of your library." Only ever a step of an Impulse (see _merge_impulse)."""
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone look at the top of the library is never built")


@dataclass(frozen=True)
class TakeFromTop:
    """The sentence after a look: "Put one of them into your hand and the rest on the bottom of your library in any
    order." (card_type None) or "You may reveal a creature card from among them and put it into your hand." """
    card_type: str | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone take from the top is never built")


@dataclass(frozen=True)
class RestOnBottom:
    """ "Put the rest on the bottom of your library in a random order." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        raise NotImplementedError("a lone put-the-rest is never built")


@dataclass(frozen=True)
class Impulse:
    """Look at the top cards, take one, put the rest on the bottom."""
    count: int | str
    card_type: str | None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.look_at_top(controller, game.amount(self.count), self.card_type)


@dataclass(frozen=True)
class Surveil:
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.surveil(controller, game.amount(self.count))


@dataclass(frozen=True)
class Mill:
    """ "Mill three cards." / "Each opponent mills three cards." / "Each player mills three cards." """
    count: int | str
    who: str  # "you", "each opponent" or "each player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "each player" or (self.who == "you") == (seat is controller):
                game.mill(seat, game.amount(self.count))


@dataclass(frozen=True)
class TargetMill:
    """ "Target player (or opponent) mills three cards." """
    count: int | str
    target: str  # "player" or "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.mill(target, game.amount(self.count))


@dataclass(frozen=True)
class EntersTapped:
    """How a permanent (usually a land) may enter tapped. `kind` is one of: "always",
    "unless_land_types" (checklands), "unless_lands_at_most" (fastlands), "unless_lands_at_least"
    (slowlands), "unless_opponents" (bond lands), "shock" (pay life or it enters tapped)."""
    kind: str
    types: tuple[str, ...] = ()
    count: int = 0
    life: int = 0


_LAND_TYPE = r"(?:Plains|Island|Swamp|Mountain|Forest)"
_ENTERS_TAPPED = [
    (re.compile(rf"{_SELF} enters tapped\.", re.I), lambda m: EntersTapped("always")),
    (re.compile(rf"{_SELF} enters tapped unless you control an? ({_LAND_TYPE}) or an? ({_LAND_TYPE})\.", re.I),
     lambda m: EntersTapped("unless_land_types", types=(m[1].capitalize(), m[2].capitalize()))),
    (re.compile(rf"{_SELF} enters tapped unless you control {_N} or (fewer|more) other lands\.", re.I),
     lambda m: EntersTapped("unless_lands_at_most" if m[2].lower() == "fewer" else "unless_lands_at_least",
                            count=_count(m[1]))),
    (re.compile(rf"{_SELF} enters tapped unless you have {_N} or more opponents\.", re.I),
     lambda m: EntersTapped("unless_opponents", count=_count(m[1]))),
    (re.compile(rf"As {_SELF} enters, you may pay {_N} life\. If you don't, it enters tapped\.", re.I),
     lambda m: EntersTapped("shock", life=_count(m[1]))),
]


def enters_tapped_rule(card: Card) -> EntersTapped | None:
    for line in rules_lines(card):
        for pattern, build in _ENTERS_TAPPED:
            if m := pattern.fullmatch(line):
                return build(m)
    return None


def is_enters_tapped_line(line: str) -> bool:
    return any(pattern.fullmatch(line) for pattern, _ in _ENTERS_TAPPED)


_CYCLING = re.compile(r"(Cycling|Basic landcycling|(?:Plains|Island|Swamp|Mountain|Forest)cycling) "
                      r"((?:\{\d+\}|\{[WUBRGC]\})+)")
_CYCLING_LAND_TYPES = {"plainscycling": "Plains", "islandcycling": "Island", "swampcycling": "Swamp",
                       "mountaincycling": "Mountain", "forestcycling": "Forest"}


def cycling(card: Card) -> tuple[str, str, tuple] | None:
    """A card's cycling: (its name, like "Forestcycling", the mana cost, what the ability does when it resolves).
    Plain cycling draws a card; basic landcycling and Forestcycling-style abilities fetch a land to your hand."""
    for line in rules_lines(card):
        if m := _CYCLING.fullmatch(line):
            word = m[1]
            if word == "Cycling":
                effects: tuple = (Draw(1),)
            elif word == "Basic landcycling":
                effects = (SearchForLands(1, (), 0, False, True),)
            else:
                effects = (SearchForLands(1, (_CYCLING_LAND_TYPES[word.lower()],), 0, False, True),)
            return word, m[2], effects
    return None


def cycling_cost(card: Card) -> str | None:
    """The mana cost from "Cycling {2}" or "Forestcycling {1}" (only mana costs are supported), or None."""
    found = cycling(card)
    return found[1] if found else None


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


@dataclass(frozen=True)
class AdditionalCost:
    """"As an additional cost to cast this spell, ..." (CR 601.2b)."""
    sacrifice: str | None = None  # the kind of permanent: "creature", "artifact or creature", ...
    discard: bool = False
    life: int = 0


_KICKER = re.compile(r"(?:Multik|K)icker ((?:\{\d+\}|\{[WUBRGC]\})+)")
_FREE_WITH_COMMANDER = re.compile(r"If you control a commander, you may cast this spell without paying its mana cost\.")
_PITCH = re.compile(rf"(If it's not your turn, )?(?i:you) may (?:pay {_N} life and )?exile an? ({_COLOR_NAMES}) card "
                    r"from your hand rather than pay this spell's mana cost\.")
_ADDITIONAL = re.compile(rf"As an additional cost to cast this spell, (?:sacrifice an? (creature|artifact|land|artifact or "
                         rf"creature|permanent)|(discard a card)|pay (?!X ){_N} life)\.")  # "pay X life" (Toxic Deluge) isn't supported
_FLASHBACK = re.compile(r"Flashback ((?:\{[^}]+\})+)")
_ESCAPE = re.compile(r"Escape\u2014((?:\{[^}]+\})+), Exile (a|one|two|three|four|five|six) other cards? from your graveyard\.")
_REDUCTION = re.compile(rf"(?:({_COLOR_NAMES}|creature|artifact|enchantment|noncreature|instant and sorcery) )?spells "
                        r"you cast cost \{(\d+)\} less to cast\.", re.I)


def kicker_cost(card: Card) -> str | None:
    """The mana cost from "Kicker {1}{U}" or "Multikicker {1}{G}" (only mana costs are supported), or None."""
    return next((m[1] for line in rules_lines(card) if (m := _KICKER.fullmatch(line))), None)


def is_multikicker(card: Card) -> bool:
    """Multikicker: the kicker cost can be paid any number of times (CR 702.33c)."""
    return any(line.startswith("Multikicker ") and _KICKER.fullmatch(line) for line in rules_lines(card))


def alternative_costs(card: Card) -> list[AlternativeCost]:
    costs = []
    for line in rules_lines(card):
        if _FREE_WITH_COMMANDER.fullmatch(line):
            costs.append(AlternativeCost("Cast without paying its mana cost", commander=True))
        elif m := _PITCH.fullmatch(line):
            life = _count(m[2]) if m[2] else 0
            text = f"Pay {life} life and exile a {m[3]} card" if life else f"Exile a {m[3]} card"
            costs.append(AlternativeCost(text, not_your_turn=bool(m[1]), life=life, exile_color=_COLOR_LETTER[m[3]]))
    return costs


@dataclass(frozen=True)
class GraveyardCast:
    """A way to cast a card from the graveyard: Flashback (then it is exiled) or Escape (exile other cards too)."""
    word: str  # "Flashback" or "Escape"
    cost: str  # the mana cost to pay instead of the card's own
    exile: int = 0  # other cards to exile from the graveyard (Escape)
    exile_after: bool = False  # exile it instead of putting it in the graveyard when it leaves the stack (Flashback)


def graveyard_casts(card: Card) -> list[GraveyardCast]:
    found = []
    for line in rules_lines(card):
        if m := _FLASHBACK.fullmatch(line):
            found.append(GraveyardCast("Flashback", m[1], exile_after=True))
        elif m := _ESCAPE.fullmatch(line):
            found.append(GraveyardCast("Escape", m[1], exile=_count(m[2])))
    return found


def additional_costs(card: Card) -> list[AdditionalCost]:
    costs = []
    for line in rules_lines(card):
        if m := _ADDITIONAL.fullmatch(line):
            costs.append(AdditionalCost(sacrifice=m[1], discard=bool(m[2]), life=_count(m[3]) if m[3] else 0))
    return costs


def cost_reductions(card: Card) -> list[tuple[str, int]]:
    """Static "Green spells you cast cost {1} less to cast." abilities (Medallions): (what kind of spell, how much).
    The kind is a color letter, a card type ("creature", "noncreature", "instant and sorcery") or "spell"."""
    found = []
    for line in rules_lines(card):
        if m := _REDUCTION.fullmatch(line):
            kind = (m[1] or "spell").lower()
            found.append((_COLOR_LETTER.get(kind, kind), int(m[2])))
    return found


def is_casting_cost_line(line: str) -> bool:
    """Kicker, alternative and additional costs: rules for casting the spell rather than what it does."""
    return any(p.fullmatch(line) for p in (_KICKER, _FREE_WITH_COMMANDER, _PITCH, _ADDITIONAL, _FLASHBACK, _ESCAPE))


def is_cost_reduction_line(line: str) -> bool:
    return _REDUCTION.fullmatch(line) is not None


@dataclass(frozen=True)
class IfKicked:
    """"If this spell was kicked, draw a card.": the effect happens only if the kicker cost was paid."""
    effect: Any

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None and game.resolving_item.kicked:
            self.effect.resolve(game, controller, target)


def _kicked(m: re.Match) -> IfKicked | None:
    effects = _parse([m[1][:1].upper() + m[1][1:]])
    return IfKicked(effects[0]) if effects else None


def kicked_effects(effects: list | None, kicked: int) -> list | None:
    """A spell's effects once it's known whether it was kicked: "If this spell was kicked, ..." effects
    become plain effects, or are dropped. This happens before targets are chosen, so kicked effects can target."""
    if effects is None:
        return None
    return [e.effect if isinstance(e, IfKicked) else e for e in effects if kicked or not isinstance(e, IfKicked)]
_LAND_TYPES = rf"({_LAND_TYPE}(?:, {_LAND_TYPE})*(?:,? or {_LAND_TYPE})?)"


def _land_types(text: str) -> tuple[str, ...]:
    return tuple(t.capitalize() for t in re.findall(_LAND_TYPE, text, re.I))


_MANA_VALUE = r"(?: with mana value \d+(?: or less| or greater)?)?"
_CARD_TYPE = rf"((?:(?:creature|artifact|enchantment|land|permanent|instant or sorcery|instant|sorcery) )?card{_MANA_VALUE})"
_SEARCH_TYPE = (r"((?:(?:creature|land|artifact|enchantment|planeswalker|instant or sorcery|instant|sorcery"
                rf"|artifact or enchantment|basic land) )?card{_MANA_VALUE})")
_CARD_PHRASE = re.compile(r"(?:(.+?) )?card(?: with mana value (\d+)(?: (or less|or greater))?)?")


def _card_kind(phrase: str | None) -> str:
    """"creature card with mana value 3 or less" -> "creature|mv<=3"; "card" -> "card". The kind is what the
    game matches library and graveyard cards against."""
    m = _CARD_PHRASE.fullmatch((phrase or "card").lower())
    kind = m[1] or "card"
    if m[2]:
        kind += "|mv" + {"or less": "<=", "or greater": ">="}.get(m[3], "=") + m[2]
    return kind


def _graveyard_kind(phrase: str | None, whose: str) -> str:
    return f"graveyard:{_card_kind(phrase)}:{whose}"


@dataclass(frozen=True)
class FetchBasicLand:
    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fetch_basic_land(controller)


_PERMANENT_KIND = (r"((?:creature|artifact|enchantment|planeswalker|nonland permanent|permanent|artifact or enchantment"
                   r"|creature or planeswalker)(?: an opponent controls| you don't control| you control)?)")
_DAMAGE_KIND = r"(any target|target creature|target player|target creature or planeswalker|target player or planeswalker)"

_TEMPLATES: list[tuple[re.Pattern, Callable[[re.Match], Any]]] = [
    (re.compile(r"if this spell was kicked, (.+)", re.I), _kicked),
    (re.compile(rf"draw {_N} cards?\.", re.I), lambda m: Draw(_count(m[1]))),
    (re.compile(rf"you gain {_N} life\.", re.I), lambda m: GainLife(_count(m[1]))),
    (re.compile(rf"each opponent loses {_N} life\.", re.I), lambda m: OpponentsLoseLife(_count(m[1]))),
    (re.compile(rf"{_SELF} deals {_N} damage to {_DAMAGE_KIND}\.", re.I),
     lambda m: Damage(_count(m[1]), "any" if m[2].lower() == "any target" else m[2].lower().removeprefix("target "))),
    (re.compile(rf"destroy (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Destroy(m[2].lower(), bool(m[1]))),
    (re.compile(r"counter target ((?:noncreature|creature|instant or sorcery|artifact|enchantment) )?spell\.", re.I),
     lambda m: Counter(f"{m[1].lower()}spell" if m[1] else "spell")),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Exile(m[2].lower(), bool(m[1]))),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND} until {_SELF} leaves the battlefield\.", re.I),
     lambda m: ExileUntilLeaves(m[2].lower(), bool(m[1]))),
    (re.compile(rf"target (player|opponent) draws {_N} cards?\.", re.I), lambda m: TargetDraw(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) gains {_N} life\.", re.I), lambda m: TargetGainLife(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) loses {_N} life\.", re.I), lambda m: TargetLoseLife(_count(m[2]), m[1].lower())),
    (re.compile(rf"return (another |up to one )?target {_PERMANENT_KIND} to its owner's hand\.", re.I),
     lambda m: ReturnToHand(m[2].lower(), (m[1] or "").lower() == "another ", (m[1] or "").lower() == "up to one ")),
    (re.compile(rf"return all {_MASS} to their owners' hands\.", re.I), lambda m: ReturnAllToHand(_mass_kind(m))),
    (re.compile(rf"return target {_CARD_TYPE} from your graveyard to your hand\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours"), "hand")),
    (re.compile(rf"(?:return|put) target {_CARD_TYPE} from (your|a) graveyard (?:to|onto) the battlefield"
                r"(?: under your control)?\.", re.I),
     lambda m: ReturnFromGraveyard(_graveyard_kind(m[1], "yours" if m[2].lower() == "your" else "any"), "battlefield")),
    (re.compile(rf"exile target {_CARD_TYPE} from a graveyard\.", re.I),
     lambda m: ExileFromGraveyard(_graveyard_kind(m[1], "any"))),
    (re.compile(rf"search your library for an? {_SEARCH_TYPE}, (?:reveal it, )?(?:put (?:it|that card) into your hand, "
                r"then shuffle|then shuffle and put (?:it|that card|the card) on top(?: of your library)?)\.", re.I),
     lambda m: SearchLibrary(_card_kind(m[1]), "hand" if "into your hand" in m[0] else "top", "reveal it" in m[0].lower())),
    (re.compile(r"search your library for a land card, put it onto the battlefield( tapped)?, then shuffle\.", re.I),
     lambda m: SearchForLands(1, ("*",), 1, bool(m[1]), False)),
    (re.compile(r"you lose life equal to its mana value\.", re.I), lambda m: LoseLifeEqualToManaValue()),
    (re.compile(rf"you lose {_N} life\.", re.I), lambda m: LoseLife(_count(m[1]))),
    (re.compile(r"search your library for up to two basic land cards, reveal those cards, put one onto the battlefield "
                r"tapped and the other into your hand, then shuffle\.", re.I),
     lambda m: SearchForLands(2, (), 1, True, True)),
    (re.compile(r"search your library for up to (two|three|four) basic land cards, (?:reveal (?:them|those cards), )?"
                r"put (?:them|those cards) onto the battlefield tapped, then shuffle\.", re.I),
     lambda m: SearchForLands(_count(m[1]), (), _count(m[1]), True, False)),
    (re.compile(rf"search your library for an? {_LAND_TYPES} card, put (?:it|that card) onto the battlefield( tapped)?, "
                r"then shuffle\.", re.I),
     lambda m: SearchForLands(1, _land_types(m[1]), 1, bool(m[2]), False)),
    (re.compile(rf"scry {_N}\.", re.I), lambda m: Scry(_count(m[1]))),
    (re.compile(rf"surveil {_N}\.", re.I), lambda m: Surveil(_count(m[1]))),
    (re.compile(rf"look at the top (?:{_N} cards?|card) of your library\.", re.I),
     lambda m: LookAtTop(_count(m[1] or "one"))),
    (re.compile(r"put one of them into your hand and the rest on the bottom of your library in any order\.", re.I),
     lambda m: TakeFromTop(None)),
    (re.compile(rf"you may reveal an? {_SEARCH_TYPE} from among them and put it into your hand\.", re.I),
     lambda m: TakeFromTop(_card_kind(m[1]))),
    (re.compile(r"put the rest on the bottom of your library in (?:a random|any) order\.", re.I),
     lambda m: RestOnBottom()),
    (re.compile(r"return a land you control to its owner's hand\.", re.I), lambda m: ReturnOwnLand()),
    (re.compile(r"add ((?:\{[WUBRGC]\})+)\.", re.I),
     lambda m: AddMana(tuple(frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[1].upper())))),
    (re.compile(r"exile all cards from all graveyards\.", re.I), lambda m: ExileAllGraveyards()),
    (re.compile(r"copy target (instant or sorcery spell|instant spell|sorcery spell)( you control)?\.", re.I),
     lambda m: CopySpell(m[1].lower() + (m[2] or "").lower())),
    (re.compile(r"you may choose new targets for the copy\.", re.I), lambda m: NewTargets()),
    (re.compile(rf"gain control of target {_PERMANENT_KIND}( until end of turn)?\.", re.I),
     lambda m: GainControl(m[1].lower(), until_end_of_turn=bool(m[2]))),
    (re.compile(r"untap that creature\.", re.I), lambda m: UntapThat()),
    (re.compile(r"proliferate\.", re.I), lambda m: Proliferate()),
    (re.compile(rf"target {_FIGHTER} fights (another )?target {_FIGHTER}\.", re.I),
     lambda m: [FightFirst(m[1].lower()), Fight(m[3].lower(), another=bool(m[2]))]),
    (re.compile(rf"target {_FIGHTER} deals damage equal to its power to target {_FIGHTER}\.", re.I),
     lambda m: [FightFirst(m[1].lower()), Fight(m[2].lower(), one_sided=True)]),
    (re.compile(r"populate\.", re.I), lambda m: Populate()),
    (re.compile(rf"create a token that's a copy of target {_PERMANENT_KIND}\.", re.I), lambda m: CopyToken(m[1].lower())),
    (re.compile(r"take an extra turn after this one\.", re.I), lambda m: ExtraTurn()),
    (re.compile(r"you become the monarch\.", re.I), lambda m: BecomeMonarch()),
    (re.compile(r"investigate\.", re.I), lambda m: CreateTokens(1, CLUE)),
    (re.compile(rf"{_VOTE_PREFIX}starting with you, each player votes for (\w+) or (\w+)\.", re.I),
     lambda m: VoteStart((m[1].lower(), m[2].lower()))),
    (re.compile(rf"{_VOTE_PREFIX}starting with you, each player votes for a nonland permanent you don't control\.", re.I),
     lambda m: VoteStart(None)),
    (re.compile(r"exile each permanent with the most votes or tied for most votes\.", re.I),
     lambda m: ExileMostVoted()),
    (re.compile(r"for each (\w+) vote, (.+)\.", re.I), lambda m: _vote_outcome("each", m[1], m[2], False)),
    (re.compile(r"if (\w+) gets more votes( or the vote is tied)?, (.+)\.", re.I),
     lambda m: _vote_outcome("more", m[1], m[3], bool(m[2]))),
    (re.compile(r"you take the initiative\.", re.I), lambda m: TakeInitiative()),
    (re.compile(r"target player takes an extra turn after this one\.", re.I), lambda m: TargetExtraTurn()),
    (re.compile(r"after this (?:main )?phase, there is an additional combat phase( followed by an additional main phase)?\.",
                re.I), lambda m: ExtraCombat(bool(m[1]))),
    (re.compile(r"untap all creatures that attacked this turn\.", re.I), lambda m: UntapCreatures("attacked")),
    (re.compile(r"untap all creatures you control\.", re.I), lambda m: UntapCreatures("yours")),
    (re.compile(r"goad target (creature)\.", re.I), lambda m: Goad(m[1].lower())),
    (re.compile(r"goad (?:all creatures you don't control|each creature your opponents control)\.", re.I),
     lambda m: GoadAll()),
    (re.compile(rf"mill {_N} cards?\.", re.I), lambda m: Mill(_count(m[1]), "you")),
    (re.compile(rf"each (opponent|player) mills {_N} cards?\.", re.I),
     lambda m: Mill(_count(m[2]), "each " + m[1].lower())),
    (re.compile(rf"target (player|opponent) mills {_N} cards?\.", re.I),
     lambda m: TargetMill(_count(m[2]), m[1].lower())),
    (re.compile(rf"destroy all {_MASS_FILTERED}\.", re.I), lambda m: _mass_effect(DestroyAll, m)),
    (re.compile(r"(?:they|it) can't be regenerated\.", re.I), lambda m: CannotRegenerate()),
    (re.compile(rf"regenerate target {_PERMANENT_KIND}\.", re.I), lambda m: Regenerate(m[1].lower())),
    (re.compile(rf"regenerate {_SELF}\.", re.I), lambda m: RegenerateSource()),
    (re.compile(r"regenerate each creature you control\.", re.I), lambda m: RegenerateEach()),
    (re.compile(rf"exile all {_MASS_FILTERED}\.", re.I), lambda m: _mass_effect(ExileAll, m)),
    (re.compile(rf"{_SELF} deals {_N} damage to each (creature you don't control|creature|opponent|player)"
                rf"(?: {_RESTRICTION})?(?: and each (opponent|player))?\.", re.I), _damage_each),
    (re.compile(rf"each (opponent|player) sacrifices an? {_SACRIFICE_KIND}\.", re.I),
     lambda m: EachSacrifices(m[1].lower(), m[2].lower())),
    (re.compile(r"sacrifice a creature\.", re.I), lambda m: SacrificeCreature()),
    (re.compile(r"Let X be (.+)\."), lambda m: DefineX(a) if (a := _amount(m[1])) else None),
    (re.compile(rf"target (player|opponent) sacrifices an? {_SACRIFICE_KIND}\.", re.I),
     lambda m: TargetSacrifices(m[1].lower(), m[2].lower())),
    (re.compile(r"exile target player's graveyard\.", re.I), lambda m: ExileGraveyard()),
    (re.compile(rf"put {_N} {_COUNTER} on target {_PERMANENT_KIND}\.", re.I),
     lambda m: PutCounters(_count(m[1]), _counter_name(m[2]), m[3].lower())),
    (re.compile(rf"put {_N} {_COUNTER} on each creature you control\.", re.I),
     lambda m: PutCountersOnEach(_count(m[1]), _counter_name(m[2]))),
    (re.compile(rf"put {_N} {_COUNTER} on {_SELF}\.", re.I),
     lambda m: PutCountersOnSource(_count(m[1]), _counter_name(m[2]))),
    (re.compile(rf"(?i:target) {_PERMANENT_KIND} {_CHANGE}"), lambda m: Pump(_modifier(m, 2), m[1].lower())),
    (re.compile(rf"(?i:{_SELF}) {_CHANGE}"), lambda m: PumpSource(_modifier(m, 1))),
    (re.compile(rf"(?i:creatures you control) {_CHANGE}"), lambda m: PumpEach(_modifier(m, 1))),
    (re.compile(r'(?i:create) (.+)\.("?)'), lambda m: _create(m, follows=False)),
    (re.compile(r'(?i:its controller creates) (.+)\.("?)'), lambda m: _create(m, follows=True)),
    (re.compile(r"its controller gains life equal to its power\.", re.I), lambda m: TargetControllerGainsLifeEqualToPower()),
    (re.compile(r"its controller may search their library for a basic land card, put (?:it|that card) onto the "
                r"battlefield tapped, then shuffle\.", re.I), lambda m: TargetControllerMayFetchBasicLand()),
    (re.compile(r"search your library for a basic land card, put (?:it|that card) onto the battlefield tapped, "
                r"then shuffle\.", re.I),
     lambda m: FetchBasicLand()),
]


_YOUR_ACTION = rf"(?:draw (?:a card|{_N} cards)|gain {_N} life|lose {_N} life)"


def _you_do(phrase: str) -> str:
    """A sentence for something you do: "draw a card" -> "Draw a card.", "lose 1 life" -> "You lose 1 life." """
    return phrase[:1].upper() + phrase[1:] + "." if phrase.lower().startswith("draw") else f"You {phrase}."


_TIMES_X = [
    (r"\b(draws?) (?:a card|cards)\b", r"\1 X cards"),
    (r"\b(gains?|loses?) (?:1 )?life\b", r"\1 X life"),
    (r"\b(creates?) (?:a|an|one) (.+?) token\b", r"\1 X \2 tokens"),
    (r"\b(creates?) a number of (.+?) tokens\b", r"\1 X \2 tokens"),
    (r"\b(put) (?:a|one) (\+1/\+1) counter\b", r"\1 X \2 counters"),
]


def _times_x(text: str) -> tuple[str, int]:
    """"draw a card" -> "draw X cards", "create a 1/1 ... token" -> "create X 1/1 ... tokens", ...;
    and how many replacements were made (0: the amount has nothing to apply to)."""
    total = 0
    for pattern, replacement in _TIMES_X:
        text, n = re.subn(pattern, replacement, text, flags=re.I)
        total += n
    return text, total


def _clauses(sentence: str) -> list[str]:
    """Rewrite wording the templates don't cover into sentences they do: "X and you gain 1 life." is two
    sentences, as is "You draw two cards and lose 2 life."; "of their choice" and a leading "You draw" /
    "You create" add nothing."""
    sentence = sentence.replace(" of their choice.", ".")
    if m := re.fullmatch(r"(.+), where X is (.+)\.", sentence):
        return [f"Let X be {m[2]}."] + _clauses(m[1] + ".") if _amount(m[2]) else [sentence]
    if m := re.fullmatch(r"(.+) (?:equal to|for each) (.+)\.", sentence):
        body, count = _times_x(m[1])
        return [f"Let X be {m[2]}."] + _clauses(body + ".") if count and _amount(m[2]) else [sentence]
    sentence = re.sub(r"^You (draw|create) ", lambda m: m[1].capitalize() + " ", sentence)
    if m := re.fullmatch(rf"(.+) and you ({_YOUR_ACTION})\.", sentence, re.I):
        return _clauses(m[1] + ".") + [_you_do(m[2])]
    if m := re.fullmatch(rf"(?:you )?(?P<first>{_YOUR_ACTION}) and (?P<second>{_YOUR_ACTION})\.", sentence, re.I):
        return [_you_do(m["first"]), _you_do(m["second"])]
    return [sentence]


def _template(sentence: str) -> Any:
    """The effect of one sentence a template understands as written, or None."""
    for pattern, build in _TEMPLATES:
        match = pattern.fullmatch(sentence)
        effect = build(match) if match else None
        if effect is not None:
            return effect
    return None


def _vote_outcome(kind: str, option: str, text: str, tie: bool) -> VoteOutcome | None:
    """What a vote does, read from the sentence's own clause; only for effects that need no target."""
    effects = _parse(_split_sentences(text[:1].upper() + text[1:] + "."))
    if not effects or any(target_kind(e) or uses_source(e) or uses_subject(e) or uses_player(e) or follows_target(e)
                          for e in effects):
        return None
    return VoteOutcome(kind, option.lower(), tuple(effects), tie)


def _merge_votes(effects: list) -> list | None:
    """"Starting with you, each player votes for X or Y. For each X vote, ..." becomes one Vote, and the permanent vote
    one VoteToExile; a vote with no outcome, or outcomes about other words, isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, VoteStart) and effect.options is None:
            if not (i + 1 < len(effects) and isinstance(effects[i + 1], ExileMostVoted)):
                return None
            merged.append(VoteToExile())
            i += 2
            continue
        if isinstance(effect, VoteStart):
            outcomes = []
            i += 1
            while i < len(effects) and isinstance(effects[i], VoteOutcome):
                outcomes.append(effects[i])
                i += 1
            if not outcomes or any(o.option not in effect.options or o.kind != outcomes[0].kind for o in outcomes):
                return None
            merged.append(Vote(effect.options, tuple(outcomes)))
            continue
        if isinstance(effect, (VoteOutcome, ExileMostVoted)):
            return None
        merged.append(effect)
        i += 1
    return merged


def _parse(sentences: list[str]) -> list | None:
    effects = []
    for sentence in sentences:
        # A sentence a template already reads is taken as written; only the others are rewritten (_clauses).
        found = [effect] if (effect := _template(sentence)) is not None else [_template(c) for c in _clauses(sentence)]
        if None in found:
            return None
        for effect in found:  # one sentence can make several effects (a fight has two targets)
            effects += effect if isinstance(effect, list) else [effect]
    merged = _merge_no_regen(effects)
    for merge in (_merge_copy, _merge_control, _merge_impulse, _merge_votes):  # each returns None for a line it rejects
        merged = merge(merged)
        if merged is None:
            return None
    return merged


def _merge_impulse(effects: list) -> list | None:
    """"Look at the top five cards of your library. You may reveal a creature card from among them and put it into your
    hand. Put the rest on the bottom ..." becomes one Impulse; a look or take that isn't completed isn't understood."""
    merged: list = []
    i = 0
    while i < len(effects):
        effect = effects[i]
        if isinstance(effect, LookAtTop) and i + 1 < len(effects) and isinstance(effects[i + 1], TakeFromTop):
            take = effects[i + 1]
            i += 2
            if take.card_type is not None:  # the optional reveal needs the rest-on-the-bottom sentence
                if not (i < len(effects) and isinstance(effects[i], RestOnBottom)):
                    return None
                i += 1
            merged.append(Impulse(effect.count, take.card_type))
            continue
        if isinstance(effect, (LookAtTop, TakeFromTop, RestOnBottom)):
            return None
        merged.append(effect)
        i += 1
    return merged


def _merge_copy(effects: list) -> list | None:
    """"Copy target instant or sorcery spell. You may choose new targets for the copy." is one effect. The second
    sentence on its own has no copy to refer to, so the line isn't understood."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, NewTargets):
            if not merged or not isinstance(merged[-1], CopySpell):
                return None
            merged[-1] = dataclasses.replace(merged[-1], new_targets=True)
        else:
            merged.append(effect)
    return merged


def _merge_control(effects: list) -> list | None:
    """Threaten: "Gain control of target creature until end of turn. Untap that creature. It gains haste until end
    of turn." is one effect. A lone "Untap that creature." has nothing to refer to, so the line isn't understood."""
    merged: list = []
    for effect in effects:
        after_control = bool(merged) and isinstance(merged[-1], GainControl)
        if isinstance(effect, UntapThat):
            if not after_control:
                return None
            merged[-1] = dataclasses.replace(merged[-1], untap=True)
        elif (isinstance(effect, PumpSource) and effect.modifier.keywords == frozenset({"haste"})
              and effect.modifier.power == effect.modifier.toughness == 0 and after_control and merged[-1].untap):
            merged[-1] = dataclasses.replace(merged[-1], haste=True)
        else:
            merged.append(effect)
    return merged


def _merge_no_regen(effects: list) -> list:
    """"Destroy all creatures. They can't be regenerated." becomes one destroy effect that skips regeneration."""
    merged: list = []
    for effect in effects:
        if isinstance(effect, CannotRegenerate) and merged and isinstance(merged[-1], (Destroy, DestroyAll)):
            merged[-1] = dataclasses.replace(merged[-1], no_regen=True)
        else:
            merged.append(effect)
    return merged


def spell_effects(card: Card) -> list | None:
    """Effects of an instant or sorcery, in order; None if any sentence isn't understood. A modal spell
    ("Choose one — ...") gives a single Modal effect."""
    lines = [line for line in rules_lines(card) if not is_casting_cost_line(line)]
    if lines and (m := _MODAL_HEADER.fullmatch(lines[0])):
        return _parse_modal(m[1].lower(), lines[1:])
    return _parse(_split_sentences("\n".join(lines)))


def line_effects(line: str) -> list | None:
    """Effects of one line of spell text (from rules_lines); None if not understood."""
    return _parse(_split_sentences(line))


@dataclass(frozen=True)
class TriggeredAbility:
    event: str  # one of TRIGGER_EVENTS
    effects: tuple
    optional: bool  # "you may ...": the controller chooses when it resolves
    text: str
    watch: "Watch | None" = None  # set when it watches other objects ("Whenever another creature enters")
    once_per_turn: bool = False  # "This ability triggers only once each turn."
    condition: "Condition | None" = None  # "At the beginning of your upkeep, if ..., ..." (CR 603.4)


@dataclass(frozen=True)
class Condition:
    """An intervening "if" clause, checked when the ability triggers and again when it resolves."""
    kind: str  # "graveyard_left", "gained_life", "opponent_more_lands", "cast_this_turn", "control_at_least",
    #            "control_none", "kicked", "your_turn", "monarch", "hand_at_least", "hand_none", "no_counter"
    count: int = 0
    what: str = ""  # a spell kind ("instant or sorcery spell") or a type ("Plains", "Snake", "creature")


def _singular(word: str) -> str:
    return word if word.endswith("ss") or word.lower() == "plains" else word.removesuffix("s")


_CONDITIONS = [
    (re.compile(r"a card left your graveyard this turn"), lambda m: Condition("graveyard_left")),
    (re.compile(r"you gained life this turn"), lambda m: Condition("gained_life")),
    (re.compile(r"an opponent controls more lands than you"), lambda m: Condition("opponent_more_lands")),
    (re.compile(r"you've cast an? (instant or sorcery spell|creature spell|noncreature spell|spell) this turn"),
     lambda m: Condition("cast_this_turn", what=m[1])),
    (re.compile(rf"you control {_N} or more ([A-Za-z]+)"),
     lambda m: Condition("control_at_least", _count(m[1]), _singular(m[2]))),
    (re.compile(r"you control no ([A-Za-z]+)"), lambda m: Condition("control_none", what=_singular(m[1]))),
    (re.compile(r"you control an? ([A-Za-z]+)"), lambda m: Condition("control_at_least", 1, _singular(m[1]))),
    (re.compile(r"it's your turn"), lambda m: Condition("your_turn")),
    (re.compile(r"you're the monarch"), lambda m: Condition("monarch")),
    (re.compile(rf"you have {_N} or more cards in hand"), lambda m: Condition("hand_at_least", _count(m[1]))),
    (re.compile(r"you have no cards in hand"), lambda m: Condition("hand_none")),
    (re.compile(rf"{_SELF} was kicked"), lambda m: Condition("kicked")),
]


def _condition(text: str) -> Condition | None:
    for pattern, build in _CONDITIONS:
        if m := pattern.fullmatch(text):
            return build(m)
    return None


@dataclass(frozen=True)
class Watch:
    """What a watching trigger looks for."""
    kind: str  # "creature", "land", "artifact", "enchantment"; for casts "spell", "creature spell", ...
    other: bool = False  # "another": not the source itself
    yours: bool = False  # "you control" / "under your control"
    nontoken: bool = False
    caster: str = "you"  # for casts: "you", "player" (anyone) or "opponent"
    theirs: bool = False  # "an opponent controls"
    first_each_turn: bool = False  # "your first ... spell each turn"


_TRIGGERS = {
    "enters": re.compile(rf"When(?:ever)? {_SELF} enters(?: the battlefield)?, (.+)", re.I),
    "dies": re.compile(rf"When(?:ever)? {_SELF} dies, (.+)", re.I),
    "attacks": re.compile(rf"Whenever {_SELF} attacks, (.+)", re.I),
    "blocks": re.compile(rf"Whenever {_SELF} blocks, (.+)", re.I),
    "ally_attacks": re.compile(r"Whenever a creature you control attacks, (.+)", re.I),
    "attacked": re.compile(r"Whenever a creature attacks you, (.+)", re.I),
    "attacked_or_walker": re.compile(r"Whenever a creature attacks you or a planeswalker you control, (.+)", re.I),
    "draw": re.compile(r"Whenever you draw a card, (.+)", re.I),
    "opponent_draw": re.compile(r"Whenever an opponent draws a card, (.+)", re.I),
    "opponent_gain_life": re.compile(r"Whenever an opponent gains life, (.+)", re.I),
    "opponent_lose_life": re.compile(r"Whenever an opponent loses life, (.+)", re.I),
    "become_monarch": re.compile(r"Whenever you become the monarch, (.+)", re.I),
    "opponent_become_monarch": re.compile(r"Whenever an opponent becomes the monarch, (.+)", re.I),
    "opponent_sacrifice_creature": re.compile(r"Whenever an opponent sacrifices a creature, (.+)", re.I),
    "second_draw": re.compile(r"Whenever you draw your second card each turn, (.+)", re.I),
    "combat_damage_to_player": re.compile(rf"Whenever {_SELF} deals combat damage to a player, (.+)", re.I),
    "upkeep": re.compile(r"At the beginning of your upkeep, (.+)", re.I),
    "end_step": re.compile(r"At the beginning of your end step, (.+)", re.I),
    "each_upkeep": re.compile(r"At the beginning of each upkeep, (.+)", re.I),
    "each_end_step": re.compile(r"At the beginning of each end step, (.+)", re.I),
    "combat": re.compile(r"At the beginning of combat on your turn, (.+)", re.I),
    "gain_life": re.compile(r"Whenever you gain life, (.+)", re.I),
    "lose_life": re.compile(r"Whenever you lose life, (.+)", re.I),
    "sacrifice_creature": re.compile(r"Whenever you sacrifice a creature, (.+)", re.I),
    "ally_combat_damage": re.compile(r"Whenever a creature you control deals combat damage to a player, (.+)", re.I),
    "token_combat_damage": re.compile(r"Whenever a creature token you control deals combat damage to a player, (.+)",
                                      re.I),
    "host_attacks": re.compile(r"Whenever (?:equipped|enchanted) creature attacks, (.+)", re.I),
    "attack_with_two": re.compile(r"Whenever you attack with two or more creatures, (.+)", re.I),
    "graveyard_leave": re.compile(r"Whenever one or more cards leave your graveyard, (.+)", re.I),
    "any_sacrifice": re.compile(r"Whenever a player sacrifices a permanent, (.+)", re.I),
    "other_sacrifice": re.compile(r"Whenever a player sacrifices another permanent, (.+)", re.I),
    "host_dies": re.compile(r"When(?:ever)? enchanted creature dies, (.+)", re.I),
    "first_life_loss": re.compile(r"Whenever you lose life for the first time each turn, (.+)", re.I),
}
TRIGGER_EVENTS = tuple(_TRIGGERS)

# One line can name several of a permanent's own events: "When this creature enters or dies, ...".
_SELF_EVENTS = {
    "enters": r"enters(?: the battlefield)?",
    "dies": r"dies",
    "attacks": r"attacks",
    "blocks": r"blocks",
    "combat_damage_to_player": r"deals combat damage to a player",
}
_ANY_SELF_EVENT = "(?:" + "|".join(_SELF_EVENTS.values()) + ")"
_SEVERAL_EVENTS = re.compile(rf"When(?:ever)? {_SELF} ({_ANY_SELF_EVENT}(?: or {_ANY_SELF_EVENT})+), (.+)", re.I)


_WHO = rf"(?:({_SELF}) or another|(another)|an?)"
_PERMANENT_WATCH = r"(nontoken creature|creature|land|artifact|enchantment)"
_WATCHES = {
    "permanent_enters": re.compile(
        rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control)? enters(?: the battlefield)?( under your control)?, (.+)", re.I),
    "creature_dies": re.compile(rf"Whenever {_WHO} (nontoken creature|creature)( you control| an opponent controls)? dies, (.+)",
                                re.I),
    "cast": re.compile(r"Whenever (you cast|a player casts|an opponent casts) (?:an?|(your first)) "
                       r"((?:white|blue|black|red|green) spell"
                       r"|spell|creature spell|noncreature spell|instant or sorcery spell|artifact spell|enchantment spell"
                       r"|Aura spell|Aura, Equipment, or Vehicle spell|historic spell|spell with \{X\} in its mana cost)"
                       r"(?(2) each turn), (.+)", re.I),
}
# Watching events whose subject is a permanent, so "it" in the effect can mean that permanent.
_SUBJECT_EVENTS = {"permanent_enters", "creature_dies"}
# Triggers about some other creature: there "it" and "that creature" mean that creature, not the source.
_OBJECT_EVENTS = {"ally_attacks", "attacked", "attacked_or_walker", "ally_combat_damage", "token_combat_damage"}
# Triggers about what some other player did: there "that player" and "they" mean that player.
_PLAYER_EVENTS = {"opponent_draw", "opponent_gain_life", "opponent_lose_life", "opponent_become_monarch"}
_THAT_CREATURE = re.compile(r"\bthat (creature|land)\b", re.I)
_PLAYER_PRONOUNS = [
    (re.compile(r"\bthey (lose|gain|draw|discard|mill)\b", re.I), r"target player \1s"),
    (re.compile(r"\bthat player (loses|gains|draws|discards|mills)\b", re.I), r"target player \1"),
    (re.compile(r"\bto that player\b", re.I), "to target player"),
]
_ABILITY_WORD = re.compile(r"^[A-Z][\w' -]* \u2014 ")  # "Landfall — ", "Constellation — "


def _watch_trigger(line: str) -> tuple[str, Watch, str] | None:
    line = _ABILITY_WORD.sub("", line)
    if m := _WATCHES["cast"].fullmatch(line):
        caster = {"you cast": "you", "a player casts": "player", "an opponent casts": "opponent"}[m[1].lower()]
        return "cast", Watch(m[3].lower(), caster=caster, first_each_turn=bool(m[2])), m[4]
    for event in ("permanent_enters", "creature_dies"):
        if m := _WATCHES[event].fullmatch(line):
            self_or_other, another, kind = m[1], m[2], m[3].lower()
            yours = m[4] == " you control" or (event == "permanent_enters" and bool(m[5]))
            watch = Watch(kind.removeprefix("nontoken "), other=bool(another) and not self_or_other,
                          yours=yours, nontoken=kind.startswith("nontoken"), theirs=m[4] == " an opponent controls")
            return event, watch, m[len(m.groups())]
    return None


_RETURN_EXILED = re.compile(rf"When(?:ever)? {_SELF} leaves the battlefield, return the exiled card to the "
                            r"battlefield under its owner's control\.", re.I)


def is_return_exiled_line(line: str) -> bool:
    """The second half of Oblivion Ring: the engine returns the exiled card when the source leaves."""
    return _RETURN_EXILED.fullmatch(line) is not None


_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}
_CHAPTER = re.compile(r"((?:I|II|III|IV|V|VI|VII)(?:, (?:I|II|III|IV|V|VI|VII))*) \u2014 (.+)")


@lru_cache(maxsize=None)
def saga_chapters(card: Card) -> dict[int, tuple[tuple, str]]:
    """A Saga's chapters: number -> (its effects, the line it is printed on). All or nothing: if any chapter isn't
    understood the Saga gets none, so it never does half of what it says."""
    found: dict[int, tuple[tuple, str]] = {}
    if "Saga" not in card.type_line:
        return found
    for line in rules_lines(card):
        if m := _CHAPTER.fullmatch(line):
            effects = _parse(_split_sentences(m[2]))
            if not effects:
                return {}
            for numeral in m[1].split(", "):
                found[_ROMAN[numeral]] = (tuple(effects), line)
    return found


@lru_cache(maxsize=None)
def triggered_abilities(card: Card) -> tuple[TriggeredAbility, ...]:
    """The triggered abilities on a permanent whose effects are all understood."""
    abilities = _triggered_abilities(card)
    for number, (effects, line) in saga_chapters(card).items():  # a lore counter makes the chapter trigger
        abilities.append(TriggeredAbility(f"chapter_{number}", effects, False, line))
    for line in rules_lines(card):  # persist and undying are keywords that come back from the graveyard
        words = {word.strip().lower() for word in line.split(",")}
        for keyword, counter in (("persist", "-1/-1"), ("undying", "+1/+1")):
            if keyword in words:
                abilities.append(TriggeredAbility("dies", (ReturnWithCounter(counter),), False, line,
                                                  condition=Condition("no_counter", what=counter)))
    if any(is_return_exiled_line(line) for line in rules_lines(card)):
        # Two-trigger wording: the enters-the-battlefield exile lasts until this permanent leaves.
        abilities = [
            dataclasses.replace(a, effects=tuple(ExileUntilLeaves(e.target, e.another) if isinstance(e, Exile) else e
                                                 for e in a.effects))
            if a.event == "enters" else a
            for a in abilities]
    return tuple(abilities)


_TRIGGERS_ONCE = " This ability triggers only once each turn."


def _trigger_body(rest: str) -> tuple[list | None, bool, bool, Condition | None]:
    """The part of a trigger after its event: (effects, or None if not understood; "you may";
    "only once each turn"; an intervening "if" clause)."""
    condition = None
    if rest.startswith("if ") and ", " in rest:
        text, rest = rest[3:].split(", ", 1)
        condition = _condition(text)
        if condition is None:
            return None, False, False, None
    once = rest.endswith(_TRIGGERS_ONCE)
    rest = rest.removesuffix(_TRIGGERS_ONCE)
    optional = rest.lower().startswith("you may ")
    rest = rest[len("you may "):] if optional else rest
    return _parse(_split_sentences(rest[:1].upper() + rest[1:])), optional, once, condition


_UNLESS_PAYS = re.compile(r"(.+?) unless that player pays ((?:\{[^}]+\})+)\.?", re.I)


def _event_body(rest: str, subject_ok: bool, player_ok: bool) -> tuple[list | None, bool, bool, Condition | None]:
    """Like _trigger_body for a trigger about another object or player. "It" means the permanent that set it off
    (only if every effect is about "it"), "that player" / "they" the player who did it (only for effects that
    target a player); where neither can be pointed at, the line isn't understood."""
    rest = _THAT_CREATURE.sub("it", rest)
    about_player = False
    if player_ok and (m := _UNLESS_PAYS.fullmatch(rest)):
        effects, optional, once, condition = _trigger_body(m[1] + ".")
        if effects is None or any(target_kind(e) or uses_source(e) or uses_subject(e) or uses_player(e)
                                  or follows_target(e) for e in effects):
            return None, False, False, None
        return [UnlessPays(tuple(effects), m[2])], optional, once, condition
    if player_ok:
        replaced = rest
        for pattern, replacement in _PLAYER_PRONOUNS:
            replaced = pattern.sub(replacement, replaced)
        about_player, rest = replaced != rest, replaced
    about_subject = re.search(r"\bit\b|\bthat spell\b", rest, re.I) is not None
    if about_subject and not subject_ok:
        return None, False, False, None
    effects, optional, once, condition = _trigger_body(rest)
    if effects is None:
        return None, False, False, None
    if about_player:
        if not all(getattr(e, "target", None) in ("player", "opponent", "any") for e in effects):
            return None, False, False, None
        effects = [OnPlayer(e) for e in effects]
    elif about_subject:
        if not all(uses_source(e) for e in effects):
            return None, False, False, None
        effects = [OnSubject(e) for e in effects]
    return effects, optional, once, condition


def _triggered_abilities(card: Card) -> list[TriggeredAbility]:
    abilities = []
    for line in _rules_text(card).splitlines():
        line = line.strip()
        bare = _ABILITY_WORD.sub("", line)  # patterns read the line without "Council's dilemma — "; its text stays whole
        if watched := _watch_trigger(line):
            event, watch, rest = watched
            effects, optional, once, condition = _event_body(
                rest, event in _SUBJECT_EVENTS, event == "cast" and watch.caster != "you")
            if effects is not None:
                abilities.append(TriggeredAbility(event, tuple(effects), optional, line, watch, once, condition))
            continue
        if several := _SEVERAL_EVENTS.fullmatch(bare):
            effects, optional, once, condition = _trigger_body(several[2])
            if effects is not None:
                for event, pattern in _SELF_EVENTS.items():
                    if any(re.fullmatch(pattern, part, re.I) for part in several[1].split(" or ")):
                        abilities.append(TriggeredAbility(event, tuple(effects), optional, line, once_per_turn=once,
                                                          condition=condition))
            continue
        for event, pattern in _TRIGGERS.items():
            match = pattern.fullmatch(bare)
            if not match:
                continue
            if event in _OBJECT_EVENTS or event in _PLAYER_EVENTS:
                effects, optional, once, condition = _event_body(match[1], event in _OBJECT_EVENTS,
                                                                 event in _PLAYER_EVENTS)
            else:
                effects, optional, once, condition = _trigger_body(match[1])
            if effects is not None:
                abilities.append(TriggeredAbility(event, tuple(effects), optional, line, once_per_turn=once,
                                                  condition=condition))
            break
    return abilities


@dataclass(frozen=True)
class ActivatedAbility:
    text: str
    effects: tuple
    mana_cost: str = ""  # e.g. "{2}{W}"; paid like a spell's cost
    tap: bool = False  # {T}
    sacrifice: bool = False  # sacrifice the source itself
    life: int = 0  # pay N life
    loyalty: int | None = None  # planeswalker loyalty change: +1, -2, 0
    sorcery_speed: bool = False  # "Activate only as a sorcery." (loyalty abilities always)
    once_per_turn: bool = False  # "Activate only once each turn."
    sacrifice_other: str | None = None  # "Sacrifice a creature": the kind ("creature", "artifact or creature", ...)
    sacrifice_another: bool = False  # "Sacrifice another creature": not the source itself
    discard: bool = False  # "Discard a card"
    exile_graveyard: bool = False  # "Exile a card from your graveyard"
    crew: int = 0  # "Crew N": tap untapped creatures you control with total power N or more


_CREW = re.compile(r"Crew (\d+)")
_ACTIVATED = re.compile(r"([^:\"]+): (.+)")
_MANA_PART = re.compile(r"(\{(?:\d+|X|S|[WUBRGC]|[WUBRGC]/[WUBRGCP]|2/[WUBRGC])\})+")
_SACRIFICE_SELF = re.compile(rf"Sacrifice {_SELF}", re.I)
_PAY_LIFE = re.compile(rf"Pay {_N} life", re.I)
_SACRIFICE_OTHER = re.compile(r"Sacrifice (another|an?) (creature|artifact|land|enchantment|permanent|artifact or creature)")
_LOYALTY = re.compile(r"([+\u2212-]?)(\d+)")
_SORCERY_ONLY = "Activate only as a sorcery."
_ONCE_EACH_TURN = "Activate only once each turn."


@lru_cache(maxsize=None)
def activated_abilities(card: Card) -> tuple[ActivatedAbility, ...]:
    """Activated abilities ("{1}, {T}, Sacrifice this artifact: Draw a card.") whose
    costs and effects are all understood. Mana abilities are handled by mana_ability."""
    planeswalker = "Planeswalker" in card.type_line
    abilities = []
    for line in rules_lines(card):
        if m := _CREW.fullmatch(line):  # a Vehicle: tap creatures and it becomes an artifact creature this turn
            abilities.append(ActivatedAbility(line, (BecomeCreature(),), crew=int(m[1])))
            continue
        match = _ACTIVATED.fullmatch(line)
        if not match or is_mana_ability(line):
            continue
        ability = _parse_activated(line, match[1], match[2], planeswalker)
        if ability is not None:
            abilities.append(ability)
    if cost := equip_cost(card):
        abilities.append(ActivatedAbility(f"Equip {cost}", (Attach(),), mana_cost=cost, sorcery_speed=True))
    return tuple(abilities)


def _parse_activated(line: str, cost: str, effect: str, planeswalker: bool) -> ActivatedAbility | None:
    fields: dict[str, Any] = {}
    loyalty = _LOYALTY.fullmatch(cost)
    if planeswalker and loyalty:
        amount = int(loyalty[2])
        fields.update(loyalty=-amount if loyalty[1] in ("\u2212", "-") else amount, sorcery_speed=True)
    else:
        for part in cost.split(", "):
            if _MANA_PART.fullmatch(part):
                fields["mana_cost"] = fields.get("mana_cost", "") + part
            elif part == "{T}":
                fields["tap"] = True
            elif _SACRIFICE_SELF.fullmatch(part):
                fields["sacrifice"] = True
            elif (m := _PAY_LIFE.fullmatch(part)) and m[1] != "X":
                fields["life"] = _count(m[1])
            elif m := _SACRIFICE_OTHER.fullmatch(part):
                fields.update(sacrifice_other=m[2], sacrifice_another=m[1] == "another")
            elif part == "Discard a card":
                fields["discard"] = True
            elif part == "Exile a card from your graveyard":
                fields["exile_graveyard"] = True
            else:
                return None
    sentences = _split_sentences(effect)
    if _SORCERY_ONLY in sentences:
        fields["sorcery_speed"] = True
        sentences.remove(_SORCERY_ONLY)
    if _ONCE_EACH_TURN in sentences:
        fields["once_per_turn"] = True
        sentences.remove(_ONCE_EACH_TURN)
    effects = _parse(sentences)
    if not effects:
        return None
    return ActivatedAbility(line, tuple(effects), **fields)


_TAP = r"\{T\}(, Sacrifice (?:CARDNAME|this (?:artifact|creature|permanent|land)))?: Add "  # group 1: sacrifice
_ADD_SYMBOLS = re.compile(_TAP + r"((?:\{[WUBRGC]\})+)\.")
_ADD_EITHER = re.compile(_TAP + r"\{([WUBRGC])\} or \{([WUBRGC])\}\.")
_ADD_ANY = re.compile(_TAP + r"one mana of any color\.")
_ADD_IDENTITY = re.compile(_TAP + r"one mana of any color in your commander's color identity\.")


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


def mana_ability_sacrifices(card: Card) -> bool:
    """Whether using the card's mana ability sacrifices it (Treasure)."""
    line = _mana_line(card)
    return bool(line and any((m := p.fullmatch(line)) and m[1] for p in _MANA_PATTERNS))


def _mana_line(card: Card) -> str | None:
    """The card's plain "{T}: Add ..." line (Signet-style lines are filter_mana_ability's)."""
    return next((line for line in rules_lines(card) if any(p.fullmatch(line) for p in _MANA_PATTERNS)), None)


_MANA_PATTERNS = (_ADD_SYMBOLS, _ADD_EITHER, _ADD_ANY, _ADD_IDENTITY)
_PAIN = re.compile(rf"\{{T\}}: Add \{{([WUBRGC])\}} or \{{([WUBRGC])\}}\. {_SELF} deals {_N} damage to you\.", re.I)
# Ancient Tomb: two mana, and the damage is dealt once however much of it is used.
_PAIN_MULTI = re.compile(rf"\{{T\}}: Add ((?:\{{[WUBRGC]\}}){{2,}})\. {_SELF} deals {_N} damage to you\.", re.I)
# City of Brass: the damage comes from the land becoming tapped.
_TAPPED_PAIN = re.compile(rf"Whenever {_SELF} becomes tapped, it deals {_N} damage to you\.", re.I)
# Mana Confluence: paying life, not damage.
_PAY_LIFE_ANY = re.compile(rf"\{{T\}}, Pay {_N} life: Add one mana of any color\.", re.I)


def is_mana_ability(line: str) -> bool:
    return (any(p.fullmatch(line) for p in _MANA_PATTERNS) or _FILTER.fullmatch(line) is not None
            or any(p.fullmatch(line) for p in (_PAIN, _PAIN_MULTI, _TAPPED_PAIN, _PAY_LIFE_ANY)))


def mana_pain(card: Card) -> tuple[frozenset[str], int] | None:
    """For painlands and Talismans ("{T}: Add {G} or {U}. This land deals 1 damage to you."): the types
    that cost damage when produced, and how much."""
    for line in rules_lines(card):
        if m := _PAIN.fullmatch(line):
            return frozenset((m[1], m[2])), _count(m[3])
        if m := _PAIN_MULTI.fullmatch(line):
            return frozenset(re.findall(r"[WUBRGC]", m[1])), _count(m[2])
        if m := _TAPPED_PAIN.fullmatch(line):  # every color it makes hurts
            return frozenset("WUBRGC"), _count(m[1])
    return None


def mana_life_cost(card: Card) -> int:
    """Life paid each time a land is tapped for mana ("{T}, Pay 1 life: Add one mana of any color."), or 0."""
    return next((_count(m[1]) for line in rules_lines(card) if (m := _PAY_LIFE_ANY.fullmatch(line))), 0)


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
    return "Land" in card.type_line and any(_ADD_IDENTITY.fullmatch(line) for line in rules_lines(card))


_FILTER = re.compile(r"((?:\{\d+\}|\{[WUBRGC]\})+), \{T\}: Add ((?:\{[WUBRGC]\})+)\.")


def filter_mana_ability(card: Card) -> tuple[str, list[frozenset[str]]] | None:
    """A mana ability that costs mana, like a Signet's "{1}, {T}: Add {W}{U}.":
    (the mana it costs, the mana it makes, one set per mana)."""
    for line in rules_lines(card):
        if m := _FILTER.fullmatch(line):
            return m[1], [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[2])]
    return None


def _mana_from_line(line: str, commander_identity: frozenset[str]) -> list[frozenset[str]] | None:
    if m := _ADD_SYMBOLS.fullmatch(line):
        return [frozenset(symbol) for symbol in re.findall(r"[WUBRGC]", m[2])]
    if m := _ADD_EITHER.fullmatch(line):
        return [frozenset((m[2], m[3]))]
    if _ADD_ANY.fullmatch(line):
        return [frozenset("WUBRG")]
    return [commander_identity] if commander_identity else None
