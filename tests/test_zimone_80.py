"""Zimone, All-Questioning (issue #80): at your end step, if a land entered under your control this turn and you control a
prime number of lands, create Primo, the Indivisible with that many +1/+1 counters. The line is the card's own Oracle text
from Scryfall (without the reminder text)."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import card, fire, FOREST, lands, pick, table3, triggers_80_supported as supported

ZIMONE = card("At the beginning of your end step, if a land entered the battlefield under your control this turn and you "
              "control a prime number of lands, create Primo, the Indivisible, a legendary 0/0 green and blue Fractal creature "
              "token, then put that many +1/+1 counters on it.", "Zimone")


class ZimoneTests(unittest.TestCase):
    def table(self, land_count, enter_land=True):
        game, _ = table3(pick())
        a = game.seats[0]
        zimone = Permanent(ZIMONE)
        a.battlefield = [zimone] + lands(land_count - (1 if enter_land else 0))
        if enter_land:
            game._enter(a, Permanent(FOREST))
        game.pending.clear()
        fire(game, a, zimone, "end_step")
        return a

    def primo(self, seat):
        return [p for p in seat.battlefield if p.card.name == "Primo, the Indivisible"]

    def test_parse(self):
        supported(self, ZIMONE)

    def test_primo_comes_in_with_a_counter_for_each_land(self):
        for count in (2, 3, 5, 7):
            [primo] = self.primo(self.table(count))
            self.assertEqual(primo.counters.get("+1/+1"), count)

    def test_it_is_a_legendary_green_and_blue_fractal(self):
        [primo] = self.primo(self.table(3))
        self.assertEqual((primo.card.type_line, primo.card.colors), ("Legendary Token Creature — Fractal", ("G", "U")))

    def test_a_number_that_is_not_prime_makes_nothing(self):
        for count in (1, 4, 6, 9):
            self.assertEqual(self.primo(self.table(count)), [], count)

    def test_no_land_entering_this_turn_makes_nothing(self):
        self.assertEqual(self.primo(self.table(3, enter_land=False)), [])

    def test_a_land_entering_under_an_opponents_control_does_not_count(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        zimone = Permanent(ZIMONE)
        a.battlefield = [zimone] + lands(3)
        game._enter(b, Permanent(FOREST))
        fire(game, a, zimone, "end_step")
        self.assertEqual(self.primo(a), [])

    def test_a_land_that_entered_on_an_earlier_turn_does_not_count(self):
        game, _ = table3(pick())
        a = game.seats[0]
        zimone = Permanent(ZIMONE)
        a.battlefield = [zimone] + lands(2)
        game._enter(a, Permanent(FOREST))
        game.turn += 1
        fire(game, a, zimone, "end_step")
        self.assertEqual(self.primo(a), [])
