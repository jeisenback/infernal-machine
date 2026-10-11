"""Small leftovers: creatures that have to block (Lure, Nemesis Mask, Roar of Challenge, Torchling) and a creature stunning itself."""

import unittest

from infernal_machine.effects import LureThisTurn, MustBlockThisTurn, PutStunOnSource, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, BIRD, OGRE, fight, names
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real

NEMESIS = real("Nemesis Mask", "{3}", "Artifact — Equipment", "All creatures able to block equipped creature do so.\nEquip {3}")
LURE_AURA = real("Lure Aura", "{1}{G}{G}", "Enchantment — Aura", "Enchant creature\nAll creatures able to block enchanted creature do so.")
ROAR = real("Roar of Challenge", "{2}{G}", "Sorcery", "All creatures able to block target creature this turn do so.")
TORCHLING = real("Torchling", "{3}{R}", "Creature — Shapeshifter", "{R}: Target creature blocks this creature this turn if able.", "1", "1")
PEEMA = real("Dare", "{1}{R}", "Sorcery", "Target creature blocks this turn if able.")
HAMMERSKULL = real("Pugnacious Skull", "{1}{R}", "Creature — Dinosaur", "Whenever this creature attacks, put a stun counter on it.", "3", "3")


def never_block(prompt, options):
    return 0  # "Don't block" is always the first option


def attack_with_everything(prompt, options):
    return 1 if options and options[0] == "Don't attack" else 0


def fight_never_blocking(attackers, blockers, before=lambda game, a, b: None):
    """Combat in which the defender would never choose to block; `before` sets up the forced blocks."""
    from tests.test_effects import table
    game, _, _ = table(attack_with_everything, never_block)
    a, b = game.seats
    a.battlefield = [Permanent(c) if not isinstance(c, Permanent) else c for c in attackers]
    b.battlefield = [Permanent(c) if not isinstance(c, Permanent) else c for c in blockers]
    before(game, a, b)
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    return game, a, b


def blockers_of(game):
    return [sorted(b.card.name for b in attack.blockers) for attack in game.combat.attacks]


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (LURE_AURA, NEMESIS, ROAR, TORCHLING, PEEMA, HAMMERSKULL):
            self.assertEqual(unsupported_lines(card), [], card.name)


class LureTests(unittest.TestCase):
    def test_without_it_nobody_blocks(self):
        game, a, b = fight_never_blocking([BEAR], [OGRE, BEAR])
        self.assertEqual(blockers_of(game), [[]])

    def test_an_aura_makes_every_able_creature_block_its_host(self):
        def attach(game, a, b):
            a.battlefield.append(Permanent(LURE_AURA, attached_to=a.battlefield[0]))
        game, a, b = fight_never_blocking([BEAR], [OGRE, BEAR], attach)
        self.assertEqual(blockers_of(game), [["Bear", "Ogre"]])

    def test_an_equipment_does_too(self):
        def equip(game, a, b):
            a.battlefield.append(Permanent(NEMESIS, attached_to=a.battlefield[0]))
        game, a, b = fight_never_blocking([BEAR], [OGRE], equip)
        self.assertEqual(blockers_of(game), [["Ogre"]])

    def test_an_aura_that_is_not_attached_to_the_attacker_does_nothing(self):
        def other(game, a, b):
            a.battlefield.append(Permanent(LURE_AURA, attached_to=a.battlefield[1]))
        game, a, b = fight_never_blocking([BEAR, OGRE], [BEAR], other)
        self.assertEqual(blockers_of(game), [[], ["Bear"]])

    def test_a_creature_that_cannot_block_it_is_not_forced(self):
        def attach(game, a, b):
            a.battlefield.append(Permanent(LURE_AURA, attached_to=a.battlefield[0]))
        game, a, b = fight_never_blocking([BIRD], [OGRE, BEAR], attach)  # nothing there has reach or flying
        self.assertEqual(blockers_of(game), [[]])

    def test_a_spell_does_it_for_this_turn_only(self):
        def roar(game, a, b):
            LureThisTurn().resolve(game, a, a.battlefield[0])
        game, a, b = fight_never_blocking([BEAR], [OGRE], roar)
        self.assertEqual(blockers_of(game), [["Ogre"]])
        game, a, b = fight_never_blocking([BEAR], [OGRE], lambda game, a, b: (roar(game, a, b), setattr(game, "turn", game.turn + 1)))
        self.assertEqual(blockers_of(game), [[]])


class MustBlockTests(unittest.TestCase):
    def test_the_target_creature_blocks_if_able(self):
        def dare(game, a, b):
            MustBlockThisTurn().resolve(game, a, b.battlefield[0])
        game, a, b = fight_never_blocking([BEAR], [OGRE, BEAR], dare)
        self.assertEqual(blockers_of(game), [["Ogre"]])  # only the one that was dared

    def test_it_must_block_the_creature_that_made_it_in_particular(self):
        def torch(game, a, b):
            game.resolving_source = a.battlefield[1]
            MustBlockThisTurn("creature", source_only=True).resolve(game, a, b.battlefield[0])
            game.resolving_source = None
        game, a, b = fight_never_blocking([BEAR, OGRE], [BEAR], torch)
        self.assertEqual(blockers_of(game), [[], ["Bear"]])  # the Ogre was the one that dared it

    def test_if_the_attacker_is_not_attacking_it_may_block_what_it_likes(self):
        def torch(game, a, b):
            game.resolving_source = Permanent(TORCHLING)  # stays at home
            MustBlockThisTurn("creature", source_only=True).resolve(game, a, b.battlefield[0])
            game.resolving_source = None
        game, a, b = fight_never_blocking([BEAR], [OGRE], torch)
        self.assertEqual(blockers_of(game), [[]])

    def test_only_this_turn(self):
        def dare(game, a, b):
            MustBlockThisTurn().resolve(game, a, b.battlefield[0])
            game.turn += 1
        game, a, b = fight_never_blocking([BEAR], [OGRE], dare)
        self.assertEqual(blockers_of(game), [[]])


class StunItselfTests(unittest.TestCase):
    def test_a_creature_that_stuns_itself_when_it_attacks(self):
        self.assertEqual([type(e) for e in triggered_abilities(HAMMERSKULL)[0].effects], [PutStunOnSource])
        game, a, b = fight_never_blocking([HAMMERSKULL], [])
        run_stack(game)
        self.assertEqual(a.battlefield[0].counters.get("stun"), 1)
        self.assertTrue(a.battlefield[0].tapped)

    def test_a_stun_counter_that_follows_a_target_still_follows_it(self):
        from infernal_machine.effects import PutStunCounters
        card = real("Freezer", "{2}{U}", "Creature — Wizard", "When this creature enters, tap target creature an opponent controls and put a stun counter on it.", "2", "2")
        self.assertEqual([type(e).__name__ for e in triggered_abilities(card)[0].effects], ["Tap", "PutStunCounters"])
        self.assertIs(PutStunCounters.follows_target, True)


if __name__ == "__main__":
    unittest.main()
