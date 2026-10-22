"""Effects of the "counters" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TYPE_CHECKING

from ...characteristics import Modifier
from ..common import Quantity
from ..targets import PREVIOUS_TARGET, SOURCE
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class PutCounters:
    count: Quantity
    counter: str  # "+1/+1" or "-1/-1"
    target: str
    another: bool = False  # "on another target creature you control": not the source itself
    optional_target: bool = False  # "on each of up to two target creatures": each target may be left out
    distinct: bool = False  # ... and may not repeat an earlier target of the same effect
    grant: frozenset[str] = frozenset()  # Pack a Punch: "It gains trample until end of turn." (it is the creature that got them)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))
            if self.grant:
                game.modify_until_end_of_turn(target, Modifier(keywords=self.grant))
            if game.resolving_item is not None and game.resolving_item.carried is None:
                game.resolving_item.carried = target  # "Then it fights ...": the creature that got the counters


@dataclass(frozen=True)
class RemoveCounters:
    """ "Remove a +1/+1 counter from target creature." / "Remove all counters from target permanent." (count None: all;
    counter None: of every kind)"""
    count: int | str | None
    counter: str | None
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.remove_counters(target, self.counter, None if self.count is None else game.amount(self.count))


@dataclass(frozen=True)
class RemoveAllCountersDraw:
    """Nexus Mentality: "Remove all counters from target nonland permanent you control. Draw a card for each counter removed
    this way." """
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            removed = sum(target.counters.values())
            game.remove_counters(target, None, None)
            game.draw(controller, removed)


PUT_COUNTERS_PROMPT = PromptKind("put_counters", "Put counters on which creature you control for ")  # followed by the source's name


@dataclass(frozen=True)
class PutCountersOnChosenCreature:
    """Breena: "you put two +1/+1 counters on a creature you control." Nothing is targeted; you choose as it resolves."""
    count: Quantity
    counter: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creatures = [p for p in controller.battlefield if "Creature" in p.card.type_line]
        if not creatures:
            return
        source = game.resolving_item.card.name if game.resolving_item is not None else "the ability"
        pick = controller.player.choose(PUT_COUNTERS_PROMPT(source), [game.label(p) for p in creatures]) if len(creatures) > 1 else 0
        game.put_counters(creatures[pick], self.counter, game.amount(self.count))


DISTRIBUTE_PROMPT = PromptKind("distribute", "Put a counter on which creature for ")  # followed by the source's name


@dataclass(frozen=True)
class DistributeCounters:
    """ "Distribute three +1/+1 counters among one, two, or three target creatures you control." The counters are given out one at
    a time as the effect resolves, to any creature of the kind (so any split among any number of them is possible). Nothing is
    targeted, but a creature that couldn't be targeted (hexproof, protection from the source) is left out all the same."""
    count: int | str
    counter: str
    kind: str  # "creature" or "creature you control"
    another: bool = False  # "other target creatures": not the source itself

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        source = game.resolving_item.card.name if game.resolving_item is not None else "the ability"
        for _ in range(game.amount(self.count)):
            options = [p for _, p in game.target_options(self.kind, controller, game.resolving_colors)]
            options = [p for p in options if not (self.another and p is game.resolving_source)]
            if not options:
                return
            pick = controller.player.choose(DISTRIBUTE_PROMPT(source), [game.label(p) for p in options]) if len(options) > 1 else 0
            game.put_counters(options[pick], self.counter, 1)


@dataclass(frozen=True)
class PutCountersOnEachUpToX:
    """Silkguard: "Put a +1/+1 counter on each of up to X target creatures you control." The targets are one list."""
    counter: str
    target: str = "creature you control"
    grant: frozenset[str] = frozenset()  # "Those creatures gain flying until end of turn."
    up_to_x = True
    multi_target = True  # its one target slot holds a list
    optional_target = True  # it needs no target to be cast

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in target or []:
            game.put_counters(permanent, self.counter, 1)
            if self.grant:
                game.modify_until_end_of_turn(permanent, Modifier(keywords=self.grant))


@dataclass(frozen=True)
class PutCounterPerPlayer:
    """Nils: "For each player, put a +1/+1 counter on up to one target creature that player controls." The targets are one
    list, a creature (or none) for each player in turn order."""
    counter: str
    target: str = "creature"
    per_player = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in target or []:
            game.put_counters(permanent, self.counter, 1)


@dataclass(frozen=True)
class MoveCountersFrom:
    """The first target of "Move a +1/+1 counter from target creature onto another target creature." """
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = target


MOVE_COUNTERS_PROMPT = PromptKind("move_counters", "Move how many ")  # followed by the counter's name; options are "0", "1", ...


SHIFT_COUNTERS_PROMPT = PromptKind("shift_counters", "Shift how many counters off ")  # then the creature's name; options are "0", "1", ... (a bot keeps them)


