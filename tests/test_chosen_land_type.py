"""Multiversal Passage: a land that is the basic land type chosen as it enters, with a shock clause (#564 row 13)."""

import unittest

from infernal_machine.effects import Condition, EntersTapped, chooses_basic_land_type, enters_tapped_rule
from infernal_machine.game import CHOOSE_LAND_TYPE_PROMPT, SHOCK_PROMPT, has_type
from infernal_machine.report import unsupported_lines
from tests.helpers import enter, pick, real, table

PASSAGE = real("Multiversal Passage", "", "Land", "As this land enters, choose a basic land type. Then you may pay 2 life. If you don't, "
                                                   "it enters tapped.\nThis land is the chosen type.")


def types_of(game, seat, permanent):
    return sorted("".join(sorted(s.types)) for s in game._mana_sources(seat) if s.permanent is permanent)


def play(*answers):
    game, a_player, _ = table(pick(*answers))
    a = game.seats[0]
    return game, a, a_player, enter(game, a, PASSAGE)


class ParseTests(unittest.TestCase):
    def test_the_card_is_read(self):
        self.assertEqual(unsupported_lines(PASSAGE), [])
        self.assertTrue(chooses_basic_land_type(PASSAGE))
        self.assertEqual(enters_tapped_rule(PASSAGE), EntersTapped("shock", life=2))

    def test_the_bare_choice_reads_without_the_shock_clause(self):
        plain = real("Plain Passage", "", "Land", "As this land enters, choose a basic land type.\nThis land is the chosen type.")
        self.assertEqual(unsupported_lines(plain), [])
        self.assertIsNone(enters_tapped_rule(plain))


class EnterTests(unittest.TestCase):
    def test_it_is_the_chosen_type_and_taps_for_its_color(self):
        game, a, a_player, passage = play("Island", "Pay")
        self.assertFalse(passage.tapped)
        self.assertEqual(a.life, 38)
        self.assertEqual(passage.card.type_line, "Land — Island")
        self.assertTrue(has_type(passage.card, "Island"))
        self.assertEqual(types_of(game, a, passage), ["U"])
        self.assertTrue(game.condition_holds(Condition("control_at_least", 1, "Island"), a))
        self.assertFalse(game.condition_holds(Condition("control_at_least", 1, "Swamp"), a))

    def test_the_type_is_chosen_before_the_life_is_asked(self):
        _, _, a_player, _ = play("Forest", "Pay")
        kinds = [p for p, _ in a_player.prompts if CHOOSE_LAND_TYPE_PROMPT.matches(p) or SHOCK_PROMPT.matches(p)]
        self.assertEqual(len(kinds), 2)
        self.assertTrue(CHOOSE_LAND_TYPE_PROMPT.matches(kinds[0]))
        self.assertTrue(SHOCK_PROMPT.matches(kinds[1]))

    def test_not_paying_enters_it_tapped(self):
        game, a, _, passage = play("Swamp", "Enter")
        self.assertTrue(passage.tapped)
        self.assertEqual(a.life, 40)
        self.assertEqual(types_of(game, a, passage), [])  # tapped: no mana now
        passage.tapped = False
        self.assertEqual(types_of(game, a, passage), ["B"])

    def test_it_leaves_the_battlefield_as_the_printed_card(self):
        game, a, _, passage = play("Mountain", "Pay")
        game._leave_together([(passage, "destroyed")])
        self.assertEqual(a.graveyard, [PASSAGE])


if __name__ == "__main__":
    unittest.main()
