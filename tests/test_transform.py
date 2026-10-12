"""Transforming double-faced cards and the day/night rule: the old werewolves (Duskwatch Recruiter), daybound and nightbound
cards, and Sagas that return transformed."""

import dataclasses
import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import ReturnTransformed, day_night_face
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))

HOWLER = real("Krallenhorde Howler", "", "Creature — Werewolf", "Creature spells you cast cost {1} less to cast.\nAt the beginning of each "
              "upkeep, if a player cast two or more spells last turn, transform this creature.", "3", "3")
RECRUITER = dataclasses.replace(
    real("Duskwatch Recruiter // Krallenhorde Howler", "{1}{G}", "Creature — Human Peasant Werewolf",
         "{2}{G}: Look at the top three cards of your library. You may reveal a creature card from among them and put it into your hand. "
         "Put the rest on the bottom of your library in any order.\nAt the beginning of each upkeep, if no spells were cast last turn, "
         "transform this creature.", "2", "2"),
    flip=dataclasses.replace(HOWLER, cmc=2.0))
NIGHT = real("Hollowhenge Huntmaster", "", "Creature — Werewolf", "Nightbound (If a player casts no spells during their own turn, it becomes "
             "night next turn.)\nWhen this creature transforms into CARDNAME, put two +1/+1 counters on it.", "4", "4")
CARETAKER = dataclasses.replace(
    real("Avabruck Caretaker // Hollowhenge Huntmaster", "{2}{G}", "Creature — Human Peasant",
         "Daybound (If a player casts no spells during their own turn, it becomes night next turn.)\nWhen this creature enters, "
         "put a +1/+1 counter on it.", "2", "3"),
    flip=dataclasses.replace(NIGHT, cmc=3.0))
PLAIN_FLIP = dataclasses.replace(real("Pearl-Ear // Pearl Back", "{1}", "Creature — Test", "", "1", "1"),
                                 flip=real("Pearl Back", "", "Creature — Test", "", "2", "2"))
WALKER_FRONT = dataclasses.replace(
    real("Flipwalk Pilgrim // Flipwalk Walker", "{2}", "Creature — Human", "", "1", "1"),
    flip=dataclasses.replace(real("Flipwalk Walker", "", "Legendary Planeswalker — Test", ""), loyalty="4"))
SAGA = dataclasses.replace(
    real("Test Saga // Test Creature", "{2}", "Enchantment — Saga", "I — You gain 1 life.\nII — You gain 1 life.\nIII — Exile this Saga, "
         "then return it to the battlefield transformed under your control."),
    flip=real("Test Creature", "", "Enchantment Creature — Spirit", "Vigilance", "3", "3"))
WOLF = dataclasses.replace(
    real("Wolf Cub // Wolf Elder", "{1}{G}", "Creature — Wolf", "When CARDNAME dies, return it to the battlefield tapped and transformed under "
         "its owner's control.", "1", "1"),
    flip=real("Wolf Elder", "", "Creature — Wolf", "Vigilance", "4", "4"))
CHEAP = real("Cheap Spell", "{G}", "Sorcery", "")


def table(*cards):
    game, _ = table3(script("Pass"))
    a = game.seats[0]
    a.hand, a.library, a.graveyard = [], [FOREST] * 8, []
    a.battlefield = [Permanent(c, sick=False) for c in cards]
    return game, a


def permanent(seat, card):
    return next(p for p in seat.battlefield if p.card is card or p.transformed_from is card)


def begin(game, step, seat=None):
    game.step = step
    game._turn_based_actions(seat or game.seats[game.active])
    run_stack(game)


def cast_cheap(seat, turn, times=1):
    seat.cast_log += [(turn, CHEAP)] * times


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (RECRUITER, CARETAKER, SAGA, WOLF):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_back_face_that_is_not_understood_counts(self):
        odd = dataclasses.replace(RECRUITER, flip=real("Odd", "", "Creature — Test", "Frobnicate the widget.", "1", "1"))
        self.assertEqual(unsupported_lines(odd), ["Odd: Frobnicate the widget."])

    def test_day_and_night_faces(self):
        self.assertEqual(day_night_face(CARETAKER), "day")
        self.assertEqual(day_night_face(NIGHT), "night")
        self.assertIsNone(day_night_face(BEAR))


