"""The Reaver Cleaver, from its real Oracle text: "Equipped creature gets +1/+1 and has trample and "Whenever this creature deals combat
damage to a player or planeswalker, create that many Treasure tokens."" A pump, a keyword and a quoted trigger in one line: the equipped
Bear is 3/3 with trample and makes a Treasure for each point it deals to a player, and none when a blocker takes it all."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, attack_all, real, run_stack, table

CLEAVER = real("The Reaver Cleaver", "{2}{R}", "Legendary Artifact — Equipment", 'Equipped creature gets +1/+1 and has trample and "Whenever '
               "this creature deals combat damage to a player or planeswalker, create that many Treasure tokens.\"\nEquip {3}", colors=("R",))


def attack_with_cleaver(*blockers):
    game, _, _ = table(attack_all, attack_all)
    a, b = game.seats[0], game.seats[1]
    bear = Permanent(BEAR)
    a.battlefield = [bear, Permanent(CLEAVER, attached_to=bear)]
    b.battlefield = [Permanent(c) for c in blockers]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    game.combat.deal_damage(False)
    run_stack(game)
    return game, a, b, bear


def treasures(seat):
    return sum(p.card.name == "Treasure" for p in seat.battlefield)


class ReaverCleaverTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(CLEAVER), [])

    def test_the_equipped_creature_is_bigger_and_has_trample(self):
        game, _, _ = table()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(CLEAVER, attached_to=bear)]
        self.assertEqual((game.power(bear), game.toughness(bear), game.has_keyword(bear, "trample")), (3, 3, True))

    def test_combat_damage_to_a_player_makes_that_many_treasures(self):
        game, a, b, _ = attack_with_cleaver()
        self.assertEqual((b.life, treasures(a)), (37, 3))

    def test_a_blocker_that_takes_it_all_makes_none(self):
        game, a, b, _ = attack_with_cleaver(OGRE)  # 3 damage, all needed by the 3/3 Ogre: none tramples over
        self.assertEqual((b.life, treasures(a)), (40, 0))


if __name__ == "__main__":
    unittest.main()
