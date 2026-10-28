"""Plot (CR 702.170): at sorcery speed pay the plot cost to exile a card from the hand, then cast it from exile on a later turn as a sorcery
without paying its mana cost."""

import unittest

from infernal_machine.effects import plot_of
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, table3, script

PLOT_TEXT = " (You may pay {1}{G} and exile this card from your hand. Cast it as a sorcery on a later turn without paying its mana cost. Plot only as a sorcery.)"
VARMINTS = real("Rise of the Varmints", "{3}{G}", "Sorcery",
                "Create X 2/1 green Varmint creature tokens, where X is the number of creature cards in your graveyard.\n"
                "Plot {2}{G} (You may pay {2}{G} and exile this card from your hand. Cast it as a sorcery on a later turn without paying its mana cost. Plot only as a sorcery.)")
OUTCASTER = real("Beastbond Outcaster", "{2}{G}", "Creature — Human Druid",
                 "When this creature enters, if you control a creature with power 4 or greater, draw a card.\nPlot {1}{G}" + PLOT_TEXT, "3", "3")
FLASH = real("Probe Instant", "{1}{G}", "Instant", "You gain 3 life.\nPlot {1}" + PLOT_TEXT)
PLAIN = real("Plain Sorcery", "{2}{R}", "Sorcery", "You gain 1 life.")


def table(*hand, mana=3, turn=2, step="main1"):
    game, _ = table3(script("Pass"))
    a = game.seats[0]
    a.hand, a.graveyard, a.exile, a.plotted = list(hand), [], [], []
    a.library = [BEAR] * 4
    a.battlefield = lands(mana)
    game.turn, game.step = turn, step
    return game, a


def plot(card):
    return "Plot: " + card.name


def cast_plotted(card):
    return "Cast plotted: " + card.name


def next_turn(game, seat):
    game.turn += 1
    for permanent in seat.battlefield:
        permanent.tapped = False


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood_and_the_cost_read(self):
        self.assertEqual(plot_of(VARMINTS), "{2}{G}")
        self.assertIsNone(plot_of(PLAIN))
        for card in (VARMINTS, OUTCASTER):
            self.assertEqual(unsupported_lines(card), [], card.name)


class BotTests(unittest.TestCase):
    def test_the_bot_plots_when_nothing_else_is_left_and_casts_the_plotted_card_free(self):
        from infernal_machine.bot import BotPlayer
        from infernal_machine.cards import Deck
        bot = BotPlayer("Bot", Deck([], [VARMINTS, BEAR], []))
        bot.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 20})
        options = ["Pass", plot(VARMINTS)]
        self.assertEqual(options[bot.choose("Priority: main1", options)], plot(VARMINTS))
        options = ["Pass", cast_plotted(VARMINTS)]
        self.assertEqual(options[bot.choose("Priority: main1", options)], cast_plotted(VARMINTS))


class NarrationTests(unittest.TestCase):
    def test_plotting_reads_as_a_sentence(self):
        from infernal_machine.client import Narrator
        narrator = Narrator()
        narrator.names[0] = "Ann"
        self.assertEqual(narrator.narrate({"event": "plotted", "seat": 0, "card": "Rise of the Varmints"}), "Ann plots Rise of the Varmints.")
        narrator.me = 0
        self.assertEqual(narrator.narrate({"event": "plotted", "seat": 0, "card": "Rise of the Varmints"}), "You plot Rise of the Varmints.")


class PlotTests(unittest.TestCase):
    def test_it_goes_to_exile_for_the_plot_cost(self):
        game, a = table(VARMINTS, mana=3)
        self.assertIn(plot(VARMINTS), game.legal_actions(a))
        game._perform(a, plot(VARMINTS))
        self.assertEqual((a.hand, a.exile, a.plotted), ([], [VARMINTS], [(2, VARMINTS)]))
        self.assertEqual(len(game._mana_sources(a)), 0, "all three lands paid {2}{G}")

    def test_not_without_the_mana(self):
        game, a = table(VARMINTS, mana=2)
        self.assertNotIn(plot(VARMINTS), game.legal_actions(a))

    def test_only_at_sorcery_speed(self):
        game, a = table(VARMINTS, mana=3, step="combat_damage")
        self.assertNotIn(plot(VARMINTS), game.legal_actions(a))
        game, a = table(VARMINTS, mana=3)
        game.active = 1
        self.assertNotIn(plot(VARMINTS), game.legal_actions(a), "not on an opponent's turn")

    def test_a_card_without_plot_is_not_offered(self):
        game, a = table(PLAIN, mana=3)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith("Plot")], [])


class CastPlottedTests(unittest.TestCase):
    def plotted(self, *cards, mana=3):
        game, a = table(*cards, mana=mana)
        game._perform(a, plot(cards[0]))
        return game, a

    def test_not_on_the_turn_it_was_plotted(self):
        game, a = self.plotted(VARMINTS)
        self.assertNotIn(cast_plotted(VARMINTS), game.legal_actions(a))

    def test_on_a_later_turn_it_is_cast_without_paying_and_leaves_exile(self):
        game, a = self.plotted(VARMINTS)
        a.graveyard = [BEAR, BEAR]
        next_turn(game, a)
        a.battlefield = []  # not one land: it is free
        self.assertIn(cast_plotted(VARMINTS), game.legal_actions(a))
        game._perform(a, cast_plotted(VARMINTS))
        run_stack(game)
        self.assertEqual((a.exile, a.plotted), ([], []))
        self.assertEqual(sum(p.card.name == "Varmint" for p in a.battlefield), 2)

    def test_a_creature_plotted_enters_without_mana_being_spent(self):
        game, a = self.plotted(OUTCASTER, mana=2)
        next_turn(game, a)
        game._perform(a, cast_plotted(OUTCASTER))
        run_stack(game)
        self.assertTrue(any(p.card is OUTCASTER for p in a.battlefield))
        self.assertEqual(len(game._mana_sources(a)), 2, "both lands are still untapped: nothing was paid")

    def test_an_instant_can_only_be_cast_plotted_at_sorcery_speed(self):
        game, a = self.plotted(FLASH, mana=2)
        next_turn(game, a)
        game.step = "combat_damage"
        self.assertNotIn(cast_plotted(FLASH), game.legal_actions(a))
        game.step = "main1"
        self.assertIn(cast_plotted(FLASH), game.legal_actions(a))

    def test_the_opponent_cannot_cast_it(self):
        game, a = self.plotted(VARMINTS)
        next_turn(game, a)
        self.assertEqual([x for x in game.legal_actions(game.seats[1]) if "plotted" in x], [])


if __name__ == "__main__":
    unittest.main()
