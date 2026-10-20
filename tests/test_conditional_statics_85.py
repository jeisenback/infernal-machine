"""The conditional static lines of issue #85: Threshold (Theorix Metamage, Void Extrapolator) and Whiplash Wordsmith.

The lines are the cards' own Oracle text from Scryfall; each has a case where the condition is false.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Condition, static_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import creature, table

SPELL = Card(name="Spell", type_line="Instant", oracle_text="Draw a card.")
LAND = Card(name="Forest", type_line="Basic Land — Forest")

METAMAGE = creature("Metamage", 2, 3, "Threshold — This creature gets +1/+0 and has flying as long as there are seven or "
                                     "more cards in your graveyard.")
EXTRAPOLATOR = creature("Extrapolator", 2, 2, "Threshold — This creature gets +1/+1 as long as there are seven or more "
                                              "cards in your graveyard.")
WORDSMITH = creature("Wordsmith", 3, 3, "As long as an opponent was dealt noncombat damage this turn, this creature has "
                                        "flying and haste.")


class ParseTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for card in (METAMAGE, EXTRAPOLATOR, WORDSMITH):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_threshold_counts_any_card_in_the_graveyard(self):
        (buff,) = static_abilities(EXTRAPOLATOR)
        self.assertEqual(buff.condition, Condition("graveyard_at_least", 7, "card"))
        self.assertTrue(buff.self_only)

    def test_an_ability_word_does_not_make_an_unknown_line_supported(self):
        card = creature("x", 1, 1, "Threshold — This creature gets +1/+1 as long as the moon is full.")
        self.assertEqual(len(unsupported_lines(card)), 1)


class ThresholdTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a, self.b = self.game.seats

    def test_the_buff_starts_at_seven_cards(self):
        extrapolator = Permanent(EXTRAPOLATOR)
        self.a.battlefield = [extrapolator]
        self.a.graveyard = [SPELL] * 6
        self.assertEqual((self.game.power(extrapolator), self.game.toughness(extrapolator)), (2, 2))
        self.a.graveyard = [SPELL] * 6 + [LAND]
        self.assertEqual((self.game.power(extrapolator), self.game.toughness(extrapolator)), (3, 3))

    def test_it_stops_when_a_card_leaves(self):
        extrapolator = Permanent(EXTRAPOLATOR)
        self.a.battlefield = [extrapolator]
        self.a.graveyard = [SPELL] * 7
        self.assertEqual(self.game.power(extrapolator), 3)
        self.a.graveyard.pop()
        self.assertEqual(self.game.power(extrapolator), 2)

    def test_an_opponents_graveyard_does_not_count(self):
        extrapolator = Permanent(EXTRAPOLATOR)
        self.a.battlefield = [extrapolator]
        self.b.graveyard = [SPELL] * 9
        self.assertEqual(self.game.power(extrapolator), 2)

    def test_power_and_flying_together(self):
        metamage = Permanent(METAMAGE)
        self.a.battlefield = [metamage]
        self.a.graveyard = [SPELL] * 6
        self.assertEqual((self.game.power(metamage), self.game.toughness(metamage), self.game.has_keyword(metamage, "flying")),
                         (2, 3, False))
        self.a.graveyard = [SPELL] * 7
        self.assertEqual((self.game.power(metamage), self.game.toughness(metamage), self.game.has_keyword(metamage, "flying")),
                         (3, 3, True))


class WhiplashWordsmithTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a, self.b = self.game.seats
        self.wordsmith = Permanent(WORDSMITH, sick=True)
        self.a.battlefield = [self.wordsmith]

    def keywords(self):
        return self.game.has_keyword(self.wordsmith, "flying"), self.game.has_keyword(self.wordsmith, "haste")

    def test_nothing_without_damage(self):
        self.assertEqual(self.keywords(), (False, False))

    def test_flying_and_haste_after_noncombat_damage_to_an_opponent(self):
        self.game.damage(self.b, 1)
        self.assertEqual(self.keywords(), (True, True))

    def test_combat_damage_does_not_count(self):
        self.game.damage(self.b, 3, combat=True)
        self.assertEqual(self.keywords(), (False, False))

    def test_losing_life_is_not_damage(self):
        self.game.change_life(self.b, -3)
        self.assertEqual(self.keywords(), (False, False))

    def test_damage_to_its_controller_does_not_count(self):
        self.game.damage(self.a, 2)
        self.assertEqual(self.keywords(), (False, False))

    def test_damage_to_a_creature_does_not_count(self):
        victim = Permanent(creature("Victim", 1, 4))
        self.b.battlefield = [victim]
        self.game.damage(victim, 2)
        self.assertEqual(self.keywords(), (False, False))

    def test_it_ends_with_the_turn(self):
        self.game.damage(self.b, 1)
        self.game.turn += 1
        self.assertEqual(self.keywords(), (False, False))

    def test_zero_damage_does_not_count(self):
        self.game.damage(self.b, 0)
        self.assertEqual(self.keywords(), (False, False))
