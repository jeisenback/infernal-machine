"""A loop of mandatory actions with no way to stop draws the game (#547, CR 104.4b). No card the engine plays makes a loop whose state
comes back exactly (the ones that repeat, like Polyraptor with Marauding Raptor, grow the board and meet its limit), so the loop here is
a real card's ability whose one effect puts the same ability on the stack again."""

import dataclasses
import unittest

from infernal_machine.effects import triggered_abilities
from infernal_machine.game import LOOP_CHECK_AFTER, LoopDraw, StackItem
from tests.helpers import pick, real, table

BOND = real("Sanguine Bond", "{3}{B}{B}", "Enchantment", "Whenever you gain life, target opponent loses that much life.")
[ABILITY] = triggered_abilities(BOND)
ENOUGH = LOOP_CHECK_AFTER + 500


@dataclasses.dataclass
class Again:
    """An effect that puts the ability back on the stack, `times` more times; `gain` life each time makes every state new."""
    times: int
    gain: int = 0

    def resolve(self, game, controller, target):
        game.resolved_count += 1
        assert game.resolved_count < ENOUGH * 4, "the loop was never stopped"
        if self.gain:
            game.change_life(controller, self.gain)
        if game.resolved_count < self.times:
            game.stack.append(StackItem(card=BOND, controller=controller, effects=[self], ability=ABILITY))


def looping_game(effect):
    game, _, _ = table(pick("Pass"))
    game.resolved_count = 0
    seat = game.seats[0]
    game.stack.append(StackItem(card=BOND, controller=seat, effects=[effect], ability=ABILITY))
    return game, seat


class LoopDrawTests(unittest.TestCase):
    def test_a_state_that_comes_back_ends_the_round_as_a_draw(self):
        game, seat = looping_game(Again(times=10**9))
        with self.assertRaises(LoopDraw):
            game._priority_round(seat)
        self.assertLessEqual(game.resolved_count, LOOP_CHECK_AFTER + 5)

    def test_a_loop_that_changes_something_each_time_is_not_one(self):
        game, seat = looping_game(Again(times=ENOUGH, gain=1))
        game._priority_round(seat)  # past the point where states are compared, and every one is new
        self.assertEqual((game.resolved_count, seat.life), (ENOUGH, 40 + ENOUGH))

    def test_a_loop_that_stops_before_the_check_is_not_one(self):
        game, seat = looping_game(Again(times=LOOP_CHECK_AFTER - 10))
        game._priority_round(seat)
        self.assertEqual(game.resolved_count, LOOP_CHECK_AFTER - 10)

    def test_play_ends_the_game_as_a_draw_and_says_why(self):
        game, seat = looping_game(Again(times=10**9))
        game.stack.clear()

        def turn(active):  # (setup has run by now)
            game.stack.append(StackItem(card=BOND, controller=active, effects=[Again(times=10**9)], ability=ABILITY))
            game._priority_round(active)
        game._take_turn = turn
        self.assertIsNone(game.play(max_turns=5))
        self.assertEqual(game.ended, "loop")


if __name__ == "__main__":
    unittest.main()
