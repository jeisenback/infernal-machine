"""Gemstone Caverns, from its real Oracle text: "If this card is in your opening hand and you're not the starting player, you may begin
the game with Gemstone Caverns on the battlefield with a luck counter on it. If you do, exile a card from your hand." and "{T}: Add {C}.
If Gemstone Caverns has a luck counter on it, instead add one mana of any color." The starting player can't; without luck it makes {C}."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import ELF, real, table

CAVERNS = real("Gemstone Caverns", "", "Legendary Land", "If this card is in your opening hand and you're not the starting player, you may "
               "begin the game with Gemstone Caverns on the battlefield with a luck counter on it. If you do, exile a card from your hand.\n"
               "{T}: Add {C}. If Gemstone Caverns has a luck counter on it, instead add one mana of any color.")


class GemstoneCavernsTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(CAVERNS), [])

    def test_only_a_player_who_doesnt_start_begins_with_it_and_exiles_a_card(self):
        game, _, _ = table(library=(CAVERNS,) * 20)
        game.setup()
        starter = game.seats[game.starting_seat]
        other = next(s for s in game.seats if s is not starter)
        self.assertEqual((starter.battlefield, len(starter.hand)), ([], 7))
        self.assertTrue(other.battlefield and other.exile)
        self.assertEqual((len(other.battlefield) + len(other.exile) + len(other.hand), [p.counters for p in other.battlefield][0]),
                         (7, {"luck": 1}))

    def test_with_a_luck_counter_it_makes_any_color(self):
        for luck, castable in (({"luck": 1}, True), ({}, False)):
            game, _, _ = table()
            a = game.seats[0]
            a.battlefield, a.hand = [Permanent(CAVERNS, counters=dict(luck))], [ELF]
            self.assertEqual(CAST + ELF.name in game.legal_actions(a), castable, luck)


if __name__ == "__main__":
    unittest.main()
