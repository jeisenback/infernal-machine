"""Issue #811: the shared drivers in tests/helpers.py. `choose` picks a target by the permanent, not its label text (two Bears, one
pumped); the step drivers run the untap and end steps as the engine does; `combat_damage` deals damage to the player when unblocked and
to the blockers when blocked, the mistake an attack built by hand without `blocked=True` made."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, OGRE, choose, combat_damage, end_step, next_turn, table3, untap_step
from tests.real import REAL

# The guards these tests are there to catch (python tools/mutate.py tests.test_shared_helpers).
MUTATIONS = [
    ("tests/helpers.py", "list(blockers), blocked=bool(blockers))", "list(blockers), blocked=False)", "a blocked attack is blocked"),
    ("tests/helpers.py", "                if label in option:", "                if label.split()[0] in option:", "by the permanent, not its name"),
    ("tests/helpers.py", "                continue  # (gone: never offered)", "                pass", "a permanent that left is skipped"),
    ("tests/helpers.py", "    game.turn += 1\n    game.active = seat.index\n    begin(game, \"untap\", seat)",
     "    game.active = seat.index\n    begin(game, \"untap\", seat)", "the untap step begins a turn"),
    ("tests/helpers.py", "    untap_step(game, seat)\n    game.step = \"main1\"", "    untap_step(game, seat)", "next_turn ends in the main phase"),
]

class ChooseTests(unittest.TestCase):
    def test_it_picks_the_permanent_whatever_its_label(self):
        game, _ = table3()
        a = game.seats[0]
        first, second = Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [first, second]
        second.counters["+1/+1"] = 1
        options = [game.label(first), game.label(second)]
        self.assertEqual(choose(game, second)("Target", options), 1)
        self.assertEqual(choose(game, first)("Target", options), 0)

    def test_it_picks_a_player_and_passes_when_none_is_offered(self):
        game, _ = table3()
        _, b, c = game.seats
        options = ["Pass", f"Player: {b.name} (seat 1)", f"Player: {c.name} (seat 2)"]
        self.assertEqual(choose(game, c)("Target", options), 2)
        self.assertEqual(choose(game, Permanent(OGRE))("Target", options), 0)


class StepTests(unittest.TestCase):
    def test_the_untap_step_untaps_the_new_active_players_permanents_only(self):
        game, _ = table3()
        a, b, _ = game.seats
        mine, theirs = Permanent(BEAR, tapped=True), Permanent(OGRE, tapped=True)
        a.battlefield, b.battlefield = [mine], [theirs]
        turn = game.turn
        untap_step(game, b)
        self.assertEqual((game.turn, game.active, mine.tapped, theirs.tapped), (turn + 1, b.index, True, False))

    def test_the_end_step_resolves_its_triggers(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(REAL["Predatory Advantage"])]
        end_step(game, b)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Lizard", "Predatory Advantage"])

    def test_next_turn_ends_this_turn_and_starts_the_next_players(self):
        game, _ = table3()
        a, b, _ = game.seats
        theirs = Permanent(OGRE, tapped=True)
        b.battlefield = [theirs]
        next_turn(game, b)
        self.assertEqual((game.active, game.step, theirs.tapped), (b.index, "main1", False))


class CombatDamageTests(unittest.TestCase):
    def test_unblocked_it_hits_the_player_and_blocked_it_hits_the_blockers(self):
        game, _ = table3()
        a, b, _ = game.seats
        ogre, bear = Permanent(OGRE, sick=False), Permanent(BEAR)
        a.battlefield, b.battlefield = [ogre], [bear]
        life = b.life
        combat_damage(game, ogre, b)
        self.assertEqual(b.life, life - 3)
        combat_damage(game, ogre, b, blockers=[bear])
        self.assertEqual((b.life, bear in b.battlefield), (life - 3, False))


if __name__ == "__main__":
    unittest.main()
