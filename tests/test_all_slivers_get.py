"""Issue #852: "All Sliver creatures get +N/+N." from the cards' real Oracle text. All seven cards whose only gap it was are fully
playable. Muscle Sliver (1/1, +1/+1) pumps itself and every player's Slivers, not their other creatures; with Sinew Sliver too, each
Sliver gets both. Thirteen cards whose only gap was "All Sliver creatures have <keyword>." are playable too: Winged Sliver gives every
player's Slivers flying, not a Bear."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Sinew Sliver", "Muscle Sliver", "Might Sliver", "Bonesplitter Sliver", "Blade Sliver", "Plated Sliver", "Watcher Sliver"]
GRANTING = ["Battering Sliver", "Fury Sliver", "Heart Sliver", "Horned Sliver", "Reflex Sliver", "Shadow Sliver", "Sidewinder Sliver",
            "Spinneret Sliver", "Spitting Sliver", "Synchronous Sliver", "Talon Sliver", "Two-Headed Sliver", "Winged Sliver"]  # ("All Sliver creatures have ...")
MUSCLE, SINEW = REAL["Muscle Sliver"], REAL["Sinew Sliver"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_all_slivers_get).
MUTATIONS = [
    ("infernal_machine/effects/statics.py", 'or who["tribe6"] or who["sub7"])', 'or who["tribe6"])', "every player's Slivers"),
    ("infernal_machine/effects/statics.py", 'who["sub5"] or who["sub7"] or who["subtokens"]', 'who["sub5"] or who["subtokens"]', "only Slivers"),
]


def size(game, permanent):
    return game.power(permanent), game.toughness(permanent)


class AllSliversGetTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)
        wording_unlocked(self, GRANTING)

    def test_a_keyword_goes_to_every_players_slivers(self):
        game, _ = table3()
        a, b, _ = game.seats
        winged, theirs, bear = Permanent(REAL["Winged Sliver"]), Permanent(SINEW), Permanent(BEAR)
        a.battlefield, b.battlefield = [winged, bear], [theirs]
        self.assertEqual([game.has_keyword(p, "flying") for p in (winged, theirs, bear)], [True, True, False])

    def test_it_pumps_every_players_slivers_and_not_their_other_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        muscle, theirs, bear = Permanent(MUSCLE), Permanent(SINEW), Permanent(BEAR)
        a.battlefield, b.battlefield = [muscle, bear], [theirs]
        self.assertEqual([size(game, p) for p in (muscle, theirs, bear)], [(3, 3), (3, 3), (2, 2)])  # (each Sliver: +1/+1 from both)

    def test_alone_it_pumps_itself(self):
        game, _ = table3()
        muscle = Permanent(MUSCLE)
        game.seats[0].battlefield = [muscle]
        self.assertEqual(size(game, muscle), (2, 2))


if __name__ == "__main__":
    unittest.main()
