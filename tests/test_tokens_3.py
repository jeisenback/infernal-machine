"""Token-making text of the real cards in issue #77."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
from infernal_machine.game import CAST, MODE_PROMPT, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

TOKEN_BEAR = replace(BEAR, name="Bear Token", type_line="Token " + BEAR.type_line)


def names(seat, *, only=None):
    return sorted(p.card.name for p in seat.battlefield if "Land" not in p.card.type_line)


class DrawAndTreasureTests(unittest.TestCase):
    def test_big_score_discards_draws_two_and_makes_two_treasures(self):
        game, _ = table3(pick(CAST + "Big Score"))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [REAL["Big Score"], BEAR], lands(4), [BEAR] * 5
        game._priority_round(a)
        run_stack(game)
        self.assertEqual((len(a.hand), names(a)), (2, ["Treasure", "Treasure"]))  # the Bear was discarded, two drawn

    def test_seize_the_spoils_makes_one(self):
        game, _ = table3(pick(CAST + "Seize"))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [REAL["Seize the Spoils"], BEAR], lands(3), [BEAR] * 5
        game._priority_round(a)
        run_stack(game)
        self.assertEqual((len(a.hand), names(a)), (2, ["Treasure"]))


class RapidHybridizationTests(unittest.TestCase):
    def test_the_creatures_controller_gets_a_frog_lizard(self):
        game, _ = table3(pick(CAST, "Bear"))
        a, b, _c = game.seats
        a.hand, a.battlefield = [REAL["Rapid Hybridization"]], lands(1)
        b.battlefield = [Permanent(BEAR)]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual((names(a), names(b)), ([], ["Frog Lizard"]))
        [token] = [p for p in b.battlefield]
        self.assertEqual((token.card.power, token.card.toughness), ("3", "3"))


class PerplexingTestTests(unittest.TestCase):
    def test_the_tokens_mode_returns_only_tokens(self):
        game, _ = table3(lambda prompt, options: 0)
        a, b, _c = game.seats
        a.hand, a.battlefield = [REAL["Perplexing Test"]], [Permanent(BEAR), Permanent(TOKEN_BEAR), *lands(5)]
        b.battlefield = [Permanent(TOKEN_BEAR), Permanent(BEAR)]
        game.step = "main1"
        game._perform(a, CAST + "Perplexing Test")
        run_stack(game)
        self.assertEqual((names(a), names(b)), ([BEAR.name], [BEAR.name]))

    def test_the_other_mode_returns_the_nontoken_creatures(self):
        game, _ = table3(lambda prompt, options: 1 if prompt.startswith(MODE_PROMPT) else 0)
        a, b, _c = game.seats
        a.hand, a.battlefield = [REAL["Perplexing Test"]], [Permanent(BEAR), Permanent(TOKEN_BEAR), *lands(5)]
        game._perform(a, CAST + "Perplexing Test")
        run_stack(game)
        self.assertEqual((names(a), [c.name for c in a.hand]), (["Bear Token"], [BEAR.name]))


class DeekahTests(unittest.TestCase):
    def test_a_fractal_with_counters_equal_to_the_spells_mana_value(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(REAL["Deekah, Fractal Theorist"])]
        spell = Card(name="Study", mana_cost="{1}{U}", cmc=2.0, type_line="Instant", oracle_text="Draw a card.")
        a.cast_log.append((game.turn, spell))
        game._observe("cast", spell, a, spell=StackItem(spell, a, []))
        run_stack(game)
        [fractal] = [p for p in a.battlefield if p.card.name == "Fractal"]
        self.assertEqual(fractal.counters, {"+1/+1": 2})


def x_policy(x, *prefixes):
    from infernal_machine.game import X_PROMPT
    return lambda prompt, options: x if prompt.startswith(X_PROMPT) else pick(*prefixes)(prompt, options)


class CurseOfTheSwineTests(unittest.TestCase):
    def test_x_creatures_are_exiled_and_their_controllers_get_boars(self):
        game, _ = table3(x_policy(2, CAST))
        a, b, _c = game.seats
        a.hand, a.battlefield = [REAL["Curse of the Swine"]], [Permanent(BEAR), *lands(6)]
        b.battlefield = [Permanent(BEAR), Permanent(BEAR)]
        game._priority_round(a)
        run_stack(game)
        exiled = len(a.exile) + len(b.exile)
        boars = sum(p.card.name == "Boar" for p in a.battlefield + b.battlefield)
        self.assertEqual((exiled, boars), (2, 2))


class PestInfestationTests(unittest.TestCase):
    def test_up_to_x_destroyed_and_twice_x_pests(self):
        game, _ = table3(x_policy(2, CAST))
        a, b, _c = game.seats
        relics = [Permanent(Card(name=f"Relic {n}", type_line="Artifact")) for n in range(3)]
        a.hand, a.battlefield = [REAL["Pest Infestation"]], lands(5)
        b.battlefield = relics
        game._priority_round(a)
        run_stack(game)
        self.assertEqual((len(b.battlefield), sum(p.card.name == "Pest" for p in a.battlefield)), (1, 4))


class OversimplifyTests(unittest.TestCase):
    def test_everyone_gets_a_fractal_as_big_as_the_power_they_lost(self):
        game, _ = table3(pick(CAST))
        a, b, c = game.seats
        a.hand, a.battlefield = [REAL["Oversimplify"]], [Permanent(BEAR), *lands(5)]
        b.battlefield = [Permanent(BEAR), Permanent(replace(BEAR, power="4", toughness="4"))]
        game._priority_round(a)
        run_stack(game)
        sizes = {seat.index: [p.counters for p in seat.battlefield if p.card.name == "Fractal"] for seat in game.seats}
        self.assertEqual(sizes, {0: [{"+1/+1": 2}], 1: [{"+1/+1": 6}], 2: []})  # c lost nothing: its 0/0 died at once


class RiteOfReplicationTests(unittest.TestCase):
    def test_five_tokens_when_kicked_one_otherwise(self):
        for kicked, expected in ((False, 1), (True, 5)):
            def policy(prompt, options, kicked=kicked):
                from infernal_machine.game import KICKER_PROMPT
                if prompt.startswith(KICKER_PROMPT):
                    return 0 if kicked else 1
                return pick(CAST, "Bear")(prompt, options)
            game, _ = table3(policy)
            a = game.seats[0]
            a.hand, a.battlefield = [REAL["Rite of Replication"]], [Permanent(BEAR), *lands(9)]
            game._priority_round(a)
            run_stack(game)
            tokens = sum(p.card.type_line.startswith("Token") for p in a.battlefield)
            self.assertEqual(tokens, expected, kicked)


class InkshieldTests(unittest.TestCase):
    def test_combat_damage_is_prevented_and_makes_an_inkling_for_each_point(self):
        game, _ = table3(pick(CAST))
        a, b, _c = game.seats
        a.hand, a.battlefield = [REAL["Inkshield"]], lands(5)
        game._priority_round(a)
        run_stack(game)
        attacker = Permanent(replace(BEAR, power="3", toughness="3"))
        b.battlefield = [attacker]
        game.combat.attacks = [Attack(attacker, b, a)]
        game.combat.deal_damage(first_strike_step=False)
        run_stack(game)
        self.assertEqual((a.life, sum(p.card.name == "Inkling" for p in a.battlefield)), (40, 3))
        game.turn += 1  # it only lasts this turn
        game.combat.attacks = [Attack(attacker, b, a)]
        game.combat.deal_damage(first_strike_step=False)
        self.assertEqual(a.life, 37)


class FurygaleFlockingTests(unittest.TestCase):
    def test_two_hasty_attackers_for_each_opponent(self):
        game, _ = table3(pick(CAST))
        a, b, c = game.seats
        a.hand, a.battlefield = [REAL["Furygale Flocking"]], lands(10)
        game._priority_round(a)
        run_stack(game)
        elementals = [p for p in a.battlefield if p.card.name == "Elemental"]
        self.assertEqual(sorted(p.must_attack.index for p in elementals), [1, 1, 2, 2])
        self.assertTrue(all(game.has_keyword(p, "haste") and game.has_keyword(p, "flying") for p in elementals))


class TwinflameTests(unittest.TestCase):
    def test_hasty_copies_for_each_target_and_strive_for_the_extras(self):
        def policy(prompt, options):
            if prompt.startswith("Choose a target"):
                return 0  # the first, then the next, then the option to stop is last
            return pick(CAST)(prompt, options)
        game, _ = table3(policy)
        a = game.seats[0]
        bear, ogre = Permanent(BEAR), Permanent(replace(BEAR, name="Ogre", power="3", toughness="3"))
        a.hand, a.battlefield = [REAL["Twinflame"]], [bear, ogre, *lands(5)]
        game._priority_round(a)
        run_stack(game)
        tokens = [p for p in a.battlefield if p.card.type_line.startswith("Token")]
        self.assertEqual(sorted(t.card.name for t in tokens), ["Bear", "Ogre"])
        self.assertTrue(all(game.has_keyword(t, "haste") for t in tokens))
        self.assertEqual(sum(p.tapped for p in a.battlefield if "Land" in p.card.type_line), 5)  # {1}{R} + {2}{R} for the second
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual([p for p in a.battlefield if p.card.type_line.startswith("Token")], [])

    def test_it_stops_offering_targets_it_cannot_afford(self):
        game, _ = table3(lambda prompt, options: 0 if prompt.startswith("Choose a target") else pick(CAST)(prompt, options))
        a = game.seats[0]
        a.hand, a.battlefield = [REAL["Twinflame"]], [Permanent(BEAR), Permanent(BEAR), Permanent(BEAR), *lands(3)]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(sum(p.card.type_line.startswith("Token") for p in a.battlefield), 1)  # only {1}{R} was affordable
