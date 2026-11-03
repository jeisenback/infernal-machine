"""Scion of Draco: "Each creature you control has vigilance if it's white, hexproof if it's blue, lifelink if it's black, first strike if
it's red, and trample if it's green." and its "Domain — This spell costs {2} less to cast for each basic land type among lands you
control." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import real, table3

SCION = real("Scion of Draco", "{12}", "Artifact Creature — Dragon", "Domain — This spell costs {2} less to cast for each basic land "
             "type among lands you control.\nFlying\nEach creature you control has vigilance if it's white, hexproof if it's blue, lifelink "
             "if it's black, first strike if it's red, and trample if it's green.", "4", "4")
WHITE = Card(name="White Knight", type_line="Creature — Knight", colors=("W",), power="2", toughness="2")
IZZET = Card(name="Izzet Mage", type_line="Creature — Wizard", colors=("U", "R"), power="2", toughness="2")
GOLEM = Card(name="Golem", type_line="Artifact Creature — Golem", power="2", toughness="2")


def land(name, types, mana):
    return Card(name=name, type_line=f"Land — {types}", produced_mana=tuple(mana))


class ScionOfDracoTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SCION), [])

    def test_each_creature_gets_the_keywords_of_its_colors(self):
        game, _ = table3()
        a = game.seats[0]
        white, izzet, golem = Permanent(WHITE), Permanent(IZZET), Permanent(GOLEM)
        a.battlefield = [Permanent(SCION), white, izzet, golem]
        self.assertTrue(game.has_keyword(white, "vigilance"))
        self.assertFalse(game.has_keyword(white, "trample"))
        self.assertTrue(game.has_keyword(izzet, "hexproof") and game.has_keyword(izzet, "first strike"))
        self.assertFalse(any(game.has_keyword(golem, k) for k in ("vigilance", "hexproof", "lifelink", "first strike", "trample")))

    def test_an_opponents_creatures_get_nothing(self):
        game, _ = table3()
        white = Permanent(WHITE)
        game.seats[0].battlefield = [Permanent(SCION)]
        game.seats[1].battlefield = [white]
        self.assertFalse(game.has_keyword(white, "vigilance"))

    def test_four_basic_land_types_make_it_cost_four(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [SCION]
        a.battlefield = [Permanent(land("Hallowed Fountain", "Plains Island", "WU")), Permanent(land("Blood Crypt", "Swamp Mountain", "BR")),
                         Permanent(land("Wastes", "Desert", "C")), Permanent(land("Wastes", "Desert", "C"))]
        self.assertIn(CAST + SCION.name, game.legal_actions(a))
        a.battlefield = a.battlefield[:1] + a.battlefield[2:]  # two types: {8}, and three lands
        self.assertNotIn(CAST + SCION.name, game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
