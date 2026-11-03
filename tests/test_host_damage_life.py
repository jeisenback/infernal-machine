""""Whenever enchanted creature deals damage, you gain that much life." (Spirit Link, Armadillo Cloak)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, real, run_stack, table3

LINK = real("Spirit Link", "{W}", "Enchantment — Aura", "Enchant creature (Target a creature as you cast this. This card enters attached to "
            "that creature.)\nWhenever enchanted creature deals damage, you gain that much life.")
CLOAK = real("Armadillo Cloak", "{1}{G}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +2/+2 and has trample.\n"
             "Whenever enchanted creature deals damage, you gain that much life.")


def table(host_seat=1):
    """Seat 0's Spirit Link on a Bear of `host_seat`."""
    game, _ = table3()
    a, host_owner = game.seats[0], game.seats[host_seat]
    bear, ogre = Permanent(BEAR), Permanent(OGRE)
    link = Permanent(LINK)
    link.attached_to = bear
    host_owner.battlefield = [bear, ogre] if host_owner is not a else [bear, ogre, link]
    if host_owner is not a:
        a.battlefield = [link]
    return game, a, bear, ogre


class SpiritLinkTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (LINK, CLOAK):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_auras_controller_gains_the_damage_dealt_to_a_player(self):
        game, a, bear, _ = table()
        game.damage(game.seats[2], 2, bear, combat=True)
        run_stack(game)
        self.assertEqual([s.life for s in game.seats], [42, 40, 38])

    def test_damage_to_a_creature_counts_too(self):
        game, a, bear, ogre = table(host_seat=0)
        game.damage(ogre, 2, bear)
        run_stack(game)
        self.assertEqual(a.life, 42)

    def test_another_creatures_damage_does_not(self):
        game, a, bear, ogre = table()
        game.damage(game.seats[2], 3, ogre, combat=True)
        run_stack(game)
        self.assertEqual(a.life, 40)


if __name__ == "__main__":
    unittest.main()
