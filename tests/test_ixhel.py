"""Ixhel, Scion of Atraxa, from its real Oracle text: "Corrupted — At the beginning of your end step, each opponent who has three or more
poison counters exiles the top card of their library face down. You may look at and play those cards for as long as they remain exiled,
and you may spend mana as though it were mana of any color to cast those spells." An opponent with fewer than three is passed by, and so
is an opponent's end step."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from infernal_machine.zones import CAST_EXILE
from tests.helpers import BEAR, SWAMP, real, run_stack, table3

IXHEL = real("Ixhel, Scion of Atraxa", "{1}{W}{B}{G}", "Legendary Creature — Phyrexian Angel", "Flying, vigilance, toxic 2\nCorrupted "
             "— At the beginning of your end step, each opponent who has three or more poison counters exiles the top card of their "
             "library face down. You may look at and play those cards for as long as they remain exiled, and you may spend mana as though "
             "it were mana of any color to cast those spells.", "2", "5", colors=("B", "G", "W"))
ELVES = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))


def end_step(whose):
    """Seat 0 has Ixhel and a Swamp; seat 1 (3 poison counters) and seat 2 (2) each have Llanowar Elves on top; `whose` end step begins."""
    game, _ = table3()
    a, b, c = game.seats
    a.battlefield = [Permanent(IXHEL), Permanent(SWAMP)]
    b.player_counters["poison"], c.player_counters["poison"] = 3, 2
    b.library, c.library = [ELVES, BEAR], [ELVES, BEAR]
    game.step = "end"
    game._turn_based_actions(game.seats[whose])
    run_stack(game)
    return game, a, b, c


class IxhelTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(IXHEL), [])

    def test_a_corrupted_opponents_top_card_is_exiled_and_yours_to_play_with_any_mana(self):
        game, a, b, c = end_step(0)
        self.assertEqual((a.exile, b.library, c.library), ([ELVES], [BEAR], [ELVES, BEAR]))  # seat 2 has only two poison counters
        game.turn += 3
        game.step, game.active = "main1", a.index
        self.assertIn(CAST_EXILE + "Llanowar Elves", game.legal_actions(a))  # with a Swamp: any color

    def test_an_opponents_end_step_passes_it_by(self):
        _, a, b, _ = end_step(1)
        self.assertEqual((a.exile, b.library), ([], [ELVES, BEAR]))


if __name__ == "__main__":
    unittest.main()
