"""Delirium (four or more card types among cards in your graveyard): Dragon's Rage Channeler's static ability and Violent Urge's rider."""

import unittest

from infernal_machine.effects import MUST_ATTACK
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BOLT, DIVINATION, FOREST, lands, pick, real, run_stack, table3

CHANNELER = real("Dragon's Rage Channeler", "{R}", "Creature — Human Shaman", "Whenever you cast a noncreature spell, surveil 1. (Look at the "
                 "top card of your library. You may put that card into your graveyard.)\nDelirium — As long as there are four or more card "
                 "types among cards in your graveyard, this creature gets +2/+2, has flying, and attacks each combat if able.", "1", "1",
                 colors=("R",))
URGE = real("Violent Urge", "{R}", "Instant", "Target creature gets +1/+0 and gains first strike until end of turn.\nDelirium — If there are "
            "four or more card types among cards in your graveyard, that creature gains double strike until end of turn.", colors=("R",))
FOUR_TYPES = [FOREST, BEAR, BOLT, DIVINATION]  # land, creature, instant, sorcery
THREE_TYPES = [FOREST, BEAR, BOLT]


class DragonsRageChannelerTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3()
        self.a = self.game.seats[0]
        self.channeler = Permanent(CHANNELER)
        self.a.battlefield = [self.channeler]

    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(CHANNELER), [])

    def test_with_delirium_it_is_a_3_3_flier_that_must_attack(self):
        self.a.graveyard = list(FOUR_TYPES)
        self.assertEqual(self.game.power(self.channeler), 3)
        self.assertTrue(self.game.has_keyword(self.channeler, "flying"))
        self.assertTrue(self.game.has_keyword(self.channeler, MUST_ATTACK))

    def test_without_it_a_plain_1_1(self):
        self.a.graveyard = list(THREE_TYPES)
        self.assertEqual(self.game.power(self.channeler), 1)
        self.assertFalse(self.game.has_keyword(self.channeler, MUST_ATTACK))


class ViolentUrgeTests(unittest.TestCase):
    def cast(self, graveyard):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.hand, a.battlefield, a.graveyard = [URGE], [bear] + lands(1), list(graveyard)
        game.active, game.step = 0, "main1"
        game._perform(a, CAST + URGE.name)
        run_stack(game)
        return game, bear

    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(URGE), [])

    def test_with_delirium_the_creature_gains_double_strike(self):
        game, bear = self.cast(FOUR_TYPES)
        self.assertEqual(game.power(bear), 3)
        self.assertTrue(game.has_keyword(bear, "double strike"))

    def test_without_it_only_first_strike(self):
        game, bear = self.cast(THREE_TYPES)
        self.assertTrue(game.has_keyword(bear, "first strike"))
        self.assertFalse(game.has_keyword(bear, "double strike"))


if __name__ == "__main__":
    unittest.main()
