"""Revel in Riches wins with ten Treasures; Mahadi, Old Gnawbone and Bootleggers' Stash make them (the Korvold cluster)."""

import unittest

from infernal_machine.effects.outcomes import TREASURE
from infernal_machine.game import Permanent
from tests.helpers import BEAR, OGRE, lands, real, table

REVEL = real("Revel in Riches", "{4}{B}", "Enchantment",
             "Whenever a creature an opponent controls dies, create a Treasure token. (It's an artifact with \"{T}, Sacrifice this token: Add one mana of any color.\")\n"
             "At the beginning of your upkeep, if you control ten or more Treasures, you win the game.")
MAHADI = real("Mahadi, Emporium Master", "{1}{B}{R}", "Legendary Creature — Devil",
              "At the beginning of your end step, create a Treasure token for each creature that died this turn. (It's an artifact with \"{T}, Sacrifice this token: Add one mana of any color.\")",
              "3", "3")
GNAWBONE = real("Old Gnawbone", "{5}{G}{G}", "Legendary Creature — Dragon",
                "Flying\nWhenever a creature you control deals combat damage to a player, create that many Treasure tokens.", "7", "7")
STASH = real("Bootleggers' Stash", "{5}{G}", "Artifact", "Lands you control have \"{T}: Create a Treasure token.\"")


def treasures(seat):
    return sum(p.card.name == "Treasure" for p in seat.battlefield)


def step(game, seat, name, permanent):
    game.step = name
    game.trigger(name, permanent, seat)
    game._priority_round(seat)


class RevelInRichesTests(unittest.TestCase):
    def test_ten_treasures_win_the_game_at_upkeep(self):
        game, _, _ = table()
        mine, theirs = game.seats
        revel = Permanent(REVEL)
        mine.battlefield = [revel]
        game.create_tokens(mine, TREASURE, 10)
        step(game, mine, "upkeep", revel)
        game._check_state()
        self.assertEqual((theirs.lost, game.winner() is mine), (True, True))

    def test_nine_do_not(self):
        game, _, _ = table()
        mine, theirs = game.seats
        revel = Permanent(REVEL)
        mine.battlefield = [revel]
        game.create_tokens(mine, TREASURE, 9)
        step(game, mine, "upkeep", revel)
        game._check_state()
        self.assertEqual((theirs.lost, game.winner()), (False, None))

    def test_a_creature_an_opponent_controls_dying_makes_a_treasure_and_your_own_does_not(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mine.battlefield = [Permanent(REVEL), Permanent(BEAR)]
        theirs.battlefield = [Permanent(OGRE)]
        game.destroy(theirs.battlefield[0])
        game._priority_round(mine)
        game.destroy(mine.battlefield[1])
        game._priority_round(mine)
        self.assertEqual(treasures(mine), 1)


class MahadiTests(unittest.TestCase):
    def test_a_treasure_for_each_creature_that_died_this_turn_whoever_controlled_it(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mahadi = Permanent(MAHADI)
        mine.battlefield = [mahadi, Permanent(BEAR)]
        theirs.battlefield = [Permanent(OGRE)]
        game.destroy(mine.battlefield[1])
        game.destroy(theirs.battlefield[0])
        step(game, mine, "end_step", mahadi)
        self.assertEqual(treasures(mine), 2)

    def test_none_when_nothing_died(self):
        game, _, _ = table()
        mine, _ = game.seats
        mahadi = Permanent(MAHADI)
        mine.battlefield = [mahadi]
        step(game, mine, "end_step", mahadi)
        self.assertEqual(treasures(mine), 0)


class OldGnawboneTests(unittest.TestCase):
    def test_a_treasure_for_each_point_of_combat_damage_a_creature_of_yours_deals(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mine.battlefield = [Permanent(GNAWBONE), Permanent(OGRE)]
        game.damage(theirs, 3, mine.battlefield[1], combat=True)
        game._priority_round(mine)
        self.assertEqual(treasures(mine), 3)

    def test_not_for_noncombat_damage_or_an_opponents_creature(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mine.battlefield = [Permanent(GNAWBONE), Permanent(OGRE)]
        theirs.battlefield = [Permanent(BEAR)]
        game.damage(theirs, 3, mine.battlefield[1], combat=False)
        game.damage(mine, 2, theirs.battlefield[0], combat=True)
        game._priority_round(mine)
        self.assertEqual(treasures(mine), 0)


class BootleggersStashTests(unittest.TestCase):
    def test_each_land_you_control_taps_for_a_treasure(self):
        game, _, _ = table()
        mine, _ = game.seats
        mine.battlefield = [Permanent(STASH), *lands(2)]
        options = [o for o in game.legal_actions(mine) if "Create a Treasure token" in o]
        self.assertEqual(len(options), 2)
        game._perform(mine, options[0])
        game._priority_round(mine)
        self.assertEqual(treasures(mine), 1)

    def test_a_creature_or_an_opponents_land_does_not_get_it(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mine.battlefield = [Permanent(STASH), Permanent(BEAR)]
        theirs.battlefield = lands(1)
        self.assertEqual([o for o in game.legal_actions(mine) if "Create a Treasure token" in o], [])
        self.assertEqual([o for o in game.legal_actions(theirs) if "Create a Treasure token" in o], [])


if __name__ == "__main__":
    unittest.main()
