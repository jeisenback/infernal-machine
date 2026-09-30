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
from .characteristics import Modifier

if TYPE_CHECKING:
    from .game import Game, Seat

_NUMBERS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_N = r"(a|an|one|two|three|four|five|six|seven|eight|nine|ten|\d+|X)"
_REMINDER = re.compile(r"\s*\([^)]*\)")
_SELF = r"(?:CARDNAME|it|this (?:spell|creature|artifact|enchantment|land|planeswalker|permanent))"


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


def enters_with_counters(card: Card) -> dict[str, int | str]:
    """Counters from "This creature enters with N (or X) +1/+1 counters on it." """
    counters: dict[str, int | str] = {}
    for line in rules_lines(card):
        if m := _ENTERS_WITH.fullmatch(line):
            name, count = _counter_name(m[2]), _count(m[1])
            counters[name] = count if count == "X" else counters.get(name, 0) + count
    return counters


def is_enters_with_counters(line: str) -> bool:
    return _ENTERS_WITH.fullmatch(line) is not None


def _signed(text: str) -> int:
    return int(text.replace("\u2212", "-"))


def _keyword_list(text: str) -> frozenset[str]:
    """ "flying", "flying and vigilance", "flying, vigilance, and trample" -> {"flying", ...}"""
    return frozenset(w.strip().lower() for w in re.split(r",? and |, ", text) if w.strip())


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
_KEYWORDS = r"([a-z]+(?: [a-z]+)?(?:(?:,? and |, )[a-z]+(?: [a-z]+)?)*)"
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


_AFFECTED = r"(?:(Other) )?(?:([A-Z][\w'-]*) )?[Cc]reatures you control"
_STATIC = re.compile(rf"{_AFFECTED} (?:get {_PT}(?: and have {_KEYWORDS})?|have {_KEYWORDS})\.")


@lru_cache(maxsize=None)
def static_abilities(card: Card) -> tuple[StaticBuff, ...]:
    buffs = []
    for line in rules_lines(card):
        if m := _STATIC.fullmatch(line):
            buffs.append(StaticBuff(_modifier(m, 3), m[1] is not None, m[2], line))
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
        game.create_tokens(controller, self.token, game.amount(self.count))


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
    rf"{_N} (\d+)/(\d+) (colorless|{_COLOR}(?:(?:,? and |, ){_COLOR})*) ((?:[A-Z][\w'-]* )+)(artifact )?"
    r"creature tokens?(?: with ([a-z ,]+))?"
)
_NAMED_TOKEN = re.compile(rf"(?i:{_N}) (Treasure|Clue|Food) tokens?")


def _token(spec: str) -> tuple[int, Card] | None:
    """Parse "a 1/1 white Soldier creature token with flying" or "two Treasure tokens"."""
    if m := _NAMED_TOKEN.fullmatch(spec):
        return _count(m[1]), _NAMED_TOKENS[m[2].lower()]
    m = _CREATURE_TOKEN.fullmatch(spec)
    if not m:
        return None
    count, power, toughness, colors, subtypes, artifact, keywords = m.groups()
    keyword_line = ""
    if keywords:
        words = [w.strip() for w in re.split(r",? and |, ", keywords) if w.strip()]
        keyword_line = ", ".join(words).capitalize()
    card = Card(
        name=subtypes.strip(),
        type_line=f"Token {'Artifact ' if artifact else ''}Creature — {subtypes.strip()}",
        oracle_text=keyword_line,
        colors=tuple(_COLOR_WORDS[c] for c in re.findall(_COLOR, colors)),
        power=power,
        toughness=toughness,
    )
    return _count(count), card


def _create(m: re.Match, follows: bool) -> Any:
    parsed = _token(m[1])
    if parsed is None:
        return None
    return (TargetControllerCreatesTokens if follows else CreateTokens)(*parsed)


@dataclass(frozen=True)
class DestroyAll:
    """ "Destroy all creatures." Indestructible permanents survive; they all die together."""
    kind: str  # "creature", "artifact or enchantment", "creature you don't control", ...

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.destroy_all(game.mass_targets(self.kind, controller))


@dataclass(frozen=True)
class ExileAll:
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.exile_all(game.mass_targets(self.kind, controller))


