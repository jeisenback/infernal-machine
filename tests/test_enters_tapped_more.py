"""The enters-tapped patterns of issue #91.

The card lines are the issue's own wording of each pattern; the cards' other lines (mana abilities and the like) are not
written here, since this file is about how the land comes in. Names are real cards that use the pattern.
"""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.effects import (EntersTapped, enters_tapped_rule, enters_with_counters, triggered_abilities)
from infernal_machine.game import CHOOSE_COLOR_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack


def land(name, text, kind="Land"):
    return Card(name=name, type_line=kind, oracle_text=text)


FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
UTILITY = Card(name="Utility Land", type_line="Land")
WALKER = Card(name="Walker", type_line="Legendary Planeswalker — Test", loyalty="3")
KING = Card(name="King", type_line="Legendary Creature — Human", power="2", toughness="2")
HORSE = Card(name="Horse", type_line="Creature — Mount", power="2", toughness="2")
CART = Card(name="Cart", type_line="Artifact — Vehicle", power="3", toughness="3")

THEORIX_ANNEX = land("Theorix Annex", "This land enters tapped unless you control a planeswalker.")
ABANDONED_CAMPGROUND = land("Abandoned Campground", "This land enters tapped unless a player has 13 or less life.")
ROOM_OF_REFUGE = land("Room of Refuge", "This land enters tapped. As it enters, choose a color.")
ARENA_OF_GLORY = land("Arena of Glory", "This land enters tapped unless you control a Mountain.")
CAVE_OF_THE_FROST_DRAGON = land("Cave of the Frost Dragon", "If you control two or more other lands, this land enters tapped.")
VIVID_MARSH = land("Vivid Marsh", "This land enters tapped with two charge counters on it.")
AGNA_QELA = land("Agna Qel'a", "This land enters tapped unless you control a basic land.")
RIVENDELL = land("Rivendell", "CARDNAME enters tapped unless you control a legendary creature.")
HICKORY_WOODLOT = land("Hickory Woodlot", "This land enters tapped with two depletion counters on it.")
REEF_ROADS = land("Reef Roads", "This land enters tapped unless you control a Mount or Vehicle.")
HOLLOW_TREES = land("Hollow Trees", "At the beginning of your upkeep, if this land is tapped, put a storage counter on it.")
DORMANT_VOLCANO = land("Dormant Volcano", "When this land enters, sacrifice it unless you return an untapped Mountain you control to its owner's hand.")
RISING_CHICANE = land("Rising Chicane", "If you were the starting player, this land enters tapped.")
FLAMEKIN_VILLAGE = land("Flamekin Village", "As this land enters, you may reveal an Elemental card from your hand. If you don't, this land enters tapped.")
ELEMENTAL = Card(name="Fire Elemental", type_line="Creature — Elemental", power="3", toughness="3")


def comes_in(game, seat, card):
    """Put `card` onto the battlefield under `seat` the way a land played from the hand does; returns the permanent."""
    permanent = Permanent(card)
    game._enter(seat, permanent)
    return permanent


class UnlessYouControlTests(unittest.TestCase):
    def test_a_planeswalker_a_basic_land_a_land_type_a_legendary_creature_or_a_mount_or_vehicle(self):
        cases = [(THEORIX_ANNEX, WALKER), (AGNA_QELA, FOREST), (ARENA_OF_GLORY, MOUNTAIN), (RIVENDELL, KING),
                 (REEF_ROADS, HORSE), (REEF_ROADS, CART)]
        for card, enabler in cases:
            with self.subTest(card=card.name, enabler=enabler.name):
                self.assertEqual(unsupported_lines(card), [])
                game, _ = table3()
                a = game.seats[0]
                self.assertTrue(comes_in(game, a, card).tapped, "alone")
                a.battlefield = [Permanent(BEAR), Permanent(UTILITY)]
                self.assertTrue(comes_in(game, a, card).tapped, "something else")
                a.battlefield.append(Permanent(enabler))
                self.assertFalse(comes_in(game, a, card).tapped, enabler.name)

    def test_only_what_you_control_counts(self):
        game, _ = table3()
        a, b, _c = game.seats
        b.battlefield = [Permanent(WALKER)]
        self.assertTrue(comes_in(game, a, THEORIX_ANNEX).tapped)

    def test_a_legendary_creature_must_be_both(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(Card(name="Legendary Relic", type_line="Legendary Artifact")), Permanent(BEAR)]
        self.assertTrue(comes_in(game, a, RIVENDELL).tapped)