SHIFT_ONTO_PROMPT = PromptKind("shift_onto", "Shift them onto which creature? ")  # followed by the source's name


@dataclass(frozen=True)
class MoveCountersToOthers:
    """Forgotten Ancient: "you may move any number of +1/+1 counters from this creature onto other creatures." (nothing is
    targeted: you choose how many, and where, as it resolves)"""
    counter: str
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        while (have := target.counters.get(self.counter, 0)) > 0:
            others = [p for s in game.live_seats() for p in s.battlefield if "Creature" in p.card.type_line and p is not target]
            if not others:
                return
            number = controller.player.choose(SHIFT_COUNTERS_PROMPT(target.card.name), [str(n) for n in range(have + 1)])
            if number == 0:
                return
            pick = controller.player.choose(SHIFT_ONTO_PROMPT(target.card.name), [game.label(p) for p in others])
            game.move_counters(target, others[pick], self.counter, number)


@dataclass(frozen=True)
class MoveCountersOnto:
    """The second target: the counters (up to `count`, or all if None) move from the first target to this one."""
    count: int | Literal["any"] | None  # a number, None for all of them, or "any" for a number the controller chooses
    counter: str | None  # None: every kind
    target: str
    another: bool = True
    same_controller: bool = False  # "... with the same controller": the second creature is under the first one's controller
    distinct: bool = True  # "another target": not the creature the counters come from

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        first = game.resolving_item.carried if game.resolving_item is not None else None
        if first is not None and target is not None and first is not target:
            count = self.count
            if count == "any":
                have = first.counters.get(self.counter, 0)
                count = controller.player.choose(MOVE_COUNTERS_PROMPT(f"{self.counter} counters"),
                                                 [str(n) for n in range(have + 1)])
            game.move_counters(first, target, self.counter, count)


@dataclass(frozen=True)
class RemoveCountersFromSource:
    """ "Remove two hour counters from this enchantment." (Midnight Oil)"""
    count: int
    counter: str
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.remove_counters(target, self.counter, self.count)


@dataclass(frozen=True)
class DoubleCountersOnSource:
    """ "Double the number of +1/+1 counters on this creature." """
    counter: str
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.counters.get(self.counter):
            game.put_counters(target, self.counter, target.counters[self.counter])


@dataclass(frozen=True)
class DoubleCounters:
    """ "Double the number of +1/+1 counters on each creature you control." """
    counter: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if "Creature" in permanent.card.type_line and permanent.counters.get(self.counter):
                game.put_counters(permanent, self.counter, permanent.counters[self.counter])


@dataclass(frozen=True)
class PutCountersOnEach:
    """ "Put a +1/+1 counter on each creature you control." (or each Vampire you control: `kind`) """
    count: Quantity
    counter: str
    kind: str = ""  # a creature type, "" for every creature
    grant: frozenset[str] = frozenset()  # Ursine Guide's spell: "They gain trample until end of turn."
    or_vehicle: bool = False  # Ao: "each permanent you control that's a creature or Vehicle"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in list(controller.battlefield):
            if ("Creature" in permanent.card.type_line or self.or_vehicle and "Vehicle" in permanent.card.type_line) \
                    and self.kind in permanent.card.type_line:
                game.put_counters(permanent, self.counter, game.amount(self.count))
                if self.grant:
                    game.modify_until_end_of_turn(permanent, Modifier(keywords=self.grant))


@dataclass(frozen=True)
class PutCountersOnEntered:
    """Oran-Rief: "Put a +1/+1 counter on each green creature that entered this turn." (any player's)"""
    counter: str
    color: str = ""  # "G"; "" for any creature

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.live_seats():
            for permanent in list(seat.battlefield):
                if permanent.entered_turn == game.turn and "Creature" in permanent.card.type_line \
                        and (not self.color or self.color in permanent.card.colors):
                    game.put_counters(permanent, self.counter, 1)


@dataclass(frozen=True)
class PutCountersOnSource:
    """ "Whenever this creature attacks, put a +1/+1 counter on it." """
    count: Quantity
    counter: str
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, self.counter, game.amount(self.count))


@dataclass(frozen=True)
class Hideaway:
    """Hideaway N: "When this enters, look at the top N cards of your library, exile one face down, then put the rest on
    the bottom in a random order." """
    count: int
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.hideaway(controller, target, self.count)


