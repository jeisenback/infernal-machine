"""A creature that "attacks each combat if able" (#208) is never offered the choice to stay home."""

import unittest

from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, creature, fight

CRUSHER = creature("Crusher", 8, 8, "Annihilator 1\nThis creature attacks each combat if able.")
NAMED = creature("Juggernaut", 5, 3, "Juggernaut attacks each combat if able.\nJuggernaut can't be blocked by Walls.")


class MustAttackTests(unittest.TestCase):
    def test_a_forced_creature_is_not_offered_staying_home_and_attacks(self):
        offered = []

        def stay_home(prompt, options):
            offered.append(list(options))
            return 0  # the first option: "Don't attack" if it is there

        game, a, b = fight([BEAR], attacker_policy=stay_home)
        self.assertEqual(offered[0][0], "Don't attack")
        self.assertEqual(b.life, 40)  # the Bear stayed home

        offered.clear()
        game, a, b = fight([NAMED], attacker_policy=stay_home)
        self.assertTrue(offered and all("Don't attack" not in options for options in offered))
        self.assertEqual(b.life, 35)  # the Juggernaut attacked anyway

    def test_a_forced_creature_still_picks_whom_to_attack(self):
        offered = []

        def pick_last(prompt, options):
            offered.append(list(options))
            return len(options) - 1

        fight([CRUSHER], attacker_policy=pick_last)
        self.assertEqual([len(options) for options in offered[:1]], [1])
        self.assertTrue(offered[0][0].startswith("Attack Player"))

    def test_a_creature_that_cannot_attack_is_not_asked(self):
        asked = []
        wall = creature("Wall", 0, 4, "Defender\nThis creature attacks each combat if able.")
        fight([wall], attacker_policy=lambda prompt, options: asked.append(prompt) or 0)
        self.assertEqual(asked, [])

    def test_the_line_is_supported(self):
        self.assertEqual(unsupported_lines(CRUSHER), [])
        self.assertEqual(unsupported_lines(NAMED), [])


if __name__ == "__main__":
    unittest.main()
