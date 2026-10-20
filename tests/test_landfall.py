"""Landfall wordings (issue #427): "you may have this creature deal ...", "can attack this turn as though it didn't have defender" and a
land that becomes a creature, from the real cards."""

import unittest

from infernal_machine.game import PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, pick, real, run_stack, table3

SQUID = real("Skyclave Squid", "{1}{U}", "Creature — Squid", "Defender\nLandfall — Whenever a land you control enters, this creature can attack this turn as though it didn't have defender.", "3", "2")
RAVAGER = real("Cosi's Ravager", "{3}{R}", "Creature — Elemental", "Landfall — Whenever a land you control enters, you may have this creature deal 1 damage to target player or planeswalker.", "2", "2")
FURY = real("Embodiment of Fury", "{3}{R}", "Creature — Elemental", "Trample\nLand creatures you control have trample.\nLandfall — Whenever a land you control enters, you may have target land you control become a 3/3 Elemental creature with haste until end of turn. It's still a land.", "4", "3")


def land_enters(game, seat):
    seat.hand = [FOREST]
    game._perform(seat, PLAY_LAND + "Forest")
    run_stack(game)


class DefenderTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SQUID), [])

    def test_a_defender_cannot_attack_until_a_land_enters(self):
        game, _ = table3()
        a = game.seats[0]
        squid = Permanent(SQUID, sick=False)
        a.battlefield = [squid]
        self.assertFalse(game.combat._can_attack(squid))
        land_enters(game, a)
        self.assertTrue(game.combat._can_attack(squid))

    def test_it_lasts_only_this_turn(self):
        game, _ = table3()
        a = game.seats[0]
        squid = Permanent(SQUID, sick=False)
        a.battlefield = [squid]
        land_enters(game, a)
        game.turn += 1
        self.assertFalse(game.combat._can_attack(squid))

    def test_another_players_land_does_not_help(self):
        game, _ = table3()
        a, b, _ = game.seats
        squid = Permanent(SQUID, sick=False)
        a.battlefield = [squid]
        land_enters(game, b)
        self.assertFalse(game.combat._can_attack(squid))

    def test_a_creature_without_defender_is_not_changed(self):
        game, _ = table3()
        bear = Permanent(BEAR, sick=False)
        game.seats[0].battlefield = [bear]
        self.assertTrue(game.combat._can_attack(bear))


class MayHaveTests(unittest.TestCase):
    def test_both_cards_are_understood(self):
        for card in (RAVAGER, FURY):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_player_takes_the_damage_when_you_say_yes(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.battlefield = [Permanent(RAVAGER)]
        before = [s.life for s in game.seats]
        land_enters(game, a)
        self.assertEqual(sum(before) - sum(s.life for s in game.seats), 1)

    def test_nothing_happens_when_you_decline(self):
        game, _ = table3(pick("No"))
        a = game.seats[0]
        a.battlefield = [Permanent(RAVAGER)]
        before = [s.life for s in game.seats]
        land_enters(game, a)
        self.assertEqual([s.life for s in game.seats], before)

    def test_a_land_becomes_a_creature_until_end_of_turn_and_is_still_a_land(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.battlefield = [Permanent(FURY)]
        land_enters(game, a)
        land = next(p for p in a.battlefield if p.card.name == "Forest")
        self.assertEqual((game.power(land), game.toughness(land)), (3, 3))
        self.assertTrue(game.has_keyword(land, "haste"))
        self.assertIn("Land", land.card.type_line)

    def test_declining_leaves_the_land_alone(self):
        game, _ = table3(pick("No"))
        a = game.seats[0]
        a.battlefield = [Permanent(FURY)]
        land_enters(game, a)
        land = next(p for p in a.battlefield if p.card.name == "Forest")
        self.assertNotEqual(game.power(land), 3)


if __name__ == "__main__":
    unittest.main()
