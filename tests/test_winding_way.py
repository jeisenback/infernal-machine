""""Choose creature or land. Reveal the top four cards of your library. Put all cards of the chosen type revealed this way into your hand
and the rest into your graveyard." (Winding Way)."""

import unittest

from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, lands, pick, real, run_stack, table3

WINDING = real("Winding Way", "{1}{G}", "Sorcery", "Choose creature or land. Reveal the top four cards of your library. Put all cards of the "
               "chosen type revealed this way into your hand and the rest into your graveyard.")
RING = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")


def cast(choice):
    game, _ = table3(pick(choice))
    a = game.seats[0]
    a.hand, a.battlefield, a.graveyard, a.library = [WINDING], lands(2), [], [BEAR, FOREST, OGRE, RING, FOREST]
    game._perform(a, CAST + WINDING.name)
    run_stack(game)
    return a


class WindingWayTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(WINDING), [])

    def test_creatures(self):
        a = cast("Creature")
        self.assertEqual(sorted(c.name for c in a.hand), ["Bear", "Ogre"])
        self.assertEqual(sorted(c.name for c in a.graveyard if c is not WINDING), ["Forest", "Sol Ring"])
        self.assertEqual(a.library, [FOREST])

    def test_lands(self):
        a = cast("Land")
        self.assertEqual([c.name for c in a.hand], ["Forest"])


if __name__ == "__main__":
    unittest.main()
