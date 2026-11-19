"""Issue #839: Firebending N, "(Whenever this creature attacks, add N {R}. This mana lasts until end of combat.)" (CR 702.189a), from the
cards' real Oracle text. All nine cards whose only gap it was are fully playable. Rough Rhino Cavalry (Firebending 2) attacks: {R}{R} is
added and stays in the pool as the combat steps end, while other mana empties; what was spent is not kept; it is gone once combat ends;
a creature that doesn't attack adds nothing."""

import unittest

from infernal_machine.combat import ATTACK_PROMPT
from infernal_machine.game import Permanent
from tests.helpers import run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Azula, On the Hunt", "Fire Sages", "Loyal Fire Sage", "Rough Rhino Cavalry", "Tundra Tank", "Uncle Iroh", "Vindictive Warden",
         "Zuko, Exiled Prince", "Zuko, Seeking Honor"]
RHINO = REAL["Rough Rhino Cavalry"]
R, G = frozenset("R"), frozenset("G")

# The guards these tests are there to catch (python tools/mutate.py tests.test_firebending).
MUTATIONS = [
    ("infernal_machine/game.py", "            seat.mana_pool.extend(frozenset(\"R\") for _ in range(kept))\n", "", "the {R} stays through combat"),
    ("infernal_machine/game.py", 'if seat.combat_mana and self.step in COMBAT_STEPS - {"end_of_combat"} | {"first_strike_damage"}:',
     "if seat.combat_mana:", "only until end of combat"),
    ("infernal_machine/game.py", 'kept = min(seat.combat_mana, seat.mana_pool.count(frozenset("R")))', "kept = seat.combat_mana",
     "only what is left of it"),
    ("infernal_machine/effects/families/mana.py", "        controller.combat_mana += self.amount\n", "", "it is firebending's mana"),
]


def attacks(attack=True):
    """Seat 0's Rough Rhino Cavalry attacks (or not) and its trigger resolves; {G} is in the pool too."""
    game, _ = table3(lambda prompt, options: (1 if attack else 0) if ATTACK_PROMPT.matches(prompt) else 0)
    a = game.seats[0]
    a.battlefield = [Permanent(RHINO, sick=False)]
    game.step = "declare_attackers"
    game.combat.declare_attackers(a)
    run_stack(game)
    a.mana_pool.append(G)
    return game, a


def step_ends(game, step):
    game.step = step
    game._empty_pools()


class FirebendingTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_its_mana_lasts_until_end_of_combat(self):
        game, a = attacks()
        self.assertEqual(sorted(a.mana_pool, key=sorted), [G, R, R])
        for step in ("declare_attackers", "declare_blockers", "combat_damage"):
            step_ends(game, step)
            self.assertEqual(a.mana_pool, [R, R], step)
        step_ends(game, "end_of_combat")
        self.assertEqual(a.mana_pool, [])

    def test_what_was_spent_is_not_kept(self):
        game, a = attacks()
        a.mana_pool.remove(R)
        step_ends(game, "declare_attackers")
        self.assertEqual(a.mana_pool, [R])
        a.mana_pool.append(R)  # ({R} from elsewhere: not firebending's)
        step_ends(game, "declare_blockers")
        self.assertEqual(a.mana_pool, [R])

    def test_a_creature_that_doesnt_attack_adds_nothing(self):
        game, a = attacks(attack=False)
        self.assertEqual(a.mana_pool, [G])


if __name__ == "__main__":
    unittest.main()
