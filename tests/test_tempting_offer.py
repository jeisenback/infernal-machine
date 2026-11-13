"""Tempting offer, from the cards' real Oracle text: the caster does it, each opponent may do it for themselves, and the caster does it
again for each opponent who did (Tempt with Discovery, Tempt with Vengeance, Tempt with Bunnies, Tempt with Glory)."""

import unittest

from infernal_machine.cards import Deck
from infernal_machine.bot import BotPlayer
from infernal_machine.effects import TEMPT_PROMPT
from infernal_machine.game import CAST, X_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, lands, real, run_stack, table3

DISCOVERY = real("Tempt with Discovery", "{3}{G}", "Sorcery", "Tempting offer — Search your library for a land card and put it onto the "
                 "battlefield. Each opponent may search their library for a land card and put it onto the battlefield. For each opponent who "
                 "searches a library this way, search your library for a land card and put it onto the battlefield. Then each player who "
                 "searched a library this way shuffles.", colors=("G",))
VENGEANCE = real("Tempt with Vengeance", "{X}{R}", "Sorcery", "Tempting offer — Create X 1/1 red Elemental creature tokens with haste. Each "
                 "opponent may create X 1/1 red Elemental creature tokens with haste. For each opponent who does, create X 1/1 red Elemental "
                 "creature tokens with haste.", colors=("R",))
BUNNIES = real("Tempt with Bunnies", "{2}{W}", "Sorcery", "Tempting Offer — Draw a card and create a 1/1 white Rabbit creature token. Then "
               "each opponent may draw a card and create a 1/1 white Rabbit creature token. For each opponent who does, you draw a card and "
               "you create a 1/1 white Rabbit creature token.", colors=("W",))
GLORY = real("Tempt with Glory", "{5}{W}", "Sorcery", "Tempting offer — Put a +1/+1 counter on each creature you control. Each opponent may "
             "put a +1/+1 counter on each creature they control. For each opponent who does, put a +1/+1 counter on each creature you "
             "control.", colors=("W",))
CARDS = (DISCOVERY, VENGEANCE, BUNNIES, GLORY)


def answering(accept):
    """Policy: accept (or decline) a tempting offer; X is 2; otherwise the first option."""
    def policy(prompt, options):
        if TEMPT_PROMPT.matches(prompt):
            return 0 if accept else 1
        if X_PROMPT.matches(prompt):
            return options.index("2")
        return 0
    return policy


def cast(card, b_accepts, c_accepts, setup=lambda game: None):
    game, _ = table3(answering(False), answering(b_accepts), answering(c_accepts))
    a = game.seats[0]
    setup(game)
    a.battlefield += lands(6)
    a.hand = [card]
    game._perform(a, CAST + card.name)
    run_stack(game)
    return game


def tokens(seat, name):
    return sum(p.card.name == name and p.card.type_line.startswith("Token") for p in seat.battlefield)


class TemptingOfferTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_an_offer_whose_sentences_differ_is_not_read(self):
        odd = real("Odd Offer", "{1}", "Sorcery", "Tempting offer — Draw a card. Each opponent may draw two cards. For each opponent who "
                   "does, draw a card.")
        self.assertNotEqual(unsupported_lines(odd), [])

    def test_tempt_with_vengeance_once_for_you_and_again_for_each_opponent_who_accepts(self):
        game = cast(VENGEANCE, True, False)
        a, b, c = game.seats
        self.assertEqual((tokens(a, "Elemental"), tokens(b, "Elemental"), tokens(c, "Elemental")), (4, 2, 0))

    def test_tempt_with_discovery_finds_lands_for_whoever_searches(self):
        def libraries(game):
            for seat in game.seats:
                seat.library = [FOREST] * 5
        game = cast(DISCOVERY, True, True, libraries)
        a, b, c = game.seats
        found = lambda seat: sum(p.card is FOREST for p in seat.battlefield)  # noqa: E731
        self.assertEqual((found(a), found(b), found(c)), (3, 1, 1))

    def test_tempt_with_bunnies_when_nobody_accepts(self):
        def libraries(game):
            game.seats[0].library = [FOREST] * 5
        game = cast(BUNNIES, False, False, libraries)
        a = game.seats[0]
        self.assertEqual((tokens(a, "Rabbit"), len(a.hand)), (1, 1))

    def test_tempt_with_glory_counts_each_players_own_creatures(self):
        bear_a, bear_b = Permanent(BEAR), Permanent(BEAR)
        def creatures(game):
            game.seats[0].battlefield, game.seats[1].battlefield = [bear_a], [bear_b]
        cast(GLORY, True, True, creatures)
        self.assertEqual((bear_a.counters.get("+1/+1"), bear_b.counters.get("+1/+1")), (3, 1))

    def test_the_bot_declines_a_tempting_offer(self):
        bot = BotPlayer("Bot", Deck(commanders=[], main=[], sideboard=[]))
        self.assertEqual(bot.choose(TEMPT_PROMPT("Tempt with Vengeance"), ["Yes", "No"]), 1)


if __name__ == "__main__":
    unittest.main()
