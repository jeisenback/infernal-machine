"""Keyword counters (CR 122.1b): a creature with a flying, indestructible or lifelink counter has that keyword, as Alchemist's Assistant,
Daring Fiendbonder and Season of the Burrow give."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import OGRE, Table, real, script, table3

WARD = real("Warding Mark", "{1}", "Sorcery", "Put an indestructible counter on target creature.")


class KeywordCounterTests(unittest.TestCase):
    def test_a_counter_gives_its_keyword(self):
        game, _ = table3()
        ogre = Permanent(OGRE)
        self.assertFalse(game.has_keyword(ogre, "flying"))
        ogre.counters["flying"] = 1
        self.assertTrue(game.has_keyword(ogre, "flying"))
        self.assertFalse(game.has_keyword(ogre, "lifelink"))

    def test_an_indestructible_counter_saves_it_from_destroy(self):
        game, _ = table3()
        a = game.seats[0]
        ogre = Permanent(OGRE)
        a.battlefield = [ogre]
        ogre.counters["indestructible"] = 1
        game.destroy(ogre)
        self.assertIn(ogre, a.battlefield)

    def test_a_spell_that_puts_the_counter_on(self):
        ogre = Permanent(OGRE)
        t = Table(WARD, mine=[ogre], n=1, policy=script("Ogre")).cast()
        self.assertEqual((ogre.counters, t.game.has_keyword(ogre, "indestructible")), ({"indestructible": 1}, True))


if __name__ == "__main__":
    unittest.main()
