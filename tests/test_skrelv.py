"""Skrelv, Defector Mite, from its real Oracle text: "{W/P}, {T}: Choose a color. Another target creature you control gains toxic 1 and
hexproof from that color until end of turn. It can't be blocked by creatures of that color this turn." With black chosen: the creature
poisons a player it hits, a black creature can't block it but a green one can, and an opponent's black spell can't target it but a green
one (or its controller's) can; Skrelv can't target itself."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, real, run_stack, table3

SKRELV = real("Skrelv, Defector Mite", "{W}", "Legendary Artifact Creature — Phyrexian Mite", "Toxic 1 (Players dealt combat damage by "
              "this creature also get a poison counter.)\nSkrelv can't block.\n{W/P}, {T}: Choose a color. Another target creature you "
              "control gains toxic 1 and hexproof from that color until end of turn. It can't be blocked by creatures of that color this "
              "turn. ({W/P} can be paid with either {W} or 2 life.)", "1", "1", colors=("W",))
BLACK = Card(name="Black Bear", type_line="Creature — Bear", power="2", toughness="2", colors=("B",))
GREEN = Card(name="Green Bear", type_line="Creature — Bear", power="2", toughness="2", colors=("G",))


def shielded():
    """Seat 0 activates Skrelv on its Bear, choosing black; returns the game, its seats and the Bear."""
    game, _ = table3(pick("Black", "Bear"))
    a, b, c = game.seats
    bear = Permanent(BEAR, sick=False)
    a.battlefield = [Permanent(SKRELV, sick=False), bear] + lands(1)
    game.step, game.active = "main1", a.index
    (action,) = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Skrelv")]
    game._perform(a, action)
    run_stack(game)
    return game, a, b, c, bear


class SkrelvTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(SKRELV), [])

    def test_skrelv_cannot_target_itself(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(SKRELV, sick=False)] + lands(1)
        game.step, game.active = "main1", a.index
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Skrelv")], [])

    def test_it_gains_toxic(self):
        game, a, b, _, bear = shielded()
        game.combat.attacks = [Attack(bear, a, b)]
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual(b.player_counters.get("poison", 0), 1)

    def test_creatures_of_that_color_cannot_block_it(self):
        game, a, b, _, bear = shielded()
        black, green = Permanent(BLACK), Permanent(GREEN)
        b.battlefield = [black, green]
        self.assertEqual((game.combat._can_block(black, bear), game.combat._can_block(green, bear)), (False, True))

    def test_it_has_hexproof_from_that_color(self):
        game, a, b, _, bear = shielded()
        def targetable(caster, colors):
            return bear in [p for _, p in game.target_options("creature", caster, frozenset(colors))]
        self.assertEqual((targetable(b, {"B"}), targetable(b, {"G"}), targetable(a, {"B"})), (False, True, True))


if __name__ == "__main__":
    unittest.main()
