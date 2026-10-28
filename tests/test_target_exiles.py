"""Strategic Betrayal: a targeted opponent exiles a creature of their choice and their graveyard (#564 row 11)."""

import unittest

from infernal_machine.effects import TargetExiles, spell_effects
from infernal_machine.game import CAST, EXILE_CHOICE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, lands, pick, real, run_stack, table3

BETRAYAL = real("Strategic Betrayal", "{1}{B}", "Sorcery", "Target opponent exiles a creature they control and their graveyard.")
SPELL = real("Spent Spell", "{B}", "Instant", "")


def cast(theirs, graveyard=(), choose="Ogre"):
    """A casts the Betrayal at B, who has `theirs` and `graveyard` and exiles the creature starting with `choose`."""
    game, (_, b_player, _) = table3(pick("Player: B"), pick(choose))
    a, b, c = game.seats
    a.hand, a.battlefield, a.graveyard = [BETRAYAL], lands(2), [SPELL]
    b.battlefield, b.graveyard = list(theirs), list(graveyard)
    c.battlefield = [Permanent(BEAR)]
    game._perform(a, CAST + "Strategic Betrayal")
    run_stack(game)
    return game, a, b, c, b_player


class ParseTests(unittest.TestCase):
    def test_the_card_is_read(self):
        self.assertEqual(unsupported_lines(BETRAYAL), [])
        self.assertEqual(spell_effects(BETRAYAL), [TargetExiles("opponent", "creature", graveyard=True)])
        plain = real("Plain", "{B}", "Sorcery", "Target player exiles an artifact they control.")
        self.assertEqual(spell_effects(plain), [TargetExiles("player", "artifact")])


class ResolveTests(unittest.TestCase):
    def test_the_opponent_chooses_the_creature_and_loses_their_graveyard(self):
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        game, a, b, c, b_player = cast([bear, ogre], graveyard=[FOREST])
        self.assertTrue(any(EXILE_CHOICE_PROMPT.matches(p) for p, _ in b_player.prompts))
        self.assertEqual(b.battlefield, [bear])
        self.assertEqual(b.exile, [OGRE, FOREST])  # the creature first, then the graveyard
        self.assertEqual(b.graveyard, [])
        self.assertEqual(a.graveyard, [SPELL, BETRAYAL])  # the caster's graveyard is untouched
        self.assertEqual(len(c.battlefield), 1)  # the other opponent is untouched

    def test_with_no_creature_the_graveyard_still_goes(self):
        game, a, b, c, b_player = cast([], graveyard=[FOREST, OGRE])
        self.assertFalse(any(EXILE_CHOICE_PROMPT.matches(p) for p, _ in b_player.prompts))
        self.assertEqual(b.exile, [FOREST, OGRE])
        self.assertEqual(b.graveyard, [])

    def test_the_only_creature_is_the_only_choice(self):
        bear = Permanent(BEAR)
        game, a, b, c, b_player = cast([bear], graveyard=[FOREST], choose="Bear")
        self.assertEqual(b.battlefield, [])
        self.assertEqual(b.exile, [BEAR, FOREST])

    def test_only_an_opponent_can_be_targeted(self):
        game, _ = table3()
        a = game.seats[0]
        self.assertNotIn(a, [t for _, t in game.target_options("opponent", a)])


if __name__ == "__main__":
    unittest.main()
