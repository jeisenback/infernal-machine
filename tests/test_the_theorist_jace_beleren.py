"""The Theorist, Jace Beleren: "At the beginning of each opponent's draw step, you draw a card." and "−2: For each opponent, return up to
one target artifact or creature that player controls to its owner's hand." """

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, begin, lands, pick, real, run_stack, table3

JACE = real("The Theorist, Jace Beleren", "{2}{U}{U}", "Legendary Planeswalker — Jace", "At the beginning of each opponent's draw step, "
            "you draw a card.\n+1: Create a 1/1 blue Illusion creature token.\n−2: For each opponent, return up to one target artifact or "
            "creature that player controls to its owner's hand.\n−6: Draw three cards. Then put X +1/+1 counters on each creature you "
            "control, where X is the number of cards in your hand.")
CRYSTAL_BALL = real("Crystal Ball", "{3}", "Artifact", "{1}, {T}: Scry 2. (Look at the top two cards of your library, then put any number "
                    "of them on the bottom and the rest on top in any order.)")


def table(policy=None):
    game, _ = table3(policy) if policy else table3()
    a, b, c = game.seats
    a.battlefield = [Permanent(JACE, loyalty=3)] + lands(4)
    for seat in game.seats:
        seat.hand, seat.library = [], [FOREST] * 5
    return game, a, b, c


class TheTheoristJaceBelerenTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(JACE), [])

    def test_you_draw_at_the_beginning_of_each_opponents_draw_step(self):
        game, a, b, _ = table()
        game.active = 1
        begin(game, "draw", b)
        self.assertEqual((len(a.hand), len(b.hand)), (1, 1))

    def test_not_on_your_own_draw_step(self):
        game, a, _, _ = table()
        begin(game, "draw", a)
        self.assertEqual(len(a.hand), 1)  # the draw step's own draw only

    def test_minus_two_returns_one_artifact_or_creature_of_each_opponent(self):
        game, a, b, c = table(pick("City of Brass", "Bear", "Crystal Ball"))  # a land would be taken if offered
        mine, theirs, ball = Permanent(BEAR), Permanent(BEAR), Permanent(CRYSTAL_BALL)
        a.battlefield.append(mine)
        b.battlefield, c.battlefield = [theirs] + lands(1), [ball]
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "The Theorist") and "−2:" in x))
        run_stack(game)
        self.assertEqual((b.hand, c.hand), ([BEAR], [CRYSTAL_BALL]))
        self.assertIn(mine, a.battlefield)  # yours is not a target
        self.assertEqual(len(b.battlefield), 1)  # a land is not a target


if __name__ == "__main__":
    unittest.main()
