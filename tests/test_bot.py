import unittest

from infernal_machine.bot import BotPlayer, goldfish, keep_hand, worst_card
from infernal_machine.cards import Card, Deck
from infernal_machine.game import Game

LAND = Card(name="Wastes", type_line="Basic Land")
CHEAP = Card(name="Sol Ring", type_line="Artifact", cmc=1)
PRICEY = Card(name="Ulamog", type_line="Legendary Creature — Eldrazi", cmc=10)
COMMANDER = Card(name="Commander", type_line="Legendary Creature — Golem")


def deck(lands, spells):
    return Deck(commanders=[COMMANDER], main=[LAND] * lands + [CHEAP] * spells, sideboard=[])


class KeepTests(unittest.TestCase):
    def test_keeps_two_to_five_lands(self):
        self.assertFalse(keep_hand([LAND] + [CHEAP] * 6))
        self.assertTrue(keep_hand([LAND] * 2 + [CHEAP] * 5))
        self.assertTrue(keep_hand([LAND] * 5 + [CHEAP] * 2))
        self.assertFalse(keep_hand([LAND] * 6 + [CHEAP]))

    def test_keeps_anything_after_two_mulligans(self):
        self.assertTrue(keep_hand([CHEAP] * 7, mulligans=2))

    def test_worst_card(self):
        self.assertEqual(worst_card([LAND, CHEAP, PRICEY, CHEAP]), 2)
        self.assertEqual(worst_card([LAND, LAND, LAND, PRICEY]), 0)
        self.assertEqual(worst_card([LAND]), 0)


class BotPlayerTests(unittest.TestCase):
    def test_bots_play_a_game(self):
        # Land-heavy so no land drop is ever missed; the bots still mulligan 6+ land hands.
        a, b = BotPlayer("A", deck(90, 9)), BotPlayer("B", deck(90, 9))
        game = Game([(a, deck(90, 9)), (b, deck(90, 9))], seed=9)
        game.play(max_turns=6)
        for seat in game.seats:
            self.assertEqual(len(seat.battlefield), 3)  # one land per own turn
            self.assertLessEqual(len(seat.hand), 7)


class GoldfishTests(unittest.TestCase):
    def test_reproducible(self):
        self.assertEqual(goldfish(deck(37, 62), games=200, seed=1), goldfish(deck(37, 62), games=200, seed=1))

    def test_all_lands_hits_every_drop_and_mulligans_twice(self):
        stats = goldfish(deck(99, 0), games=50, turns=4)
        self.assertEqual(stats.land_drop_rate, {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0})
        self.assertEqual(stats.mulligan_rate, 1.0)
        self.assertEqual(stats.average_opening_lands, 6.0)  # kept at two mulligans, one bottomed

    def test_no_lands_misses_everything(self):
        stats = goldfish(deck(0, 99), games=20, turns=3)
        self.assertEqual(stats.land_drop_rate, {1: 0.0, 2: 0.0, 3: 0.0})

    def test_typical_commander_mana_base(self):
        stats = goldfish(deck(37, 62), games=2000, turns=4)
        self.assertLess(stats.mulligan_rate, 0.25)
        self.assertGreater(stats.land_drop_rate[3], stats.land_drop_rate[4])
        self.assertGreater(stats.land_drop_rate[1], 0.95)


if __name__ == "__main__":
    unittest.main()
