"""Finale of Devastation, from its real Oracle text: "Search your library and/or graveyard for a creature card with mana value X or less
and put it onto the battlefield. If you search your library this way, shuffle. If X is 10 or more, creatures you control get +X/+X and gain
haste until end of turn." A card above X is not offered; a graveyard card can be taken; below 10 there is no pump."""

import unittest

from infernal_machine.effects import spell_effects
from infernal_machine.game import StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BIG, COMPARE_BEAR, FOREST, pick, real, table3

FINALE = real("Finale of Devastation", "{X}{G}{G}", "Sorcery", "Search your library and/or graveyard for a creature card with mana value X or "
              "less and put it onto the battlefield. If you search your library this way, shuffle. If X is 10 or more, creatures you control "
              "get +X/+X and gain haste until end of turn.", colors=("G",))


def finale(x, choice, library=(), graveyard=()):
    offered = []
    def policy(prompt, options):
        offered.extend(options)
        return pick(choice)(prompt, options)
    game, _ = table3(policy)
    a = game.seats[0]
    a.library, a.graveyard = list(library), list(graveyard)
    game._apply_effects(StackItem(FINALE, a, spell_effects(FINALE), x=x))
    return game, a, offered


class FinaleTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(FINALE), [])

    def test_from_the_library_only_mana_value_x_or_less(self):
        game, a, offered = finale(2, "Grizzly Bears", library=[BIG, COMPARE_BEAR, FOREST])
        self.assertEqual(("Big" in offered, [p.card.name for p in a.battlefield]), (False, ["Grizzly Bears"]))

    def test_from_the_graveyard(self):
        game, a, offered = finale(2, "Grizzly Bears (graveyard)", library=[FOREST, FOREST], graveyard=[COMPARE_BEAR])
        self.assertEqual(([p.card.name for p in a.battlefield], a.graveyard), (["Grizzly Bears"], []))

    def test_x_ten_or_more_pumps_and_hastes_your_creatures(self):
        for x, power in ((10, 12), (9, 2)):
            game, a, _ = finale(x, "Grizzly Bears", library=[COMPARE_BEAR])
            bear = a.battlefield[0]
            self.assertEqual((game.power(bear), game.has_keyword(bear, "haste")), (power, x >= 10), x)


if __name__ == "__main__":
    unittest.main()
