"""A state trigger (CR 603.8), from the cards' real Oracle text: "When you control no Islands, sacrifice this creature." (Dandân) triggers
whenever its controller controls no Island, once until it resolves, and not while they control one. Gorilla Pack counts Forests."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, real, run_stack, table3

DANDAN = real("Dandân", "{U}{U}", "Creature — Fish", "This creature can't attack unless defending player controls an Island.\nWhen you "
              "control no Islands, sacrifice this creature.", "4", "1", colors=("U",))
GORILLAS = real("Gorilla Pack", "{2}{G}", "Creature — Ape", "This creature can't attack unless defending player controls a Forest.\nWhen you "
                "control no Forests, sacrifice this creature.", "3", "3", colors=("G",))
ISLAND = real("Island", "", "Basic Land — Island", "")


def checked(*cards):
    game, _ = table3()
    a = game.seats[0]
    a.battlefield = [Permanent(c) for c in cards]
    game._check_state()
    return game, a


class StateTriggerTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (DANDAN, GORILLAS):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_with_no_island_it_triggers_once_and_is_sacrificed(self):
        game, a = checked(DANDAN, FOREST)
        game._check_state()  # still no Island, but it already triggered
        self.assertEqual(len(game.pending), 1)
        run_stack(game)
        self.assertEqual(([p.card.name for p in a.battlefield], [c.name for c in a.graveyard]), (["Forest"], ["Dandân"]))

    def test_with_an_island_nothing_happens(self):
        game, a = checked(DANDAN, ISLAND)
        self.assertEqual((game.pending, len(a.battlefield)), ([], 2))

    def test_not_while_it_has_lost_its_abilities(self):
        game, _ = table3()
        a = game.seats[0]
        dandan, keeper = Permanent(DANDAN), Permanent(FOREST)
        dandan.loses_abilities_while = keeper  # as The Wondrous Wasp's "for as long as" leaves it: no abilities while that stays
        a.battlefield, game.seats[1].battlefield = [dandan], [keeper]
        game._check_state()
        self.assertEqual(game.pending, [])

    def test_gorilla_pack_counts_forests(self):
        self.assertEqual(checked(GORILLAS, FOREST)[0].pending, [])
        self.assertEqual(len(checked(GORILLAS, ISLAND)[0].pending), 1)


if __name__ == "__main__":
    unittest.main()
