"""Veil of Summer, from its real Oracle text: "Draw a card if an opponent has cast a blue or black spell this turn. Spells you control
can't be countered this turn. You and permanents you control gain hexproof from blue and from black until end of turn." The draw needs an
opponent's blue or black spell this turn; hexproof stops only their blue and black sources, and only this turn."""

import unittest

from infernal_machine.effects import spell_effects
from infernal_machine.game import Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, real, table3

VEIL = real("Veil of Summer", "{G}", "Instant", "Draw a card if an opponent has cast a blue or black spell this turn. Spells you control can't "
            "be countered this turn. You and permanents you control gain hexproof from blue and from black until end of turn.", colors=("G",))
BLUE = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
GREEN = real("Giant Growth", "{G}", "Instant", "Target creature gets +3/+3 until end of turn.", colors=("G",))


def veiled(opponent_cast=None, turn_offset=0):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.library, a.battlefield = [FOREST] * 3, [Permanent(BEAR)]
    if opponent_cast is not None:
        b.cast_log.append((game.turn - turn_offset, opponent_cast))
    for effect in spell_effects(VEIL):
        effect.resolve(game, a, None)
    return game, a, b


class VeilOfSummerTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(VEIL), [])

    def test_it_draws_only_after_an_opponents_blue_or_black_spell_this_turn(self):
        for cast, offset, drawn in ((BLUE, 0, 1), (GREEN, 0, 0), (BLUE, 1, 0), (None, 0, 0)):
            _, a, _ = veiled(cast, offset)
            self.assertEqual(len(a.hand), drawn, (cast and cast.name, offset))

    def test_your_spells_cant_be_countered_this_turn(self):
        game, a, b = veiled()
        self.assertEqual((game.uncounterable(StackItem(BEAR, a)), game.uncounterable(StackItem(BEAR, b))), (True, False))
        game.turn += 1
        self.assertFalse(game.uncounterable(StackItem(BEAR, a)))

    def test_you_and_your_permanents_have_hexproof_from_blue_and_black(self):
        game, a, b = veiled()
        bear = a.battlefield[0]
        targets = lambda kind, colors, caster=b: [t for _, t in game.target_options(kind, caster, frozenset(colors))]
        self.assertNotIn(bear, targets("creature", "U"))
        self.assertNotIn(a, targets("player", "B"))
        self.assertEqual((bear in targets("creature", "R"), a in targets("player", "R"), bear in targets("creature", "U", a)), (True, True, True))
        game.turn += 1
        self.assertIn(bear, targets("creature", "U"))


if __name__ == "__main__":
    unittest.main()
