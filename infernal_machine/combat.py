"""Combat: declaring attackers and blockers, and combat damage (CR 506-511).

Creatures attack players (not planeswalkers yet). Supported keywords: flying,
reach, vigilance, haste, defender, menace, trample, first strike, double
strike, deathtouch and lifelink.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .cards import has_keyword

if TYPE_CHECKING:
    from .game import Game, Permanent, Seat

ATTACK_PROMPT = "Attack with "  # followed by the creature's label
BLOCK_PROMPT = "Block with "
NO_ATTACK = "Don't attack"
NO_BLOCK = "Don't block"


@dataclass(eq=False)
class Attack:
    attacker: Permanent
    controller: Seat
    defender: Seat
    blockers: list[Permanent] = field(default_factory=list)
    blocked: bool = False  # stays blocked even if its blockers leave (CR 509.1h)


def power(permanent: Permanent) -> int:
    value = permanent.card.power
    return max(0, int(value)) if value and value.lstrip("-").isdigit() else 0


def lethal_damage(permanent: Permanent, deathtouch: bool) -> int:
    """Damage still needed to destroy a blocker; any amount is lethal with deathtouch."""
    toughness = permanent.card.toughness
    if deathtouch or not (toughness and toughness.lstrip("-").isdigit()):
        return 1
    return max(0, int(toughness) - permanent.damage)


class Combat:
    def __init__(self, game: Game):
        self.game = game
        self.attacks: list[Attack] = []

    def declare_attackers(self, seat: Seat) -> None:
        """Ask the active player, creature by creature, whether and whom to attack (CR 508.1)."""
        opponents = self.game.opponents(seat)
        options = [NO_ATTACK] + [f"Attack Player: {o.name} (seat {o.index})" for o in opponents]
        for permanent in list(seat.battlefield):
            if not self._can_attack(permanent):
                continue
            choice = seat.player.choose(ATTACK_PROMPT + self.game.label(permanent), options)
            if choice == 0:
                continue
            defender = opponents[choice - 1]
            if not has_keyword(permanent.card, "vigilance"):
                permanent.tapped = True
            self.attacks.append(Attack(permanent, seat, defender))
            self.game.trigger("attacks", permanent.card, seat)
            self.game.broadcast({"event": "attack", "seat": seat.index, "card": permanent.card.name,
                                 "defender": defender.index})

    def declare_blockers(self) -> None:
        """Each defending player, in turn order, assigns blockers (CR 509.1)."""
        defenders = {id(a.defender): a.defender for a in self.attacks}
        for seat in self.game.turn_order_from_active():
            if id(seat) not in defenders:
                continue
            for permanent in list(seat.battlefield):
                if permanent.tapped or "Creature" not in permanent.card.type_line:
                    continue
                blockable = [a for a in self.attacks if a.defender is seat and _can_block(permanent, a.attacker)]
                if not blockable:
                    continue
                options = [NO_BLOCK] + [f"Block {self.game.label(a.attacker)}" for a in blockable]
                choice = seat.player.choose(BLOCK_PROMPT + self.game.label(permanent), options)
                if choice:
                    attack = blockable[choice - 1]
                    attack.blockers.append(permanent)
                    self.game.broadcast({"event": "block", "seat": seat.index, "card": permanent.card.name,
                                         "attacker": attack.attacker.card.name})
        for attack in self.attacks:
            # Menace: a creature blocked by only one creature is unblocked instead (CR 702.110b).
            if has_keyword(attack.attacker.card, "menace") and len(attack.blockers) == 1:
                self.game.broadcast({"event": "block_removed", "card": attack.blockers[0].card.name,
                                     "reason": "menace"})
                attack.blockers = []
            attack.blocked = bool(attack.blockers)

    def has_first_strike(self) -> bool:
        creatures = [a.attacker for a in self.attacks] + [b for a in self.attacks for b in a.blockers]
        return any(_first_strike(c) or _double_strike(c) for c in creatures)

    def deal_damage(self, first_strike_step: bool) -> None:
        """Combat damage is worked out first, then dealt all at once (CR 510.1-510.2)."""
        hits: list[tuple[Permanent, Seat | Permanent, int]] = []
        for attack in self.attacks:
            attacker = attack.attacker
            if not self.game.on_battlefield(attacker):
                continue
            blockers = [b for b in attack.blockers if self.game.on_battlefield(b)]
            if _deals_damage_now(attacker, first_strike_step):
                amount = power(attacker)
                if not attack.blocked:
                    hits.append((attacker, attack.defender, amount))
                else:
                    hits += self._assign(attacker, blockers, attack.defender, amount)
            for blocker in blockers:
                if _deals_damage_now(blocker, first_strike_step):
                    hits.append((blocker, attacker, power(blocker)))
        for source, target, amount in hits:
            if amount > 0:
                self.game.damage(target, amount, source=source, combat=True)

    def _assign(self, attacker: Permanent, blockers: list[Permanent], defender: Seat,
                amount: int) -> list[tuple[Permanent, Seat | Permanent, int]]:
        """Lethal damage to each blocker in order, the rest to the last one, or to
        the player with trample (CR 510.1c-d)."""
        deathtouch = has_keyword(attacker.card, "deathtouch")
        trample = has_keyword(attacker.card, "trample")
        hits: list[tuple[Permanent, Seat | Permanent, int]] = []
        for blocker in blockers:
            share = min(amount, lethal_damage(blocker, deathtouch))
            hits.append((attacker, blocker, share))
            amount -= share
        if amount > 0 and trample:
            hits.append((attacker, defender, amount))
        elif amount > 0 and hits:
            source, target, share = hits[-1]
            hits[-1] = (source, target, share + amount)
        return hits

    def _can_attack(self, permanent: Permanent) -> bool:
        card = permanent.card
        return ("Creature" in card.type_line and not permanent.tapped
                and not (permanent.sick and not has_keyword(card, "haste"))
                and not has_keyword(card, "defender"))


def _can_block(blocker: Permanent, attacker: Permanent) -> bool:
    if has_keyword(attacker.card, "flying"):
        return has_keyword(blocker.card, "flying") or has_keyword(blocker.card, "reach")
    return True


def _first_strike(permanent: Permanent) -> bool:
    return has_keyword(permanent.card, "first strike")


def _double_strike(permanent: Permanent) -> bool:
    return has_keyword(permanent.card, "double strike")


def _deals_damage_now(permanent: Permanent, first_strike_step: bool) -> bool:
    if first_strike_step:
        return _first_strike(permanent) or _double_strike(permanent)
    return _double_strike(permanent) or not _first_strike(permanent)