class LifeTotalTests(unittest.TestCase):
    def test_unless_a_player_has_13_or_less_life(self):
        self.assertEqual(enters_tapped_rule(ABANDONED_CAMPGROUND), EntersTapped("unless_a_player_life", count=13))
        self.assertEqual(unsupported_lines(ABANDONED_CAMPGROUND), [])
        game, _ = table3()
        a, b, c = game.seats
        self.assertTrue(comes_in(game, a, ABANDONED_CAMPGROUND).tapped)  # everyone is at 40
        c.life = 14
        self.assertTrue(comes_in(game, a, ABANDONED_CAMPGROUND).tapped)
        c.life = 13
        self.assertFalse(comes_in(game, a, ABANDONED_CAMPGROUND).tapped)  # any player, not only you or an opponent
        c.life, a.life = 40, 5
        self.assertFalse(comes_in(game, a, ABANDONED_CAMPGROUND).tapped)


class OtherLandsTests(unittest.TestCase):
    def test_two_or_more_other_lands_and_it_is_tapped(self):
        self.assertEqual(enters_tapped_rule(CAVE_OF_THE_FROST_DRAGON), EntersTapped("if_lands_at_least", count=2))
        self.assertEqual(unsupported_lines(CAVE_OF_THE_FROST_DRAGON), [])
        game, _ = table3()
        a = game.seats[0]
        self.assertFalse(comes_in(game, a, CAVE_OF_THE_FROST_DRAGON).tapped)  # the first two lands come in untapped
        a.battlefield = [Permanent(FOREST)]
        self.assertFalse(comes_in(game, a, CAVE_OF_THE_FROST_DRAGON).tapped)
        a.battlefield = [Permanent(FOREST), Permanent(UTILITY)]
        self.assertTrue(comes_in(game, a, CAVE_OF_THE_FROST_DRAGON).tapped)


class StartingPlayerTests(unittest.TestCase):
    def test_tapped_if_you_were_the_starting_player(self):
        self.assertEqual(enters_tapped_rule(RISING_CHICANE), EntersTapped("if_starting_player"))
        self.assertEqual(unsupported_lines(RISING_CHICANE), [])
        game, _ = table3()
        a, b, _c = game.seats
        game.starting_seat = a.index
        self.assertTrue(comes_in(game, a, RISING_CHICANE).tapped)
        self.assertFalse(comes_in(game, b, RISING_CHICANE).tapped)

    def test_the_game_remembers_who_started(self):
        game, _ = table3()
        game.setup()
        self.assertEqual(game.starting_seat, game.active)  # nobody has taken a turn yet


class RevealAnElementalTests(unittest.TestCase):
    def test_reveal_one_from_your_hand_or_it_enters_tapped(self):
        self.assertEqual(enters_tapped_rule(FLAMEKIN_VILLAGE), EntersTapped("reveal", types=("Elemental",)))
        self.assertEqual(unsupported_lines(FLAMEKIN_VILLAGE), [])
        game, _ = table3(pick("Reveal"))
        a = game.seats[0]
        self.assertTrue(comes_in(game, a, FLAMEKIN_VILLAGE).tapped)  # nothing to reveal
        a.hand = [BEAR]
        self.assertTrue(comes_in(game, a, FLAMEKIN_VILLAGE).tapped)  # not an Elemental
        a.hand = [BEAR, ELEMENTAL]
        self.assertFalse(comes_in(game, a, FLAMEKIN_VILLAGE).tapped)
        self.assertEqual(a.hand, [BEAR, ELEMENTAL])  # revealed, not discarded

    def test_declining_to_reveal_enters_tapped(self):
        game, _ = table3(pick("Enter tapped"))
        a = game.seats[0]
        a.hand = [ELEMENTAL]
        self.assertTrue(comes_in(game, a, FLAMEKIN_VILLAGE).tapped)

    def test_the_snarl_pattern_with_two_land_types_still_works(self):
        snarl = land("Frostboil Snarl", "As this land enters, you may reveal an Island or Mountain card from your hand. If you don't, this land enters tapped.")
        self.assertEqual(enters_tapped_rule(snarl), EntersTapped("reveal", types=("Island", "Mountain")))


