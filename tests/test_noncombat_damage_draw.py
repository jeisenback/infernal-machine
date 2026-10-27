"""Niv-Mizzet, Visionary: "Whenever a source you control deals noncombat damage to an opponent, you draw that many cards." With
Niv-Mizzet, Parun it is an infinite loop (a draw is one damage, one damage is a draw)."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, FOREST, lands, pick, real, run_stack, table

VISIONARY = real("Niv-Mizzet, Visionary", "{4}{U}{R}", "Legendary Creature — Dragon Wizard", "Flying\nYou have no maximum hand size.\n"
                 "Whenever a source you control deals noncombat damage to an opponent, you draw that many cards.", "6", "6")
PARUN = real("Niv-Mizzet, Parun", "{U}{U}{U}{R}{R}{R}", "Legendary Creature — Dragon Wizard", "This spell can't be countered.\nFlying\n"
             "Whenever you draw a card, Niv-Mizzet deals 1 damage to any target.\nWhenever a player casts an instant or sorcery spell, you draw a card.",
             "5", "5")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def board(*cards):
    game, _, _ = table(pick("Player: B"), library=(FOREST,) * 20)
    mine, theirs = game.seats
    mine.battlefield = [Permanent(card, sick=False) for card in cards]
    mine.library = [FOREST] * 80
    return game, mine, theirs


class NoncombatDamageDrawTests(unittest.TestCase):
    def test_a_spells_damage_draws_that_many_cards(self):
        game, mine, theirs = board(VISIONARY)
        mine.battlefield += lands(1)
        mine.hand = [BOLT]
        game._perform(mine, "Cast: Lightning Bolt")
        run_stack(game)
        self.assertEqual((theirs.life, len(mine.library)), (37, 77))

    def test_an_abilitys_damage_from_a_permanent_you_control_draws(self):
        game, mine, theirs = board(VISIONARY)
        game.damage(theirs, 2, mine.battlefield[0])
        run_stack(game)
        self.assertEqual(len(mine.library), 78)

    def test_with_nivmizzet_parun_it_draws_until_the_opponent_is_dead(self):
        game, mine, theirs = board(VISIONARY, PARUN)
        game.draw(mine, 1)
        run_stack(game)
        game._check_state()
        self.assertTrue(theirs.lost)

    def test_combat_damage_does_not_draw(self):
        game, mine, theirs = board(VISIONARY, BEAR)
        game.damage(theirs, 2, mine.battlefield[1], combat=True)
        run_stack(game)
        self.assertEqual(len(mine.library), 80)

    def test_damage_to_you_or_to_a_creature_does_not_draw(self):
        game, mine, theirs = board(VISIONARY, BEAR)
        game.damage(mine, 2, mine.battlefield[1])
        game.damage(mine.battlefield[1], 1, mine.battlefield[1])
        run_stack(game)
        self.assertEqual(len(mine.library), 80)

    def test_an_opponents_source_does_not_draw_for_you(self):
        game, mine, theirs = board(VISIONARY)
        theirs.battlefield = [Permanent(BEAR, sick=False)]
        game.damage(mine, 2, theirs.battlefield[0])
        run_stack(game)
        self.assertEqual(len(mine.library), 80)


if __name__ == "__main__":
    unittest.main()
