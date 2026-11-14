""""Whenever this creature attacks and isn't blocked" (CR 509.1h), from the cards' real Oracle text: it triggers once blockers are
declared and none block it, and "defending player" is the player it attacks (Eternal of Harsh Truths draws, Abyssal Nightstalker makes them
discard, Swamp Mosquito gives them a poison counter). A blocked attacker's trigger doesn't happen."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, attack_all, real, run_stack, table

ETERNAL = real("Eternal of Harsh Truths", "{2}{U}", "Creature — Zombie Cleric", "Afflict 2 (Whenever this creature becomes blocked, "
               "defending player loses 2 life.)\nWhenever this creature attacks and isn't blocked, draw a card.", "1", "3", colors=("U",))
NIGHTSTALKER = real("Abyssal Nightstalker", "{3}{B}", "Creature — Nightstalker", "Whenever this creature attacks and isn't blocked, defending "
                    "player discards a card.", "2", "2", colors=("B",))
MOSQUITO = real("Swamp Mosquito", "{1}{B}", "Creature — Insect", "Flying\nWhenever this creature attacks and isn't blocked, defending player "
                "gets a poison counter. (A player with ten or more poison counters loses the game.)", "0", "1", colors=("B",))


def block(prompt, options):
    return len(options) - 1  # the last option blocks


def no_block(prompt, options):
    return 0  # "Don't block"


def combat(attacker, blocker_policy=no_block, blockers=(BEAR,)):
    game, _, _ = table(attack_all, blocker_policy)
    a, b = game.seats
    a.battlefield, a.library = [Permanent(attacker)], [FOREST] * 5
    b.battlefield, b.hand = [Permanent(c) for c in blockers], [FOREST, FOREST]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    run_stack(game)
    return a, b


class AttacksUnblockedTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (ETERNAL, NIGHTSTALKER, MOSQUITO):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_unblocked_it_triggers_and_defending_player_is_the_one_attacked(self):
        a, _ = combat(ETERNAL)
        _, b = combat(NIGHTSTALKER)
        _, poisoned = combat(MOSQUITO)
        self.assertEqual((len(a.hand), len(b.hand), poisoned.player_counters.get("poison")), (1, 1, 1))

    def test_blocked_it_does_not(self):
        a, _ = combat(ETERNAL, block)
        _, b = combat(NIGHTSTALKER, block)
        self.assertEqual((len(a.hand), len(b.hand)), (0, 2))


if __name__ == "__main__":
    unittest.main()
