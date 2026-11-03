""""Artifacts and creatures entering don't cause abilities to trigger." (Doorkeeper Thrull), "Creatures entering ..." (Torpor Orb)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, enter, real, run_stack, table3

THRULL = real("Doorkeeper Thrull", "{1}{W}", "Creature — Thrull", "Flash\nFlying\nArtifacts and creatures entering don't cause abilities to "
              "trigger.", "1", "2")
ORB = real("Torpor Orb", "{2}", "Artifact", "Creatures entering don't cause abilities to trigger.")
VISIONARY = real("Elvish Visionary", "{1}{G}", "Creature — Elf Shaman", "When this creature enters, draw a card.", "1", "1")
WARDEN = real("Soul Warden", "{W}", "Creature — Human Cleric", "Whenever another creature enters, you gain 1 life.", "1", "1")
REFRACTOR = real("Energy Refractor", "{2}", "Artifact", "When this artifact enters, draw a card.\n{2}: Add one mana of any color.")


def table(*battlefield):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.hand, a.library = [], [OGRE] * 5
    b.battlefield = [Permanent(card) for card in battlefield]
    return game, a


def enters(game, a, card):
    enter(game, a, card)
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (THRULL, ORB):
            self.assertEqual(unsupported_lines(card), [], card.name)


class DoorkeeperThrullTests(unittest.TestCase):
    def test_a_creature_entering_triggers_nothing(self):
        game, a = table(THRULL)
        a.battlefield = [Permanent(WARDEN)]
        enters(game, a, VISIONARY)
        self.assertEqual((a.hand, a.life), ([], 40))

    def test_an_artifact_entering_triggers_nothing(self):
        game, a = table(THRULL)
        enters(game, a, REFRACTOR)
        self.assertEqual(a.hand, [])

    def test_without_it_they_trigger(self):
        game, a = table()
        a.battlefield = [Permanent(WARDEN)]
        enters(game, a, VISIONARY)
        self.assertEqual((a.hand, a.life), ([OGRE], 41))


class TorporOrbTests(unittest.TestCase):
    def test_a_creature_entering_triggers_nothing(self):
        game, a = table(ORB)
        enters(game, a, VISIONARY)
        self.assertEqual(a.hand, [])

    def test_an_artifact_entering_still_triggers(self):
        game, a = table(ORB)
        enters(game, a, REFRACTOR)
        self.assertEqual(a.hand, [OGRE])


if __name__ == "__main__":
    unittest.main()
