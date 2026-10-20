"""Counter-related text of the real cards in issue #76."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
from infernal_machine.effects import (HYPOTHESIS_COUNTER_PROMPT, PARITY_PROMPT, Counter, OpponentsLoseCounters,
                                      RemoveAllCountersDraw, VowCounters, ZimonesHypothesis, spell_effects, suspend_of)
from infernal_machine.game import CAST, MODE_PROMPT, OPTIONAL_PROMPT, SUSPEND, X_PROMPT, Permanent, StackItem
from infernal_machine.mana import Cost
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

RELIC = Card(name="Relic", type_line="Artifact")


class PlusOneReplacementTests(unittest.TestCase):
    def test_kami_adds_one_to_counters_on_any_permanent_you_control(self):
        game, _ = table3()
        a, b, _c = game.seats
        a.battlefield = [Permanent(REAL["Kami of Whispered Hopes"])]
        relic, bear, theirs = Permanent(RELIC), Permanent(BEAR), Permanent(BEAR)
        a.battlefield += [relic, bear]
        b.battlefield = [theirs]
        for permanent in (relic, bear, theirs):
            game.put_counters(permanent, "+1/+1", 1)
        self.assertEqual((relic.counters, bear.counters, theirs.counters), ({"+1/+1": 2}, {"+1/+1": 2}, {"+1/+1": 1}))

    def test_ozolith_covers_artifacts_and_creatures_but_not_lands_or_other_counters(self):
        game, _ = table3()
        a = game.seats[0]
        land = Permanent(Card(name="Forest", type_line="Basic Land", produced_mana=("G",)))
        relic, bear = Permanent(RELIC), Permanent(BEAR)
        a.battlefield = [Permanent(REAL["Ozolith, the Shattered Spire"]), relic, bear, land]
        for permanent in (relic, bear, land):
            game.put_counters(permanent, "+1/+1", 1)
        game.put_counters(bear, "charge", 1)
        self.assertEqual((relic.counters, bear.counters, land.counters),
                         ({"+1/+1": 2}, {"+1/+1": 2, "charge": 1}, {"+1/+1": 1}))

    def test_two_of_them_add_up(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(REAL["Kami of Whispered Hopes"]), Permanent(REAL["Ozolith, the Shattered Spire"]), bear]
        game.put_counters(bear, "+1/+1", 1)
        self.assertEqual(bear.counters, {"+1/+1": 3})


class KamiManaTests(unittest.TestCase):
    def test_it_taps_for_as_much_mana_as_its_power(self):
        game, _ = table3()
        a = game.seats[0]
        kami = Permanent(REAL["Kami of Whispered Hopes"], counters={"+1/+1": 2})  # a 1/1 with two counters
        a.battlefield = [kami]
        sorcery = Card(name="Big", mana_cost="{G}{G}{G}", type_line="Sorcery")
        self.assertIsNotNone(game._payment(a, sorcery))
        self.assertIsNone(game._payment(a, replace(sorcery, mana_cost="{G}{G}{G}{G}")))
        kami.sick = True  # a creature that just came in cannot tap for mana
        self.assertIsNone(game._payment(a, sorcery))


class EntersWithCountersTests(unittest.TestCase):
    def test_primo_enters_with_twice_x(self):
        game, _ = table3()
        a = game.seats[0]
        primo = Permanent(REAL["Primo, the Unbounded"])
        game._enter(a, primo, x=3)
        self.assertEqual(primo.counters, {"+1/+1": 6})
        self.assertEqual(game.power(primo), 6)

    def test_primo_makes_a_fractal_as_big_as_the_damage_dealt_by_base_power_zero_creatures(self):
        game, _ = table3()
        a, b, _c = game.seats
        primo = Permanent(REAL["Primo, the Unbounded"], counters={"+1/+1": 4})  # a 4/4 whose base power is 0
        a.battlefield = [primo]
        game.combat.attacks = [Attack(primo, a, b)]
        game.combat.deal_damage(first_strike_step=False)
        run_stack(game)
        [fractal] = [p for p in a.battlefield if p.card.name == "Fractal"]
        self.assertEqual((b.life, fractal.counters), (36, {"+1/+1": 4}))

    def test_woe_strider_escapes_with_two_counters_but_is_not_cast_with_them(self):
        game, _ = table3()
        a = game.seats[0]
        cast = Permanent(REAL["Woe Strider"])
        escaped = Permanent(REAL["Woe Strider"], escaped=True)
        game._enter(a, cast)
        game._enter(a, escaped)
        self.assertEqual((cast.counters, escaped.counters), ({}, {"+1/+1": 2}))


class AlteredEgoTests(unittest.TestCase):
    def test_it_copies_a_creature_with_x_additional_counters(self):
        game, _ = table3(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Bear")), 0))
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR)]
        ego = Permanent(REAL["Altered Ego"])
        game._enter(a, ego, x=3)
        self.assertEqual((ego.card.name, ego.counters, game.power(ego)), (BEAR.name, {"+1/+1": 3}, 2 + 3))

    def test_it_cannot_be_countered(self):
        game, _ = table3()
        a, b, _c = game.seats
        spell = StackItem(REAL["Altered Ego"], a, [])
        game.stack.append(spell)
        Counter().resolve(game, b, spell)
        self.assertIn(spell, game.stack)


class PrimordialHydraTests(unittest.TestCase):
    def test_it_doubles_each_upkeep_and_tramples_from_ten_counters(self):
        game, _ = table3()
        a = game.seats[0]
        hydra = Permanent(REAL["Primordial Hydra"], counters={"+1/+1": 3})
        a.battlefield = [hydra]
        self.assertFalse(game.has_keyword(hydra, "trample"))
        game.trigger("upkeep", hydra, a)
        run_stack(game)
        self.assertEqual((hydra.counters, game.has_keyword(hydra, "trample")), ({"+1/+1": 6}, False))
        game.trigger("upkeep", hydra, a)
        run_stack(game)
        self.assertEqual((hydra.counters, game.has_keyword(hydra, "trample")), ({"+1/+1": 12}, True))


class NevTests(unittest.TestCase):
    def test_creatures_with_counters_have_trample(self):
        game, _ = table3()
        a, b, _c = game.seats
        with_counter, without, theirs = Permanent(BEAR, counters={"+1/+1": 1}), Permanent(BEAR), Permanent(BEAR, counters={"+1/+1": 1})
        a.battlefield = [Permanent(REAL["Nev, the Practical Dean"]), with_counter, without]
        b.battlefield = [theirs]
        self.assertEqual([game.has_keyword(p, "trample") for p in (with_counter, without, theirs)], [True, False, False])


class GormaTests(unittest.TestCase):
    def test_nontoken_creatures_enter_with_a_counter_for_each_creature_that_died_this_turn(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(REAL["Gorma, the Gullet"]), Permanent(BEAR), Permanent(BEAR)]
        before = Permanent(BEAR)
        game._enter(a, before)
        self.assertEqual(before.counters, {})  # nothing has died yet
        for dying in list(a.battlefield[1:3]):
            game.destroy(dying)
        late, token = Permanent(BEAR), Permanent(replace(BEAR, type_line="Token " + BEAR.type_line))
        game._enter(a, late)
        game._enter(a, token)
        self.assertEqual((late.counters, token.counters), ({"+1/+1": 2}, {}))
        game.turn += 1
        next_turn = Permanent(BEAR)
        game._enter(a, next_turn)
        self.assertEqual(next_turn.counters, {})


class ZimoneTests(unittest.TestCase):
    X_SPELL = Card(name="Blaze", mana_cost="{X}{R}", type_line="Sorcery", oracle_text="Draw X cards.")

    def test_the_first_x_spell_each_turn_costs_less_for_each_counter(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(REAL["Zimone, Infinite Analyst"], counters={"+1/+1": 2})]
        self.assertEqual(game.cost_reduction(a, self.X_SPELL), 2)
        self.assertEqual(game.cost_reduction(a, BEAR), 0)  # not an X spell
        a.cast_log.append((game.turn, self.X_SPELL))
        self.assertEqual(game.cost_reduction(a, self.X_SPELL), 0)  # only the first


class FinalActTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(REAL["Final Act"]), [])

    def test_opponents_lose_their_counters_and_you_keep_yours(self):
        game, _ = table3()
        a, b, c = game.seats
        a.player_counters, b.player_counters, c.player_counters = {"poison": 1}, {"poison": 3}, {"energy": 2}
        OpponentsLoseCounters().resolve(game, a, None)
        self.assertEqual((a.player_counters, b.player_counters, c.player_counters), ({"poison": 1}, {}, {}))


class NexusMentalityTests(unittest.TestCase):
    CARD = REAL["Nexus Mentality"]

    def modes(self, with_commander):
        def policy(prompt, options):
            return 0
        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(RELIC), Permanent(RELIC)]  # something for each mode to target
        if with_commander:
            a.battlefield.append(Permanent(Card(name="Omnath", type_line="Legendary Creature", power="1", toughness="1")))
        modal = spell_effects(self.CARD)[0]
        _effects, _ = game._choose_modes(a, self.CARD, modal, casting=True)
        return [p for p, o in game.seats[0].player.prompts if p.startswith(MODE_PROMPT)]

    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(self.CARD), [])

    def test_one_mode_normally_and_both_with_a_commander(self):
        self.assertEqual(len(self.modes(False)), 1)
        self.assertEqual(len(self.modes(True)), 2)

    def test_move_all_counters_of_every_kind(self):
        game, _ = table3()
        a = game.seats[0]
        source, destination = Permanent(RELIC, counters={"+1/+1": 2, "charge": 3}), Permanent(RELIC, counters={"charge": 1})
        game.move_counters(source, destination, None, None)
        self.assertEqual((source.counters, destination.counters), ({}, {"+1/+1": 2, "charge": 4}))

    def test_remove_all_counters_and_draw_that_many(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 6
        relic = Permanent(RELIC, counters={"+1/+1": 2, "charge": 3})
        a.battlefield = [relic]
        RemoveAllCountersDraw("nonland permanent you control").resolve(game, a, relic)
        self.assertEqual((relic.counters, len(a.hand)), ({}, 5))


class ZimonesHypothesisTests(unittest.TestCase):
    def cast(self, counter_on, parity):
        def policy(prompt, options):
            if HYPOTHESIS_COUNTER_PROMPT.matches(prompt):
                return counter_on
            if PARITY_PROMPT.matches(prompt):
                return parity
            return 0
        game, _ = table3(policy)
        a, b, _c = game.seats
        two, three, four = Permanent(BEAR), Permanent(replace(BEAR, power="3")), Permanent(replace(BEAR, power="4"))
        a.battlefield, b.battlefield = [two, three], [four]
        ZimonesHypothesis().resolve(game, a, None)
        return a, b

    def test_even_returns_the_even_power_creatures(self):
        a, b = self.cast(counter_on=0, parity=1)  # a counter on the first creature: it is a 3/3 now; even: only the 4-power one
        self.assertEqual(([p.card.power for p in a.battlefield], len(b.battlefield)), (["2", "3"], 0))

    def test_odd_returns_the_odd_power_creatures_and_zero_is_even(self):
        a, b = self.cast(counter_on=3, parity=0)  # no counter (the last option); odd: the 3-power one
        self.assertEqual(([p.card.power for p in a.battlefield], len(b.battlefield)), (["2"], 1))


class ManaBloomTests(unittest.TestCase):
    BLOOM = REAL["Mana Bloom"]

    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(self.BLOOM), [])

    def test_a_counter_makes_one_mana_once_each_turn(self):
        game, _ = table3()
        a = game.seats[0]
        bloom = Permanent(self.BLOOM)
        game._enter(a, bloom, x=3)
        a.battlefield = [bloom]
        one = Card(name="One", mana_cost="{R}", type_line="Sorcery")
        two = Card(name="Two", mana_cost="{R}{R}", type_line="Sorcery")
        self.assertIsNone(game._payment(a, two))  # one mana a turn
        payment = game._payment(a, one)
        game._spend_mana(a, payment)
        self.assertEqual((bloom.counters, bloom.tapped), ({"charge": 2}, False))
        self.assertIsNone(game._payment(a, one))  # already used this turn
        game.turn += 1
        self.assertIsNotNone(game._payment(a, one))

    def test_with_no_counters_it_returns_to_hand_at_upkeep(self):
        game, _ = table3()
        a = game.seats[0]
        bloom = Permanent(self.BLOOM)
        a.battlefield = [bloom]
        game.trigger("upkeep", bloom, a)
        run_stack(game)
        self.assertEqual((a.battlefield, a.hand), ([], [self.BLOOM]))
        bloom = Permanent(self.BLOOM, counters={"charge": 1})
        a.battlefield, a.hand = [bloom], []
        game.trigger("upkeep", bloom, a)
        run_stack(game)
        self.assertEqual((a.battlefield, a.hand), ([bloom], []))


class SilkguardTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(REAL["Silkguard"]), [])

    def test_counters_on_up_to_x_creatures_and_hexproof_for_the_modified(self):
        def policy(prompt, options):
            if X_PROMPT.matches(prompt):
                return 2
            return pick(CAST)(prompt, options)
        game, _ = table3(policy)
        a = game.seats[0]
        one, two, three = Permanent(BEAR), Permanent(BEAR), Permanent(BEAR)
        aura = Permanent(REAL["Pacifism"], attached_to=three)
        a.hand, a.battlefield = [REAL["Silkguard"]], [one, two, three, aura, *lands(3)]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual([p.counters for p in (one, two, three)], [{"+1/+1": 1}, {"+1/+1": 1}, {}])
        self.assertEqual([game.has_keyword(p, "hexproof") for p in (one, two, three, aura)], [True, True, True, True])

    def test_x_zero_targets_nothing(self):
        game, _ = table3(lambda prompt, options: 0 if X_PROMPT.matches(prompt) else pick(CAST)(prompt, options))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.hand, a.battlefield = [REAL["Silkguard"]], [bear, *lands(2)]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual((bear.counters, game.has_keyword(bear, "hexproof")), ({}, False))


class PromiseOfLoyaltyTests(unittest.TestCase):
    def test_each_player_keeps_one_creature_and_it_cannot_attack_the_caster(self):
        game, _ = table3(lambda prompt, options: 0)
        a, b, c = game.seats
        a.battlefield = [Permanent(BEAR), Permanent(BEAR)]
        b.battlefield = [Permanent(BEAR), Permanent(BEAR), Permanent(BEAR)]
        VowCounters().resolve(game, a, None)
        self.assertEqual((len(a.battlefield), len(b.battlefield), len(c.battlefield)), (1, 1, 0))
        kept = b.battlefield[0]
        self.assertEqual((kept.counters, kept.vow_of), ({"vow": 1}, a))
        game.step = "declare_attackers"
        asked = []
        b.player = type(b.player)("B", lambda prompt, options: asked.append(options) or 0)
        game.combat.declare_attackers(b)
        self.assertTrue(all("seat 0" not in option for option in asked[0]))  # not the caster
        self.assertTrue(any("seat 2" in option for option in asked[0]))

    def test_without_the_vow_counter_it_may_attack_again(self):
        game, _ = table3()
        a, b, _c = game.seats
        bear = Permanent(BEAR, counters={"vow": 1})
        bear.vow_of = a
        b.battlefield = [bear]
        self.assertEqual(game.combat._attackable(b, bear, game.opponents(b), [])[0], [game.seats[2]])
        game.remove_counters(bear, "vow", 1)
        self.assertEqual(game.combat._attackable(b, bear, game.opponents(b), [])[0], [a, game.seats[2]])


class NilsTests(unittest.TestCase):
    NILS = REAL["Nils, Discipline Enforcer"]

    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(self.NILS), [])

    def test_attackers_with_counters_pay_x_to_attack_nils_controller(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(self.NILS)]
        carrier = Permanent(BEAR, counters={"+1/+1": 2})
        b.battlefield = [carrier, *lands(1)]
        self.assertEqual(game.combat._attack_tax(carrier, a), Cost(generic=2))
        self.assertEqual(game.combat._attack_tax(carrier, c), Cost())
        self.assertEqual(game.combat._attackable(b, carrier, game.opponents(b), [])[0], [c])  # it cannot pay {2}
        b.battlefield.append(Permanent(RELIC))
        b.battlefield += lands(1)
        self.assertEqual(game.combat._attackable(b, carrier, game.opponents(b), [])[0], [a, c])

    def test_the_end_step_trigger_gives_each_player_a_counter(self):
        game, _ = table3(lambda prompt, options: 0)
        a, b, c = game.seats
        bears = [Permanent(BEAR), Permanent(BEAR), Permanent(BEAR)]
        a.battlefield, b.battlefield, c.battlefield = [Permanent(self.NILS), bears[0]], [bears[1]], [bears[2]]
        game.trigger("end_step", a.battlefield[0], a)
        run_stack(game)
        nils = a.battlefield[0]
        self.assertEqual([nils.counters] + [p.counters for p in bears[1:]], [{"+1/+1": 1}] * 3)  # (the first choice was Nils)


class ShadrixTests(unittest.TestCase):
    SHADRIX = REAL["Shadrix Silverquill"]

    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(self.SHADRIX), [])

    def test_two_modes_for_two_different_players(self):
        game, _ = table3(lambda prompt, options: 0)
        a, b, c = game.seats
        a.battlefield = [Permanent(self.SHADRIX)]
        b.library = [BEAR] * 3
        game.trigger("combat", a.battlefield[0], a)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Shadrix Silverquill", "Inkling"])
        self.assertEqual((b.life, len(b.hand), a.life), (39, 1, 40))  # a different player drew and lost life

    def test_the_controller_may_decline(self):
        game, _ = table3(lambda prompt, options: 1 if OPTIONAL_PROMPT.matches(prompt) else 0)
        a, b, c = game.seats
        a.battlefield = [Permanent(self.SHADRIX)]
        game.trigger("combat", a.battlefield[0], a)
        run_stack(game)
        self.assertEqual(len(a.battlefield), 1)


class RousingRefrainTests(unittest.TestCase):
    REFRAIN = REAL["Rousing Refrain"]

    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(self.REFRAIN), [])
        self.assertEqual(suspend_of(self.REFRAIN), (3, "{1}{R}"))

    def test_casting_it_adds_red_for_the_opponents_hand_and_suspends_it(self):
        game, _ = table3(pick(CAST, "Player: B"))
        a, b, _c = game.seats
        b.hand = [BEAR] * 4
        a.hand, a.battlefield = [self.REFRAIN], lands(5)
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(len(a.mana_pool), 4)
        self.assertEqual(([c.name for c in a.exile], a.suspended, a.graveyard), (["Rousing Refrain"], [[self.REFRAIN, 3]], []))

    def test_the_mana_lasts_through_the_steps_of_the_turn_and_goes_at_cleanup(self):
        game, _ = table3()
        a = game.seats[0]
        game.add_mana(a, (frozenset("R"),) * 3)
        a.keep_pool_turn = game.turn
        game.step = "main1"
        game._empty_pools()
        self.assertEqual(len(a.mana_pool), 3)
        game.step = "cleanup"
        game._empty_pools()
        self.assertEqual(a.mana_pool, [])

    def test_suspend_from_hand_then_it_is_cast_free_when_the_last_counter_goes(self):
        game, _ = table3(pick(CAST, "Player: B"))
        a, b, _c = game.seats
        b.hand = [BEAR] * 2
        a.hand, a.battlefield = [self.REFRAIN], lands(2)
        self.assertIn(SUSPEND + "Rousing Refrain", game.legal_actions(a))
        game._perform(a, SUSPEND + "Rousing Refrain")
        self.assertEqual((a.hand, a.suspended), ([], [[self.REFRAIN, 3]]))
        for upkeep in (1, 2):
            game._tick_suspend(a)
            self.assertEqual(a.suspended[0][1], 3 - upkeep)
        game.step = "upkeep"
        game._tick_suspend(a)
        run_stack(game)
        self.assertEqual(len(a.mana_pool), 2)  # cast without paying, naming the opponent with two cards
        self.assertEqual(a.suspended, [[self.REFRAIN, 3]])  # and it exiled itself with three counters again
