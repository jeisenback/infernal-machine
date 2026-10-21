"""Paying for things with mana (CR 106, 601.2g-h): which permanents can make which mana, what pays a cost, and tapping them.

`Game` holds a `ManaPayer` (as it holds a `Combat`) and keeps thin methods that call it, so the effects and the tests go through
`game._pay_cost` and the like as before. The payer reads the board through its back-reference to the game.
"""

from __future__ import annotations

import contextlib
import dataclasses
from dataclasses import dataclass
from itertools import combinations, permutations
from typing import TYPE_CHECKING

from .analysis import is_land
from .cards import Card, has_keyword
from .effects import (additional_land_mana, charge_mana, chosen_color_mana, counter_mana, counter_removal_mana, filter_mana_ability,
                      granted_land_mana, granted_mana, group_mana_grants, has_next_x_rider, is_identity_mana_land, land_mana_units,
                      makes_mana_by_power, mana_ability, mana_ability_needs_no_tap, mana_ability_sacrifices, mana_among_legendary,
                      mana_bonus, mana_condition, mana_extra_cost, mana_life_condition, mana_life_cost, mana_life_types, mana_lines,
                      mana_of_imprinted, mana_pain, mana_per_count, mana_restriction, mana_threshold, reflected_mana, restricted_mana,
                      with_granted_mana)
from .filters import has_type, parse_filter
from .mana import GENERIC_ONLY, SNOW, Cost, parse_cost, pay

if TYPE_CHECKING:
    from .game import Game, Permanent, Seat

MAX_LIFE_MANA = 10  # Channel: how many life-paid {C} the payer offers at once


@dataclass(frozen=True)
class ManaSource:
    """One mana a permanent can make when tapped, and whether making it hurts (painlands, Talismans)."""
    permanent: "Permanent | None"  # None: mana already in the pool
    types: frozenset[str]  # one mana of one of these types
    pain: frozenset[str] = frozenset()  # types that deal `damage` to the controller when produced
    damage: int = 0
    life: bool = False  # the `damage` is life paid (Mana Confluence), not damage dealt
    restriction: str | None = None  # what the mana may be spent on (see effects.mana_restriction)
    counter: str | None = None  # the counter removed from the permanent when this mana is used (Vivid and depletion lands)
    counter_free: frozenset[str] = frozenset()  # ... unless it pays for one of these types (the Vivid land's own color)
    counter_each: bool = False  # one counter comes off for each of this permanent's mana that is used (the storage lands)


def _snowy(permanent: "Permanent", types: frozenset[str]) -> frozenset[str]:
    """A snow permanent's mana can also pay for {S}."""
    return types | {SNOW} if "Snow" in permanent.card.type_line else types


def _pain(source: ManaSource, symbol: frozenset[str] | None) -> int:
    """Damage for tapping `source` for mana paying `symbol` (None: generic, so any type will do)."""
    options = source.types if symbol is None else source.types & symbol
    return source.damage if source.pain and all(t in source.pain for t in options) else 0


class Payment(list["Permanent"]):
    """The permanents to tap for a cost; `pain` is the damage their mana deals to the payer, `life` the life it costs,
    `pool` the mana types it uses up from the payer's mana pool."""
    pain: int = 0
    life: int = 0
    pool: tuple[frozenset[str], ...] = ()
    filters: tuple["Permanent", ...] = ()  # the permanents whose Signet-style ability ("{1}, {T}: Add ...") was used
    counters: tuple[tuple["Permanent", str, int], ...] = ()  # the lands whose mana cost counters (Vivid, depletion, storage): which, how many
    phyrexian_life: int = 0  # how many Phyrexian mana symbols were paid with 2 life instead of mana (Compleated reads it)


