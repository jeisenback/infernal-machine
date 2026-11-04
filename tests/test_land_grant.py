""""If you have no land cards in hand, you may reveal your hand rather than pay this spell's mana cost." (Land Grant)."""

import unittest

from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, OGRE, pick, real, run_stack, table3

GRANT = real("Land Grant", "{1}{G}", "Sorcery", "If you have no land cards in hand, you may reveal your hand rather than pay this spell's mana "
             "cost.\nSearch your library for a Forest card, reveal that card, put it into your hand, then shuffle.")


def table(hand):
    game, _ = table3(pick("Reveal your hand", "Forest"))
    a = game.seats[0]
    a.hand, a.battlefield, a.library = [GRANT] + list(hand), [], [OGRE, FOREST, OGRE]
    return game, a


class LandGrantTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(GRANT), [])

    def test_free_with_no_land_in_hand(self):
        game, a = table([OGRE])
        game._perform(a, CAST + GRANT.name)
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.hand), ["Forest", "Ogre"])

    def test_a_land_in_hand_means_paying_the_cost(self):
        game, a = table([FOREST])
        self.assertNotIn(CAST + GRANT.name, game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
