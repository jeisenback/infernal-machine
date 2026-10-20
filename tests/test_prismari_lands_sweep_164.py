"""The ten Prismari lands of the precon decks (issue #164), each played from its real Oracle text: how it comes in
(tapped or untapped, with a case on each side of the line), the mana it makes really pays for a spell, and the extra
abilities do what they say."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, CYCLE, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, lands, pick, PLAINS, real, run_stack, Table, table3

ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
BLUE = real("Blue Draw", "{U}", "Instant", "Draw a card.", colors=("U",))
RED = real("Red Draw", "{R}", "Instant", "Draw a card.", colors=("R",))
BLUE_BLUE = real("Double Blue", "{U}{U}", "Instant", "Draw a card.", colors=("U",))
RED_RED = real("Double Red", "{R}{R}", "Instant", "Draw a card.", colors=("R",))
BLUE_RED = real("Blue Red", "{U}{R}", "Instant", "Draw a card.", colors=("U", "R"))
GREEN = real("Green Draw", "{G}", "Instant", "Draw a card.", colors=("G",))
ONE = real("One Draw", "{1}", "Instant", "Draw a card.")


def land(name, type_line, text, mana):
    """A land as Scryfall gives it: the Oracle text and the mana it can produce."""
    return Card(name=name, type_line=type_line, oracle_text=text, produced_mana=tuple(mana))


COASTAL = land("Coastal Peak", "Land — Island Mountain", "({T}: Add {U} or {R}.)\nThis land enters tapped.\nCycling {2} ({2}, Discard this card: Draw a card.)", "RU")
SPRINGS = land("Turbulent Springs", "Land — Island Mountain", "({T}: Add {U} or {R}.)\nThis land enters tapped unless your opponents control eight or more lands.", "RU")
BLUFFS = land("Cascade Bluffs", "Land", "{T}: Add {C}.\n{U/R}, {T}: Add {U}{U}, {U}{R}, or {R}{R}.", "CRU")
FERROUS = land("Ferrous Lake", "Land", "{1}, {T}: Add {U}{R}.", "RU")
REEF = land("Shivan Reef", "Land", "{T}: Add {C}.\n{T}: Add {U} or {R}. This land deals 1 damage to you.", "CRU")
FALLS = land("Sulfur Falls", "Land", "This land enters tapped unless you control an Island or a Mountain.\n{T}: Add {U} or {R}.", "RU")
TEMPLE = land("Temple of Epiphany", "Land", "This land enters tapped.\nWhen this land enters, scry 1. (Look at the top card of your library. You may put that card on the bottom.)\n{T}: Add {U} or {R}.", "RU")
SUMMIT = land("Spectacle Summit", "Land", "This land enters tapped.\n{T}: Add {U} or {R}.\n{2}{U}{R}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)", "RU")
TRIBUTARY = land("Molten Tributary", "Land — Island Mountain", "({T}: Add {U} or {R}.)\nThis land enters tapped.", "RU")
CAMPUS = land("Prismari Campus", "Land", "This land enters tapped.\n{T}: Add {U} or {R}.\n{4}, {T}: Scry 1. (Look at the top card of your library. You may put that card on the bottom.)", "RU")

ALL = [COASTAL, SPRINGS, BLUFFS, FERROUS, REEF, FALLS, TEMPLE, SUMMIT, TRIBUTARY, CAMPUS]
BLUE_OR_RED = [COASTAL, SPRINGS, REEF, FALLS, TEMPLE, SUMMIT, TRIBUTARY, CAMPUS]
ALWAYS_TAPPED = [COASTAL, TEMPLE, SUMMIT, TRIBUTARY, CAMPUS]


def play(policy, card, mine=(), theirs=()):
    """Seat 0 plays `card` from its hand; returns (game, seat, permanent)."""
    game, _ = table3(policy)
    a = game.seats[0]
    a.battlefield = list(mine)
    game.seats[1].battlefield = list(theirs)
    a.hand = [card]
    a.library = [PLAINS, FOREST, FOREST, FOREST]
    game._perform(a, PLAY_LAND + card.name)
    run_stack(game)
    return game, a, next(p for p in a.battlefield if p.card.name == card.name)


def entered_tapped(card, mine=(), theirs=()):
    return play(pick(), card, mine, theirs)[2].tapped


def castable(spell, *permanents):
    t = Table(spell, n=0, mine=list(permanents))
    return any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a))


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


def can_activate(game, seat, fragment):
    return any(a.startswith(ACTIVATE) and fragment in a for a in game.legal_actions(seat))


class EveryLandTests(unittest.TestCase):
    def test_parse(self):
        for card in ALL:
            with self.subTest(card=card.name):
                self.assertEqual(unsupported_lines(card), [])

    def test_the_lands_that_always_enter_tapped_do(self):
        for card in ALWAYS_TAPPED:
            with self.subTest(card=card.name):
                self.assertTrue(entered_tapped(card, mine=[Permanent(ISLAND), Permanent(MOUNTAIN)]))

    def test_the_lands_that_enter_untapped_do(self):
        for card in (REEF, FERROUS, BLUFFS):
            with self.subTest(card=card.name):
                self.assertFalse(entered_tapped(card))

    def test_a_land_that_makes_blue_or_red_pays_for_either_but_not_for_another_color(self):
        for card in BLUE_OR_RED:
            with self.subTest(card=card.name):
                self.assertTrue(castable(BLUE, Permanent(card)), "blue")
                self.assertTrue(castable(RED, Permanent(card)), "red")
                self.assertFalse(castable(GREEN, Permanent(card)), "green")
                self.assertFalse(castable(BLUE_RED, Permanent(card)), "it makes one mana")


class TurbulentSpringsTests(unittest.TestCase):
    def test_it_enters_tapped_unless_the_opponents_control_eight_or_more_lands(self):
        self.assertTrue(entered_tapped(SPRINGS, theirs=lands(7)), "seven")
        self.assertFalse(entered_tapped(SPRINGS, theirs=lands(8)), "eight")
        self.assertFalse(entered_tapped(SPRINGS, theirs=lands(12)), "twelve")

    def test_your_own_lands_do_not_count(self):
        self.assertTrue(entered_tapped(SPRINGS, mine=lands(9), theirs=lands(2)))

    def test_nonland_permanents_of_the_opponents_do_not_count(self):
        self.assertTrue(entered_tapped(SPRINGS, theirs=lands(5) + [Permanent(BEAR)] * 5))

    def test_the_lands_of_the_opponents_together_count(self):
        game, _ = table3(pick())
        game.seats[1].battlefield = lands(4)
        game.seats[2].battlefield = lands(4)
        a = game.seats[0]
        a.hand = [SPRINGS]
        game._perform(a, PLAY_LAND + SPRINGS.name)
        self.assertFalse(a.battlefield[-1].tapped)


class ShivanReefTests(unittest.TestCase):
    def pay(self, spell):
        t = Table(spell, n=0, mine=[Permanent(REEF)])
        before = t.a.life
        t.cast()
        return before - t.a.life

    def test_colored_mana_costs_one_life(self):
        self.assertEqual(self.pay(BLUE), 1)
        self.assertEqual(self.pay(RED), 1)

    def test_colorless_mana_costs_nothing(self):
        self.assertEqual(self.pay(ONE), 0)


class SulfurFallsTests(unittest.TestCase):
    def test_an_island_or_a_mountain_makes_it_untapped(self):
        for enabler in (ISLAND, MOUNTAIN, COASTAL, TRIBUTARY):
            with self.subTest(enabler=enabler.name):
                self.assertFalse(entered_tapped(FALLS, mine=[Permanent(enabler)]))

    def test_other_lands_and_permanents_do_not(self):
        self.assertTrue(entered_tapped(FALLS))
        self.assertTrue(entered_tapped(FALLS, mine=[Permanent(FOREST), Permanent(PLAINS), Permanent(WASTES), Permanent(BEAR)]))

    def test_an_opponents_island_or_mountain_does_not(self):
        self.assertTrue(entered_tapped(FALLS, theirs=[Permanent(ISLAND), Permanent(MOUNTAIN)]))


class CoastalPeakTests(unittest.TestCase):
    def test_cycling_costs_two_and_draws_a_card(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(2)
        a.hand = [COASTAL]
        a.library = [PLAINS, FOREST]
        game._perform(a, CYCLE + COASTAL.name)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), (["Plains"], ["Coastal Peak"]))
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_cycling_needs_two_mana(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(1)
        a.hand = [COASTAL]
        self.assertFalse(any(x.startswith(CYCLE) for x in game.legal_actions(a)))


class CascadeBluffsTests(unittest.TestCase):
    def test_on_its_own_it_makes_only_colorless(self):
        self.assertTrue(castable(ONE, Permanent(BLUFFS)))
        self.assertFalse(castable(BLUE, Permanent(BLUFFS)))
        self.assertFalse(castable(RED, Permanent(BLUFFS)))

    def test_with_blue_or_red_mana_to_pay_it_makes_two_mana_of_either_color_pair(self):
        for spell in (BLUE_BLUE, BLUE_RED, RED_RED):
            for payer in (ISLAND, MOUNTAIN):
                with self.subTest(spell=spell.name, payer=payer.name):
                    self.assertTrue(castable(spell, Permanent(BLUFFS), Permanent(payer)))

    def test_it_cannot_make_green_or_be_paid_for_with_other_colors(self):
        self.assertFalse(castable(GREEN, Permanent(BLUFFS), Permanent(ISLAND)))
        self.assertFalse(castable(BLUE_BLUE, Permanent(BLUFFS), Permanent(FOREST)))

    def test_it_makes_exactly_two_mana_for_the_one_it_took(self):
        three = real("Triple", "{U}{U}{U}", "Instant", "Draw a card.", colors=("U",))
        self.assertFalse(castable(three, Permanent(BLUFFS), Permanent(ISLAND)))
        self.assertTrue(castable(three, Permanent(BLUFFS), Permanent(ISLAND), Permanent(ISLAND)))


class FerrousLakeTests(unittest.TestCase):
    def test_one_mana_of_any_kind_turns_into_blue_and_red(self):
        for payer in (ISLAND, FOREST, WASTES):
            with self.subTest(payer=payer.name):
                self.assertTrue(castable(BLUE_RED, Permanent(FERROUS), Permanent(payer)))

    def test_it_cannot_pay_for_itself(self):
        self.assertFalse(castable(BLUE_RED, Permanent(FERROUS)))
        self.assertFalse(castable(BLUE, Permanent(FERROUS)))

    def test_it_makes_exactly_blue_and_red(self):
        self.assertFalse(castable(BLUE_BLUE, Permanent(FERROUS), Permanent(WASTES)))
        self.assertFalse(castable(GREEN, Permanent(FERROUS), Permanent(WASTES)))


class TempleOfEpiphanyTests(unittest.TestCase):
    def test_it_scries_one_when_it_enters_and_the_card_may_go_to_the_bottom(self):
        game, a, _ = play(pick("Put on the bottom"), TEMPLE)
        self.assertEqual((a.library[0].name, a.library[-1].name), ("Forest", "Plains"))

    def test_the_card_may_stay_on_top(self):
        game, a, _ = play(pick("Keep on top"), TEMPLE)
        self.assertEqual((a.library[0].name, len(a.library)), ("Plains", 4))


class SpectacleSummitTests(unittest.TestCase):
    def table(self, policy, mine):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(SUMMIT)] + [Permanent(c) for c in mine]
        a.library = [PLAINS, FOREST, FOREST, FOREST]
        return game, a

    def test_two_blue_red_and_two_more_pay_to_surveil_one(self):
        game, a = self.table(pick("Put into"), [ISLAND, MOUNTAIN, FOREST, FOREST])
        activate(game, a, "Surveil")
        self.assertEqual([c.name for c in a.graveyard], ["Plains"])
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_the_card_may_stay_on_top(self):
        game, a = self.table(pick("Keep on top"), [ISLAND, MOUNTAIN, FOREST, FOREST])
        activate(game, a, "Surveil")
        self.assertEqual((a.library[0].name, a.graveyard), ("Plains", []))

    def test_without_the_mana_it_cannot_be_activated(self):
        game, a = self.table(pick(), [ISLAND, MOUNTAIN, FOREST])
        self.assertFalse(can_activate(game, a, "Surveil"))

    def test_the_blue_and_the_red_are_required(self):
        game, a = self.table(pick(), [FOREST, FOREST, FOREST, FOREST])
        self.assertFalse(can_activate(game, a, "Surveil"))


class PrismariCampusTests(unittest.TestCase):
    def table(self, policy, others):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(CAMPUS)] + others
        a.library = [PLAINS, FOREST, FOREST, FOREST]
        return game, a

    def test_four_mana_and_a_tap_scry_one_and_the_card_may_go_to_the_bottom(self):
        game, a = self.table(pick("Put on the bottom"), lands(4))
        activate(game, a, "Scry")
        self.assertEqual((a.library[0].name, a.library[-1].name), ("Forest", "Plains"))
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_the_card_may_stay_on_top(self):
        game, a = self.table(pick("Keep on top"), lands(4))
        activate(game, a, "Scry")
        self.assertEqual(a.library[0].name, "Plains")

    def test_three_other_lands_are_not_enough(self):
        game, a = self.table(pick(), lands(3))
        self.assertFalse(can_activate(game, a, "Scry"))


if __name__ == "__main__":
    unittest.main()
