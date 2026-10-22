"""Spirit of Resilience (issue #80): a counter whenever cards leave your graveyard, and it may become a copy of an artifact
or creature card among them until end of turn. The line is the card's own Oracle text from Scryfall."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import GraveyardTarget, Permanent
from tests.helpers import BEAR, BIG, card, FOREST, pick, RELIC, run_stack, SHRINE, table3, triggers_80_supported as supported

SPIRIT = card("Whenever one or more cards leave your graveyard, put a +1/+1 counter on this creature, then you may have this "
              "creature become a copy of an artifact or creature card from among those cards until end of turn.", "Spirit")


class SpiritOfResilienceTests(unittest.TestCase):
    def table(self, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.spirit = Permanent(SPIRIT)
        a.battlefield = [self.spirit]
        return game, a

    def leave(self, game, a, *cards):
        a.graveyard = list(cards)
        for c in cards:
            game.exile_from_graveyard(GraveyardTarget(c, a))
        run_stack(game)

    def leave_together(self, game, a, *cards):
        a.graveyard = list(cards)
        game.shuffle_into_library(a, [GraveyardTarget(c, a) for c in cards])
        run_stack(game)

    def test_parse(self):
        supported(self, SPIRIT)

    def test_a_counter_and_a_copy_of_the_creature_card(self):
        game, a = self.table("Big")
        self.leave(game, a, BIG)
        self.assertEqual(self.spirit.counters.get("+1/+1"), 1)
        self.assertEqual(self.spirit.card.name, "Big")

    def test_the_copy_may_be_declined(self):
        game, a = self.table("Don't copy anything")
        self.leave(game, a, BIG)
        self.assertEqual((self.spirit.counters.get("+1/+1"), self.spirit.card.name), (1, "Spirit"))

    def test_a_noncreature_nonartifact_card_gives_only_the_counter(self):
        game, a = self.table("Shrine")
        self.leave_together(game, a, SHRINE, FOREST)
        self.assertEqual((self.spirit.counters.get("+1/+1"), self.spirit.card.name), (1, "Spirit"))

    def test_one_counter_for_cards_leaving_together_and_a_choice_among_the_eligible(self):
        game, a = self.table("Relic")
        self.leave_together(game, a, SHRINE, RELIC, FOREST)
        self.assertEqual((self.spirit.counters.get("+1/+1"), self.spirit.card.name), (1, "Relic"))

    def test_a_copy_of_an_artifact_card(self):
        game, a = self.table("Relic")
        self.leave(game, a, RELIC)
        self.assertEqual(self.spirit.card.name, "Relic")

    def test_it_returns_to_itself_at_end_of_turn(self):
        game, a = self.table("Big")
        self.leave(game, a, BIG)
        self.assertEqual(self.spirit.original.name, "Spirit")  # restored from here at cleanup

    def test_cards_leaving_an_opponents_graveyard_do_nothing(self):
        game, a = self.table("Big")
        b = game.seats[1]
        b.graveyard = [BIG]
        game.exile_from_graveyard(GraveyardTarget(BIG, b))
        run_stack(game)
        self.assertEqual(self.spirit.counters.get("+1/+1", 0), 0)
