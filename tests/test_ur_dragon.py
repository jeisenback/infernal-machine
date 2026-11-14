"""The Ur-Dragon, a tracked deck's commander, from its real Oracle text. Eminence: "As long as The Ur-Dragon is in the command zone or on the
battlefield, other Dragon spells you cast cost {1} less to cast." (not The Ur-Dragon itself, nor a non-Dragon). "Whenever one or more Dragons
you control attack, draw that many cards, then you may put a permanent card from your hand onto the battlefield." (only Dragons count)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, attack_all, real, run_stack, table, table3

UR_DRAGON = real("The Ur-Dragon", "{4}{W}{U}{B}{R}{G}", "Legendary Creature — Dragon Avatar", "Eminence — As long as The Ur-Dragon is in the "
                 "command zone or on the battlefield, other Dragon spells you cast cost {1} less to cast.\nFlying\nWhenever one or more Dragons "
                 "you control attack, draw that many cards, then you may put a permanent card from your hand onto the battlefield.", "10", "10",
                 colors=tuple("WUBRG"))
SHIVAN = real("Shivan Dragon", "{4}{R}{R}", "Creature — Dragon", "Flying\n{R}: This creature gets +1/+0 until end of turn.", "5", "5",
              colors=("R",))


class EminenceTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        self.assertEqual(unsupported_lines(UR_DRAGON), [])

    def test_from_the_command_zone_or_the_battlefield_other_dragons_cost_one_less(self):
        game, _ = table3()
        a = game.seats[0]
        self.assertEqual(game.caster.cost_reduction(a, SHIVAN), 0)
        a.command_zone = [UR_DRAGON]
        self.assertEqual((game.caster.cost_reduction(a, SHIVAN), game.caster.cost_reduction(a, UR_DRAGON),
                          game.caster.cost_reduction(a, BEAR)), (1, 0, 0))
        a.command_zone, a.battlefield = [], [Permanent(UR_DRAGON)]
        self.assertEqual(game.caster.cost_reduction(a, SHIVAN), 1)

    def test_an_opponents_ur_dragon_does_nothing_for_you(self):
        game, _ = table3()
        game.seats[1].command_zone = [UR_DRAGON]
        self.assertEqual(game.caster.cost_reduction(game.seats[0], SHIVAN), 0)


class AttackTests(unittest.TestCase):
    def attack(self, *attackers, home=()):
        game, _, _ = table(attack_all, lambda prompt, options: 0)
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(c) for c in attackers] + [Permanent(c, tapped=True) for c in home], [FOREST] * 5
        game.combat.declare_attackers(a)
        run_stack(game)
        return a

    def test_it_draws_one_for_each_attacking_dragon_and_puts_a_permanent_down(self):
        a = self.attack(UR_DRAGON, SHIVAN, BEAR)
        self.assertEqual((len(a.hand), sum(p.card.name == "Forest" for p in a.battlefield)), (1, 1))  # two drawn, one Forest put down

    def test_without_attacking_dragons_it_does_not_trigger(self):
        a = self.attack(BEAR, home=[UR_DRAGON])  # The Ur-Dragon stays home tapped: only a Bear attacks
        self.assertEqual(a.hand, [])


if __name__ == "__main__":
    unittest.main()
