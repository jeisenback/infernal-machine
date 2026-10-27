"""Wrathful Raptors: "Whenever a Dinosaur you control is dealt damage, it deals that much damage to any target that isn't a Dinosaur." """

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, FOREST, OGRE, pick, real, run_stack, table

RAPTORS = real("Wrathful Raptors", "{4}{R}", "Creature — Dinosaur", "Trample\nWhenever a Dinosaur you control is dealt damage, it deals that much damage "
               "to any target that isn't a Dinosaur.", "5", "5")
RAPTOR = real("Pack Raptor", "{1}{R}", "Creature — Dinosaur", "", "1", "1")


def board(policy, mine_cards, theirs_cards=()):
    game, _, _ = table(policy, library=(FOREST,) * 20)
    mine, theirs = game.seats
    mine.battlefield = [Permanent(card, sick=False) for card in mine_cards]
    theirs.battlefield = [Permanent(card, sick=False) for card in theirs_cards]
    return game, mine, theirs


class WrathfulRaptorsTests(unittest.TestCase):
    def test_it_deals_the_damage_its_dinosaur_was_dealt_to_the_target(self):
        game, mine, theirs = board(pick("Player: B"), [RAPTORS], [OGRE])
        game.damage(mine.battlefield[0], 3, theirs.battlefield[0])
        run_stack(game)
        self.assertEqual(theirs.life, 37)

    def test_any_dinosaur_you_control_sets_it_off(self):
        game, mine, theirs = board(pick("Player: B"), [RAPTORS, RAPTOR], [OGRE])
        game.damage(mine.battlefield[1], 2, theirs.battlefield[0])
        run_stack(game)
        self.assertEqual(theirs.life, 38)

    def test_a_dinosaur_that_died_of_the_damage_still_deals_it(self):
        game, mine, theirs = board(pick("Player: B"), [RAPTORS, RAPTOR], [OGRE])
        game.damage(mine.battlefield[1], 4, theirs.battlefield[0])
        game._check_state()
        run_stack(game)
        self.assertEqual((theirs.life, len(mine.battlefield)), (36, 1))

    def test_a_dinosaur_is_not_offered_as_the_target(self):
        offered = []

        def policy(prompt, options):
            offered.extend(options)
            return pick("Player: B")(prompt, options)
        game, mine, theirs = board(policy, [RAPTORS], [OGRE, RAPTOR])
        game.damage(mine.battlefield[0], 1, theirs.battlefield[0])
        run_stack(game)
        self.assertTrue(any(o.startswith("Ogre") for o in offered))
        self.assertFalse(any(o.startswith(("Pack Raptor", "Wrathful Raptors")) for o in offered))

    def test_a_creature_that_is_not_a_dinosaur_does_not_set_it_off(self):
        game, mine, theirs = board(pick("Player: B"), [RAPTORS, BEAR], [OGRE])
        game.damage(mine.battlefield[1], 1, theirs.battlefield[0])
        run_stack(game)
        self.assertEqual(theirs.life, 40)

    def test_an_opponents_dinosaur_does_not_set_it_off(self):
        game, mine, theirs = board(pick("Player: B"), [RAPTORS], [OGRE, RAPTOR])
        game.damage(theirs.battlefield[1], 1, mine.battlefield[0])
        run_stack(game)
        self.assertEqual(theirs.life, 40)


if __name__ == "__main__":
    unittest.main()
