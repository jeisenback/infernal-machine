""""When this creature enters, if you control another creature named Faerie Miscreant, draw a card." (Faerie Miscreant)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, enter, real, run_stack, table3

MISCREANT = real("Faerie Miscreant", "{U}", "Creature — Faerie Rogue", "Flying\nWhen this creature enters, if you control another creature "
                 "named Faerie Miscreant, draw a card.", "1", "1")


def enters(*others):
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.library, a.battlefield = [], [OGRE] * 3, [Permanent(card) for card in others]
    enter(game, a, MISCREANT)
    run_stack(game)
    return a


class FaerieMiscreantTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(MISCREANT), [])

    def test_with_another_it_draws(self):
        self.assertEqual(len(enters(MISCREANT).hand), 1)

    def test_alone_it_does_not(self):
        self.assertEqual(enters(OGRE).hand, [])


if __name__ == "__main__":
    unittest.main()
