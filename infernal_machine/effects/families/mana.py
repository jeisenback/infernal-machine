"""Effects of the "mana" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ..targets import PREVIOUS_TARGET
from .base import Amount, Condition

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class _DelayedMana:
    """Mana Drain's second sentence (see _merge_exile)."""


@dataclass(frozen=True)
class AddDevotionMana:
    """Nyx Lotus: "Choose a color. Add an amount of mana of that color equal to your devotion to that color." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.add_devotion_mana(controller)


@dataclass(frozen=True)
class AddManaPerCardInHand:
    """Rousing Refrain: "Add {R} for each card in target opponent's hand." """
    symbol: str
    target: str = "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.add_mana(controller, tuple(frozenset(self.symbol) for _ in target.hand))


@dataclass(frozen=True)
class AddManaForEach:
    """Battle Hymn, Brightstone Ritual: "Add {R} for each creature you control." / "... for each Goblin on the battlefield." """
    symbol: str
    amount: Amount

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.add_mana(controller, tuple(frozenset(self.symbol) for _ in range(game.evaluate(self.amount, controller))))


@dataclass(frozen=True)
class AddManaPerTappedLand:
    """Mana Geyser: "Add {R} for each tapped land your opponents control." """
    symbol: str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        count = sum(1 for seat in game.opponents(controller) for p in seat.battlefield if p.tapped and "Land" in p.card.type_line)
        game.add_mana(controller, tuple(frozenset(self.symbol) for _ in range(count)))


@dataclass(frozen=True)
class KeepManaThisTurn:
    """ "Until end of turn, you don't lose this mana as steps and phases end." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.keep_pool_turn = game.turn


@dataclass(frozen=True)
class _ManaForEachDestroyed:
    """ "Add {B} or {G} for each permanent destroyed this way." (see _merge_conditional)"""
    options: frozenset[str]


@dataclass(frozen=True)
class PlayersLoseSacrificeAddManaDraw:
    """Priest of Forgotten Gods: "Any number of target players each lose 2 life and sacrifice a creature of their choice. You add {B}{B}
    and draw a card." """
    life: int
    units: tuple[frozenset[str], ...]
    target: str = "player"
    any_number = True
    multi_target = True
    optional_target = True

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in target or []:
            if not seat.lost:
                game.change_life(seat, -self.life)
                game.sacrifice(seat, "creature")
        game.add_mana(controller, self.units)
        game.draw(controller, 1)


@dataclass(frozen=True)
class LoseLifeEqualToManaValue:
    """Reanimate: "You lose life equal to its mana value." (the card the previous effect put onto the battlefield)"""
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(controller, -int(target.card.cmc))


@dataclass(frozen=True)
class AddMana:
    """Ritual: "Add {B}{B}{B}." The mana waits in its controller's pool until the step ends."""
    units: tuple[frozenset[str], ...]
    more: tuple[frozenset[str], ...] = ()  # Cabal Ritual: "Threshold — Add {B}{B}{B}{B}{B} instead if there are seven or more cards in your graveyard."
    more_if: "Condition | None" = None
    per_named: frozenset[str] = frozenset()  # Rite of Flame: one more of these for each card with this spell's name in a graveyard

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        units = self.more if self.more_if and game.condition_holds(self.more_if, controller, game.resolving_source) else self.units
        if self.per_named and game.resolving_item is not None:
            named = sum(c.name == game.resolving_item.card.name for s in game.seats for c in s.graveyard)
            units = units + (self.per_named,) * named
        game.add_mana(controller, units)


@dataclass(frozen=True)
class _InsteadMana:
    """ "Threshold — Add {B}{B}{B}{B}{B} instead if there are seven or more cards in your graveyard." (see _merge_conditional)"""
    condition: "Condition"
    units: tuple[frozenset[str], ...]


@dataclass(frozen=True)
class ExtraMountainMana:
    """Pyre Rhymer's Molten Tide: "Until end of turn, whenever you tap a Mountain for mana, add an additional {R}." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.extra_mountain_mana_turn = game.turn


@dataclass(frozen=True)
class PayLifeForMana:
    """Yavimaya Bloomsage's Channel: "Until end of turn, any time you could activate a mana ability, you may pay 1 life. If
    you do, add {C}." Paying for something uses it automatically, after the mana that costs nothing."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.life_mana_turn = game.turn
