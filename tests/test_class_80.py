"""Class enchantments (issue #80): Intermediate Chirography and Advanced Reconstruction. A Class starts at level 1 and gains the
next level for the cost on its "Level N" line, only at sorcery speed. Lines are the cards' own Oracle text from Scryfall."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import activate, fire
from tests.test_triggers_80 import FOREST, RELIC

CHIROGRAPHY = Card(name="Intermediate Chirography", mana_cost="{1}{B}", cmc=2.0, type_line="Enchantment — Class",
                   oracle_text="(Gain the next level as a sorcery to add its ability.)\nWhen this Class enters, create a 2/1 white and "
                               "black Inkling creature token with flying.\n{1}{B}: Level 2\nWhenever you lose life for the first time "
                               "each turn, put a +1/+1 counter on target creature you control.\n{2}{B}: Level 3\nAt the beginning of "
                               "each end step, if a modified creature died under your control this turn, create a 2/1 white and "
                               "black Inkling creature token with flying. (Equipment, Auras you control, and counters are "
                               "modifications.)")


class ClassLevelTests(unittest.TestCase):
    def table(self, lands_in_play=6):
        game, _ = table3(pick())
        a = game.seats[0]
        game.step = "main1"
        self.cls = Permanent(CHIROGRAPHY)
        a.battlefield = lands(lands_in_play)
        game._enter(a, self.cls)
        run_stack(game)
        return game, a

    def level_actions(self, game, a):
        return [x for x in game.legal_actions(a) if "Level" in x]

    def test_parse(self):
        self.assertEqual(unsupported_lines(CHIROGRAPHY), [])

    def test_it_enters_at_level_one_with_only_the_first_ability(self):
        game, a = self.table()
        self.assertEqual(self.cls.level, 1)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Inkling"]), 1)  # the enters ability
        a.battlefield.append(bear := Permanent(BEAR))
        game.change_life(a, -1)
        run_stack(game)
        self.assertIsNone(bear.counters.get("+1/+1"))  # level 2 has not been gained

    def test_only_the_next_level_is_offered(self):
        game, a = self.table()
        [action] = self.level_actions(game, a)
        self.assertIn("Level 2", action)

    def test_level_two_adds_its_ability(self):
        game, a = self.table()
        activate(game, a, "Level 2")
        run_stack(game)
        self.assertEqual(self.cls.level, 2)
        bear = Permanent(BEAR)
        a.battlefield.append(bear)
        game.change_life(a, -1)
        run_stack(game)
        self.assertEqual(sum(p.counters.get("+1/+1", 0) for p in a.battlefield if p is not self.cls), 1)

    def test_level_three_follows_level_two_and_is_the_last(self):
        game, a = self.table(lands_in_play=8)
        activate(game, a, "Level 2")
        run_stack(game)
        [action] = self.level_actions(game, a)
        self.assertIn("Level 3", action)
        activate(game, a, "Level 3")
        run_stack(game)
        self.assertEqual((self.cls.level, self.level_actions(game, a)), (3, []))

    def test_level_three_makes_an_inkling_when_a_modified_creature_died(self):
        game, a = self.table(lands_in_play=8)
        for fragment in ("Level 2", "Level 3"):
            activate(game, a, fragment)
            run_stack(game)
        game.step = "end"
        before = len([p for p in a.battlefield if p.card.name == "Inkling"])
        a.modified_died_turn = game.turn
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Inkling"]), before + 1)

    def test_a_level_is_gained_only_at_sorcery_speed(self):
        game, a = self.table()
        game.step = "combat_damage"
        self.assertEqual(self.level_actions(game, a), [])

    def test_a_level_costs_its_mana(self):
        game, a = self.table(lands_in_play=1)
        self.assertEqual(self.level_actions(game, a), [])

    def test_it_goes_to_the_graveyard_as_the_card_it_is(self):
        game, a = self.table()
        activate(game, a, "Level 2")
        run_stack(game)
        game._leave_battlefield(self.cls, "destroyed")
        self.assertEqual([c.oracle_text == CHIROGRAPHY.oracle_text for c in a.graveyard], [True])


RECONSTRUCTION = Card(name="Advanced Reconstruction", mana_cost="{3}{R}", cmc=4.0, type_line="Enchantment — Class",
                      oracle_text="(Gain the next level as a sorcery to add its ability.)\nAt the beginning of your first main phase, "
                                  "mill a card, then exile a card from your graveyard at random. You may play the exiled card this "
                                  "turn.\n{1}{R}: Level 2\nWhenever one or more cards leave your graveyard, this Class deals 2 damage "
                                  "to each opponent.\n{1}{R}: Level 3\nSpells you cast from anywhere other than your hand cost {2} "
                                  "less to cast.")
FLASHBACK_SPELL = Card(name="Rerun", mana_cost="{3}{R}", cmc=4.0, type_line="Sorcery", oracle_text="Draw a card.\nFlashback {3}{R}")
HAND_SPELL = Card(name="Cheap", mana_cost="{2}{R}", cmc=3.0, type_line="Sorcery", oracle_text="Draw a card.")


class AdvancedReconstructionTests(unittest.TestCase):
    def table(self, level, lands_in_play=8):
        game, _ = table3(pick())
        a, b, _ = game.seats
        game.step = "main1"
        self.cls = Permanent(RECONSTRUCTION)
        a.battlefield = lands(lands_in_play)
        game._enter(a, self.cls)
        for _ in range(level - 1):
            game.class_level_up(self.cls)
        a.library = [FOREST] * 10
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(RECONSTRUCTION), [])

    def test_level_one_mills_and_exiles_at_the_first_main_phase(self):
        game, a, b = self.table(1)
        game.step = "main1"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(len(a.exile), 1)

    def test_level_two_deals_two_damage_when_cards_leave_the_graveyard(self):
        game, a, b = self.table(2)
        a.graveyard = [RELIC]
        game.exile_card_from_graveyard(a, RELIC, False)
        run_stack(game)
        self.assertEqual(b.life, 38)

    def test_before_level_two_nothing_happens(self):
        game, a, b = self.table(1)
        a.graveyard = [RELIC]
        game.exile_card_from_graveyard(a, RELIC, False)
        run_stack(game)
        self.assertEqual(b.life, 40)

    def test_level_three_makes_spells_from_the_graveyard_cost_two_less(self):
        game, a, b = self.table(3, lands_in_play=2)
        a.graveyard = [FLASHBACK_SPELL]
        self.assertTrue([x for x in game.legal_actions(a) if "Rerun" in x])  # {3}{R} flashback for two lands

    def test_without_level_three_it_is_too_expensive(self):
        game, a, b = self.table(2, lands_in_play=2)
        a.graveyard = [FLASHBACK_SPELL]
        self.assertFalse([x for x in game.legal_actions(a) if "Rerun" in x])

    def test_a_spell_cast_from_the_hand_is_not_cheaper(self):
        game, a, b = self.table(3, lands_in_play=2)
        a.hand = [HAND_SPELL]
        self.assertFalse([x for x in game.legal_actions(a) if "Cheap" in x])
