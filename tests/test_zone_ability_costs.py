"""An ability that works from the graveyard and has no mana in its cost (#513): Cauldron Familiar's "Sacrifice a Food: Return this card
from your graveyard to the battlefield." was offered with no look at the Food, and listing the actions asserted on its empty mana cost.
The Familiar is from its real Oracle text; the Food and the Treasure are probes."""

import unittest

from infernal_machine.game import ACTIVATE_GRAVEYARD, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, pick, real, run_stack, table

FAMILIAR = real("Cauldron Familiar", "{B}", "Creature — Cat", "When this creature enters, each opponent loses 1 life and you gain 1 life.\n"
                "Sacrifice a Food: Return this card from your graveyard to the battlefield.", "1", "1")
FOOD = real("Food Probe", "{0}", "Artifact — Food", "")
TREASURE = real("Treasure Probe", "{0}", "Artifact — Treasure", "")
ACTION = ACTIVATE_GRAVEYARD + "Cauldron Familiar"


def seat_with(*permanents, mana=0):
    game, _, _ = table(pick(ACTION))
    a = game.seats[0]
    a.graveyard = [FAMILIAR]
    a.battlefield = [*(Permanent(c) for c in permanents), *lands(mana)]
    return game, a


class FromTheGraveyardWithAnotherCostTests(unittest.TestCase):
    def test_every_line_is_read(self):
        self.assertEqual(unsupported_lines(FAMILIAR), [])

    def test_with_no_food_it_is_not_offered_and_listing_does_not_raise(self):
        game, a = seat_with(TREASURE)
        self.assertNotIn(ACTION, game.legal_actions(a))

    def test_with_a_food_it_is_offered_without_any_mana(self):
        game, a = seat_with(FOOD)
        self.assertIn(ACTION, game.legal_actions(a))

    def test_it_sacrifices_the_food_and_comes_back(self):
        game, a = seat_with(FOOD, TREASURE)
        game._perform(a, ACTION)
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Cauldron Familiar", "Treasure Probe"])
        self.assertEqual(a.graveyard, [FOOD])

    def test_it_asks_nothing_of_the_lands(self):
        game, a = seat_with(FOOD, mana=2)
        game._perform(a, ACTION)
        run_stack(game)
        self.assertFalse(any(p.tapped for p in a.battlefield))

    def test_the_familiar_does_not_come_back_twice_from_one_food(self):
        game, a = seat_with(FOOD)
        game._perform(a, ACTION)
        run_stack(game)
        a.battlefield = [p for p in a.battlefield if p.card is not FAMILIAR]
        a.graveyard = [FAMILIAR]
        self.assertNotIn(ACTION, game.legal_actions(a))  # the Food went to the graveyard with the first return


if __name__ == "__main__":
    unittest.main()
