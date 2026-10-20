"""Laelia, the Blade Reforged (issue #80): a +1/+1 counter whenever one or more cards are put into exile from your library
and/or your graveyard. The line is the card's own Oracle text from Scryfall."""

import unittest

from infernal_machine.game import GraveyardTarget, Permanent
from tests.helpers import BEAR, card, FOREST, pick, RELIC, run_stack, table3, triggers_80_supported as supported

LAELIA = card("Whenever one or more cards are put into exile from your library and/or your graveyard, put a +1/+1 counter on "
              "Laelia.", "Laelia")


class LaeliaTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3(pick())
        self.a, self.b, _ = self.game.seats
        self.laelia = Permanent(LAELIA)
        self.a.battlefield = [self.laelia]
        self.a.library = [FOREST, RELIC, FOREST]

    def counters(self):
        run_stack(self.game)
        return self.laelia.counters.get("+1/+1", 0)

    def test_parse(self):
        supported(self, LAELIA)

    def test_exiling_from_the_library_adds_one_counter_for_the_whole_event(self):
        self.game.exile_top(self.a, 2, None)
        self.assertEqual(self.counters(), 1)

    def test_exiling_a_card_from_the_graveyard_adds_a_counter(self):
        self.a.graveyard = [RELIC]
        self.game.exile_card_from_graveyard(self.a, RELIC, False)
        self.assertEqual(self.counters(), 1)

    def test_exiling_from_the_graveyard_as_a_cost_adds_a_counter(self):
        self.a.graveyard = [RELIC, FOREST]
        self.game.exile_own_graveyard(self.a, 2)
        self.assertEqual(self.counters(), 1)

    def test_an_opponents_cards_do_not_count(self):
        self.b.library = [FOREST]
        self.game.exile_top(self.b, 1, None)
        self.assertEqual(self.counters(), 0)

    def test_exiling_a_permanent_does_not_count(self):
        bear = Permanent(BEAR)
        self.a.battlefield.append(bear)
        self.game.exile(bear)
        self.assertEqual(self.counters(), 0)

    def test_exiling_from_an_empty_library_does_not_count(self):
        self.a.library = []
        self.game.exile_top(self.a, 1, None)
        self.assertEqual(self.counters(), 0)

    def test_exiling_a_targeted_card_from_your_graveyard_adds_a_counter(self):
        self.a.graveyard = [RELIC]
        self.game.exile_from_graveyard(GraveyardTarget(RELIC, self.a))
        self.assertEqual(self.counters(), 1)

    def test_exiling_a_card_from_an_opponents_graveyard_does_not_count(self):
        self.b.graveyard = [RELIC]
        self.game.exile_from_graveyard(GraveyardTarget(RELIC, self.b))
        self.assertEqual(self.counters(), 0)
