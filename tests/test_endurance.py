"""Endurance, from its real Oracle text: "When this creature enters, up to one target player puts all the cards from their graveyard on
the bottom of their library in a random order." The cards go under the library, the top stays where it was; with no target, nothing moves."""

import unittest

from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, enter, pick, real, run_stack, table3

ENDURANCE = real("Endurance", "{1}{G}{G}", "Creature — Elemental Incarnation", "Flash\nReach\nWhen this creature enters, up to one target "
                 "player puts all the cards from their graveyard on the bottom of their library in a random order.\nEvoke—Exile a green card "
                 "from your hand.", "3", "4", colors=("G",))


def enters(choice, offered=None):
    def policy(prompt, options):
        if offered is not None:
            offered.extend(options)
        return pick(choice)(prompt, options)
    game, _ = table3(policy)
    a, b = game.seats[0], game.seats[1]
    b.graveyard, b.library = [BEAR, OGRE], [FOREST]
    enter(game, a, ENDURANCE)
    run_stack(game)
    return b


class EnduranceTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(ENDURANCE), [])

    def test_the_target_players_graveyard_goes_under_their_library(self):
        b = enters("Player: B")
        self.assertEqual((b.graveyard, b.library[0].name, sorted(c.name for c in b.library[1:])), ([], "Forest", ["Bear", "Ogre"]))

    def test_with_no_target_nothing_moves(self):
        offered = []
        b = enters("No target", offered)
        self.assertEqual(("No target" in offered, [c.name for c in b.graveyard], len(b.library)), (True, ["Bear", "Ogre"], 1))


if __name__ == "__main__":
    unittest.main()
