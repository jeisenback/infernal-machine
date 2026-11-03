"""Searching for one of two kinds: Starfield Shepherd's "search your library for a basic Plains card or a creature card with mana value 1 or
less, reveal it, put it into your hand, then shuffle." and Gatecreeper Vine's "a basic land card or a Gate card"."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, PLAINS, pick, real, run_stack, table3

SHEPHERD = real("Starfield Shepherd", "{3}{W}{W}", "Creature — Angel", "Flying\nWhen this creature enters, search your library for a basic "
                "Plains card or a creature card with mana value 1 or less, reveal it, put it into your hand, then shuffle.\nWarp {1}{W} (You may "
                "cast this card from your hand for its warp cost. Exile this creature at the beginning of the next end step, then you may cast "
                "it from exile on a later turn.)", "3", "2")
VINE = real("Gatecreeper Vine", "{1}{G}", "Creature — Plant", "Defender\nWhen this creature enters, you may search your library for a "
            "basic land card or a Gate card, reveal it, put it into your hand, then shuffle.", "0", "2")
ONE_DROP = Card(name="One Drop", mana_cost="{W}", cmc=1.0, type_line="Creature — Soldier", power="1", toughness="1")
GATE = Card(name="Gate", type_line="Land — Gate")
THREE_DROP = Card(name="Three Drop", mana_cost="{2}{W}", cmc=3.0, type_line="Creature — Soldier", power="3", toughness="3")


def enters(card, library, *answers):
    game, _ = table3(pick(*answers))
    a = game.seats[0]
    a.hand, a.library = [], list(library)
    game._enter(a, Permanent(card))
    run_stack(game)
    return a


class SearchEitherKindTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SHEPHERD, VINE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_shepherd_finds_a_plains_or_a_one_drop_but_not_a_bigger_creature(self):
        self.assertEqual(enters(SHEPHERD, [OGRE, PLAINS], "Plains").hand, [PLAINS])
        self.assertEqual(enters(SHEPHERD, [OGRE, ONE_DROP], "One Drop").hand, [ONE_DROP])
        self.assertEqual(enters(SHEPHERD, [THREE_DROP], "Three Drop").hand, [])

    def test_vine_finds_a_gate(self):
        self.assertEqual(enters(VINE, [OGRE, GATE], "Yes", "Gate").hand, [GATE])


if __name__ == "__main__":
    unittest.main()