class TransformTests(unittest.TestCase):
    def test_it_turns_over_and_back_keeping_counters_and_damage(self):
        game, a = table(PLAIN_FLIP)
        pearl = a.battlefield[0]
        pearl.counters["+1/+1"], pearl.damage = 1, 1
        game.transform(pearl)
        self.assertEqual((pearl.card.name, game.power(pearl)), ("Pearl Back", 3))
        self.assertEqual((pearl.counters["+1/+1"], pearl.damage), (1, 1))
        game.transform(pearl)
        self.assertEqual(pearl.card, PLAIN_FLIP)
        self.assertIsNone(pearl.transformed_from)

    def test_it_leaves_as_its_front_face(self):
        game, a = table(PLAIN_FLIP)
        pearl = a.battlefield[0]
        game.transform(pearl)
        game.destroy(pearl)
        self.assertEqual(a.graveyard, [PLAIN_FLIP])

    def test_a_transformed_permanent_that_is_blinked_returns_as_its_front_face(self):
        game, a = table(PLAIN_FLIP)
        game.transform(a.battlefield[0])
        game.flicker(a.battlefield[0], a, "now", "battlefield", under_owner=True)
        self.assertEqual([p.card for p in a.battlefield], [PLAIN_FLIP])

    def test_the_mana_value_stays_the_front_faces(self):
        game, a = table(RECRUITER)
        game.transform(a.battlefield[0])
        self.assertEqual(a.battlefield[0].card.cmc, 2.0)

    def test_a_single_faced_card_does_not_transform(self):
        game, a = table(BEAR)
        game.transform(a.battlefield[0])
        self.assertEqual(a.battlefield[0].card, BEAR)

    def test_a_token_does_not_transform(self):
        token = dataclasses.replace(PLAIN_FLIP, type_line="Token Creature — Test")
        game, a = table(token)
        game.transform(a.battlefield[0])
        self.assertEqual(a.battlefield[0].card, token)

    def test_a_planeswalker_back_starts_with_its_loyalty(self):
        game, a = table(WALKER_FRONT)
        game.transform(a.battlefield[0])
        self.assertEqual(a.battlefield[0].loyalty, 4)
        game.transform(a.battlefield[0])
        self.assertIsNone(a.battlefield[0].loyalty)

    def test_a_card_that_left_cannot_transform(self):
        game, a = table(PLAIN_FLIP)
        pearl = a.battlefield[0]
        a.battlefield.clear()
        game.transform(pearl)
        self.assertEqual(pearl.card, PLAIN_FLIP)


class OldWerewolfTests(unittest.TestCase):
    def test_it_transforms_when_nobody_cast_a_spell_last_turn(self):
        game, a = table(RECRUITER)
        begin(game, "upkeep")
        self.assertEqual(a.battlefield[0].card.name, "Krallenhorde Howler")

    def test_it_stays_when_a_spell_was_cast(self):
        game, a = table(RECRUITER)
        cast_cheap(game.seats[1], game.turn - 1)
        begin(game, "upkeep")
        self.assertEqual(a.battlefield[0].card, RECRUITER)

    def test_it_changes_back_when_a_player_cast_two_spells(self):
        game, a = table(RECRUITER)
        game.transform(a.battlefield[0])
        cast_cheap(game.seats[1], game.turn - 1, 2)
        begin(game, "upkeep")
        self.assertEqual(a.battlefield[0].card, RECRUITER)

    def test_one_spell_each_from_two_players_is_not_enough(self):
        game, a = table(RECRUITER)
        game.transform(a.battlefield[0])
        cast_cheap(game.seats[0], game.turn - 1)
        cast_cheap(game.seats[1], game.turn - 1)
        begin(game, "upkeep")
        self.assertEqual(a.battlefield[0].card.name, "Krallenhorde Howler")


