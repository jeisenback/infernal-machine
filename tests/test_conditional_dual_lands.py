"""Gleaming Bastion and its four siblings: colored mana only the turn the land entered or while you control a basic land (#564 row 9)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Condition, mana_lines
from infernal_machine.game import CAST, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import real, table3

BASTION = real("Gleaming Bastion", "", "Land", "{T}: Add {C}.\n{T}: Add {W} or {U}. Activate only if this land entered this turn or if you "
                                               "control a basic land.")
LAIR = real("Hidden Lair", "", "Land", "{T}: Add {C}.\n{T}: Add {U} or {B}. Activate only if this land entered this turn or if you control "
                                       "a basic land.")
PLAINS = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
NONBASIC = Card(name="City of Brass", type_line="Land", produced_mana=tuple("WUBRG"))


def types_of(game, seat, permanent):
    """The mana types each of the permanent's sources can make."""
    return sorted("".join(sorted(s.types)) for s in game._mana_sources(seat) if s.permanent is permanent)


class ParseTests(unittest.TestCase):
    def test_the_lands_are_read(self):
        for card in (BASTION, LAIR):
            self.assertEqual(unsupported_lines(card), [], card.name)
        either = Condition("source_entered_this_turn", otherwise=Condition("control_at_least", 1, "basic land"))
        self.assertEqual(mana_lines(BASTION), [(frozenset("C"), None), (frozenset("WU"), either)])

    def test_a_condition_the_grammar_does_not_know_leaves_the_line_unread(self):
        odd = real("Odd Bastion", "", "Land", "{T}: Add {C}.\n{T}: Add {W} or {U}. Activate only if this land entered this turn or if the moon "
                                              "is full.")
        self.assertEqual(len(unsupported_lines(odd)), 1)


class ManaTests(unittest.TestCase):
    def table(self, *battlefield):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = list(battlefield)
        return game, a

    def test_only_colorless_with_no_basic_land_on_a_later_turn(self):
        bastion = Permanent(BASTION)
        game, a = self.table(bastion, Permanent(NONBASIC))
        self.assertEqual(types_of(game, a, bastion), ["C"])

    def test_either_color_while_you_control_a_basic_land(self):
        bastion = Permanent(BASTION)
        game, a = self.table(bastion, Permanent(PLAINS))
        self.assertEqual(types_of(game, a, bastion), ["CUW"])

    def test_either_color_the_turn_it_entered_then_only_colorless(self):
        game, a = self.table()
        a.hand = [BASTION]
        game._perform(a, PLAY_LAND + "Gleaming Bastion")
        bastion = a.battlefield[-1]
        self.assertEqual(types_of(game, a, bastion), ["CUW"])
        game.turn += 1
        self.assertEqual(types_of(game, a, bastion), ["C"])

    def test_it_pays_for_a_blue_spell_only_when_its_condition_holds(self):
        bastion = Permanent(BASTION)
        game, a = self.table(bastion)
        a.hand = [real("Ponder", "{U}", "Sorcery", "Draw a card.")]
        self.assertNotIn(CAST + "Ponder", game.legal_actions(a))
        a.battlefield.append(Permanent(PLAINS))
        self.assertIn(CAST + "Ponder", game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
