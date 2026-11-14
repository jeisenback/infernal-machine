"""Discover (CR 701.57), with Pantlaza, Sun-Favored, a tracked deck's commander, from the real Oracle text: "Whenever Pantlaza or another
Dinosaur you control enters, you may discover X, where X is that creature's toughness. Do this only once each turn." The card found is cast
for free or put into the hand; a card with a greater mana value is passed over, and a non-Dinosaur sets nothing off."""

import unittest

from infernal_machine.game import DISCOVER_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, COMPARE_BEAR, FOREST, enter, real, run_stack, table3

PANTLAZA = real("Pantlaza, Sun-Favored", "{2}{R}{G}{W}", "Legendary Creature — Dinosaur", "Whenever Pantlaza or another Dinosaur you control "
                "enters, you may discover X, where X is that creature's toughness. Do this only once each turn. (Exile cards from the top of "
                "your library until you exile a nonland card with that mana value or less. Cast it without paying its mana cost or put it "
                "into your hand. Put the rest on the bottom in a random order.)", "4", "4", colors=("G", "R", "W"))
COLOSSADACTYL = real("Colossadactyl", "{2}{G}{G}", "Creature — Dinosaur", "Reach, trample", "4", "5", colors=("G",))
TRUMPETING = real("Trumpeting Carnosaur", "{4}{R}{R}", "Creature — Dinosaur", "Trample\nWhen this creature enters, discover 5.\n{2}{R}, "
                  "Discard this card: It deals 3 damage to target creature or planeswalker.", "6", "6", colors=("R",))


def playing(cast=True):
    """A table where seat 0 takes every "may" and casts the discovered card (or, with `cast` False, puts it into their hand)."""
    def answer(prompt, options):
        return (0 if cast else 1) if DISCOVER_PROMPT.matches(prompt) else 0
    game, _ = table3(answer)
    return game, game.seats[0]


class DiscoverTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (PANTLAZA, TRUMPETING):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_pantlaza_entering_discovers_four_and_casts_the_card_found(self):
        game, a = playing()
        a.library = [FOREST, BIG, COMPARE_BEAR, FOREST]  # the 5-drop is passed over: 4 is Pantlaza's toughness
        enter(game, a, PANTLAZA)
        run_stack(game)
        self.assertEqual(([p.card.name for p in a.battlefield], sorted(c.name for c in a.library), a.hand),
                         (["Pantlaza, Sun-Favored", "Grizzly Bears"], ["Big", "Forest", "Forest"], []))

    def test_a_card_not_cast_goes_to_the_hand(self):
        game, a = playing(cast=False)
        a.library = [FOREST, COMPARE_BEAR]
        enter(game, a, PANTLAZA)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.library], a.exile), (["Grizzly Bears"], ["Forest"], []))

    def test_x_is_the_toughness_of_the_dinosaur_that_entered(self):
        game, a = playing(cast=False)
        a.battlefield = [Permanent(PANTLAZA)]
        a.library = [BIG]
        enter(game, a, COLOSSADACTYL)  # toughness 5: the 5-drop is found
        run_stack(game)
        self.assertEqual([c.name for c in a.hand], ["Big"])

    def test_only_once_each_turn(self):
        game, a = playing(cast=False)
        a.library = [COMPARE_BEAR, BIG, COMPARE_BEAR]
        enter(game, a, PANTLAZA)
        run_stack(game)
        enter(game, a, COLOSSADACTYL)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], len(a.library)), (["Grizzly Bears"], 2))

    def test_a_non_dinosaur_sets_nothing_off(self):
        game, a = playing(cast=False)
        a.battlefield = [Permanent(PANTLAZA)]
        a.library = [COMPARE_BEAR]
        enter(game, a, BEAR)
        run_stack(game)
        self.assertEqual((a.hand, len(a.library)), ([], 1))

    def test_discover_with_no_card_small_enough_puts_everything_back(self):
        game, a = playing()
        a.library = [FOREST, BIG]
        game.discover(a, 4)
        self.assertEqual((sorted(c.name for c in a.library), a.hand, a.exile), (["Big", "Forest"], [], []))


if __name__ == "__main__":
    unittest.main()
