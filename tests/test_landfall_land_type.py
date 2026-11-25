"""Landfall abilities that do more when the land that entered is a basic land type ("If that land is a Mountain, ..."), from the cards'
real Oracle text. All four are fully playable. Oran-Rief Hydra gets one +1/+1 counter for a land, two for a Forest; Akoum Hellkite
deals 1 damage to the Ogre, 2 for a Mountain; Guul Draz Overseer gives the Bear +1/+0, +2/+0 for a Swamp, and not itself; Koth, the
Geomancer deals 1 damage to each opponent and adds {R} only for a Mountain. The type is the land's that entered, not any land's."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import PLAY_LAND, Permanent
from tests.helpers import BEAR, FOREST, OGRE, SWAMP, choose, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Oran-Rief Hydra", "Akoum Hellkite", "Guul Draz Overseer", "Koth, the Geomancer"]
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))

# The guards these tests are there to catch (python tools/mutate.py tests.test_landfall_land_type).
MUTATIONS = [
    ("infernal_machine/game.py", "            subject = subject or (self.resolving_item.subject if self.resolving_item is not None else None)",
     "            pass", "the land that entered is looked at as it resolves"),
    ("infernal_machine/effects/families/counters.py", "game.amount(self.instead if more else self.count)", "game.amount(self.count)",
     "two counters for a Forest"),
    ("infernal_machine/effects/triggers.py", 'r"|\\bIf it is an? (?:Plains|Island|Swamp|Mountain|Forest),", re.I)',
     'r"|\\bIf it is an? (?:Plains|Island|Swamp|Mountain|Forest), you may return that nonland permanent card", re.I)',
     "the land in the condition is not what the ability acts on"),
    ("infernal_machine/effects/outcomes.py", "lambda previous, marker: IfElse(marker.condition, (replace(previous, modifier=marker.modifier),), (previous,))",
     "lambda previous, marker: replace(previous, modifier=marker.modifier)", "+2/+0 only for a Swamp"),
]


def landfall(name, land, theirs=()):
    """Seat 0 has `name` and a Bear and plays `land`; seat 1 has `theirs`. Seat 0 aims at seat 1's first permanent."""
    game, players = table3()
    a, b, _ = game.seats
    source, bear = Permanent(REAL[name], sick=False), Permanent(BEAR, sick=False)
    a.battlefield, a.hand = [source, bear], [land]
    b.battlefield = [Permanent(c) for c in theirs]
    players[0].policy = choose(game, *b.battlefield)
    game._perform(a, PLAY_LAND + land.name)
    run_stack(game)
    return game, a, b, source, bear


class LandfallLandTypeTests(unittest.TestCase):
    def test_every_card_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_two_counters_for_a_forest(self):
        _, _, _, hydra, _ = landfall("Oran-Rief Hydra", FOREST)
        self.assertEqual(hydra.counters.get("+1/+1"), 2)
        _, _, _, hydra, _ = landfall("Oran-Rief Hydra", MOUNTAIN)
        self.assertEqual(hydra.counters.get("+1/+1"), 1)

    def test_two_damage_for_a_mountain(self):
        _, _, b, _, _ = landfall("Akoum Hellkite", MOUNTAIN, theirs=[OGRE])
        self.assertEqual([p.damage for p in b.battlefield], [2])
        _, _, b, _, _ = landfall("Akoum Hellkite", FOREST, theirs=[OGRE])
        self.assertEqual([p.damage for p in b.battlefield], [1])

    def test_plus_two_for_a_swamp_and_not_itself(self):
        game, _, _, overseer, bear = landfall("Guul Draz Overseer", SWAMP)
        self.assertEqual((game.power(bear), game.power(overseer)), (4, 3))
        game, _, _, _, bear = landfall("Guul Draz Overseer", WASTES)
        self.assertEqual(game.power(bear), 3)

    def test_red_mana_only_for_a_mountain(self):
        game, a, b, _, _ = landfall("Koth, the Geomancer", MOUNTAIN)
        self.assertEqual((b.life, a.mana_pool), (39, [frozenset("R")]))
        game, a, b, _, _ = landfall("Koth, the Geomancer", FOREST)
        self.assertEqual((b.life, a.mana_pool), (39, []))

    def test_it_is_the_land_that_entered(self):
        game, _ = table3()
        a = game.seats[0]
        hydra = Permanent(REAL["Oran-Rief Hydra"], sick=False)
        a.battlefield, a.hand = [hydra, Permanent(FOREST)], [MOUNTAIN]  # (a Forest already there does not count)
        game._perform(a, PLAY_LAND + MOUNTAIN.name)
        run_stack(game)
        self.assertEqual(hydra.counters.get("+1/+1"), 1)


if __name__ == "__main__":
    unittest.main()
