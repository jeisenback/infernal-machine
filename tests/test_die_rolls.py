"""Rolling a die (CR 706): "roll a d20" and what is "equal to the result". Lines are the cards' own Oracle text; the die is scripted."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, fire, real, table3

COPPER = real("Ancient Copper Dragon", "{4}{R}{R}", "Creature — Elder Dragon",
              "Flying\nWhenever this creature deals combat damage to a player, roll a d20. You create a number of Treasure tokens equal to "
              "the result.", "6", "5", colors=("R",))
GOLD = real("Ancient Gold Dragon", "{5}{W}{W}", "Creature — Elder Dragon",
            "Flying\nWhenever this creature deals combat damage to a player, roll a d20. You create a number of 1/1 blue Faerie Dragon "
            "creature tokens with flying equal to the result.", "7", "10", colors=("W",))
SILVER = real("Ancient Silver Dragon", "{6}{U}{U}", "Creature — Elder Dragon",
              "Flying\nWhenever this creature deals combat damage to a player, roll a d20. Draw cards equal to the result. You have no "
              "maximum hand size for the rest of the game.", "8", "8", colors=("U",))


class Die:
    """Every roll comes out as `result` (and remembers how many sides it was asked for)."""

    def __init__(self, result: int):
        self.result, self.sides = result, None

    def randint(self, low: int, high: int) -> int:
        self.sides = high
        return self.result


def names(seat):
    return [p.card.name for p in seat.battlefield]


class DieRollTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (COPPER, GOLD, SILVER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_copper_makes_as_many_treasures_as_the_d20_shows(self):
        for result in (7, 1):
            game, _ = table3()
            game.rng = die = Die(result)
            a = game.seats[0]
            dragon = Permanent(COPPER)
            a.battlefield = [dragon]
            fire(game, a, dragon, "combat_damage_to_player")
            self.assertEqual((names(a).count("Treasure"), die.sides), (result, 20), result)

    def test_gold_makes_flying_faerie_dragons(self):
        game, _ = table3()
        game.rng = Die(3)
        a = game.seats[0]
        dragon = Permanent(GOLD)
        a.battlefield = [dragon]
        fire(game, a, dragon, "combat_damage_to_player")
        faeries = [p for p in a.battlefield if p.card.name == "Faerie Dragon"]
        self.assertEqual((len(faeries), all(game.has_keyword(p, "flying") for p in faeries)), (3, True))

    def test_silver_draws_and_keeps_its_hand_for_the_rest_of_the_game(self):
        game, _ = table3()
        game.rng = Die(12)
        a, b, _ = game.seats
        dragon = Permanent(SILVER)
        a.battlefield, a.library = [dragon], [FOREST] * 20
        fire(game, a, dragon, "combat_damage_to_player")
        a.battlefield = []  # the dragon gone: the rest of the game still
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual(len(a.hand), 12)
        b.hand = [FOREST] * 9  # an opponent still discards down to seven
        game._turn_based_actions(b)
        self.assertEqual(len(b.hand), 7)
