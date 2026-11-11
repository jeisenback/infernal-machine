"""A mana ability's own cost ("{3}, {T}: Add {B} for each basic Swamp you control.") is paid with mana the rest of the payment
doesn't need: the lands that make another color pay the {3}, and the Swamps are left for the spell's {B}s."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from tests.helpers import FOREST, SWAMP, table3

STRONGHOLD = Card(name="Cabal Stronghold", type_line="Land", oracle_text="{T}: Add {C}.\n{3}, {T}: Add {B} for each basic Swamp you "
                  "control.", produced_mana=("B", "C"))  # as Scryfall gives it
BLUFFS = Card(name="Cascade Bluffs", type_line="Land", oracle_text="{T}: Add {C}.\n{U/R}, {T}: Add {U}{U}, {U}{R}, or {R}{R}.",
              produced_mana=("C", "R", "U"))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))


def payable(lands, cost):
    game, _ = table3()
    seat = game.seats[0]
    seat.battlefield = [Permanent(card) for card in lands]
    return game._payment(seat, Card(name="Probe", mana_cost=cost, type_line="Sorcery")) is not None


class FilterCostPaymentTests(unittest.TestCase):
    def test_the_swamps_listed_first_are_left_for_the_spell(self):
        # The Forests pay the {3} and the Stronghold makes {B}{B}; with the Swamps' {B}{B} that is four black.
        lands = [STRONGHOLD, SWAMP, SWAMP] + [FOREST] * 3
        self.assertTrue(payable(lands, "{B}{B}{B}{B}"))
        self.assertFalse(payable(lands, "{B}{B}{B}{B}{B}"))  # four black at most: two from the Swamps, two from the Stronghold

    def test_a_filter_with_a_hybrid_cost_leaves_the_color_the_spell_needs(self):
        # The Mountain pays {U/R}; the Island, listed first, is left for the spell's last {U}.
        self.assertTrue(payable([ISLAND, MOUNTAIN, BLUFFS], "{U}{U}{U}"))

    def test_it_still_cannot_make_more_than_the_lands_can(self):
        self.assertFalse(payable([STRONGHOLD, SWAMP, SWAMP, FOREST, FOREST], "{B}{B}{B}{B}"))  # the {3} needs three other lands


if __name__ == "__main__":
    unittest.main()
