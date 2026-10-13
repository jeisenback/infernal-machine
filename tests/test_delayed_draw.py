"""Portent, Clairvoyance, Flare and their kin: "Draw a card at the beginning of the next turn's upkeep." The card is drawn at the next upkeep,
not now, and only the player who cast the spell draws it (Arcane Denial and the Bauble artifacts already worked; the plain wording did not)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects.outcomes import DelayedDraw, _template
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import Table, real, run_stack

FLARE = real("Flare", "{2}{R}", "Instant", "Flare deals 1 damage to any target.\nDraw a card at the beginning of the next turn's upkeep.",
             colors=("R",))
PYKNITE = real("Pyknite", "{2}{G}", "Creature — Ouphe", "When this creature enters, draw a card at the beginning of the next turn's upkeep.", "1", "1",
               colors=("G",))
LIBRARY = [Card(name=f"Card {i}", type_line="Land") for i in range(12)]


def next_upkeep(t, seat):
    t.game.turn += 1
    t.game.step = "upkeep"
    t.game._turn_based_actions(seat)


class DelayedDrawTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (FLARE, PYKNITE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_nothing_is_drawn_now(self):
        t = Table(FLARE, "Player", n=6, library=LIBRARY).cast()
        self.assertEqual(len(t.a.hand), 0)

    def test_the_card_comes_at_the_next_upkeep(self):
        t = Table(FLARE, "Player", n=6, library=LIBRARY).cast()
        next_upkeep(t, t.b)
        self.assertEqual(len(t.a.hand), 1)

    def test_only_once(self):
        t = Table(FLARE, "Player", n=6, library=LIBRARY).cast()
        next_upkeep(t, t.b)
        next_upkeep(t, t.c)
        self.assertEqual(len(t.a.hand), 1)

    def test_nobody_else_draws(self):
        t = Table(FLARE, "Player", n=6, library=LIBRARY).cast()
        before = (len(t.b.hand), len(t.c.hand))
        next_upkeep(t, t.b)
        self.assertEqual((len(t.b.hand), len(t.c.hand)), before)

    def test_an_enters_trigger_does_the_same(self):
        t = Table(PYKNITE, n=6, library=LIBRARY).cast()
        self.assertEqual(len(t.a.hand), 0)
        next_upkeep(t, t.b)
        self.assertEqual(len(t.a.hand), 1)

    def test_the_number_is_read(self):
        self.assertEqual(_template("You draw three cards at the beginning of the next turn's upkeep."), DelayedDraw(3, False))
        self.assertEqual(_template("Draw a card at the beginning of the next turn's upkeep."), DelayedDraw(1, False))


if __name__ == "__main__":
    unittest.main()
