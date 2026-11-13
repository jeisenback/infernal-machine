"""Miracle (CR 702.94), from the cards' real Oracle text: the first card drawn in a turn may be cast for its miracle cost as it is drawn
(Temporal Mastery for {1}{U}, Entreat the Angels for {X}{W}{W}); a later draw, or a cost that can't be paid, leaves it in hand."""

import unittest

from infernal_machine.game import MIRACLE_PROMPT, X_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, lands, real, run_stack, table3

MASTERY = real("Temporal Mastery", "{5}{U}{U}", "Sorcery", "Take an extra turn after this one. Exile Temporal Mastery.\nMiracle {1}{U} (You may "
               "cast this card for its miracle cost when you draw it if it's the first card you drew this turn.)", colors=("U",))
ANGELS = real("Entreat the Angels", "{X}{X}{W}{W}{W}", "Sorcery", "Create X 4/4 white Angel creature tokens with flying.\nMiracle {X}{W}{W} (You "
              "may cast this card for its miracle cost when you draw it if it's the first card you drew this turn.)", colors=("W",))


def policy(prompt, options):
    """Cast a miracle; X as big as can be paid; otherwise the first option."""
    if MIRACLE_PROMPT.matches(prompt):
        return 0
    if X_PROMPT.matches(prompt):
        return len(options) - 1
    return 0


class MiracleTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (MASTERY, ANGELS):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_first_card_drawn_is_cast_for_its_miracle_cost(self):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield, a.library = lands(2), [MASTERY, FOREST]
        game.draw(a, 1)
        run_stack(game)
        self.assertEqual((MASTERY in a.hand, [c.name for c in a.exile], sum(p.tapped for p in a.battlefield)), (False, ["Temporal Mastery"], 2))

    def test_a_second_card_drawn_this_turn_is_no_miracle(self):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield, a.library = lands(2), [FOREST, MASTERY]
        game.draw(a, 2)
        run_stack(game)
        self.assertEqual((MASTERY in a.hand, a.exile), (True, []))

    def test_a_miracle_that_cannot_be_paid_for_stays_in_hand(self):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield, a.library = lands(1), [MASTERY]
        game.draw(a, 1)
        run_stack(game)
        self.assertEqual((MASTERY in a.hand, a.exile), (True, []))

    def test_entreat_the_angels_chooses_x_for_its_miracle_cost(self):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield, a.library = lands(4), [ANGELS]  # {X}{W}{W} with X = 2
        game.draw(a, 1)
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Angel" for p in a.battlefield), 2)


if __name__ == "__main__":
    unittest.main()
