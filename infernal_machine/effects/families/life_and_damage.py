"""Effects of the "life and damage" family (split from outcomes.py; the sentences that make them are still read there)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TYPE_CHECKING

from ...cards import Card
from ...characteristics import Modifier
from ..common import Quantity
from ..targets import (DEAD_SOURCE, MassFilter, PLAYER, PREVIOUS_TARGET, SOURCE)

if TYPE_CHECKING:
    from ...game import Game, Seat


@dataclass(frozen=True)
class GainLife:
    amount: Quantity

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.change_life(controller, game.amount(self.amount))


@dataclass(frozen=True)
class ExileDamagedIfDie:
    """ "If a creature dealt damage this way would die this turn, exile it instead." (Anger of the Gods): every creature the spell
    has dealt damage to."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for creature in game.resolving_damaged:
            creature.exile_if_dies = game.turn


@dataclass(frozen=True)
class PlayerLosesLife:
    """Afflict N: "defending player loses N life", the player the trigger is about."""
    amount: int
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.change_life(target, -self.amount)


@dataclass(frozen=True)
class OpponentsLoseLife:
    amount: Quantity

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            game.change_life(seat, -game.amount(self.amount))


@dataclass(frozen=True)
class Damage:
    amount: Quantity
    target: str
    optional_target: bool = False  # one point of "4 damage divided as you choose among any number of targets"
    distinct: bool = False  # "... to each of up to two targets": the second can't be the first again

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.damage(target, game.amount(self.amount))


@dataclass(frozen=True)
class DamageToYou:
    """Mana Vault: "... it deals 1 damage to you." (the ability's controller, from its source)"""
    amount: Quantity

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.damage(controller, game.amount(self.amount))


@dataclass(frozen=True)
class RevealTopTradeLife:
    """Keen Duelist: you and target opponent each reveal the top card, lose life equal to the other's card's mana value, and
    put your own revealed card into your hand."""
    target: str = "opponent"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is None:
            return
        pair = (controller, target)
        revealed = [(seat, seat.library.pop(0) if seat.library else None) for seat in pair]
        for seat, card in revealed:
            if card is not None:
                game.broadcast({"event": "revealed", "seat": seat.index, "card": card.name})
        for (seat, _), (_, other) in zip(revealed, reversed(revealed)):
            if other is not None:
                game.change_life(seat, -int(other.cmc))
        for seat, card in revealed:
            if card is not None:
                seat.hand.append(card)


@dataclass(frozen=True)
class EachPlayerLosesLife:
    amount: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            game.change_life(seat, -game.amount(self.amount))


@dataclass(frozen=True)
class Drain:
    """ "Each opponent loses X life. You gain life equal to the life lost this way." """
    amount: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        lost = 0
        for seat in game.opponents(controller):
            game.change_life(seat, -game.amount(self.amount))
            lost += game.amount(self.amount)
        game.change_life(controller, lost)


@dataclass(frozen=True)
class _GainLifeLost:
    """ "You gain life equal to the life lost this way." (see _merge_drain) """


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
class TargetControllerGainsLifeEqualToPower:
    """Swords to Plowshares: "Its controller gains life equal to its power." """
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.last_controller is not None:
            game.change_life(target.last_controller, max(0, target.last_power))


@dataclass(frozen=True)
class DamageWhatItAttacks:
    """Raid Bombardment: "... deals 1 damage to the player or planeswalker that creature is attacking." The creature that
    attacked is the subject."""
    amount: int
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        attack = next((a for a in game.combat.attacks if a.attacker is target), None) if target is not None else None
        if attack is not None:
            game.damage(attack.walker if attack.walker is not None else attack.defender, self.amount)


@dataclass(frozen=True)
class Annihilate:
    """Annihilator N: "Whenever this creature attacks, defending player sacrifices N permanents." The defending player
    is the player the trigger was about."""
    count: int
    binds = PLAYER

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.sacrifice(target, "permanent", self.count)


@dataclass(frozen=True)
class EachDamagesItself:
    """Wave of Reckoning: "Each creature deals damage to itself equal to its power." (all at the same time)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creatures = [(p, game.power(p)) for seat in game.live_seats() for p in seat.battlefield if "Creature" in p.card.type_line]
        for permanent, power in creatures:
            game.damage(permanent, max(power, 0), source=permanent)


@dataclass(frozen=True)
class EachCreatureDamagesItsController:
    """Rakdos Charm: "Each creature deals 1 damage to its controller." (all at the same time)"""
    amount: int

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        creatures = [(p, seat) for seat in game.live_seats() for p in seat.battlefield if "Creature" in p.card.type_line]
        for permanent, owner in creatures:
            game.damage(owner, self.amount, source=permanent)


@dataclass(frozen=True)
class PreventCombatDamageToYou:
    """Inkshield: "Prevent all combat damage that would be dealt to you this turn. For each 1 damage prevented this way,
    create a 2/1 white and black Inkling creature token with flying." The second sentence is folded in by
    _merge_prevention; the game creates the tokens as the damage is prevented."""
    token: Card | None = None  # one for each point of damage prevented

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.prevent_combat_damage(controller, self.token)


@dataclass(frozen=True)
class PreventAllCombatDamage:
    """Fog: "Prevent all combat damage that would be dealt this turn." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.fog_turn = game.turn


