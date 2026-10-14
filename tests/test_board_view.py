"""`Game._board_view` caches what is true of the whole board; these check that the cache follows every kind of change (#340)."""

import dataclasses
import unittest

from infernal_machine.game import Permanent
from tests.test_effects import table
from tests.test_modifiers import ANTHEM, BEAR, ELF, HASTE, LORD


class BoardViewTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.seat = self.game.seats[0]

    def test_it_is_reused_while_the_board_is_the_same(self):
        self.seat.battlefield = [Permanent(ANTHEM), Permanent(BEAR)]
        self.assertIs(self.game._board_view(), self.game._board_view())

    def test_a_permanent_arriving_or_leaving_changes_what_it_says(self):
        bear = Permanent(BEAR)
        self.seat.battlefield = [bear]
        self.assertEqual(self.game.power(bear), 2)
        anthem = Permanent(ANTHEM)
        self.seat.battlefield = [anthem, bear]
        self.assertEqual(self.game.power(bear), 3)
        self.seat.battlefield = [bear]
        self.assertEqual(self.game.power(bear), 2)

    def test_a_permanent_changing_card_in_place_changes_what_it_says(self):
        bear, other = Permanent(BEAR), Permanent(ELF)
        self.seat.battlefield = [other, bear]
        self.assertEqual(self.game.power(bear), 2)
        other.card = ANTHEM  # a Clone or a transform: the same permanent, a different card
        self.assertEqual(self.game.power(bear), 3)
        other.card = ELF
        self.assertEqual(self.game.power(bear), 2)

    def test_control_changing_hands_changes_whose_creatures_are_pumped(self):
        anthem, mine, theirs = Permanent(ANTHEM), Permanent(BEAR), Permanent(BEAR)
        self.seat.battlefield = [anthem, mine]
        self.game.seats[1].battlefield = [theirs]
        self.assertEqual((self.game.power(mine), self.game.power(theirs)), (3, 2))
        self.seat.battlefield, self.game.seats[1].battlefield = [mine], [anthem, theirs]
        self.assertEqual((self.game.power(mine), self.game.power(theirs)), (2, 3))

    def test_rules_statics_follow_the_board_too(self):
        self.seat.battlefield = [Permanent(BEAR)]
        self.assertEqual(self.game._static_rules(), [])
        self.assertIs(self.game._static_rules(), self.game._static_rules())
        fervor = Permanent(HASTE)
        self.seat.battlefield = [fervor, Permanent(BEAR)]
        self.assertTrue(self.game.has_keyword(self.seat.battlefield[1], "haste"))
        self.seat.battlefield = [Permanent(BEAR)]
        self.assertFalse(self.game.has_keyword(self.seat.battlefield[0], "haste"))

    def test_a_card_that_dies_stops_pumping(self):
        lord, elf = Permanent(LORD), Permanent(ELF)
        self.seat.battlefield = [lord, elf]
        self.assertEqual(self.game.power(elf), 2)  # Elvish Archdruid: other Elves get +1/+1
        self.seat.battlefield = [elf]
        self.assertEqual(self.game.power(elf), 1)

    def test_a_copy_of_a_card_is_not_mistaken_for_the_original(self):
        # Tokens and copies are new Card objects with the same name: the key is the object, so they get their own entry.
        anthem_copy = dataclasses.replace(ANTHEM, type_line="Token Enchantment")
        bear = Permanent(BEAR)
        self.seat.battlefield = [Permanent(ANTHEM), bear]
        self.assertEqual(self.game.power(bear), 3)
        self.seat.battlefield = [Permanent(anthem_copy), bear]
        self.assertEqual(self.game.power(bear), 3)


if __name__ == "__main__":
    unittest.main()
