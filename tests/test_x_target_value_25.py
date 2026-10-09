"""A spell with "target creature with mana value X" can only be cast for an X that some creature has (found by running bot
games on the real precon decks, #25: Entrancing Melody crashed the cast when the chosen X matched no creature).
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

MELODY = Card(name="Entrancing Melody", mana_cost="{X}{U}{U}", cmc=2.0, type_line="Sorcery", colors=("U",),
              oracle_text="Gain control of target creature with mana value X.")


def creature(name, mana_value):
    return Card(name=name, mana_cost="{" + str(mana_value) + "}" if mana_value else "", cmc=float(mana_value),
                type_line="Creature — Test", power="2", toughness="2")


def setup(opponent_creatures, mana, policy=None):
    seen = {}

    def default(prompt, options):
        if prompt.startswith("Choose X"):
            seen["x_options"] = list(options)
            return len(options) - 1  # like the bot: the largest X offered
        return 0

    game, _ = table3(policy or default)
    a, b, _ = game.seats
    a.hand, a.battlefield = [MELODY], lands(mana)
    b.battlefield = [Permanent(c) for c in opponent_creatures]
    game.active, game.step = 0, "main1"
    return game, a, b, seen


class XTargetTests(unittest.TestCase):
    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(MELODY), [])

    def test_the_largest_x_offered_is_one_with_a_target(self):
        game, a, b, seen = setup([creature("Three", 3)], mana=7)  # X could be anything up to 5
        game._perform(a, CAST + "Entrancing Melody")
        run_stack(game)
        self.assertEqual(seen["x_options"], ["3"])  # only the mana value that a creature has
        self.assertEqual([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], ["Three"])

    def test_every_mana_value_in_play_is_offered(self):
        game, a, b, seen = setup([creature("Two", 2), creature("Four", 4), creature("Seven", 7)], mana=7)
        game._perform(a, CAST + "Entrancing Melody")
        self.assertEqual(seen["x_options"], ["2", "4"])  # 7 needs nine mana

    def test_a_creature_with_mana_value_zero_needs_x_zero(self):
        game, a, b, seen = setup([creature("Token", 0)], mana=2)
        game._perform(a, CAST + "Entrancing Melody")
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], ["Token"])

    def test_it_is_not_offered_when_no_creature_has_an_affordable_mana_value(self):
        game, a, b, seen = setup([creature("Six", 6)], mana=4)  # X could only be 2
        self.assertNotIn(CAST + "Entrancing Melody", game.legal_actions(a))

    def test_it_is_offered_when_one_does(self):
        game, a, b, seen = setup([creature("Two", 2)], mana=4)
        self.assertIn(CAST + "Entrancing Melody", game.legal_actions(a))

    def test_it_is_not_offered_with_no_creature_at_all(self):
        game, a, b, seen = setup([], mana=6)
        self.assertNotIn(CAST + "Entrancing Melody", game.legal_actions(a))
