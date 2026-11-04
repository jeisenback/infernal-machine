""""When this artifact enters or is put into a graveyard from the battlefield, draw a card." (Ichor Wellspring)."""

import unittest

from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, enter, real, run_stack, table3

WELLSPRING = real("Ichor Wellspring", "{2}", "Artifact", "When this artifact enters or is put into a graveyard from the battlefield, draw a "
                  "card.")


def table():
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.library = [], [OGRE] * 4
    return game, a


class IchorWellspringTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(WELLSPRING), [])

    def test_it_draws_when_it_enters_and_when_it_is_destroyed(self):
        game, a = table()
        wellspring = enter(game, a, WELLSPRING)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)
        game.destroy(wellspring)
        run_stack(game)
        self.assertEqual(len(a.hand), 2)

    def test_exiled_it_does_not_draw(self):
        game, a = table()
        wellspring = enter(game, a, WELLSPRING)
        run_stack(game)
        game.exile(wellspring)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)


if __name__ == "__main__":
    unittest.main()
