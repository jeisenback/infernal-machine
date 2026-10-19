"""Effects of the "turns and control" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ...game import Game, Seat


DEMONSTRATE_PROMPT = "Copy it with demonstrate? "  # followed by the spell's name; options are YES_NO


DEMONSTRATE_OPPONENT_PROMPT = "Choose an opponent to also copy "  # followed by the spell's name


@dataclass(frozen=True)
class Demonstrate:
    """Demonstrate: "When you cast this spell, you may copy it. If you do, choose an opponent to also copy it." The
    spell cast is `carried`; each copy's controller chooses new targets."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        spell = game.resolving_item.carried if game.resolving_item is not None else None
        if spell is None or controller.player.choose(DEMONSTRATE_PROMPT + spell.card.name, ["Yes", "No"]) != 0:
            return
        game.copy_spell(spell, controller, new_targets=True)
        opponents = game.opponents(controller)
        if opponents:
            pick = controller.player.choose(DEMONSTRATE_OPPONENT_PROMPT + spell.card.name,
                                            [f"Player: {o.name} (seat {o.index})" for o in opponents])
            game.copy_spell(spell, opponents[pick], new_targets=True)


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
class SylvanLibrary:
    """Sylvan Library: "you may draw two additional cards. If you do, choose two cards in your hand drawn this turn. For each of
    those cards, pay 4 life or put the card on top of your library." """
    life: int = 4

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.sylvan_library(controller, self.life)


@dataclass(frozen=True)
class ExtraLandDrop:
    """Explore: "You may play an additional land this turn." """
    count: int = 1

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if controller.extra_lands_turn != game.turn:
            controller.extra_lands, controller.extra_lands_turn = 0, game.turn
        controller.extra_lands += self.count


@dataclass(frozen=True)
class OpponentsCantCast:
    """Silence: "Your opponents can't cast spells this turn." (Ranger-Captain of Eos: "... noncreature spells ...")"""
    kind: str = ""  # "" for any spell, "noncreature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for opponent in game.opponents(controller):
            opponent.cast_barred = (game.turn, self.kind)


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
class BecomeMonarch:
    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.become_monarch(controller)


@dataclass(frozen=True)
class TakeInitiative:
    """ "You take the initiative." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.take_initiative(controller)
