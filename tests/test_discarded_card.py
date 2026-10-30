"""A spell that asks about the card discarded to pay its additional cost: Grab the Prize."""

import unittest

from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, OGRE, lands, pick, real, run_stack, table3

GRAB = real("Grab the Prize", "{1}{R}", "Sorcery", "As an additional cost to cast this spell, discard a card.\nDraw two cards. If the discarded "
            "card wasn't a land card, Grab the Prize deals 2 damage to each opponent.")


def cast_discarding(discard):
    game, _ = table3(pick(discard.name))
    a = game.seats[0]
    a.hand, a.graveyard = [GRAB, discard], []
    a.library = [OGRE, OGRE, OGRE]
    a.battlefield = lands(2)
    game._perform(a, CAST + GRAB.name)
    run_stack(game)
    return game, a


class GrabThePrizeTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(GRAB), [])

    def test_a_nonland_discard_deals_damage_to_each_opponent(self):
        game, a = cast_discarding(OGRE)
        self.assertEqual(a.hand, [OGRE, OGRE])
        self.assertIn(OGRE, a.graveyard)
        self.assertEqual([s.life for s in game.seats], [40, 38, 38])

    def test_a_land_discard_only_draws(self):
        game, a = cast_discarding(FOREST)
        self.assertEqual(a.hand, [OGRE, OGRE])
        self.assertIn(FOREST, a.graveyard)
        self.assertEqual([s.life for s in game.seats], [40, 40, 40])

    def test_it_cannot_be_cast_without_a_card_to_discard(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield = [GRAB], lands(2)
        self.assertNotIn(CAST + GRAB.name, game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
