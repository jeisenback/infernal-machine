""""Counter target instant spell." (Dispel)."""

import unittest

from infernal_machine.effects import spell_effects
from infernal_machine.game import CAST, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, DIVINATION, lands, run_stack, table3, real

DISPEL = real("Dispel", "{U}", "Instant", "Counter target instant spell.")
GROWTH = real("Giant Growth", "{G}", "Instant", "Target creature gets +3/+3 until end of turn.")


def answer(spell):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    game.stack.append(StackItem(spell, b, spell_effects(spell), []))
    a.hand, a.battlefield = [DISPEL], lands(1)
    return game, a, b


class DispelTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(DISPEL), [])

    def test_it_counters_an_instant(self):
        game, a, b = answer(GROWTH)
        game._perform(a, CAST + DISPEL.name)
        run_stack(game)
        self.assertIn(GROWTH, b.graveyard)

    def test_a_sorcery_or_creature_spell_is_no_target(self):
        for spell in (DIVINATION, BEAR):
            game, a, b = answer(spell)
            self.assertNotIn(CAST + DISPEL.name, game.legal_actions(a), spell.name)


if __name__ == "__main__":
    unittest.main()
