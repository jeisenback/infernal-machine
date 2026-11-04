""""This spell costs {2} less to cast for each card you've cycled or discarded this turn." (Hollow One)."""

import unittest

from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, lands, real, table3

HOLLOW = real("Hollow One", "{5}", "Artifact Creature — Golem", "This spell costs {2} less to cast for each card you've cycled or discarded "
              "this turn.\nCycling {2} ({2}, Discard this card: Draw a card.)", "4", "4")


def table():
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.library = [BEAR, OGRE, OGRE], [OGRE] * 3
    return game, a


class HollowOneTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(HOLLOW), [])

    def test_two_less_for_each_discard_this_turn(self):
        game, a = table()
        self.assertEqual(game.cost_reduction(a, HOLLOW), 0)
        game.discard(a, 2)
        self.assertEqual(game.cost_reduction(a, HOLLOW), 4)

    def test_cycling_counts(self):
        game, a = table()
        a.hand.append(HOLLOW)
        a.battlefield = lands(2)
        a.hand.remove(HOLLOW)  # as the cycle action takes it from the hand
        game._cycle(a, HOLLOW)
        self.assertEqual(game.cost_reduction(a, HOLLOW), 2)

    def test_last_turns_discards_do_not(self):
        game, a = table()
        game.discard(a, 1)
        game.turn += 1
        self.assertEqual(game.cost_reduction(a, HOLLOW), 0)
        game.discard(a, 1)  # the count starts again
        self.assertEqual(game.cost_reduction(a, HOLLOW), 2)


if __name__ == "__main__":
    unittest.main()
