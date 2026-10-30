"""Revolt: "if a permanent left the battlefield under your control this turn" (Fatal Push)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, creature, lands, pick, real, run_stack, table3

PUSH = real("Fatal Push", "{B}", "Instant", "Destroy target creature if it has mana value 2 or less.\nRevolt — Destroy that creature if it "
            "has mana value 4 or less instead if a permanent left the battlefield under your control this turn.")
TWO = Card(name="Two", mana_cost="{1}{G}", cmc=2.0, type_line="Creature — Test", power="2", toughness="2")
FOUR = Card(name="Four", mana_cost="{3}{G}", cmc=4.0, type_line="Creature — Test", power="4", toughness="4")
FIVE = Card(name="Five", mana_cost="{4}{G}", cmc=5.0, type_line="Creature — Test", power="5", toughness="5")
CLUE = Card(name="Clue", type_line="Token Artifact — Clue")


def push(victim, revolt=False, revolt_by_opponent=False, last_turn=False):
    """Cast Fatal Push at the opponent's `victim`; first a permanent of the caster's (or of the opponent's) leaves the battlefield."""
    game, _ = table3(pick("Two", "Four", "Five"))
    a, b = game.seats[0], game.seats[1]
    a.hand, a.battlefield = [PUSH], lands(1)
    target = Permanent(victim)
    b.battlefield = [target]
    if revolt or revolt_by_opponent:
        clue = Permanent(CLUE)
        (a if revolt else b).battlefield.append(clue)
        game._leave_battlefield(clue, "sacrificed")
    if last_turn:
        game.turn += 1
    game._perform(a, CAST + PUSH.name)
    run_stack(game)
    return game.on_battlefield(target)


class FatalPushTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(PUSH), [])

    def test_it_destroys_a_creature_of_mana_value_two(self):
        self.assertFalse(push(TWO))

    def test_without_revolt_a_four_survives(self):
        self.assertTrue(push(FOUR))

    def test_with_revolt_a_four_is_destroyed(self):
        self.assertFalse(push(FOUR, revolt=True))

    def test_with_revolt_a_five_survives(self):
        self.assertTrue(push(FIVE, revolt=True))

    def test_an_opponents_permanent_leaving_is_not_revolt(self):
        self.assertTrue(push(FOUR, revolt_by_opponent=True))

    def test_revolt_is_only_for_this_turn(self):
        self.assertTrue(push(FOUR, revolt=True, last_turn=True))

if __name__ == "__main__":
    unittest.main()
