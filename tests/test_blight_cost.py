"""Blight as an optional additional cost, and "If this spell's additional cost was paid, ..." (Requiting Hex, #564 row 8)."""

import unittest

from infernal_machine.effects import NOTHING_MORE, AdditionalCost, Destroy, GainLife, IfAdditionalCostPaid, additional_costs, spell_effects

from infernal_machine.game import BLIGHT_PROMPT, COST_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Permanent, Table, creature, real

HEX = real("Requiting Hex", "{B}", "Instant",
           "As an additional cost to cast this spell, you may blight 1. (You may put a -1/-1 counter on a creature you control.)\n"
           "Destroy target creature with mana value 2 or less. If this spell's additional cost was paid, you gain 2 life.")
BIG = real("Big One", "{2}{G}", "Creature — Beast", "", "4", "4")


def cast(*answers, mine=()):
    """Seat A casts the Hex at B's Bear with `mine` on A's side; `answers` are the cost choice, the target and the creature blighted."""
    bear = Permanent(BEAR)
    t = Table(HEX, *answers, n=1, mine=list(mine), theirs=[bear])
    life = t.a.life
    t.cast()
    return t, bear, t.a.life - life


def prompts(t, kind):
    return [options for prompt, options in t.a.player.prompts if kind.matches(prompt)]


class ParseTests(unittest.TestCase):
    def test_the_card_is_read(self):
        self.assertEqual(unsupported_lines(HEX), [])
        self.assertEqual(additional_costs(HEX), [AdditionalCost(options=(AdditionalCost(blight=1), NOTHING_MORE))])
        self.assertEqual(spell_effects(HEX), [Destroy("creature with mana value 2 or less"), IfAdditionalCostPaid(GainLife(2))])

    def test_a_rider_that_is_not_understood_leaves_the_spell_unread(self):
        odd = real("Odd Hex", "{B}", "Instant", "As an additional cost to cast this spell, you may blight 1.\n"
                                                 "Destroy target creature. If this spell's additional cost was paid, frobnicate.")
        self.assertTrue(unsupported_lines(odd))


class CastTests(unittest.TestCase):
    def test_blighting_puts_the_counter_and_pays_for_the_life(self):
        ogre = Permanent(OGRE)
        t, bear, gained = cast("Blight", "Bear", "Ogre", mine=[ogre])
        self.assertEqual(prompts(t, COST_PROMPT), [["Blight 1", "Pay nothing more"]])
        self.assertEqual(ogre.counters.get("-1/-1"), 1)
        self.assertEqual(t.game.power(ogre), 2)
        self.assertNotIn(bear, t.b.battlefield)
        self.assertEqual(gained, 2)

    def test_paying_nothing_more_still_destroys_but_gains_no_life(self):
        ogre = Permanent(OGRE)
        t, bear, gained = cast("Pay nothing", "Bear", mine=[ogre])
        self.assertEqual(prompts(t, BLIGHT_PROMPT), [])
        self.assertIsNone(ogre.counters.get("-1/-1"))
        self.assertNotIn(bear, t.b.battlefield)
        self.assertEqual(gained, 0)

    def test_with_no_creature_to_blight_there_is_no_choice(self):
        t, bear, gained = cast("Bear")
        self.assertEqual(prompts(t, COST_PROMPT), [])
        self.assertEqual(prompts(t, BLIGHT_PROMPT), [])
        self.assertNotIn(bear, t.b.battlefield)
        self.assertEqual(gained, 0)

    def test_a_blighted_one_toughness_creature_dies(self):
        weak = Permanent(creature("Weakling", 1, 1))
        t, bear, gained = cast("Blight", "Bear", "Weakling", mine=[weak])
        self.assertNotIn(weak, t.a.battlefield)
        self.assertIn(weak.card, t.a.graveyard)
        self.assertEqual(gained, 2)

    def test_a_creature_with_mana_value_three_is_not_a_target(self):
        big = Permanent(BIG)
        t = Table(HEX, n=1, theirs=[big])
        labels = [label for label, _ in t.game.target_options("creature with mana value 2 or less", t.a)]
        self.assertFalse(any(label.startswith("Big One") for label in labels))


if __name__ == "__main__":
    unittest.main()
