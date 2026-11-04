""""If a source you control would deal noncombat damage to a creature an opponent controls, put that many -1/-1 counters on that creature
instead." (Soul-Scar Mage)."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BIG, lands, pick, real, run_stack, table3

MAGE = real("Soul-Scar Mage", "{R}", "Creature — Human Wizard", "Prowess\nIf a source you control would deal noncombat damage to a creature "
            "an opponent controls, put that many -1/-1 counters on that creature instead.", "1", "2")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def bolt(answer, mage_seat=0):
    game, _ = table3(pick(answer))
    a, b = game.seats[0], game.seats[1]
    giant, mine = Permanent(BIG), Permanent(BIG)
    game.seats[mage_seat].battlefield.append(Permanent(MAGE))
    a.hand, a.battlefield = [BOLT], a.battlefield + lands(1) + [mine]
    b.battlefield.append(giant)
    game._perform(a, CAST + BOLT.name)
    run_stack(game)
    return game, giant, mine


class SoulScarMageTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(MAGE), [])

    def test_your_burn_puts_minus_counters_on_their_creature(self):
        game, giant, _ = bolt("Big 5/5 (seat 1")
        self.assertEqual((giant.counters.get("-1/-1"), giant.damage), (3, 0))
        self.assertEqual(game.power(giant), 2)

    def test_your_own_creature_takes_damage(self):
        game, _, mine = bolt("Big 5/5 (seat 0")
        self.assertEqual((mine.counters.get("-1/-1", 0), mine.damage), (0, 3))

    def test_an_opponents_mage_does_not_help_you(self):
        game, giant, _ = bolt("Big 5/5 (seat 1", mage_seat=1)
        self.assertEqual((giant.counters.get("-1/-1", 0), giant.damage), (0, 3))

    def test_combat_damage_is_damage(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.battlefield, attacker, giant = [Permanent(MAGE)], Permanent(BIG), Permanent(BIG)
        a.battlefield.append(attacker)
        b.battlefield = [giant]
        game.damage(giant, 2, attacker, combat=True)
        self.assertEqual((giant.counters.get("-1/-1", 0), giant.damage), (0, 2))


if __name__ == "__main__":
    unittest.main()
