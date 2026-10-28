"""Look at the top N cards, put some into your hand and the rest on the bottom or into the graveyard (#564: Stock Up's family)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import spell_effects
from infernal_machine.effects.families.library_and_hand import Impulse
from infernal_machine.effects.families.spells_and_misc import KickedInstead
from infernal_machine.game import LOOK_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import Table, real

STOCK_UP = real("Stock Up", "{2}{U}", "Sorcery", "Look at the top five cards of your library. Put two of them into your hand and the rest on the "
                                                 "bottom of your library in any order.")
SLEIGHT = real("Sleight of Hand", "{U}", "Sorcery", "Look at the top two cards of your library. Put one of them into your hand and the other on the "
                                                   "bottom of your library.")
FLOW_STATE = real("Flow State", "{1}{U}", "Sorcery", "Look at the top three cards of your library. Put one of them into your hand and the rest on the "
                                                    "bottom of your library in any order. If there is an instant card and a sorcery card in your "
                                                    "graveyard, instead put two of them into your hand and the rest on the bottom of your library in "
                                                    "any order.")
CONSULT = real("Consult the Star Charts", "{1}{U}", "Instant", "Kicker {1}{U} (You may pay an additional {1}{U} as you cast this spell.)\n"
                                                               "Look at the top X cards of your library, where X is the number of lands you control. "
                                                               "Put one of those cards into your hand. If this spell was kicked, put two of those cards "
                                                               "into your hand instead. Put the rest on the bottom of your library in a random order.")
ORACLE = real("Sea Gate Oracle", "{2}{U}", "Creature — Human Wizard", "When this creature enters, look at the top two cards of your library. Put one "
                                                                       "of them into your hand and the other on the bottom of your library.", "1", "3")
GLIMPSE = real("Glimpse the Future", "{2}{U}", "Sorcery", "Look at the top three cards of your library. Put one of them into your hand and the rest "
                                                         "into your graveyard.")
DRAWN = real("Drawn from Dreams", "{2}{U}{U}", "Sorcery", "Look at the top seven cards of your library. Put two of them into your hand and the rest "
                                                         "on the bottom of your library in a random order.")
DARK_BARGAIN = real("Dark Bargain", "{3}{B}", "Instant", "Look at the top three cards of your library. Put two of them into your hand and the other "
                                                        "into your graveyard. Dark Bargain deals 2 damage to you.")
THASSA = real("Thassa's Intervention", "{X}{U}{U}", "Instant", "Choose one —\n• Look at the top X cards of your library. Put up to two of them into "
                                                               "your hand and the rest on the bottom of your library in a random order.\n• Counter "
                                                               "target spell unless its controller pays twice {X}.")
INSTANT = real("Spent Instant", "{U}", "Instant", "")
SORCERY = real("Spent Sorcery", "{U}", "Sorcery", "")


def library(n=9):
    return [real(f"Card {i}", "{1}", "Sorcery", "") for i in range(n)]


def names(cards):
    return [c.name for c in cards]


class ParseTests(unittest.TestCase):
    def test_the_family_is_read(self):
        for card in (STOCK_UP, SLEIGHT, FLOW_STATE, CONSULT, ORACLE, GLIMPSE, DRAWN, DARK_BARGAIN):
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertEqual(spell_effects(STOCK_UP), [Impulse(5, None, take=2)])
        self.assertEqual(spell_effects(GLIMPSE), [Impulse(3, None, rest="graveyard")])
        self.assertEqual(spell_effects(CONSULT)[1:], [Impulse("X", None), KickedInstead("take", 2)])

    def test_up_to_two_is_not_read_yet(self):
        self.assertTrue(unsupported_lines(THASSA))

    def test_a_take_with_no_word_on_the_rest_is_not_read(self):
        half = Card(name="Half", mana_cost="{U}", type_line="Sorcery",
                    oracle_text="Look at the top three cards of your library. Put one of those cards into your hand.")
        self.assertIsNone(spell_effects(half))
        self.assertTrue(unsupported_lines(half))


class StockUpTests(unittest.TestCase):
    def test_two_of_the_top_five_go_to_hand_and_the_rest_to_the_bottom(self):
        t = Table(STOCK_UP, "Card 3", "Card 0", library=library()).cast()
        self.assertEqual(sorted(names(t.a.hand)), ["Card 0", "Card 3"])
        self.assertEqual(names(t.a.library[:4]), ["Card 5", "Card 6", "Card 7", "Card 8"], "the cards below the five are on top now")
        self.assertEqual(sorted(names(t.a.library[4:])), ["Card 1", "Card 2", "Card 4"], "the other three went to the bottom")
        self.assertEqual(len([p for p, _ in t.game.seats[0].player.prompts if p == LOOK_PROMPT]), 2)

    def test_the_second_take_offers_only_what_is_left(self):
        t = Table(STOCK_UP, "Card 3", "Card 0", library=library()).cast()
        first, second = [o for p, o in t.a.player.prompts if p == LOOK_PROMPT]
        self.assertEqual(first, ["Card 0", "Card 1", "Card 2", "Card 3", "Card 4"])
        self.assertEqual(second, ["Card 0", "Card 1", "Card 2", "Card 4"])

    def test_a_short_library_takes_what_there_is(self):
        t = Table(STOCK_UP, library=library(1)).cast()
        self.assertEqual(names(t.a.hand), ["Card 0"])
        self.assertEqual(t.a.library, [])


class SleightOfHandTests(unittest.TestCase):
    def test_one_of_two_to_hand_and_the_other_to_the_bottom(self):
        t = Table(SLEIGHT, "Card 1", library=library(4)).cast()
        self.assertEqual(names(t.a.hand), ["Card 1"])
        self.assertEqual(names(t.a.library), ["Card 2", "Card 3", "Card 0"])

    def test_the_trigger_form_on_a_creature(self):
        t = Table(ORACLE, "Card 1", library=library(4)).cast()
        self.assertEqual(names(t.a.hand), ["Card 1"])
        self.assertEqual(names(t.a.library), ["Card 2", "Card 3", "Card 0"])
        self.assertIn("Sea Gate Oracle", [p.card.name for p in t.a.battlefield])


class RestIntoGraveyardTests(unittest.TestCase):
    def test_glimpse_the_future_bins_the_other_two(self):
        t = Table(GLIMPSE, "Card 2", library=library(5)).cast()
        self.assertEqual(names(t.a.hand), ["Card 2"])
        self.assertEqual(names(t.a.library), ["Card 3", "Card 4"])
        self.assertEqual(sorted(names(t.a.graveyard)), ["Card 0", "Card 1", "Glimpse the Future"])
        self.assertEqual(sorted(e["card"] for e in t.b.player.events if e["event"] == "milled"), ["Card 0", "Card 1"], "public, as a mill is")

    def test_dark_bargain_takes_two_bins_one_and_hurts(self):
        t = Table(DARK_BARGAIN, "Card 0", "Card 2", library=library(4)).cast()
        self.assertEqual(sorted(names(t.a.hand)), ["Card 0", "Card 2"])
        self.assertEqual(names(t.a.library), ["Card 3"])
        self.assertIn("Card 1", names(t.a.graveyard))
        self.assertEqual(t.a.life, 38)


class FlowStateTests(unittest.TestCase):
    def test_with_an_instant_and_a_sorcery_in_the_graveyard_it_takes_two(self):
        t = Table(FLOW_STATE, "Card 0", "Card 2", graveyard=[INSTANT, SORCERY], library=library(5)).cast()
        self.assertEqual(sorted(names(t.a.hand)), ["Card 0", "Card 2"])
        self.assertEqual(names(t.a.library), ["Card 3", "Card 4", "Card 1"])

    def test_with_only_sorceries_in_the_graveyard_it_takes_one(self):
        t = Table(FLOW_STATE, "Card 0", "Card 2", graveyard=[SORCERY, SORCERY], library=library(5)).cast()
        self.assertEqual(names(t.a.hand), ["Card 0"])
        self.assertEqual(len(t.a.library), 4)

    def test_with_an_empty_graveyard_it_takes_one(self):
        t = Table(FLOW_STATE, "Card 0", "Card 2", library=library(5)).cast()
        self.assertEqual(names(t.a.hand), ["Card 0"])


class ConsultTheStarChartsTests(unittest.TestCase):
    def test_x_is_the_lands_you_control_and_one_card_comes_to_hand(self):
        t = Table(CONSULT, "Card 2", n=3, library=library(6)).cast()  # three lands: the kicker can't be paid, so it isn't offered
        options = next(o for p, o in t.a.player.prompts if p == LOOK_PROMPT)
        self.assertEqual(options, ["Card 0", "Card 1", "Card 2"], "three lands: the top three")
        self.assertEqual(names(t.a.hand), ["Card 2"])
        self.assertEqual(names(t.a.library[:3]), ["Card 3", "Card 4", "Card 5"])
        self.assertEqual(sorted(names(t.a.library[3:])), ["Card 0", "Card 1"])

    def test_kicked_it_takes_two(self):
        t = Table(CONSULT, "Yes", "Card 2", "Card 0", n=4, library=library(6)).cast()
        self.assertEqual(sorted(names(t.a.hand)), ["Card 0", "Card 2"])
        self.assertEqual(names(t.a.library[:2]), ["Card 4", "Card 5"])
        self.assertEqual(sorted(names(t.a.library[2:])), ["Card 1", "Card 3"])

    def test_not_kicked_with_the_same_lands_it_takes_one(self):
        t = Table(CONSULT, "No", "Card 2", "Card 0", n=4, library=library(6)).cast()
        self.assertEqual(names(t.a.hand), ["Card 2"])


if __name__ == "__main__":
    unittest.main()
