"""Ruthless Technomancer, from its real Oracle text: "When this creature enters, you may sacrifice another creature you control. If you
do, create a number of Treasure tokens equal to that creature's power." and "{2}{B}, Sacrifice X artifacts: Return target creature card
with power X or less from your graveyard to the battlefield. X can't be 0." X is announced before the target is chosen (CR 601.2b,
602.2b), so only an X that leaves a target is offered, and never 0."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, RELIC, activate, creature, enter, lands, real, run_stack, table3

TECHNOMANCER = real("Ruthless Technomancer", "{3}{B}", "Creature — Human Wizard", "When this creature enters, you may sacrifice another "
                    "creature you control. If you do, create a number of Treasure tokens equal to that creature's power.\n{2}{B}, Sacrifice X "
                    "artifacts: Return target creature card with power X or less from your graveyard to the battlefield. X can't be 0.",
                    "2", "4", colors=("B",))
WALL = creature("Wall", 0, 4)


def treasures(seat):
    return sum(p.card.name == "Treasure" for p in seat.battlefield)


def can_activate(game, seat):
    return any(a.startswith(ACTIVATE) and "Ruthless Technomancer" in a for a in game.legal_actions(seat))


class EntersTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(TECHNOMANCER), [])

    def test_sacrificing_another_creature_makes_treasures_equal_to_its_power(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(OGRE)]
        enter(game, a, TECHNOMANCER)
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], treasures(a)), (["Ogre"], 3))

    def test_declining_sacrifices_nothing(self):
        game, _ = table3(lambda prompt, options: len(options) - 1)
        a = game.seats[0]
        a.battlefield = [Permanent(OGRE)]
        enter(game, a, TECHNOMANCER)
        run_stack(game)
        self.assertEqual((a.graveyard, treasures(a)), ([], 0))


class ReturnTests(unittest.TestCase):
    def board(self, graveyard, artifacts):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(TECHNOMANCER), *lands(3), *[Permanent(RELIC) for _ in range(artifacts)]]
        a.graveyard = list(graveyard)
        return game, a

    def test_sacrificing_two_artifacts_returns_a_creature_with_power_two_or_less(self):
        game, a = self.board([OGRE, BEAR], 2)
        activate(game, a, "Ruthless Technomancer")  # X 1 is not offered: no target; the first X offered is 2 (the Ogre's power is 3)
        self.assertEqual(([p.card.name for p in a.battlefield if p.card.name in ("Bear", "Relic")], sorted(c.name for c in a.graveyard)),
                         (["Bear"], ["Ogre", "Relic", "Relic"]))

    def test_no_x_with_a_target_no_activation(self):
        game, a = self.board([OGRE], 2)  # at most X 2, and the Ogre has power 3
        self.assertFalse(can_activate(game, a))

    def test_x_cant_be_zero(self):
        game, a = self.board([WALL], 0)  # the 0-power Wall would be a target for X 0
        self.assertFalse(can_activate(game, a))
        a.battlefield.append(Permanent(RELIC))
        self.assertTrue(can_activate(game, a))


if __name__ == "__main__":
    unittest.main()
