"""Draw doubling (CR 614.1): "If you would draw a card, draw two cards instead." (Thought Reflection) and "... except the first one you draw
in each of your draw steps ..." (Alhammarret's Archive, Teferi's Ageless Insight)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import ARCHIVE, real, table3

REFLECTION = real("Thought Reflection", "{4}{U}{U}{U}", "Enchantment", "If you would draw a card, draw two cards instead.")
INSIGHT = real("Teferi's Ageless Insight", "{2}{U}{U}", "Legendary Enchantment", "If you would draw a card except the first one you draw in "
               "each of your draw steps, draw two cards instead.")


def setup(*cards):
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield = [Permanent(c) for c in cards]
    a.library = [Card(name=f"Card {i}", type_line="Land") for i in range(10)]
    b.library = [Card(name=f"Other {i}", type_line="Land") for i in range(10)]
    return game, a, b


class DrawDoublingTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (REFLECTION, INSIGHT, ARCHIVE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_every_draw_is_two(self):
        game, a, b = setup(REFLECTION)
        game.draw(a, 1)
        game.draw(a, 3)
        self.assertEqual((len(a.hand), len(a.library)), (8, 2))

    def test_only_its_controller(self):
        game, a, b = setup(REFLECTION)
        game.draw(b, 2)
        self.assertEqual(len(b.hand), 2)

    def test_two_of_them_make_four(self):
        game, a, b = setup(REFLECTION, REFLECTION)
        game.draw(a, 1)
        self.assertEqual(len(a.hand), 4)

    def test_not_the_first_card_of_the_draw_step(self):
        for card in (INSIGHT, ARCHIVE):
            game, a, b = setup(card)
            game._draw_step_draw = True
            game.draw(a, 1)
            self.assertEqual(len(a.hand), 1, card.name)
            game._draw_step_draw = False
            game.draw(a, 1)
            self.assertEqual(len(a.hand), 3, card.name)

    def test_an_empty_library_ends_the_drawing(self):
        game, a, b = setup(REFLECTION)
        a.library = a.library[:1]
        game.draw(a, 1)
        self.assertEqual((len(a.hand), a.drew_from_empty), (1, True))


if __name__ == "__main__":
    unittest.main()
