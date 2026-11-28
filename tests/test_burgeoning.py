"""Burgeoning (#906 by EDHREC rank), from its real Oracle text: "Whenever an opponent plays a land, you may put a land card from your hand
onto the battlefield." An opponent playing a Forest lets its controller put a Forest from hand onto the battlefield (which is not a land
play: their own land drop is still there); its controller playing a land does nothing."""

import unittest

from infernal_machine.game import PLAY_LAND, Permanent
from tests.helpers import FOREST, run_stack, table3, wording_unlocked
from tests.real import REAL

BURGEONING = REAL["Burgeoning"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_burgeoning).
MUTATIONS = [
    ("infernal_machine/game.py", '        seat.lands_played += 1\n        self.happened("land_played", seat)', "        seat.lands_played += 1",
     "a land played is heard"),
]


def lands(seat):
    return sum(p.card.name == "Forest" for p in seat.battlefield)


class BurgeoningTests(unittest.TestCase):
    def test_it_is_playable(self):
        wording_unlocked(self, ["Burgeoning"])

    def test_an_opponents_land_drop(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield, a.hand = [Permanent(BURGEONING)], [FOREST, FOREST]
        b.hand = [FOREST]
        game.active = 1
        game._perform(b, PLAY_LAND + "Forest")
        run_stack(game)
        self.assertEqual((lands(a), len(a.hand), a.lands_played), (1, 1, 0))

    def test_not_its_controllers_own(self):
        game, _ = table3()
        a, _, _ = game.seats
        a.battlefield, a.hand = [Permanent(BURGEONING)], [FOREST, FOREST]
        game._perform(a, PLAY_LAND + "Forest")
        run_stack(game)
        self.assertEqual((lands(a), len(a.hand)), (1, 1))


if __name__ == "__main__":
    unittest.main()
