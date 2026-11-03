"""Returning or sacrificing lands instead of paying a spell's mana cost: "You may return an Island you control to its owner's hand
rather than pay this spell's mana cost." (Daze), "... two Islands ..." (Gush), "You may sacrifice two Mountains rather than pay this spell's
mana cost." (Fireblast)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import AlternativeCost, alternative_costs
from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, pick, real, run_stack, table3

DAZE = real("Daze", "{1}{U}", "Instant", "You may return an Island you control to its owner's hand rather than pay this spell's mana cost.\n"
            "Counter target spell unless its controller pays {1}.")
GUSH = real("Gush", "{4}{U}", "Instant", "You may return two Islands you control to their owner's hand rather than pay this spell's mana "
            "cost.\nDraw two cards.")
FIREBLAST = real("Fireblast", "{4}{R}{R}", "Instant", "You may sacrifice two Mountains rather than pay this spell's mana cost.\nFireblast "
                 "deals 4 damage to any target.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))


def table(hand, lands):
    game, _ = table3(pick("Return", "Sacrifice", "Player: B"))
    a = game.seats[0]
    a.hand, a.library = list(hand), [OGRE] * 5
    a.battlefield = [Permanent(card) for card in lands]
    return game, a


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (DAZE, GUSH, FIREBLAST):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_cost_is_read(self):
        self.assertEqual(alternative_costs(DAZE), [AlternativeCost("Return an Island", returns="Island", return_count=1)])
        self.assertEqual(alternative_costs(GUSH), [AlternativeCost("Return two Islands", returns="Island", return_count=2)])
        self.assertEqual(alternative_costs(FIREBLAST),
                         [AlternativeCost("Sacrifice two Mountains", returns="Mountain", return_count=2, sacrificed=True)])


class DazeTests(unittest.TestCase):
    def test_it_returns_an_island_and_counters_a_spell_its_controller_cannot_pay_for(self):
        game, a = table([DAZE], [ISLAND, FOREST])
        b = game.seats[1]
        spell = StackItem(BEAR, b, [], [])
        game.stack.append(spell)
        game._perform(a, CAST + DAZE.name)
        run_stack(game)
        self.assertEqual(a.hand, [ISLAND])
        self.assertEqual([p.card.name for p in a.battlefield], ["Forest"])
        self.assertIn(BEAR, b.graveyard)

    def test_it_needs_an_island(self):
        game, a = table([DAZE], [FOREST])
        game.stack.append(StackItem(BEAR, game.seats[1], [], []))
        self.assertNotIn(CAST + DAZE.name, game.legal_actions(a))


class GushTests(unittest.TestCase):
    def test_it_returns_two_islands_and_draws_two(self):
        game, a = table([GUSH], [ISLAND, ISLAND, ISLAND])
        game._perform(a, CAST + GUSH.name)
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.hand), ["Island", "Island", "Ogre", "Ogre"])
        self.assertEqual(len(a.battlefield), 1)

    def test_one_island_is_not_enough(self):
        game, a = table([GUSH], [ISLAND])
        self.assertNotIn(CAST + GUSH.name, game.legal_actions(a))


class FireblastTests(unittest.TestCase):
    def test_it_sacrifices_two_mountains_and_deals_4(self):
        game, a = table([FIREBLAST], [MOUNTAIN, MOUNTAIN, FOREST])
        game._perform(a, CAST + FIREBLAST.name)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Forest"])
        self.assertEqual(a.graveyard.count(MOUNTAIN), 2)
        self.assertEqual(game.seats[1].life, 36)

    def test_one_mountain_is_not_enough(self):
        game, a = table([FIREBLAST], [MOUNTAIN, FOREST])
        self.assertNotIn(CAST + FIREBLAST.name, game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
