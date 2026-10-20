"""The order damage is changed in (CR 616.1): doubling, "plus N" and prevention are all replacement effects, so the player being dealt the
damage (or the controller of the damaged permanent) chooses the order, and is asked only when the order changes the result. Doubling before a
shield of 2 against 3 damage is 4; the shield first is 2."""

import unittest

from infernal_machine.game import DAMAGE_ORDER_PROMPT, Permanent
from tests.helpers import BEAR, FURNACE, OGRE, pick, real, table3, TOMIK


def setup(*cards, policies=()):
    game, players = table3(*policies)
    a, b, _ = game.seats
    ogre = Permanent(OGRE)
    a.battlefield = [Permanent(c) for c in cards] + [ogre]
    return game, players, a, b, ogre


def asked(player):
    return [(prompt, options) for prompt, options in player.prompts if DAMAGE_ORDER_PROMPT.matches(prompt)]


class DamageOrderTests(unittest.TestCase):
    def test_the_least_damage_is_listed_first_and_is_the_default(self):
        game, (_, b_player, _), a, b, ogre = setup(FURNACE)
        game.shield(b, 2)
        game.damage(b, 3, ogre)
        self.assertEqual(b.life, 40 - 2)  # the shield first, then doubled
        (prompt, options), = asked(b_player)
        self.assertEqual(options, ["2 damage (prevention then Furnace of Rath)", "4 damage (Furnace of Rath then prevention)"])

    def test_the_damaged_player_can_choose_the_other_order(self):
        game, _, a, b, ogre = setup(FURNACE, policies=(None, lambda prompt, options: len(options) - 1))
        game.shield(b, 2)
        game.damage(b, 3, ogre)
        self.assertEqual(b.life, 40 - 4)

    def test_the_shield_is_used_up_by_what_it_prevented(self):
        game, _, a, b, ogre = setup(FURNACE)
        game.shield(b, 10)
        game.damage(b, 3, ogre)
        self.assertEqual((b.life, game.shields[0][1]), (40, 7))  # all prevented either way: the order that keeps more of the shield

    def test_doubling_and_adding_are_ordered_too(self):
        game, (_, b_player, _), a, b, ogre = setup(FURNACE, TOMIK)
        game.damage(b, 3, ogre)
        self.assertEqual(b.life, 40 - 7)  # doubled, then plus 1; the other order is 8
        self.assertEqual([len(options) for _, options in asked(b_player)], [2])

    def test_no_question_when_the_order_does_not_matter(self):
        game, (a_player, b_player, _), a, b, ogre = setup(FURNACE)
        game.damage(b, 3, ogre)  # nothing to order it with
        game.shield(b, 2)
        game.damage(a.battlefield[-1], 1, ogre)  # a different target, no shield on it
        self.assertEqual(asked(b_player), [])

    def test_the_controller_of_a_damaged_permanent_chooses(self):
        game, (a_player, b_player, _), a, b, ogre = setup(FURNACE)
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        game.shield(bear, 1)
        game.damage(bear, 2, ogre)
        self.assertEqual((len(asked(b_player)), len(asked(a_player))), (1, 0))
        self.assertEqual(bear.damage, 2)  # (2 - 1) doubled


if __name__ == "__main__":
    unittest.main()
