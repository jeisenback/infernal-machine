"""Creatures can't attack you or planeswalkers you control unless their controller pays {N} for each of those creatures: Baird, Archon of
Absolution, Norn's Annex ({W/P}) and Sphere of Safety ({X}, the number of enchantments its controller has)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, PLAINS, creature, lands, real, table

BAIRD = real("Baird, Steward of Argive", "{2}{W}{W}", "Legendary Creature — Human Soldier", "Vigilance\nCreatures can't attack you or "
             "planeswalkers you control unless their controller pays {1} for each of those creatures.", "2", "4")
ARCHON = real("Archon of Absolution", "{3}{W}", "Creature — Angel Archon", "Flying, protection from white\nCreatures can't attack you or "
              "planeswalkers you control unless their controller pays {1} for each of those creatures.", "3", "2")
ANNEX = real("Norn's Annex", "{3}{W/P}", "Artifact", "({W/P} can be paid with either {W} or 2 life.)\nCreatures can't attack you or "
             "planeswalkers you control unless their controller pays {W/P} for each of those creatures.")
SPHERE = real("Sphere of Safety", "{4}{W}", "Enchantment", "Creatures can't attack you or planeswalkers you control unless their controller "
              "pays {X} for each of those creatures, where X is the number of enchantments you control.")
AURA = real("Pacifism", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature can't attack or block.")
BEAR = creature("Grizzly Bears", 2, 2)
ATTACK_ALL = lambda prompt, options: 1 if prompt.startswith("Attack") and len(options) > 1 else 0


def declare(taxer, creatures, mana, extra=()):
    game, _, _ = table(ATTACK_ALL)
    a, b = game.seats
    a.battlefield = [Permanent(c, sick=False) for c in creatures] + mana
    b.battlefield = [Permanent(taxer), *[Permanent(c) for c in extra]]
    game.combat.declare_attackers(a)
    return game, a, len(game.combat.attacks)


def tapped(seat):
    return sum(p.tapped for p in seat.battlefield if "Land" in p.card.type_line)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (BAIRD, ARCHON, ANNEX, SPHERE):
            self.assertEqual(unsupported_lines(card), [], card.name)


    def test_an_x_it_cannot_work_out_is_not_understood(self):
        card = real("Odd Sphere", "{4}{W}", "Enchantment", "Creatures can't attack you or planeswalkers you control unless their controller "
                    "pays {X} for each of those creatures, where X is the weather.")
        self.assertEqual(len(unsupported_lines(card)), 1)

    def test_an_x_with_no_explanation_is_not_understood(self):
        card = real("Odd Sphere", "{4}{W}", "Enchantment", "Creatures can't attack you or planeswalkers you control unless their controller "
                    "pays {X} for each of those creatures.")
        self.assertEqual(len(unsupported_lines(card)), 1)


class FixedAmountTests(unittest.TestCase):
    def test_one_for_each_attacker(self):
        for card in (BAIRD, ARCHON):
            game, a, attackers = declare(card, [BEAR, BEAR], lands(2, FOREST))
            self.assertEqual((attackers, tapped(a)), (2, 2), card.name)

    def test_only_as_many_attackers_as_the_mana_pays_for(self):
        game, a, attackers = declare(BAIRD, [BEAR, BEAR, BEAR], lands(2, FOREST))
        self.assertEqual((attackers, tapped(a)), (2, 2))


class PhyrexianTests(unittest.TestCase):
    def test_it_is_paid_with_white_mana_when_there_is_some(self):
        game, a, attackers = declare(ANNEX, [BEAR, BEAR], lands(2, PLAINS))
        self.assertEqual((attackers, tapped(a), a.life), (2, 2, 40))

    def test_it_is_paid_with_two_life_when_there_is_not(self):
        game, a, attackers = declare(ANNEX, [BEAR, BEAR], [])
        self.assertEqual((attackers, a.life), (2, 36))


class CountedAmountTests(unittest.TestCase):
    def test_x_is_the_number_of_enchantments_its_controller_has(self):
        game, a, attackers = declare(SPHERE, [BEAR, BEAR], lands(3, FOREST), extra=[AURA, AURA])  # Sphere and two more: X = 3
        self.assertEqual((attackers, tapped(a)), (1, 3))

    def test_alone_it_is_one_for_each(self):
        game, a, attackers = declare(SPHERE, [BEAR, BEAR], lands(2, FOREST))
        self.assertEqual((attackers, tapped(a)), (2, 2))

    def test_the_attacker_cannot_afford_it(self):
        game, a, attackers = declare(SPHERE, [BEAR], lands(2, FOREST), extra=[AURA, AURA])
        self.assertEqual((attackers, tapped(a)), (0, 0))


if __name__ == "__main__":
    unittest.main()
