""""If CARDNAME would be put into a graveyard from anywhere, reveal CARDNAME and shuffle it into its owner's library instead." (CR 614.1,
614.12): Blightsteel Colossus, Progenitus and Nexus of Fate."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, Table, pick, real, table3

LINE = "If {0} would be put into a graveyard from anywhere, reveal {0} and shuffle it into its owner's library instead."
BLIGHTSTEEL = real("Blightsteel Colossus", "{12}", "Artifact Creature — Phyrexian Golem",
                   "Trample, infect, indestructible\n" + LINE.format("Blightsteel Colossus"), "11", "11")
PROGENITUS = real("Progenitus", "{W}{W}{U}{U}{B}{B}{R}{R}{G}{G}", "Legendary Creature — Hydra Avatar",
                  "Protection from everything\n" + LINE.format("Progenitus"), "10", "10")
NEXUS = real("Nexus of Fate", "{5}{U}{U}", "Instant", "Take an extra turn after this one.\n" + LINE.format("Nexus of Fate"))


def names(cards):
    return [c.name for c in cards]


class ShuffleReplacementTests(unittest.TestCase):
    def setUp(self):
        self.game, _ = table3()
        self.a = self.game.seats[0]
        self.a.library = []

    def test_the_cards_are_understood(self):
        for card in (BLIGHTSTEEL, PROGENITUS, NEXUS):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_creature_that_leaves_the_battlefield_is_shuffled_in_and_does_not_die(self):
        colossus = Permanent(BLIGHTSTEEL)
        self.a.battlefield = [colossus]
        self.game._leave_battlefield(colossus, "sacrificed")
        self.assertEqual((names(self.a.library), self.a.graveyard), (["Blightsteel Colossus"], []))
        self.assertEqual(self.game.deaths_count, 0)

    def test_a_discarded_card_is_shuffled_in(self):
        self.a.hand = [BLIGHTSTEEL]
        self.game.discard(self.a, None)
        self.assertEqual((names(self.a.library), self.a.graveyard), (["Blightsteel Colossus"], []))

    def test_a_milled_card_is_shuffled_back_in(self):
        self.a.library = [BLIGHTSTEEL, BEAR]
        self.game.mill(self.a, 1)
        self.assertEqual(sorted(names(self.a.library)), ["Bear", "Blightsteel Colossus"])
        self.assertEqual(self.a.graveyard, [])

    def test_the_spell_is_shuffled_in_after_it_resolves(self):
        t = Table(NEXUS, n=7, policy=pick("Pass")).cast()
        self.assertEqual((names(t.a.library).count("Nexus of Fate"), t.a.graveyard), (1, []))
        self.assertEqual(t.game.extra_turns, [0])

    def test_other_cards_still_go_to_the_graveyard(self):
        bear = Permanent(BEAR)
        self.a.battlefield = [bear]
        self.game._leave_battlefield(bear, "sacrificed")
        self.assertEqual((names(self.a.graveyard), self.a.library), (["Bear"], []))

    def test_a_commander_may_go_to_the_command_zone_instead(self):
        for answer, zone in (("Command", "command_zone"), ("Library", "library")):
            game, (player, *_) = table3(pick(answer))
            a = game.seats[0]
            a.library, a.commander_names = [], {"Progenitus"}
            game._move_card(a, PROGENITUS, "graveyard")
            self.assertEqual(names(getattr(a, zone)), ["Progenitus"], answer)
            self.assertEqual(a.graveyard, [])
            self.assertIn(["Command zone", "Library"], [options for _, options in player.prompts])


if __name__ == "__main__":
    unittest.main()
