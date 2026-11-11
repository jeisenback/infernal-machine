"""Effects that tap, untap, fight, goad or force a creature to attack or block (split from combat_and_pump.py)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..targets import PREVIOUS_TARGET, SOURCE, SUBJECT
from .base import Condition
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


UNTAP_CREATURE_PROMPT = PromptKind("untap_creature", "Untap which creature? ")


UNTAP_LANDS_PROMPT = PromptKind("untap_lands", "Untap which land? ")


DONE = "Done"


@dataclass(frozen=True)
class TapOrUntap:
    """ "You may tap or untap target creature." """
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap_or_untap(controller, target)


@dataclass(frozen=True)
class TapAndGoad:
    """Killian, Decisive Mentor: "Tap up to one target creature and goad it." """
    target: str = "creature"
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)
            game.goad(target, controller)


@dataclass(frozen=True)
class _UntapThatLand:
    """ "Then if you control four or more lands, untap that land." """
    condition: "Condition"


@dataclass(frozen=True)
class _UntapThoseLands:
    """Spell mastery: "If there are two or more instant and/or sorcery cards in your graveyard, untap those lands." """
    condition: "Condition"


@dataclass(frozen=True)
class UntapThat:
    """ "Untap that creature." Only meaningful right after "Gain control of ...": _merge_control folds it in."""
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        pass


@dataclass(frozen=True)
class Tap:
    """ "Tap two target permanents.": one effect per target, each a different permanent."""
    target: str
    distinct: bool = False
    optional_target: bool = False
    strip_while_source: bool = False  # The Wondrous Wasp: "It loses all abilities for as long as CARDNAME remains on the battlefield."
    lock_while_tapped: bool = False  # Braided Net: "Its activated abilities can't be activated for as long as it remains tapped."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)
            if self.lock_while_tapped:
                target.locked_while_tapped = True
            if self.strip_while_source:
                game.strip_while(target, game.resolving_source)


@dataclass(frozen=True)
class _LockedWhileTapped:
    """ "Its activated abilities can't be activated for as long as it remains tapped." after a Tap (Braided Net)."""


@dataclass(frozen=True)
class _LosesAbilitiesWhileSource:
    """ "It loses all abilities for as long as CARDNAME remains on the battlefield." after a Tap (The Wondrous Wasp)."""


@dataclass(frozen=True)
class LureThisTurn:
    """Roar of Challenge: "All creatures able to block target creature this turn do so." """
    target: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.lured_turn = game.turn


@dataclass(frozen=True)
class AttackDespiteDefender:
    """ "This creature can attack this turn as though it didn't have defender." (Skyclave Squid, Krotiq Nestguard): the ability's source."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.defender_ok_turn = game.turn  # CR 702.3b: it attacks as though it had no defender, this turn only


@dataclass(frozen=True)
class MustBlockThisTurn:
    """ "Target creature blocks this turn if able." / "... blocks this creature this turn if able." (Torchling: that creature in
    particular, the source of the ability)"""
    target: str = "creature"
    source_only: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.must_block_turn = game.turn
            target.must_block_what = game.resolving_source if self.source_only else None


@dataclass(frozen=True)
class TapThat:
    """ "Tap it." / "Tap that creature.": the target of the effect before it."""
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.tap(target)


@dataclass(frozen=True)
class DoesntUntapNext:
    """Sleep of the Dead: "Tap target creature. It doesn't untap during its controller's next untap step." (Permanent.skips_next_untap)"""
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            target.skips_next_untap = True


@dataclass(frozen=True)
class AttackersDontUntapNext:
    """Tangle: "Each attacking creature doesn't untap during its controller's next untap step." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for attack in game.combat.attacks:
            attack.attacker.skips_next_untap = True


@dataclass(frozen=True)
class FightFirst:
    """The first target of a fight ("Target creature you control ... fights ..."): remembered for the second."""
    target: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = target


@dataclass(frozen=True)
class FightSourceFirst:
    """ "When this creature enters, it fights up to one target creature you don't control.": the creature that fights is the source."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.resolving_item is not None:
            game.resolving_item.carried = target


