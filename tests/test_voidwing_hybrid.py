"""Voidwing Hybrid, from its real Oracle text: "When you proliferate, return this card from your graveyard to your hand." Heard from the
graveyard (Game.happened); an opponent's proliferating, or proliferating while it is on the battlefield, does nothing."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import real, run_stack, table3

VOIDWING = real("Voidwing Hybrid", "{U}{B}", "Creature — Phyrexian Bat", "Flying\nToxic 1 (Players dealt combat damage by this creature "
                "also get a poison counter.)\nWhen you proliferate, return this card from your graveyard to your hand.", "2", "1",
                colors=("B", "U"))
ASPIRANT = real("Scheming Aspirant", "{1}{B}", "Creature \u2014 Phyrexian Advisor", "Whenever you proliferate, each opponent loses 2 life "
                "and you gain 2 life.", "1", "3", colors=("B",))


class VoidwingHybridTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(VOIDWING), [])

    def test_proliferating_returns_it_from_your_graveyard(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard = [VOIDWING]
        game.proliferate(a)
        run_stack(game)
        self.assertEqual((a.hand, a.graveyard), ([VOIDWING], []))

    def test_another_proliferate_trigger_does_nothing_from_the_graveyard(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard = [ASPIRANT]
        game.proliferate(a)
        run_stack(game)
        self.assertEqual((a.life, a.graveyard), (40, [ASPIRANT]))

    def test_an_opponent_proliferating_or_it_on_the_battlefield_does_nothing(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.graveyard = [VOIDWING]
        game.proliferate(b)
        run_stack(game)
        self.assertEqual((a.hand, a.graveyard), ([], [VOIDWING]))
        a.graveyard, a.battlefield = [], [Permanent(VOIDWING)]
        game.proliferate(a)
        run_stack(game)
        self.assertEqual((a.hand, [p.card.name for p in a.battlefield]), ([], ["Voidwing Hybrid"]))


if __name__ == "__main__":
    unittest.main()
