"""The one-off lines of issue #80 that no other card shares (Blossoming Bogbeast first). Lines are the cards' own Oracle text from
Scryfall; each has cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import activate, fire
from tests.test_triggers_80 import FOREST, RELIC, SHRINE, card

BOGBEAST = Card(name="Blossoming Bogbeast", mana_cost="{4}{G}", type_line="Creature — Beast", power="5", toughness="5",
                oracle_text="Whenever this creature attacks, you gain 2 life. Then creatures you control gain trample and get +X/+X "
                            "until end of turn, where X is the amount of life you gained this turn.")


class BlossomingBogbeastTests(unittest.TestCase):
    def attack(self, gained_before=0):
        game, _ = table3(pick())
        a = game.seats[0]
        self.beast, self.bear = Permanent(BOGBEAST), Permanent(BEAR)
        a.battlefield = [self.beast, self.bear]
        if gained_before:
            game.change_life(a, gained_before)
        fire(game, a, self.beast, "attacks")
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(BOGBEAST), [])

    def test_it_gains_two_life_and_every_creature_gets_plus_two(self):
        game, a = self.attack()
        self.assertEqual((a.life, game.power(self.beast), game.power(self.bear)), (42, 7, 4))
        self.assertTrue(game.has_keyword(self.bear, "trample"))

    def test_the_bonus_counts_all_the_life_gained_this_turn(self):
        game, a = self.attack(gained_before=3)
        self.assertEqual((game.power(self.beast), game.power(self.bear)), (10, 7))  # 3 + 2


ANGER = Card(name="Anger", mana_cost="{3}{R}", type_line="Creature — Incarnation", power="2", toughness="2",
             oracle_text="Haste\nAs long as this card is in your graveyard and you control a Mountain, creatures you control have haste.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))


class AngerTests(unittest.TestCase):
    def table(self, graveyard=(), battlefield=()):
        game, _ = table3(pick())
        a, b, _ = game.seats
        self.bear = Permanent(BEAR, sick=True)
        a.battlefield = [self.bear, *battlefield]
        a.graveyard = list(graveyard)
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(ANGER), [])

    def test_in_the_graveyard_with_a_mountain_your_creatures_have_haste(self):
        game, a, b = self.table([ANGER], [Permanent(MOUNTAIN)])
        self.assertTrue(game.has_keyword(self.bear, "haste"))

    def test_without_a_mountain_it_does_nothing(self):
        game, a, b = self.table([ANGER], [Permanent(FOREST)])
        self.assertFalse(game.has_keyword(self.bear, "haste"))

    def test_on_the_battlefield_it_gives_no_haste_to_others(self):
        game, a, b = self.table([], [Permanent(ANGER), Permanent(MOUNTAIN)])
        self.assertFalse(game.has_keyword(self.bear, "haste"))

    def test_in_an_opponents_graveyard_it_does_nothing_for_you(self):
        game, a, b = self.table([], [Permanent(MOUNTAIN)])
        b.graveyard = [ANGER]
        self.assertFalse(game.has_keyword(self.bear, "haste"))

    def test_it_works_for_the_graveyard_owner_only(self):
        game, a, b = self.table([], [])
        theirs = Permanent(BEAR, sick=True)
        b.battlefield = [theirs, Permanent(MOUNTAIN)]
        b.graveyard = [ANGER]
        self.assertEqual((game.has_keyword(theirs, "haste"), game.has_keyword(self.bear, "haste")), (True, False))

    def test_it_stops_when_the_card_leaves_the_graveyard(self):
        game, a, b = self.table([ANGER], [Permanent(MOUNTAIN)])
        a.graveyard = []
        self.assertFalse(game.has_keyword(self.bear, "haste"))


COMMAND = Card(name="Quandrix Command", mana_cost="{1}{G}{U}", cmc=3.0, type_line="Instant",
               oracle_text="Choose two —\n• Return target creature or planeswalker to its owner's hand.\n• Counter target "
                           "artifact or enchantment spell.\n• Put two +1/+1 counters on target creature.\n• Target player "
                           "shuffles up to three target cards from their graveyard into their library.")


class QuandrixCommandTests(unittest.TestCase):
    def cast(self, graveyard, *choices):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.bear = Permanent(BEAR)
        a.battlefield = [self.bear] + lands(3)
        a.hand = [COMMAND]
        a.graveyard = list(graveyard)
        a.library = [FOREST] * 5
        game._perform(a, CAST + "Quandrix Command")
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(COMMAND), [])

    def test_up_to_three_cards_are_shuffled_into_the_library(self):
        game, a = self.cast([RELIC, SHRINE, FOREST, OGRE_CARD], "Put two", "Target player", "Relic", "Shrine", "Forest", "Ogre")
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Ogre", "Quandrix Command"])
        self.assertEqual(len(a.library), 8)

    def test_it_pairs_with_the_counter_mode(self):
        game, a = self.cast([RELIC], "Put two", "Target player", "Bear", "Relic")
        self.assertEqual((self.bear.counters.get("+1/+1"), [c.name for c in a.graveyard]), (2, ["Quandrix Command"]))

    def test_it_may_shuffle_nothing(self):
        game, a = self.cast([RELIC], "Put two", "Target player", "Bear", "No target")
        self.assertEqual([c.name for c in a.graveyard], ["Relic", "Quandrix Command"])


OGRE_CARD = Card(name="Ogre", mana_cost="{3}", cmc=3.0, type_line="Creature — Ogre", power="3", toughness="3")
