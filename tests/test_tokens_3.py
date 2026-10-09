"""Token-making text of the real cards in issue #77."""

import unittest
from dataclasses import replace

from infernal_machine.cards import Card
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
