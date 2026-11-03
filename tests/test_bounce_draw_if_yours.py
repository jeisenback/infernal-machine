"""Boomerang Basics: "Return target nonland permanent to its owner's hand. If you controlled that permanent, draw a card." """

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, RELIC, lands, pick, real, run_stack, table3

BASICS = real("Boomerang Basics", "{U}", "Sorcery — Lesson", "Return target nonland permanent to its owner's hand. If you controlled that "
              "permanent, draw a card.")


def bounce(mine):
    game, _ = table3(pick("Relic"))
    a, b = game.seats[0], game.seats[1]
    a.hand, a.library = [BASICS], [OGRE, OGRE]
    a.battlefield = lands(1) + ([Permanent(RELIC)] if mine else [])
    b.hand, b.battlefield = [], [] if mine else [Permanent(RELIC)]
    game._perform(a, CAST + BASICS.name)
    run_stack(game)
    return a, b


class BoomerangBasicsTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(BASICS), [])

    def test_returning_your_own_permanent_draws(self):
        a, _ = bounce(mine=True)
        self.assertEqual(sorted(c.name for c in a.hand), ["Ogre", "Relic"])

    def test_returning_an_opponents_permanent_does_not(self):
        a, b = bounce(mine=False)
        self.assertEqual((a.hand, b.hand), ([], [RELIC]))


if __name__ == "__main__":
    unittest.main()
