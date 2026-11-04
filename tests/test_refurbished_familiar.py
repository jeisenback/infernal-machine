""""When this creature enters, each opponent discards a card. For each opponent who can't, you draw a card." (Refurbished Familiar)."""

import unittest

from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, OGRE, enter, real, run_stack, table3

FAMILIAR = real("Refurbished Familiar", "{3}{B}", "Artifact Creature — Zombie Rat", "Affinity for artifacts (This spell costs {1} less to cast "
                "for each artifact you control.)\nFlying\nWhen this creature enters, each opponent discards a card. For each opponent who "
                "can't, you draw a card.", "2", "1")


class RefurbishedFamiliarTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(FAMILIAR), [])

    def test_each_opponent_discards_and_an_empty_hand_draws_you_a_card(self):
        game, _ = table3()
        a, b, c = game.seats
        a.hand, a.library = [], [OGRE] * 3
        b.hand, c.hand = [FOREST], []
        enter(game, a, FAMILIAR)
        run_stack(game)
        self.assertEqual((b.hand, b.graveyard[-1:]), ([], [FOREST]))
        self.assertEqual(len(a.hand), 1)  # C could not discard

    def test_no_draw_when_everyone_discards(self):
        game, _ = table3()
        a, b, c = game.seats
        a.hand, a.library = [], [OGRE] * 3
        b.hand, c.hand = [FOREST], [OGRE]
        enter(game, a, FAMILIAR)
        run_stack(game)
        self.assertEqual(a.hand, [])


if __name__ == "__main__":
    unittest.main()
