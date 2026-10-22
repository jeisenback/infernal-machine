"""The mana pieces of Kinnan's and Sisay's combos (#214, third slice): Bloom Tender and Faeburrow Elder ("For each color among
permanents you control, add one mana of that color."), Selvala, Heart of the Wilds (X mana by the greatest power, and her draw for the
biggest creature) and Jegantha, the Wellspring (mana that can't pay generic costs). Each card from its real Oracle text; the costs
and the creatures are probes."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, enter, real, run_stack, table3

BLOOM = real("Bloom Tender", "{1}{G}", "Creature — Elf Druid",
             "Vivid — {T}: For each color among permanents you control, add one mana of that color.", "1", "1", colors=("G",))
FAEBURROW = real("Faeburrow Elder", "{1}{G}{W}", "Creature — Treefolk Druid",
                 "Vigilance\nThis creature gets +1/+1 for each color among permanents you control.\n{T}: For each color among "
                 "permanents you control, add one mana of that color.", "0", "0", colors=("G", "W"))
SELVALA = real("Selvala, Heart of the Wilds", "{1}{G}{G}", "Legendary Creature — Elf Scout",
               "Whenever another creature enters, its controller may draw a card if its power is greater than each other creature's "
               "power.\n{G}, {T}: Add X mana in any combination of colors, where X is the greatest power among creatures you control.",
               "2", "3", colors=("G",))
JEGANTHA = real("Jegantha, the Wellspring", "{4}{R/G}", "Legendary Creature — Elemental Elk",
                "Companion — No card in your starting deck has more than one of the same mana symbol in its mana cost. (If this card is "
                "your chosen companion, you may put it into your hand from outside the game for {3} as a sorcery.)\n{T}: Add "
                "{W}{U}{B}{R}{G}. This mana can't be spent to pay generic mana costs.", "5", "5", colors=("G", "R"))

BLUE_ROCK = real("Blue Rock", "{U}", "Artifact", "", colors=("U",))
BEAST = real("Beast Probe", "{4}", "Creature — Beast", "", "5", "5")
SQUIRREL = real("Squirrel Probe", "{1}", "Creature — Squirrel", "", "1", "1")


def seat_with(*cards):
    game, _ = table3(None)
    a = game.seats[0]
    a.battlefield = [Permanent(c) for c in cards]
    return game, a


def made(game, seat):
    return sorted("".join(sorted(s.types)) for s in game._mana_sources(seat))


def payable(game, seat, cost):
    return game._payment(seat, Card(name="Probe", mana_cost=cost, type_line="Sorcery")) is not None


class ParseTests(unittest.TestCase):
    def test_every_line_is_read(self):
        for card in (BLOOM, FAEBURROW, SELVALA, JEGANTHA):
            self.assertEqual(unsupported_lines(card), [], card.name)


class EachColorTests(unittest.TestCase):
    def test_bloom_tender_alone_makes_its_own_green(self):
        game, a = seat_with(BLOOM)
        self.assertEqual(made(game, a), ["G"])

    def test_one_mana_of_each_color_among_your_permanents(self):
        game, a = seat_with(BLOOM, BLUE_ROCK)
        self.assertEqual(made(game, a), ["G", "U"])
        self.assertTrue(payable(game, a, "{G}{U}"))

    def test_an_opponents_permanents_do_not_count(self):
        game, a = seat_with(BLOOM)
        game.seats[1].battlefield = [Permanent(BLUE_ROCK)]
        self.assertEqual(made(game, a), ["G"])

    def test_faeburrow_elder_grows_with_the_colors_and_makes_them(self):
        game, a = seat_with(FAEBURROW)
        elder = a.battlefield[0]
        self.assertEqual((game.power(elder), game.toughness(elder)), (2, 2))
        self.assertEqual(made(game, a), ["G", "W"])
        a.battlefield.append(Permanent(BLUE_ROCK))
        self.assertEqual((game.power(elder), game.toughness(elder)), (3, 3))


class SelvalaManaTests(unittest.TestCase):
    def test_x_is_the_greatest_power_among_your_creatures(self):
        game, a = seat_with(SELVALA, BEAST, FOREST)
        self.assertTrue(payable(game, a, "{W}{U}{B}{R}{G}"))  # the Forest pays {G}; Selvala makes five, the Beast's power

    def test_with_only_her_own_power_she_makes_two(self):
        game, a = seat_with(SELVALA, FOREST)
        self.assertTrue(payable(game, a, "{W}{U}"))
        self.assertFalse(payable(game, a, "{W}{U}{B}"))

    def test_a_summoning_sick_selvala_makes_nothing(self):
        game, a = seat_with(SELVALA, BEAST, FOREST)
        a.battlefield[0].sick = True
        self.assertFalse(payable(game, a, "{W}{U}"))


class SelvalaDrawTests(unittest.TestCase):
    def setUp(self):
        self.asked = []

        def yes(prompt, options):
            self.asked.append(prompt)
            return 0
        self.game, _ = table3(None, yes)
        self.a, self.b = self.game.seats[0], self.game.seats[1]
        self.a.battlefield = [Permanent(SELVALA)]
        self.b.library = [FOREST] * 5

    def test_the_biggest_creature_entering_lets_its_controller_draw(self):
        enter(self.game, self.b, BEAST)
        run_stack(self.game)
        self.assertEqual(len(self.b.hand), 1)
        self.assertEqual(len(self.asked), 1)

    def test_a_creature_that_is_not_the_biggest_draws_nothing(self):
        enter(self.game, self.b, SQUIRREL)
        run_stack(self.game)
        self.assertEqual(self.b.hand, [])
        self.assertEqual(self.asked, [])

    def test_a_tie_is_not_greater(self):
        self.a.battlefield.append(Permanent(BEAST))
        enter(self.game, self.b, BEAST)
        run_stack(self.game)
        self.assertEqual(self.b.hand, [])


class JeganthaTests(unittest.TestCase):
    def test_it_pays_colored_symbols(self):
        game, a = seat_with(JEGANTHA)
        self.assertTrue(payable(game, a, "{W}{U}{B}{R}{G}"))

    def test_it_never_pays_generic_mana(self):
        game, a = seat_with(JEGANTHA)
        self.assertFalse(payable(game, a, "{1}"))
        game, a = seat_with(JEGANTHA, FOREST, FOREST)
        self.assertTrue(payable(game, a, "{2}{W}{U}"))
        self.assertFalse(payable(game, a, "{3}{W}{U}"))


if __name__ == "__main__":
    unittest.main()
