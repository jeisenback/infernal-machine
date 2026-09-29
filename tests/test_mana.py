import unittest

from infernal_machine.mana import Cost, parse_cost, pay

G, U, W = frozenset("G"), frozenset("U"), frozenset("W")
GU = frozenset("GU")
ANY = frozenset("WUBRG")


class ParseCostTests(unittest.TestCase):
    def test_parses_symbols(self):
        self.assertEqual(parse_cost("{2}{G}{G}"), Cost(2, (G, G)))
        self.assertEqual(parse_cost("{X}{U}"), Cost(0, (U,)))
        self.assertEqual(parse_cost("{G/U}{W/P}{C}"), Cost(0, (GU, W, frozenset("C"))))
        self.assertEqual(parse_cost("{0}"), Cost(0, ()))

    def test_unsupported_or_missing(self):
        self.assertIsNone(parse_cost(""))
        self.assertIsNone(parse_cost("{S}"))
        self.assertIsNone(parse_cost("{2/W}"))


class PayTests(unittest.TestCase):
    def test_pays_colors_then_generic(self):
        self.assertEqual(sorted(pay(Cost(1, (G,)), [U, G])), [0, 1])

    def test_keeps_flexible_sources_untapped(self):
        self.assertEqual(pay(Cost(0, (G,)), [ANY, G]), [1])
        self.assertEqual(pay(Cost(1, ()), [ANY, U]), [1])

    def test_backtracks_to_find_an_assignment(self):
        # The dual must pay U, so the Forest pays G.
        self.assertEqual(sorted(pay(Cost(0, (G, U)), [GU, G])), [0, 1])

    def test_hybrid(self):
        self.assertEqual(pay(Cost(0, (GU,)), [U]), [0])

    def test_cannot_pay(self):
        self.assertIsNone(pay(Cost(0, (W,)), [G, U]))
        self.assertIsNone(pay(Cost(3, ()), [G, U]))
        self.assertIsNone(pay(Cost(0, (G, G)), [GU]))
        self.assertIsNone(pay(Cost(1, ()), [frozenset()]))  # makes no mana


if __name__ == "__main__":
    unittest.main()
