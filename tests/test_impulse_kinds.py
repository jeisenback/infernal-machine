""""You may reveal a colorless card from among them and put it into your hand." (Ancient Stirrings), "You may reveal any number of creature
cards from among them and put the revealed cards into your hand." (Lead the Stampede)."""

import unittest

from infernal_machine.game import CAST, LOOK_PROMPT, NONE_TAKEN
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, lands, real, run_stack, table3

STIRRINGS = real("Ancient Stirrings", "{G}", "Sorcery", "Look at the top five cards of your library. You may reveal a colorless card from "
                 "among them and put it into your hand. Then put the rest on the bottom of your library in any order.")
STAMPEDE = real("Lead the Stampede", "{2}{G}", "Sorcery", "Look at the top five cards of your library. You may reveal any number of creature "
                "cards from among them and put the revealed cards into your hand. Put the rest on the bottom of your library in any order.")
BEARS = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
GOLEM = real("Bronze Golem", "{3}", "Artifact Creature — Golem", "", "2", "2")
RING = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")


def cast(spell, library, policy=None):
    game, _ = table3(policy)
    a = game.seats[0]
    a.hand, a.battlefield, a.library = [spell], lands(3), list(library)
    game._perform(a, CAST + spell.name)
    run_stack(game)
    return a


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (STIRRINGS, STAMPEDE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class AncientStirringsTests(unittest.TestCase):
    def test_only_colorless_cards_are_offered(self):
        offered = []

        def policy(prompt, options):
            if LOOK_PROMPT.matches(prompt):
                offered.append(sorted(options))
            return 0
        a = cast(STIRRINGS, [BEARS, RING, FOREST, BEARS, BEARS], policy)
        self.assertEqual(offered, [sorted(["Sol Ring", "Forest", NONE_TAKEN])])  # a land is colorless too
        self.assertEqual(len(a.hand), 1)


class LeadTheStampedeTests(unittest.TestCase):
    def test_every_creature_may_be_taken(self):
        a = cast(STAMPEDE, [BEARS, RING, GOLEM, BEARS, FOREST])
        self.assertEqual(sorted(c.name for c in a.hand), ["Bronze Golem", "Grizzly Bears", "Grizzly Bears"])
        self.assertEqual(sorted(c.name for c in a.library), ["Forest", "Sol Ring"])


if __name__ == "__main__":
    unittest.main()
