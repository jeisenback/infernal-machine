""""This creature can't be blocked this turn except by creatures with haste." (Gingerbrute), "... except by Walls." (Varchild's Crusader's
wording)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, activate, creature, lands, real, table3

GINGERBRUTE = real("Gingerbrute", "{1}", "Artifact Creature — Food Golem", "Haste (This creature can attack and {T} as soon as it comes "
                   "under your control.)\n{1}: This creature can't be blocked this turn except by creatures with haste.\n{2}, {T}, "
                   "Sacrifice this creature: You gain 3 life.", "1", "1")
SPRINTER = creature("Sprinter", 2, 2, "Haste")
WALL = real("Wall of Wood", "{G}", "Creature — Wall", "Defender", "0", "3")
DODGER = real("Dodger", "{0}", "Creature — Human", "{0}: This creature can't be blocked this turn except by Walls.", "1", "1")


def table(attacker, *blockers):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(attacker)] + lands(1)
    b.battlefield = [Permanent(card) for card in blockers]
    return game, a, b


class GingerbruteTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(GINGERBRUTE), [])

    def test_only_creatures_with_haste_can_block_it(self):
        game, a, b = table(GINGERBRUTE, BEAR, SPRINTER)
        activate(game, a, "can't be blocked")
        bear, sprinter = b.battlefield
        self.assertFalse(game.combat._can_block(bear, a.battlefield[0]))
        self.assertTrue(game.combat._can_block(sprinter, a.battlefield[0]))

    def test_anything_can_block_it_before_the_ability(self):
        game, a, b = table(GINGERBRUTE, BEAR)
        self.assertTrue(game.combat._can_block(b.battlefield[0], a.battlefield[0]))

    def test_except_by_walls(self):
        game, a, b = table(DODGER, BEAR, WALL)
        activate(game, a, "can't be blocked")
        bear, wall = b.battlefield
        self.assertFalse(game.combat._can_block(bear, a.battlefield[0]))
        self.assertTrue(game.combat._can_block(wall, a.battlefield[0]))


if __name__ == "__main__":
    unittest.main()
