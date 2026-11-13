"""Spectacle (CR 702.137), from the card's real Oracle text: Light Up the Stage may be cast for {R} rather than {2}{R}, but only once an
opponent has lost life this turn."""

import unittest

from infernal_machine.game import CAST, COST_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, lands, real, run_stack, table3

STAGE = real("Light Up the Stage", "{2}{R}", "Sorcery", "Spectacle {R} (You may cast this spell for its spectacle cost rather than its mana "
             "cost if an opponent lost life this turn.)\nExile the top two cards of your library. Until the end of your next turn, you may "
             "play those cards.", colors=("R",))


def spectacle(prompt, options):
    """Pay the spectacle cost when offered."""
    if COST_PROMPT.matches(prompt):
        return next(i for i, o in enumerate(options) if o.startswith("Spectacle"))
    return 0


class SpectacleTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(STAGE), [])

    def test_it_costs_r_once_an_opponent_lost_life_this_turn(self):
        for lost, castable in ((True, True), (False, False)):
            game, _ = table3(spectacle)
            a, b = game.seats[0], game.seats[1]
            a.battlefield, a.hand, a.library = lands(1), [STAGE], [FOREST, FOREST, FOREST]
            if lost:
                game.change_life(b, -2)
            self.assertEqual(CAST + STAGE.name in game.legal_actions(a), castable, lost)
            if castable:
                game._perform(a, CAST + STAGE.name)
                run_stack(game)
                self.assertEqual((len(a.exile), len(a.library), a.battlefield[0].tapped), (2, 1, True))

    def test_its_mana_cost_still_works_without_spectacle(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(3), [STAGE], [FOREST, FOREST]
        game._perform(a, CAST + STAGE.name)
        run_stack(game)
        self.assertEqual((len(a.exile), sum(p.tapped for p in a.battlefield)), (2, 3))


if __name__ == "__main__":
    unittest.main()
