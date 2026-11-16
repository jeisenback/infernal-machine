"""Venerated Rotpriest, from its real Oracle text: "Whenever a creature you control becomes the target of a spell, target opponent gets a
poison counter." A spell targeting an opponent's creature sets nothing off."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, SOL_RING, lands, pick, real, run_stack, table3

ROTPRIEST = real("Venerated Rotpriest", "{G}", "Creature — Phyrexian Druid", "Toxic 1 (Players dealt combat damage by this creature also "
                 "get a poison counter.)\nWhenever a creature you control becomes the target of a spell, target opponent gets a poison "
                 "counter.", "1", "2", colors=("G",))
GIANT_GROWTH = real("Giant Growth", "{G}", "Instant", "Target creature gets +3/+3 until end of turn.", None, None, colors=("G",))
NATURALIZE = real("Naturalize", "{1}{G}", "Instant", "Destroy target artifact or enchantment.", None, None, colors=("G",))


def cast_on(whose):
    """Seat 0, with Venerated Rotpriest, casts Giant Growth on the Bear of seat `whose`; returns the poison counters of seats 1 and 2."""
    game, _ = table3(pick("Bear 2/2 (seat %d" % whose))
    a, b, c = game.seats
    a.battlefield = [Permanent(ROTPRIEST)] + lands(1)
    game.seats[whose].battlefield.append(Permanent(BEAR))
    a.hand = [GIANT_GROWTH]
    game._perform(a, CAST + "Giant Growth")
    run_stack(game)
    return b.player_counters.get("poison", 0) + c.player_counters.get("poison", 0)


class VeneratedRotpriestTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(ROTPRIEST), [])

    def test_a_spell_targeting_your_creature_poisons_an_opponent(self):
        self.assertEqual(cast_on(0), 1)

    def test_a_spell_targeting_an_opponents_creature_does_not(self):
        self.assertEqual(cast_on(1), 0)

    def test_a_spell_targeting_your_noncreature_permanent_does_not(self):
        game, _ = table3(pick("Sol Ring"))
        a, b, c = game.seats
        a.battlefield = [Permanent(ROTPRIEST), Permanent(SOL_RING)] + lands(2)
        a.hand = [NATURALIZE]
        game._perform(a, CAST + "Naturalize")
        run_stack(game)
        self.assertEqual((b.player_counters.get("poison", 0) + c.player_counters.get("poison", 0), sorted(x.name for x in a.graveyard)),
                         (0, ["Naturalize", "Sol Ring"]))


if __name__ == "__main__":
    unittest.main()
