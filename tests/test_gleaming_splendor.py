"""Gleaming Splendor, from its real Oracle text: "{2}{W}: Two target players each draw a card." Two different players (CR 115.3): the
player chosen first is not offered as the second target, and each of the two draws one."""

import unittest

from infernal_machine.game import Permanent, TARGET_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, activate, lands, real, table3

SPLENDOR = real("Gleaming Splendor", "{1}{W}", "Enchantment", "Whenever an opponent draws their second card each turn, you create a Treasure "
                "token.\n{2}{W}: Two target players each draw a card.", colors=("W",))


class GleamingSplendorTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(SPLENDOR), [])

    def test_two_different_players_each_draw_a_card(self):
        asked = []
        def policy(prompt, options):
            if TARGET_PROMPT.matches(prompt):
                asked.append(list(options))
            return 0
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(SPLENDOR), *lands(3)]
        for seat in game.seats:
            seat.library = [FOREST] * 3
        activate(game, a, "Gleaming Splendor")
        first = asked[0][0]
        self.assertEqual((len(asked), first in asked[1], [len(s.hand) for s in game.seats]), (2, False, [1, 1, 0]))


if __name__ == "__main__":
    unittest.main()
