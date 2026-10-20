"""Effects of the "destroy and sacrifice" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..targets import MassFilter, SOURCE
from .exile_and_return import GiveBack
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class Destroy:
    target: str
    another: bool = False  # "destroy another target ...": not the source itself
    no_regen: bool = False  # "It can't be regenerated."
    optional_target: bool = False  # "destroy up to two target ...": each target may be left out
    distinct: bool = False  # ... and may not repeat an earlier target of the same effect
    if_color: str = ""  # Pyroblast: "Destroy target permanent if it's blue." (checked as it resolves)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and (not self.if_color or self.if_color in target.card.colors):
            game.destroy(target, self.no_regen)


@dataclass(frozen=True)
class MaySacrificeThen:
    """Springbloom Druid: "You may sacrifice a land. If you do, search your library for up to two basic land cards, ..." """
    kind: str
    then: Any

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.may_sacrifice(controller, self.kind):
            self.then.resolve(game, controller, target)


@dataclass(frozen=True)
class _MaySacrifice:
    """Half of "You may sacrifice a permanent. If you do, draw two cards." (see _merge_loot)."""
    kind: str


CHOOSE_TYPE_PROMPT = PromptKind("choose_a_type", "Choose a type")  # options: the types that can be chosen (Season of Gathering)


@dataclass(frozen=True)
class DestroyAllOfChosenType:
    """Season of Gathering: "Choose artifact or enchantment. Destroy all permanents of the chosen type." """
    kinds: tuple[str, ...]  # what can be chosen

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        kind = self.kinds[controller.player.choose(CHOOSE_TYPE_PROMPT, [k.capitalize() for k in self.kinds])]
        game.destroy_all(game.mass_targets(kind, controller), False, None, controller)


@dataclass(frozen=True)
class _SacrificeThemLater:
    """ "Sacrifice them at the beginning of the next end step.": only ever after TokensJoinAttack."""


@dataclass(frozen=True)
class DestroyAll:
    """ "Destroy all creatures." Indestructible permanents survive; they all die together."""
    kind: str  # "creature", "artifact or enchantment", "creature you don't control", ...
    restriction: MassFilter | None = None  # "... with flying"
    no_regen: bool = False  # "They can't be regenerated."
    gives: "GiveBack | None" = None  # "For each creature destroyed this way, its controller creates a 1/1 token"
    mana_each: frozenset[str] = frozenset()  # Culling Ritual: "Add {B} or {G} for each permanent destroyed this way."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        destroyed = game.destroy_all(game.mass_targets(self.kind, controller, self.restriction), self.no_regen, self.gives, controller)
        if self.mana_each:
            game.add_mana(controller, tuple(self.mana_each for _ in destroyed))


@dataclass(frozen=True)
class DestroyX:
    """Immoral Bargain: "Destroy X target nonland permanents." Exactly X targets, in one list."""
    target: str
    up_to_x = True
    exact_x = True
    multi_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.destroy_all(list(target or []))


@dataclass(frozen=True)
class DestroyUpToX:
    """Pest Infestation: "Destroy up to X target artifacts and/or enchantments." Up to X targets, in one list."""
    target: str
    up_to_x = True
    multi_target = True
    optional_target = True  # it needs no target to be cast

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.destroy_all(list(target or []))


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
    binds = SOURCE

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
class SacrificeSelf:
    """Evoke: "When this creature enters, sacrifice it." """
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game._leave_battlefield(target, "sacrificed")


@dataclass(frozen=True)
class SacrificeCreature:
    """ "Sacrifice a creature." (you choose which) """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.sacrifice(controller)


@dataclass(frozen=True)
class EachSacrifices:
    """ "Each opponent sacrifices a creature." / "Each player sacrifices a land." """
    who: str  # "opponent", "player" or "you" ("Sacrifice two lands.")
    kind: str = "creature"  # "creature", "artifact", "enchantment", "land", "permanent", "nonland permanent", ...
    count: int | str | None = 1  # "two lands"; None: "all creatures they control"
    greatest: bool = False  # "a creature with the greatest power among creatures they control"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "player" or (self.who == "you") == (seat is controller):
                game.sacrifice(seat, self.kind, None if self.count is None else game.amount(self.count), self.greatest)


@dataclass(frozen=True)
class TragicArrogance:
    """Tragic Arrogance: "For each player, you choose from among the permanents that player controls an artifact, a creature, an
    enchantment, and a planeswalker. Then each player sacrifices all other nonland permanents they control." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tragic_arrogance(controller)


@dataclass(frozen=True)
class SacrificeAll:
    """ "Sacrifice all creatures you control." """
    kind: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.sacrifice(controller, self.kind, None)


@dataclass(frozen=True)
class TargetSacrifices:
    """ "Target player sacrifices a creature." (target is "player" or "opponent") """
    target: str
    kind: str = "creature"
    greatest: bool = False  # "a creature with the greatest power among creatures they control" (Consumed by Greed)

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.sacrifice(target, self.kind, greatest=self.greatest)


@dataclass(frozen=True)
class SacrificeUnlessPay:
    """Gateway Plaza and the like: "When this land enters, sacrifice it unless you pay {1}." """
    cost: str
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.on_battlefield(target) and not game.pays_unless(controller, self.cost, target.card):
            game._leave_battlefield(target, "sacrificed")
