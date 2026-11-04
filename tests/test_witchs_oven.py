""""{T}, Sacrifice a creature: Create a Food token. If the sacrificed creature's toughness was 4 or greater, create two Food tokens instead."
(Witch's Oven)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, activate, pick, real, table3

OVEN = real("Witch's Oven", "{1}", "Artifact", "{T}, Sacrifice a creature: Create a Food token. If the sacrificed creature's toughness was 4 "
            "or greater, create two Food tokens instead. (They're artifacts with \"{2}, {T}, Sacrifice this token: You gain 3 life.\")")


def bake(creature):
    game, _ = table3(pick(creature.name))
    a = game.seats[0]
    a.battlefield = [Permanent(OVEN), Permanent(creature)]
    activate(game, a, "Witch's Oven")
    return [p for p in a.battlefield if p.card.name == "Food"]


class WitchsOvenTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(OVEN), [])

    def test_a_small_creature_makes_one_food(self):
        self.assertEqual(len(bake(BEAR)), 1)

    def test_toughness_four_or_more_makes_two(self):
        self.assertEqual(len(bake(BIG)), 2)


if __name__ == "__main__":
    unittest.main()
