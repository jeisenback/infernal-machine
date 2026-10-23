"""Casting a spell (CR 601): the ways to cast it, its costs and options, its targets, and putting it on the stack.

`Game` holds a `Caster` (as it holds a `Combat` and a `ManaPayer`) and keeps thin methods that call it, so the effects and the tests
go through `game._cast`, `game._payment` and the like as before. The caster reads and changes the game through its back-reference.
Names defined in `game.py` (the prompts, `StackItem`, the card helpers) are reached as `g.NAME`, since `game.py` imports this module.
"""

from __future__ import annotations

import dataclasses
import itertools
from typing import Callable

from .analysis import is_land
from .cards import Card, has_keyword
from .characteristics import source_qualities
from .effects import (AlternativeCost, AttachAura, Cascade, CopySpellTimes, Demonstrate, Draw, GainLife, GraveyardCast, Modal, MorphCost,
                      Scry, TriggeredAbility, additional_costs, affinity_for, alternative_costs, buyback_cost, buyback_other_cost,
                      chosen_cost_reductions, conditional_cost_reduction, cost_reductions, entwine_cost, escalate_cost, gift_of,
                      granted_affinity, is_multikicker, kicked_effects, kicker_costs, kicker_other_cost, mana_ability_sacrifices,
                      mana_spent_trigger, non_hand_cost_reduction, overloaded_effects, reduced_by_greatest_power, reduced_by_total_power,
                      replicate_cost, restricted_mana, self_cost_reduction, storm_kind, strive_cost, target_kind, triggered_abilities,
                      x_limited_by_players, x_spell_discount)
from .filters import has_type, parse_filter
from .mana import Cost, cost_of, parse_cost
from .payment import Payment

from . import game as g


