import unittest

from infernal_machine.analysis import analyze, color_pips
from infernal_machine.cards import Card

FOREST = Card(name="Forest", type_line="Basic Land — Forest")
ELVES = Card(name="Llanowar Elves", mana_cost="{G}", cmc=1, type_line="Creature — Elf Druid")
KITCHEN = Card(name="Kitchen Finks", mana_cost="{1}{G/W}{G/W}", cmc=3, type_line="Creature — Ouphe")
CRAB = Card(name="Hullbreaker Horror", mana_cost="{5}{U}{U}", cmc=7, type_line="Creature — Kraken Horror")
EMRAKUL = Card(name="Emrakul, the Aeons Torn", mana_cost="{15}", cmc=15, type_line="Legendary Creature — Eldrazi")


class AnalysisTests(unittest.TestCase):
    def test_color_pips(self):
        self.assertEqual(color_pips("{1}{G/W}{G/W}"), {"G": 2, "W": 2})
        self.assertEqual(color_pips("{2/B}{R/P}{X}{C}"), {"B": 1, "R": 1})
        self.assertEqual(color_pips(""), {})

    def test_analyze(self):
        stats = analyze([FOREST, FOREST, ELVES, KITCHEN, CRAB, EMRAKUL])
        self.assertEqual(stats.card_count, 6)
        self.assertEqual(stats.land_count, 2)
        self.assertEqual(stats.average_mana_value, 6.5)
        self.assertEqual(stats.curve, {0: 0, 1: 1, 2: 0, 3: 1, 4: 0, 5: 0, 6: 0, 7: 2})
        self.assertEqual(stats.color_pips, {"W": 2, "U": 2, "G": 3})

    def test_all_lands(self):
        stats = analyze([FOREST])
        self.assertEqual((stats.land_count, stats.average_mana_value), (1, 0.0))


if __name__ == "__main__":
    unittest.main()
