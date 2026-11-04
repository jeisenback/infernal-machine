""""At the beginning of each opponent's upkeep, untap a creature you control. If you've completed a dungeon, untap all creatures you control
instead." (White Plume Adventurer)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, fire, real, table3

ADVENTURER = real("White Plume Adventurer", "{2}{W}", "Creature — Orc Cleric", "When this creature enters, you take the initiative.\nAt the "
                  "beginning of each opponent's upkeep, untap a creature you control. If you've completed a dungeon, untap all creatures "
                  "you control instead.", "3", "3", colors=("W",))


def opponents_upkeep(completed):
    game, _ = table3(lambda prompt, options: 0)
    a = game.seats[0]
    adventurer, bear, ogre = Permanent(ADVENTURER), Permanent(BEAR, tapped=True), Permanent(OGRE, tapped=True)
    a.battlefield, a.dungeons_completed = [adventurer, bear, ogre], completed
    fire(game, a, adventurer, "opponent_upkeep")
    return [p.tapped for p in (bear, ogre)]


class WhitePlumeAdventurerTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(ADVENTURER), [])

    def test_one_creature_untaps(self):
        self.assertEqual(sorted(opponents_upkeep(0)), [False, True])

    def test_after_a_dungeon_all_untap(self):
        self.assertEqual(opponents_upkeep(1), [False, False])

    def test_venturing_out_of_the_last_room_completes_the_undercity(self):
        game, _ = table3(lambda prompt, options: 0)
        a = game.seats[0]
        a.undercity_room = "Throne of the Dead Three"
        game.venture(a)
        self.assertEqual(a.dungeons_completed, 1)


if __name__ == "__main__":
    unittest.main()
