"""Impractical Joke: damage can't be prevented this turn, then 3 damage to up to one target creature or planeswalker (#564 row 15)."""

import unittest

from infernal_machine.effects import Damage, NoPreventionThisTurn, spell_effects
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, Table, creature, real

JOKE = real("Impractical Joke", "{R}", "Sorcery", "Damage can't be prevented this turn. Impractical Joke deals 3 damage to up to one target "
                                                  "creature or planeswalker.")
WALL = creature("Wall", 2, 6)


def hurt(game, victim, amount, source=None, combat=False):
    before = victim.damage if isinstance(victim, Permanent) else victim.life
    game.damage(victim, amount, source=source, combat=combat)
    return (victim.damage - before) if isinstance(victim, Permanent) else (before - victim.life)


class ParseTests(unittest.TestCase):
    def test_the_card_is_read(self):
        self.assertEqual(unsupported_lines(JOKE), [])
        self.assertEqual(spell_effects(JOKE), [NoPreventionThisTurn(), Damage(3, "creature or planeswalker", optional_target=True)])


class NoPreventionTests(unittest.TestCase):
    def test_a_shielded_creature_takes_the_damage(self):
        wall = Permanent(WALL)
        t = Table(JOKE, "Wall", theirs=[wall])
        t.game.shield(wall, 10)
        t.cast()
        self.assertEqual(wall.damage, 3)

    def test_a_fog_and_a_shield_on_a_player_stop_working_for_the_turn(self):
        t = Table(JOKE, theirs=[])  # no target: the spell still resolves
        t.game.fog_turn = t.game.turn
        t.game.shield(t.b, 10)
        t.cast()
        self.assertEqual(hurt(t.game, t.b, 2, source=Permanent(BEAR), combat=True), 2)
        self.assertEqual(hurt(t.game, t.b, 2), 2)

    def test_prevention_works_again_next_turn(self):
        t = Table(JOKE, theirs=[])
        t.cast()
        t.game.turn += 1
        t.game.shield(t.b, 10)
        self.assertEqual(hurt(t.game, t.b, 2), 0)

    def test_without_the_joke_the_shield_holds(self):
        t = Table(JOKE, theirs=[])
        t.game.shield(t.b, 10)
        self.assertEqual(hurt(t.game, t.b, 2), 0)


if __name__ == "__main__":
    unittest.main()
