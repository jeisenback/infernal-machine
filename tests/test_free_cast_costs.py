"""A spell cast without paying its mana cost still has its additional costs to pay (CR 601.2b, 601.2h); with none to pay it with, it is not
cast and stays where it is. Found by a bot-strength run (#535): a cascade into a spell with "discard a card" as an additional cost, with an
empty hand, crashed in the bot's choice of what to discard. The cards are Tormenting Voice and Village Rites from their real Oracle text."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, FOREST, OGRE, pick, real, run_stack, table3

VOICE = real("Tormenting Voice", "{1}{R}", "Sorcery", "As an additional cost to cast this spell, discard a card.\nDraw two cards.", colors=("R",))
RITES = real("Village Rites", "{B}", "Instant", "As an additional cost to cast this spell, sacrifice a creature.\nDraw two cards.", colors=("B",))


class FreeCastCostsTests(unittest.TestCase):
    def cascade(self, found, hand=(), battlefield=()):
        game, players = table3(pick("Yes"))
        a = game.seats[0]
        a.hand = list(hand)
        a.battlefield = [Permanent(c) for c in battlefield]
        a.library = [FOREST, found, FOREST, FOREST, FOREST, FOREST]
        game.cascade(a, 4)
        run_stack(game)
        return game, a, players[0]

    def test_with_nothing_to_discard_it_is_not_cast_and_goes_to_the_bottom(self):
        game, a, player = self.cascade(VOICE)
        self.assertEqual((game.stack, a.exile, a.graveyard, a.hand), ([], [], [], []))
        self.assertIn("Tormenting Voice", [c.name for c in a.library])
        self.assertIn({"event": "cant_cast", "seat": 0, "card": "Tormenting Voice"}, player.events)

    def test_with_a_card_to_discard_it_is_cast_and_the_cost_paid(self):
        game, a, _ = self.cascade(VOICE, hand=[BEAR])
        self.assertEqual([c.name for c in a.graveyard], ["Bear", "Tormenting Voice"])
        self.assertEqual(len(a.hand), 2)  # it drew two

    def test_with_no_creature_to_sacrifice_it_is_not_cast(self):
        game, a, _ = self.cascade(RITES)
        self.assertEqual((game.stack, a.exile, a.graveyard), ([], [], []))
        self.assertIn("Village Rites", [c.name for c in a.library])

    def test_with_a_creature_to_sacrifice_it_is_cast_and_the_cost_paid(self):
        game, a, _ = self.cascade(RITES, battlefield=[OGRE])
        self.assertEqual([p.card.name for p in a.battlefield], [])
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Ogre", "Village Rites"])
        self.assertEqual(len(a.hand), 2)

    def test_a_copy_of_a_card_that_is_cast_pays_the_cost_too(self):
        """"Cast a copy of the card" (Isochron Scepter) is a cast: with no card to discard it is not."""
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.hand = []
        game._cast(a, VOICE, [VOICE], free=True, copy=True)
        self.assertEqual(game.stack, [])
        a.hand = [BEAR]
        game._cast(a, VOICE, [VOICE], free=True, copy=True)
        self.assertEqual(len(game.stack), 1)
        self.assertEqual([c.name for c in a.graveyard], ["Bear"])


if __name__ == "__main__":
    unittest.main()