class Caster:
    """Everything between choosing to cast a spell and the spell being on the stack."""

    def __init__(self, game: g.Game):
        self.game = game

    def _cast(self, seat: g.Seat, card: Card, zone: list[Card], from_command_zone: bool = False,
              graveyard: GraveyardCast | None = None, prepared: g.Permanent | None = None, free: bool = False,
              copy: bool = False, bottom_after: bool = False, madness: AlternativeCost | None = None,
              whole: Card | None = None, face_down: tuple[str, MorphCost] | None = None) -> None:
        effects = g._effects(card)
        paying = dataclasses.replace(card, mana_cost=graveyard.cost) if graveyard else card
        extra = ""
        if effects and isinstance(effects[0], Modal):
            effects, extra = self._choose_modes(seat, card, effects[0], from_command_zone, casting=True)
        # Alternative costs and kicker are announced before targets are chosen (CR 601.2b-c).
        ways = ([AlternativeCost("Cast without paying its mana cost")] if free else [madness] if madness
                else self._cast_ways(seat, card, from_command_zone, graveyard, zone is seat.hand))
        alternative = ways[0]
        if len(ways) > 1:
            options = [f"Pay {card.mana_cost}" if way is None else way.text for way in ways]
            alternative = ways[seat.player.choose(g.COST_PROMPT(card.name), options)]
        if alternative and alternative.bestow:  # an Aura spell that must target a creature
            effects = [AttachAura("creature")]
        if alternative and alternative.overload:  # every "target" is "each": no targets
            effects = overloaded_effects(card) or effects
        kicked, kickers = (0, ()) if graveyard else self._choose_kicks(seat, card, effects, from_command_zone, alternative)
        gift = None if graveyard or prepared is not None or copy else self._choose_gift(seat, card, effects)
        kicked = kicked or int(gift is not None)  # a promised gift is a kick that costs nothing
        replicated = 0 if graveyard or prepared is not None else self._choose_replicate(seat, card, from_command_zone, kickers, extra, alternative)
        if replicated:
            extra += g._checked(replicate_cost(card)) * replicated
        bought_back = self._choose_buyback(seat, card, from_command_zone, kickers, extra, alternative)
        if bought_back:
            extra += buyback_cost(card) or ""
        effects = kicked_effects(effects, kicked, kickers)
        picked = self._pick_options(seat, card, alternative, kicked, bought_back, lambda mana: self._payment(
            seat, paying, from_command_zone, 0, alternative, kickers, extra + mana))
        if free and not self._can_pay_extras(seat, card, alternative, kicked, bought_back):
            # CR 601.2b, 601.2h: a spell whose additional cost can't be paid can't be cast, even for free (cascade, suspend ...): it stays where it is
            self.game.broadcast({"event": "cant_cast", "seat": seat.index, "card": card.name})
            return
        extra += "".join(o.mana for o in picked)  # "pay {3}{B}" as an additional cost
        x = 0  # announced before the targets (CR 601.2b-c): "up to X target creatures" needs it
        if alternative is None and (cost_of(paying.mana_cost).x or any(c.sacrifice_x for c in additional_costs(card))):
            # casting without paying the mana cost makes X 0; Immoral Bargain has X only in its additional cost
            most = self._max_x(seat, paying, from_command_zone, kickers, extra)
            for effect in effects or []:  # "Exile X target creatures": there have to be X legal targets
                if getattr(effect, "exact_x", False):
                    most = min(most, len(self.game.target_options(g._checked(target_kind(effect)), seat, source_qualities(card))))
            if x_limited_by_players(card):
                most = min(most, len(self.game.live_seats()))
            for cost in additional_costs(card):  # "sacrifice X creatures": there have to be X of them, after the mana has taken its sources
                if cost.sacrifice_x:
                    kind = g._checked(cost.sacrifice)
                    most = min(most, sum(g._permanent_matches(kind, p.card) for p in seat.battlefield))
                    while most and sum(g._permanent_matches(kind, p.card) for p in seat.battlefield
                                       if id(p) not in self._sacrificed_for_mana(self._payment(
                                           seat, paying, from_command_zone, most, alternative, kickers, extra) or [])) < most:
                        most -= 1
            choices = self._x_values_with_targets(seat, effects, source_qualities(card), most)
            if not choices:  # nothing could be targeted for any X that can be paid
                return
            x = choices[seat.player.choose(g.X_PROMPT(card.name), [str(n) for n in choices])]
        elif any(c.life_x for c in additional_costs(card)):  # "pay X life": any amount that leaves you alive
            x = seat.player.choose(g.LIFE_X_PROMPT(card.name), [str(n) for n in range(max(seat.life, 1))])
        self.game.targeting_x = x
        strive = strive_cost(card)
        if strive:  # as many targets as the mana will pay for: each one beyond the first costs more
            more = 0
            while more < g.MAX_TARGETS and self._payment(seat, paying, from_command_zone, x, alternative, kickers,
                                                       extra + strive * (more + 1)) is not None:
                more += 1
            self.game.targeting_max = more + 1
        chosen_targets = self._choose_targets(seat, effects, card.name, colors=source_qualities(card))
        self.game.targeting_max = None
        if chosen_targets is None:  # no legal target (a free cast: cascade, suspend ...): it isn't cast, and stays where it is
            self.game.broadcast({"event": "cant_cast", "seat": seat.index, "card": card.name})
            return
        targets, labels = chosen_targets
        if strive:
            chosen = sum(len(t) for e, t in zip([e for e in effects or [] if target_kind(e)], targets)
                         if getattr(e, "any_number", False))
            extra += strive * max(0, chosen - 1)
        delve = 0
        if alternative is None and not graveyard and has_keyword(card, "delve"):  # exile as few cards as will do
            delve = next(k for k in range(self.game._delve_max(seat, paying) + 1)
                         if self._payment(seat, paying, from_command_zone, x, alternative, kickers, extra, delve=k) is not None)
        cost = g._checked(self._cast_cost(seat, paying, from_command_zone, x, alternative, kickers, extra, delve=delve))
        with self.game._paying_for(seat, paying):
            tapped = g._checked(self.game._pay_cost(seat, cost))
        self.game._spend_mana(seat, tapped)
        no_counter = any((limited := restricted_mana(p.card)) is not None and limited.uncounterable
                         and self.game._restricted_mana_ok(p, limited, paying) for p in tapped)
        spent = cost.generic + len(cost.colored) + len(cost.twobrid) + len(cost.phyrexian)  # "mana spent to cast it"
        for _ in range(delve):
            exiled = seat.graveyard[seat.player.choose(g.DELVE_PROMPT(card.name), [c.name for c in seat.graveyard])]
            seat.graveyard.remove(exiled)
            self.game.broadcast({"event": "left_graveyard", "seat": seat.index, "card": exiled.name, "to": "exile"})
            self.game._move_card(seat, exiled, "exile")
        if delve:
            self.game._left_graveyard(seat)
        zone.remove(whole or card)
        if prepared is not None:  # a copy of the spell is cast, and the creature is no longer prepared
            prepared.prepared = False
        self._pay_extras(seat, card, alternative, graveyard, x, kicked, bought_back, picked)
        sacrificed = self.game._sacrifice_for_copies(seat, card)
        item = g.StackItem(card, seat, effects, targets, x=x, kicked=kicked, kickers=kickers, gift=gift, bought_back=bought_back, exile_after=bool(graveyard and graveyard.exile_after), bottom_after=bottom_after,
                         foretold=graveyard is not None and graveyard.word == "Foretell", from_graveyard=graveyard is not None and graveyard.word != "Foretell",
                         is_copy=prepared is not None or copy, evoked=bool(alternative and alternative.evoke),
                         escaped=bool(graveyard and graveyard.word == "Escape"),
                         bestowed=bool(alternative and alternative.bestow), mana_spent=spent, cant_be_countered=no_counter,
                         dashed=bool(alternative and alternative.dash), warped=bool(alternative and alternative.warp), whole=whole, face_down=face_down,
                         from_hand=zone is seat.hand, owner=self._cast_owner(seat, card, zone), phyrexian_life=tapped.phyrexian_life)
        self.game.stack.append(item)
        event = {"event": "cast", "seat": seat.index, "card": card.name,
                 "from": "prepared" if prepared else "graveyard" if graveyard else "command_zone" if from_command_zone else "hand",
                 "targets": labels, "x": x, "tapped": [p.card.name for p in tapped]}
        if kicked:
            event["kicked"] = kicked
        if extra:
            event["extra_cost"] = extra
        if alternative:
            event["alternative"] = alternative.text
        self.game.broadcast(event)
        seat.cast_log.append((self.game.turn, card))
        copies = (replicated or 0) + sacrificed
        if (storm := storm_kind(card)) is not None and prepared is None:
            before = [t for s in self.game.seats for t, _ in s.cast_log if t == self.game.turn]  # spells cast before this one
            copies += (len(before) - 1) if storm == "storm" else (self.game.graveyarded_count if self.game.graveyarded_turn == self.game.turn else 0)
        if copies and prepared is None:  # Replicate, Storm, Gravestorm: a trigger above the spell copies it
            ability = TriggeredAbility("cast", (CopySpellTimes(copies),), False, "Copy this spell")
            self.game.stack.append(g.StackItem(card, seat, list(ability.effects), [], ability, carried=item))
        if has_keyword(card, "demonstrate") and prepared is None:
            ability = TriggeredAbility("cast", (Demonstrate(),), False, "Demonstrate")
            self.game.stack.append(g.StackItem(card, seat, list(ability.effects), [], ability, carried=item))
        for ability in triggered_abilities(card):  # "When you cast this spell, ..." (Hydroid Krasis, Artisan of Kozilek)
            if ability.event == "cast_self" and prepared is None:
                cast_effects = list(ability.effects)
                chosen = self._choose_targets(seat, cast_effects, card.name, colors=source_qualities(card))
                if chosen is not None:  # (with no legal target the ability is removed, as any trigger is)
                    self.game.stack.append(g.StackItem(card, seat, cast_effects, chosen[0], ability, x=x))
        for source in tapped or ():  # Study Hall, Path of Ancestry: "When that mana is spent to cast ..., scry"
            if self.game._mana_spent_matches(seat, source, card, from_command_zone, tapped):
                trigger = g._checked(mana_spent_trigger(source.card))
                if trigger.counters:  # Opal Palace: it enters with more counters
                    item.rider_counters += 1
                    continue
                scry = trigger.scry
                count = seat.commander_casts.get(card.name, 0) + 1 if scry == "commander_casts" else int(scry)
                ability = TriggeredAbility("cast", (Scry("X"),), False, f"Scry {count}")
                self.game.stack.append(g.StackItem(source.card, seat, list(ability.effects), [], ability, source, x=count))
        if seat.x_rider_turn == self.game.turn and seat.x_rider_count and "{X}" in card.mana_cost:  # Brass Infiniscope
            ability = TriggeredAbility("cast", (Draw(1), GainLife("hX")), False, "Draw a card and gain half X life")
            for _ in range(seat.x_rider_count):
                self.game.stack.append(g.StackItem(card, seat, list(ability.effects), [], ability, x=x))
            seat.x_rider_count = 0
        if has_keyword(card, "cascade") and prepared is None:  # the trigger goes on the stack above the spell
            ability = TriggeredAbility("cast", (Cascade(int(card.cmc) + x),), False, "Cascade")
            self.game.stack.append(g.StackItem(card, seat, list(ability.effects), [], ability))
        if seat.copy_next_turn == self.game.turn and ("Instant" in card.type_line or "Sorcery" in card.type_line):
            seat.copy_next_turn = None  # a delayed trigger: it copies the spell, with new targets
            copies = sum(seat.commander_casts.values()) if seat.copy_next_per_commander else 1
            if copies:
                ability = TriggeredAbility("cast", (CopySpellTimes(copies),), False, "Copy that spell")
                self.game.stack.append(g.StackItem(card, seat, list(ability.effects), [], ability, carried=item))
        self.game._observe("cast", card, seat, x=x, from_hand=zone is seat.hand and not prepared,
                      prepared=prepared is not None, spell=item, from_graveyard=graveyard is not None and graveyard.word != "Foretell")
        if seat.spent_turn != self.game.turn:
            seat.spent_turn, seat.spent_amount = self.game.turn, 0
        before, seat.spent_amount = seat.spent_amount, seat.spent_amount + spent
        for total in range(before + 1, seat.spent_amount + 1):  # "Whenever you expend N": the Nth mana spent this turn
            self.game._observe("expend", card, seat, x=total)
        for target in (t for chosen in item.targets for t in (chosen if isinstance(chosen, list) else [chosen])):
            if isinstance(target, g.Permanent) and self.game.on_battlefield(target):  # "Whenever this creature becomes the target of a spell"
                self.game.trigger("targeted", target, self.game.controller(target))
        self.game._check_ward(item)

    def _cast_ways(self, seat: g.Seat, card: Card, from_command_zone: bool,
                   graveyard: GraveyardCast | None = None, from_hand: bool = True) -> list[AlternativeCost | None]:
        """The ways `seat` can cast `card` now: None for its mana cost, then its alternative costs. Casting from
        the graveyard has one way: its flashback or escape cost (and enough other cards to exile)."""
        if graveyard:
            paying = dataclasses.replace(card, mana_cost=graveyard.cost)
            others = len(seat.graveyard) - (card in seat.graveyard)
            if graveyard.discard_land and not any(is_land(c) for c in seat.hand):
                return []
            if graveyard.requires and not any(parse_filter(graveyard.requires).matches(p.card) for p in seat.battlefield):
                return []  # Gravecrawler: only while its caster controls a Zombie
            return [None] if others >= graveyard.exile and graveyard.life <= seat.life and self._payment(seat, paying) is not None else []
        return [way for way in [None, *alternative_costs(card)]
                if not (way and way.warp and not from_hand)  # warp is a way to cast from the hand only
                and self._can_pay_extras(seat, card, way, afford=lambda extra, way=way: self._payment(
                    seat, card, from_command_zone, alternative=way, extra=extra,
                    delve=self.game._delve_max(seat, card) if way is None else 0))
                and not (way and way.bestow and not self.game.target_options("creature", seat, source_qualities(card)))]

    def _cast_cost(self, seat: g.Seat, card: Card, from_command_zone: bool = False, x: int = 0,
                   alternative: AlternativeCost | None = None, kickers: tuple[str, ...] = (), extra: str = "",
                   delve: int = 0) -> Cost | None:
        """The mana to pay for `card` with X = `x`. An alternative cost replaces the mana cost; commander tax and
        kicker are added, then cost reductions apply."""
        if alternative:
            cost = parse_cost(alternative.mana_cost) if alternative.mana_cost else Cost()  # Evoke and Overload cost mana
        else:
            cost = parse_cost(card.mana_cost)
        if cost is None:
            return None
        if from_command_zone:
            cost = cost.plus_generic(self.game.commander_tax(seat, card))
        for kicker in kickers:
            cost = cost + cost_of(kicker)
        if extra:  # entwine, or escalate for each mode beyond the first
            cost = cost + cost_of(extra)
        return cost.with_x(x).reduced(self.cost_reduction(seat, card) + delve)

    def cost_reduction(self, seat: g.Seat, card: Card) -> int:
        """How much less generic mana `card` costs `seat` (Medallions and the like)."""
        reduction = sum(amount for p in seat.battlefield for kind, amount in cost_reductions(p.card)
                        if g._spell_matches(kind, card))
        kinds = card.type_line.partition("\u2014")[2].split()
        for owner in self.game.live_seats():  # Herald's Horn, Urza's Incubator: spells of the type a permanent chose
            for p in owner.battlefield:
                if p.chosen_type in kinds and not self.game.loses_abilities(p):
                    reduction += sum(amount for creature_only, yours_only, amount in chosen_cost_reductions(p.card)
                                     if (owner is seat or not yours_only) and ("Creature" in card.type_line or not creature_only))
        if (kind := affinity_for(card)) is not None:  # Affinity for planeswalkers
            reduction += sum(has_type(p.card, kind) for p in seat.battlefield)
        if "{X}" in card.mana_cost and not any("{X}" in c.mana_cost for turn, c in seat.cast_log if turn == self.game.turn):
            reduction += sum(p.counters.get("+1/+1", 0) for p in seat.battlefield if x_spell_discount(p.card))  # Zimone
        for p in seat.battlefield:  # Pearl-Ear, Imperial Advisor: affinity for Auras
            if (kind := granted_affinity(p.card)) and g._spell_matches(kind, card):
                reduction += sum(has_type(a.card, "aura") for a in seat.battlefield)
        if not any(c is card for c in seat.hand):  # Advanced Reconstruction: spells cast from anywhere other than your hand
            reduction += sum(non_hand_cost_reduction(p.card) for p in seat.battlefield)
        if (conditional := conditional_cost_reduction(card)) and self.game.condition_holds(conditional[1], seat):
            reduction += conditional[0]
        if reduced_by_total_power(card):
            reduction += sum(self.game.power(p) for p in seat.battlefield if "Creature" in p.card.type_line)
        if reduced_by_greatest_power(card):  # The Great Henge
            reduction += max((self.game.power(p) for p in seat.battlefield if "Creature" in p.card.type_line), default=0)
        if own := self_cost_reduction(card):  # "This spell costs {1} less to cast for each creature on the battlefield."
            amount, what = own
            counted = (sum(has_type(p.card, "creature") for s in self.game.live_seats() for p in s.battlefield)
                       if what == "creature" else sum(g._card_matches(what, c) for c in seat.graveyard))
            reduction += amount * counted
        return reduction

    def _extra_costs(self, card: Card, kicked: int, bought_back: bool = False) -> list:
        """The non-mana costs of casting `card`: its additional costs, plus a non-mana kicker cost if kicked and a non-mana
        buyback cost if bought back."""
        kicker = kicker_other_cost(card) if kicked else None
        buyback = buyback_other_cost(card) if bought_back else None
        return additional_costs(card) + ([kicker] if kicker else []) + ([buyback] if buyback else [])

    def _can_pay_extras(self, seat: g.Seat, card: Card, alternative: AlternativeCost | None, kicked: int = 0,
                        bought_back: bool = False, afford: Callable[[str], Payment | None] | None = None) -> bool:
        """Whether `seat` can pay the parts of casting `card` that aren't mana: additional costs (one of the options in "sacrifice
        an artifact or discard a card or pay {2}"), a non-mana kicker cost, and `alternative`'s condition, life and card to exile.
        `afford` gives the permanents that pay the mana cost with the extra mana an option adds, or None if it can't be paid."""
        return bool(self._payable_options(seat, card, alternative, kicked, bought_back, afford))

    def _payable_options(self, seat: g.Seat, card: Card, alternative: AlternativeCost | None, kicked: int = 0,
                         bought_back: bool = False, afford: Callable[[str], Payment | None] | None = None) -> list[tuple]:
        """The ways to choose one option of each "this or that" additional cost that `seat` can pay (one empty way if the card
        has none)."""
        extras = self._extra_costs(card, kicked, bought_back)
        plain = [c for c in extras if not c.options]
        ways = []
        for picked in itertools.product(*(c.options for c in extras if c.options)):
            if not self._extras_payable(seat, card, alternative, plain + list(picked)):
                continue
            if afford is not None:
                payment = afford("".join(o.mana for o in picked))
                if payment is None or not self._sacrifices_survive(seat, plain + list(picked), payment):
                    continue
            ways.append(picked)
        return ways

    def _pick_options(self, seat: g.Seat, card: Card, alternative: AlternativeCost | None, kicked: int, bought_back: bool,
                      afford: Callable[[str], Payment | None]) -> tuple:
        """The option of each "this or that" additional cost that `seat` pays: asked when more than one way can be paid."""
        ways = self._payable_options(seat, card, alternative, kicked, bought_back, afford)
        if len(ways) > 1:
            return ways[seat.player.choose(g.COST_PROMPT(card.name), [", ".join(g._extra_text(o) for o in way) for way in ways])]
        return ways[0] if ways else ()

    def _extras_payable(self, seat: g.Seat, card: Card, alternative: AlternativeCost | None, extras: list) -> bool:
        others = list(seat.hand)
        if card in others:
            others.remove(card)
        if sum(c.life for c in extras) + (alternative.life if alternative else 0) > seat.life:  # CR 119.4
            return False
        if sum(c.discard for c in extras) > len(others):
            return False
        for kind in {c.sacrifice for c in extras if c.sacrifice and not c.sacrifice_x}:
            needed = sum(c.sacrifice == kind for c in extras if not c.sacrifice_x)
            if sum(g._permanent_matches(kind, p.card) for p in seat.battlefield) < needed:
                return False
        if alternative is None:
            return True
        if alternative.commander and not any(p.card.name in (p.owner or seat).commander_names for p in seat.battlefield):
            return False
        if alternative.not_your_turn and self.game.active == seat.index:
            return False
        return not alternative.exile_color or any(alternative.exile_color in c.colors for c in others)

    def _pay_extras(self, seat: g.Seat, card: Card, alternative: AlternativeCost | None,
                    graveyard: GraveyardCast | None = None, x: int = 0, kicked: int = 0, bought_back: bool = False,
                    picked: tuple = ()) -> None:
        """Pay the non-mana costs of casting `card`, which has already left its zone."""
        for _ in range(graveyard.exile if graveyard else 0):  # Escape: exile other cards from the graveyard
            exiled = seat.graveyard[seat.player.choose(g.ESCAPE_PROMPT, [c.name for c in seat.graveyard])]
            seat.graveyard.remove(exiled)
            self.game.broadcast({"event": "left_graveyard", "seat": seat.index, "card": exiled.name, "to": "exile"})
            self.game._move_card(seat, exiled, "exile")
        if graveyard and graveyard.exile:
            self.game._left_graveyard(seat)
        if graveyard and graveyard.life:  # "Flashback\u2014{1}{U}, Pay 3 life."
            self.game.change_life(seat, -graveyard.life)
        if graveyard and graveyard.discard_land:  # Retrace
            lands = [c for c in seat.hand if is_land(c)]
            discarded = lands[seat.player.choose(g.DISCARD_PROMPT, [c.name for c in lands])]
            seat.hand.remove(discarded)
            self.game.broadcast({"event": "discard", "seat": seat.index, "card": discarded.name})
            self.game._move_card(seat, discarded, "graveyard")
        if alternative and alternative.exile_color:
            options = [c for c in seat.hand if alternative.exile_color in c.colors]
            exiled = options[seat.player.choose(g.PITCH_PROMPT, [c.name for c in options])]
            seat.hand.remove(exiled)
            self.game.broadcast({"event": "exiled_from_hand", "seat": seat.index, "card": exiled.name})
            self.game._move_card(seat, exiled, "exile")
        extras = [c for c in self._extra_costs(card, kicked, bought_back) if not c.options] + list(picked)
        for extra in extras:
            if extra.discard:
                discarded = seat.hand[seat.player.choose(g.DISCARD_PROMPT, [c.name for c in seat.hand])]
                seat.hand.remove(discarded)
                self.game.broadcast({"event": "discard", "seat": seat.index, "card": discarded.name})
                self.game._discard_into_zone(seat, discarded)
            for _ in range(x if extra.sacrifice_x else 1 if extra.sacrifice else 0):
                options = [p for p in seat.battlefield if g._permanent_matches(extra.sacrifice, p.card)]
                choice = options[seat.player.choose(g.SACRIFICE_COST_PROMPT(card.name), [self.game.label(p) for p in options])]
                self.game._leave_together([(choice, "sacrificed")])
        life = (sum(c.life for c in extras) + (alternative.life if alternative else 0)
                + (x if any(c.life_x for c in additional_costs(card)) else 0))
        if life:
            self.game.change_life(seat, -life)

    def _max_x(self, seat: g.Seat, card: Card, from_command_zone: bool, kickers: tuple[str, ...], extra: str = "") -> int:
        x = 0
        while x < g.MAX_X and self._payment(seat, card, from_command_zone, x + 1, kickers=kickers, extra=extra) is not None:
            x += 1
        return x

    def _choose_kicks(self, seat: g.Seat, card: Card, effects: list | None, from_command_zone: bool,
                      alternative: AlternativeCost | None) -> tuple[int, tuple[str, ...]]:
        """Ask which kicker costs to pay: yes or no, any affordable number for multikicker, or each of two kicker
        costs. Returns (times kicked, mana kicker costs paid). A kick is only offered when it can be paid and the
        spell's kicked targets exist."""
        costs = kicker_costs(card)
        if not costs and kicker_other_cost(card) is None:
            return 0, ()

        def possible(kickers: tuple[str, ...], kicked: int) -> bool:
            return (self.game._targets_exist(seat, kicked_effects(effects, kicked, kickers) or [], source_qualities(card))
                    and self._can_pay_extras(seat, card, alternative, kicked)
                    and self._payment(seat, card, from_command_zone, alternative=alternative, kickers=kickers) is not None)

        if is_multikicker(card):
            most = 0
            while most < g.MAX_X and possible(costs * (most + 1), most + 1):
                most += 1
            times = seat.player.choose(g.MULTIKICKER_PROMPT(card.name), [str(n) for n in range(most + 1)]) if most else 0
            return times, costs * times
        if len(costs) == 2:
            chosen: tuple[str, ...] = ()
            for cost in costs:
                if (possible(chosen + (cost,), len(chosen) + 1)
                        and seat.player.choose(g.KICKER_PROMPT(f"{card.name} ({cost})"), g.YES_NO) == 0):
                    chosen += (cost,)
            return len(chosen), chosen
        if possible(costs, 1) and seat.player.choose(g.KICKER_PROMPT(card.name), g.YES_NO) == 0:
            return 1, costs
        return 0, ()

    def _choose_buyback(self, seat: g.Seat, card: Card, from_command_zone: bool, kickers: tuple[str, ...], extra: str,
                        alternative: AlternativeCost | None) -> bool:
        """Buyback: ask whether to pay it, when the spell has one and it can be paid on top of everything else."""
        mana = buyback_cost(card)
        if mana is None and buyback_other_cost(card) is None:
            return False
        return (self._can_pay_extras(seat, card, alternative, bought_back=True)
                and self._payment(seat, card, from_command_zone, alternative=alternative, kickers=kickers,
                                  extra=extra + (mana or "")) is not None
                and seat.player.choose(g.BUYBACK_PROMPT(card.name), g.YES_NO) == 0)

    def _choose_gift(self, seat: g.Seat, card: Card, effects: list | None) -> g.Seat | None:
        """Gift: the caster may promise an opponent the gift as the spell is cast (only if what a promised gift adds can be done).
        Returns that opponent, or None."""
        if gift_of(card) is None:
            return None
        opponents = [o for o in self.game.opponents(seat) if not o.lost]
        if not opponents or not self.game._targets_exist(seat, kicked_effects(effects, 1) or [], source_qualities(card)):
            return None
        pick = seat.player.choose(g.GIFT_PROMPT(card.name), ["Don't promise a gift"] + [f"Give it to {o.name} (seat {o.index})" for o in opponents])
        return opponents[pick - 1] if pick else None

    def _choose_modes(self, seat: g.Seat, card: Card, modal: Modal, from_command_zone: bool = False,
                      casting: bool = False, source: g.Permanent | None = None) -> tuple[list, str]:
        """Ask the controller for the modes of a modal spell or ability (only ones with legal targets are offered):
        the chosen modes' effects in printed order, and any extra mana cost for them. When casting, entwine (all the
        modes) and escalate (each mode beyond the first) are offered if they can be paid for."""
        colors = source_qualities(card)
        available = [i for i, effects in enumerate(modal.modes) if self.game._targets_exist(seat, effects, colors, source)]
        if len(available) < (min(modal.min, 1) if modal.repeat else modal.min):
            return [], ""
        if modal.optional and seat.player.choose(g.OPTIONAL_PROMPT(card.name), g.YES_NO) != 0:
            return [], ""  # "you may choose two": declined
        entwine, escalate = (entwine_cost(card), escalate_cost(card)) if casting else (None, None)
        if modal.commander_both and any(p.card.name in (p.owner or seat).commander_names for p in seat.battlefield):
            modal = dataclasses.replace(modal, max=len(modal.modes))  # "if you control a commander ... you may choose both"
        if (entwine and len(available) == len(modal.modes) > 1
                and self._payment(seat, card, from_command_zone, extra=entwine) is not None
                and seat.player.choose(g.ENTWINE_PROMPT(card.name), g.YES_NO) == 0):
            return [effect for modes in modal.modes for effect in modes], entwine
        chosen: list[int] = []
        if modal.mode_costs:  # Spree: one or more modes, each adding its cost, as many as the caster can pay for (CR 702.172)
            paid = ""
            while True:
                affordable = [i for i in available if i not in chosen
                              and self._payment(seat, card, from_command_zone, extra=paid + modal.mode_costs[i]) is not None]
                if not affordable:
                    break
                options = [g._shown(modal.texts[i], card) for i in affordable] + ([g.DONE_MODES] if chosen else [])
                pick = seat.player.choose(g.MODE_PROMPT(card.name), options)
                if pick == len(affordable):
                    break
                chosen.append(affordable[pick])
                paid += modal.mode_costs[affordable[pick]]
            return [effect for i in sorted(chosen) for effect in modal.modes[i]], paid
        if modal.costs:  # a Season: spend up to `max` pawprints, each mode as often as it fits
            left = modal.max
            while usable := [i for i in available if modal.costs[i] <= left]:
                pick = seat.player.choose(g.MODE_PROMPT(card.name), [g._shown(modal.texts[i], card) for i in usable] + [g.DONE_MODES])
                if pick == len(usable):
                    break
                chosen.append(usable[pick])
                left -= modal.costs[usable[pick]]
            return [effect for i in sorted(chosen) for effect in modal.modes[i]], ""
        while len(chosen) < modal.max and (modal.repeat or len(chosen) < len(available)):
            if escalate and chosen and self._payment(seat, card, from_command_zone,
                                                     extra=escalate * len(chosen)) is None:
                break  # another mode would cost more than the caster has
            remaining = [i for i in available if modal.repeat or i not in chosen]
            options = [g._shown(modal.texts[i], card) for i in remaining]
            if len(chosen) >= modal.min:
                options.append(g.DONE_MODES)
            pick = seat.player.choose(g.MODE_PROMPT(card.name), options)
            if pick == len(remaining):
                break
            chosen.append(remaining[pick])
        extra = escalate * (len(chosen) - 1) if escalate and len(chosen) > 1 else ""
        return [effect for i in sorted(chosen) for effect in modal.modes[i]], extra

    def _choose_targets(self, seat: g.Seat, effects, source_name: str, source: g.Permanent | None = None,
                        colors: frozenset[str] = frozenset()) -> tuple[list, list[str]] | None:
        self.game.targeting_source = source
        try:
            return self._choose_targets_now(seat, effects, source_name, source, colors)
        finally:
            self.game.targeting_source = None

    def _choose_targets_now(self, seat: g.Seat, effects, source_name: str, source: g.Permanent | None = None,
                            colors: frozenset[str] = frozenset()) -> tuple[list, list[str]] | None:
        """Ask `seat` for a target per targeting effect: (targets, labels), or None if one has no legal target.
        "Another target ..." can't be `source` itself, and
        nothing with protection from `colors` (the colors of the spell or source) can be chosen."""
        targets, labels = [], []
        chosen: dict[str, set[int]] = {}  # kind -> which of its options were already chosen ("up to two target ...")
        for effect in effects or []:
            kind = target_kind(effect)
            if not kind:
                continue
            kind = self.game._fixed_kind(kind, source)
            if getattr(effect, "per_player", False):  # "for each player, ... up to one target creature that player controls"
                picked = []
                for owner in self.game.turn_order_from_active():
                    pool = [o for o in self.game.target_options(kind, seat, colors) if self.game.controller_of(o[1]) is owner]
                    if pool:
                        pick = seat.player.choose(g.TARGET_PROMPT(source_name), [o[0] for o in pool] + [g.NO_TARGET])
                        if pick < len(pool):
                            picked.append(pool[pick][1])
                targets.append(picked)
                labels.append(", ".join(self.game.label(p) for p in picked) or g.NO_TARGET)
                continue
            if getattr(effect, "up_to_x", False) or getattr(effect, "any_number", False):
                # "up to X target creatures", "X target creatures", "any number of target creatures": one slot holding a list
                picked: list = []
                picked_labels: list[str] = []
                taken_here = set()
                exact = getattr(effect, "exact_x", False)  # "X target creatures": no stopping early
                limit = self.game.targeting_x if getattr(effect, "up_to_x", False) else (
                    getattr(effect, "max_targets", 0) or (self.game.targeting_max if self.game.targeting_max is not None else g.MAX_TARGETS))
                for _ in range(limit):
                    pool = [(i, o) for i, o in enumerate(self.game.target_options(kind, seat, colors)) if i not in taken_here
                            and not (getattr(effect, "another", False) and self.game.option_is_source(o[1], source))]  # "other target creatures"
                    if not pool:
                        break
                    pick = seat.player.choose(g.TARGET_PROMPT(source_name),
                                              [o[1][0] for o in pool] + ([] if exact else [g.NO_TARGET]))
                    if pick == len(pool):
                        break
                    taken_here.add(pool[pick][0])
                    picked.append(pool[pick][1][1])
                    picked_labels.append(pool[pick][1][0])
                targets.append(picked)
                labels.append(", ".join(picked_labels) or g.NO_TARGET)
                continue
            taken = chosen.setdefault(kind, set())
            options = [(i, o) for i, o in enumerate(self.game.target_options(kind, seat, colors))
                       if not (getattr(effect, "another", False) and self.game.option_is_source(o[1], source))
                       and not (getattr(effect, "same_controller", False) and targets
                                and self.game.controller_of(o[1]) is not self.game.controller_of(targets[-1]))
                       and not (getattr(effect, "distinct", False) and i in taken)]
            if getattr(effect, "optional_target", False):  # "up to one target": it can be left out
                options.append((-1, (g.NO_TARGET, None)))
            if not options:
                return None
            index, (label, target) = options[seat.player.choose(g.TARGET_PROMPT(source_name), [o[1][0] for o in options])]
            if index >= 0:
                taken.add(index)
            targets.append(target)
            labels.append(label)
        return targets, labels

    def _payment(self, seat: g.Seat, card: Card, from_command_zone: bool = False, x: int = 0,
                 alternative: AlternativeCost | None = None, kickers: tuple[str, ...] = (), extra: str = "",
                 delve: int = 0) -> Payment | None:
        """The permanents to tap for `card` with X = `x`, or None if it can't be paid for now."""
        cost = self._cast_cost(seat, card, from_command_zone, x, alternative, kickers, extra, delve)
        if cost is None:
            return None
        with self.game._paying_for(seat, card):
            return self.game._pay_cost(seat, cost)

    def _x_values_with_targets(self, seat: g.Seat, effects, colors: frozenset[str], most: int) -> list[int]:
        """The X from 0 to `most` for which every "target creature with mana value X" has a legal target. Any X will do
        for a spell whose targets don't depend on X."""
        kinds = [kind for e in effects or [] if (kind := target_kind(e)) and kind.endswith(" with mana value x")]
        if not kinds:
            return list(range(most + 1))
        saved, good = self.game.targeting_x, []
        try:
            for n in range(most + 1):
                self.game.targeting_x = n
                if all(self.game.target_options(self.game._fixed_kind(kind, None), seat, colors) for kind in kinds):
                    good.append(n)
        finally:
            self.game.targeting_x = saved
        return good

    def _cast_owner(self, seat: g.Seat, card: Card, zone: list[Card]) -> g.Seat | None:
        """Whose card `card` is when `seat` casts it from `zone` and it isn't theirs: the seat whose zone it is in, or the one
        Ragavan took it from. None for the caster's own card."""
        for other in self.game.seats:
            if other is not seat and any(zone is z for z in (other.hand, other.graveyard, other.exile, other.library)):
                return other
        if zone is seat.exile:
            entry = next((e for e in seat.borrowed if e[0] is card), None)
            if entry is not None:
                seat.borrowed.remove(entry)
                return entry[1]
        return None

    def _sacrifices_survive(self, seat: g.Seat, extras: list, payment: list[g.Permanent]) -> bool:
        """Whether enough permanents are left for the sacrifice costs once the mana payment has sacrificed the sources that go
        with their mana (a Treasure or an Eldrazi Spawn can pay for the mana or be the sacrifice, not both)."""
        spent = self._sacrificed_for_mana(payment)
        for kind in {c.sacrifice for c in extras if c.sacrifice and not c.sacrifice_x}:
            needed = sum(c.sacrifice == kind for c in extras if not c.sacrifice_x)
            if sum(g._permanent_matches(kind, p.card) for p in seat.battlefield if id(p) not in spent) < needed:
                return False
        return True

    @staticmethod
    def _sacrificed_for_mana(payment: list[g.Permanent]) -> set[int]:
        """The sources in a mana payment that are sacrificed to make their mana (Treasure, Eldrazi Spawn), by id."""
        return {id(p) for p in payment if not is_land(p.card) and mana_ability_sacrifices(p.card)}

    def _choose_replicate(self, seat: g.Seat, card: Card, from_command_zone: bool, kickers: tuple[str, ...], extra: str,
                          alternative: AlternativeCost | None) -> int:
        """Replicate {cost}: how many times to pay it (any affordable number)."""
        cost = replicate_cost(card)
        if cost is None:
            return 0
        most = 0
        while (most < g.MAX_X and self._payment(seat, card, from_command_zone, alternative=alternative, kickers=kickers,
                                              extra=extra + cost * (most + 1)) is not None):
            most += 1
        return seat.player.choose(g.REPLICATE_PROMPT(card.name), [str(n) for n in range(most + 1)]) if most else 0
