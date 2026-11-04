""""This spell costs {X} less to cast, where X is the number of cards in your graveyard that are instant cards, sorcery cards, and/or have
an Adventure." (Hearth Elemental // Stoke Genius)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BOLT, DIVINATION, scryfall, table3

ELEMENTAL = {"name": "Hearth Elemental", "mana_cost": "{5}{R}", "type_line": "Creature — Elemental", "power": "4", "toughness": "5",
             "oracle_text": "This spell costs {X} less to cast, where X is the number of cards in your graveyard that are instant cards, "
                            "sorcery cards, and/or have an Adventure."}
STOKE = {"name": "Stoke Genius", "mana_cost": "{1}{R}", "type_line": "Sorcery — Adventure",
         "oracle_text": "Discard your hand, then draw two cards. (Then exile this card. You may cast the creature later from exile.)"}
HEARTH = Card.from_scryfall(scryfall("adventure", ELEMENTAL, STOKE, cmc=6.0, colors=["R"]))


class HearthElementalTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(HEARTH), [])

    def test_instants_sorceries_and_adventurers_in_the_graveyard_count(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard = [BOLT, DIVINATION, HEARTH]
        self.assertEqual(game.cost_reduction(a, HEARTH), 3)

    def test_other_cards_do_not(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard = [BEAR]
        self.assertEqual(game.cost_reduction(a, HEARTH), 0)


if __name__ == "__main__":
    unittest.main()
