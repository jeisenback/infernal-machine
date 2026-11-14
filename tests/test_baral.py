"""Baral, Chief of Compliance, from its real Oracle text: "Whenever a spell or ability you control counters a spell, you may draw a
card. If you do, discard a card." Counterspell counters a spell: Baral loots. An opponent's counterspell, or a countered ability, does
not set it off."""

import unittest

from infernal_machine.effects import triggered_abilities
from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BOLT, FOREST, lands, real, run_stack, table3

BARAL = real("Baral, Chief of Compliance", "{1}{U}", "Legendary Creature — Human Wizard", "Instant and sorcery spells you cast cost {1} "
             "less to cast.\nWhenever a spell or ability you control counters a spell, you may draw a card. If you do, discard a card.",
             "1", "3", colors=("U",))
COUNTERSPELL = real("Counterspell", "{U}{U}", "Instant", "Counter target spell.", colors=("U",))


def countered_by(counterer_index):
    """Seat 1 casts a spell; the seat `counterer_index` counters it with Counterspell; seat 0 has Baral."""
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(BARAL)]
    a.library = [FOREST] * 3
    b.hand, b.battlefield = [BOLT], lands(1)
    game._perform(b, CAST + BOLT.name)
    counterer = game.seats[counterer_index]
    counterer.hand = [COUNTERSPELL]
    counterer.battlefield = counterer.battlefield + lands(2)
    game._perform(counterer, CAST + "Counterspell")
    run_stack(game)
    return game, a


class BaralTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(BARAL), [])

    def test_countering_a_spell_loots(self):
        game, a = countered_by(0)
        self.assertEqual((len(a.library), len(a.hand), [c.name for c in a.graveyard]), (2, 0, ["Counterspell", "Forest"]))

    def test_an_opponents_counterspell_does_not(self):
        game, a = countered_by(2)
        self.assertEqual((len(a.library), a.hand), (3, []))

    def test_countering_an_ability_does_not(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.battlefield, a.library = [Permanent(BARAL)], [FOREST] * 3
        ability = StackItem(BARAL, b, [], ability=triggered_abilities(BARAL)[0])
        game.stack.append(ability)
        game.resolving_item = StackItem(COUNTERSPELL, a)  # a spell of Baral's controller counters an ability
        game.counter(ability)
        game.resolving_item = None
        run_stack(game)
        self.assertEqual(len(a.library), 3)


if __name__ == "__main__":
    unittest.main()
