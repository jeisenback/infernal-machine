"""Kaito, Bane of Nightmares: "During your turn, as long as Kaito has one or more loyalty counters on him, he's a 3/4 Ninja creature and
has hexproof." and "0: Surveil 2. Then draw a card for each opponent who lost life this turn." """

import unittest

from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, end_turn, lands, real, run_stack, table3

KAITO = real("Kaito, Bane of Nightmares", "{2}{U}{B}", "Legendary Planeswalker — Kaito", "Ninjutsu {1}{U}{B} ({1}{U}{B}, Return an "
             "unblocked attacker you control to hand: Put this card onto the battlefield from your hand tapped and attacking.)\nDuring "
             "your turn, as long as Kaito has one or more loyalty counters on him, he's a 3/4 Ninja creature and has hexproof.\n+1: You "
             "get an emblem with \"Ninjas you control get +1/+1.\"\n0: Surveil 2. Then draw a card for each opponent who lost life this "
             "turn.\n−2: Tap target creature. Put two stun counters on it.", colors=("U", "B"))


def table():
    game, _ = table3()
    a, b, c = game.seats
    a.battlefield, a.library = lands(4), [FOREST] * 5
    return game, a, b, c


def kaito(seat):
    return next(p for p in seat.battlefield if p.card.name == KAITO.name)


class KaitoBaneOfNightmaresTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(KAITO), [])

    def test_on_your_turn_he_is_a_three_four_ninja_creature_with_hexproof(self):
        game, a, _, _ = table()
        a.battlefield.append(Permanent(KAITO, loyalty=4))
        game.step = "untap"
        game._turn_based_actions(a)
        walker = kaito(a)
        self.assertEqual((walker.card.type_line, game.power(walker), game.toughness(walker)),
                         ("Legendary Planeswalker Creature — Kaito Ninja", 3, 4))
        self.assertTrue(game.has_keyword(walker, "hexproof"))
        end_turn(game, a)  # the cleanup step: a planeswalker again
        self.assertEqual((walker.card.type_line, game.has_keyword(walker, "hexproof")), ("Legendary Planeswalker — Kaito", False))

    def test_cast_on_your_turn_he_enters_as_a_creature_but_not_on_an_opponents(self):
        game, a, _, _ = table()
        a.hand = [KAITO]
        game._perform(a, CAST + KAITO.name)
        run_stack(game)
        self.assertIn("Creature", kaito(a).card.type_line)
        game, a, _, _ = table()
        game.active = 1
        game._enter(a, Permanent(KAITO, loyalty=4))
        self.assertNotIn("Creature", kaito(a).card.type_line)

    def test_zero_draws_a_card_for_each_opponent_who_lost_life_this_turn(self):
        game, a, b, c = table()
        a.battlefield.append(Permanent(KAITO, loyalty=4))
        b.life_lost_turn, b.life_lost_amount = game.turn, 3
        c.life_lost_turn, c.life_lost_amount = game.turn - 1, 3  # last turn: not counted
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "0: Surveil" in x))
        run_stack(game)
        self.assertEqual(len(a.hand), 1)


if __name__ == "__main__":
    unittest.main()
