"""The ten Quandrix lands of the precon decks (issue #165), each played from its real Oracle text: how it comes in
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
GREEN = real("Green Draw", "{G}", "Instant", "Draw a card.", colors=("G",))
BLUE = real("Blue Draw", "{U}", "Instant", "Draw a card.", colors=("U",))
GREEN_GREEN = real("Double Green", "{G}{G}", "Instant", "Draw a card.", colors=("G",))
BLUE_BLUE = real("Double Blue", "{U}{U}", "Instant", "Draw a card.", colors=("U",))
GREEN_BLUE = real("Green Blue", "{G}{U}", "Instant", "Draw a card.", colors=("G", "U"))
RED = real("Red Draw", "{R}", "Instant", "Draw a card.", colors=("R",))
ONE = real("One Draw", "{1}", "Instant", "Draw a card.")


def land(name, type_line, text, mana):
    """A land as Scryfall gives it: the Oracle text and the mana it can produce."""
    return Card(name=name, type_line=type_line, oracle_text=text, produced_mana=tuple(mana))


WILDERNESS = land("Turbulent Wilderness", "Land — Forest Island", "({T}: Add {G} or {U}.)\nThis land enters tapped unless your opponents control eight or more lands.", "GU")
GROVE = land("Flooded Grove", "Land", "{T}: Add {C}.\n{G/U}, {T}: Add {G}{G}, {G}{U}, or {U}{U}.", "CGU")
HARBOR = land("Hinterland Harbor", "Land", "This land enters tapped unless you control a Forest or an Island.\n{T}: Add {G} or {U}.", "GU")
BASIN = land("Overflowing Basin", "Land", "{1}, {T}: Add {G}{U}.", "GU")
COPSE = land("Rain-Slicked Copse", "Land — Forest Island", "({T}: Add {G} or {U}.)\nThis land enters tapped.\nCycling {2} ({2}, Discard this card: Draw a card.)", "GU")
VERDURE = land("Sodden Verdure", "Land — Forest Island", "({T}: Add {G} or {U}.)\nThis land enters tapped unless you control two or more basic lands.", "GU")
SNARL = land("Vineglimmer Snarl", "Land", "As this land enters, you may reveal a Forest or Island card from your hand. If you don't, this land enters tapped.\n{T}: Add {G} or {U}.", "GU")
GARDENS = land("Paradox Gardens", "Land", "This land enters tapped.\n{T}: Add {G} or {U}.\n{2}{G}{U}, {T}: Surveil 1. (Look at the top card of your library. You may put it into your graveyard.)", "GU")
CAMPUS = land("Quandrix Campus", "Land", "This land enters tapped.\n{T}: Add {G} or {U}.\n{4}, {T}: Scry 1. (Look at the top card of your library. You may put that card on the bottom.)", "GU")
ISLET = land("Tangled Islet", "Land — Forest Island", "({T}: Add {G} or {U}.)\nThis land enters tapped.", "GU")

ALL = [WILDERNESS, GROVE, HARBOR, BASIN, COPSE, VERDURE, SNARL, GARDENS, CAMPUS, ISLET]
GREEN_OR_BLUE = [WILDERNESS, HARBOR, COPSE, VERDURE, SNARL, GARDENS, CAMPUS, ISLET]
ALWAYS_TAPPED = [COPSE, GARDENS, CAMPUS, ISLET]


def play(policy, card, mine=(), theirs=(), hand=()):
    """Seat 0 plays `card` from its hand (which also holds `hand`); returns (game, seat, permanent)."""
    game, _ = table3(policy)
    a = game.seats[0]
    a.battlefield = list(mine)
    game.seats[1].battlefield = list(theirs)
    a.hand = [card, *hand]
    a.library = [PLAINS, FOREST, FOREST, FOREST]
    game._perform(a, PLAY_LAND + card.name)
    run_stack(game)
    return game, a, next(p for p in a.battlefield if p.card.name == card.name)


def entered_tapped(card, mine=(), theirs=(), hand=(), policy=None):
    return play(policy or pick(), card, mine, theirs, hand)[2].tapped


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
                self.assertTrue(entered_tapped(card, mine=[Permanent(FOREST), Permanent(ISLAND)], hand=[FOREST, ISLAND]))

    def test_the_lands_that_enter_untapped_do(self):
        for card in (BASIN, GROVE):
            with self.subTest(card=card.name):
                self.assertFalse(entered_tapped(card))

    def test_a_land_that_makes_green_or_blue_pays_for_either_but_not_for_another_color(self):
        for card in GREEN_OR_BLUE:
            with self.subTest(card=card.name):
                self.assertTrue(castable(GREEN, Permanent(card)), "green")
                self.assertTrue(castable(BLUE, Permanent(card)), "blue")
                self.assertFalse(castable(RED, Permanent(card)), "red")
                self.assertFalse(castable(GREEN_BLUE, Permanent(card)), "it makes one mana")


class TurbulentWildernessTests(unittest.TestCase):
    def test_it_enters_tapped_unless_the_opponents_control_eight_or_more_lands(self):
        self.assertTrue(entered_tapped(WILDERNESS, theirs=lands(7)), "seven")
        self.assertFalse(entered_tapped(WILDERNESS, theirs=lands(8)), "eight")
        self.assertFalse(entered_tapped(WILDERNESS, theirs=lands(12)), "twelve")

    def test_your_own_lands_do_not_count(self):
        self.assertTrue(entered_tapped(WILDERNESS, mine=lands(9), theirs=lands(2)))

    def test_nonland_permanents_of_the_opponents_do_not_count(self):
        self.assertTrue(entered_tapped(WILDERNESS, theirs=lands(5) + [Permanent(BEAR)] * 5))

    def test_the_lands_of_the_opponents_together_count(self):
        game, _ = table3(pick())
        game.seats[1].battlefield = lands(4)
        game.seats[2].battlefield = lands(4)
        a = game.seats[0]
        a.hand = [WILDERNESS]
        game._perform(a, PLAY_LAND + WILDERNESS.name)
        self.assertFalse(a.battlefield[-1].tapped)


class HinterlandHarborTests(unittest.TestCase):
    def test_a_forest_or_an_island_makes_it_untapped(self):
        for enabler in (FOREST, ISLAND, COPSE, ISLET):
            with self.subTest(enabler=enabler.name):
                self.assertFalse(entered_tapped(HARBOR, mine=[Permanent(enabler)]))

    def test_other_lands_and_permanents_do_not(self):
        self.assertTrue(entered_tapped(HARBOR))
        self.assertTrue(entered_tapped(HARBOR, mine=[Permanent(MOUNTAIN), Permanent(PLAINS), Permanent(WASTES), Permanent(BEAR)]))

    def test_an_opponents_forest_or_island_does_not(self):
        self.assertTrue(entered_tapped(HARBOR, theirs=[Permanent(FOREST), Permanent(ISLAND)]))

    def test_a_forest_or_island_in_hand_does_not(self):
        self.assertTrue(entered_tapped(HARBOR, hand=[FOREST, ISLAND]))


class SoddenVerdureTests(unittest.TestCase):
    def test_two_or_more_basic_lands_make_it_untapped(self):
        self.assertFalse(entered_tapped(VERDURE, mine=[Permanent(MOUNTAIN), Permanent(MOUNTAIN)]))
        self.assertFalse(entered_tapped(VERDURE, mine=[Permanent(FOREST), Permanent(ISLAND), Permanent(WASTES)]))

    def test_one_basic_land_is_not_enough(self):
        self.assertTrue(entered_tapped(VERDURE))
        self.assertTrue(entered_tapped(VERDURE, mine=[Permanent(FOREST)]))

    def test_nonbasic_lands_do_not_count(self):
        self.assertTrue(entered_tapped(VERDURE, mine=[Permanent(HARBOR), Permanent(WILDERNESS), Permanent(ISLET)]))

    def test_an_opponents_basic_lands_do_not_count(self):
        self.assertTrue(entered_tapped(VERDURE, theirs=lands(4)))


class VineglimmerSnarlTests(unittest.TestCase):
    def test_revealing_a_forest_or_an_island_from_hand_lets_it_enter_untapped(self):
        for card in (FOREST, ISLAND, ISLET):
            with self.subTest(card=card.name):
                game, a, snarl = play(pick("Reveal"), SNARL, hand=[BEAR, card])
                self.assertFalse(snarl.tapped)
                self.assertEqual([c.name for c in a.hand], ["Bear", card.name], "revealed, not discarded")

    def test_it_enters_tapped_when_nothing_in_hand_can_be_revealed(self):
        self.assertTrue(entered_tapped(SNARL, policy=pick("Reveal")), "empty hand")
        self.assertTrue(entered_tapped(SNARL, hand=[BEAR, MOUNTAIN, PLAINS], policy=pick("Reveal")), "no Forest or Island")

    def test_a_land_on_the_battlefield_is_not_a_reveal(self):
        self.assertTrue(entered_tapped(SNARL, mine=[Permanent(FOREST), Permanent(ISLAND)], policy=pick("Reveal")))

    def test_declining_to_reveal_enters_tapped(self):
        self.assertTrue(entered_tapped(SNARL, hand=[FOREST], policy=pick("Enter tapped")))


class RainSlickedCopseTests(unittest.TestCase):
    def test_cycling_costs_two_and_draws_a_card(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(2)
        a.hand = [COPSE]
        a.library = [PLAINS, FOREST]
        game._perform(a, CYCLE + COPSE.name)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), (["Plains"], ["Rain-Slicked Copse"]))
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_cycling_needs_two_mana(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = lands(1)
        a.hand = [COPSE]
        self.assertFalse(any(x.startswith(CYCLE) for x in game.legal_actions(a)))


class FloodedGroveTests(unittest.TestCase):
    def test_on_its_own_it_makes_only_colorless(self):
        self.assertTrue(castable(ONE, Permanent(GROVE)))
        self.assertFalse(castable(GREEN, Permanent(GROVE)))
        self.assertFalse(castable(BLUE, Permanent(GROVE)))

    def test_with_green_or_blue_mana_to_pay_it_makes_two_mana_of_either_color_pair(self):
        for spell in (GREEN_GREEN, GREEN_BLUE, BLUE_BLUE):
            for payer in (FOREST, ISLAND):
                with self.subTest(spell=spell.name, payer=payer.name):
                    self.assertTrue(castable(spell, Permanent(GROVE), Permanent(payer)))

    def test_it_cannot_make_red_or_be_paid_for_with_other_colors(self):
        self.assertFalse(castable(RED, Permanent(GROVE), Permanent(FOREST)))
        self.assertFalse(castable(GREEN_GREEN, Permanent(GROVE), Permanent(MOUNTAIN)))

    def test_it_makes_exactly_two_mana_for_the_one_it_took(self):
        three = real("Triple", "{G}{G}{G}", "Instant", "Draw a card.", colors=("G",))
        self.assertFalse(castable(three, Permanent(GROVE), Permanent(FOREST)))
        self.assertTrue(castable(three, Permanent(GROVE), Permanent(FOREST), Permanent(FOREST)))


class OverflowingBasinTests(unittest.TestCase):
    def test_one_mana_of_any_kind_turns_into_green_and_blue(self):
        for payer in (FOREST, MOUNTAIN, WASTES):
            with self.subTest(payer=payer.name):
                self.assertTrue(castable(GREEN_BLUE, Permanent(BASIN), Permanent(payer)))

    def test_it_cannot_pay_for_itself(self):
        self.assertFalse(castable(GREEN_BLUE, Permanent(BASIN)))
        self.assertFalse(castable(GREEN, Permanent(BASIN)))

    def test_it_makes_exactly_green_and_blue(self):
        self.assertFalse(castable(GREEN_GREEN, Permanent(BASIN), Permanent(WASTES)))
        self.assertFalse(castable(RED, Permanent(BASIN), Permanent(WASTES)))


class ParadoxGardensTests(unittest.TestCase):
    def table(self, policy, mine):
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(GARDENS)] + [Permanent(c) for c in mine]
        a.library = [PLAINS, FOREST, FOREST, FOREST]
        return game, a

    def test_green_blue_and_two_more_pay_to_surveil_one(self):
        game, a = self.table(pick("Put into"), [FOREST, ISLAND, MOUNTAIN, MOUNTAIN])
        activate(game, a, "Surveil")
        self.assertEqual([c.name for c in a.graveyard], ["Plains"])
        self.assertTrue(all(p.tapped for p in a.battlefield))

    def test_the_card_may_stay_on_top(self):
        game, a = self.table(pick("Keep on top"), [FOREST, ISLAND, MOUNTAIN, MOUNTAIN])
        activate(game, a, "Surveil")
        self.assertEqual((a.library[0].name, a.graveyard), ("Plains", []))

    def test_without_the_mana_it_cannot_be_activated(self):
        game, a = self.table(pick(), [FOREST, ISLAND, MOUNTAIN])
        self.assertFalse(can_activate(game, a, "Surveil"))

    def test_the_green_and_the_blue_are_required(self):
        game, a = self.table(pick(), [MOUNTAIN, MOUNTAIN, MOUNTAIN, MOUNTAIN])
        self.assertFalse(can_activate(game, a, "Surveil"))


class QuandrixCampusTests(unittest.TestCase):
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
