"""Conspiracy Theorist (issue #80): "Whenever you discard one or more nonland cards, you may exile one of them from your
graveyard. If you do, you may cast it this turn."

The line is the card's own Oracle text from Scryfall. It triggers once for a whole discard, not once per card.
"""

import unittest

from infernal_machine.game import Permanent
from tests.test_effects import pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_triggers_80 import FOREST, RELIC, SHRINE, card, names, supported

THEORIST = card("Whenever you discard one or more nonland cards, you may exile one of them from your graveyard. If you do, you "
                "may cast it this turn.", "Theorist")


class ConspiracyTheoristTests(unittest.TestCase):
    def table(self, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        a.battlefield = [Permanent(THEORIST)]
        return game, a

    def test_parse(self):
        supported(self, THEORIST)

    def test_a_discarded_nonland_card_can_be_exiled_and_cast(self):
        game, a = self.table("Yes", "Relic")
        a.hand = [RELIC]
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual((a.graveyard, names(a, "exile")), ([], ["Relic"]))
        self.assertEqual([c.name for c, until in a.exile_play], ["Relic"])

    def test_declining_leaves_it_in_the_graveyard(self):
        game, a = self.table("No")
        a.hand = [RELIC]
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual((names(a, "graveyard"), a.exile), (["Relic"], []))

    def test_a_discarded_land_does_not_trigger_it(self):
        game, a = self.table("Yes", "Forest")
        a.hand = [FOREST]
        game.discard(a, 1)
        self.assertEqual(game.pending, [])

    def test_discarding_a_whole_hand_triggers_once_and_exiles_one_card(self):
        game, a = self.table("Yes", "Shrine")
        a.hand = [RELIC, FOREST, SHRINE]
        game.discard(a, None)
        run_stack(game)
        self.assertEqual((names(a, "graveyard"), names(a, "exile")), (["Forest", "Relic"], ["Shrine"]))

    def test_a_land_in_the_same_discard_is_not_a_choice(self):
        game, a = self.table("Yes", "Relic")
        a.hand = [FOREST, RELIC]
        game.discard(a, None)
        run_stack(game)
        self.assertEqual((names(a, "graveyard"), names(a, "exile")), (["Forest"], ["Relic"]))

    def test_an_opponents_discard_does_not_trigger_it(self):
        game, a = self.table("Yes", "Relic")
        game.seats[1].hand = [RELIC]
        game.discard(game.seats[1], 1)
        self.assertEqual(game.pending, [])
