"""Karakas: "{T}: Return target legendary creature to its owner's hand." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, activate, real, table3

KARAKAS = real("Karakas", "", "Legendary Land", "{T}: Add {W}.\n{T}: Return target legendary creature to its owner's hand.")
LEGEND = Card(name="Legend", mana_cost="{2}", type_line="Legendary Creature — Elf", power="2", toughness="2")


def table(theirs):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(KARAKAS)]
    b.battlefield = [Permanent(card) for card in theirs]
    b.hand = []
    return game, a, b


class KarakasTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(KARAKAS), [])

    def test_it_returns_a_legendary_creature(self):
        game, a, b = table([LEGEND])
        activate(game, a, "Return target legendary creature")
        self.assertEqual((b.battlefield, b.hand), ([], [LEGEND]))

    def test_a_creature_that_is_not_legendary_is_not_a_target(self):
        game, a, _ = table([BEAR])
        self.assertFalse(any(x.startswith(ACTIVATE) and "Return target legendary" in x for x in game.legal_actions(a)))


if __name__ == "__main__":
    unittest.main()