class CountersOnEntryTests(unittest.TestCase):
    def test_enters_tapped_with_charge_or_depletion_counters(self):
        for card, counter in ((VIVID_MARSH, "charge"), (HICKORY_WOODLOT, "depletion")):
            with self.subTest(card=card.name):
                self.assertEqual(enters_tapped_rule(card), EntersTapped("always"))
                self.assertEqual(enters_with_counters(card), {counter: 2})
                self.assertEqual(unsupported_lines(card), [])
                game, _ = table3()
                a = game.seats[0]
                permanent = comes_in(game, a, card)
                self.assertEqual((permanent.tapped, permanent.counters), (True, {counter: 2}))


class ChooseAColorTests(unittest.TestCase):
    def test_it_enters_tapped_and_you_choose_a_color_as_it_does(self):
        self.assertEqual(enters_tapped_rule(ROOM_OF_REFUGE), EntersTapped("always"))
        self.assertEqual(unsupported_lines(ROOM_OF_REFUGE), [])
        seen = []

        def policy(prompt, options):
            seen.append((prompt, list(options)))
            return options.index("Red")

        game, _ = table3(policy)
        a = game.seats[0]
        permanent = comes_in(game, a, ROOM_OF_REFUGE)
        self.assertEqual((permanent.tapped, permanent.chosen_color), (True, "R"))
        self.assertEqual(seen, [(CHOOSE_COLOR_PROMPT + "Room of Refuge", ["White", "Blue", "Black", "Red", "Green"])])

    def test_the_choice_can_stand_alone_on_a_line_of_its_own(self):
        card = land("Colorful Land", "This land enters tapped.\nAs this land enters, choose a color.")
        self.assertEqual(unsupported_lines(card), [])
        game, _ = table3(pick("Blue"))
        self.assertEqual(comes_in(game, game.seats[0], card).chosen_color, "U")


class StorageCounterTests(unittest.TestCase):
    def test_a_storage_counter_at_your_upkeep_if_the_land_is_tapped(self):
        [ability] = triggered_abilities(HOLLOW_TREES)
        self.assertEqual((ability.event, ability.condition.kind), ("upkeep", "source_tapped"))
        self.assertEqual(unsupported_lines(HOLLOW_TREES), [])
        game, _ = table3()
        a = game.seats[0]
        tapped, untapped = Permanent(HOLLOW_TREES, tapped=True), Permanent(HOLLOW_TREES)
        a.battlefield = [tapped, untapped]
        game.step = "upkeep"
        for permanent in list(a.battlefield):
            game.trigger("upkeep", permanent, a)
        run_stack(game)
        self.assertEqual((tapped.counters, untapped.counters), ({"storage": 1}, {}))


class KarooTests(unittest.TestCase):
    def test_return_an_untapped_land_of_the_type_or_sacrifice_it(self):
        self.assertEqual(unsupported_lines(DORMANT_VOLCANO), [])
        game, _ = table3(pick("Return"))
        a = game.seats[0]
        mountain = Permanent(MOUNTAIN)
        a.battlefield = [mountain, Permanent(FOREST)]
        karoo = comes_in(game, a, DORMANT_VOLCANO)
        run_stack(game)
        self.assertEqual((karoo in a.battlefield, mountain in a.battlefield, a.hand), (True, False, [MOUNTAIN]))

    def test_with_no_untapped_mountain_it_is_sacrificed(self):
        game, _ = table3(pick("Return"))
        a = game.seats[0]
        a.battlefield = [Permanent(MOUNTAIN, tapped=True), Permanent(FOREST)]
        karoo = comes_in(game, a, DORMANT_VOLCANO)
        run_stack(game)
        self.assertEqual((karoo in a.battlefield, a.hand), (False, []))
        self.assertIn(DORMANT_VOLCANO, a.graveyard)

    def test_you_can_decline_and_lose_the_karoo_instead(self):
        game, _ = table3(pick("Sacrifice"))
        a = game.seats[0]
        mountain = Permanent(MOUNTAIN)
        a.battlefield = [mountain]
        karoo = comes_in(game, a, DORMANT_VOLCANO)
        run_stack(game)
        self.assertEqual((karoo in a.battlefield, mountain in a.battlefield), (False, True))
