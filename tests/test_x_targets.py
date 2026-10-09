"""The three X-target token cards of issue #77: Curse of the Swine, Pest Infestation and Twinflame.

The cards are module-level constants so `tools/audit_real_text.py` compares them with Scryfall's text. Pest Infestation's
quoted ability is cut off with "..." in the issue; "you gain 1 life." is completed from memory.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (CopyTokensOfTargets, CreateTokens, DestroyUpToX, ExileX, GiveBack, spell_effects,
                                      strive_cost, triggered_abilities)
from infernal_machine.game import CAST, TARGET_PROMPT, X_PROMPT, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_game import ScriptedPlayer
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

CURSE_OF_THE_SWINE = Card(name="Curse of the Swine", mana_cost="{X}{U}{U}", type_line="Sorcery", colors=("U",), cmc=2,
                          oracle_text="Exile X target creatures. For each creature exiled this way, its controller "
                                      "creates a 2/2 green Boar creature token.")
PEST_INFESTATION = Card(name="Pest Infestation", mana_cost="{X}{G}", type_line="Sorcery", colors=("G",), cmc=1,
                        oracle_text="Destroy up to X target artifacts and/or enchantments. Create twice X 1/1 black and "
                                    "green Pest creature tokens with \"When this token dies, you gain 1 life.\"")
TWINFLAME = Card(name="Twinflame", mana_cost="{1}{R}", type_line="Sorcery", colors=("R",), cmc=2,
                 oracle_text="Strive — This spell costs {2}{R} more to cast for each target beyond the first.\n"
                             "Choose any number of target creatures you control. For each of them, create a token that's "
                             "a copy of that creature, except it has haste. Exile those tokens at the beginning of the "
                             "next end step.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))
RELIC = Card(name="Relic", type_line="Artifact")
SHRINE = Card(name="Shrine", type_line="Enchantment")
BOAR = Card(name="Boar", type_line="Token Creature — Boar", colors=("G",), power="2", toughness="2")
PEST = Card(name="Pest", type_line="Token Creature — Pest", colors=("B", "G"), power="1", toughness="1",
            oracle_text="When this token dies, you gain 1 life.")
WARDEN = Card(name="Token Watcher", type_line="Enchantment",
              oracle_text="Whenever you create one or more creature tokens, you gain 1 life.")


def count(seat, name):
    return sum(p.card.name == name for p in seat.battlefield)


def script(*answers):
    """A policy that answers each question with the first option starting with the next answer, then passes."""
    queue = iter(answers)
    return lambda prompt, options: pick(next(queue, "Pass"))(prompt, options)


class CurseOfTheSwineTests(unittest.TestCase):
    def test_parse(self):
        gives = GiveBack(1, BOAR)
        self.assertEqual(spell_effects(CURSE_OF_THE_SWINE), [ExileX("creature", gives)])
        self.assertEqual(unsupported_lines(CURSE_OF_THE_SWINE), [])

    def test_exiles_exactly_x_and_gives_each_controller_a_boar(self):
        game, _ = table3(script(CAST, "2", "Bear", "Ogre"))
        a, b, c = game.seats
        a.hand, a.battlefield = [CURSE_OF_THE_SWINE], lands(4)
        b.battlefield = [Permanent(BEAR), Permanent(BEAR)]
        c.battlefield = [Permanent(OGRE)]
        game._priority_round(a)
        self.assertEqual(sorted(p.card.name for p in b.battlefield), ["Bear", "Boar"])  # one Bear exiled, one stays
        self.assertEqual(sorted(p.card.name for p in c.battlefield), ["Boar"])
        self.assertEqual(count(a, "Boar"), 0)

    def test_x_can_not_be_more_than_there_are_creatures_to_target(self):
        seen = []

        def policy(prompt, options):
            if prompt.startswith(X_PROMPT):
                seen.append(list(options))
                return len(options) - 1
            return pick(CAST)(prompt, options)

        game, _ = table3(policy)
        a, b, _c = game.seats
        a.hand, a.battlefield = [CURSE_OF_THE_SWINE], lands(8)
        b.battlefield = [Permanent(BEAR), Permanent(OGRE)]
        game._priority_round(a)
        self.assertEqual(seen, [["0", "1", "2"]])  # eight lands pay for X = 6, but only two creatures can be targeted
        self.assertEqual(sorted(p.card.name for p in b.battlefield), ["Boar", "Boar"])

    def test_x_zero_exiles_nothing_and_a_gone_target_gives_nothing(self):
        game, _ = table3()
        a, b, _c = game.seats
        bear = Permanent(BEAR)
        b.battlefield = [bear]
        [effect] = spell_effects(CURSE_OF_THE_SWINE)
        item = StackItem(CURSE_OF_THE_SWINE, a, [effect], [[]], x=0)
        game._resolve(item)
        self.assertEqual(b.battlefield, [bear])
        b.battlefield = []  # the target left before the spell resolved
        game._resolve(StackItem(CURSE_OF_THE_SWINE, a, [effect], [[bear]], x=1))
        self.assertEqual(b.battlefield, [])  # fizzled: no Boar for a creature that was not exiled


class PestInfestationTests(unittest.TestCase):
    def test_parse(self):
        [destroy, tokens] = spell_effects(PEST_INFESTATION)
        self.assertEqual(destroy, DestroyUpToX("artifact or enchantment"))
        self.assertEqual(tokens, CreateTokens("2X", PEST))
        self.assertEqual(unsupported_lines(PEST_INFESTATION), [])

    def test_destroys_up_to_x_and_makes_twice_x_pests_that_gain_life(self):
        game, _ = table3(script(CAST, "2", "Relic", "Shrine"))
        a, b, _c = game.seats
        a.hand, a.battlefield = [PEST_INFESTATION], lands(3)  # the default test land makes any color
        b.battlefield = [Permanent(RELIC), Permanent(SHRINE), Permanent(RELIC)]
        game._priority_round(a)
        self.assertEqual(sorted(p.card.name for p in b.battlefield), ["Relic"])
        self.assertEqual(count(a, "Pest"), 4)
        pest = next(p for p in a.battlefield if p.card.name == "Pest")
        game._leave_battlefield(pest, "dies")
        run_stack(game)
        self.assertEqual(a.life, 41)

    def test_all_its_targets_gone_it_does_nothing_but_with_no_targets_it_still_makes_pests(self):
        game, _ = table3()
        a, b, _c = game.seats
        relic = Permanent(RELIC)
        effects = spell_effects(PEST_INFESTATION)
        game._resolve(StackItem(PEST_INFESTATION, a, effects, [[relic]], x=2))  # it is not on the battlefield any more
        self.assertEqual(count(a, "Pest"), 0)  # every target illegal: the spell doesn't resolve (CR 608.2b)
        game._resolve(StackItem(PEST_INFESTATION, a, effects, [[]], x=2))  # no targets were chosen
        self.assertEqual(count(a, "Pest"), 4)


class TwinflameTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(strive_cost(TWINFLAME), "{2}{R}")
        self.assertEqual(spell_effects(TWINFLAME), [CopyTokensOfTargets("creature you control", True, True)])
        self.assertEqual(unsupported_lines(TWINFLAME), [])
        half = Card(name="Half", type_line="Sorcery", oracle_text="For each of them, create a token that's a copy of that "
                                                                  "creature, except it has haste.")
        self.assertIsNone(spell_effects(half))

    def test_each_extra_target_costs_more_and_the_tokens_have_haste_and_leave_at_end_of_turn(self):
        game, _ = table3(script(CAST, "Bear", "Ogre", "No target"))
        a = game.seats[0]
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        a.hand, a.battlefield = [TWINFLAME], lands(5, MOUNTAIN) + [bear, ogre]
        game._priority_round(a)
        self.assertEqual(sum(p.tapped for p in a.battlefield if "Land" in p.card.type_line), 5)  # {1}{R} + {2}{R}
        tokens = [p for p in a.battlefield if "Token" in p.card.type_line]
        self.assertEqual(sorted(p.card.name for p in tokens), ["Bear", "Ogre"])
        self.assertTrue(all(game.has_keyword(p, "haste") for p in tokens))
        self.assertFalse(game.has_keyword(bear, "haste"))
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Land" not in p.card.type_line), ["Bear", "Ogre"])
        self.assertEqual([p.card.type_line for p in a.battlefield if "Land" not in p.card.type_line],
                         [BEAR.type_line, OGRE.type_line])  # the real ones are still there, the tokens are gone

    def test_it_only_offers_as_many_targets_as_the_mana_pays_for(self):
        offered = []

        def policy(prompt, options):
            if prompt.startswith(TARGET_PROMPT):
                offered.append(len(options))
                return 0
            return pick(CAST)(prompt, options)

        game, _ = table3(policy)
        a = game.seats[0]
        # {1}{R} for one target; a second would cost {2}{R} more, which four lands can't pay
        a.hand, a.battlefield = [TWINFLAME], lands(4, MOUNTAIN) + [Permanent(BEAR), Permanent(OGRE)]
        game._priority_round(a)
        self.assertEqual(offered, [3])  # two creatures and "no target", asked once
        self.assertEqual(sum(1 for p in a.battlefield if "Token" in p.card.type_line), 1)
        self.assertEqual(sum(p.tapped for p in a.battlefield if "Land" in p.card.type_line), 2)

    def test_copies_made_together_are_one_batch_of_tokens(self):
        game, _ = table3(script(CAST, "Bear", "Ogre", "No target"))
        a = game.seats[0]
        a.hand, a.battlefield = [TWINFLAME], lands(5, MOUNTAIN) + [Permanent(BEAR), Permanent(OGRE), Permanent(WARDEN)]
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(a.life, 41)  # "one or more creature tokens" once, not once per copy