class ManaPayer:
    """What pays for a cost: the mana each permanent can make now, the cheapest set of them that pays, and tapping them."""

    def __init__(self, game: Game):
        self.game = game
        self._spending_spell: Card | None = None  # the spell mana is being paid for right now (Cavern of Souls, convoke)
        self._spending_x = False  # ... or an ability whose cost has {X}
        self._spending_from_hand = False  # ... and whether that spell is being cast from its owner's hand

    @contextlib.contextmanager
    def _paying_for(self, seat: Seat, card: Card):
        """While mana is paid for casting `card`, which is still in the zone it is cast from."""
        self._spending_spell, self._spending_from_hand = card, any(c is card for c in seat.hand)
        try:
            yield
        finally:
            self._spending_spell, self._spending_from_hand = None, False

    @staticmethod
    def _restricted_mana_ok(source: Permanent, limited, spell: Card | None) -> bool:
        """Whether `source`'s restricted mana can pay for `spell`: one of the kind the ability names (filters.py), and of the type the
        permanent chose as it entered when the ability says "of the chosen type"."""
        if spell is None or not parse_filter(limited.spell).matches(spell):
            return False
        return not limited.chosen or source.chosen_type in spell.type_line.partition("\u2014")[2].split()

    def _restricted_units(self, seat: Seat, permanent: Permanent, limited) -> list[frozenset[str]]:
        """The mana a restricted ability makes for what is being paid for now, or nothing."""
        if not self._restricted_mana_ok(permanent, limited, self._spending_spell):
            return []
        if limited.condition is not None and not self.game.condition_holds(limited.condition, seat, permanent):
            return []
        return list(limited.mana)

    def _restriction_ok(self, restriction: str | None) -> bool:
        """Whether mana limited by `restriction` can pay for what is being paid for now."""
        if restriction is None:
            return True
        spell = self._spending_spell
        if restriction == "not_from_hand":  # Heartwood Crafter: only spells cast from hand are off limits
            return not self._spending_from_hand
        if restriction == "instant_or_sorcery":  # Galazeth Prismari
            return spell is not None and ("Instant" in spell.type_line or "Sorcery" in spell.type_line)
        if restriction == "x_cost":
            return self._spending_x or (spell is not None and "{X}" in spell.mana_cost)
        return spell is not None and (spell.cmc >= 5 or "{X}" in spell.mana_cost)

    def _mana_sources(self, seat: Seat, exclude: Permanent | None = None) -> list[ManaSource]:
        """One entry per mana each untapped permanent can make: nonland sources first, then lands, and sources that sacrifice
        themselves (Treasure) last. `pay` does not take them in that order; `_pay_mana` leaves the sacrificing ones for last."""
        abilities, lands, sacrifices = [], [], []
        pooled = [ManaSource(None, unit) for unit in seat.mana_pool]
        foods = sum(has_type(p.card, "food") for p in seat.battlefield)  # Gilded Goose: one Food per use
        grants = [g for p in seat.battlefield if not self.game.loses_abilities(p) for g in group_mana_grants(p.card)]
        for permanent in seat.battlefield:
            if permanent.tapped or permanent is exclude or self.game.loses_abilities(permanent):
                continue
            if not is_land(permanent.card) and self.game._ability_barred(permanent):
                continue  # Stony Silence, Grand Abolisher: its mana ability can't be activated either
            card = permanent.card
            if grants and not is_land(card) and (given := tuple(line for kind, line in grants if kind in card.type_line)):
                card = with_granted_mana(card, given)  # Goldspan Dragon, Galazeth Prismari
            pain, damage = mana_pain(card) or (frozenset(), 0)
            if (condition := mana_condition(card)) and not self.game.condition_holds(condition, seat, permanent):
                continue  # "Activate only if you control five or more lands."
            if (per := mana_per_count(card)) is not None:  # Gaea's Cradle: as much as you control
                if not per[0] and not (permanent.sick and "Creature" in card.type_line):
                    lands.extend(ManaSource(permanent, frozenset(per[1]))
                                 for _ in range(sum(has_type(p.card, per[2]) for p in seat.battlefield)))
                if not per[0] or mana_ability(card, seat.color_identity) is None:
                    continue  # (Cabal Coffers has only the ability that costs mana; Evendo's plain {T}: Add {G} is read below)
            if is_land(card):
                if life_cost := mana_life_cost(card):
                    plain = mana_ability(card, seat.color_identity)  # Spire of Industry, a Horizon land: {C} costs nothing
                    free = frozenset().union(*plain) if plain else frozenset()
                    paid = mana_life_types(card)
                    condition = mana_life_condition(card)
                    if seat.life > life_cost and not (condition and not self.game.condition_holds(condition, seat, permanent)):  # never down to 0
                        lands.append(ManaSource(permanent, paid | free, paid, life_cost, life=True))
                    elif free:
                        lands.append(ManaSource(permanent, free))
                    continue
                if (cm := counter_removal_mana(card)) is not None:  # Vivid Crag, Hickory Woodlot: the mana costs a counter
                    plain = mana_ability(card, seat.color_identity)
                    free = frozenset().union(*plain) if plain else frozenset()  # the Vivid land's own color costs nothing
                    if cm.each:  # a storage land: one mana for each counter it could lose
                        lands.extend(ManaSource(permanent, cm.mana[0], counter=cm.counter, counter_each=True)
                                     for _ in range(permanent.counters.get(cm.counter, 0)))
                    elif permanent.counters.get(cm.counter, 0):
                        lands.extend(ManaSource(permanent, mana | free, counter=cm.counter, counter_free=free) for mana in cm.mana)
                    elif free:
                        lands.append(ManaSource(permanent, free))
                    continue
                gifted = [mana for other in self.game.seats for a in other.battlefield if a.attached_to is permanent
                          for mana in granted_mana(a.card)]  # "Enchanted land has "{T}: Add {G}{G}."": the better of the two
                extra = [ManaSource(permanent, mana, pain, damage) for other in self.game.seats for a in other.battlefield
                         if a.attached_to is permanent for mana in additional_land_mana(a.card, a.chosen_color)]  # Wild Growth, Utopia Sprawl
                if seat.extra_mountain_mana_turn == self.game.turn and "Mountain" in card.type_line:  # Molten Tide
                    extra.append(ManaSource(permanent, frozenset("R"), pain, damage))
                if (bonus := mana_bonus(card)) is not None and all(any(p.card.name == name for p in seat.battlefield) for name in bonus[0]):
                    lands.extend([ManaSource(permanent, frozenset("C"), pain, damage) for _ in range(bonus[1])] + extra)
                    continue  # the Urza lands: more mana with the other two
                if (lines := mana_lines(card)) is not None:  # a Verge land: each color has its own line and condition
                    types = frozenset().union(*(t for t, condition in lines if condition is None or self.game.condition_holds(condition, seat, permanent)))
                    lands.extend(([ManaSource(permanent, types, pain, damage)] if types else []) + extra)
                    continue
                if units := land_mana_units(card):  # a bounceland or Ancient Tomb makes several mana in one tap
                    lands.extend([ManaSource(permanent, mana, pain, damage) for mana in units] + extra)
                    continue
                if len(gifted) > 1:  # more mana than the land's own single one
                    lands.extend([ManaSource(permanent, mana, pain, damage) for mana in gifted] + extra)
                    continue
                # Command Tower makes only the colors of your commander, whatever the card data lists.
                types = seat.color_identity if is_identity_mana_land(card) else frozenset(card.produced_mana)
                if (chosen := chosen_color_mana(card)) is not None:  # Room of Refuge, a Thriving land: the color chosen as it entered
                    types = frozenset(c for c in (chosen[0], permanent.chosen_color) if c)
                    if not types:
                        continue
                if filter_mana_ability(card) is not None:  # Hall of Oracles: the colors cost {1}; alone it makes {C}
                    plain = mana_ability(card, seat.color_identity)
                    types = frozenset().union(*plain) if plain else frozenset()
                    if not types:
                        continue
                if reflect := reflected_mana(card):
                    types = self._reflected_types(seat, *reflect)
                    if not types:
                        continue
                if (limited := restricted_mana(card)) is not None:  # Cavern of Souls, Eldrazi Temple: the restricted mana only for the right spells
                    plain = mana_ability(card, seat.color_identity) or []  # its other "{T}: Add" line, not the card data (which lists every color)
                    types = frozenset().union(*plain) if plain else frozenset()
                    if units := self._restricted_units(seat, permanent, limited):
                        if len(units) > 1:  # Eldrazi Temple: two mana in one tap, like a bounceland
                            lands.extend([ManaSource(permanent, _snowy(permanent, mana), pain, damage) for mana in units] + extra)
                            continue
                        types = types | units[0]
                if given := tuple(line for kind, line in grants if kind == "Land"):  # Chromatic Lantern
                    types = types | granted_land_mana(given, seat.color_identity)
                types = types | self.game._land_type_mana(permanent)  # Urborg: it is a Swamp too
                lands.extend(([ManaSource(permanent, _snowy(permanent, types), pain, damage)] if types else []) + extra)  # no mana: no source
            elif not (permanent.sick and "Creature" in card.type_line and not mana_ability_needs_no_tap(card)):
                bucket = sacrifices if mana_ability_sacrifices(card) else abilities
                extra = mana_extra_cost(card)
                if extra == "food" and foods <= 0 or extra == "mill" and not seat.library:
                    continue  # nothing to pay the mana ability's extra cost with
                if extra == "food":
                    foods -= 1
                if (charge := charge_mana(card)) is not None:  # Astral Cornucopia: a mana for each charge counter
                    if permanent.counters.get("charge", 0) and self._restriction_ok(charge[1]):
                        bucket.extend(ManaSource(permanent, charge[0], restriction=charge[1])
                                      for _ in range(permanent.counters["charge"]))
                if (kind := counter_mana(card)) is not None:  # Mana Bloom: a counter for one mana, once each turn
                    if permanent.counters.get(kind, 0) and permanent.activated_turn.get("counter mana") != self.game.turn:
                        bucket.append(ManaSource(permanent, frozenset("WUBRG")))
                    continue
                if reflect := reflected_mana(card):  # Fellwar Stone: what the opponents' lands could produce
                    types = self._reflected_types(seat, *reflect)
                    if types:
                        bucket.append(ManaSource(permanent, types))
                    continue
                units = ([frozenset("WUBRG")] * max(0, self.game.power(permanent)) if makes_mana_by_power(card)
                         else mana_ability(card, seat.color_identity) or [])  # (the power's worth need not be one color here)
                if mana_among_legendary(card):  # Mox Amber: the colors of its controller's legendary creatures and planeswalkers
                    colors = frozenset(c for p in seat.battlefield if "Legendary" in p.card.type_line
                                       and ("Creature" in p.card.type_line or "Planeswalker" in p.card.type_line) for c in p.card.colors)
                    units = [colors] if colors else []
                elif mana_of_imprinted(card):  # Chrome Mox: the colors of the card exiled with it
                    colors = frozenset(c for _, exiled in permanent.exiled_with for c in exiled.colors)
                    units = [colors] if colors else []
                if (limited := restricted_mana(card)) is not None and (limited_units := self._restricted_units(seat, permanent, limited)):
                    # Delighted Halfling: its colorless mana or the restricted color in one tap; Rivaz of the Claw: two of any colors
                    units = ([units[0] | limited_units[0]] + units[1:] if units else [limited_units[0]]) + limited_units[1:]
                restriction = mana_restriction(card)
                if not self._restriction_ok(restriction):
                    continue
                for mana in units:
                    bucket.append(ManaSource(permanent, _snowy(permanent, mana), pain, damage, restriction=restriction))
        return pooled + abilities + lands + sacrifices + self._convoke_sources(seat, exclude, pooled + abilities + lands + sacrifices)

    def _convoke_sources(self, seat: Seat, exclude: Permanent | None, taken: list[ManaSource]) -> list[ManaSource]:
        """While a spell with Convoke (or Improvise) is being paid for: each untapped creature (artifact) not already a mana
        source can be tapped for {1}, or for one mana of its color. Summoning-sick ones can, since it isn't a {T} cost; they go
        first, being the ones that couldn't attack anyway."""
        spell = self._spending_spell
        if spell is None:
            return []
        convoke, improvise = has_keyword(spell, "convoke"), has_keyword(spell, "improvise")
        busy = {id(s.permanent) for s in taken if s.permanent is not None}
        found = []
        for permanent in sorted(seat.battlefield, key=lambda p: not p.sick):
            if permanent.tapped or permanent is exclude or id(permanent) in busy:
                continue
            if convoke and "Creature" in permanent.card.type_line:
                found.append(ManaSource(permanent, frozenset(permanent.card.colors) or frozenset({GENERIC_ONLY})))
            elif improvise and "Artifact" in permanent.card.type_line:
                found.append(ManaSource(permanent, frozenset({GENERIC_ONLY})))
        return found

    def _reflected_types(self, seat: Seat, opponents: bool, colorless: bool) -> frozenset[str]:
        """What Exotic Orchard / Reflecting Pool can make: the mana types the lands of the opponents (or your other
        lands) could produce. Lands that copy this kind of ability add nothing, so there is no loop."""
        owners = [s for s in self.game.live_seats() if (s is not seat) == opponents] if opponents else [seat]
        types: set[str] = set()
        for owner in owners:
            for land in owner.battlefield:
                if is_land(land.card) and not reflected_mana(land.card):
                    types |= set(land.card.produced_mana)
        return frozenset(types if colorless else types - {"C"})

    def _pay_cost(self, seat: Seat, cost: Cost, exclude: Permanent | None = None) -> Payment | None:
        """The permanents to tap for `cost`, or None if it can't be paid. A Phyrexian symbol is paid with mana
        when that works, otherwise with 2 life (never down to 0 life)."""
        for by_life in range(len(cost.phyrexian) + 1):
            rest = dataclasses.replace(cost, phyrexian=cost.phyrexian[by_life:])
            payment = self._pay_mana(seat, rest, exclude)
            if payment is not None and not by_life:
                return payment
            if payment is not None and seat.life > payment.life + 2 * by_life:
                payment.life += 2 * by_life
                payment.phyrexian_life = by_life
                return payment
        return None

    def _pay_mana(self, seat: Seat, cost: Cost, exclude: Permanent | None = None) -> Payment | None:
        """The permanents to tap for a cost of mana only, or None if it can't be paid.

        Signet-style sources ("{1}, {T}: Add {W}{U}.") are tried only when plain
        sources aren't enough, fewest first; their own costs are paid from plain sources.
        """
        sources = self._mana_sources(seat, exclude)
        filters = self._filter_sources(seat, exclude)
        keepers = [s for s in sources if not self._sacrifices_itself(s)]
        for pool in ([keepers] if len(keepers) < len(sources) else []) + [sources]:  # a Treasure or Eldrazi Spawn is spent only if nothing else will pay
            for size in range(len(filters) + 1):
                for combo in combinations(filters, size):
                    chosen = self._pay_with_filters(cost, pool, combo)
                    if chosen is not None:
                        return chosen
        if seat.life_mana_turn == self.game.turn and seat.life > 1:  # Channel: only when nothing that costs nothing will do
            lives = [ManaSource(None, frozenset("C"), frozenset("C"), 1, life=True) for _ in range(min(seat.life - 1, MAX_LIFE_MANA))]
            for size in range(len(filters) + 1):
                for combo in combinations(filters, size):
                    chosen = self._pay_with_filters(cost, sources + lives, combo)
                    if chosen is not None and chosen.life < seat.life:  # never down to 0
                        return chosen
        return None

    @staticmethod
    def _sacrifices_itself(source: ManaSource) -> bool:
        """Whether making this mana sacrifices its permanent (Treasure, Eldrazi Spawn)."""
        permanent = source.permanent
        return permanent is not None and not is_land(permanent.card) and mana_ability_sacrifices(permanent.card)

    def _pay_with_filters(self, cost: Cost, sources: list[ManaSource], combo) -> Payment | None:
        """Pay `cost` using the filters in `combo`, in any order: each filter's own cost is paid from plain sources or
        the mana earlier filters made (so Signets can feed each other, but none feeds itself)."""
        for ordered in permutations(combo):
            if (payment := self._pay_in_order(cost, sources, ordered)) is not None:
                return payment
        return None

    def _pay_in_order(self, cost: Cost, sources: list[ManaSource], ordered) -> Payment | None:
        pool = list(sources)
        used: list[tuple[ManaSource, frozenset[str] | None]] = []
        for permanent, activation, units in ordered:
            # Its own cost is paid by other permanents: a filter can't tap for mana to pay for its own ability.
            available = [i for i, s in enumerate(pool) if s.permanent is not permanent]
            paid_here: dict[int, frozenset[str]] = {}
            chosen_here = pay(activation, [pool[i].types for i in available], paid_here)
            if chosen_here is None:
                return None
            chosen = [available[j] for j in chosen_here]
            paid = {available[j]: symbol for j, symbol in paid_here.items()}
            used += [(pool[i], paid.get(i)) for i in chosen]
            pool = [s for i, s in enumerate(pool) if i not in chosen] + [ManaSource(permanent, mana) for mana in units]
        paid = {}
        chosen = pay(cost, [s.types for s in pool], paid)
        if chosen is None:
            return None
        used += [(pool[i], paid.get(i)) for i in chosen]
        # A permanent that makes several mana (Sol Ring) is tapped once. Mana already in the pool has no permanent.
        permanents = [s.permanent for s, _ in used if s.permanent is not None] + [p for p, _, _ in ordered]
        payment = Payment({id(p): p for p in permanents}.values())
        payment.pool = tuple(s.types for s, _ in used if s.permanent is None and not s.life)  # a life-paid {C} (Channel) isn't pooled
        payment.filters = tuple(p for p, _, _ in ordered)
        # A permanent hurts (or costs life) once per tap, however many of its mana are used.
        hurt: dict[int, int] = {}
        paid_life: dict[int, int] = {}
        for source, symbol in used:
            into = paid_life if source.life else hurt
            key = id(source) if source.permanent is None else id(source.permanent)  # each life-paid {C} costs its own life
            into[key] = max(into.get(key, 0), _pain(source, symbol))
        payment.pain, payment.life = sum(hurt.values()), sum(paid_life.values())
        # A land whose mana costs a counter loses one per tap, unless it only made its own color (or generic mana).
        losing: dict[int, list] = {}
        for s, symbol in used:
            if s.counter and not (s.counter_free and (symbol is None or s.counter_free & symbol)):
                entry = losing.setdefault(id(s.permanent), [s.permanent, s.counter, 0])
                entry[2] = entry[2] + 1 if s.counter_each else 1
        payment.counters = tuple(tuple(entry) for entry in losing.values())
        return payment

    def _filter_sources(self, seat: Seat, exclude: Permanent | None) -> list[tuple[Permanent, Cost, list]]:
        found = []
        for permanent in seat.battlefield:
            if permanent.tapped or permanent is exclude or (permanent.sick and "Creature" in permanent.card.type_line) \
                    or self.game.loses_abilities(permanent):
                continue
            ability = filter_mana_ability(permanent.card)
            if ability:
                found.append((permanent, parse_cost(ability[0]), ability[1]))
            elif (per := mana_per_count(permanent.card)) is not None and per[0] \
                    and permanent.counters.get("charge", 0) >= mana_threshold(permanent.card):  # Cabal Coffers, Evendo
                units = [frozenset(per[1])] * sum(has_type(p.card, per[2]) for p in seat.battlefield)
                if units:
                    found.append((permanent, parse_cost(per[0]), units))
        return found

    def _spend_mana(self, seat: Seat, sources: list[Permanent]) -> None:
        """Tap the chosen mana sources; ones whose mana ability sacrifices them (Treasure) are sacrificed,
        and painlands and Talismans that made painful mana damage the payer."""
        for source in sources:
            if (kind := counter_mana(source.card)) is not None:  # no {T} in the cost: it isn't tapped
                self.game.remove_counters(source, kind, 1)
                source.activated_turn["counter mana"] = self.game.turn
                continue
            self.game.tap(source)
            if has_next_x_rider(source.card):  # Brass Infiniscope
                seat.x_rider_count = (seat.x_rider_count if seat.x_rider_turn == self.game.turn else 0) + 1
                seat.x_rider_turn = self.game.turn
            if not is_land(source.card) and mana_ability_sacrifices(source.card):
                self.game._leave_battlefield(source, "sacrificed")
            if (extra := mana_extra_cost(source.card)) == "mill":
                self.game.mill(seat, 1)
            elif extra == "food" and (food := next((p for p in seat.battlefield if has_type(p.card, "food")), None)):
                self.game._leave_battlefield(food, "sacrificed")
        for permanent, kind, amount in getattr(sources, "counters", ()):  # Vivid, depletion and storage lands
            self.game.remove_counters(permanent, kind, amount)
            removal = counter_removal_mana(permanent.card)
            if not permanent.counters.get(kind) and removal is not None and removal.sacrifice_at_zero:
                self.game._leave_battlefield(permanent, "sacrificed")
        if pain := getattr(sources, "pain", 0):
            self.game.damage(seat, pain)
        if life := getattr(sources, "life", 0):
            self.game.change_life(seat, -life)
        for unit in getattr(sources, "pool", ()):
            seat.mana_pool.remove(unit)
