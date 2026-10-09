"""Alchemy "conjure" for the prepare cards of issue #85: Galathul Galecaller, Crescendo Conductor and Ursine Guide.

A conjured card is looked up when the deck loads (so nothing is fetched mid-game) and marked as conjured, which is what
"a spell that isn't from your starting deck" asks about. Lines are the cards' own Oracle text from Scryfall.
"""

import dataclasses
import unittest

from infernal_machine.cards import Card, CardNotFound, Deck, load_deck
from infernal_machine.effects import triggered_abilities
from infernal_machine.game import CAST, Game, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_cast_events import BOLT
from tests.test_effects import lands
from tests.test_exile import COMMANDER
from tests.test_game import ScriptedPlayer
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import half, prepper, supported
from tests.test_x_targets import script

STORM_CROW = Card(name="Storm Crow", mana_cost="{1}{U}", cmc=2.0, type_line="Creature — Bird", oracle_text="Flying",
                  power="1", toughness="2", colors=("U",))
BEAR_CUB = Card(name="Bear Cub", mana_cost="{1}{G}", cmc=2.0, type_line="Creature — Bear", power="2", toughness="2",
                colors=("G",))

SQUALL = half("Corvid Squall", "Conjure a card named Storm Crow onto the battlefield.")
CALLER = Card(name="Galecaller // Corvid Squall", mana_cost="{2}", type_line="Creature — Wizard", power="1", toughness="1",
              prepare=SQUALL)
CONDUCTOR = prepper("Reach\nWhenever you conjure one or more cards, this creature becomes prepared.", "Conductor")
URSINE = prepper("This creature enters prepared.\nWhenever you cast a spell that isn't from your starting deck, conjure a card "
                 "named Bear Cub onto the battlefield. This creature becomes prepared.", "Ursine")


def conjuring_table(**conjurable):
    game, _ = table3(script(CAST + "Corvid Squall"))
    game.seats[0].conjurable = conjurable
    return game, game.seats[0]


class ParseTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for card in (CALLER, CONDUCTOR, URSINE):
            supported(self, card)
        self.assertEqual(unsupported_lines(SQUALL), [])

    def test_the_conjure_event_and_the_starting_deck_watch(self):
        self.assertIn("conjure", [a.event for a in triggered_abilities(CONDUCTOR)])
        watch = next(a.watch for a in triggered_abilities(URSINE) if a.event == "cast")
        self.assertTrue(watch.not_starting_deck)


class ConjureTests(unittest.TestCase):
    def test_the_spell_puts_the_named_card_onto_the_battlefield(self):
        game, a = conjuring_table(**{"Storm Crow": STORM_CROW})
        a.hand, a.battlefield = [SQUALL], lands(1)
        game._priority_round(a)
        [crow] = [p for p in a.battlefield if p.card.name == "Storm Crow"]
        self.assertEqual((crow.card.conjured, crow.sick), (True, True))
        self.assertFalse(STORM_CROW.conjured)  # the definition itself is untouched

    def test_a_card_that_cannot_be_found_does_nothing(self):
        game, a = conjuring_table()
        a.hand, a.battlefield = [SQUALL], lands(1)
        game._priority_round(a)
        self.assertEqual([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], [])

    def test_conjuring_prepares_crescendo_conductor(self):
        game, a = conjuring_table(**{"Storm Crow": STORM_CROW})
        conductor = Permanent(CONDUCTOR)
        a.battlefield = [conductor]
        game.conjure(a, "Storm Crow")
        run_stack(game)
        self.assertTrue(conductor.prepared)

    def test_conjuring_nothing_leaves_it_unprepared(self):
        game, a = conjuring_table()
        conductor = Permanent(CONDUCTOR)
        a.battlefield = [conductor]
        game.conjure(a, "Storm Crow")
        run_stack(game)
        self.assertFalse(conductor.prepared)

    def test_an_opponents_conjuring_does_not_prepare_it(self):
        game, a = conjuring_table()
        game.seats[1].conjurable = {"Storm Crow": STORM_CROW}
        conductor = Permanent(CONDUCTOR)
        a.battlefield = [conductor]
        game.conjure(game.seats[1], "Storm Crow")
        run_stack(game)
        self.assertFalse(conductor.prepared)


class StartingDeckTests(unittest.TestCase):
    def cast(self, card):
        game, a = conjuring_table(**{"Bear Cub": BEAR_CUB})
        ursine = Permanent(URSINE)
        a.battlefield = [ursine]
        a.cast_log.append((game.turn, card))
        game._observe("cast", card, a)
        run_stack(game)
        return a, ursine

    def test_a_conjured_spell_conjures_a_cub_and_prepares_it(self):
        a, ursine = self.cast(dataclasses.replace(BOLT, conjured=True))
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Bear Cub"], ["Bear Cub"])
        self.assertTrue(ursine.prepared)

    def test_a_spell_from_the_starting_deck_does_nothing(self):
        a, ursine = self.cast(BOLT)
        self.assertEqual([p.card.name for p in a.battlefield], ["Ursine // Quick Study"])
        self.assertFalse(ursine.prepared)


class FakeSource:
    def __init__(self, *cards):
        self.cards = {c.name: c for c in cards}

    def get(self, name):
        if name not in self.cards:
            raise CardNotFound(name)
        return self.cards[name]

    def get_many(self, names):
        names = list(dict.fromkeys(names))
        if missing := [n for n in names if n not in self.cards]:
            raise CardNotFound(", ".join(missing))
        return {n: self.cards[n] for n in names}


class DeckTests(unittest.TestCase):
    def test_the_deck_loads_the_cards_its_text_conjures(self):
        deck = load_deck("1 Galecaller // Corvid Squall", FakeSource(CALLER, STORM_CROW))
        self.assertEqual(deck.conjured, {"Storm Crow": STORM_CROW})

    def test_a_card_that_cannot_be_found_is_left_out(self):
        deck = load_deck("1 Galecaller // Corvid Squall", FakeSource(CALLER))
        self.assertEqual(deck.conjured, {})

    def test_a_deck_without_conjuring_conjures_nothing(self):
        self.assertEqual(load_deck("1 Storm Crow", FakeSource(STORM_CROW)).conjured, {})

    def test_each_seat_gets_its_decks_cards(self):
        deck = Deck(commanders=[COMMANDER], main=[STORM_CROW] * 20, sideboard=[], conjured={"Bear Cub": BEAR_CUB})
        other = Deck(commanders=[COMMANDER], main=[STORM_CROW] * 20, sideboard=[])
        game = Game([(ScriptedPlayer("A"), deck), (ScriptedPlayer("B"), other)], seed=1)
        self.assertEqual((game.seats[0].conjurable, game.seats[1].conjurable), ({"Bear Cub": BEAR_CUB}, {}))
