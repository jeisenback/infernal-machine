"""Domain: the number of basic land types among lands you control (CR 205.3i). Leyline Binding's "costs {1} less to cast for each basic
land type among lands you control." and Tribal Flames' "deals X damage to any target, where X is the number of basic land types ..." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, pick, real, run_stack, table3

BINDING = real("Leyline Binding", "{5}{W}", "Enchantment", "Flash\nDomain — This spell costs {1} less to cast for each basic land type "
               "among lands you control.\nWhen this enchantment enters, exile target nonland permanent an opponent controls until this "
               "enchantment leaves the battlefield.")
FLAMES = real("Tribal Flames", "{1}{R}", "Sorcery", "Domain — Tribal Flames deals X damage to any target, where X is the number of basic "
              "land types among lands you control.")


def land(name, types, mana):
    return Card(name=name, type_line=f"Land — {types}", produced_mana=tuple(mana))


PLAINS = land("Plains", "Plains", "W")
MOUNTAIN = land("Mountain", "Mountain", "R")
WATERY_GRAVE = land("Watery Grave", "Island Swamp", "UB")  # one land, two basic land types


def table(hand, lands):
    game, _ = table3(pick("Player: B", "Ogre"))
    a = game.seats[0]
    a.hand, a.battlefield = list(hand), [Permanent(card) for card in lands]
    game.seats[1].battlefield = [Permanent(OGRE)]
    return game, a


class DomainTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (BINDING, FLAMES):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_each_type_is_counted_once(self):
        game, a = table([], [PLAINS, PLAINS, MOUNTAIN, WATERY_GRAVE])
        self.assertEqual(game.basic_land_types(a), 4)

    def test_tribal_flames_deals_one_damage_for_each_type(self):
        game, a = table([FLAMES], [MOUNTAIN, MOUNTAIN, WATERY_GRAVE])
        game._perform(a, CAST + FLAMES.name)
        run_stack(game)
        self.assertEqual(game.seats[1].life, 37)

    def test_leyline_binding_costs_one_less_for_each_type(self):
        game, a = table([BINDING], [PLAINS, MOUNTAIN, WATERY_GRAVE])  # four types: {5}{W} costs {1}{W}
        self.assertIn(CAST + BINDING.name, game.legal_actions(a))
        game._perform(a, CAST + BINDING.name)
        run_stack(game)
        self.assertEqual(sum(p.tapped for p in a.battlefield), 2)
        self.assertEqual(game.seats[1].battlefield, [])

    def test_fewer_types_cost_more(self):
        game, a = table([BINDING], [PLAINS, PLAINS, MOUNTAIN])  # two types: {3}{W}, and three lands
        self.assertNotIn(CAST + BINDING.name, game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
