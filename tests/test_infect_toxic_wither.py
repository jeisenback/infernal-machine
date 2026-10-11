"""Infect, Toxic N and Wither (#197, #213): poison counters for players, -1/-1 counters for creatures."""

import unittest

from infernal_machine.client import Narrator, render_board
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, creature, fight

PLAGUE = creature("Plague Myr", 3, 3, "Infect")
STING = creature("Sting", 2, 2, "Wither")
VENOM = creature("Venom", 2, 2, "Toxic 2")
DOUBLE_VENOM = creature("Double Venom", 2, 2, "Toxic 1, toxic 2")
VAMPIRE = creature("Vampire", 2, 2, "Infect, lifelink")
TITAN = creature("Titan", 4, 4)
BIG_INFECT = creature("Big Infect", 10, 10, "Infect")


def poison(seat):
    return seat.player_counters.get("poison", 0)


class InfectTests(unittest.TestCase):
    def test_infect_damage_to_a_player_is_poison_not_life_loss(self):
        game, a, b = fight([PLAGUE])
        self.assertEqual((b.life, poison(b)), (40, 3))

    def test_infect_damage_to_a_creature_is_minus_counters_not_damage(self):
        game, a, b = fight([PLAGUE], [TITAN], blocker_policy=lambda prompt, options: len(options) - 1)
        [titan] = b.battlefield
        self.assertEqual((titan.damage, titan.counters.get("-1/-1")), (0, 3))
        self.assertEqual(game.toughness(titan), 1)

    def test_enough_minus_counters_kill_the_creature(self):
        game, a, b = fight([PLAGUE], [OGRE], blocker_policy=lambda prompt, options: len(options) - 1)
        self.assertEqual(b.battlefield, [])  # 3/3 with three -1/-1 counters

    def test_a_blocked_infect_creature_does_not_poison_the_player(self):
        game, a, b = fight([PLAGUE], [BEAR], blocker_policy=lambda prompt, options: len(options) - 1)
        self.assertEqual((b.life, poison(b)), (40, 0))

    def test_ten_poison_counters_lose_the_game(self):
        game, a, b = fight([BIG_INFECT])
        self.assertEqual(poison(b), 10)
        self.assertTrue(b.lost)

    def test_nine_poison_counters_do_not(self):
        game, a, b = fight([PLAGUE])
        game.give_poison(b, 6)
        game._check_state()
        self.assertFalse(b.lost)
        game.give_poison(b, 1)
        game._check_state()
        self.assertTrue(b.lost)

    def test_infect_damage_that_is_not_combat_damage_poisons_too(self):
        game, a, b = fight([])
        game.damage(b, 4, source=Permanent(PLAGUE))
        self.assertEqual((b.life, poison(b)), (40, 4))

    def test_lifelink_still_gains_life_from_infect_damage(self):
        game, a, b = fight([VAMPIRE])
        self.assertEqual((a.life, b.life, poison(b)), (42, 40, 2))


class WitherTests(unittest.TestCase):
    def test_wither_damage_to_a_creature_is_minus_counters(self):
        game, a, b = fight([STING], [OGRE], blocker_policy=lambda prompt, options: len(options) - 1)
        [ogre] = b.battlefield
        self.assertEqual((ogre.damage, ogre.counters.get("-1/-1")), (0, 2))
        self.assertEqual(game.toughness(ogre), 1)

    def test_wither_damage_to_a_player_is_ordinary_life_loss(self):
        game, a, b = fight([STING])
        self.assertEqual((b.life, poison(b)), (38, 0))

    def test_a_creature_without_wither_still_marks_damage(self):
        game, a, b = fight([OGRE], [OGRE], blocker_policy=lambda prompt, options: len(options) - 1)
        self.assertEqual(b.battlefield, [])  # 3 damage on a 3/3
        self.assertEqual(a.battlefield, [])


class ToxicTests(unittest.TestCase):
    def test_toxic_gives_poison_in_addition_to_the_damage(self):
        game, a, b = fight([VENOM])
        self.assertEqual((b.life, poison(b)), (38, 2))

    def test_toxic_keywords_add_up(self):
        game, a, b = fight([DOUBLE_VENOM])
        self.assertEqual(poison(b), 3)

    def test_toxic_needs_combat_damage_to_the_player(self):
        game, a, b = fight([VENOM], [BEAR], blocker_policy=lambda prompt, options: len(options) - 1)
        self.assertEqual((b.life, poison(b)), (40, 0))
        game.damage(b, 2, source=a.battlefield[0] if a.battlefield else Permanent(VENOM))
        self.assertEqual(poison(b), 0)  # noncombat damage

    def test_the_view_shows_poison(self):
        game, a, b = fight([VENOM])
        self.assertEqual([s["poison"] for s in game.snapshot(None)["seats"]], [0, 2])


class DisplayTests(unittest.TestCase):
    def test_the_text_client_shows_poison(self):
        game, a, b = fight([VENOM])
        board = render_board(game.snapshot(None))
        self.assertIn("Poison counters: 2", board)
        self.assertNotIn("Poison counters: 0", board)
        narrator = Narrator()
        narrator.narrate({"event": "seat", "seat": 1, "name": "Bob", "life": 40, "commanders": []})
        self.assertEqual(narrator.narrate({"event": "poison", "seat": 1, "added": 2, "total": 2}),
                         "Bob gets 2 poison counters (2).")


class ReportTests(unittest.TestCase):
    def test_the_keywords_are_supported(self):
        for text in ("Infect", "Wither", "Toxic 2", "Flying, infect", "Trample, toxic 1",
                     "Infect (This creature deals damage to creatures in the form of -1/-1 counters.)"):
            with self.subTest(text):
                self.assertEqual(unsupported_lines(creature("Test", 1, 1, text)), [])


if __name__ == "__main__":
    unittest.main()
