"""Effects that happen only if something holds, is paid or is won: if/else, kicker, may pay, unless pays, coins and dice (split from spells_and_misc.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..targets import DEAD_SUBJECT, PLAYER, SOURCE, SOURCE_AND_SUBJECT, SUBJECT, binding, target_kind
from .base import Condition
if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class ReflexiveTrigger:
    """ "When you do, if it has four or more quest counters on it, put a +1/+1 counter on target creature you control." (Earthbender
    Ascension): a reflexive trigger (CR 603.12) set up by the effect before it, which always happens. It goes on the stack as an
    ability of its own and chooses its targets then; the intervening "if" is checked as it triggers and resolves (CR 603.4)."""
    effects: tuple
    condition: "Condition | None" = None
    text: str = ""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.reflexive_trigger(controller, self.effects, self.condition, self.text)


@dataclass(frozen=True)
class MayDiscardThen:
    """ "You may discard a card. If you do, <effects>." (Party Thrasher) and "... When you do, <effects>." (Inti, Seneschal of the Sun),
    whose effects are then a reflexive trigger (CR 603.12) that chooses its targets as it goes on the stack."""
    then: tuple
    reflexive: bool = False
    text: str = ""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.may_discard_then(controller, self.then, self.reflexive, self.text)


@dataclass(frozen=True)
class Conditional:
    """ "Then if there are three or more creature cards in your graveyard, this creature becomes prepared.": the effect
    happens only if the condition holds as it resolves."""
    condition: "Condition"
    effect: Any

    @property
    def binds(self) -> str | None:
        return found if (found := binding(self.effect)) in (SOURCE, SUBJECT, PLAYER) else None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.condition_holds(self.condition, controller, game.resolving_source):
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class IfElse:
    """ "If you control a Demon, each opponent loses 2 life and you gain 2 life." and, folded in, "Otherwise, you lose 2 life." (Unholy
    Annex): `then` if the condition holds as it resolves, else `otherwise`. Neither has a target."""
    condition: "Condition"
    then: tuple
    otherwise: tuple = ()

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for effect in self.then if game.condition_holds(self.condition, controller, game.resolving_source) else self.otherwise:
            effect.resolve(game, controller, target)


@dataclass(frozen=True)
class _Otherwise:
    effects: tuple


@dataclass(frozen=True)
class RollTable:
    """ "Roll a d20." and its table (CR 706.2): "1\u20149 | Create a Treasure token. 10\u201419 | ... 20 | ...": the row the result falls
    in happens. `rows` are (lowest, highest, effects); no effect of a row has a target or acts on the ability's source."""
    sides: int
    rows: tuple

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        result = game.roll_die(controller, self.sides)
        for low, high, effects in self.rows:
            if low <= result <= high:
                for effect in effects:
                    effect.resolve(game, controller, None)


@dataclass(frozen=True)
class RollDie:
    """ "Roll a d20." (CR 706): the result is what "equal to the result" and "where X is the result" read (`Game.die_result`)."""
    sides: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.roll_die(controller, self.sides)


