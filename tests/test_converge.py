""""Converge — Exile target nonland permanent if its mana value is less than or equal to the number of colors of mana spent to cast this
spell." (Prismatic Ending)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects.common import colors_spent
from infernal_machine.game import CAST, X_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import PLAINS, real, run_stack, table3

ENDING = real("Prismatic Ending", "{X}{W}", "Sorcery", "Converge — Exile target nonland permanent if its mana value is less than or equal "
              "to the number of colors of mana spent to cast this spell.")
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
TWO_DROP = real("Bear Cub", "{1}{G}", "Creature — Bear", "", "2", "2")


def cast(*lands, x=1):
    def policy(prompt, options):
        if X_PROMPT.matches(prompt):
            return options.index(str(x))
        return next((i for i, o in enumerate(options) if o.startswith("Bear Cub")), 0)
    game, _ = table3(policy)
    a, b = game.seats[0], game.seats[1]
    cub = Permanent(TWO_DROP)
    a.hand, a.battlefield = [ENDING], [Permanent(card) for card in lands]
    b.battlefield = [cub]
    game._perform(a, CAST + ENDING.name)
    run_stack(game)
    return b, cub


class PrismaticEndingTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(ENDING), [])

    def test_two_colors_exile_a_two_drop(self):
        b, cub = cast(PLAINS, ISLAND)
        self.assertEqual(b.battlefield, [])
        self.assertIn(TWO_DROP, b.exile)

    def test_one_color_does_not(self):
        b, cub = cast(PLAINS, PLAINS)
        self.assertEqual(b.battlefield, [cub])


class ColorsSpentTests(unittest.TestCase):
    def test_each_mana_counts_as_one_color_it_could_be(self):
        self.assertEqual(colors_spent((frozenset("W"), frozenset("WU"))), 2)
        self.assertEqual(colors_spent((frozenset("W"), frozenset("W"))), 1)
        self.assertEqual(colors_spent((frozenset("C"), frozenset("WUBRG"))), 1)
        self.assertEqual(colors_spent((frozenset("WU"), frozenset("W"), frozenset("U"))), 2)

    def test_an_earlier_mana_is_counted_as_another_color_when_that_counts_more(self):
        for second in "WU":  # whichever color the first mana took, one of these needs it moved
            self.assertEqual(colors_spent((frozenset("WU"), frozenset(second))), 2, second)


if __name__ == "__main__":
    unittest.main()
