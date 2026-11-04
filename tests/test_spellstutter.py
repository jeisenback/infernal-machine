""""When this creature enters, counter target spell with mana value X or less, where X is the number of Faeries you control."
(Spellstutter Sprite)."""

import unittest

from infernal_machine.effects import spell_effects
from infernal_machine.game import Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import enter, real, run_stack, table3

SPRITE = real("Spellstutter Sprite", "{1}{U}", "Creature — Faerie Wizard", "Flash\nFlying\nWhen this creature enters, counter target spell "
              "with mana value X or less, where X is the number of Faeries you control.", "1", "1")
FAERIE = real("Faerie Miscreant", "{U}", "Creature — Faerie Wizard", "Flying", "1", "1")
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.")
DIVINATION = real("Divination", "{2}{U}", "Sorcery", "Draw two cards.")


def stutter(spell, faeries):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(FAERIE) for _ in range(faeries)]
    item = StackItem(spell, b, spell_effects(spell), [])
    game.stack.append(item)
    enter(game, a, SPRITE)
    game._put_triggers_on_stack()
    return game, b, item


class SpellstutterSpriteTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(SPRITE), [])

    def test_it_counters_a_spell_up_to_its_faerie_count(self):
        game, b, item = stutter(DIVINATION, faeries=2)  # three Faeries with the Sprite
        run_stack(game)
        self.assertNotIn(item, game.stack)
        self.assertIn(DIVINATION, b.graveyard)

    def test_a_bigger_spell_is_no_target(self):
        game, b, item = stutter(DIVINATION, faeries=1)
        self.assertNotIn(item, game.stack[-1].targets)

    def test_fewer_faeries_by_resolution_means_no_counter(self):
        game, b, item = stutter(OPT, faeries=0)  # X is 1 as it goes on the stack
        game.seats[0].battlefield.clear()  # the Sprite is gone before the ability resolves: X is 0
        run_stack(game)
        self.assertNotIn(item, game.stack)
        self.assertEqual(len(b.hand), 1)  # Opt resolved


if __name__ == "__main__":
    unittest.main()
