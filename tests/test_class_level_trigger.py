""""When this Class becomes level 2, return target instant or sorcery card from your graveyard to your hand." (Stormchaser's Talent)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import activate, lands, pick, real, run_stack, table3

TALENT = Card(name="Stormchaser's Talent", mana_cost="{U}", cmc=1.0, type_line="Enchantment — Class",
              oracle_text="(Gain the next level as a sorcery to add its ability.)\nWhen this Class enters, create a 1/1 blue and red Otter "
                          "creature token with prowess.\n{3}{U}: Level 2\nWhen this Class becomes level 2, return target instant or "
                          "sorcery card from your graveyard to your hand.\n{5}{U}: Level 3\nWhenever you cast an instant or sorcery spell, "
                          "create a 1/1 blue and red Otter creature token with prowess.")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def table():
    game, _ = table3(pick())
    a = game.seats[0]
    talent = Permanent(TALENT)
    a.battlefield, a.hand, a.graveyard = lands(4), [], [BOLT]
    game._enter(a, talent)
    run_stack(game)
    return game, a, talent


class StormchasersTalentTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(TALENT), [])

    def test_level_two_returns_an_instant(self):
        game, a, talent = table()
        self.assertEqual(a.hand, [])
        activate(game, a, "Level 2")
        run_stack(game)
        self.assertEqual(talent.level, 2)
        self.assertEqual((a.hand, a.graveyard), ([BOLT], []))


if __name__ == "__main__":
    unittest.main()
