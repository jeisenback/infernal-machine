"""Norn's Decree, from its real Oracle text: "Whenever one or more creatures an opponent controls deal combat damage to you, that opponent
gets a poison counter." (once, however many of their creatures hit you; not when your creatures hit them) and "Whenever a player attacks,
if one or more players being attacked are poisoned, the attacking player draws a card." (not when no player attacked is poisoned)."""

import unittest

from infernal_machine.combat import Attack
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, attack_all, run_stack, real, table3

DECREE = real("Norn's Decree", "{2}{W}", "Enchantment", "Whenever one or more creatures an opponent controls deal combat damage to you, that "
              "opponent gets a poison counter.\nWhenever a player attacks, if one or more players being attacked are poisoned, the attacking "
              "player draws a card.", None, None, colors=("W",))


def table():
    """Seat 0 has Norn's Decree; every seat has a library and attacks the first opponent it is offered with everything."""
    game, _ = table3(attack_all, attack_all, attack_all)
    a, b, c = game.seats
    a.battlefield = [Permanent(DECREE)]
    for seat in game.seats:
        seat.library = [BEAR] * 5
    return game, a, b, c


def poison(seat):
    return seat.player_counters.get("poison", 0)


def bears(seat, n):
    made = [Permanent(BEAR, sick=False) for _ in range(n)]
    seat.battlefield += made
    return made


class CombatDamageTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(DECREE), [])

    def test_an_opponents_creatures_hitting_you_give_them_one_poison_counter(self):
        game, a, b, c = table()
        game.combat.attacks = [Attack(bear, b, a) for bear in bears(b, 2)]
        game.combat.deal_damage(first_strike_step=False)
        run_stack(game)
        self.assertEqual((poison(a), poison(b), poison(c)), (0, 1, 0))

    def test_your_creatures_hitting_an_opponent_give_nobody_poison(self):
        game, a, b, c = table()
        game.combat.attacks = [Attack(bears(a, 1)[0], a, b)]
        game.combat.deal_damage(first_strike_step=False)
        run_stack(game)
        self.assertEqual((poison(a), poison(b), poison(c)), (0, 0, 0))


class AttackTests(unittest.TestCase):
    def attack(self, poisoned):
        """Seat 2 attacks seat 0 (the first opponent offered), who has `poisoned` poison counters: how many cards each seat drew."""
        game, a, b, c = table()
        a.player_counters["poison"] = poisoned
        bears(c, 1)
        hands = [len(s.hand) for s in game.seats]
        game.combat.declare_attackers(c)
        run_stack(game)
        return [len(s.hand) - n for s, n in zip(game.seats, hands)]

    def test_attacking_a_poisoned_player_draws_the_attacker_a_card(self):
        self.assertEqual(self.attack(1), [0, 0, 1])

    def test_attacking_an_unpoisoned_player_draws_nothing(self):
        self.assertEqual(self.attack(0), [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
