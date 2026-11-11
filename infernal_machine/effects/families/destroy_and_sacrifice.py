"""Effects of the "destroy and sacrifice" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..targets import MassFilter, SOURCE
from .exile_and_return import GiveBack
from ...prompts import PromptKind

if TYPE_CHECKING:
    from ...game import Game, Seat
    from .base import Condition
    from ...cards import Card


@dataclass(frozen=True)
class Destroy:
    target: str
    another: bool = False  # "destroy another target ...": not the source itself
    no_regen: bool = False  # "It can't be regenerated."
    optional_target: bool = False  # "destroy up to two target ...": each target may be left out
    distinct: bool = False  # ... and may not repeat an earlier target of the same effect
    if_color: str = ""  # Pyroblast: "Destroy target permanent if it's blue." (checked as it resolves)
    if_mana_value: int | None = None  # Fatal Push: "Destroy target creature if it has mana value 2 or less." (checked as it resolves) ...
    instead_mana_value: int | None = None  # ... "Revolt \u2014 Destroy that creature if it has mana value 4 or less instead if ..."
    instead_if: "Condition | None" = None  # ... "a permanent left the battlefield under your control this turn."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or (self.if_color and self.if_color not in target.card.colors):
            return
        most = self.if_mana_value
        if self.instead_if is not None and game.condition_holds(self.instead_if, controller, game.resolving_source):
            most = self.instead_mana_value
        if most is None or target.card.cmc <= most:
            game.destroy(target, self.no_regen)


@dataclass(frozen=True)
class _InsteadManaValue:
    """ "Revolt \u2014 Destroy that creature if it has mana value 4 or less instead if ..." after a Destroy (see _CONDITIONAL)."""
    most: int
    condition: "Condition"


@dataclass(frozen=True)
class MaySacrificeThen:
    """Springbloom Druid: "You may sacrifice a land. If you do, search your library for up to two basic land cards, ..." The Sackville-
    Bagginses: "you may sacrifice another creature or artifact. If you do, draw a card and create a Treasure token." (`then` is a tuple
    of effects; "another" is not the source itself)."""
    kind: str
    then: Any
    another: bool = False

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if game.may_sacrifice(controller, self.kind, exclude=game.resolving_source if self.another else None):
            for effect in self.then if isinstance(self.then, tuple) else (self.then,):
                effect.resolve(game, controller, target)


@dataclass(frozen=True)
class _MaySacrifice:
    """Half of "You may sacrifice a permanent. If you do, draw two cards." (see _merge_loot)."""
    kind: str
    another: bool = False  # "you may sacrifice another creature": not the source itself


CHOOSE_TYPE_PROMPT = PromptKind("choose_a_type", "Choose a type")  # options: the types that can be chosen (Season of Gathering)


@dataclass(frozen=True)
class ChooseTypeRevealTop:
    """Winding Way: "Choose creature or land. Reveal the top four cards of your library. Put all cards of the chosen type revealed this
    way into your hand and the rest into your graveyard." """
    kinds: tuple[str, ...]
    count: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        kind = self.kinds[controller.player.choose(CHOOSE_TYPE_PROMPT, [k.capitalize() for k in self.kinds])]
        revealed = controller.library[:self.count]
        del controller.library[:len(revealed)]
        game.broadcast({"event": "revealed", "seat": controller.index, "cards": [c.name for c in revealed]})
        for card in revealed:
            if kind.capitalize() in card.type_line:
                controller.hand.append(card)
            else:
                game._move_card(controller, card, "graveyard")


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
    life_each: int = 0  # Fumigate: "You gain 1 life for each creature destroyed this way."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        destroyed = game.destroy_all(game.mass_targets(self.kind, controller, self.restriction), self.no_regen, self.gives, controller)
        if self.mana_each:
            game.add_mana(controller, tuple(self.mana_each for _ in destroyed))
        if self.life_each and destroyed:
            game.change_life(controller, self.life_each * len(destroyed))


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
class Vanish:
    """Vanishing (CR 702.63a): "At the beginning of your upkeep, if this permanent has a time counter on it, remove a time counter from it.
    When the last is removed, sacrifice it." """
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.counters.get("time", 0) > 0:
            game.remove_counters(target, "time", 1)
            if not target.counters.get("time", 0):
                game._leave_battlefield(target, "sacrificed")


@dataclass(frozen=True)
class ReturnSelfAtNextEndStep:
    """Sakashima the Impostor's copy: "{2}{U}{U}: Return CARDNAME to its owner's hand at the beginning of the next end step." """
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.leave_at_next_end_step([target], "returned", "hand")


@dataclass(frozen=True)
class ExileSelf:
    """Heat Shimmer's token: "At the beginning of the end step, exile this token." """
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game._leave_together([(target, "exiled")], "exile")


@dataclass(frozen=True)
class SacrificeSelfThenCreate:
    """The Misty Mountains Cold: "Then if you control four or more Treasures, sacrifice this Saga. If you do, create a 6/6 red Dragon
    creature token with flying." """
    condition: "Condition"
    token: "Card"
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None or not game.condition_holds(self.condition, controller, target):
            return
        game._leave_battlefield(target, "sacrificed")
        game.create_tokens(controller, self.token, 1)


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
    greatest_if_evidence: bool = False  # Extract a Confession: "If evidence was collected, instead ... the greatest power ..."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        greatest = self.greatest or (self.greatest_if_evidence and game.resolving_item is not None and game.resolving_item.evidence)
        for seat in game.turn_order_from_active():
            if self.who == "player" or (self.who == "you") == (seat is controller):
                game.sacrifice(seat, self.kind, None if self.count is None else game.amount(self.count), greatest)


@dataclass(frozen=True)
class TragicArrogance:
    """Tragic Arrogance: "For each player, you choose from among the permanents that player controls an artifact, a creature, an
    enchantment, and a planeswalker. Then each player sacrifices all other nonland permanents they control." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.tragic_arrogance(controller)


@dataclass(frozen=True)
class SacrificeAll:
    """ "Sacrifice all creatures you control." X is how many were sacrificed (Hellion Eruption: "then create that many")."""
    kind: str = "creature"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.x_value = len(game.sacrifice(controller, self.kind, None))


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


@dataclass(frozen=True)
class ChosenTypeEffect:
    """Distant Melody, Kindred Dominance, Raise the Palisade: the controller names a creature type as it resolves, then draws for each
    permanent of it they control, or destroys or returns every creature that isn't of it (a changeling is every type)."""
    what: str  # "draw", "destroy" or "bounce"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        item = game.resolving_item
        if item is None:
            return
        kind = game._choose_creature_type(controller, item.card)
        if self.what == "draw":
            game.draw(controller, sum(kind in game.subtypes(p) for p in controller.battlefield))
            return
        others = [p for p in game.mass_targets("creature", controller) if kind not in game.subtypes(p)]
        if self.what == "destroy":
            game.destroy_all(others, caster=controller)
        else:
            game.return_all_to_hand(others)
