"""Lands whose mana costs a counter (issue #91): the Vivid lands ("{T}, Remove a charge counter: Add one mana of any color")
and the depletion lands ("{T}, Remove a depletion counter: Add {G}{G}. If there are no depletion counters, sacrifice it"),
each played from its real Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import pick, real, run_stack, Table, table3

ANY = ("B", "G", "R", "U", "W")

VIVID = Card(name="Vivid Creek", type_line="Land", produced_mana=ANY,
             oracle_text="This land enters tapped with two charge counters on it.\n{T}: Add {U}.\n"
                         "{T}, Remove a charge counter from this land: Add one mana of any color.")
WOODLOT = Card(name="Hickory Woodlot", type_line="Land", produced_mana=("G",),
               oracle_text="This land enters tapped with two depletion counters on it.\n{T}, Remove a depletion counter from this land: "
                           "Add {G}{G}. If there are no depletion counters on this land, sacrifice it.")
SPELLS = {c: real(f"{c} Draw", f"{{{c}}}", "Instant", "Draw a card.", colors=(c,)) for c in "WUBRG"}
ONE = real("One Draw", "{1}", "Instant", "Draw a card.")
GREEN_GREEN = real("Double Green", "{G}{G}", "Instant", "Draw a card.", colors=("G",))
ONE_GREEN_GREEN = real("Three Green", "{1}{G}{G}", "Instant", "Draw a card.", colors=("G",))


def land(card, counters):
    permanent = Permanent(card)
    if counters:
        permanent.counters[{"Vivid Creek": "charge", "Hickory Woodlot": "depletion"}[card.name]] = counters
    return permanent


def colors_it_pays(permanent):
    found = ""
    for color, spell in SPELLS.items():
        t = Table(spell, n=0, mine=[permanent])
        if any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a)):
            found += color
    return "".join(sorted(found))


def cast(spell, permanent):
    t = Table(spell, n=0, mine=[permanent])
    t.cast()
    return t


def enter(card):
    game, _ = table3(pick())
    a = game.seats[0]
    a.hand = [card]
    game._perform(a, PLAY_LAND + card.name)
    run_stack(game)
    return a.battlefield[0], a


class ParseTests(unittest.TestCase):
    def test_both_lands_are_fully_understood(self):
        for card in (VIVID, WOODLOT):
            with self.subTest(card=card.name):
                self.assertEqual(unsupported_lines(card), [])


class VividLandTests(unittest.TestCase):
    def test_it_enters_tapped_with_two_charge_counters(self):
        permanent, _ = enter(VIVID)
        self.assertEqual((permanent.tapped, permanent.counters), (True, {"charge": 2}))

    def test_with_counters_it_pays_for_any_color(self):
        self.assertEqual(colors_it_pays(land(VIVID, 2)), "BGRUW")

    def test_without_counters_it_makes_only_its_own_color(self):
        self.assertEqual(colors_it_pays(land(VIVID, 0)), "U")

    def test_another_color_costs_a_counter(self):
        t = cast(SPELLS["R"], land(VIVID, 2))
        self.assertEqual(t.a.battlefield[0].counters, {"charge": 1})
        self.assertTrue(t.a.battlefield[0].tapped)

    def test_its_own_color_costs_nothing(self):
        t = cast(SPELLS["U"], land(VIVID, 2))
        self.assertEqual(t.a.battlefield[0].counters, {"charge": 2})
        self.assertTrue(t.a.battlefield[0].tapped)

    def test_generic_mana_costs_nothing(self):
        t = cast(ONE, land(VIVID, 2))
        self.assertEqual(t.a.battlefield[0].counters, {"charge": 2})

    def test_the_last_counter_is_used_and_the_land_stays(self):
        t = cast(SPELLS["G"], land(VIVID, 1))
        permanent = t.a.battlefield[0]
        self.assertEqual(permanent.counters, {})
        self.assertIn(permanent, t.a.battlefield)
        permanent.tapped = False
        self.assertEqual(colors_it_pays(permanent), "U")

    def test_a_counter_is_used_per_tap_not_per_card(self):
        t = Table(real("Two", "{R}{1}", "Instant", "Draw a card.", colors=("R",)), n=0, mine=[land(VIVID, 2), Permanent(Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",)))])
        t.cast()
        self.assertEqual(t.a.battlefield[0].counters, {"charge": 2}, "the Mountain made the red; the Vivid land paid the generic")


class DepletionLandTests(unittest.TestCase):
    def test_it_enters_tapped_with_two_depletion_counters(self):
        permanent, _ = enter(WOODLOT)
        self.assertEqual((permanent.tapped, permanent.counters), (True, {"depletion": 2}))

    def test_it_makes_two_mana_of_its_color_for_a_counter(self):
        t = cast(GREEN_GREEN, land(WOODLOT, 2))
        permanent = t.a.battlefield[0]
        self.assertEqual((permanent.counters, permanent.tapped), ({"depletion": 1}, True))
        self.assertIn(permanent, t.a.battlefield)

    def test_one_mana_of_the_two_still_costs_the_counter(self):
        t = cast(SPELLS["G"], land(WOODLOT, 2))
        self.assertEqual(t.a.battlefield[0].counters, {"depletion": 1})

    def test_the_second_use_removes_the_last_counter_and_the_land_is_sacrificed(self):
        t = cast(GREEN_GREEN, land(WOODLOT, 1))
        self.assertEqual(t.a.battlefield, [])
        self.assertIn("Hickory Woodlot", [c.name for c in t.a.graveyard])

    def test_it_makes_only_its_own_color(self):
        self.assertEqual(colors_it_pays(land(WOODLOT, 2)), "G")

    def test_with_no_counters_it_makes_no_mana(self):
        self.assertEqual(colors_it_pays(land(WOODLOT, 0)), "")

    def test_one_tap_is_one_counter_even_for_three_mana(self):
        forest = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
        t = Table(ONE_GREEN_GREEN, n=0, mine=[land(WOODLOT, 2), Permanent(forest)])
        t.cast()
        self.assertEqual(t.a.battlefield[0].counters, {"depletion": 1})


if __name__ == "__main__":
    unittest.main()
