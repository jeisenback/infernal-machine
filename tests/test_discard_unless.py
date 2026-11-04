""""Then discard two cards unless you discard an artifact card." (Thirst for Knowledge), "... unless you discard an instant or sorcery card
or a creature card with flying." (Steamcore Scholar)."""

import unittest

from infernal_machine.game import DISCARD_UNLESS_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, enter, real, run_stack, table3

SCHOLAR = real("Steamcore Scholar", "{2}{U}", "Creature — Weird Detective", "Flying, vigilance\nWhen this creature enters, draw two cards. "
               "Then discard two cards unless you discard an instant or sorcery card or a creature card with flying.", "2", "2")
THIRST = real("Thirst for Knowledge", "{2}{U}", "Instant", "Draw three cards. Then discard two cards unless you discard an artifact card.")
BIRD = real("Storm Crow", "{1}{U}", "Creature — Bird", "Flying", "1", "2")
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def scholar(first, library):
    game, _ = table3(lambda prompt, options: options.index(first) if DISCARD_UNLESS_PROMPT.matches(prompt) else 0)
    a = game.seats[0]
    a.hand, a.graveyard, a.library = [], [], list(library)
    enter(game, a, SCHOLAR)
    run_stack(game)
    return a


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SCHOLAR, THIRST):
            self.assertEqual(unsupported_lines(card), [], card.name)


class SteamcoreScholarTests(unittest.TestCase):
    def test_discarding_an_instant_is_enough(self):
        a = scholar("Lightning Bolt", [BOLT, OGRE])
        self.assertEqual((a.hand, a.graveyard), ([OGRE], [BOLT]))

    def test_a_creature_with_flying_is_enough(self):
        a = scholar("Storm Crow", [BIRD, OGRE])
        self.assertEqual(a.hand, [OGRE])

    def test_anything_else_means_two(self):
        a = scholar("Bear", [BEAR, FOREST])
        self.assertEqual(a.hand, [])
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Forest"])


if __name__ == "__main__":
    unittest.main()
