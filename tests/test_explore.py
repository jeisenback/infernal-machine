""""When this creature enters, create a Map token." (Spyglass Siren) and the Map's "{1}, {T}, Sacrifice this token: Target creature you
control explores. Activate only as a sorcery." (CR 701.44)."""

import unittest

from infernal_machine.effects.outcomes import MAP
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, activate, enter, lands, pick, real, run_stack, table3

SIREN = real("Spyglass Siren", "{U}", "Creature — Siren Pirate", "Flying\nWhen this creature enters, create a Map token. (It's an artifact "
             "with \"{1}, {T}, Sacrifice this token: Target creature you control explores. Activate only as a sorcery.\")", "1", "1")


def table(top, *answers):
    game, _ = table3(pick(*answers, "Bear"))
    a = game.seats[0]
    bear = Permanent(BEAR)
    a.hand, a.graveyard, a.library = [], [], [top, OGRE]
    a.battlefield = [bear, Permanent(MAP)] + lands(1)
    return game, a, bear


class SpyglassSirenTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SIREN), [])

    def test_it_creates_a_map(self):
        game, _ = table3()
        a = game.seats[0]
        enter(game, a, SIREN)
        run_stack(game)
        self.assertIn("Map", [p.card.name for p in a.battlefield])


class ExploreTests(unittest.TestCase):
    def test_a_land_goes_to_the_hand(self):
        game, a, bear = table(FOREST)
        activate(game, a, "Map")
        self.assertEqual(a.hand, [FOREST])
        self.assertEqual(bear.counters.get("+1/+1", 0), 0)
        self.assertNotIn("Map", [p.card.name for p in a.battlefield])

    def test_a_nonland_card_gives_a_counter_and_may_go_to_the_graveyard(self):
        game, a, bear = table(OGRE, "Put into your graveyard")
        activate(game, a, "Map")
        self.assertEqual(bear.counters.get("+1/+1"), 1)
        self.assertEqual((a.hand, a.graveyard[-1:], a.library), ([], [OGRE], [OGRE]))

    def test_or_stay_on_top(self):
        game, a, bear = table(BEAR, "Keep on top")
        activate(game, a, "Map")
        self.assertEqual(bear.counters.get("+1/+1"), 1)
        self.assertEqual(a.library, [BEAR, OGRE])

    def test_an_empty_library_still_gives_a_counter(self):
        game, a, bear = table(OGRE)
        a.library = []
        activate(game, a, "Map")
        self.assertEqual(bear.counters.get("+1/+1"), 1)


if __name__ == "__main__":
    unittest.main()
