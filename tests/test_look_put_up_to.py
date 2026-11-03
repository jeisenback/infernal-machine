""""Look at the top six cards of your library. Put up to two creature cards with mana value 3 or less from among them onto the
battlefield. Put the rest on the bottom of your library in any order." (Collected Company, United Battlefront, Storm the Festival)."""

import unittest

from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, lands, real, run_stack, table3

COMPANY = real("Collected Company", "{3}{G}", "Instant", "Look at the top six cards of your library. Put up to two creature cards with "
               "mana value 3 or less from among them onto the battlefield. Put the rest on the bottom of your library in any order.")
BATTLEFRONT = real("United Battlefront", "{3}{W}", "Sorcery", "Look at the top seven cards of your library. Put up to two noncreature, "
                   "nonland permanent cards with mana value 3 or less from among them onto the battlefield. Put the rest on the bottom "
                   "of your library in a random order.")
BEARS = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", "2", "2")
GIANT = real("Hill Giant", "{3}{R}", "Creature — Giant", "", "3", "3")
ELF = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1")
RING = real("Sol Ring", "{1}", "Artifact", "{T}: Add {C}{C}.")


def cast(spell, library):
    game, _ = table3()
    a = game.seats[0]
    a.hand, a.battlefield, a.library = [spell], lands(6), list(library)
    game._perform(a, CAST + spell.name)
    run_stack(game)
    return a


def entered(seat):
    return sorted(p.card.name for p in seat.battlefield if p.card.name != "City of Brass")


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (COMPANY, BATTLEFRONT):
            self.assertEqual(unsupported_lines(card), [], card.name)


class CollectedCompanyTests(unittest.TestCase):
    def test_two_small_creatures_enter_and_the_rest_go_to_the_bottom(self):
        a = cast(COMPANY, [GIANT, BEARS, FOREST, ELF, BEARS, FOREST, RING])
        self.assertEqual(entered(a), ["Grizzly Bears", "Llanowar Elves"])
        self.assertEqual(a.library[0], RING)  # the seventh card was not looked at
        self.assertEqual(sorted(c.name for c in a.library[1:]), ["Forest", "Forest", "Grizzly Bears", "Hill Giant"])

    def test_a_four_drop_is_never_put(self):
        a = cast(COMPANY, [GIANT, FOREST, FOREST, FOREST, FOREST, FOREST])
        self.assertEqual(entered(a), [])


class UnitedBattlefrontTests(unittest.TestCase):
    def test_only_noncreature_nonland_permanents(self):
        a = cast(BATTLEFRONT, [BEARS, FOREST, RING, ELF, FOREST, FOREST, FOREST])
        self.assertEqual(entered(a), ["Sol Ring"])


if __name__ == "__main__":
    unittest.main()
