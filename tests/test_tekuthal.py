"""Tekuthal, Inquiry Dominus, from its real Oracle text: "{1}{U/P}{U/P}, Remove three counters from among other artifacts, creatures, and
planeswalkers you control: Put an indestructible counter on Tekuthal." Loyalty counts; Tekuthal's own counters and an enchantment's don't,
and with fewer than three it can't be activated."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, table3

TEKUTHAL = real("Tekuthal, Inquiry Dominus", "{2}{U}{U}", "Legendary Creature — Phyrexian Horror", "Flying\nIf you would proliferate, "
                "proliferate twice instead.\n{1}{U/P}{U/P}, Remove three counters from among other artifacts, creatures, and planeswalkers "
                "you control: Put an indestructible counter on Tekuthal. ({U/P} can be paid with either {U} or 2 life.)", "3", "5",
                colors=("U",))
WALKER = Card(name="Walker", type_line="Legendary Planeswalker — Test", loyalty="1")
SAGA = Card(name="Shrine", type_line="Enchantment", oracle_text="")


def table(*others):
    """Seat 0 controls Tekuthal, three lands and `others` (permanents)."""
    game, _ = table3()
    a = game.seats[0]
    tekuthal = Permanent(TEKUTHAL)
    a.battlefield = [tekuthal, *others] + lands(3)
    game.step, game.active = "main1", a.index
    return game, a, tekuthal


def offered(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE + "Tekuthal")]


class TekuthalTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(TEKUTHAL), [])

    def test_three_counters_among_others_pay_for_an_indestructible_counter(self):
        bear, walker = Permanent(BEAR, counters={"+1/+1": 2}), Permanent(WALKER, loyalty=1)
        game, a, tekuthal = table(bear, walker)
        (action,) = offered(game, a)
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((tekuthal.counters, bear.counters.get("+1/+1", 0), walker.loyalty), ({"indestructible": 1}, 0, 0))

    def test_fewer_than_three_or_the_wrong_ones_do_not(self):
        game, a, _ = table(Permanent(BEAR, counters={"+1/+1": 2}))
        self.assertEqual(offered(game, a), [])
        game, a, tekuthal = table(Permanent(BEAR, counters={"+1/+1": 2}))
        tekuthal.counters["+1/+1"] = 3
        self.assertEqual(offered(game, a), [])  # its own counters don't count
        game, a, _ = table(Permanent(BEAR, counters={"+1/+1": 2}), Permanent(SAGA, counters={"lore": 3}))
        self.assertEqual(offered(game, a), [])  # nor an enchantment's


if __name__ == "__main__":
    unittest.main()
