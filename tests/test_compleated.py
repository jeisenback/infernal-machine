"""Compleated (#424): a Phyrexian mana symbol in a planeswalker's cost may be paid with 2 life, and for each one paid that way the
walker enters with two fewer loyalty counters (CR 702.150). Played from the cards' real Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, pick, real, settle, table


def walker(name, cost, text, loyalty, colors):
    return Card(**{**real(name, cost, "Legendary Planeswalker — " + name.split(",")[0], text, colors=colors).__dict__, "loyalty": loyalty})


VRASKA = walker("Vraska, Betrayal's Sting", "{4}{B}{B/P}",
                "Compleated ({B/P} can be paid with {B} or 2 life. If life was paid, this planeswalker enters with two fewer loyalty "
                "counters.)\n"
                "0: You draw a card and lose 1 life. Proliferate.\n"
                "−2: Target creature becomes a Treasure artifact with \"{T}, Sacrifice this artifact: Add one mana of any color\" and loses "
                "all other card types and abilities.\n"
                "−9: If target player has fewer than nine poison counters, they get a number of poison counters equal to the difference.",
                "6", ("B",))
NISSA = walker("Nissa, Ascended Animist", "{3}{G}{G}{G/P}{G/P}",
               "Compleated ({G/P} can be paid with {G} or 2 life. For each {G/P} paid with life, this planeswalker enters with two fewer "
               "loyalty counters.)\n"
               "+1: Create an X/X green Phyrexian Horror creature token, where X is Nissa's loyalty.\n"
               "−1: Destroy target artifact or enchantment.\n"
               "−7: Until end of turn, creatures you control get +1/+1 for each Forest you control and gain trample.", "7", ("G",))


def cast(card, land_count):
    game, _, _ = table(pick(CAST))
    seat = game.seats[0]
    seat.battlefield = lands(land_count)
    seat.hand = [card]
    settle(game)
    walker = next((p for p in seat.battlefield if p.card is card), None)
    return seat, walker


class CompleatedTests(unittest.TestCase):
    def test_the_keyword_line_is_read(self):
        self.assertNotIn("Compleated", unsupported_lines(VRASKA))
        self.assertNotIn("Compleated", unsupported_lines(NISSA))

    def test_paying_the_phyrexian_symbol_with_life_costs_two_loyalty(self):
        seat, vraska = cast(VRASKA, 5)  # {4}{B} from the lands; {B/P} with 2 life
        self.assertEqual((seat.life, vraska.loyalty), (38, 4))

    def test_paying_it_with_mana_keeps_the_loyalty(self):
        seat, vraska = cast(VRASKA, 6)
        self.assertEqual((seat.life, vraska.loyalty), (40, 6))

    def test_two_symbols_paid_with_life_cost_four(self):
        seat, nissa = cast(NISSA, 5)  # {3}{G}{G} from the lands; both {G/P} with life
        self.assertEqual((seat.life, nissa.loyalty), (36, 3))

    def test_one_of_two_symbols_paid_with_life_costs_two(self):
        seat, nissa = cast(NISSA, 6)
        self.assertEqual((seat.life, nissa.loyalty), (38, 5))


if __name__ == "__main__":
    unittest.main()
