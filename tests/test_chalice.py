""""Whenever a player casts a spell with mana value equal to the number of charge counters on this artifact, counter that spell."
(Chalice of the Void)."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, lands, real, run_stack, table3

CHALICE = real("Chalice of the Void", "{X}{X}", "Artifact", "This artifact enters with X charge counters on it.\nWhenever a player casts a "
               "spell with mana value equal to the number of charge counters on this artifact, counter that spell.")
DIVINATION = real("Divination", "{2}{U}", "Sorcery", "Draw two cards.")
GROWTH = real("Giant Growth", "{G}", "Instant", "Target creature gets +3/+3 until end of turn.")


def cast_into(spell, charge):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    chalice = Permanent(CHALICE)
    chalice.counters["charge"] = charge
    a.battlefield = [chalice]
    bear = Permanent(BEAR)
    b.battlefield, b.hand, b.library = [bear] + lands(3), [spell], [OGRE, OGRE, OGRE]
    game.active = 1
    game._perform(b, CAST + spell.name)
    run_stack(game)
    return game, b, bear


class ChaliceTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(CHALICE), [])

    def test_a_spell_of_that_mana_value_is_countered(self):
        game, b, bear = cast_into(GROWTH, 1)
        self.assertIn(GROWTH, b.graveyard)
        self.assertEqual(game.power(bear), 2)

    def test_another_mana_value_resolves(self):
        game, b, bear = cast_into(DIVINATION, 1)
        self.assertEqual(b.hand, [OGRE, OGRE])

    def test_with_no_counters_a_mana_value_1_spell_resolves(self):
        game, b, bear = cast_into(GROWTH, 0)
        self.assertEqual(game.power(bear), 5)


if __name__ == "__main__":
    unittest.main()