@dataclass(frozen=True)
class PreventNext:
    """ "Prevent the next 2 damage that would be dealt to any target (target creature, you, this creature) this turn."
    With no `target` and not `on_source`, it is the controller that is shielded."""
    amount: int
    target: str = ""
    on_source: bool = False  # it is about the ability's source, not a chosen target

    @property
    def binds(self) -> str | None:
        return SOURCE if self.on_source else None

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        shielded = target if (self.target or self.on_source) else controller
        if shielded is not None:
            game.shield(shielded, self.amount)


@dataclass(frozen=True)
class TargetLoseHalfLife:
    """ "Target player loses half their life, rounded up (down)." """
    target: str  # "player" or "opponent"
    round_up: bool

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.life > 0:
            game.change_life(target, -((target.life + 1) // 2 if self.round_up else target.life // 2))


@dataclass(frozen=True)
class DrawHalfLibraryLoseHalfLife:
    """Peer into the Abyss: "Target player draws cards equal to half the number of cards in their library and loses half
    their life. Round up each time." """
    target: str = "player"

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None:
            game.draw(target, (len(target.library) + 1) // 2)
            TargetLoseHalfLife("player", True).resolve(game, controller, target)


@dataclass(frozen=True)
class LoseAllButOneLife:
    """Soulgorger Orgg: "You lose all but 1 life." The source remembers how much."""
    binds = SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        lost = max(0, controller.life - 1)
        if target is not None:
            target.stored = lost
        game.change_life(controller, -lost)


@dataclass(frozen=True)
class GainLifeItLost:
    """Soulgorger Orgg: "you gain life equal to the life you lost when it entered." """
    binds = DEAD_SOURCE

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and target.stored:
            game.change_life(controller, target.stored)


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
            if self.creatures == "opponents and planeswalkers":  # Volcanic Torrent
                for permanent in game.mass_targets("planeswalker you don't control", controller, None):
                    game.damage(permanent, amount)
        if self.players:
            for seat in (game.live_seats() if self.players == "all" else game.opponents(controller)):
                game.damage(seat, amount)


@dataclass(frozen=True)
class GivePoison:
    """Prologue to Phyresis: "Each opponent gets a poison counter." / Ichor Rats: "each player gets a poison counter." (CR 122.1f)"""
    who: str  # "opponent" or "player"
    count: int = 1

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.turn_order_from_active():
            if self.who == "player" or seat is not controller:
                game.give_poison(seat, self.count)


@dataclass(frozen=True)
class PoisonShrinksOpponentsCreatures:
    """Phyresis Outbreak: "Then each creature your opponents control gets -1/-1 until end of turn for each poison counter its
    controller has." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        for seat in game.opponents(controller):
            poison = seat.player_counters.get("poison", 0)
            if poison:
                for permanent in [p for p in seat.battlefield if "Creature" in p.card.type_line]:
                    game.modify_until_end_of_turn(permanent, Modifier(power=-poison, toughness=-poison))


@dataclass(frozen=True)
class DamageTargetsController:
    """Blooming Blast: "... also deals 3 damage to that creature's controller." (the creature the effect before it targeted)"""
    amount: int
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        owner = game.controller_of(target) if target is not None else None
        if owner is not None:
            game.damage(owner, self.amount, source=game.resolving_source)


@dataclass(frozen=True)
class LoseLife:
    amount: int | str

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        game.change_life(controller, -game.amount(self.amount))


@dataclass(frozen=True)
class TargetControllerGainsLife:
    """Nature's Claim: "Its controller gains 4 life." """
    amount: int
    binds = PREVIOUS_TARGET

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        owner = getattr(target, "last_controller", None) or getattr(target, "controller", None)
        if owner is not None:
            game.change_life(owner, self.amount)


@dataclass(frozen=True)
class LifeLocked:
    """Teferi's Protection: "Your life total can't change" until your next turn: no life is gained or lost."""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        controller.life_locked = True


@dataclass(frozen=True)
class PowerDamageToEachOther:
    """Chandra's Ignition: "Target creature you control deals damage equal to its power to each other creature and each
    opponent." (the creature is the one FightFirst remembered)"""

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        source = game.resolving_item.carried if game.resolving_item is not None else None
        if source is None or not game.on_battlefield(source):
            return
        power = game.power(source)
        hit = [p for seat in game.live_seats() for p in seat.battlefield if "Creature" in p.card.type_line and p is not source]
        for victim in [*hit, *game.opponents(controller)]:
            game.damage(victim, power, source=source)


@dataclass(frozen=True)
class RevealTopToHandDrain:
    """Yuriko: "Reveal the top card of your library and put that card into your hand. Each opponent loses life equal to that card's
    mana value." """

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if not controller.library:
            return
        card = controller.library.pop(0)
        controller.hand.append(card)
        game.broadcast({"event": "revealed", "seat": controller.index, "card": card.name})
        for opponent in game.opponents(controller):
            game.change_life(opponent, -int(card.cmc))


@dataclass(frozen=True)
class WhenThatDealsCombatDamage:
    """Stensian Sanguinist: "Whenever that creature deals combat damage to a player this combat, this creature becomes
    prepared." The creature is the last one targeted; the watch lives on this combat, so it ends with it."""
    then: Any
    binds = PREVIOUS_TARGET
    text = "Whenever that creature deals combat damage to a player this combat, this creature becomes prepared."

    def resolve(self, game: Game, controller: Seat, target: Any) -> None:
        if target is not None and game.resolving_source is not None:
            game.combat.damage_watches.append((target, game.resolving_source, self))
