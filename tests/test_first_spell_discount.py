"""The first spell of a kind each turn costs less (Radagast's family; Momo, Friendly Flier in the Standard decks, #564)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import first_spell_reductions
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import pick, real, table

MOMO = real("Momo, Friendly Flier", "{W}", "Legendary Creature — Lemur Bat Ally",
            "Flying\nThe first non-Lemur creature spell with flying you cast during each of your turns costs {1} less to cast.\n"
            "Whenever another creature you control with flying enters, Momo gets +1/+1 until end of turn.", "1", "1")
MELEK = real("Melek, Reforged Researcher", "{3}{U}{R}", "Legendary Creature — Weird Detective",
             "Melek, Reforged Researcher's power and toughness are each equal to twice the number of instant and sorcery cards in your graveyard.\n"
             "The first instant or sorcery spell you cast each turn costs {3} less to cast.", "*", "*")
SHADOW = real("Shadow in the Warp", "{1}{R}", "Enchantment",
              "The first creature spell you cast each turn costs {2} less to cast.\nWhenever an opponent casts their first noncreature spell "
              "each turn, this enchantment deals 2 damage to that player.")
GECKO = real("Vine Gecko", "{1}{G}", "Creature — Elemental Lizard",
             "The first kicked spell you cast each turn costs {1} less to cast.\nWhenever you cast a kicked spell, put a +1/+1 counter on this creature.", "2", "2")
HAWK = real("Test Hawk", "{2}{W}", "Creature — Bird", "Flying", "2", "2")
LEMUR = real("Test Lemur", "{2}{W}", "Creature — Lemur", "Flying", "2", "2")
OX = real("Test Ox", "{2}{W}", "Creature — Ox", "", "3", "3")
BOLT = real("Test Bolt", "{2}{R}", "Instant", "Test Bolt deals 3 damage to any target.")
PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))


class ParseTests(unittest.TestCase):
    def test_the_family_is_read(self):
        self.assertEqual(first_spell_reductions(MOMO), [("non-Lemur creature spell with flying", 1, True)])
        self.assertEqual(first_spell_reductions(SHADOW), [("creature spell", 2, False)])
        self.assertEqual(first_spell_reductions(MELEK), [("instant or sorcery spell", 3, False)])
        self.assertEqual(unsupported_lines(MOMO), [])
        self.assertEqual(unsupported_lines(SHADOW), [])

    def test_a_kicked_spell_is_not_a_kind_the_engine_knows(self):
        self.assertEqual(first_spell_reductions(GECKO), [])
        self.assertIn("The first kicked spell you cast each turn costs {1} less to cast.", unsupported_lines(GECKO))


def board(*permanents, hand=(), cast_log=()):
    game, _, _ = table()
    a = game.seats[0]
    a.battlefield = [Permanent(c) for c in permanents]
    a.hand = list(hand)
    a.cast_log = [(game.turn, c) for c in cast_log]
    return game, a


class MomoTests(unittest.TestCase):
    def test_the_first_flying_creature_spell_on_your_turn_costs_one_less(self):
        game, a = board(MOMO)
        self.assertEqual(game.cost_reduction(a, HAWK), 1)

    def test_not_a_lemur_not_a_creature_without_flying_and_not_an_instant(self):
        game, a = board(MOMO)
        self.assertEqual([game.cost_reduction(a, c) for c in (LEMUR, OX, BOLT)], [0, 0, 0])

    def test_only_the_first_each_turn(self):
        game, a = board(MOMO, cast_log=[HAWK])
        self.assertEqual(game.cost_reduction(a, HAWK), 0, "a flyer was cast this turn already")
        game, a = board(MOMO, cast_log=[OX])
        self.assertEqual(game.cost_reduction(a, HAWK), 1, "an Ox is not of the kind")

    def test_not_on_an_opponents_turn(self):
        game, a = board(MOMO)
        game.active = 1
        self.assertEqual(game.cost_reduction(a, HAWK), 0)

    def test_the_discount_lets_the_spell_be_cast_with_one_land_fewer(self):
        game, a = board(MOMO, PLAINS, PLAINS, hand=[HAWK])
        self.assertIn(CAST + HAWK.name, game.legal_actions(a), "{2}{W} with two Plains and the discount")
        game, a = board(PLAINS, PLAINS, hand=[HAWK])
        self.assertNotIn(CAST + HAWK.name, game.legal_actions(a), "and not without Momo")

    def test_cast_through_the_game(self):
        game, _, _ = table(pick(CAST + HAWK.name))
        a = game.seats[0]
        a.battlefield = [Permanent(MOMO), Permanent(PLAINS), Permanent(PLAINS)]
        a.hand = [HAWK, HAWK]
        game._priority_round(a)
        self.assertEqual([p.card.name for p in a.battlefield].count("Test Hawk"), 1, "the first Hawk for two, the second not affordable")


class EachTurnTests(unittest.TestCase):
    def test_each_turn_counts_an_opponents_turn_too(self):
        game, a = board(SHADOW)
        game.active = 1
        self.assertEqual(game.cost_reduction(a, OX), 2)
        self.assertEqual(game.cost_reduction(a, BOLT), 0)


if __name__ == "__main__":
    unittest.main()
