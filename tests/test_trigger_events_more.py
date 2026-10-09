"""More trigger events and conditions: issues #70 and #71.

Each watcher is an Enchantment whose trigger gains its controller 1 life, so a test reads the life total. Every event has a
case where it must not fire.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Draw, Watch, triggered_abilities
from infernal_machine.game import CAST, CAST_GRAVEYARD, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, creature
from tests.test_effects import FOREST, lands, pick, table

ISLAND = Card(name="Island", type_line="Basic Land", produced_mana=("U",))


def watcher(text, kind="Enchantment"):
    return Card(name="Watcher", mana_cost="{1}", type_line=kind, oracle_text=text)


def settle(game):
    game._priority_round(game.seats[0])


def life(seat):
    return seat.life - 40


def ability(card):
    [found] = triggered_abilities(card)
    return found


def supported(test, card):
    test.assertEqual(unsupported_lines(card), [], card.oracle_text)


def attack_with_everything(prompt, options):
    return 1 if options[0] == "Don't attack" else 0


class BecomesTappedTests(unittest.TestCase):
    def test_parse(self):
        found = ability(watcher("Whenever a creature you control becomes tapped, you gain 1 life."))
        self.assertEqual((found.event, found.watch.kind, found.watch.yours), ("permanent_taps", "creature", True))
        supported(self, watcher("Whenever a permanent you control becomes tapped, you gain 1 life."))

    def test_only_your_creatures_and_only_when_they_were_untapped(self):
        game, _, _ = table()
        a, b = game.seats
        bear, theirs, land = Permanent(BEAR), Permanent(BEAR), Permanent(FOREST)
        a.battlefield = [Permanent(watcher("Whenever a creature you control becomes tapped, you gain 1 life.")), bear, land]
        b.battlefield = [theirs]
        game.tap(land)  # not a creature
        game.tap(theirs)  # not yours
        settle(game)
        self.assertEqual(life(a), 0)
        game.tap(bear)
        game.tap(bear)  # already tapped: it doesn't become tapped again
        settle(game)
        self.assertEqual(life(a), 1)

    def test_a_permanent_you_control_includes_lands(self):
        game, _, _ = table()
        a = game.seats[0]
        land = Permanent(FOREST)
        a.battlefield = [Permanent(watcher("Whenever a permanent you control becomes tapped, you gain 1 life.")), land]
        game.tap(land)
        settle(game)
        self.assertEqual(life(a), 1)

    def test_tapping_for_mana_and_attacking_count(self):
        game, _, _ = table(attack_with_everything)
        a = game.seats[0]
        a.battlefield = [Permanent(watcher("Whenever a creature you control becomes tapped, you gain 1 life.")),
                         Permanent(BEAR), Permanent(creature("Cat", 2, 2, "Vigilance"))]
        game.combat.declare_attackers(a)  # the Bear taps to attack; vigilance doesn't tap
        settle(game)
        self.assertEqual(life(a), 1)


class CycleScryTests(unittest.TestCase):
    def test_cycling_a_card(self):
        cycler = Card(name="Cycler", mana_cost="{3}", type_line="Instant", oracle_text="Cycling {1}")
        supported(self, watcher("Whenever you cycle a card, you gain 1 life."))
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(watcher("Whenever you cycle a card, you gain 1 life.")), *lands(2)]
        b.battlefield = [Permanent(watcher("Whenever you cycle a card, you gain 1 life.")), *lands(2)]
        a.hand = [cycler]
        game._cycle(a, cycler)
        settle(game)
        self.assertEqual((life(a), life(b)), (1, 0))

    def test_scry_and_surveil(self):
        game, _, _ = table()
        a, b = game.seats
        for text in ("Whenever you scry, you gain 1 life.", "Whenever you surveil, you gain 1 life."):
            supported(self, watcher(text))
            a.battlefield.append(Permanent(watcher(text)))
        game.scry(a, 1)
        settle(game)
        self.assertEqual(life(a), 1)  # only the scry watcher
        game.surveil(a, 1)
        game.scry(b, 1)  # an opponent's doesn't count
        settle(game)
        self.assertEqual(life(a), 2)


class AttackEventTests(unittest.TestCase):
    def test_a_creature_attacking_alone(self):
        text = "Whenever you attack with a creature alone, you gain 1 life."
        supported(self, watcher(text))
        game, _, _ = table(attack_with_everything)
        a = game.seats[0]
        a.battlefield = [Permanent(watcher(text)), Permanent(BEAR)]
        game.combat.declare_attackers(a)
        settle(game)
        self.assertEqual(life(a), 1)
        game, _, _ = table(attack_with_everything)
        a = game.seats[0]
        a.battlefield = [Permanent(watcher(text)), Permanent(BEAR), Permanent(OGRE)]
        game.combat.declare_attackers(a)
        settle(game)
        self.assertEqual(life(a), 0)  # two attackers: not alone

    def test_the_other_wording_and_it_means_the_attacker(self):
        text = "Whenever a creature you control attacks alone, put a +1/+1 counter on it."
        supported(self, watcher(text))
        game, _, _ = table(attack_with_everything)
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(watcher(text)), bear]
        game.combat.declare_attackers(a)
        settle(game)
        self.assertEqual(bear.counters, {"+1/+1": 1})

    def test_one_or_more_creatures_attack_is_one_event(self):
        text = "Whenever one or more creatures you control attack, you gain 1 life."
        supported(self, watcher(text))
        game, _, _ = table(attack_with_everything)
        a = game.seats[0]
        a.battlefield = [Permanent(watcher(text)), Permanent(BEAR), Permanent(OGRE)]
        game.combat.declare_attackers(a)
        settle(game)
        self.assertEqual(life(a), 1)

    def test_an_opponent_attacks_and_how_many_of_them_attack_you(self):
        text = ("Whenever an opponent attacks with creatures, if two or more of those creatures are attacking you and/or "
                "planeswalkers you control, you gain 1 life.")
        supported(self, watcher(text))
        for attackers, expected in (([BEAR, OGRE], 1), ([BEAR], 0)):
            game, _, _ = table(None, attack_with_everything)
            a, b = game.seats
            a.battlefield = [Permanent(watcher(text))]
            b.battlefield = [Permanent(c) for c in attackers]
            game.combat.declare_attackers(b)
            settle(game)
            self.assertEqual(life(a), expected, [c.name for c in attackers])


class EntersUnderOpponentTests(unittest.TestCase):
    def test_both_wordings(self):
        for text in ("Whenever a creature enters under an opponent's control, you gain 1 life.",
                     "Whenever a creature an opponent controls enters, you gain 1 life."):
            with self.subTest(text=text):
                supported(self, watcher(text))
                game, _, _ = table()
                a, b = game.seats
                a.battlefield = [Permanent(watcher(text))]
                game._enter(a, Permanent(BEAR))
                game._enter(b, Permanent(Card(name="Forest", type_line="Basic Land")))
                settle(game)
                self.assertEqual(life(a), 0)  # yours, and not a creature
                game._enter(b, Permanent(BEAR))
                settle(game)
                self.assertEqual(life(a), 1)


class GraveyardCastTests(unittest.TestCase):
    FLASHBACK = Card(name="Spell", mana_cost="{1}", type_line="Sorcery", oracle_text="You gain 3 life.\nFlashback {1}")

    def test_cast_from_your_graveyard_and_from_anywhere_other_than_your_hand(self):
        graveyard = "Whenever you cast a spell from your graveyard, you gain 1 life."
        elsewhere = "Whenever you cast a spell from anywhere other than your hand, you gain 1 life."
        for text in (graveyard, elsewhere):
            supported(self, watcher(text))
            game, _, _ = table(pick(CAST_GRAVEYARD, CAST))
            a = game.seats[0]
            a.battlefield = [Permanent(watcher(text)), *lands(2)]
            a.graveyard = [self.FLASHBACK]
            settle(game)
            self.assertEqual(life(a), 3 + 1, text)  # the flashback's own 3 life and the trigger
            game, _, _ = table(pick(CAST))
            a = game.seats[0]
            a.battlefield = [Permanent(watcher(text)), *lands(2)]
            a.hand = [Card(name="Spell", mana_cost="{1}", type_line="Sorcery", oracle_text="You gain 3 life.")]
            settle(game)
            self.assertEqual(life(a), 3, text)  # cast from the hand: no trigger

    def test_a_player_casts_from_their_graveyard(self):
        text = "Whenever a player casts a spell from their graveyard, you gain 1 life."
        supported(self, watcher(text))
        game, _, _ = table(None, pick(CAST_GRAVEYARD))
        a, b = game.seats
        a.battlefield = [Permanent(watcher(text))]
        b.battlefield = lands(2)
        b.graveyard = [self.FLASHBACK]
        game.active = 1
        game._priority_round(b)
        self.assertEqual(life(a), 1)


class CardToGraveyardTests(unittest.TestCase):
    TEXT = "Whenever a creature card is put into your graveyard from anywhere, you gain 1 life."

    def test_from_anywhere_and_only_yours(self):
        supported(self, watcher(self.TEXT))
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(watcher(self.TEXT))]
        game._move_card(a, BEAR, "graveyard")  # milled, discarded, died: all go through here
        game._move_card(a, Card(name="Relic", type_line="Artifact"), "graveyard")
        game._move_card(b, BEAR, "graveyard")
        game._move_card(a, BEAR, "hand")
        settle(game)
        self.assertEqual(life(a), 1)

    def test_a_creature_that_dies_counts_and_a_token_does_not(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(watcher(self.TEXT))]
        bear = Permanent(BEAR)
        a.battlefield.append(bear)
        game._leave_battlefield(bear, "dies")
        token = Permanent(Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1"))
        a.battlefield.append(token)
        game._leave_battlefield(token, "dies")
        settle(game)
        self.assertEqual(life(a), 1)


class ExpendTests(unittest.TestCase):
    TEXT = "Whenever you expend 4, you gain 1 life."

    def spell(self, cost):
        return Card(name=f"Spell {cost}", mana_cost="{%d}" % cost, type_line="Artifact")

    def test_parse(self):
        found = ability(watcher(self.TEXT))
        self.assertEqual((found.event, found.watch.expend), ("expend", 4))
        supported(self, watcher(self.TEXT))

    def test_it_fires_as_the_total_mana_spent_on_spells_this_turn_reaches_four(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.battlefield = [Permanent(watcher(self.TEXT)), *lands(6)]
        a.hand = [self.spell(3)]
        settle(game)
        self.assertEqual(life(a), 0)  # three mana so far
        a.hand = [self.spell(2)]
        settle(game)
        self.assertEqual(life(a), 1)  # five: it crossed four
        a.hand = [self.spell(1)]
        settle(game)
        self.assertEqual(life(a), 1)  # once a turn

    def test_a_new_turn_starts_the_count_again(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.battlefield = [Permanent(watcher(self.TEXT)), *lands(6)]
        a.hand = [self.spell(4)]
        settle(game)
        self.assertEqual(life(a), 1)
        game.turn += 1
        for permanent in a.battlefield:
            permanent.tapped = False
        a.hand = [self.spell(4)]
        settle(game)
        self.assertEqual(life(a), 2)


class DrawStepTests(unittest.TestCase):
    def test_draw_an_additional_card(self):
        card = watcher("At the beginning of your draw step, draw an additional card.", "Creature — Test")
        found = ability(card)
        self.assertEqual((found.event, found.effects), ("draw_step", (Draw(1),)))
        supported(self, card)
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(card)]
        b.battlefield = [Permanent(card)]
        game.step = "draw"
        game._turn_based_actions(a)
        settle(game)
        self.assertEqual((len(a.hand), len(b.hand)), (2, 0))  # the turn's draw and the extra, only for the active player


class OpponentTimingTests(unittest.TestCase):
    def test_each_opponents_upkeep_and_end_step(self):
        for text, step in (("At the beginning of each opponent's upkeep, you gain 1 life.", "upkeep"),
                           ("At the beginning of each opponent's end step, you gain 1 life.", "end"),
                           ("At the beginning of an opponent's end step, you gain 1 life.", "end")):
            with self.subTest(text=text):
                supported(self, watcher(text))
                game, _, _ = table()
                a, b = game.seats
                a.battlefield = [Permanent(watcher(text))]
                game.step = step
                game._turn_based_actions(a)  # your own turn: no
                settle(game)
                self.assertEqual(life(a), 0)
                game.active = 1
                game._turn_based_actions(b)
                settle(game)
                self.assertEqual(life(a), 1)


class InterveningIfTests(unittest.TestCase):
    def test_if_you_control_no_other_creatures(self):
        card = watcher("At the beginning of your end step, if you control no other creatures, you gain 1 life.",
                       "Creature — Test")
        self.assertEqual(ability(card).condition.kind, "control_no_other")
        supported(self, card)
        game, _, _ = table()
        a = game.seats[0]
        source = Permanent(card)
        a.battlefield = [source]
        game.trigger("end_step", source, a)
        settle(game)
        self.assertEqual(life(a), 1)  # it doesn't count itself
        a.battlefield.append(Permanent(BEAR))
        game.trigger("end_step", source, a)
        settle(game)
        self.assertEqual(life(a), 1)

    def test_if_a_modified_creature_died_under_your_control_this_turn(self):
        text = "At the beginning of each end step, if a modified creature died under your control this turn, you gain 1 life."
        supported(self, watcher(text))
        for modifier, expected in (("none", 0), ("counter", 1), ("aura", 1), ("equipment", 1)):
            with self.subTest(modifier=modifier):
                game, _, _ = table()
                a, b = game.seats
                source = Permanent(watcher(text))
                bear = Permanent(BEAR)
                a.battlefield = [source, bear]
                if modifier == "counter":
                    bear.counters["+1/+1"] = 1
                elif modifier == "aura":
                    a.battlefield.append(Permanent(Card(name="Halo", type_line="Enchantment — Aura"), attached_to=bear))
                elif modifier == "equipment":
                    a.battlefield.append(Permanent(Card(name="Sword", type_line="Artifact — Equipment"), attached_to=bear))
                game._leave_battlefield(bear, "dies")
                game.trigger("each_end_step", source, a)
                settle(game)
                self.assertEqual(life(a), expected)

    def test_a_modified_creature_of_an_opponent_does_not_count(self):
        text = "At the beginning of each end step, if a modified creature died under your control this turn, you gain 1 life."
        game, _, _ = table()
        a, b = game.seats
        source = Permanent(watcher(text))
        a.battlefield = [source]
        bear = Permanent(BEAR, counters={"+1/+1": 1})
        b.battlefield = [bear]
        game._leave_battlefield(bear, "dies")
        game.trigger("each_end_step", source, a)
        settle(game)
        self.assertEqual(life(a), 0)


class WatchQualifierTests(unittest.TestCase):
    def test_enters_with_power_4_or_greater_or_flying(self):
        for text, big, small in (("Whenever a creature you control with power 4 or greater enters, you gain 1 life.",
                                  creature("Big", 4, 4), BEAR),
                                 ("Whenever a creature you control with flying enters, you gain 1 life.",
                                  creature("Flier", 1, 1, "Flying"), BEAR)):
            with self.subTest(text=text):
                supported(self, watcher(text))
                game, _, _ = table()
                a = game.seats[0]
                a.battlefield = [Permanent(watcher(text))]
                game._enter(a, Permanent(small))
                settle(game)
                self.assertEqual(life(a), 0)
                game._enter(a, Permanent(big))
                settle(game)
                self.assertEqual(life(a), 1)

    def test_dies_with_a_counter_or_with_power_4_or_greater(self):
        for text in ("Whenever a creature you control with a +1/+1 counter on it dies, you gain 1 life.",
                     "Whenever a creature you control with power 4 or greater dies, you gain 1 life."):
            with self.subTest(text=text):
                supported(self, watcher(text))
                game, _, _ = table()
                a = game.seats[0]
                plain, marked = Permanent(BEAR), Permanent(OGRE, counters={"+1/+1": 1})  # a 4/4 with a counter
                a.battlefield = [Permanent(watcher(text)), plain, marked]
                game._leave_battlefield(plain, "dies")
                settle(game)
                self.assertEqual(life(a), 0)
                game._leave_battlefield(marked, "dies")
                settle(game)
                self.assertEqual(life(a), 1)

    def test_an_opponents_creature_with_the_quality_does_not_count(self):
        text = "Whenever a creature you control with power 4 or greater enters, you gain 1 life."
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(watcher(text))]
        game._enter(b, Permanent(creature("Big", 5, 5)))
        settle(game)
        self.assertEqual(life(a), 0)


class CastQualifierTests(unittest.TestCase):
    TEXT = "Whenever you cast a multicolored spell, you gain 1 life."

    def test_multicolored(self):
        supported(self, watcher(self.TEXT))
        for colors, expected in (((), 0), (("W",), 0), (("W", "U"), 1), (("W", "U", "B"), 1)):
            game, _, _ = table(pick(CAST))
            a = game.seats[0]
            a.battlefield = [Permanent(watcher(self.TEXT)), *lands(2)]
            a.hand = [Card(name="Gold", mana_cost="{1}", type_line="Artifact", colors=colors)]
            settle(game)
            self.assertEqual(life(a), expected, colors)
