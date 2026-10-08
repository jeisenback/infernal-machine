import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import EntersTapped, enters_tapped_rule
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_effects import FOREST, pick
from tests.test_lands import SWAMP, enter
from tests.test_mass_effects import table3

PORT = REAL["Scorched Geyser"]
ISLANDS = REAL["Mystic Sanctuary"]
TURBULENT = REAL["Turbulent Fen"]
SNARL = Card(name="Furycalm Snarl", type_line="Land", produced_mana=("R", "W"),
             oracle_text="As this land enters, you may reveal a Mountain or Plains card from your hand. If you don't, "
                         "this land enters tapped.\n{T}: Add {R} or {W}.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
DUAL = Card(name="Volcanic Island", type_line="Land — Island Mountain", produced_mana=("U", "R"))
PLAINS_CARD = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))


class ParseTests(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(enters_tapped_rule(PORT), EntersTapped("unless_basic_lands", count=2))
        self.assertEqual(enters_tapped_rule(ISLANDS), EntersTapped("unless_land_type_count", types=("Island",), count=3))
        self.assertEqual(enters_tapped_rule(TURBULENT), EntersTapped("unless_opponent_lands", count=8))
        self.assertEqual(enters_tapped_rule(SNARL), EntersTapped("reveal", types=("Mountain", "Plains")))

    def test_the_report_no_longer_lists_these_lines(self):
        for card in (PORT, TURBULENT, SNARL):
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertEqual(unsupported_lines(ISLANDS), [])


class BasicLandTests(unittest.TestCase):
    def test_two_basic_lands(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(FOREST), Permanent(SWAMP)]
        self.assertFalse(enter(game, a, PORT).tapped)

    def test_nonbasic_lands_do_not_count(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(FOREST), Permanent(DUAL)]
        self.assertTrue(enter(game, a, PORT).tapped)


class LandTypeCountTests(unittest.TestCase):
    def test_three_other_islands(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(ISLAND), Permanent(DUAL), Permanent(ISLAND)]  # a dual with the Island type counts
        self.assertFalse(enter(game, a, ISLANDS).tapped)

    def test_two_is_not_enough(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(ISLAND), Permanent(ISLAND), Permanent(SWAMP)]
        self.assertTrue(enter(game, a, ISLANDS).tapped)


class OpponentLandTests(unittest.TestCase):
    def test_eight_lands_across_opponents(self):
        game, _ = table3()
        a, b, c = game.seats
        b.battlefield = [Permanent(FOREST) for _ in range(5)]
        c.battlefield = [Permanent(FOREST) for _ in range(3)]
        self.assertFalse(enter(game, a, TURBULENT).tapped)

    def test_seven_is_not_enough_and_your_own_lands_do_not_count(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(FOREST) for _ in range(9)]
        b.battlefield = [Permanent(FOREST) for _ in range(4)]
        c.battlefield = [Permanent(FOREST) for _ in range(3)]
        self.assertTrue(enter(game, a, TURBULENT).tapped)


class SnarlTests(unittest.TestCase):
    def test_reveal_a_matching_card_to_enter_untapped(self):
        game, _ = table3(pick("Reveal"))
        a = game.seats[0]
        a.hand = [MOUNTAIN]
        events = []
        game.broadcast = lambda event, **kw: events.append(event)
        self.assertFalse(enter(game, a, SNARL).tapped)
        self.assertEqual(a.hand, [MOUNTAIN])  # revealing does not remove it
        self.assertIn({"event": "revealed", "seat": 0, "card": "Mountain"}, events)

    def test_choosing_not_to_reveal(self):
        game, _ = table3(pick("Enter tapped"))
        a = game.seats[0]
        a.hand = [MOUNTAIN]
        self.assertTrue(enter(game, a, SNARL).tapped)

    def test_nothing_to_reveal(self):
        game, _ = table3(pick("Reveal"))
        a = game.seats[0]
        a.hand = [FOREST, ISLAND]
        self.assertTrue(enter(game, a, SNARL).tapped)

    def test_either_land_type_will_do(self):
        game, _ = table3(pick("Reveal"))
        a = game.seats[0]
        a.hand = [FOREST, PLAINS_CARD]
        self.assertFalse(enter(game, a, SNARL).tapped)


if __name__ == "__main__":
    unittest.main()
