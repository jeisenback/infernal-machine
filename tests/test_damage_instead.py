""""CARDNAME deals N damage instead if <condition>." after a damage sentence: Galvanic Blast (Metalcraft), Unholy Heat (Delirium)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import RELIC, lands, pick, real, run_stack, table3

BLAST = real("Galvanic Blast", "{R}", "Instant", "Galvanic Blast deals 2 damage to any target.\nMetalcraft — Galvanic Blast deals 4 "
             "damage instead if you control three or more artifacts.")
HEAT = real("Unholy Heat", "{R}", "Instant", "Unholy Heat deals 2 damage to target creature or planeswalker.\nDelirium — Unholy Heat "
            "deals 6 damage instead if there are four or more card types among cards in your graveyard.")


def blast(artifacts, lose_one=False):
    """Galvanic Blast at player B with `artifacts` artifacts out; with `lose_one`, one of them leaves before it resolves."""
    game, _ = table3(pick("Player: B"))
    a, b = game.seats[0], game.seats[1]
    relics = [Permanent(RELIC) for _ in range(artifacts)]
    a.hand, a.battlefield = [BLAST], lands(1) + relics
    game._perform(a, CAST + BLAST.name)
    if lose_one:
        game._leave_battlefield(relics[0], "destroyed")
    run_stack(game)
    return 40 - b.life


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (BLAST, HEAT):
            self.assertEqual(unsupported_lines(card), [], card.name)


class GalvanicBlastTests(unittest.TestCase):
    def test_two_artifacts_two_damage(self):
        self.assertEqual(blast(2), 2)

    def test_three_artifacts_four_damage(self):
        self.assertEqual(blast(3), 4)

    def test_metalcraft_is_checked_as_it_resolves(self):
        self.assertEqual(blast(3, lose_one=True), 2)


if __name__ == "__main__":
    unittest.main()