@dataclass(frozen=True)
class CannotRegenerate:
    """ "They can't be regenerated." Regeneration isn't in the engine, so there's nothing to do."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class DamageEach:
    """ "This spell deals 2 damage to each creature (and each player)." Nothing is targeted."""
    amount: int | str
    creatures: str | None  # None, "all", or "opponents" (only creatures you don't control)
    players: str | None  # None, "opponents" or "all"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        amount = game.amount(self.amount)
        if self.creatures:
            kind = "creature" if self.creatures == "all" else "creature you don't control"
            for permanent in game.mass_targets(kind, controller):
                game.damage(permanent, amount)
        if self.players:
            for seat in (game.live_seats() if self.players == "all" else game.opponents(controller)):
                game.damage(seat, amount)


@dataclass(frozen=True)
class EachSacrifices:
    """ "Each opponent sacrifices a creature." / "Each player sacrifices a creature." """
    who: str  # "opponent" or "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "player" or seat is not controller:
                game.sacrifice(seat)


@dataclass(frozen=True)
class TargetSacrifices:
    """ "Target player sacrifices a creature." (target is "player" or "opponent") """
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.sacrifice(target)


_MASS_KINDS = {"creatures": "creature", "artifacts": "artifact", "enchantments": "enchantment",
               "planeswalkers": "planeswalker", "lands": "land", "nonland permanents": "nonland permanent",
               "artifacts and enchantments": "artifact or enchantment",
               "creatures and planeswalkers": "creature or planeswalker"}
_MASS = (r"(artifacts and enchantments|creatures and planeswalkers|nonland permanents|creatures|artifacts"
         r"|enchantments|planeswalkers|lands)( you don't control| you control| an opponent controls)?")


def _mass_kind(m: re.Match) -> str:
    return _MASS_KINDS[m[1].lower()] + (m[2] or "")


def _damage_each(m: re.Match) -> DamageEach:
    creatures = players = None
    for part in (m[2].lower(), (m[3] or "").lower()):
        if part == "creature":
            creatures = "all"
        elif part == "creature you don't control":
            creatures = "opponents"
        elif part:
            players = "all" if part == "player" else "opponents"
    return DamageEach(_count(m[1]), creatures, players)


@dataclass(frozen=True)
class ReturnToHand:
    """Bounce: "Return target nonland permanent you don't control to its owner's hand." """
    target: str

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


@dataclass(frozen=True)
class Scry:
    count: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.scry(controller, game.amount(self.count))


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


_CYCLING = re.compile(r"Cycling ((?:\{\d+\}|\{[WUBRGC]\})+)")


def cycling_cost(card: Card) -> str | None:
    """The mana cost from "Cycling {2}" (only mana costs are supported), or None."""
    return next((m[1] for line in rules_lines(card) if (m := _CYCLING.fullmatch(line))), None)


def is_cycling_line(line: str) -> bool:
    return _CYCLING.fullmatch(line) is not None
_LAND_TYPES = rf"({_LAND_TYPE}(?:, {_LAND_TYPE})*(?:,? or {_LAND_TYPE})?)"


def _land_types(text: str) -> tuple[str, ...]:
    return tuple(t.capitalize() for t in re.findall(_LAND_TYPE, text, re.I))


_CARD_TYPE = r"(?:(creature|artifact|enchantment|land|permanent|instant or sorcery|instant|sorcery) )?card"
_SEARCH_TYPE = (r"(?:(creature|land|artifact|enchantment|planeswalker|instant or sorcery|instant|sorcery"
                r"|artifact or enchantment|basic land) )?card")


def _graveyard_kind(card_type: str | None, whose: str) -> str:
    return f"graveyard:{card_type or 'card'}:{whose}"


@dataclass(frozen=True)
class FetchBasicLand:
    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fetch_basic_land(controller)


_PERMANENT_KIND = (r"((?:creature|artifact|enchantment|planeswalker|nonland permanent|permanent|artifact or enchantment"
                   r"|creature or planeswalker)(?: an opponent controls| you don't control| you control)?)")
_DAMAGE_KIND = r"(any target|target creature|target player|target creature or planeswalker|target player or planeswalker)"

_TEMPLATES: list[tuple[re.Pattern, Callable[[re.Match], Any]]] = [
    (re.compile(rf"draw {_N} cards?\.", re.I), lambda m: Draw(_count(m[1]))),
    (re.compile(rf"you gain {_N} life\.", re.I), lambda m: GainLife(_count(m[1]))),
    (re.compile(rf"each opponent loses {_N} life\.", re.I), lambda m: OpponentsLoseLife(_count(m[1]))),
    (re.compile(rf"{_SELF} deals {_N} damage to {_DAMAGE_KIND}\.", re.I),
     lambda m: Damage(_count(m[1]), "any" if m[2].lower() == "any target" else m[2].lower().removeprefix("target "))),
    (re.compile(rf"destroy target {_PERMANENT_KIND}\.", re.I), lambda m: Destroy(m[1].lower())),
    (re.compile(r"counter target spell\.", re.I), lambda m: Counter()),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND}\.", re.I), lambda m: Exile(m[2].lower(), bool(m[1]))),
    (re.compile(rf"exile (another )?target {_PERMANENT_KIND} until {_SELF} leaves the battlefield\.", re.I),
     lambda m: ExileUntilLeaves(m[2].lower(), bool(m[1]))),
    (re.compile(rf"target (player|opponent) draws {_N} cards?\.", re.I), lambda m: TargetDraw(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) gains {_N} life\.", re.I), lambda m: TargetGainLife(_count(m[2]), m[1].lower())),
    (re.compile(rf"target (player|opponent) loses {_N} life\.", re.I), lambda m: TargetLoseLife(_count(m[2]), m[1].lower())),
    (re.compile(rf"return target {_PERMANENT_KIND} to its owner's hand\.", re.I), lambda m: ReturnToHand(m[1].lower())),
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
     lambda m: SearchLibrary(m[1] or "card", "hand" if "into your hand" in m[0] else "top", "reveal it" in m[0].lower())),
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
    (re.compile(rf"mill {_N} cards?\.", re.I), lambda m: Mill(_count(m[1]), "you")),
    (re.compile(rf"each (opponent|player) mills {_N} cards?\.", re.I),
     lambda m: Mill(_count(m[2]), "each " + m[1].lower())),
    (re.compile(rf"target (player|opponent) mills {_N} cards?\.", re.I),
     lambda m: TargetMill(_count(m[2]), m[1].lower())),
    (re.compile(rf"destroy all {_MASS}\.", re.I), lambda m: DestroyAll(_mass_kind(m))),
    (re.compile(r"they can't be regenerated\.", re.I), lambda m: CannotRegenerate()),
    (re.compile(rf"exile all {_MASS}\.", re.I), lambda m: ExileAll(_mass_kind(m))),
    (re.compile(rf"{_SELF} deals {_N} damage to each (creature you don't control|creature|opponent|player)"
                r"(?: and each (opponent|player))?\.", re.I), _damage_each),
    (re.compile(r"each (opponent|player) sacrifices a creature\.", re.I), lambda m: EachSacrifices(m[1].lower())),
    (re.compile(r"target (player|opponent) sacrifices a creature\.", re.I), lambda m: TargetSacrifices(m[1].lower())),
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
    (re.compile(r"(?i:create) (.+)\."), lambda m: _create(m, follows=False)),
    (re.compile(r"(?i:its controller creates) (.+)\."), lambda m: _create(m, follows=True)),
    (re.compile(r"its controller gains life equal to its power\.", re.I), lambda m: TargetControllerGainsLifeEqualToPower()),
    (re.compile(r"its controller may search their library for a basic land card, put (?:it|that card) onto the "
                r"battlefield tapped, then shuffle\.", re.I), lambda m: TargetControllerMayFetchBasicLand()),
    (re.compile(r"search your library for a basic land card, put (?:it|that card) onto the battlefield tapped, "
                r"then shuffle\.", re.I),
     lambda m: FetchBasicLand()),
]


def _parse(sentences: list[str]) -> list | None:
    effects = []
    for sentence in sentences:
        for pattern, build in _TEMPLATES:
            match = pattern.fullmatch(sentence)
            effect = build(match) if match else None
            if effect is not None:
                effects.append(effect)
                break
        else:
            return None
    return effects


def spell_effects(card: Card) -> list | None:
    """Effects of an instant or sorcery, in order; None if any sentence isn't understood. A modal spell
    ("Choose one — ...") gives a single Modal effect."""
    lines = rules_lines(card)
    if lines and (m := _MODAL_HEADER.fullmatch(lines[0])):
        return _parse_modal(m[1].lower(), lines[1:])
    return _parse(_split_sentences(_rules_text(card)))


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


@dataclass(frozen=True)
class Watch:
    """What a watching trigger looks for."""
    kind: str  # "creature", "land", "artifact", "enchantment"; for casts "spell", "creature spell", ...
    other: bool = False  # "another": not the source itself
    yours: bool = False  # "you control" / "under your control"
    nontoken: bool = False


_TRIGGERS = {
    "enters": re.compile(rf"When(?:ever)? {_SELF} enters(?: the battlefield)?, (.+)", re.I),
    "dies": re.compile(rf"When(?:ever)? {_SELF} dies, (.+)", re.I),
    "attacks": re.compile(rf"Whenever {_SELF} attacks, (.+)", re.I),
    "combat_damage_to_player": re.compile(rf"Whenever {_SELF} deals combat damage to a player, (.+)", re.I),
    "upkeep": re.compile(r"At the beginning of your upkeep, (.+)", re.I),
    "end_step": re.compile(r"At the beginning of your end step, (.+)", re.I),
}
TRIGGER_EVENTS = tuple(_TRIGGERS)


_WHO = rf"(?:({_SELF}) or another|(another)|an?)"
_PERMANENT_WATCH = r"(nontoken creature|creature|land|artifact|enchantment)"
_WATCHES = {
    "permanent_enters": re.compile(
        rf"Whenever {_WHO} {_PERMANENT_WATCH}( you control)? enters(?: the battlefield)?( under your control)?, (.+)", re.I),
    "creature_dies": re.compile(rf"Whenever {_WHO} (nontoken creature|creature)( you control)? dies, (.+)", re.I),
    "cast": re.compile(r"Whenever you cast an? (spell|creature spell|noncreature spell|instant or sorcery spell"
                       r"|artifact spell|enchantment spell), (.+)", re.I),
}
_ABILITY_WORD = re.compile(r"^[A-Z][\w' -]* \u2014 ")  # "Landfall — ", "Constellation — "


def _watch_trigger(line: str) -> tuple[str, Watch, str] | None:
    line = _ABILITY_WORD.sub("", line)
    if m := _WATCHES["cast"].fullmatch(line):
        return "cast", Watch(m[1].lower()), m[2]
    for event in ("permanent_enters", "creature_dies"):
        if m := _WATCHES[event].fullmatch(line):
            self_or_other, another, kind = m[1], m[2], m[3].lower()
            yours = bool(m[4]) or (event == "permanent_enters" and bool(m[5]))
            watch = Watch(kind.removeprefix("nontoken "), other=bool(another) and not self_or_other,
                          yours=yours, nontoken=kind.startswith("nontoken"))
            return event, watch, m[len(m.groups())]
    return None


_RETURN_EXILED = re.compile(rf"When(?:ever)? {_SELF} leaves the battlefield, return the exiled card to the "
                            r"battlefield under its owner's control\.", re.I)


def is_return_exiled_line(line: str) -> bool:
    """The second half of Oblivion Ring: the engine returns the exiled card when the source leaves."""
    return _RETURN_EXILED.fullmatch(line) is not None


@lru_cache(maxsize=None)
def triggered_abilities(card: Card) -> tuple[TriggeredAbility, ...]:
    """The triggered abilities on a permanent whose effects are all understood."""
    abilities = _triggered_abilities(card)
    if any(is_return_exiled_line(line) for line in rules_lines(card)):
        # Two-trigger wording: the enters-the-battlefield exile lasts until this permanent leaves.
        abilities = [
            TriggeredAbility(a.event, tuple(ExileUntilLeaves(e.target, e.another) if isinstance(e, Exile) else e
                                            for e in a.effects), a.optional, a.text, a.watch)
            if a.event == "enters" else a
            for a in abilities]
    return tuple(abilities)


def _triggered_abilities(card: Card) -> list[TriggeredAbility]:
    abilities = []
    for line in _rules_text(card).splitlines():
        line = line.strip()
        if watched := _watch_trigger(line):
            event, watch, rest = watched
            # Here "it"/"that creature" may mean the other object, not the source: not supported yet.
            if re.search(r"\bit\b|\bthat (creature|land|spell)\b", rest, re.I):
                continue
            optional = rest.lower().startswith("you may ")
            rest = rest[len("you may "):] if optional else rest
            effects = _parse(_split_sentences(rest[:1].upper() + rest[1:]))
            if effects is not None:
                abilities.append(TriggeredAbility(event, tuple(effects), optional, line, watch))
            continue
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


_ACTIVATED = re.compile(r"([^:\"]+): (.+)")
_MANA_PART = re.compile(r"(\{(?:\d+|[WUBRGC]|[WUBRGC]/[WUBRGCP])\})+")
_SACRIFICE_SELF = re.compile(rf"Sacrifice {_SELF}", re.I)
_PAY_LIFE = re.compile(rf"Pay {_N} life", re.I)
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


def is_mana_ability(line: str) -> bool:
    return (any(p.fullmatch(line) for p in _MANA_PATTERNS) or _FILTER.fullmatch(line) is not None
            or _PAIN.fullmatch(line) is not None)


def mana_pain(card: Card) -> tuple[frozenset[str], int] | None:
    """For painlands and Talismans ("{T}: Add {G} or {U}. This land deals 1 damage to you."): the types
    that cost damage when produced, and how much."""
    for line in rules_lines(card):
        if m := _PAIN.fullmatch(line):
            return frozenset((m[1], m[2])), _count(m[3])
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
