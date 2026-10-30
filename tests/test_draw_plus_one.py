"""Quantum Riddler: "As long as you have one or fewer cards in hand, if you would draw one or more cards, you draw that many cards plus
one instead." """

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, lands, real, run_stack, table3

RIDDLER = real("Quantum Riddler", "{3}{U}{U}", "Creature — Sphinx", "Flying\nWhen this creature enters, draw a card.\nAs long as you "
               "have one or fewer cards in hand, if you would draw one or more cards, you draw that many cards plus one instead.\nWarp {1}{U}",
               "4", "6")


def table(hand, riddlers=1):
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.library = list(hand), [OGRE] * 10
    a.battlefield = [Permanent(RIDDLER) for _ in range(riddlers)]
    return game, a


class QuantumRiddlerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(RIDDLER), [])

    def test_with_one_card_in_hand_a_draw_of_two_is_three(self):
        game, a = table([BEAR])
        game.draw(a, 2)
        self.assertEqual(len(a.hand), 1 + 3)

    def test_with_two_cards_in_hand_it_does_not_apply(self):
        game, a = table([BEAR, BEAR])
        game.draw(a, 2)
        self.assertEqual(len(a.hand), 2 + 2)

    def test_two_riddlers_add_one_each(self):
        game, a = table([], riddlers=2)
        game.draw(a, 1)
        self.assertEqual(len(a.hand), 3)

    def test_without_a_riddler_nothing_changes(self):
        game, a = table([], riddlers=0)
        game.draw(a, 1)
        self.assertEqual(len(a.hand), 1)

    def test_its_own_enters_draw_is_two_from_an_empty_hand(self):
        game, a = table([RIDDLER], riddlers=0)
        a.battlefield = lands(5)
        game._perform(a, CAST + RIDDLER.name)
        run_stack(game)
        self.assertEqual(len(a.hand), 2)


if __name__ == "__main__":
    unittest.main()
