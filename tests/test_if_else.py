""""If you control a Demon, each opponent loses 2 life and you gain 2 life. Otherwise, you lose 2 life." (Unholy Annex)."""

import unittest

from infernal_machine.effects.outcomes import _parse
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, fire, real, table3

ANNEX = real("Unholy Annex", "{2}{B}", "Enchantment — Room", "At the beginning of your end step, draw a card. If you control a Demon, each "
             "opponent loses 2 life and you gain 2 life. Otherwise, you lose 2 life.")
DEMON = real("Demon", "", "Token Creature — Demon", "Flying", "6", "6")


def end_step(*others):
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.library = [], [OGRE, OGRE]
    annex = Permanent(ANNEX)
    a.battlefield = [annex] + [Permanent(card) for card in others]
    fire(game, a, annex, "end_step")
    return game, a


class UnholyAnnexTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(ANNEX), [])

    def test_with_a_demon_it_drains_each_opponent(self):
        game, a = end_step(DEMON)
        self.assertEqual(a.hand, [OGRE])
        self.assertEqual([s.life for s in game.seats], [42, 38, 38])

    def test_without_a_demon_you_lose_2_life(self):
        game, a = end_step(OGRE)
        self.assertEqual(a.hand, [OGRE])
        self.assertEqual([s.life for s in game.seats], [38, 40, 40])

    def test_a_lone_otherwise_is_not_read(self):
        card = real("Lone", "{B}", "Sorcery", "Draw a card. Otherwise, you lose 2 life.")
        self.assertNotEqual(unsupported_lines(card), [])

    def test_a_targeted_effect_is_not_read(self):  # Horobi's Whisper: its target would be chosen whether or not you control a Swamp
        self.assertIsNone(_parse(["If you control a Swamp, destroy target nonblack creature."]))


if __name__ == "__main__":
    unittest.main()
