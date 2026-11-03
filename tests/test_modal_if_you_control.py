"""Flame of Anor: "Choose one. If you control a Wizard as you cast this spell, you may choose two instead." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, lands, pick, real, run_stack, table3

FLAME = real("Flame of Anor", "{1}{U}{R}", "Instant", "Choose one. If you control a Wizard as you cast this spell, you may choose two instead."
             "\n• Target player draws two cards.\n• Destroy target artifact.\n• Flame of Anor deals 5 damage to target creature.")
WIZARD = Card(name="Wizard", mana_cost="{U}", type_line="Creature — Human Wizard", power="1", toughness="1")


def cast(wizard):
    game, _ = table3(pick("Target player draws", "Flame of Anor deals", "Player: A", "Ogre"))
    a, b = game.seats[0], game.seats[1]
    a.hand, a.library = [FLAME], [OGRE] * 3
    a.battlefield = lands(3) + ([Permanent(WIZARD)] if wizard else [])
    b.battlefield = [Permanent(OGRE)]
    game._perform(a, CAST + FLAME.name)
    run_stack(game)
    return a, b


class FlameOfAnorTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(FLAME), [])

    def test_with_a_wizard_two_modes(self):
        a, b = cast(wizard=True)
        self.assertEqual(len(a.hand), 2)
        self.assertEqual(b.battlefield[0].damage, 5)

    def test_without_a_wizard_one_mode(self):
        a, b = cast(wizard=False)
        self.assertEqual(len(a.hand), 2)
        self.assertEqual(b.battlefield[0].damage, 0)


if __name__ == "__main__":
    unittest.main()
