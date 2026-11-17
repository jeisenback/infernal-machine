"""Issue #799: Fading N, "(This permanent enters with N fade counters on it. At the beginning of your upkeep, remove a fade counter from it.
If you can't, sacrifice it.)" (CR 702.32a), from the cards' real Oracle text. All eleven cards whose only gap it was are fully playable.
On Blastoderm (Fading 3): it enters with three fade counters, loses one each upkeep and is still there with none, and is sacrificed only
at the upkeep that finds none to remove (unlike vanishing, which sacrifices it as the last counter is removed)."""

import unittest

from tests.helpers import begin, enter, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Ancient Hydra", "Blastoderm", "Cloudskate", "Defender en-Vec", "Jolting Merfolk", "Phyrexian Prowler", "Rejuvenation Chamber",
         "Rusting Golem", "Skyshroud Behemoth", "Skyshroud Ridgeback", "Woodripper"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_fading).
MUTATIONS = [
    ("infernal_machine/effects/families/destroy_and_sacrifice.py", '        if target.counters.get("fade", 0) > 0:\n            game.remove_counters(target, "fade", 1)',
     '        if target.counters.get("fade", 0) > 1:\n            game.remove_counters(target, "fade", 1)', "sacrificed only when none is left to remove"),
    ("infernal_machine/effects/statics.py", '            add("fade", int(f[1]))', '            add("fade", int(f[1]) - 1)', "it enters with N fade counters"),
    ("infernal_machine/effects/triggers.py", "        if FADING.fullmatch(line):  # its fade counters", "        if False:  # its fade counters",
     "the upkeep trigger"),
]


class FadingTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_a_counter_each_upkeep_then_sacrificed_when_none_is_left(self):
        game, _ = table3()
        a = game.seats[0]
        blastoderm = enter(game, a, REAL["Blastoderm"])
        self.assertEqual(blastoderm.counters, {"fade": 3})
        for left in (2, 1, 0):
            begin(game, "upkeep", a)
            self.assertEqual((blastoderm.counters.get("fade", 0), blastoderm in a.battlefield), (left, True), left)
        begin(game, "upkeep", a)
        self.assertEqual((blastoderm in a.battlefield, [c.name for c in a.graveyard]), (False, ["Blastoderm"]))

    def test_not_at_an_opponents_upkeep(self):
        game, _ = table3()
        a, b, _ = game.seats
        blastoderm = enter(game, a, REAL["Blastoderm"])
        game.active = b.index
        begin(game, "upkeep", b)
        self.assertEqual(blastoderm.counters, {"fade": 3})


if __name__ == "__main__":
    unittest.main()
