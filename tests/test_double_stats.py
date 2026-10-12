"""Doubling power and toughness until end of turn: Unleash Fury, Bulk Up, Double Trouble, Reckless Amplimancer, Unnatural Growth (which
triggers at the beginning of each combat, whoever's turn it is)."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.characteristics import Modifier
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, lands, pick, real, run_stack, table3

FURY = real("Unleash Fury", "{1}{R}", "Instant", "Double the power of target creature until end of turn.")
TROUBLE = real("Double Trouble", "{4}{R}", "Instant", "Double the power of each creature you control until end of turn.")
EPIC = real("Epic Fight", "{2}{G}", "Sorcery", "Choose one or both —\n• Double target creature's power and toughness until end of turn.\n"
            "• Target creature you control fights target creature an opponent controls.")
AMPLIMANCER = real("Reckless Amplimancer", "{1}{G}", "Creature — Elf Druid", "{4}{G}: Double this creature's power and toughness until end of turn.",
                   "2", "2")
GROWTH = real("Unnatural Growth", "{1}{G}{G}{G}{G}", "Enchantment", "At the beginning of each combat, double the power and toughness of each "
              "creature you control until end of turn.")
MOUSE = real("Mouse", "{1}", "Creature — Mouse", "", "1", "3")


def stats(game, permanent):
    return game.power(permanent), game.toughness(permanent)


class DoubleStatsTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (FURY, TROUBLE, EPIC, AMPLIMANCER, GROWTH):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_target_creature_power_only(self):
        ogre = Permanent(OGRE)
        t = Table(FURY, mine=[ogre], n=2, policy=pick("Ogre"))
        t.cast()
        self.assertEqual(stats(t.game, ogre), (6, 3))

    def test_it_doubles_the_current_power_after_other_pumps(self):
        ogre = Permanent(OGRE)
        t = Table(FURY, mine=[ogre], n=2, policy=pick("Ogre"))
        t.game.modify_until_end_of_turn(ogre, Modifier(2, 0))
        t.cast()
        self.assertEqual(stats(t.game, ogre), (10, 3))

    def test_each_creature_you_control_but_not_theirs(self):
        ogre, bear, theirs = Permanent(OGRE), Permanent(BEAR), Permanent(OGRE)
        t = Table(TROUBLE, mine=[ogre, bear], theirs=[theirs], n=5).cast()
        self.assertEqual((stats(t.game, ogre), stats(t.game, bear), stats(t.game, theirs)), ((6, 3), (4, 2), (3, 3)))

    def test_power_and_toughness_of_the_creature_itself(self):
        game, _ = table3()
        a = game.seats[0]
        amp = Permanent(AMPLIMANCER)
        a.battlefield = [amp] + lands(5)
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE)))
        run_stack(game)
        self.assertEqual(stats(game, amp), (4, 4))

    def test_unnatural_growth_triggers_on_every_combat(self):
        game, _ = table3()
        a, b, _ = game.seats
        mouse, theirs = Permanent(MOUSE), Permanent(OGRE)
        a.battlefield = [Permanent(GROWTH), mouse]
        b.battlefield = [theirs]
        game.active, game.step = 1, "beginning_of_combat"  # an opponent's combat
        game._turn_based_actions(b)
        run_stack(game)
        self.assertEqual((stats(game, mouse), stats(game, theirs)), ((2, 6), (3, 3)))
        game.active, game.step = 0, "beginning_of_combat"  # and then its controller's own
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(stats(game, mouse), (4, 12))


if __name__ == "__main__":
    unittest.main()
