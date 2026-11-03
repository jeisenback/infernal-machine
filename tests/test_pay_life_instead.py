"""Snuff Out: "If you control a Swamp, you may pay 4 life rather than pay this spell's mana cost." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import AlternativeCost, alternative_costs
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, OGRE, SWAMP, pick, real, run_stack, table3

SNUFF = real("Snuff Out", "{3}{B}", "Instant", "If you control a Swamp, you may pay 4 life rather than pay this spell's mana cost.\nDestroy "
             "target nonblack creature. It can't be regenerated.")
BLACK = Card(name="Black Knight", mana_cost="{B}", type_line="Creature — Knight", colors=("B",), power="2", toughness="2")


def table(lands, theirs=OGRE):
    game, _ = table3(pick("Pay 4 life", theirs.name))
    a, b = game.seats[0], game.seats[1]
    a.hand, a.battlefield = [SNUFF], [Permanent(card) for card in lands]
    b.battlefield = [Permanent(theirs)]
    return game, a, b


class SnuffOutTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SNUFF), [])
        self.assertEqual(alternative_costs(SNUFF), [AlternativeCost("Pay 4 life", life=4, requires="Swamp")])

    def test_with_a_swamp_it_costs_four_life(self):
        game, a, b = table([SWAMP])
        game._perform(a, CAST + SNUFF.name)
        run_stack(game)
        self.assertEqual((a.life, b.battlefield), (36, []))
        self.assertFalse(a.battlefield[0].tapped)

    def test_without_a_swamp_it_cannot_be_cast_for_life(self):
        game, a, _ = table([FOREST])
        self.assertNotIn(CAST + SNUFF.name, game.legal_actions(a))

    def test_a_black_creature_is_not_a_target(self):
        game, a, _ = table([SWAMP], BLACK)
        self.assertNotIn(CAST + SNUFF.name, game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
