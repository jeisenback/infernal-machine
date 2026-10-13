"""Spree: "+ {1}{U} — Counter target spell." Each mode has its own additional cost; the caster chooses one or more of them, pays the mana cost
plus the cost of every chosen mode, and the chosen modes happen in printed order (CR 702.172). Three Steps Ahead, Insatiable Avarice,
Explosive Derailment, Phantom Interference, Unfortunate Accident."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import DONE_MODES, MODE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, creature, lands, pick, real, script

STEPS = real("Three Steps Ahead", "{U}", "Instant", "Spree (Choose one or more additional costs.)\n+ {1}{U} — Counter target spell.\n"
             "+ {3} — Create a token that's a copy of target artifact or creature you control.\n+ {2} — Draw two cards, then discard a card.",
             colors=("U",))
LIBRARY = [Card(name=f"Card {i}", type_line="Land") for i in range(12)]
DRAW = "+ {2} — Draw"
COPY = "+ {3} — Create a token"
COUNTER = "+ {1}{U} — Counter"


def tapped(seat):
    return sum(p.tapped for p in seat.battlefield if "Land" in p.card.type_line)


def modes_asked(table):
    return [options for prompt, options in table.a.player.prompts if prompt.startswith(MODE_PROMPT)]


class SpreeTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(STEPS), [])

    def test_one_mode_adds_its_cost(self):
        t = Table(STEPS, policy=script(DRAW, "Done"), n=6, library=LIBRARY).cast()
        self.assertEqual(tapped(t.a), 3)  # {U} and the {2} of the mode
        self.assertEqual(len(t.a.hand), 1)  # draw two, discard one

    def test_two_modes_add_both_costs(self):
        t = Table(STEPS, policy=script(DRAW, COPY, "Done", "Bear"), n=6, mine=[Permanent(BEAR)], library=LIBRARY).cast()
        self.assertEqual(tapped(t.a), 6)  # {U} + {2} + {3}
        self.assertEqual(sorted(p.card.name for p in t.a.battlefield if "Creature" in p.card.type_line), ["Bear", "Bear"])

    def test_a_mode_the_caster_cannot_pay_for_is_not_offered(self):
        t = Table(STEPS, policy=script(DRAW, "Done"), n=4, mine=[Permanent(BEAR)], library=LIBRARY).cast()
        first = modes_asked(t)[0]
        self.assertEqual([o[:5] for o in first], ["+ {3}", "+ {2}"])  # {1}{U} counter needs a spell to target
        self.assertEqual(tapped(t.a), 3)

    def test_after_a_mode_only_what_still_fits_is_offered(self):
        t = Table(STEPS, policy=script(DRAW, COPY, "Done"), n=5, mine=[Permanent(BEAR)], library=LIBRARY).cast()
        self.assertEqual(len(modes_asked(t)), 1)  # {U}+{2} leaves 2 of 5: the {3} copy no longer fits, so nothing more is asked
        self.assertEqual(tapped(t.a), 3)
        self.assertEqual(len([p for p in t.a.battlefield if p.card.name == "Bear"]), 1)

    def test_done_is_not_offered_before_a_mode_is_chosen(self):
        t = Table(STEPS, policy=script(DRAW, "Done"), n=6, library=LIBRARY).cast()
        self.assertNotIn(DONE_MODES, modes_asked(t)[0])

    def test_the_modes_happen_in_printed_order(self):
        # drawn first, the copy would be of a creature that was discarded; the copy comes first whatever the choice order
        t = Table(STEPS, policy=script(DRAW, COPY, "Done", "Bear"), n=6, mine=[Permanent(BEAR)], library=LIBRARY).cast()
        self.assertEqual(len(t.a.hand), 1)
        self.assertEqual(len([p for p in t.a.battlefield if p.card.name == "Bear"]), 2)


if __name__ == "__main__":
    unittest.main()
