"""Soulbond (CR 702.95) with Tandem Lookout: it pairs with another unpaired creature as either enters, and while paired both creatures
have "Whenever this creature deals damage to an opponent, draw a card." With Niv-Mizzet, Parun it is an infinite loop."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, FOREST, lands, pick, real, run_stack, table

LOOKOUT = real("Tandem Lookout", "{2}{U}", "Creature — Human Scout",
               "Soulbond (You may pair this creature with another unpaired creature when either enters. They remain paired for as long as you control both of them.)\n"
               "As long as Tandem Lookout is paired with another creature, each of those creatures has \"Whenever this creature deals damage to an opponent, draw a card.\"",
               "2", "1")
PARUN = real("Niv-Mizzet, Parun", "{U}{U}{U}{R}{R}{R}", "Legendary Creature — Dragon Wizard", "This spell can't be countered.\nFlying\n"
             "Whenever you draw a card, Niv-Mizzet deals 1 damage to any target.\nWhenever a player casts an instant or sorcery spell, you draw a card.",
             "5", "5")
OTHER = real("Hill Giant", "{3}{R}", "Creature — Giant", "", "3", "3")


def board(policy, *cards):
    game, _, _ = table(policy, library=(FOREST,) * 20)
    mine, theirs = game.seats
    mine.battlefield = [Permanent(card, sick=False) for card in cards]
    mine.library = [FOREST] * 80
    return game, mine, theirs


def pair_of(permanent):
    return permanent.paired.card.name if permanent.paired else None


class SoulbondTests(unittest.TestCase):
    def test_it_pairs_with_another_creature_as_it_enters(self):
        game, mine, theirs = board(pick("Bear"), BEAR)
        lookout = Permanent(LOOKOUT)
        game._enter(mine, lookout)
        self.assertEqual((pair_of(lookout), pair_of(mine.battlefield[0])), ("Bear", "Tandem Lookout"))

    def test_it_pairs_with_a_creature_that_enters_later(self):
        game, mine, theirs = board(pick("Bear"))
        lookout = Permanent(LOOKOUT)
        game._enter(mine, lookout)
        self.assertIsNone(lookout.paired)
        bear = Permanent(BEAR)
        game._enter(mine, bear)
        self.assertEqual(pair_of(lookout), "Bear")

    def test_it_may_decline(self):
        game, mine, theirs = board(pick("Don't pair"), BEAR)
        lookout = Permanent(LOOKOUT)
        game._enter(mine, lookout)
        self.assertIsNone(lookout.paired)

    def test_an_already_paired_creature_is_not_offered(self):
        game, mine, theirs = board(pick("Bear"), BEAR)
        first, second = Permanent(LOOKOUT), Permanent(LOOKOUT)
        game._enter(mine, first)
        game._enter(mine, second)
        self.assertEqual((pair_of(first), second.paired), ("Bear", None))

    def test_the_pair_ends_when_one_leaves(self):
        game, mine, theirs = board(pick("Bear"), BEAR)
        lookout = Permanent(LOOKOUT)
        game._enter(mine, lookout)
        game._leave_together([(mine.battlefield[0], "sacrificed")])
        game._check_state()
        self.assertIsNone(lookout.paired)

    def test_a_paired_creature_that_deals_damage_to_an_opponent_draws(self):
        game, mine, theirs = board(pick("Bear"), BEAR)
        game._enter(mine, Permanent(LOOKOUT))
        game.damage(theirs, 1, mine.battlefield[0])
        run_stack(game)
        self.assertEqual(len(mine.library), 79)

    def test_the_partner_that_is_not_the_lookout_draws_too_and_an_unpaired_creature_does_not(self):
        game, mine, theirs = board(pick("Bear"), BEAR, OTHER)
        game._enter(mine, Permanent(LOOKOUT))
        game.damage(theirs, 1, mine.battlefield[1])  # Hill Giant is not paired
        run_stack(game)
        self.assertEqual(len(mine.library), 80)

    def test_damage_to_you_or_to_a_creature_does_not_draw(self):
        game, mine, theirs = board(pick("Bear"), BEAR)
        game._enter(mine, Permanent(LOOKOUT))
        game.damage(mine, 1, mine.battlefield[0])
        game.damage(mine.battlefield[1], 1, mine.battlefield[0])
        run_stack(game)
        self.assertEqual(len(mine.library), 80)

    def test_with_nivmizzet_parun_it_draws_until_the_opponent_is_dead(self):
        game, mine, theirs = board(pick("Player: B"), PARUN)
        game._enter(mine, Permanent(LOOKOUT))
        game.draw(mine, 1)
        run_stack(game)
        game._check_state()
        self.assertTrue(theirs.lost)


if __name__ == "__main__":
    unittest.main()
