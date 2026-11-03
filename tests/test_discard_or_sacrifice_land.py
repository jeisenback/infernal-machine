""""You may discard a card or sacrifice a land. If you do, draw two cards." (Highway Robbery)."""

import unittest

from infernal_machine.game import CAST, DISCARD_OR_SACRIFICE_PROMPT, DO_NEITHER, SACRIFICE_A_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, OGRE, RAINBOW, pick, real, run_stack, table3

ROBBERY = real("Highway Robbery", "{1}{R}", "Sorcery", "You may discard a card or sacrifice a land. If you do, draw two cards.\nPlot {1}{R} "
               "(You may pay {1}{R} and exile this card from your hand. Cast it as a sorcery on a later turn without paying its mana "
               "cost. Plot only as a sorcery.)")


def cast(answer, hand=(OGRE,), lands=(RAINBOW, RAINBOW, FOREST)):
    game, _ = table3(pick(answer, "Forest"))
    a = game.seats[0]
    a.hand, a.graveyard, a.library = [ROBBERY] + list(hand), [], [OGRE, OGRE, OGRE]
    a.battlefield = [Permanent(card) for card in lands]
    game._perform(a, CAST + ROBBERY.name)
    run_stack(game)
    return a


class HighwayRobberyTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(ROBBERY), [])

    def test_discarding_draws_two(self):
        a = cast("Discard a card")
        self.assertEqual((len(a.hand), a.graveyard.count(OGRE)), (2, 1))

    def test_sacrificing_a_land_draws_two(self):
        a = cast("Sacrifice a land")
        self.assertEqual(len(a.hand), 3)
        self.assertNotIn("Forest", [p.card.name for p in a.battlefield])

    def test_neither_draws_nothing(self):
        a = cast("Neither")
        self.assertEqual(a.hand, [OGRE])

    def test_only_what_can_be_paid_is_offered(self):
        offered = []

        def policy(prompt, options):
            if DISCARD_OR_SACRIFICE_PROMPT.matches(prompt):
                offered.append(list(options))
            return options.index(DO_NEITHER) if DO_NEITHER in options else 0
        game, _ = table3(policy)
        a = game.seats[0]
        a.hand, a.battlefield = [ROBBERY], [Permanent(RAINBOW), Permanent(RAINBOW)]
        game._perform(a, CAST + ROBBERY.name)
        run_stack(game)
        self.assertEqual(offered, [[SACRIFICE_A_LAND, DO_NEITHER]])  # an empty hand: no discard; its tapped lands can still be sacrificed

    def test_without_lands_sacrificing_is_not_offered(self):  # cast for free once plotted
        offered = []
        game, _ = table3(lambda prompt, options: offered.append(list(options)) or len(options) - 1)
        a = game.seats[0]
        a.hand, a.battlefield = [OGRE], []
        game.may_discard_or_sacrifice_land_to_draw(a, 2)
        self.assertEqual(offered, [["Discard a card", DO_NEITHER]])


if __name__ == "__main__":
    unittest.main()
