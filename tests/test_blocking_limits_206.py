"""Blocking limits (#206): "can't be blocked by creatures with power 2 or less", by a color or type, except by black creatures, by
more than one creature, except by three or more, "can't block creatures with power 3 or greater", and "can't block and can't be
blocked" - each played from the card's own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Combat
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import attack_all, table, table3


def creature(name, text="", power=2, colors=(), types="Creature — Bear"):
    return Card(name=name, mana_cost="{1}", type_line=types, oracle_text=text, power=str(power), toughness="3", colors=colors)


def can_block(attacker, blocker):
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield, b.battlefield = [Permanent(attacker)], [Permanent(blocker)]
    game.combat = Combat(game)
    return game.combat._can_block(b.battlefield[0], a.battlefield[0])


def last(prompt, options):
    return len(options) - 1


class PowerLimitTests(unittest.TestCase):
    def test_not_blocked_by_power_or_less(self):
        attacker = creature("Vanguard", "This creature can't be blocked by creatures with power 2 or less.")
        self.assertFalse(can_block(attacker, creature("Small", power=1)))
        self.assertFalse(can_block(attacker, creature("Even", power=2)))
        self.assertTrue(can_block(attacker, creature("Big", power=3)))

    def test_not_blocked_by_power_or_greater(self):
        attacker = creature("Beastbinder", "This creature can't be blocked by creatures with power 4 or greater.")
        self.assertFalse(can_block(attacker, creature("Huge", power=5)))
        self.assertFalse(can_block(attacker, creature("Exactly", power=4)))
        self.assertTrue(can_block(attacker, creature("Small", power=3)))

    def test_a_pumped_blocker_counts_by_its_power_now(self):
        attacker = creature("Vanguard", "This creature can't be blocked by creatures with power 2 or less.")
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield, b.battlefield = [Permanent(attacker)], [Permanent(creature("Bear"))]
        game.combat = Combat(game)
        from infernal_machine.characteristics import Modifier
        game.modify_until_end_of_turn(b.battlefield[0], Modifier(1, 1))
        self.assertTrue(game.combat._can_block(b.battlefield[0], a.battlefield[0]))

    def test_cant_block_creatures_with_power_or_greater(self):
        blocker = creature("Orcs", "This creature can't block creatures with power 3 or greater.")
        self.assertFalse(can_block(creature("Ogre", power=3), blocker))
        self.assertTrue(can_block(creature("Bear", power=2), blocker))


class TypeAndColorTests(unittest.TestCase):
    def test_not_blocked_by_artifact_creatures(self):
        attacker = creature("Steed", "This creature can't be blocked by artifact creatures.")
        self.assertFalse(can_block(attacker, creature("Golem", types="Artifact Creature — Golem")))
        self.assertTrue(can_block(attacker, creature("Bear")))

    def test_not_blocked_by_walls(self):
        attacker = creature("Juggernaut", "This creature can't be blocked by Walls.")
        self.assertFalse(can_block(attacker, creature("Wall", types="Creature — Wall")))
        self.assertTrue(can_block(attacker, creature("Bear")))

    def test_not_blocked_by_a_color(self):
        attacker = creature("Shade", "This creature can't be blocked by blue creatures.")
        self.assertFalse(can_block(attacker, creature("Merfolk", colors=("U",))))
        self.assertFalse(can_block(attacker, creature("Izzet", colors=("U", "R"))))
        self.assertTrue(can_block(attacker, creature("Elf", colors=("G",))))
        self.assertTrue(can_block(attacker, creature("Colorless")))

    def test_not_blocked_by_flying_creatures(self):
        attacker = creature("Hunter", "This creature can't be blocked by creatures with flying.")
        self.assertFalse(can_block(attacker, creature("Bird", "Flying")))
        self.assertTrue(can_block(attacker, creature("Spider", "Reach")))

    def test_except_by_black_creatures(self):
        attacker = creature("Wraith", "This creature can't be blocked except by black creatures.")
        self.assertTrue(can_block(attacker, creature("Zombie", colors=("B",))))
        self.assertFalse(can_block(attacker, creature("Elf", colors=("G",))))
        self.assertFalse(can_block(attacker, creature("Colorless")))

    def test_except_by_creatures_with_flying(self):
        attacker = creature("Drake", "This creature can't be blocked except by creatures with flying.")
        self.assertTrue(can_block(attacker, creature("Bird", "Flying")))
        self.assertFalse(can_block(attacker, creature("Spider", "Reach")))
        self.assertFalse(can_block(attacker, creature("Bear")))


def blocked_by(attackers, blockers):
    """Each attacker's blockers once every blocker has been assigned (each blocker blocks the last attacker it may)."""
    game, _, _ = table(attack_all, last)
    a, b = game.seats
    a.battlefield = [Permanent(c) for c in attackers]
    b.battlefield = [Permanent(c) for c in blockers]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    return [[p.card.name for p in attack.blockers] for attack in game.combat.attacks], b


