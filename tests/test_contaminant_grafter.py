"""Contaminant Grafter, from its real Oracle text: "Whenever one or more creatures you control deal combat damage to one or more players,
proliferate." Once for the damage step, however many players were hit; not when your creatures hit no player, nor when an opponent's
creatures hit you."""

import unittest

from infernal_machine.combat import Attack
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, real, run_stack, table3

GRAFTER = real("Contaminant Grafter", "{4}{G}", "Creature — Phyrexian Druid", "Trample, toxic 1\nWhenever one or more creatures you "
               "control deal combat damage to one or more players, proliferate.\nCorrupted — At the beginning of your end step, if an "
               "opponent has three or more poison counters, draw a card, then you may put a land card from your hand onto the battlefield.",
               "5", "5", colors=("G",))


def combat(attacks):
    """Seat 0 has Contaminant Grafter with a +1/+1 counter; `attacks(a, b, c)` lists the attacks; combat damage is dealt."""
    game, _ = table3()
    a, b, c = game.seats
    grafter = Permanent(GRAFTER, counters={"+1/+1": 1})
    a.battlefield = [grafter]
    game.combat.attacks = attacks(game, a, b, c)
    game.combat.deal_damage(first_strike_step=False)
    run_stack(game)
    return grafter


def bear(seat):
    seat.battlefield.append(creature := Permanent(BEAR, sick=False))
    return creature


class ContaminantGrafterTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(GRAFTER), [])

    def test_hitting_two_players_proliferates_once(self):
        grafter = combat(lambda game, a, b, c: [Attack(bear(a), a, b), Attack(bear(a), a, c)])
        self.assertEqual(grafter.counters["+1/+1"], 2)

    def test_no_player_hit_or_an_opponent_hitting_you_does_not(self):
        def blocked(game, a, b, c):
            return [Attack(bear(a), a, b, blockers=[bear(b)], blocked=True)]
        self.assertEqual(combat(blocked).counters["+1/+1"], 1)
        self.assertEqual(combat(lambda game, a, b, c: [Attack(bear(b), b, a)]).counters["+1/+1"], 1)


if __name__ == "__main__":
    unittest.main()
