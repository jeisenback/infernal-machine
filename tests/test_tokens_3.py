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
