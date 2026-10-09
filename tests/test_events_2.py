"""Trigger events of the real cards in issue #70: tapped, cycled, scried, attacks alone, an opponent's creature entering,
casting from the graveyard, creature cards reaching the graveyard, and expending mana."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.effects import untaps_in_other_untap_steps
from infernal_machine.game import CAST, CYCLE, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

CYCLER = REAL["Generous Ent"]  # forestcycling {1}
ONE_DRAW = Card(name="Quick Recall", mana_cost="{1}", cmc=1.0, type_line="Instant", oracle_text="Draw a card.")


class CreatureTappedTests(unittest.TestCase):
    QUEST = REAL["Quest for Renewal"]

    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(self.QUEST), [])

    def test_a_creature_you_control_becoming_tapped_adds_a_quest_counter(self):
        game, _ = table3(lambda prompt, options: 0)
        a, b, _c = game.seats
        quest, mine, theirs = Permanent(self.QUEST), Permanent(BEAR), Permanent(BEAR)
        a.battlefield, b.battlefield = [quest, mine], [theirs]
        mine.tapped = True
        theirs.tapped = True
        game._check_state()
        run_stack(game)
        self.assertEqual(quest.counters, {"quest": 1})
        mine.tapped = True  # already tapped: it does not become tapped again
        game._check_state()
        run_stack(game)
        self.assertEqual(quest.counters, {"quest": 1})

    def test_entering_tapped_is_not_becoming_tapped_and_non_creatures_do_not_count(self):
        game, _ = table3(lambda prompt, options: 0)
        a = game.seats[0]
        quest = Permanent(self.QUEST)
        a.battlefield = [quest, Permanent(BEAR, tapped=True), Permanent(Card(name="Relic", type_line="Artifact"))]
        a.battlefield[2].tapped = True
        game._check_state()
        run_stack(game)
        self.assertEqual(quest.counters, {})

    def test_with_four_counters_your_creatures_untap_in_the_other_players_untap_step(self):
        self.assertEqual(untaps_in_other_untap_steps(self.QUEST), ("quest", 4))
        game, _ = table3()
        a, b, _c = game.seats
        tapped = Permanent(BEAR, tapped=True)
        a.battlefield = [Permanent(self.QUEST, counters={"quest": 3}), tapped]
        game.step = "untap"
        game._turn_based_actions(b)
        self.assertTrue(tapped.tapped)
        a.battlefield[0].counters["quest"] = 4
        game._turn_based_actions(b)
        self.assertFalse(tapped.tapped)


class CycleTests(unittest.TestCase):
    def test_cycling_another_card_triggers_and_discarding_does_not(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(REAL["Drannith Healer"]), *lands(2)]
        a.hand, a.library = [CYCLER, BEAR], [BEAR] * 3
        game._perform(a, CYCLE + CYCLER.name)
        run_stack(game)
        self.assertEqual(a.life, 41)
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual(a.life, 41)

    def test_cycle_or_discard_covers_both(self):
        game, _ = table3()
        a = game.seats[0]
        vizier = Permanent(REAL["Pitiless Vizier"])
        a.battlefield, a.hand, a.library = [vizier, *lands(2)], [CYCLER, BEAR], [BEAR] * 3
        game._perform(a, CYCLE + CYCLER.name)
        run_stack(game)
        self.assertTrue(game.has_keyword(vizier, "indestructible"))
        vizier.until_end_of_turn.clear()
        game.discard(a, 1)
        run_stack(game)
        self.assertTrue(game.has_keyword(vizier, "indestructible"))


class ScryAndSurveilTests(unittest.TestCase):
    def test_scry_or_surveil_puts_counters_on_each_creature(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(REAL["Denzilore Fatehold"]), Permanent(BEAR)]
        a.library = [BEAR] * 5
        game.scry(a, 1)
        run_stack(game)
        game.surveil(a, 1)
        run_stack(game)
        game.scry(a, 0)  # nothing is looked at
        run_stack(game)
        self.assertEqual([p.counters for p in a.battlefield], [{"+1/+1": 2}] * 2)

    def test_scry_only_triggers_once_each_turn_for_the_watcher(self):
        game, _ = table3()
        a = game.seats[0]
        watcher = Permanent(REAL["Nimrodel Watcher"])
        a.battlefield, a.library = [watcher], [BEAR] * 5
        game.scry(a, 1)
        run_stack(game)
        game.scry(a, 1)
        run_stack(game)
        game.surveil(a, 1)  # not a scry
        run_stack(game)
        self.assertEqual((game.power(watcher), game.has_keyword(watcher, "can't be blocked")), (2 + 1, True))


class AttackAloneTests(unittest.TestCase):
    @staticmethod
    def policy(prompt, options):
        return next((i for i, o in enumerate(options) if o.startswith("Attack Player: B")), 0)

    def attack(self, count):
        game, _ = table3(self.policy)
        a = game.seats[0]
        squire = Permanent(REAL["Aven Squire"])
        a.battlefield = [squire, *[Permanent(BEAR) for _ in range(count - 1)]]
        game.combat.declare_attackers(a)
        run_stack(game)
        return game, squire

    def test_exalted_pumps_a_lone_attacker(self):
        game, squire = self.attack(1)
        self.assertEqual((game.power(squire), game.toughness(squire)), (1 + 1, 1 + 1))

    def test_two_attackers_are_not_alone(self):
        game, squire = self.attack(2)
        self.assertEqual(game.power(squire), 1)

    def test_black_panther_gets_a_counter_when_a_creature_attacks_alone(self):
        game, _ = table3(self.policy)
        a = game.seats[0]
        panther, bear = Permanent(REAL["Black Panther, Claws of Bast"]), Permanent(BEAR)
        a.battlefield = [panther, bear]
        panther.tapped = True  # only the Bear can attack
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual((bear.counters, panther.counters), ({}, {"+1/+1": 1}))  # the counter goes on Black Panther himself


class OpponentCreatureEntersTests(unittest.TestCase):
    def test_an_opponents_creature_entering_costs_them_life_but_yours_does_not(self):
        game, _ = table3(lambda prompt, options: 0)
        a, b, _c = game.seats
        a.battlefield = [Permanent(REAL["Blood Seeker"])]
        game._enter(a, Permanent(BEAR))
        run_stack(game)
        self.assertEqual((a.life, b.life), (40, 40))
        game._enter(b, Permanent(BEAR))
        run_stack(game)
        self.assertEqual((a.life, b.life), (40, 39))


class CastFromGraveyardTests(unittest.TestCase):
    def test_only_a_spell_cast_from_your_graveyard_triggers(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield, a.library = [Permanent(REAL["Secrets of the Dead"])], [BEAR] * 4
        item = StackItem(ONE_DRAW, a, [])
        game._observe("cast", ONE_DRAW, a, spell=item)
        run_stack(game)
        self.assertEqual(len(a.hand), 0)  # from the hand
        game._observe("cast", ONE_DRAW, a, spell=item, from_graveyard=True)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)
        game._observe("cast", ONE_DRAW, b, spell=item, from_graveyard=True)  # an opponent's
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_it_works_with_a_flashed_back_spell(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        flashback = Card(name="Rewind", mana_cost="{9}", cmc=9.0, type_line="Sorcery",
                         oracle_text="Draw a card.\nFlashback {1}")
        a.battlefield, a.library = [Permanent(REAL["Secrets of the Dead"]), *lands(2)], [BEAR] * 4
        a.graveyard = [flashback]
        game._perform(a, "Cast from graveyard: Rewind")
        run_stack(game)
        self.assertEqual(len(a.hand), 2)  # the spell's own draw, and the trigger's


class CreatureCardToGraveyardTests(unittest.TestCase):
    # No fully supported real card has this trigger (Soulcipher Board also transforms), so this watcher is invented.
    WATCHER = Card(name="Grave Watcher", type_line="Artifact",
                   oracle_text="Whenever a creature card is put into your graveyard from anywhere, you gain 1 life.")

    def test_a_creature_card_reaching_your_graveyard_from_anywhere(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield = [Permanent(self.WATCHER)]
        a.hand = [BEAR]
        game.discard(a, 1)  # from the hand
        game._move_card(a, BEAR, "graveyard")  # from the library, say
        game._move_card(a, ONE_DRAW, "graveyard")  # not a creature
        game._move_card(b, BEAR, "graveyard")  # an opponent's graveyard
        run_stack(game)
        self.assertEqual(a.life, 42)


class ExpendTests(unittest.TestCase):
    def cast(self, game, seat, mana):
        spell = replace(ONE_DRAW, mana_cost="{" + str(mana) + "}", cmc=float(mana))
        seat.battlefield += lands(mana)
        seat.hand = [spell]
        game._perform(seat, CAST + spell.name)
        run_stack(game)

    def test_the_fourth_mana_spent_fires_once(self):
        game, _ = table3(pick(CAST))
        a, b, _c = game.seats
        a.battlefield = [Permanent(REAL["Teapot Slinger"])]
        a.library = [BEAR] * 9
        self.cast(game, a, 3)
        self.assertEqual(b.life, 40)  # three so far
        self.cast(game, a, 2)
        self.assertEqual(b.life, 38)  # the fourth was spent
        self.cast(game, a, 3)
        self.assertEqual(b.life, 38)  # expend 4 happens once a turn
        game.turn += 1
        self.cast(game, a, 4)
        self.assertEqual(b.life, 36)

    def test_junkblade_bruiser_and_wandertale_mentor(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        bruiser, mentor = Permanent(REAL["Junkblade Bruiser"]), Permanent(REAL["Wandertale Mentor"])
        a.battlefield, a.library = [bruiser, mentor], [BEAR] * 9
        self.cast(game, a, 4)
        self.assertEqual((game.power(bruiser), mentor.counters), (4 + 2, {"+1/+1": 1}))