@dataclass(frozen=True)
class FlipUntilLose:
    """ "Flip a coin until you lose a flip." (Okaun, Zndrsplt, Mirror March, Crazed Firecat: "... for each flip you won")"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.flip_until_lose(controller)


@dataclass(frozen=True)
class FlipCoin:
    """ "Flip a coin." (CR 705) and, folded in, "If you lose the flip, this artifact deals 3 damage to you." (Mana Crypt): `then` happens
    when the flip is won (`on_win`) or lost. Krark, the Thumbless says both: `otherwise` happens on the other result."""
    then: Any = None
    on_win: bool = True
    otherwise: Any = None

    @property
    def binds(self) -> str | None:
        return found if self.then is not None and (found := binding(self.then)) in (SOURCE, SUBJECT, PLAYER) else None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        won = game.flip_coin(controller)
        if self.then is not None and won == self.on_win:
            self.then.resolve(game, controller, target)
        elif self.otherwise is not None and won != self.on_win:
            self.otherwise.resolve(game, controller, target)


@dataclass(frozen=True)
class _IfFlip:
    """ "If you win the flip, ..." / "If you lose the flip, ..." after "Flip a coin." (see _CONDITIONAL)."""
    on_win: bool
    effect: Any


@dataclass(frozen=True)
class _IfYouDo:
    """ "If you do, <effect>." after an effect that can be declined or fail (see _merge_conditional)."""
    effect: Any


@dataclass(frozen=True)
class UnlessPays:
    """ "Draw a card unless that player pays {1}": the effects happen unless the player who set the trigger off pays.
    Only for effects that need no target, so they run the same either way."""
    effects: tuple
    cost: str
    binds = PLAYER
    cost_power: bool = False  # Esper Sentinel: "{X}, where X is this creature's power"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        cost = self.cost
        if self.cost_power:
            source = game.resolving_source
            cost = "{%d}" % (game.power(source) if source is not None and game.on_battlefield(source) else 0)
        item = game.resolving_item
        if target is not None and item is not None and game.pays_unless(target, cost, item.card):
            return
        for effect in self.effects:
            effect.resolve(game, controller, None)


@dataclass(frozen=True)
class IfKicked:
    """"If this spell was kicked, draw a card.": the effect happens only if the kicker cost was paid.
    `kicker` names one of two kicker costs: "If this spell was kicked with its {1}{B} kicker, ..." """
    effect: Any
    kicker: str = ""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None and game.resolving_item.kicked:
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class IfAdditionalCostPaid:
    """"If this spell's additional cost was paid, you gain 2 life." (Requiting Hex): the effect happens only if the optional
    additional cost was paid; like IfKicked, it is settled as the spell is cast (`additional_paid_effects`)."""
    effect: Any

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None and game.resolving_item.additional_paid:
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class KickedInstead:
    """"If this spell was kicked, it deals 4 damage instead.": when kicked, the previous effect's `field`
    (its damage, number of tokens or cards) becomes `value`."""
    field: str
    value: int | str


@dataclass(frozen=True)
class IfNotKicked:
    """ "If the gift wasn't promised, you lose 2 life.": the effect happens only if the spell was not kicked (or its gift not promised)."""
    effect: Any

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None and not game.resolving_item.kicked:
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class _KickedInsteadTail:
    """ "If this spell was kicked, that creature gets -5/-5 until end of turn instead." (see _parse): what stands in for the effect before
    it, with "that creature" the target of that effect."""
    text: str


@dataclass(frozen=True)
class KickedReplaces:
    """ "If the gift was promised, instead counter target spell.": when kicked (or its gift promised) these effects stand in for the
    effect just before."""
    effects: tuple


@dataclass(frozen=True)
class MayPay:
    """Trudge Garden, Veinwitch Coven: "You may pay {2}. If you do, <effect>." The effect is one that may have a target, chosen
    when the ability goes on the stack either way."""
    cost: str
    effect: Any

    @property
    def target(self) -> str | None:
        return target_kind(self.effect)

    @property
    def binds(self) -> str | None:
        return found if (found := binding(self.effect)) in (SOURCE, SUBJECT, SOURCE_AND_SUBJECT, DEAD_SUBJECT, PLAYER) else None  # as Conditional

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if game.pays_optional(controller, self.cost, item.card if item is not None else None):
            self.effect.resolve(game, controller, target)


@dataclass(frozen=True)
class MayPayCountersOnSubject:
    """Emiel the Blessed: "Whenever another creature you control enters, you may pay {G/W}. If you do, put a +1/+1 counter on it. If
    it's a Unicorn, put two +1/+1 counters on it instead." The creature that entered is the subject; the payment is chosen as the
    ability resolves, and only a Unicorn (a creature with the type) gets the second counter."""
    cost: str
    subtype: str
    binds = SUBJECT

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:  # it left the battlefield before the ability resolved
            return
        item = game.resolving_item
        if game.pays_optional(controller, self.cost, item.card if item is not None else None):
            game.put_counters(target, "+1/+1", 2 if self.subtype in target.card.type_line.partition("\u2014")[2].split() else 1)


@dataclass(frozen=True)
class MayPayLoot:
    """Conspiracy Theorist: "You may pay {1} and discard a card. If you do, draw a card." """
    cost: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if controller.hand and game.pays_optional(controller, self.cost, item.card if item is not None else None):
            game.discard(controller, 1)
            game.draw(controller, 1)
