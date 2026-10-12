"""Templates for effects that cannot take an X are written with a fixed number, so a line with X reports unsupported
instead of building an effect that needs a number."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Condition, spell_effects
from infernal_machine.effects.common import _count, _number
from infernal_machine.report import unsupported_lines


def spell(text):
    return Card(name="Test", type_line="Sorcery", oracle_text=text)


class FixedNumberTests(unittest.TestCase):
    def test_a_number_is_understood(self):
        self.assertEqual(unsupported_lines(spell("Each creature deals 2 damage to its controller.")), [])
        self.assertEqual(unsupported_lines(spell("Each creature deals two damage to its controller.")), [])

    def test_x_is_unsupported_where_the_effect_cannot_take_it(self):
        self.assertEqual(unsupported_lines(spell("Each creature deals X damage to its controller.")),
                         ["Each creature deals X damage to its controller."])
        self.assertIsNone(spell_effects(spell("Each creature deals X damage to its controller.")))

    def test_x_is_still_understood_where_it_is_resolved(self):
        self.assertEqual(unsupported_lines(spell("Draw X cards.")), [])

    def test_a_condition_with_a_fixed_number(self):
        self.assertEqual(unsupported_lines(spell("Draw a card. If you have five or more cards in hand, draw two cards instead.")), [])
        self.assertEqual(unsupported_lines(spell("Draw a card. If you have X or more cards in hand, draw two cards instead.")),
                         ["Draw a card. If you have X or more cards in hand, draw two cards instead."])

    def test_number_refuses_x(self):
        self.assertEqual(_number("three"), 3)
        self.assertEqual(_count("X"), "X")
        with self.assertRaises(AssertionError):
            _number("X")


if __name__ == "__main__":
    unittest.main()
