"""Retrace, backup, demonstrate, bestow and encore on the real cards that have them (issue #74)."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.effects import DEMONSTRATE_PROMPT, alternative_costs, graveyard_casts, triggered_abilities
from infernal_machine.game import CAST, CAST_GRAVEYARD, COST_PROMPT, ENCORE, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


class RetraceTests(unittest.TestCase):
    def test_throes_of_chaos_is_understood(self):
        self.assertEqual(unsupported_lines(REAL["Throes of Chaos"]), [])
        [retrace] = graveyard_casts(REAL["Throes of Chaos"])
        self.assertEqual((retrace.word, retrace.cost, retrace.discard_land), ("Retrace", "{3}{R}", True))

    def test_it_is_cast_from_the_graveyard_by_discarding_a_land(self):
        game, _ = table3()
        a = game.seats[0]
        throes = REAL["Throes of Chaos"]
        a.graveyard, a.hand, a.library = [throes], [FOREST], [BEAR] * 5
        a.battlefield = lands(4)
        self.assertIn(CAST_GRAVEYARD + "Throes of Chaos", game.legal_actions(a))
        game._perform(a, CAST_GRAVEYARD + "Throes of Chaos")
        run_stack(game)
        self.assertEqual(a.hand, [])  # the Forest was discarded
        self.assertIn(FOREST, a.graveyard)
        self.assertIn(throes, a.graveyard)  # not exiled: it can be cast again

    def test_it_needs_a_land_in_hand(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard, a.hand = [REAL["Throes of Chaos"]], [BEAR]
        a.battlefield = lands(4)
        self.assertNotIn(CAST_GRAVEYARD + "Throes of Chaos", game.legal_actions(a))


class DemonstrateTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for name in ("Replication Technique", "Creative Technique"):
            self.assertEqual(unsupported_lines(REAL[name]), [], name)

    def test_the_caster_and_an_opponent_each_copy_the_spell(self):
        game, _ = table3(pick(CAST))
        a, b, _c = game.seats
        a.hand, a.battlefield = [REAL["Replication Technique"]], [Permanent(BEAR), *lands(5)]
        b.battlefield = [Permanent(replace(BEAR, name="Opposing Bear"))]
        game._priority_round(a)
        run_stack(game)
        bears = lambda seat: sum(p.card.name in ("Bear", "Opposing Bear") for p in seat.battlefield)
        self.assertEqual((bears(a), bears(b)), (3, 2))  # the spell and the caster's copy; the opponent's copy

    def test_the_caster_may_decline(self):
        game, _ = table3(lambda prompt, options: 1 if DEMONSTRATE_PROMPT.matches(prompt) else pick(CAST)(prompt, options))
        a, b, _c = game.seats
        a.hand, a.battlefield = [REAL["Replication Technique"]], [Permanent(BEAR), *lands(5)]
        b.battlefield = [Permanent(BEAR)]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual((len(a.battlefield) - 5, len(b.battlefield)), (2, 1))

    def test_creative_technique_casts_the_first_nonland_card_free(self):
        game, _ = table3(lambda prompt, options: 1 if DEMONSTRATE_PROMPT.matches(prompt) else pick(CAST)(prompt, options))
        a = game.seats[0]
        bolt = Card(name="Study", mana_cost="{5}{G}", type_line="Instant", oracle_text="Draw a card.")
        a.hand, a.battlefield = [REAL["Creative Technique"]], lands(5)
        a.library = [FOREST, bolt, FOREST, FOREST]  # the only nonland card, wherever the shuffle puts it
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)  # Study came from the library for free and drew a card


class BackupTests(unittest.TestCase):
    def enter(self, policy=None):
        game, _ = table3(policy)
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        scalelord = Permanent(REAL["Guardian Scalelord"])
        game._enter(a, scalelord)
        run_stack(game)
        return game, a, bear, scalelord

    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(REAL["Guardian Scalelord"]), [])

    def test_another_creature_gets_the_counter_and_the_abilities_until_end_of_turn(self):
        game, a, bear, scalelord = self.enter(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Bear")), 0))
        self.assertEqual(bear.counters, {"+1/+1": 1})
        self.assertTrue(game.has_keyword(bear, "flying"))
        self.assertTrue(any(t.event == "attacks" for t in triggered_abilities(bear.card)))
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual(bear.counters, {"+1/+1": 1})  # the counter stays
        self.assertFalse(game.has_keyword(bear, "flying"))

    def test_the_backup_creature_itself_just_gets_the_counter(self):
        game, a, bear, scalelord = self.enter(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Guardian")), 0))
        self.assertEqual((scalelord.counters, bear.counters), ({"+1/+1": 1}, {}))
        self.assertEqual(scalelord.card, REAL["Guardian Scalelord"])  # nothing was added to its own text

    def test_attacking_returns_a_permanent_up_to_its_power(self):
        game, _ = table3()
        a = game.seats[0]
        cheap = Card(name="Cheap Relic", mana_cost="{3}", cmc=3.0, type_line="Artifact")
        dear = Card(name="Dear Relic", mana_cost="{6}", cmc=6.0, type_line="Artifact")
        scalelord = Permanent(REAL["Guardian Scalelord"])  # power 3
        a.battlefield, a.graveyard = [scalelord], [dear, cheap, FOREST]
        game.trigger("attacks", scalelord, a)
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Cheap Relic", "Guardian Scalelord"])
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Dear Relic", "Forest"])


class EncoreTests(unittest.TestCase):
    def setup_encore(self):
        game, _ = table3()
        a, b, c = game.seats
        angel = REAL["Angel of Indemnity"]
        a.graveyard, a.battlefield = [angel], lands(8)
        return game, a, b, c, angel

    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(REAL["Angel of Indemnity"]), [])

    def test_a_token_copy_for_each_opponent_attacks_that_opponent_and_is_sacrificed(self):
        game, a, b, c, angel = self.setup_encore()
        self.assertIn(ENCORE + "Angel of Indemnity", game.legal_actions(a))
        game._perform(a, ENCORE + "Angel of Indemnity")
        run_stack(game)
        tokens = [p for p in a.battlefield if p.card.name == "Angel of Indemnity"]
        self.assertEqual(sorted(t.must_attack.index for t in tokens), [1, 2])
        self.assertTrue(all(game.has_keyword(t, "haste") for t in tokens))
        self.assertEqual((a.graveyard, a.exile), ([], [angel]))
        game.step = "declare_attackers"
        game.combat.declare_attackers(a)
        self.assertEqual(sorted(x.defender.index for x in game.combat.attacks), [1, 2])
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual([p for p in a.battlefield if p.card.name == "Angel of Indemnity"], [])

    def test_only_at_sorcery_speed_and_with_the_mana(self):
        game, a, b, c, angel = self.setup_encore()
        a.battlefield = lands(7)
        self.assertNotIn(ENCORE + "Angel of Indemnity", game.legal_actions(a))


class BestowTests(unittest.TestCase):
    EIDOLON = REAL["Eidolon of Countless Battles"]

    def cast_bestowed(self, bear):
        def policy(prompt, options):
            if COST_PROMPT.matches(prompt):
                return next(i for i, o in enumerate(options) if o.startswith("Bestow"))
            return pick(CAST)(prompt, options)
        game, _ = table3(policy)
        a = game.seats[0]
        a.hand, a.battlefield = [self.EIDOLON], [bear, *lands(4)]
        game._priority_round(a)
        run_stack(game)
        return game, a

    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(self.EIDOLON), [])
        self.assertEqual([c.bestow for c in alternative_costs(self.EIDOLON)], [True])

    def test_bestowed_it_is_an_aura_that_pumps_the_creature(self):
        bear = Permanent(BEAR)
        game, a = self.cast_bestowed(bear)
        [aura] = [p for p in a.battlefield if p.card.name == self.EIDOLON.name]
        self.assertIs(aura.attached_to, bear)
        self.assertNotIn("Creature", aura.card.type_line)
        self.assertEqual((game.power(bear), game.toughness(bear)), (2 + 2, 2 + 2))  # one creature, one Aura

    def test_it_becomes_a_creature_when_its_creature_leaves(self):
        bear = Permanent(BEAR)
        game, a = self.cast_bestowed(bear)
        game.destroy(bear)
        game._check_state()
        [eidolon] = [p for p in a.battlefield if p.card.name == self.EIDOLON.name]
        self.assertEqual((eidolon.card, eidolon.attached_to), (self.EIDOLON, None))
        self.assertEqual((game.power(eidolon), game.toughness(eidolon)), (1, 1))  # itself is the one creature

    def test_cast_normally_it_is_a_creature(self):
        game, _ = table3(pick(CAST))
        a = game.seats[0]
        a.hand, a.battlefield = [self.EIDOLON], lands(3)
        game._priority_round(a)
        run_stack(game)
        [eidolon] = [p for p in a.battlefield if p.card.name == self.EIDOLON.name]
        self.assertEqual((game.power(eidolon), eidolon.attached_to), (1, None))

    def test_without_a_creature_there_is_no_bestow(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield = [self.EIDOLON], lands(4)
        self.assertEqual([w.bestow for w in game._cast_ways(a, self.EIDOLON, False) if w], [])
