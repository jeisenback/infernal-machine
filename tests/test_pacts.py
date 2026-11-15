"""The Pacts, from their real Oracle text: "At the beginning of your next upkeep, pay {3}{U}{U}. If you don't, you lose the game." (CR 603.7,
CR 104.3e). The cost is paid at its controller's next upkeep, not another player's; with the mana there it is paid, and without it they lose."""

import unittest

from infernal_machine.effects import spell_effects
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, real, table3

NEGATION = real("Pact of Negation", "{0}", "Instant", "Counter target spell.\nAt the beginning of your next upkeep, pay {3}{U}{U}. If you don't, "
                "you lose the game.", colors=("U",))
TITAN = real("Pact of the Titan", "{0}", "Instant", "Create a 4/4 red Giant creature token.\nAt the beginning of your next upkeep, pay {4}{R}. "
             "If you don't, you lose the game.", colors=("R",))


def after_titan(lands_count):
    game, _ = table3()
    a = game.seats[0]
    a.battlefield = lands(lands_count)
    for effect in spell_effects(TITAN):  # it resolves: the Giant, and the payment set for the next upkeep
        effect.resolve(game, a, None)
    return game, a


def upkeep(game, seat):
    game.turn += 1
    game.active, game.step = seat.index, "upkeep"
    game._turn_based_actions(seat)


class PactTests(unittest.TestCase):
    def test_the_pacts_are_understood(self):
        for card in (NEGATION, TITAN):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_paid_at_your_next_upkeep(self):
        game, a = after_titan(5)
        upkeep(game, game.seats[1])  # another player's upkeep passes it by
        self.assertEqual(sum(p.tapped for p in a.battlefield), 0)
        upkeep(game, a)
        self.assertEqual((a.lost, sum(p.tapped for p in a.battlefield)), (False, 5))

    def test_without_the_mana_you_lose(self):
        game, a = after_titan(4)
        upkeep(game, a)
        self.assertTrue(a.lost)

    def test_only_once(self):
        game, a = after_titan(5)
        upkeep(game, a)
        for p in a.battlefield:
            p.tapped = False
        upkeep(game, a)
        self.assertEqual((a.lost, sum(p.tapped for p in a.battlefield)), (False, 0))


if __name__ == "__main__":
    unittest.main()