class DayNightTests(unittest.TestCase):
    def test_a_daybound_permanent_makes_it_day(self):
        game, a = table()
        self.assertIsNone(game.day_night)
        game._enter(a, Permanent(CARETAKER))
        self.assertEqual(game.day_night, "day")

    def test_a_turn_without_spells_makes_it_night(self):
        game, a = table()
        game._enter(a, Permanent(CARETAKER))
        run_stack(game)
        game.previous_player = game.seats[1]
        begin(game, "untap")
        self.assertEqual(game.day_night, "night")
        self.assertEqual(permanent(a, CARETAKER).card.name, "Hollowhenge Huntmaster")

    def test_a_spell_in_the_previous_turn_keeps_it_day(self):
        game, a = table()
        game._enter(a, Permanent(CARETAKER))
        game.previous_player = game.seats[1]
        cast_cheap(game.seats[1], game.turn - 1)
        begin(game, "untap")
        self.assertEqual(game.day_night, "day")

    def test_only_the_previous_players_spells_count(self):
        game, a = table()
        game._enter(a, Permanent(CARETAKER))
        game.previous_player = game.seats[1]
        cast_cheap(game.seats[0], game.turn - 1, 3)
        begin(game, "untap")
        self.assertEqual(game.day_night, "night")

    def test_two_spells_make_it_day_again(self):
        game, a = table()
        game._enter(a, Permanent(CARETAKER))
        game._set_day_night("night")
        game.previous_player = game.seats[1]
        cast_cheap(game.seats[1], game.turn - 1, 2)
        begin(game, "untap")
        self.assertEqual(game.day_night, "day")
        self.assertEqual(permanent(a, CARETAKER).card.name, "Avabruck Caretaker // Hollowhenge Huntmaster")

    def test_one_spell_leaves_the_night(self):
        game, a = table()
        game._enter(a, Permanent(CARETAKER))
        game._set_day_night("night")
        game.previous_player = game.seats[1]
        cast_cheap(game.seats[1], game.turn - 1)
        begin(game, "untap")
        self.assertEqual(game.day_night, "night")

    def test_a_daybound_permanent_enters_transformed_at_night(self):
        game, a = table()
        game.day_night = "night"
        game._enter(a, Permanent(CARETAKER))
        self.assertEqual(a.battlefield[-1].card.name, "Hollowhenge Huntmaster")

    def test_other_effects_cannot_transform_a_daybound_permanent(self):
        game, a = table(CARETAKER)
        game.transform(a.battlefield[0])
        self.assertEqual(a.battlefield[0].card, CARETAKER)

    def test_a_trigger_for_transforming_into_the_card(self):
        game, a = table(CARETAKER)
        game.day_night = "day"
        game._set_day_night("night")
        run_stack(game)
        self.assertEqual(a.battlefield[0].counters.get("+1/+1"), 2)

    def test_the_condition_its_day_or_night(self):
        from infernal_machine.effects.outcomes import Condition
        game, a = table()
        game.day_night = "day"
        self.assertTrue(game.condition_holds(Condition("day"), a))
        self.assertFalse(game.condition_holds(Condition("night"), a))


class ReturnTransformedTests(unittest.TestCase):
    def test_a_saga_comes_back_as_its_other_face(self):
        game, a = table(SAGA)
        saga = a.battlefield[0]
        ReturnTransformed().resolve(game, a, saga)
        [back] = a.battlefield
        self.assertEqual((back.card.name, back.transformed_from), ("Test Creature", SAGA))
        self.assertIsNot(back, saga)

    def test_the_third_chapter_does_it(self):
        game, a = table()
        game._enter(a, Permanent(SAGA, sick=True))
        run_stack(game)
        for chapter in (2, 3):
            a.battlefield[0].counters["lore"] = chapter
            game.trigger(f"chapter_{chapter}", a.battlefield[0], a)
            run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Test Creature"])
        self.assertEqual(a.graveyard, [])

    def test_a_creature_that_dies_comes_back_tapped_and_transformed(self):
        game, a = table(WOLF)
        game.destroy(a.battlefield[0])
        run_stack(game)
        [back] = a.battlefield
        self.assertEqual(back.card.name, "Wolf Elder")
        self.assertTrue(back.tapped)
        self.assertEqual(a.graveyard, [])


if __name__ == "__main__":
    unittest.main()