@dataclass(frozen=True)
class FightSubjectFirst:
    """Frontier Siege: "Whenever a creature you control with flying enters, you may have it fight target creature you don't control.":
    the creature that set the trigger off is the one that fights."""
    binds = SUBJECT

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
    optional_target: bool = False  # "fights up to one target creature"
    follows: bool = False  # "It fights ...": the creature the sentence before it targeted, or the source if nothing did (see _merge_conditional)
    then: bool = False  # "Then it fights ...": there has to be a sentence before it, it is never the source

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        first = game.resolving_item.carried if game.resolving_item is not None else None
        if first is not None and target is not None and first is not target:
            game.fight(first, target, self.one_sided)


@dataclass(frozen=True)
class UntapCreatures:
    which: str  # "attacked": the creatures that attacked this turn; "yours": every creature you control

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for permanent in controller.battlefield:
            if "Creature" in permanent.card.type_line and (self.which == "yours" or permanent.attacked_turn == game.turn):
                game.untap(permanent)


@dataclass(frozen=True)
class UntapACreature:
    """White Plume Adventurer: "Untap a creature you control." (you choose, not a target); with `all_if`, "If you've completed a dungeon,
    untap all creatures you control instead." (see _CONDITIONAL)."""
    all_if: Condition | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if self.all_if is not None and game.condition_holds(self.all_if, controller):
            UntapCreatures("yours").resolve(game, controller, target)
            return
        tapped = [p for p in controller.battlefield if p.tapped and "Creature" in p.card.type_line]
        if tapped:
            game.untap(tapped[controller.player.choose(UNTAP_CREATURE_PROMPT, [game.label(p) for p in tapped])])


@dataclass(frozen=True)
class _InsteadUntapAll:
    """ "If you've completed a dungeon, untap all creatures you control instead." after UntapACreature."""
    condition: Condition


@dataclass(frozen=True)
class Untap:
    """ "Untap target land." """
    target: str
    another: bool = False
    optional_target: bool = False  # "Untap up to two target lands"
    distinct: bool = False
    counter_if_artifact_creature: bool = False  # Tezzeret, Cruel Captain: "If it's an artifact creature, put a +1/+1 counter on it."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.untap(target)
            if self.counter_if_artifact_creature and "Artifact" in target.card.type_line and "Creature" in target.card.type_line:
                game.put_counters(target, "+1/+1", 1)


@dataclass(frozen=True)
class UntapLands:
    """ "Untap up to three lands." (Frantic Search, Snap): you choose, not a target."""
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for _ in range(self.count):
            tapped = [p for p in controller.battlefield if p.tapped and "Land" in p.card.type_line]
            if not tapped:
                return
            choice = controller.player.choose(UNTAP_LANDS_PROMPT, [game.label(p) for p in tapped] + [DONE])
            if choice >= len(tapped):
                return
            game.untap(tapped[choice])
            game.broadcast({"event": "untapped", "seat": controller.index, "card": tapped[choice].card.name})


@dataclass(frozen=True)
class UntapSource:
    """ "Untap it" / "Untap this creature": the ability's source (or, in a watching trigger, the permanent that set it off)."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.untap(target)


@dataclass(frozen=True)
class UntapAll:
    """ "Untap all lands you control." """
    kind: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.untap_all(controller, self.kind)


@dataclass(frozen=True)
class TapAll:
    """ "Tap all creatures your opponents control." Naya Charm: "... target player controls." (`target` "player")"""
    target: str | None = None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in ([target] if target is not None else []) if self.target else game.opponents(controller):
            for permanent in seat.battlefield:
                if "Creature" in permanent.card.type_line:
                    game.tap(permanent)


@dataclass(frozen=True)
class TapEnchanted:
    """An Aura's "When this Aura enters, tap enchanted creature." (Infinite Coursework adds "It becomes unprepared.") With `untap`,
    Freed from the Real's "{U}: Untap enchanted creature." """
    unprepare: bool = False
    untap: bool = False
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        host = target.attached_to if target is not None else None
        if host is not None and game.on_battlefield(host) and self.untap:
            game.untap(host)
        elif host is not None and game.on_battlefield(host):
            game.tap(host)
            if self.unprepare:
                game.unprepare(host)


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
