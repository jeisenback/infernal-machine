"""Distribute counters among creatures (Verdurous Gearhulk, The Earth Crystal, Grove's Bounty, Spoils of War)."""

import unittest

from infernal_machine.effects import DistributeCounters, spell_effects
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, real, run_stack, script, table3, TROLL

GEARHULK = real("Verdurous Gearhulk", "{3}{G}{G}", "Artifact Creature — Construct", "Trample\nWhen this creature enters, distribute four +1/+1 "
                "counters among any number of target creatures you control.", "4", "4")
CRYSTAL = real("The Earth Crystal", "{3}{G}{G}", "Legendary Artifact", "{4}{G}{G}, {T}: Distribute two +1/+1 counters among one or two target "
               "creatures you control.")
BOUNTY = real("Grove's Bounty", "{X}{G}{G}", "Sorcery — Adventure", "Distribute X +1/+1 counters among any number of target creatures you control.")
SPOILS = real("Spoils of War", "{X}{G}", "Sorcery", "Distribute X +1/+1 counters among any number of target creatures.")
RITE = real("Elven Rite", "{G}{G}", "Sorcery", "Distribute two +1/+1 counters among one or two target creatures.")
FLYTRAP = real("Wurm Forger", "{3}{G}", "Creature — Treefolk", "When this creature enters, distribute three +1/+1 counters among one, two, or three "
               "other target creatures you control.", "2", "2")


def counters(p):
    return p.counters.get("+1/+1", 0)


def board(*mine, theirs=(), policy=None):
    game, _ = table3(policy or script("Pass"))
    a, b = game.seats[:2]
    a.hand, a.graveyard = [], []
    a.battlefield = [Permanent(c, sick=False) for c in mine]
    b.battlefield = [Permanent(c, sick=False) for c in theirs]
    return game, a, b


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (GEARHULK, CRYSTAL, BOUNTY, SPOILS, RITE, FLYTRAP):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_effect_is_read(self):
        self.assertEqual(spell_effects(RITE), [DistributeCounters(2, "+1/+1", "creature")])
        self.assertEqual(spell_effects(BOUNTY), [DistributeCounters("X", "+1/+1", "creature you control")])


class ResolveTests(unittest.TestCase):
    def test_the_counters_can_all_go_on_one_creature(self):
        game, a, b = board(BEAR, OGRE, policy=script("Bear", "Bear", "Bear", "Bear"))
        game._enter(a, Permanent(GEARHULK))
        run_stack(game)
        bear = next(p for p in a.battlefield if p.card is BEAR)
        self.assertEqual(counters(bear), 4)

    def test_or_be_split_among_several(self):
        game, a, b = board(BEAR, OGRE, policy=script("Bear", "Ogre", "Bear", "Ogre"))
        game._enter(a, Permanent(GEARHULK))
        run_stack(game)
        self.assertEqual([counters(p) for p in a.battlefield if p.card in (BEAR, OGRE)], [2, 2])

    def test_it_may_go_on_the_gearhulk_itself(self):
        game, a, b = board(policy=script("Verdurous", "Verdurous", "Verdurous", "Verdurous"))
        game._enter(a, Permanent(GEARHULK))
        run_stack(game)
        self.assertEqual(counters(a.battlefield[0]), 4)

    def test_only_your_creatures_when_the_text_says_so(self):
        game, a, b = board(BEAR, theirs=[OGRE])
        DistributeCounters(3, "+1/+1", "creature you control").resolve(game, a, None)
        self.assertEqual(counters(a.battlefield[0]), 3)
        self.assertEqual(counters(b.battlefield[0]), 0)

    def test_a_creature_that_cannot_be_targeted_is_left_out(self):
        game, a, b = board(BEAR, theirs=[TROLL], policy=lambda prompt, options: len(options) - 1)
        DistributeCounters(2, "+1/+1", "creature").resolve(game, a, None)
        self.assertEqual(counters(b.battlefield[0]), 0)
        self.assertEqual(counters(a.battlefield[0]), 2)

    def test_protection_from_the_color_of_the_source_leaves_a_creature_out(self):
        pro_green = real("Pro Green", "{1}", "Creature — Test", "Protection from green", "1", "1")
        game, a, b = board(theirs=[pro_green], policy=lambda prompt, options: 0)
        game.resolving_colors = frozenset("G")
        DistributeCounters(2, "+1/+1", "creature").resolve(game, a, None)
        self.assertEqual(counters(b.battlefield[0]), 0)

    def test_x_is_the_x_of_the_spell(self):
        game, a, b = board(BEAR)
        game.x_value = 3
        DistributeCounters("X", "+1/+1", "creature you control").resolve(game, a, None)
        self.assertEqual(counters(a.battlefield[0]), 3)

    def test_with_no_creature_nothing_happens(self):
        game, a, b = board()
        DistributeCounters(2, "+1/+1", "creature you control").resolve(game, a, None)

    def test_other_creatures_leaves_out_the_source(self):
        game, a, b = board(FLYTRAP, BEAR)
        game.resolving_source = a.battlefield[0]
        DistributeCounters(2, "+1/+1", "creature you control", another=True).resolve(game, a, None)
        self.assertEqual([counters(p) for p in a.battlefield], [0, 2])


if __name__ == "__main__":
    unittest.main()
