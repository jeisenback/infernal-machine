"""Nezahal, Primal Tide, from its real Oracle text: "Discard three cards: Exile Nezahal. Return it to the battlefield tapped under its
owner's control at the beginning of the next end step." Three cards are discarded; it is gone until the end step, then back tapped. With
two cards in hand it can't be done."""

import unittest

from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, activate, real, table3

NEZAHAL = real("Nezahal, Primal Tide", "{5}{U}{U}", "Legendary Creature — Elder Dinosaur", "This spell can't be countered.\nYou have no maximum "
               "hand size.\nWhenever an opponent casts a noncreature spell, draw a card.\nDiscard three cards: Exile Nezahal. Return it to the "
               "battlefield tapped under its owner's control at the beginning of the next end step.", "7", "7", colors=("U",))


def end_step(game):
    game.step = "end"
    due = [what for turn, what in game.at_end_step if turn <= game.turn]
    game.at_end_step = [(turn, what) for turn, what in game.at_end_step if turn > game.turn]
    for what in due:
        what()


def with_nezahal(hand):
    game, _ = table3()
    a = game.seats[0]
    a.battlefield, a.hand = [Permanent(NEZAHAL)], [FOREST] * hand
    return game, a


class NezahalTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(NEZAHAL), [])

    def test_it_is_exiled_and_returns_tapped_at_the_next_end_step(self):
        game, a = with_nezahal(3)
        activate(game, a, "Nezahal")
        self.assertEqual((a.battlefield, [c.name for c in a.exile], len(a.graveyard), a.hand), ([], ["Nezahal, Primal Tide"], 3, []))
        end_step(game)
        self.assertEqual(([p.card.name for p in a.battlefield], [p.tapped for p in a.battlefield], a.exile),
                         (["Nezahal, Primal Tide"], [True], []))

    def test_not_with_two_cards_in_hand(self):
        game, a = with_nezahal(2)
        self.assertFalse(any(x.startswith(ACTIVATE) and "Nezahal" in x for x in game.legal_actions(a)))


if __name__ == "__main__":
    unittest.main()
