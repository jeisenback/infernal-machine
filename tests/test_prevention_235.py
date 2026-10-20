"""Damage prevention, batch 1 (#235): shields ("prevent the next N damage"), Fog, a creature that prevents damage to itself, to
its controller, and "damage can't be prevented"; played from the cards' own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BIG, pick, real, Table, table3


def card(name, text="", type_line="Creature — Bear", power=2, toughness=2):
    return Card(name=name, mana_cost="{1}", cmc=1, type_line=type_line, oracle_text=text, power=str(power), toughness=str(toughness))


BEAR = card("Bear")
GOLEM = card("Golem", "", "Artifact Creature — Golem", 3, 3)
FOG = real("Fog", "{G}", "Instant", "Prevent all combat damage that would be dealt this turn.")
BANDAGE = real("Bandage", "{W}", "Instant", "Prevent the next 1 damage that would be dealt to any target this turn.\nDraw a card.")
ANOINT = real("Anoint", "{2}{W}", "Instant", "Prevent the next 3 damage that would be dealt to target creature this turn.")
SHIELDED = real("Shielded Passage", "{W}", "Instant", "Prevent all damage that would be dealt to target creature this turn.")
SQUEES_TOY = card("Squee's Toy", "{T}: Prevent the next 1 damage that would be dealt to target creature this turn.", "Artifact")
BULWARK = card("Reinforced Bulwark", "{T}: Prevent the next 1 damage that would be dealt to you this turn.", "Artifact Creature — Wall")
EIDOLON = card("Aurora Eidolon", "Sacrifice this creature: Prevent the next 2 damage that would be dealt to any target this turn.")
SPORE_FROG = card("Spore Frog", "Sacrifice this creature: Prevent all combat damage that would be dealt this turn.")
LYNX = card("Glittering Lynx", "Prevent all damage that would be dealt to this creature.")
GOMAZOA = card("Guard Gomazoa", "Prevent all combat damage that would be dealt to this creature.")
ISTVAN = card("Uncle Istvan", "Prevent all damage that would be dealt to this creature by creatures.")
CHASM = card("Glacial Chasm", "Prevent all damage that would be dealt to you.", "Land")
SUNSPINE = card("Sunspine Lynx", "Damage can't be prevented.")
MALIGNUS = card("Malignus", "Damage that would be dealt by this creature can't be prevented.", "Creature — Elemental", 4, 4)
LIFELINKER = card("Priest", "Lifelink")


def setup(mine=(), theirs=()):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(c) for c in mine]
    b.battlefield = [Permanent(c) for c in theirs]
    return game, a, b


def hurt(game, victim, amount, source=None, combat=False):
    before = victim.damage if isinstance(victim, Permanent) else victim.life
    game.damage(victim, amount, source=source, combat=combat)
    return (victim.damage - before) if isinstance(victim, Permanent) else (before - victim.life)


class ShieldTests(unittest.TestCase):
    def test_it_absorbs_the_next_n_and_is_then_used_up(self):
        game, a, b = setup([BIG])
        big = a.battlefield[0]
        game.shield(big, 2)
        self.assertEqual(hurt(game, big, 3), 1)
        self.assertEqual(hurt(game, big, 2), 2)

    def test_a_small_hit_leaves_the_rest_of_the_shield(self):
        game, a, b = setup([BIG])
        big = a.battlefield[0]
        game.shield(big, 3)
        self.assertEqual((hurt(game, big, 1), hurt(game, big, 1), hurt(game, big, 3)), (0, 0, 2))

    def test_it_lasts_only_this_turn(self):
        game, a, b = setup([BIG])
        game.shield(a.battlefield[0], 5)
        game.turn += 1
        self.assertEqual(hurt(game, a.battlefield[0], 3), 3)

    def test_it_covers_only_what_it_was_made_for(self):
        game, a, b = setup([BIG, BEAR])
        game.shield(a.battlefield[0], 5)
        self.assertEqual(hurt(game, a.battlefield[1], 2), 2)

    def test_a_player_can_be_shielded(self):
        game, a, b = setup()
        game.shield(a, 3)
        self.assertEqual((hurt(game, a, 2), hurt(game, a, 4)), (0, 3))

    def test_shields_add_up(self):
        game, a, b = setup([BIG])
        big = a.battlefield[0]
        game.shield(big, 2)
        game.shield(big, 3)
        self.assertEqual(hurt(game, big, 6), 1)

    def test_from_a_spell_to_any_target(self):
        t = Table(BANDAGE, n=2, theirs=[Permanent(BIG)], policy=lambda prompt, options: next(
            (i for i, o in enumerate(options) if o.startswith("Big")), 0)).cast()
        big = t.b.battlefield[0]
        self.assertEqual((hurt(t.game, big, 2)), 1)

    def test_from_a_spell_to_a_target_creature(self):
        t = Table(ANOINT, n=3, mine=[Permanent(BIG)], policy=lambda prompt, options: next(
            (i for i, o in enumerate(options) if o.startswith("Big")), 0)).cast()
        self.assertEqual(hurt(t.game, one(t.a, "Big"), 5), 2)

    def test_all_damage_to_a_creature_this_turn(self):
        t = Table(SHIELDED, n=1, mine=[Permanent(BIG)], policy=lambda prompt, options: next(
            (i for i, o in enumerate(options) if o.startswith("Big")), 0)).cast()
        self.assertEqual(hurt(t.game, one(t.a, "Big"), 100), 0)

    def test_an_ability_that_shields_you(self):
        game, _ = table3(pick(ACTIVATE))
        a = game.seats[0]
        a.battlefield = [Permanent(BULWARK)]
        a.battlefield[0].sick = False
        game._priority_round(a)
        self.assertEqual(hurt(game, a, 3), 2)

    def test_a_creature_that_shields_itself(self):
        warden = card("Warden", "{T}: Prevent the next 2 damage that would be dealt to this creature this turn.")
        game, _ = table3(pick(ACTIVATE))
        a = game.seats[0]
        a.battlefield = [Permanent(warden), Permanent(BIG)]
        a.battlefield[0].sick = False
        game._priority_round(a)
        self.assertEqual((hurt(game, a.battlefield[0], 3), hurt(game, a.battlefield[1], 3)), (1, 3))

    def test_a_creature_that_shields_another_by_sacrificing(self):
        game, _ = table3(pick(ACTIVATE, "Big"))
        a = game.seats[0]
        a.battlefield = [Permanent(EIDOLON), Permanent(BIG)]
        game._priority_round(a)
        self.assertEqual([p.card.name for p in a.battlefield], ["Big"])  # the Eidolon was sacrificed
        self.assertEqual(hurt(game, a.battlefield[0], 3), 1)


def one(seat, name):
    return next(p for p in seat.battlefield if p.card.name == name)


class FogTests(unittest.TestCase):
    def test_combat_damage_is_prevented_this_turn(self):
        t = Table(FOG, n=1)
        t.cast()
        attacker = Permanent(BEAR)
        t.b.battlefield = [attacker]
        self.assertEqual((hurt(t.game, t.a, 3, source=attacker, combat=True), hurt(t.game, t.b, 3, source=attacker, combat=True)), (0, 0))

    def test_other_damage_is_not(self):
        t = Table(FOG, n=1)
        t.cast()
        self.assertEqual(hurt(t.game, t.a, 3), 3)
        self.assertEqual(hurt(t.game, t.a, 2, source=Permanent(BEAR)), 2)

    def test_it_ends_with_the_turn(self):
        t = Table(FOG, n=1)
        t.cast()
        t.game.turn += 1
        self.assertEqual(hurt(t.game, t.a, 3, source=Permanent(BEAR), combat=True), 3)

    def test_a_sacrifice_fog(self):
        game, _ = table3(pick(ACTIVATE))
        a = game.seats[0]
        a.battlefield = [Permanent(SPORE_FROG)]
        game._priority_round(a)
        self.assertEqual(hurt(game, a, 2, source=Permanent(BEAR), combat=True), 0)


class StaticTests(unittest.TestCase):
    def test_all_damage_to_this_creature(self):
        game, a, b = setup([LYNX, BEAR])
        self.assertEqual((hurt(game, one(a, "Glittering Lynx"), 50), hurt(game, one(a, "Bear"), 2)), (0, 2))

    def test_only_combat_damage_to_this_creature(self):
        game, a, b = setup([GOMAZOA])
        gomazoa = a.battlefield[0]
        self.assertEqual((hurt(game, gomazoa, 5, combat=True), hurt(game, gomazoa, 1)), (0, 1))

    def test_only_damage_from_creatures(self):
        game, a, b = setup([ISTVAN])
        istvan = a.battlefield[0]
        self.assertEqual((hurt(game, istvan, 5, source=Permanent(BEAR)), hurt(game, istvan, 3)), (0, 3))

    def test_a_noncreature_source_that_is_an_artifact_creature_still_counts_as_a_creature(self):
        game, a, b = setup([ISTVAN])
        self.assertEqual(hurt(game, a.battlefield[0], 5, source=Permanent(GOLEM)), 0)

    def test_a_source_that_is_not_a_creature_is_not_stopped(self):
        game, a, b = setup([ISTVAN])
        relic = Permanent(card("Relic", "", "Artifact"))
        self.assertEqual(hurt(game, a.battlefield[0], 3, source=relic), 3)

    def test_it_stops_when_the_permanent_leaves(self):
        game, a, b = setup([CHASM])
        self.assertEqual(hurt(game, a, 3), 0)
        a.battlefield.clear()
        self.assertEqual(hurt(game, a, 3), 3)

    def test_all_damage_to_you(self):
        game, a, b = setup([CHASM])
        self.assertEqual((hurt(game, a, 7), hurt(game, b, 7)), (0, 7))


class CantBePreventedTests(unittest.TestCase):
    def test_it_beats_a_shield_a_fog_and_a_static(self):
        game, a, b = setup([LYNX], [SUNSPINE])
        lynx = a.battlefield[0]
        game.shield(a, 10)
        game.shield(lynx, 10)
        game.fog_turn = game.turn
        self.assertEqual((hurt(game, a, 3), hurt(game, lynx, 3), hurt(game, a, 2, source=Permanent(BEAR), combat=True)), (3, 3, 2))

    def test_a_creature_whose_own_damage_cant_be_prevented(self):
        game, a, b = setup([MALIGNUS], [BEAR])
        malignus = a.battlefield[0]
        game.shield(b, 10)
        self.assertEqual(hurt(game, b, 4, source=malignus), 4)
        self.assertEqual(hurt(game, b, 4, source=b.battlefield[0]), 0)  # anyone else's damage is still prevented


class WhatPreventionStopsTests(unittest.TestCase):
    def test_prevented_combat_damage_sets_off_no_combat_damage_trigger(self):
        thief = card("Thief", "Whenever this creature deals combat damage to a player, you gain 3 life.")
        game, a, b = setup([thief])
        game.shield(b, 5)
        life = a.life
        game.damage(b, 2, source=a.battlefield[0], combat=True)
        game._put_triggers_on_stack()
        while game.stack:
            game._resolve(game.stack.pop())
        self.assertEqual(a.life, life)
        game.damage(b, 9, source=a.battlefield[0], combat=True)  # what is left of the 5 is 3, so 6 is dealt
        game._put_triggers_on_stack()
        while game.stack:
            game._resolve(game.stack.pop())
        self.assertEqual(a.life, life + 3)

    def test_prevented_damage_gives_no_lifelink(self):
        game, a, b = setup([LIFELINKER], [BIG])
        game.shield(b, 5)
        life = a.life
        game.damage(b, 3, source=a.battlefield[0])
        self.assertEqual(a.life, life)

    def test_partly_prevented_damage_gives_the_rest(self):
        game, a, b = setup([LIFELINKER])
        game.shield(b, 2)
        life = a.life
        game.damage(b, 5, source=a.battlefield[0])
        self.assertEqual(a.life, life + 3)

    def test_prevented_infect_damage_gives_no_poison(self):
        infect = card("Plague Myr", "Infect", power=3, toughness=3)
        game, a, b = setup([infect])
        game.shield(b, 5)
        game.damage(b, 3, source=a.battlefield[0])
        self.assertEqual(b.player_counters.get("poison", 0), 0)


class ReportTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for c in (FOG, BANDAGE, ANOINT, SHIELDED, SQUEES_TOY, BULWARK, EIDOLON, SPORE_FROG, LYNX, GOMAZOA, ISTVAN, CHASM,
                  SUNSPINE, MALIGNUS):
            with self.subTest(c.name):
                self.assertEqual(unsupported_lines(c), [])


if __name__ == "__main__":
    unittest.main()
