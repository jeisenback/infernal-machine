import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import filter_mana_ability, reflected_mana
from infernal_machine.game import CYCLE, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import FOREST, pick, table
from tests.test_lands import SWAMP, spell
from tests.test_mass_effects import table3

MYSTIC = Card(name="Fetid Heath", type_line="Land", produced_mana=("C",),
              oracle_text="{T}: Add {C}.\n{W/B}, {T}: Add {W}{W}, {W}{B}, or {B}{B}.")
ORCHARD = Card(name="Exotic Orchard", type_line="Land", produced_mana=("W", "U", "B", "R", "G"),
               oracle_text="{T}: Add one mana of any color that a land an opponent controls could produce.")
POOL = Card(name="Reflecting Pool", type_line="Land", produced_mana=("W", "U", "B", "R", "G", "C"),
            oracle_text="{T}: Add one mana of any type that a land you control could produce.")
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
LIFE_CYCLER = Card(name="Cycler", mana_cost="{3}", type_line="Land", oracle_text="Cycling—Pay 2 life.")


class FilterLandTests(unittest.TestCase):
    def test_parse(self):
        cost, units = filter_mana_ability(MYSTIC)
        self.assertEqual((cost, units), ("{W/B}", [frozenset("WB"), frozenset("WB")]))
        self.assertEqual(unsupported_lines(MYSTIC), [])

    def test_a_filter_land_turns_one_swamp_into_two_white(self):
        game, _, _ = table(None)
        a = game.seats[0]
        a.battlefield = [Permanent(MYSTIC), Permanent(SWAMP)]
        self.assertIsNotNone(game._payment(a, spell("{W}{W}")))

    def test_it_needs_its_colored_cost(self):
        game, _, _ = table(None)
        a = game.seats[0]
        a.battlefield = [Permanent(MYSTIC), Permanent(FOREST)]  # green can't pay {W/B}
        self.assertIsNone(game._payment(a, spell("{W}{W}")))

    def test_it_cannot_pay_for_itself(self):
        game, _, _ = table(None)
        a = game.seats[0]
        a.battlefield = [Permanent(MYSTIC)]
        self.assertIsNone(game._payment(a, spell("{W}{W}")))


class ReflectingLandTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(reflected_mana(ORCHARD), (True, False))
        self.assertEqual(reflected_mana(POOL), (False, True))
        self.assertEqual((unsupported_lines(ORCHARD), unsupported_lines(POOL)), ([], []))

    def test_exotic_orchard_makes_what_opponents_lands_make(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(ORCHARD), Permanent(SWAMP)]
        b.battlefield = [Permanent(MOUNTAIN)]
        self.assertIsNotNone(game._payment(a, spell("{R}{B}")))  # the Orchard is red, the Swamp black
        self.assertIsNone(game._payment(a, spell("{B}{B}")))  # your own Swamp doesn't change what the Orchard makes

    def test_exotic_orchard_without_opponent_lands_makes_nothing(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(ORCHARD)]
        self.assertIsNone(game._payment(a, spell("{1}")))

    def test_exotic_orchard_never_makes_colorless(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(ORCHARD)]
        b.battlefield = [Permanent(WASTES)]
        self.assertIsNone(game._payment(a, spell("{1}")))

    def test_reflecting_pool_reads_your_other_lands(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(POOL), Permanent(MOUNTAIN)]
        b.battlefield = [Permanent(SWAMP)]
        self.assertIsNotNone(game._payment(a, spell("{R}{R}")))
        self.assertIsNone(game._payment(a, spell("{B}{R}")))

    def test_reflecting_pool_counts_colorless(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(POOL), Permanent(WASTES)]
        self.assertIsNotNone(game._payment(a, spell("{C}{C}")))

    def test_two_reflecting_lands_do_not_feed_each_other(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(POOL), Permanent(POOL)]
        self.assertIsNone(game._payment(a, spell("{1}")))


class LifeCyclingTests(unittest.TestCase):
    def test_pay_life_to_cycle(self):
        game, _, _ = table(pick(CYCLE))
        a = game.seats[0]
        a.hand, a.library = [LIFE_CYCLER], [FOREST]
        game._priority_round(a)
        self.assertEqual((a.life, [c.name for c in a.graveyard], len(a.hand)), (38, ["Cycler"], 1))

    def test_not_offered_without_spare_life(self):
        game, _, _ = table(pick(CYCLE))
        a = game.seats[0]
        a.hand, a.life = [LIFE_CYCLER], 2
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CYCLE)], [])


if __name__ == "__main__":
    unittest.main()