class NumberOfBlockersTests(unittest.TestCase):
    def test_cannot_be_blocked_by_more_than_one_creature(self):
        hydra = creature("Hydra", "This creature can't be blocked by more than one creature.", power=5)
        blockers, _ = blocked_by([hydra], [creature("A"), creature("B"), creature("C")])
        self.assertEqual(blockers, [["A"]])  # the other two were not offered the block

    def test_other_attackers_can_be_blocked_by_several(self):
        blockers, _ = blocked_by([creature("Plain", power=5)], [creature("A"), creature("B"), creature("C")])
        self.assertEqual(blockers, [["A", "B", "C"]])

    def test_except_by_three_or_more_creatures(self):
        troll = creature("Troll", "This creature can't be blocked except by three or more creatures.", power=4)
        blockers, _ = blocked_by([troll], [creature("A"), creature("B")])
        self.assertEqual(blockers, [[]])  # two blockers are not enough: it is unblocked instead
        blockers, _ = blocked_by([troll], [creature("A"), creature("B"), creature("C")])
        self.assertEqual(blockers, [["A", "B", "C"]])

    def test_nobody_blocking_is_fine(self):
        troll = creature("Troll", "This creature can't be blocked except by three or more creatures.", power=4)
        self.assertEqual(blocked_by([troll], [])[0], [[]])

    def test_except_by_two_or_more_is_like_menace(self):
        pair = creature("Pair", "This creature can't be blocked except by two or more creatures.", power=3)
        self.assertEqual(blocked_by([pair], [creature("A")])[0], [[]])
        self.assertEqual(blocked_by([pair], [creature("A"), creature("B")])[0], [["A", "B"]])


class CantBlockAndBeBlockedTests(unittest.TestCase):
    def test_it_neither_blocks_nor_is_blocked(self):
        text = "This creature can't block and can't be blocked."
        outcast = creature("Outcast", text)
        self.assertFalse(can_block(creature("Attacker"), outcast))
        self.assertFalse(can_block(outcast, creature("Blocker")))


class ReportTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for text in ("This creature can't be blocked by creatures with power 2 or less.",
                     "This creature can't be blocked by creatures with power 4 or greater.",
                     "This creature can't be blocked by artifact creatures.", "This creature can't be blocked by Walls.",
                     "This creature can't be blocked by blue creatures.", "This creature can't be blocked by creatures with flying.",
                     "This creature can't be blocked except by black creatures.",
                     "This creature can't be blocked except by creatures with flying.",
                     "This creature can't block creatures with power 3 or greater.",
                     "This creature can't be blocked by more than one creature.",
                     "This creature can't be blocked except by three or more creatures.",
                     "This creature can't block and can't be blocked."):
            with self.subTest(text):
                self.assertEqual(unsupported_lines(creature("Test", text)), [])


if __name__ == "__main__":
    unittest.main()
