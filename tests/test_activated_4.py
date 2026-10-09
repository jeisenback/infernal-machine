"""Mana abilities of issue #73 that were still unsupported: spending restrictions (Troyan, Elementalist's Palette),
extra costs (Gilded Goose's Food, Millikin's mill) and one mana for each counter (Astral Cornucopia). Real Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.mana import parse_cost
from tests.real import REAL
from tests.test_effects import table

FOOD = Card(name="Food", type_line="Artifact — Food")
CHEAP = Card(name="Cheap Spell", mana_cost="{3}", cmc=3, type_line="Sorcery")
BIG = Card(name="Big Spell", mana_cost="{3}{G}{U}", cmc=5, type_line="Sorcery")
X_SPELL = Card(name="X Spell", mana_cost="{X}{G}", type_line="Sorcery")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def seat_with(*cards, library=0):
    game = table()[0]
    seat = game.seats[0]
    seat.battlefield = [Permanent(c) for c in cards]
    seat.library = [Card(name=f"Card {i}", type_line="Sorcery") for i in range(library)]
    return game, seat


def can_pay(game, seat, spell):
    return game._payment(seat, spell) is not None


class SpendingRestrictionTests(unittest.TestCase):
    def test_troyan_mana_pays_for_a_big_spell(self):
        game, seat = seat_with(REAL["Troyan, Gutsy Explorer"], *[FOREST] * 3)
        self.assertTrue(can_pay(game, seat, BIG))  # 5 mana: {G}{U} from Troyan and three lands

    def test_troyan_mana_cannot_pay_for_a_small_spell(self):
        game, seat = seat_with(REAL["Troyan, Gutsy Explorer"], *[FOREST] * 2)
        self.assertFalse(can_pay(game, seat, CHEAP))  # the lands make only 2 of 3

    def test_troyan_mana_pays_for_a_spell_with_x(self):
        game, seat = seat_with(REAL["Troyan, Gutsy Explorer"], FOREST)
        self.assertTrue(can_pay(game, seat, X_SPELL))

    def test_troyan_mana_cannot_pay_an_abilitys_cost(self):
        game, seat = seat_with(REAL["Troyan, Gutsy Explorer"])
        self.assertIsNone(game._pay_cost(seat, parse_cost("{G}")))


class ExtraCostTests(unittest.TestCase):
    def test_gilded_goose_sacrifices_a_food_for_mana(self):
        game, seat = seat_with(REAL["Gilded Goose"], FOOD)
        cost = parse_cost("{U}")
        game._spend_mana(seat, game._pay_cost(seat, cost))
        self.assertEqual([p.card.name for p in seat.battlefield], ["Gilded Goose"])
        self.assertTrue(seat.battlefield[0].tapped)

    def test_gilded_goose_makes_no_mana_without_a_food(self):
        game, seat = seat_with(REAL["Gilded Goose"])
        self.assertIsNone(game._pay_cost(seat, parse_cost("{U}")))

    def test_two_geese_need_two_foods(self):
        game, seat = seat_with(REAL["Gilded Goose"], REAL["Gilded Goose"], FOOD)
        self.assertIsNone(game._pay_cost(seat, parse_cost("{U}{G}")))

    def test_millikin_mills_a_card_for_colorless(self):
        game, seat = seat_with(REAL["Millikin"], library=3)
        game._spend_mana(seat, game._pay_cost(seat, parse_cost("{1}")))
        self.assertEqual((len(seat.library), len(seat.graveyard)), (2, 1))

    def test_millikin_with_an_empty_library_makes_no_mana(self):
        game, seat = seat_with(REAL["Millikin"])
        self.assertIsNone(game._pay_cost(seat, parse_cost("{1}")))


class CounterManaTests(unittest.TestCase):
    def test_astral_cornucopia_makes_a_mana_for_each_charge_counter(self):
        game, seat = seat_with(REAL["Astral Cornucopia"])
        seat.battlefield[0].counters["charge"] = 3
        self.assertIsNotNone(game._pay_cost(seat, parse_cost("{1}{G}{U}")))
        self.assertIsNone(game._pay_cost(seat, parse_cost("{1}{G}{U}{R}")))

    def test_astral_cornucopia_without_counters_makes_nothing(self):
        game, seat = seat_with(REAL["Astral Cornucopia"])
        self.assertIsNone(game._pay_cost(seat, parse_cost("{1}")))

    def test_palette_charge_mana_pays_only_for_x_spells(self):
        game, seat = seat_with(REAL["Elementalist's Palette"])
        seat.battlefield[0].counters["charge"] = 2
        self.assertTrue(can_pay(game, seat, Card(name="X", mana_cost="{X}", type_line="Sorcery")))
        self.assertFalse(can_pay(game, seat, Card(name="Two", mana_cost="{2}", type_line="Sorcery")))

    def test_palette_always_makes_one_mana_of_any_color(self):
        game, seat = seat_with(REAL["Elementalist's Palette"])
        self.assertIsNotNone(game._pay_cost(seat, parse_cost("{R}")))


if __name__ == "__main__":
    unittest.main()
