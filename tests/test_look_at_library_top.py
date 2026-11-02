"""Mishra's Bauble: "{T}, Sacrifice this artifact: Look at the top card of target player's library. Draw a card at the beginning of the
next turn's upkeep." """

import unittest

from infernal_machine.report import unsupported_lines
from infernal_machine.game import Permanent
from tests.helpers import BEAR, OGRE, activate, pick, real, table3

BAUBLE = real("Mishra's Bauble", "{0}", "Artifact", "{T}, Sacrifice this artifact: Look at the top card of target player's library. Draw a "
              "card at the beginning of the next turn's upkeep.")


def table():
    game, players = table3(pick("Player: B"))
    a, b = game.seats[0], game.seats[1]
    a.hand, a.library = [], [OGRE, OGRE]
    b.library = [BEAR, OGRE]
    a.battlefield = [Permanent(BAUBLE)]
    return game, players[0], a, b


class MishrasBaubleTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(BAUBLE), [])

    def test_only_its_controller_sees_the_targeted_players_top_card(self):
        game, player, a, b = table()
        activate(game, a, "Mishra's Bauble")
        self.assertIn({"event": "library_top", "seat": b.index, "cards": ["Bear"]}, player.events)
        self.assertEqual(b.library, [BEAR, OGRE])  # it stays where it is
        self.assertFalse(any(e.get("event") == "library_top" for e in game.seats[1].player.events))
        self.assertEqual(a.battlefield, [])

    def test_the_draw_waits_for_the_next_upkeep(self):
        game, _, a, _ = table()
        activate(game, a, "Mishra's Bauble")
        self.assertEqual(a.hand, [])
        game.turn += 1
        game.step = "upkeep"
        game._turn_based_actions(game.seats[1])
        self.assertEqual(a.hand, [OGRE])


if __name__ == "__main__":
    unittest.main()
