""""Put target card from a graveyard on top of its owner's library." (Noxious Revival)."""

import unittest

from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, lands, pick, real, run_stack, table3

REVIVAL = real("Noxious Revival", "{G/P}", "Instant", "({G/P} can be paid with either {G} or 2 life.)\nPut target card from a graveyard on top "
               "of its owner's library.")


def cast(answer):
    game, _ = table3(pick(answer))
    a, b = game.seats[0], game.seats[1]
    a.hand, a.battlefield, a.graveyard, a.library = [REVIVAL], lands(1), [BEAR], [FOREST]
    b.graveyard, b.library = [OGRE], [FOREST]
    game._perform(a, CAST + REVIVAL.name)
    run_stack(game)
    return a, b


class NoxiousRevivalTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(REVIVAL), [])

    def test_an_opponents_card_goes_on_top_of_their_library(self):
        a, b = cast("Ogre (seat 1")
        self.assertEqual((b.graveyard, b.library), ([], [OGRE, FOREST]))
        self.assertEqual(a.library, [FOREST])

    def test_or_your_own(self):
        a, b = cast("Bear (seat 0")
        self.assertEqual(a.library, [BEAR, FOREST])
        self.assertEqual(b.graveyard, [OGRE])


if __name__ == "__main__":
    unittest.main()
