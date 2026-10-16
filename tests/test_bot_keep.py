"""Keeping or mulliganing an opening hand by the deck it is for (#394)."""

import unittest

from infernal_machine.bot import FEATURES, MAX_MULLIGANS, BotPlayer, keep_hand_for
from infernal_machine.cards import Card, Deck
from infernal_machine.game import KEEP_PROMPT
from tests.helpers import real

LAND = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
ONE = real("Spark", "{R}", "Instant", "Spark deals 1 damage to any target.")
TWO = real("Cheap Bear", "{1}{R}", "Creature — Bear", "", 2, 2)
FIVE = real("Big Drake", "{4}{R}", "Creature — Drake", "", 5, 5)


class KeepHandForTests(unittest.TestCase):
    def test_a_cheap_deck_keeps_two_lands_with_two_cheap_spells(self):
        self.assertTrue(keep_hand_for([LAND] * 2 + [ONE, TWO, FIVE, FIVE, FIVE], 2.0))

    def test_a_top_heavy_deck_does_not(self):
        self.assertFalse(keep_hand_for([LAND] * 2 + [ONE, TWO, FIVE, FIVE, FIVE], 4.0))

    def test_two_lands_and_only_one_cheap_spell_is_a_mulligan_even_for_a_cheap_deck(self):
        self.assertFalse(keep_hand_for([LAND] * 2 + [ONE, FIVE, FIVE, FIVE, FIVE], 2.0))

    def test_three_to_five_lands_are_kept_and_the_rest_are_not(self):
        spells = [FIVE] * 4
        self.assertEqual([keep_hand_for([LAND] * n + spells[:7 - n], 4.0) for n in range(0, 8)],
                         [False, False, False, True, True, True, False, False])

    def test_after_two_mulligans_anything_is_kept(self):
        self.assertTrue(keep_hand_for([LAND] * 7, 4.0, MAX_MULLIGANS))
        self.assertFalse(keep_hand_for([LAND] * 7, 4.0, MAX_MULLIGANS - 1))


class BotKeepTests(unittest.TestCase):
    def decision(self, deck_spells, hand, features=FEATURES):
        deck = Deck([], [LAND] * 36 + deck_spells, [])
        bot = BotPlayer("Bot", deck, features=features)
        bot.notify({"event": "opening_hand", "cards": [c.name for c in hand], "mulligans": 0})
        return bot.choose(KEEP_PROMPT, ["Keep", "Mulligan"])

    def test_the_bot_knows_what_its_deck_costs(self):
        hand = [LAND, LAND, ONE, TWO, FIVE, FIVE, FIVE]
        self.assertEqual(self.decision([ONE, TWO] * 12, hand), 0, "a cheap deck keeps it")
        self.assertEqual(self.decision([FIVE] * 24, hand), 1, "a top-heavy deck sends it back")

    def test_the_plain_bot_keeps_every_two_lander(self):
        hand = [LAND, LAND, FIVE, FIVE, FIVE, FIVE, FIVE]
        self.assertEqual(self.decision([FIVE] * 24, hand, features=FEATURES - {"keep"}), 0)
        self.assertEqual(self.decision([FIVE] * 24, hand), 1)


if __name__ == "__main__":
    unittest.main()