@dataclass(frozen=True)
class VowCounters:
    """Promise of Loyalty: "Each player puts a vow counter on a creature they control and sacrifices the rest. Each of
    those creatures can't attack you or planeswalkers you control for as long as it has a vow counter on it." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            creatures = [p for p in seat.battlefield if "Creature" in p.card.type_line]
            if not creatures:
                continue
            keep = creatures[seat.player.choose(VOW_PROMPT, [game.label(p) for p in creatures])]
            keep.counters["vow"] = keep.counters.get("vow", 0) + 1
            keep.vow_of = controller
            game._leave_together([(p, "sacrificed") for p in creatures if p is not keep])


VOW_PROMPT = PromptKind("vow", "Choose the creature that gets the vow counter")


@dataclass(frozen=True)
class DoubleCountersOnTarget:
    """ "Double the number of +1/+1 counters on target creature." """
    counter: str
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.counters.get(self.counter):
            game.put_counters(target, self.counter, target.counters[self.counter])


@dataclass(frozen=True)
class LevelUp:
    """Class: "{1}{B}: Level 2": the Class gains the next level (only at sorcery speed, and only the level after its own)."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.class_level_up(target)


@dataclass(frozen=True)
class EachExilesGraveyardCardCounters:
    """Augusta, Order Returned: "each player exiles a card from their graveyard. When one or more nonland cards are exiled this way,
    put that many +1/+1 counters on target attacking creature." (the target is chosen with the trigger)"""
    target: str = "attacking creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = game.each_player_exiles_graveyard_card(controller)
        if count and target is not None and game.on_battlefield(target):
            game.put_counters(target, "+1/+1", count)


@dataclass(frozen=True)
class DoubleCountersOnTargets:
    """Kinetic Ooze: "If X is 10 or more, double the number of +1/+1 counters on any number of other target creatures." Targets
    are chosen whatever X is; nothing is doubled below `min_x`."""
    counter: str
    target: str
    min_x: int
    another = True
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.x_value < self.min_x:
            return
        for creature in target or []:
            if game.on_battlefield(creature) and creature.counters.get(self.counter):
                game.put_counters(creature, self.counter, creature.counters[self.counter])


@dataclass(frozen=True)
class DoubleAllCountersOnTargets:
    """Deepglow Skate: "double the number of each kind of counter on any number of target permanents." Each kind is put again, so a
    counter doubler doubles it once more."""
    target: str
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in target or []:
            if game.on_battlefield(permanent):
                for counter, count in list(permanent.counters.items()):
                    if count > 0:
                        game.put_counters(permanent, counter, count)


@dataclass(frozen=True)
class Amass:
    """Orcish Bowmasters: "Amass Orcs 1." Put that many +1/+1 counters on an Army you control; without one, create a 0/0 black
    Army creature token first. The Army is also an Orc."""
    count: int
    kind: str = ""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.amass(controller, self.count, self.kind)


@dataclass(frozen=True)
class TargetPutsCountersOnEach:
    """Shadrix Silverquill: "Target player puts a +1/+1 counter on each creature they control." """
    counter: str
    target: str = "player"
    distinct: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            for permanent in list(target.battlefield):
                if "Creature" in permanent.card.type_line:
                    game.put_counters(permanent, self.counter, 1)


@dataclass(frozen=True)
class ExileWithTimeCounters:
    """Rousing Refrain: "Exile Rousing Refrain with three time counters on it." The spell is suspended instead of going
    to the graveyard once it has resolved."""
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.suspend_after = self.count


@dataclass(frozen=True)
class PutCounterOnHost:
    """Seismic Tutelage: "When this Aura enters, put a +1/+1 counter on enchanted creature." """
    count: int
    counter: str
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.attached_to is not None:
            game.put_counters(target.attached_to, self.counter, self.count)


@dataclass(frozen=True)
class OpponentsLoseCounters:
    """Final Act: "Each opponent loses all counters." (the counters on players: poison, energy, experience, ...)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for opponent in game.opponents(controller):
            opponent.player_counters.clear()


@dataclass(frozen=True)
class _PutCountersAndAttach:
    """The second sentence of Fractal Harness: "Put X +1/+1 counters on it and attach this Equipment to it." """
    count: int | str
    counter: str


@dataclass(frozen=True)
class PutStunOnSource:
    """ "Put three stun counters on it." in a trigger of the creature itself (Pugnacious Hammerskull, Ambling Stormshell)."""
    count: int | str = 1
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, "stun", game.amount(self.count))


@dataclass(frozen=True)
class PutStunCounters:
    """ "Put a stun counter on it." / "... on that creature.": the target of the effect before it."""
    count: int | str = 1
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.put_counters(target, "stun", game.amount(self.count))


@dataclass(frozen=True)
class PutStunOnEach:
    """ "Put a stun counter on each of them." after "Tap up to two target creatures.": _merge_stun puts a stun counter after
    each tap, so this is never resolved itself."""
    count: int | str = 1

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class Proliferate:
    """ "Proliferate.": choose any permanents with counters; each gets one more counter of each kind it has."""
    times: int | str = 1  # "Proliferate X times."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for _ in range(game.amount(self.times)):
            game.proliferate(controller)
