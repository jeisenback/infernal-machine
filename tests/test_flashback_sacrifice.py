"""Flashback whose cost is a sacrifice: "Flashback—Sacrifice a Mountain." (Lava Dart), "... three creatures." (Dread Return)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import GraveyardCast, graveyard_casts
from infernal_machine.game import CAST_GRAVEYARD, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, pick, real, run_stack, table3

DART = real("Lava Dart", "{R}", "Instant", "Lava Dart deals 1 damage to any target.\nFlashback—Sacrifice a Mountain. (You may cast this "
            "card from your graveyard for its flashback cost. Then exile it.)")
DREAD = real("Dread Return", "{2}{B}{B}", "Sorcery", "Return target creature card from your graveyard to the battlefield.\nFlashback—"
             "Sacrifice three creatures. (You may cast this card from your graveyard for its flashback cost. Then exile it.)")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))


def table(graveyard, battlefield, policy=None):
    game, _ = table3(policy)
    a = game.seats[0]
    a.hand, a.graveyard, a.exile = [], list(graveyard), []
    a.battlefield = [Permanent(card) for card in battlefield]
    return game, a


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (DART, DREAD):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_cost_is_read(self):
        self.assertEqual(graveyard_casts(DART), [GraveyardCast("Flashback", "{0}", exile_after=True, sacrifice="Mountain", sacrifices=1)])
        self.assertEqual(graveyard_casts(DREAD), [GraveyardCast("Flashback", "{0}", exile_after=True, sacrifice="creature", sacrifices=3)])


class LavaDartTests(unittest.TestCase):
    def test_it_sacrifices_a_mountain_and_is_exiled(self):
        game, a = table([DART], [MOUNTAIN, FOREST], pick("Player: B"))
        game._perform(a, CAST_GRAVEYARD + DART.name)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Forest"])
        self.assertEqual(game.seats[1].life, 39)
        self.assertEqual((a.graveyard, a.exile), ([MOUNTAIN], [DART]))

    def test_it_needs_a_mountain(self):
        game, a = table([DART], [FOREST, FOREST])
        self.assertNotIn(CAST_GRAVEYARD + DART.name, game.legal_actions(a))


class DreadReturnTests(unittest.TestCase):
    def test_it_sacrifices_three_creatures(self):
        game, a = table([DREAD, OGRE], [BEAR, BEAR, BEAR, BEAR])
        game._perform(a, CAST_GRAVEYARD + DREAD.name)
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Bear", "Ogre"])
        self.assertEqual(a.exile, [DREAD])

    def test_two_creatures_are_not_enough(self):
        game, a = table([DREAD, OGRE], [BEAR, BEAR, FOREST])
        self.assertNotIn(CAST_GRAVEYARD + DREAD.name, game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
