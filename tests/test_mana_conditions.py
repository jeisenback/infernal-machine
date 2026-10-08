import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Condition, filter_mana_ability, is_mana_ability, mana_ability, mana_condition
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import FOREST
from tests.test_lands import spell
from tests.test_mass_effects import table3

TEMPLE = Card(name="Temple of the False God", type_line="Land", produced_mana=("C",),
              oracle_text="{T}: Add {C}{C}. Activate only if you control five or more lands.")
MOX = Card(name="Mox Jasper", mana_cost="{0}", type_line="Artifact", produced_mana=("W", "U", "B", "R", "G"),
           oracle_text="{T}: Add one mana of any color. Activate only if you control a Dragon.")
HALL = Card(name="Hall of Oracles", type_line="Land", produced_mana=("C",),
            oracle_text="{T}: Add {C}.\n{1}, {T}: Add one mana of any color.")
MOON = Card(name="Moon Stone", mana_cost="{1}", type_line="Artifact",
            oracle_text="{T}: Add {G}. Activate only if the moon is full.")
DRAGON = Card(name="Dragon", type_line="Creature — Dragon", power="4", toughness="4")


class ParseTests(unittest.TestCase):
    def test_conditions_are_read(self):
        self.assertEqual(mana_condition(TEMPLE), Condition("control_at_least", 5, "land"))
        self.assertEqual(mana_condition(MOX), Condition("control_at_least", 1, "Dragon"))
        self.assertIsNone(mana_condition(HALL))
        self.assertEqual(mana_ability(TEMPLE, frozenset()), [frozenset("C"), frozenset("C")])

    def test_hall_of_oracles_turns_one_mana_into_any_color(self):
        self.assertEqual(filter_mana_ability(HALL), ("{1}", [frozenset("WUBRG")]))
        self.assertTrue(is_mana_ability("{1}, {T}: Add one mana of any color."))

    def test_the_report_understands_them(self):
        for card in (TEMPLE, MOX, HALL):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_an_unknown_condition_is_not_a_mana_ability(self):
        self.assertFalse(is_mana_ability("{T}: Add {G}. Activate only if the moon is full."))
        self.assertIsNone(mana_ability(MOON, frozenset()))
        self.assertEqual(len(unsupported_lines(MOON)), 1)


class SourceTests(unittest.TestCase):
    def sources(self, game, seat, permanent):
        return [s for s in game._mana_sources(seat) if s.permanent is permanent]

    def test_a_land_that_needs_five_lands(self):
        game, _ = table3()
        a = game.seats[0]
        temple = Permanent(TEMPLE)
        a.battlefield = [temple, *[Permanent(FOREST) for _ in range(3)]]
        self.assertEqual(self.sources(game, a, temple), [])  # four lands
        a.battlefield.append(Permanent(FOREST))
        self.assertEqual(len(self.sources(game, a, temple)), 2)  # five lands: {C}{C}

    def test_it_pays_for_a_spell_only_with_five_lands(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(TEMPLE), *[Permanent(FOREST) for _ in range(3)]]
        self.assertIsNone(game._payment(a, spell("{4}")))
        a.battlefield.append(Permanent(FOREST))
        self.assertIsNotNone(game._payment(a, spell("{6}")))

    def test_a_nonland_with_a_condition(self):
        game, _ = table3()
        a = game.seats[0]
        mox = Permanent(MOX)
        a.battlefield = [mox]
        self.assertEqual(self.sources(game, a, mox), [])
        a.battlefield.append(Permanent(DRAGON))
        self.assertEqual(len(self.sources(game, a, mox)), 1)

    def test_hall_of_oracles_filters_into_any_color(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(FOREST)]
        self.assertIsNone(game._payment(a, spell("{W}")))  # a Forest alone makes green
        a.battlefield = [Permanent(HALL)]
        self.assertIsNone(game._payment(a, spell("{W}")))  # the Hall needs {1} to make its mana
        a.battlefield = [Permanent(HALL), Permanent(FOREST)]
        self.assertIsNotNone(game._payment(a, spell("{W}")))  # the Forest pays {1}, the Hall makes white


if __name__ == "__main__":
    unittest.main()
