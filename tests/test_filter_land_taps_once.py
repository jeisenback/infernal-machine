"""A land with a plain mana ability and a costed one ("{T}: Add {C}." and "{U/R}, {T}: Add {U}{U}, ...") is tapped once in a
payment: for one ability or the other, never both (CR 107.5). The precons' filter lands could pay twice from one tap."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from tests.helpers import table3

BLUFFS = Card(name="Cascade Bluffs", type_line="Land", oracle_text="{T}: Add {C}.\n{U/R}, {T}: Add {U}{U}, {U}{R}, or {R}{R}.",
              produced_mana=("C", "R", "U"))  # as Scryfall gives it
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))


def payable(lands, cost):
    game, _ = table3()
    seat = game.seats[0]
    seat.battlefield = [Permanent(card) for card in lands]
    return game._payment(seat, Card(name="Probe", mana_cost=cost, type_line="Sorcery")) is not None


class FilterLandTapsOnceTests(unittest.TestCase):
    def test_the_filter_makes_two_from_two_lands(self):
        self.assertTrue(payable([BLUFFS, ISLAND], "{U}{U}"))  # the Island pays {U/R}, the Bluffs makes {U}{U}

    def test_it_does_not_also_make_its_colorless(self):
        self.assertFalse(payable([BLUFFS, ISLAND], "{1}{U}{U}"))  # three mana from two lands only if the Bluffs tapped twice

    def test_a_third_land_pays_the_rest(self):
        self.assertTrue(payable([BLUFFS, ISLAND, ISLAND], "{1}{U}{U}"))


if __name__ == "__main__":
    unittest.main()
