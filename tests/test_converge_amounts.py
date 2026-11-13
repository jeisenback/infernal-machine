"""Converge amounts (CR 702.119 counts each color of mana spent), from the cards' real Oracle text: Painful Truths (draw X cards and lose X life)
and Crystalline Crawler (a +1/+1 counter for each color), cast with one color of mana and with several."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, PLAINS, SWAMP, real, run_stack, table3

TRUTHS = real("Painful Truths", "{2}{B}", "Sorcery", "Converge — You draw X cards and lose X life, where X is the number of colors of mana "
              "spent to cast this spell.", colors=("B",))
CRAWLER = real("Crystalline Crawler", "{4}", "Artifact Creature — Construct", "Converge — This creature enters with a +1/+1 counter on it for "
               "each color of mana spent to cast it.\nRemove a +1/+1 counter from this creature: Add one mana of any color.\n{T}: Put a +1/+1 "
               "counter on this creature.", "1", "1")
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))


def cast(card, land_cards):
    game, _ = table3()
    a = game.seats[0]
    a.battlefield, a.library, a.hand = [Permanent(c) for c in land_cards], [FOREST] * 5, [card]
    game._perform(a, CAST + card.name)
    run_stack(game)
    return game, a


class ConvergeAmountTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (TRUTHS, CRAWLER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_painful_truths_counts_the_colors_spent(self):
        for land_cards, x in (([SWAMP, SWAMP, SWAMP], 1), ([SWAMP, FOREST, PLAINS], 3)):
            game, a = cast(TRUTHS, land_cards)
            self.assertEqual((len(a.hand), a.life), (x, 40 - x), [c.name for c in land_cards])

    def test_crystalline_crawler_gets_a_counter_for_each_color(self):
        for land_cards, counters in (([FOREST] * 4, 1), ([FOREST, SWAMP, PLAINS, ISLAND], 4)):
            game, a = cast(CRAWLER, land_cards)
            crawler = next(p for p in a.battlefield if p.card is CRAWLER)
            self.assertEqual(crawler.counters.get("+1/+1"), counters, [c.name for c in land_cards])


if __name__ == "__main__":
    unittest.main()
