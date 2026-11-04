""""Whenever this land attacks, create a Food token and exile up to one target card from a graveyard." (Restless Cottage)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, fire, real, table3

COTTAGE = real("Restless Cottage", "", "Land", "This land enters tapped.\n{T}: Add {B} or {G}.\n{2}{B}{G}: This land becomes a 4/4 black and "
               "green Horror creature until end of turn. It's still a land.\nWhenever this land attacks, create a Food token and exile up to "
               "one target card from a graveyard.")


def attack(graveyard):
    game, _ = table3(lambda prompt, options: 0)
    a, b = game.seats[0], game.seats[1]
    cottage = Permanent(COTTAGE)
    a.battlefield, a.graveyard = [cottage], []
    b.graveyard, b.exile = list(graveyard), []
    fire(game, a, cottage, "attacks")
    return a, b


class RestlessCottageTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(COTTAGE), [])

    def test_it_makes_a_food_and_exiles_a_card_from_a_graveyard(self):
        a, b = attack([BEAR])
        self.assertEqual([p.card.name for p in a.battlefield], ["Restless Cottage", "Food"])
        self.assertEqual((b.graveyard, b.exile), ([], [BEAR]))

    def test_with_no_card_in_a_graveyard_it_still_makes_a_food(self):
        a, b = attack([])
        self.assertEqual([p.card.name for p in a.battlefield], ["Restless Cottage", "Food"])
        self.assertEqual(b.exile, [])


if __name__ == "__main__":
    unittest.main()
