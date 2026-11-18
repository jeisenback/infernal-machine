"""Combat: declaring attackers and blockers, and combat damage (CR 506-511).

Creatures attack players or the planeswalkers they control. Supported keywords: flying,
reach, vigilance, haste, defender, menace, trample, first strike, double
strike, deathtouch and lifelink, whether printed or granted; power, toughness
and keywords are read through the game so modifiers count.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from .characteristics import Modifier, source_qualities
from .effects import (copy_of, CANT_ATTACK, CANT_BE_BLOCKED, CANT_BLOCK, MUST_ATTACK, NOT_BLOCKED_BY, ONLY_BLOCKED_BY, Annihilate, PutCountersOnSource, TriggeredAbility, attack_tax_per_counter, attack_taxes,
                      combat_restrictions)
from .filters import parse_filter
from .mana import Cost, cost_of
from .prompts import PromptKind

if TYPE_CHECKING:
    from .game import Game, Permanent, Seat

MYRIAD_PROMPT = PromptKind("myriad", "Myriad: create a token copy of ")  # followed by the creature and the opponent; Yes or No
ATTACK_PROMPT = PromptKind("attack", "Attack with ")  # followed by the creature's label
BLOCK_PROMPT = PromptKind("block", "Block with ")
MUST_BLOCK_PROMPT = PromptKind("must_block", "Choose a creature that blocks ")  # followed by the attacker that must be blocked if able
ASSIGN_PROMPT = PromptKind("assign", "Damage first to a blocker of ")  # followed by the attacker's label
NO_ATTACK = "Don't attack"
NO_BLOCK = "Don't block"


@dataclass(eq=False)
class Attack:
    attacker: Permanent
    controller: Seat
    defender: Seat  # the player attacked, or the controller of the planeswalker attacked
    blockers: list[Permanent] = field(default_factory=list)
    blocked: bool = False  # stays blocked even if its blockers leave (CR 509.1h)
    walker: Permanent | None = None  # the planeswalker attacked, if it isn't the player


LANDWALKS = ("Island", "Swamp", "Mountain", "Forest", "Plains")


class Combat:
    def __init__(self, game: Game):
        self.game = game
        self.attacks: list[Attack] = []
        self.damage_watches: list[tuple[Permanent, Permanent, Any]] = []  # (creature, watcher, effect): Stensian Sanguinist
        self.exile_at_end: list[Permanent] = []  # myriad tokens: exiled at end of combat

    def declare_attackers(self, seat: Seat) -> None:
        """Ask the active player, creature by creature, whether and whom to attack (CR 508.1). The costs to attack are
        added up as the attackers are chosen and tapped, then paid once, after the last one (CR 508.1h-i)."""
        opponents = self.game.opponents(seat)
        self.game.send_state(seat)
        all_walkers = [p for o in opponents for p in o.battlefield if p.loyalty is not None]
        owed = Cost()  # the total cost to attack so far
        declared: list[tuple[Permanent, Seat, Permanent | None]] = []
        for permanent in list(seat.battlefield):
            if not self._can_attack(permanent):
                continue
            opponents, walkers = self._attackable(seat, permanent, self.game.opponents(seat), all_walkers, owed)
            if not opponents:
                continue
            options = ([NO_ATTACK] + [f"Attack Player: {o.name} (seat {o.index})" for o in opponents]
                       + [f"Attack Planeswalker: {self.game.label(p)}" for p in walkers])
            walker = None
            if permanent.must_attack in opponents:  # an Encore token
                defender = permanent.must_attack
            elif goader := self.game.goader_of(permanent):  # must attack, and not the goader if there's anyone else
                targets = [o for o in opponents if o is not goader] or opponents
                defender = targets[0] if len(targets) == 1 else targets[seat.player.choose(
                    ATTACK_PROMPT(self.game.label(permanent)), [f"Attack Player: {o.name} (seat {o.index})" for o in targets])]
            else:
                forced = self._has(permanent, MUST_ATTACK) or (permanent.must_attack_turn != 0 and permanent.must_attack_turn == self.game.turn)  # "attacks each combat if able": no way to stay home
                choice = seat.player.choose(ATTACK_PROMPT(self.game.label(permanent)), options[forced:]) + forced
                if choice == 0:
                    continue
                if choice <= len(opponents):
                    defender = opponents[choice - 1]
                else:
                    walker = walkers[choice - 1 - len(opponents)]
                    defender = self.game.controller(walker)
            if not self.game.has_keyword(permanent, "vigilance"):
                self.game.tap(permanent)
            owed += self._attack_tax(permanent, defender)  # Nils: {X} to attack, X the counters on the attacker
            self.attacks.append(Attack(permanent, seat, defender, walker=walker))
            permanent.attacked_turn = self.game.turn
            declared.append((permanent, defender, walker))
        if owed != Cost():  # every attacker was chosen so that this can be paid (see _attackable)
            payment = self.game._pay_cost(seat, owed)
            assert payment is not None
            self.game._spend_mana(seat, payment)
        for permanent, defender, walker in declared:
            self.game.trigger("attacks", permanent, seat)
            if self.game.has_keyword(permanent, "myriad"):
                self._myriad(permanent, seat, defender)
            if walker is None:
                self.game.trigger("attacks_player", permanent, seat, player=defender)
            if n := self.game.annihilator(permanent):
                self.game._queue(TriggeredAbility("attacks", (Annihilate(n),), False, f"Annihilator {n}"), permanent, seat,
                                 player=defender)
            if walker is None and self.game.has_keyword(permanent, "dethrone") \
                    and defender.life >= max(s.life for s in self.game.live_seats()):  # CR 702.105: the player with the most life, or tied
                self.game._queue(TriggeredAbility("attacks", (PutCountersOnSource(1, "+1/+1"),), False, "Dethrone"), permanent, seat)
            self.game.happened("ally_attacks", seat, subject=permanent)
            self.game._remembered_attack(permanent, defender)
            self.game._observe("creature_attacks", permanent.card, seat, subject=permanent)  # with a qualifier (Raid Bombardment)
            self.game.happened("attacked_or_walker", defender, subject=permanent)
            if walker is None:
                self.game.happened("attacked", defender, subject=permanent)
            for owner in self.game.live_seats():  # "Whenever equipped / enchanted creature attacks"
                for attachment in list(owner.battlefield):
                    if attachment.attached_to is permanent:
                        self.game.trigger("host_attacks", attachment, owner, permanent, x=defender.index)  # x: the seat attacked (Contract)
            self.game.broadcast({"event": "attack", "seat": seat.index, "card": permanent.card.name,
                                 "defender": defender.index,
                                 **({"planeswalker": walker.card.name} if walker is not None else {})})
        if self.attacks:  # Windbrisk Heights: "if you attacked with three or more creatures this turn"
            seat.most_attackers = len(self.attacks)
            seat.attackers_turn = self.game.turn
        if len(self.attacks) >= 2:
            for permanent in list(seat.battlefield):
                self.game.trigger("attack_with_two", permanent, seat)
        if len(self.attacks) >= 3:
            for permanent in list(seat.battlefield):
                self.game.trigger("attack_with_three", permanent, seat)
        if self.attacks:
            for holder in self.game.live_seats():  # Killian: an attacker enchanted by an Aura that holder controls (any attacker)
                if any(self._enchanted_by(a.attacker, holder) for a in self.attacks):
                    for permanent in list(holder.battlefield):
                        self.game.trigger("enchanted_attack", permanent, holder)
            for permanent in list(seat.battlefield):
                self.game.trigger("creatures_attack", permanent, seat)
                for ability in self.game._triggers_of(permanent):  # "Whenever one or more Dragons you control attack": x is how many
                    if ability.event == "type_attack" and (kind := re.match(r"Whenever one or more ([A-Z][a-z]+)s ", ability.text)) \
                            and (n := sum(kind[1] in self.game.subtypes(a.attacker) for a in self.attacks)):
                        self.game.trigger("type_attack", permanent, seat, x=n, text=ability.text)
            self.game.happened("tribe_attack", seat, *{kind.lower() for a in self.attacks
                                                       for kind in a.attacker.card.type_line.partition("\u2014")[2].split()})
            if len(self.attacks) == 1:  # "Whenever you attack with a creature alone"; "Whenever this creature attacks alone"
                self.game.happened("attack_alone", seat, subject=self.attacks[0].attacker)
                self.game.trigger("attacks_alone", self.attacks[0].attacker, seat)
            for other in self.game.opponents(seat):  # "Whenever an opponent attacks with creatures"
                at_them = sum(1 for a in self.attacks if a.defender is other)
                for permanent in list(other.battlefield):
                    self.game.trigger("opponent_attacks", permanent, other, player=seat, x=at_them)
                    if at_them:  # (a creature attacking one of their planeswalkers has them as its defender too)
                        self.game.trigger("opponent_attacks_you", permanent, other, player=seat)
                    if len(self.attacks) >= 2:
                        self.game.trigger("other_attacks_two", permanent, other, player=seat, x=at_them)
            attacked = {id(a.defender): a.defender for a in self.attacks if a.walker is None}
            for watcher in self.game.live_seats():  # "Whenever a player attacks one of your opponents": once for each
                for defender in attacked.values():
                    if defender is not watcher:
                        for permanent in list(watcher.battlefield):
                            self.game.trigger("attacks_opponent", permanent, watcher, player=seat, x=defender.index)
            if any(a.defender.player_counters.get("poison", 0) > 0 for a in self.attacks):  # Norn's Decree: a player attacked is poisoned
                for watcher in self.game.live_seats():
                    for permanent in list(watcher.battlefield):
                        self.game.trigger("player_attacks_poisoned", permanent, watcher, player=seat)

    def _myriad(self, permanent: Permanent, seat: Seat, defender: Seat) -> None:
        """Myriad: for each opponent other than the defending player, you may create a token copy of the creature that's tapped
        and attacking that player; the tokens are exiled at end of combat."""
        for opponent in self.game.opponents(seat):
            if opponent is defender or seat.player.choose(MYRIAD_PROMPT(self.game.label(permanent) + f" attacking {opponent.name}?"), ["Yes", "No"]) != 0:
                continue
            for made in self.game.create_tokens(seat, copy_of(permanent.card, as_token=True), 1):
                made.tapped = True
                self.attacks.append(Attack(made, seat, opponent))
                self.exile_at_end.append(made)
                self.game.broadcast({"event": "attack", "seat": seat.index, "card": made.card.name, "defender": opponent.index})

    @staticmethod
    def _enchanted_by(creature: Permanent, holder: Seat) -> bool:
        """Whether an Aura `holder` controls is attached to `creature`."""
        return any(p.attached_to is creature and "Aura" in p.card.type_line for p in holder.battlefield)

    def _attack_tax(self, permanent: Permanent, defender: Seat) -> Cost:
        """What attacking `defender` costs `permanent`: Nils makes each counter on the attacker cost {1}; Ghostly Prison, Baird and
        the like charge each attacker, a fixed cost or {X} for a count the defender works out (Sphere of Safety)."""
        counters = sum(permanent.counters.values())
        tax = Cost(generic=counters * sum(attack_tax_per_counter(p.card) for p in defender.battlefield)) if counters else Cost()
        for source in defender.battlefield:
            for each in attack_taxes(source.card):
                tax += Cost(generic=self.game.evaluate(each.amount, defender)) if each.amount is not None else cost_of(each.cost)
        return tax

    def _barred_from_attacking(self, permanent: Permanent, defender: Seat) -> bool:
        """Whether a static ability of the defender's keeps `permanent` from attacking them (or their planeswalkers), or one of its own:
        "This creature can't attack unless defending player controls an Island." (CR 508.1c)"""
        if any(r.kind == "unless_defender_controls" and not any(parse_filter(r.what).matches(p.card) for p in defender.battlefield)
               for r in combat_restrictions(permanent.card)):
            return True
        subtypes = self.game.subtypes(permanent)
        for source in defender.battlefield:
            for restriction in combat_restrictions(source.card):
                if restriction.kind == "no_attack_tribe" and restriction.what in subtypes:
                    return True
                if restriction.kind == "no_attack_enchanted" and any(
                        a.attached_to is permanent and "Aura" in a.card.type_line and self.game.controller_of(a) is defender
                        for seat in self.game.seats for a in seat.battlefield):
                    return True
        return False

    def _attackable(self, seat: Seat, permanent: Permanent, opponents: list[Seat],
                    walkers: list[Permanent], owed: Cost | None = None) -> tuple[list[Seat], list[Permanent]]:
        """The players (and their planeswalkers) `permanent` may attack: not the one a vow counter keeps it from
        (Promise of Loyalty), and not one whose attack tax the attacking player can't pay on top of the `owed` that the
        attackers chosen before it already cost. It taps to attack (unless it has vigilance), so its own mana is out."""
        owed = Cost() if owed is None else owed
        barred = permanent.vow_of if permanent.counters.get("vow") else None
        untapped = permanent if not self.game.has_keyword(permanent, "vigilance") else None
        # Even an untaxed attacker is checked once something is owed: it taps, and the mana the tax counted on may be its own (a mana
        # creature, or one that Enduring Vitality lets tap for mana).
        allowed = [o for o in opponents if o is not barred and not self._barred_from_attacking(permanent, o) and (
            (total := owed + self._attack_tax(permanent, o)) == Cost()
            or self.game._pay_cost(seat, total, untapped) is not None)]
        barred_walkers = [(whose, kind) for whose, kind, turn in seat.cant_attack_walkers if turn == self.game.turn]  # Jace, Multiverse Architect
        return allowed, [w for w in walkers if self.game.controller_of(w) in allowed
                         and not any(self.game.controller_of(w) is whose and kind in self.game.subtypes(w) for whose, kind in barred_walkers)]

    def add_attacker(self, permanent: Permanent, controller: Seat, defender: Seat) -> None:
        """A creature put onto the battlefield "tapped and attacking": it was never declared as an attacker, so
        nothing triggers on its attacking."""
        self.attacks.append(Attack(permanent, controller, defender))
        permanent.attacked_turn = self.game.turn

    def declare_blockers(self) -> None:
        """Each defending player, in turn order, assigns blockers (CR 509.1)."""
        defenders = {id(a.defender): a.defender for a in self.attacks}
        for seat in self.game.turn_order_from_active():
            if id(seat) not in defenders:
                continue
            self.game.send_state(seat)
            for attack in self.attacks:  # "This creature must be blocked if able": one of the creatures that can block it does
                if attack.defender is seat and any(r.kind == "must_be_blocked" for r in combat_restrictions(attack.attacker.card)):
                    able = [p for p in seat.battlefield if not p.tapped and "Creature" in p.card.type_line
                            and self._can_block(p, attack.attacker) and not any(p in a.blockers for a in self.attacks)]
                    if able:
                        pick = able[0] if len(able) == 1 else able[seat.player.choose(
                            MUST_BLOCK_PROMPT(self.game.label(attack.attacker)), [self.game.label(p) for p in able])]
                        self._block(seat, pick, attack)
            for permanent in list(seat.battlefield):
                if permanent.tapped or "Creature" not in permanent.card.type_line:
                    continue
                while self._blocking(permanent) < self._block_limit(permanent):  # Ghastbark Twins: one more (CR 509.1a)
                    blockable = [a for a in self.attacks if a.defender is seat and permanent not in a.blockers
                                 and self._can_block(permanent, a.attacker) and not self._has_enough_blockers(a)]
                    if not blockable:
                        break
                    forced = [a for a in blockable if self._lured(a.attacker)]
                    if forced:  # "All creatures able to block this creature do so.": on every block it has (CR 509.1c)
                        self._block(seat, permanent, forced[0])
                        continue
                    if not self._blocking(permanent):
                        if permanent.must_block_turn == self.game.turn:  # "Target creature blocks this turn if able.": one block will do it
                            wanted = [a for a in blockable if permanent.must_block_what in (None, a.attacker)]
                            if wanted:
                                self._block(seat, permanent, wanted[0])
                                continue
                    options = [NO_BLOCK] + [f"Block {self.game.label(a.attacker)}" for a in blockable]
                    choice = seat.player.choose(BLOCK_PROMPT(self.game.label(permanent)), options)
                    if not choice:
                        break
                    self._block(seat, permanent, blockable[choice - 1])
        for attack in self.attacks:
            # Menace: a creature blocked by only one creature is unblocked instead (CR 702.111b); so is one that can't be
            # blocked except by three or more, when fewer than that block it.
            needed = max([2 if self.game.has_keyword(attack.attacker, "menace") else 0]
                         + [int(r.what) for r in combat_restrictions(attack.attacker.card) if r.kind == "min_blockers"])
            if 0 < len(attack.blockers) < needed:
                self.game.broadcast({"event": "block_removed", "card": attack.blockers[0].card.name,
                                     "reason": "menace" if needed == 2 else f"needs {needed} blockers"})
                attack.blockers = []
            attack.blocked = bool(attack.blockers)
            if attack.blockers:  # Bushido, Afflict, Rampage and "Whenever this creature becomes blocked": x is the blockers past the first
                self.game.trigger("becomes_blocked", attack.attacker, attack.controller, player=attack.defender, x=len(attack.blockers) - 1)
            else:  # "Whenever this creature attacks and isn't blocked" (CR 509.1h: unblocked once blockers are declared)
                self.game.trigger("attacks_unblocked", attack.attacker, attack.controller, player=attack.defender)
            if self.game.has_keyword(attack.attacker, "flanking"):  # blocked by a creature without flanking: -1/-1
                for blocker in attack.blockers:
                    if not self.game.has_keyword(blocker, "flanking"):
                        self.game.modify_until_end_of_turn(blocker, Modifier(-1, -1))

    def _lured(self, attacker: Permanent) -> bool:
        """Whether every creature able to block `attacker` has to: its own text, an effect this turn, or an Aura or Equipment on it."""
        if attacker.lured_turn == self.game.turn or any(r.kind == "all_must_block" for r in combat_restrictions(attacker.card)):
            return True
        return any(p.attached_to is attacker and any(r.kind == "host_must_be_blocked_by_all" for r in combat_restrictions(p.card))
                   for seat in self.game.live_seats() for p in seat.battlefield)

    def _blocking(self, blocker: Permanent) -> int:
        """How many attackers `blocker` blocks."""
        return sum(blocker in a.blockers for a in self.attacks)

    def _block_limit(self, blocker: Permanent) -> int:
        """How many attackers `blocker` may block: one, and more with "can block an additional creature each combat"."""
        if self.game.loses_abilities(blocker):
            return 1
        return 1 + sum(int(r.what) for r in combat_restrictions(blocker.card) if r.kind == "extra_blocks")

    def _block(self, seat: Seat, blocker: Permanent, attack: Attack) -> None:
        first = not self._blocking(blocker)
        attack.blockers.append(blocker)
        if first:  # "Whenever this creature blocks": once, however many it blocks
            self.game.trigger("blocks", blocker, seat)
        self.game.broadcast({"event": "block", "seat": seat.index, "card": blocker.card.name,
                             "attacker": attack.attacker.card.name})

    @staticmethod
    def _has_enough_blockers(attack: Attack) -> bool:
        """Whether a creature that "can't be blocked by more than one creature" already has all the blockers it can have."""
        return any(r.kind == "max_blockers" and len(attack.blockers) >= int(r.what) for r in combat_restrictions(attack.attacker.card))

    def has_first_strike(self) -> bool:
        creatures = [a.attacker for a in self.attacks] + [b for a in self.attacks for b in a.blockers]
        return any(self._has(c, "first strike") or self._has(c, "double strike") for c in creatures)

    def deal_damage(self, first_strike_step: bool) -> None:
        """Combat damage is worked out first, then dealt all at once (CR 510.1-510.2)."""
        hits: list[tuple[Permanent, Seat | Permanent, int]] = []
        split: list[Permanent] = []  # the blockers whose damage was divided among the attackers they block
        for attack in self.attacks:
            attacker = attack.attacker
            if not self.game.on_battlefield(attacker):
                continue
            blockers = [b for b in attack.blockers if self.game.on_battlefield(b)]
            # What it is attacking: the player, or the planeswalker (nothing, if that has left the battlefield).
            victim = attack.walker if attack.walker is not None else attack.defender
            if attack.walker is not None and not self.game.on_battlefield(attack.walker):
                victim = None
            if self._deals_damage_now(attacker, first_strike_step):
                amount = max(0, self.game.power(attacker))
                if not attack.blocked:
                    if victim is not None:
                        hits.append((attacker, victim, amount))
                else:
                    hits += self._assign(attacker, attack.controller, blockers, victim, amount)
            for blocker in blockers:
                if self._deals_damage_now(blocker, first_strike_step) and blocker not in split:
                    blocked = [a.attacker for a in self.attacks if blocker in a.blockers and self.game.on_battlefield(a.attacker)]
                    if len(blocked) > 1:  # CR 510.1d: a creature blocking several divides its damage among them
                        split.append(blocker)
                        controller = self.game.controller(blocker)
                        hits += self._assign(blocker, controller, blocked, None, max(0, self.game.power(blocker)))
                    else:
                        hits.append((blocker, attacker, max(0, self.game.power(blocker))))
        from .game import Seat  # game imports this module, so it can't be imported at the top
        hit_players: dict[tuple[int, int], tuple[Seat, list[Permanent]]] = {}  # (hitter, player hit) -> who did it
        dealt: dict[tuple[int, int], dict[int, int]] = {}  # the same key -> how much each of them dealt
        outer = self.game._batch
        self.game._batch = set() if outer is None else outer  # watchers of "one or more ... deal combat damage" hear of it once
        try:
            for source, target, amount in hits:
                if amount > 0:
                    hitter = self.game.controller_of(source)
                    self.game.damage(target, amount, source=source, combat=True)
                    if hitter is not None and isinstance(target, Seat):  # a player, not a permanent
                        hit_players.setdefault((hitter.index, target.index), (hitter, []))[1].append(source)
                        dealt.setdefault((hitter.index, target.index), {})[id(source)] = amount
        finally:
            self.game._batch = outer
        for key, (hitter, sources) in hit_players.items():  # "Whenever one or more creatures you control deal combat damage ..."
            zero_power = [s for s in sources if s.card.power == "0"]  # base power 0 (Primo): the damage they dealt
            for permanent in list(hitter.battlefield):
                self.game.trigger("creatures_combat_damage", permanent, hitter, subject=sources[0])
                if zero_power:
                    self.game.trigger("zero_power_combat_damage", permanent, hitter, subject=zero_power[0],
                                      x=sum(dealt[key][id(s)] for s in zero_power))
                if any(s.card.type_line.startswith("Token") for s in sources):
                    self.game.trigger("tokens_combat_damage", permanent, hitter, subject=sources[0])
                if artifacts := [s for s in sources if "Artifact" in s.card.type_line.partition("\u2014")[0]]:
                    self.game.trigger("artifact_creatures_combat_damage", permanent, hitter, subject=artifacts[0])
        for (_, hit_index), (hitter, _) in hit_players.items():  # "Whenever one or more creatures an opponent controls deal combat damage to
            hit = self.game.seats[hit_index]  # you": once for each opponent whose creatures hit you
            if hit is not hitter:
                for permanent in list(hit.battlefield):
                    self.game.trigger("opponent_creatures_combat_damage_you", permanent, hit, player=hitter)
        for hitter in {id(h): h for h, _ in hit_players.values()}.values():  # "... to one or more players": once for the damage step
            sources = [s for h, hit in hit_players.values() if h is hitter for s in hit]
            for permanent in list(hitter.battlefield):
                self.game.trigger("creatures_combat_damage_players", permanent, hitter, subject=sources[0])

    def _assign(self, attacker: Permanent, controller: Seat, blockers: list[Permanent], defender: Seat | Permanent | None,
                amount: int) -> list[tuple[Permanent, Seat | Permanent, int]]:
        """Lethal damage to each blocker in an order its controller chooses, the rest to the last one, or to
        the player or planeswalker with trample (CR 510.1c-d)."""
        blockers = self._damage_order(attacker, controller, blockers) if amount > 0 else blockers
        deathtouch = self.game.has_keyword(attacker, "deathtouch")
        trample = self.game.has_keyword(attacker, "trample")
        hits: list[tuple[Permanent, Seat | Permanent, int]] = []
        for blocker in blockers:
            share = min(amount, self._lethal_damage(blocker, deathtouch))
            hits.append((attacker, blocker, share))
            amount -= share
        if amount > 0 and trample and defender is not None:
            hits.append((attacker, defender, amount))
        elif amount > 0 and hits:
            source, target, share = hits[-1]
            hits[-1] = (source, target, share + amount)
        return hits

    def _damage_order(self, attacker: Permanent, controller: Seat, blockers: list[Permanent]) -> list[Permanent]:
        """With several blockers the attacker's controller picks which gets lethal damage first, then next, ..."""
        remaining, ordered = list(blockers), []
        while len(remaining) > 1:
            pick = controller.player.choose(ASSIGN_PROMPT(self.game.label(attacker)),
                                            [self.game.label(b) for b in remaining])
            ordered.append(remaining.pop(pick))
        return ordered + remaining

    def _lethal_damage(self, permanent: Permanent, deathtouch: bool) -> int:
        """Damage still needed to destroy a blocker; any amount is lethal with deathtouch."""
        current = self.game.toughness(permanent)
        if deathtouch or current is None:
            return 1
        return max(0, current - permanent.damage)

    def _has(self, permanent: Permanent, keyword: str) -> bool:
        return self.game.has_keyword(permanent, keyword)

    def _can_attack(self, permanent: Permanent) -> bool:
        return ("Creature" in permanent.card.type_line and not permanent.tapped and self.game.no_attacks_turn != self.game.turn
                and not (permanent.sick and not self._has(permanent, "haste"))
                and not (self._has(permanent, "defender") and permanent.defender_ok_turn != self.game.turn)
                and not self._has(permanent, CANT_ATTACK) and not self._unless_unmet(permanent, "attack"))

    def _unless_unmet(self, permanent: Permanent, action: str) -> bool:
        """ "This creature can't attack or block unless you control seven or more lands.": a condition that doesn't hold now."""
        return any(r.kind == "unless" and r.condition is not None and action in r.what.split(" or ")
                   and not self.game.condition_holds(r.condition, self.game.controller(permanent), permanent)
                   for r in combat_restrictions(permanent.card))

    def _can_block(self, blocker: Permanent, attacker: Permanent) -> bool:
        if self._has(blocker, CANT_BLOCK) or self._has(blocker, "decayed") or self._has(attacker, CANT_BE_BLOCKED):
            return False
        if self._unless_unmet(blocker, "block"):
            return False
        if self._has(attacker, "shadow") != self._has(blocker, "shadow"):  # shadow blocks and is blocked only by shadow
            return False
        if self._evades(blocker, attacker):
            return False
        if any(k.startswith(ONLY_BLOCKED_BY) and not self._passes(blocker, k.removeprefix(ONLY_BLOCKED_BY))
               for m in self.game.modifiers(attacker) for k in m.keywords):
            return False  # Gingerbrute: "can't be blocked this turn except by creatures with haste"
        if any(k.startswith(NOT_BLOCKED_BY) and self._passes(blocker, k.removeprefix(NOT_BLOCKED_BY))
               for m in self.game.modifiers(attacker) for k in m.keywords):
            return False  # Skrelv, Defector Mite: "It can't be blocked by creatures of that color this turn."
        for r in combat_restrictions(attacker.card):  # "can't be blocked by creatures with power 2 or less", "... except by black creatures"
            if (r.kind == "not_blocked_by" and self._passes(blocker, r.what)) \
                    or (r.kind == "only_blocked_by" and not self._passes(blocker, r.what)):
                return False
        if any(r.kind == "cant_block" and self._passes(attacker, r.what) for r in combat_restrictions(blocker.card)):
            return False  # "This creature can't block creatures with power 3 or greater."
        if self._has(attacker, "skulk") and self.game.power(blocker) > self.game.power(attacker):
            return False
        if blocker.counters.get("+1/+1", 0) > 0 and any(r.kind == "unleashed" for r in combat_restrictions(blocker.card)) \
                and not self.game.loses_abilities(blocker):
            return False  # Unleash (CR 702.98a): it can't block as long as it has a +1/+1 counter on it (and has the ability)
        if any(r.kind == "block_only_flying" for r in combat_restrictions(blocker.card)) and not self._has(attacker, "flying"):
            return False  # Brazen Borrower
        if any(r.kind == "weaker_cant_block" for r in combat_restrictions(attacker.card)) \
                and self.game.power(blocker) < self.game.power(attacker):
            return False  # Elusive Otter
        if self.game.protected_from(attacker, source_qualities(blocker.card)):  # can't be blocked by those colors
            return False
        if self._has(attacker, "flying"):
            return self._has(blocker, "flying") or self._has(blocker, "reach")
        return True

    def _passes(self, creature: Permanent, test: str) -> bool:
        """Whether a creature passes a restriction's test: "power<=2", "power>=3", "type:Artifact", "color:U", "keyword:flying"."""
        kind, _, value = test.partition(":")
        if test.startswith("power"):
            power = self.game.power(creature)
            return power <= int(test[7:]) if test[5] == "<" else power >= int(test[7:])
        if kind == "type":
            return value in creature.card.type_line
        if kind == "color":
            return value in creature.card.colors
        return self._has(creature, value)

    def _evades(self, blocker: Permanent, attacker: Permanent) -> bool:
        """Whether the attacker's fear, intimidate, horsemanship or landwalk keeps this creature from blocking it."""
        colors = attacker.card.colors
        if self._has(attacker, "fear") and not ("Artifact" in blocker.card.type_line or "B" in blocker.card.colors):
            return True
        if self._has(attacker, "intimidate") and not ("Artifact" in blocker.card.type_line
                                                      or set(colors) & set(blocker.card.colors)):
            return True
        if self._has(attacker, "horsemanship") and not self._has(blocker, "horsemanship"):
            return True
        defender = self.game.controller_of(blocker)
        return defender is not None and any(
            self._has(attacker, f"{land.lower()}walk")
            and any("Land" in p.card.type_line and land in p.card.type_line for p in defender.battlefield)
            for land in LANDWALKS)

    def _deals_damage_now(self, permanent: Permanent, first_strike_step: bool) -> bool:
        first, double = self._has(permanent, "first strike"), self._has(permanent, "double strike")
        return first or double if first_strike_step else double or not first
