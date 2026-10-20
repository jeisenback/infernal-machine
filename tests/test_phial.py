"""Phial of Galadriel: "If you would draw a card while you have no cards in hand, draw two cards instead." and "If you would gain life while
you have 5 or less life, you gain twice that much life instead." Each condition is looked at before the draw or the life gain."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import ARCHIVE, real, table3

PHIAL = real("Phial of Galadriel", "{3}", "Legendary Artifact", "If you would draw a card while you have no cards in hand, draw two cards "
             "instead.\nIf you would gain life while you have 5 or less life, you gain twice that much life instead.\n{T}: Add one mana of any "
             "color.")


def setup(*cards):
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield = [Permanent(c) for c in cards]
    a.library = [Card(name=f"Card {i}", type_line="Land") for i in range(10)]
    b.library = [Card(name=f"Other {i}", type_line="Land") for i in range(10)]
    return game, a, b


class PhialTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(PHIAL), [])

    def test_a_draw_with_no_cards_in_hand_is_two(self):
        game, a, b = setup(PHIAL)
        game.draw(a, 1)
        self.assertEqual(len(a.hand), 2)

    def test_not_with_a_card_in_hand(self):
        game, a, b = setup(PHIAL)
        a.hand = [Card(name="Spare", type_line="Land")]
        game.draw(a, 1)
        self.assertEqual(len(a.hand), 2)  # the spare and one more

    def test_each_card_of_a_draw_looks_at_the_hand_again(self):
        game, a, b = setup(PHIAL)
        game.draw(a, 2)  # the first draw makes two cards; the second finds a full hand
        self.assertEqual(len(a.hand), 3)

    def test_only_its_controller(self):
        game, a, b = setup(PHIAL)
        game.draw(b, 1)
        self.assertEqual(len(b.hand), 1)

    def test_life_gained_at_five_or_less_is_doubled(self):
        game, a, b = setup(PHIAL)
        a.life = 5
        game.change_life(a, 3)
        self.assertEqual(a.life, 11)

    def test_not_above_five_life(self):
        game, a, b = setup(PHIAL)
        a.life = 6
        game.change_life(a, 3)
        self.assertEqual(a.life, 9)

    def test_it_stacks_with_another_life_doubler(self):
        game, a, b = setup(PHIAL, ARCHIVE)
        a.life = 4
        game.change_life(a, 2)
        self.assertEqual(a.life, 4 + 2 * 2 * 2)

    def test_losing_life_is_not_changed(self):
        game, a, b = setup(PHIAL)
        a.life = 4
        game.change_life(a, -2)
        self.assertEqual(a.life, 2)


if __name__ == "__main__":
    unittest.main()
