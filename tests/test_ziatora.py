"""Ziatora, the Incinerator, from its real Oracle text: "At the beginning of your end step, you may sacrifice another creature. When you
do, Ziatora deals damage equal to that creature's power to any target and you create three Treasure tokens." The damage is a reflexive
trigger (CR 603.12) that chooses its target after the sacrifice, and counts the sacrificed creature's last power (CR 608.2h). Declining,
or having no other creature, does nothing."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, fire, pick, real, table3

ZIATORA = real("Ziatora, the Incinerator", "{3}{B}{R}{G}", "Legendary Creature — Demon Dragon", "Flying\nAt the beginning of your end step, "
               "you may sacrifice another creature. When you do, Ziatora deals damage equal to that creature's power to any target and you "
               "create three Treasure tokens.", "6", "6", colors=("B", "R", "G"))


def end_step(policy, *others):
    game, _ = table3(policy)
    a = game.seats[0]
    ziatora = Permanent(ZIATORA)
    a.battlefield = [ziatora, *[Permanent(c) for c in others]]
    fire(game, a, ziatora, "end_step")
    return game, a


def treasures(seat):
    return sum(p.card.name == "Treasure" for p in seat.battlefield)


class ZiatoraTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(ZIATORA), [])

    def test_sacrificing_another_creature_deals_its_power_and_makes_three_treasures(self):
        game, a = end_step(pick("Yes", "Ogre", "Player: B"), OGRE)
        self.assertEqual((game.seats[1].life, treasures(a), [c.name for c in a.graveyard]), (37, 3, ["Ogre"]))

    def test_declining_does_nothing(self):
        game, a = end_step(pick("No"), OGRE)
        self.assertEqual(([s.life for s in game.seats], treasures(a), a.graveyard), ([40, 40, 40], 0, []))

    def test_alone_it_does_nothing(self):
        game, a = end_step(pick("Yes", "Player: B"))
        self.assertEqual(([s.life for s in game.seats], treasures(a)), ([40, 40, 40], 0))


if __name__ == "__main__":
    unittest.main()
