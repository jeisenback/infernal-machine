"""Braids, Arisen Nightmare, from its real Oracle text: "At the beginning of your end step, you may sacrifice an artifact, creature,
enchantment, land, or planeswalker. If you do, each opponent may sacrifice a permanent of their choice that shares a card type with it.
For each opponent who doesn't, that player loses 2 life and you draw a card." An opponent with nothing of that type can't sacrifice;
declining the first sacrifice does nothing."""

import unittest

from infernal_machine.game import SHARE_SACRIFICE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, fire, real, table3

BRAIDS = real("Braids, Arisen Nightmare", "{1}{B}{B}", "Legendary Creature — Nightmare", "At the beginning of your end step, you may "
              "sacrifice an artifact, creature, enchantment, land, or planeswalker. If you do, each opponent may sacrifice a permanent of "
              "their choice that shares a card type with it. For each opponent who doesn't, that player loses 2 life and you draw a card.",
              "3", "3", colors=("B",))


def end_step(opponents_sacrifice, b_has, c_has, braids_sacrifices=True):
    def policy(prompt, options):
        if SHARE_SACRIFICE_PROMPT.matches(prompt):
            return 0 if opponents_sacrifice else 1
        if options == ["Yes", "No"]:
            return 0 if braids_sacrifices else 1
        return next((i for i, o in enumerate(options) if o.startswith("Bear")), 0)  # Braids's controller sacrifices the Bear
    game, _ = table3(policy, policy, policy)
    a, b, c = game.seats
    braids = Permanent(BRAIDS)
    a.battlefield, a.library = [braids, Permanent(BEAR)], [FOREST] * 5
    b.battlefield, c.battlefield = [Permanent(x) for x in b_has], [Permanent(x) for x in c_has]
    fire(game, a, braids, "end_step")
    return game, a, b, c


class BraidsTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(BRAIDS), [])

    def test_an_opponent_who_sacrifices_a_creature_is_spared(self):
        game, a, b, c = end_step(True, [OGRE], [OGRE])
        self.assertEqual(([s.life for s in game.seats], len(a.hand), b.battlefield, c.battlefield), ([40, 40, 40], 0, [], []))

    def test_each_opponent_who_doesnt_loses_two_and_you_draw(self):
        game, a, b, c = end_step(False, [OGRE], [FOREST])  # C has no creature to sacrifice; B chooses not to
        self.assertEqual(([s.life for s in game.seats], len(a.hand), len(b.battlefield), len(c.battlefield)), ([40, 38, 38], 2, 1, 1))

    def test_an_opponent_with_nothing_of_that_type_cant_be_spared(self):
        game, a, b, c = end_step(True, [OGRE], [FOREST])  # both would sacrifice; C's Forest shares no type with the Bear
        self.assertEqual(([s.life for s in game.seats], len(a.hand), b.battlefield, len(c.battlefield)), ([40, 40, 38], 1, [], 1))

    def test_declining_does_nothing(self):
        game, a, b, c = end_step(False, [OGRE], [OGRE], braids_sacrifices=False)
        self.assertEqual(([s.life for s in game.seats], len(a.hand), len(a.battlefield)), ([40, 40, 40], 0, 2))


if __name__ == "__main__":
    unittest.main()
