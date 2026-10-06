"""Combat: declaring attackers and blockers, and combat damage (CR 506-511).

Creatures attack players (not planeswalkers yet). Supported keywords: flying,
reach, vigilance, haste, defender, menace, trample, first strike, double
strike, deathtouch and lifelink, whether printed or granted; power, toughness
and keywords are read through the game so modifiers count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .effects import CANT_ATTACK, CANT_BLOCK

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


class Combat:
    def __init__(self, game: Game):
        self.game = game
        self.attacks: list[Attack] = []

    def declare_attackers(self, seat: Seat) -> None:
        """Ask the active player, creature by creature, whether and whom to attack (CR 508.1)."""
        opponents = self.game.opponents(seat)
        self.game.send_state(seat)
        options = [NO_ATTACK] + [f"Attack Player: {o.name} (seat {o.index})" for o in opponents]
        for permanent in list(seat.battlefield):
            if not self._can_attack(permanent):
                continue
            if goader := permanent.goaded_by:  # must attack, and not the goader if there's anyone else
                targets = [o for o in opponents if o is not goader] or opponents
                defender = targets[0] if len(targets) == 1 else targets[seat.player.choose(
                    ATTACK_PROMPT + self.game.label(permanent), [f"Attack Player: {o.name} (seat {o.index})" for o in targets])]
            else:
                choice = seat.player.choose(ATTACK_PROMPT + self.game.label(permanent), options)
                if choice == 0:
                    continue
                defender = opponents[choice - 1]
            if not self.game.has_keyword(permanent, "vigilance"):
                permanent.tapped = True
            self.attacks.append(Attack(permanent, seat, defender))
            permanent.attacked_turn = self.game.turn
            self.game.trigger("attacks", permanent, seat)
            self.game._trigger_each("ally_attacks", seat)
            self.game._trigger_each("attacked", defender)
            for owner in self.game.live_seats():  # "Whenever equipped / enchanted creature attacks"
                for attachment in list(owner.battlefield):
                    if attachment.attached_to is permanent:
                        self.game.trigger("host_attacks", attachment, owner)
            self.game.broadcast({"event": "attack", "seat": seat.index, "card": permanent.card.name,
                                 "defender": defender.index})
        if len(self.attacks) >= 2:
            for permanent in list(seat.battlefield):
                self.game.trigger("attack_with_two", permanent, seat)

    def declare_blockers(self) -> None:
        """Each defending player, in turn order, assigns blockers (CR 509.1)."""
        defenders = {id(a.defender): a.defender for a in self.attacks}
        for seat in self.game.turn_order_from_active():
            if id(seat) not in defenders:
                continue
            self.game.send_state(seat)
            for permanent in list(seat.battlefield):
                if permanent.tapped or "Creature" not in permanent.card.type_line:
                    continue
                blockable = [a for a in self.attacks if a.defender is seat and self._can_block(permanent, a.attacker)]
                if not blockable:
                    continue
                options = [NO_BLOCK] + [f"Block {self.game.label(a.attacker)}" for a in blockable]
                choice = seat.player.choose(BLOCK_PROMPT + self.game.label(permanent), options)
                if choice:
                    attack = blockable[choice - 1]
                    attack.blockers.append(permanent)
                    self.game.trigger("blocks", permanent, seat)
                    self.game.broadcast({"event": "block", "seat": seat.index, "card": permanent.card.name,
                                         "attacker": attack.attacker.card.name})
        for attack in self.attacks:
            # Menace: a creature blocked by only one creature is unblocked instead (CR 702.110b).
            if self.game.has_keyword(attack.attacker, "menace") and len(attack.blockers) == 1:
                self.game.broadcast({"event": "block_removed", "card": attack.blockers[0].card.name,
                                     "reason": "menace"})
                attack.blockers = []
            attack.blocked = bool(attack.blockers)

    def has_first_strike(self) -> bool:
        creatures = [a.attacker for a in self.attacks] + [b for a in self.attacks for b in a.blockers]
        return any(self._has(c, "first strike") or self._has(c, "double strike") for c in creatures)

    def deal_damage(self, first_strike_step: bool) -> None:
        """Combat damage is worked out first, then dealt all at once (CR 510.1-510.2)."""
        hits: list[tuple[Permanent, Seat | Permanent, int]] = []
        for attack in self.attacks:
            attacker = attack.attacker
            if not self.game.on_battlefield(attacker):
                continue
            blockers = [b for b in attack.blockers if self.game.on_battlefield(b)]
            if self._deals_damage_now(attacker, first_strike_step):
                amount = max(0, self.game.power(attacker))
                if not attack.blocked:
                    hits.append((attacker, attack.defender, amount))
                else:
                    hits += self._assign(attacker, blockers, attack.defender, amount)
            for blocker in blockers:
                if self._deals_damage_now(blocker, first_strike_step):
                    hits.append((blocker, attacker, max(0, self.game.power(blocker))))
        for source, target, amount in hits:
            if amount > 0:
                self.game.damage(target, amount, source=source, combat=True)

    def _assign(self, attacker: Permanent, blockers: list[Permanent], defender: Seat,
                amount: int) -> list[tuple[Permanent, Seat | Permanent, int]]:
        """Lethal damage to each blocker in order, the rest to the last one, or to
        the player with trample (CR 510.1c-d)."""
        deathtouch = self.game.has_keyword(attacker, "deathtouch")
        trample = self.game.has_keyword(attacker, "trample")
        hits: list[tuple[Permanent, Seat | Permanent, int]] = []
        for blocker in blockers:
            share = min(amount, self._lethal_damage(blocker, deathtouch))
            hits.append((attacker, blocker, share))
            amount -= share
        if amount > 0 and trample:
            hits.append((attacker, defender, amount))
        elif amount > 0 and hits:
            source, target, share = hits[-1]
            hits[-1] = (source, target, share + amount)
        return hits

    def _lethal_damage(self, permanent: Permanent, deathtouch: bool) -> int:
        """Damage still needed to destroy a blocker; any amount is lethal with deathtouch."""
        current = self.game.toughness(permanent)
        if deathtouch or current is None:
            return 1
        return max(0, current - permanent.damage)

    def _has(self, permanent: Permanent, keyword: str) -> bool:
        return self.game.has_keyword(permanent, keyword)

    def _can_attack(self, permanent: Permanent) -> bool:
        return ("Creature" in permanent.card.type_line and not permanent.tapped
                and not (permanent.sick and not self._has(permanent, "haste"))
                and not self._has(permanent, "defender") and not self._has(permanent, CANT_ATTACK))

    def _can_block(self, blocker: Permanent, attacker: Permanent) -> bool:
        if self._has(blocker, CANT_BLOCK):
            return False
        if self.game.protected_from(attacker, frozenset(blocker.card.colors)):  # can't be blocked by those colors
            return False
        if self._has(attacker, "flying"):
            return self._has(blocker, "flying") or self._has(blocker, "reach")
        return True

    def _deals_damage_now(self, permanent: Permanent, first_strike_step: bool) -> bool:
        first, double = self._has(permanent, "first strike"), self._has(permanent, "double strike")
        return first or double if first_strike_step else double or not first
