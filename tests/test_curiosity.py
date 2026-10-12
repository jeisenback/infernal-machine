"""Curiosity and Sleeper's Robe: "Whenever enchanted creature deals [combat] damage to an opponent, you may draw a card." The opponent is
the Aura's controller's opponent, whoever controls the creature."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, pick, real, run_stack, table3

CURIOSITY = real("Curiosity", "{U}", "Enchantment — Aura", "Enchant creature\nWhenever enchanted creature deals damage to an opponent, "
                 "you may draw a card.")
ROBE = real("Sleeper's Robe", "{1}{U}", "Enchantment — Aura", "Enchant creature\nEnchanted creature has fear. (It can't be blocked "
            "except by artifact creatures and/or black creatures.)\nWhenever enchanted creature deals combat damage to an opponent, you may draw a card.")


def setup(aura, answer="Yes"):
    """Seat 0 controls the Aura on its own Ogre; returns (game, a, b, ogre)."""
    game, _ = table3(pick(answer))
    a, b, _ = game.seats
    ogre = Permanent(OGRE)
    a.battlefield = [ogre, Permanent(aura, attached_to=ogre)]
    a.library = [Card(name=f"Card {i}", type_line="Land") for i in range(5)]
    return game, a, b, ogre


def hit(game, target, amount, source, combat=False):
    game.damage(target, amount, source, combat)
    run_stack(game)


class CuriosityTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (CURIOSITY, ROBE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_any_damage_to_an_opponent_draws(self):
        game, a, b, ogre = setup(CURIOSITY)
        hit(game, b, 2, ogre)
        self.assertEqual(len(a.hand), 1)
        hit(game, b, 2, ogre, combat=True)
        self.assertEqual(len(a.hand), 2)

    def test_you_may_decline(self):
        game, a, b, ogre = setup(CURIOSITY, "No")
        hit(game, b, 2, ogre)
        self.assertEqual(len(a.hand), 0)

    def test_not_for_damage_to_a_creature_or_to_its_own_controller_or_none(self):
        game, a, b, ogre = setup(CURIOSITY)
        bear = Permanent(OGRE)
        b.battlefield = [bear]
        hit(game, bear, 2, ogre)
        hit(game, a, 2, ogre)
        hit(game, b, 0, ogre)
        self.assertEqual(len(a.hand), 0)

    def test_not_for_damage_from_another_creature(self):
        game, a, b, ogre = setup(CURIOSITY)
        other = Permanent(OGRE)
        a.battlefield.append(other)
        hit(game, b, 2, other)
        self.assertEqual(len(a.hand), 0)

    def test_opponent_means_an_opponent_of_the_auras_controller(self):
        game, a, b, ogre = setup(CURIOSITY)
        theirs = Permanent(OGRE)
        b.battlefield = [theirs]
        a.battlefield[1].attached_to = theirs  # Curiosity (controlled by seat 0) on seat 1's creature
        hit(game, a, 2, theirs)  # it hurts the Aura's controller: no draw
        self.assertEqual(len(a.hand), 0)
        hit(game, b, 2, theirs)  # it hurts its own controller, an opponent of the Aura's controller: draw
        self.assertEqual(len(a.hand), 1)

    def test_sleepers_robe_is_combat_damage_only(self):
        game, a, b, ogre = setup(ROBE)
        hit(game, b, 2, ogre)
        self.assertEqual(len(a.hand), 0)
        hit(game, b, 2, ogre, combat=True)
        self.assertEqual(len(a.hand), 1)


if __name__ == "__main__":
    unittest.main()
