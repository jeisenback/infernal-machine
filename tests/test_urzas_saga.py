"""Urza's Saga, from its Oracle text: a mana ability, then a Construct maker, then a cheap artifact, then it is sacrificed."""

import dataclasses
import unittest

from infernal_machine.cards import Card
from infernal_machine.effects.outcomes import GainsAbility
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, real, run_stack, script, table3

SAGA = real("Urza's Saga", "", "Enchantment Land — Urza's Saga",
            "(As this Saga enters and after your draw step, add a lore counter. Sacrifice after III.)\n"
            'I — This Saga gains "{T}: Add {C}."\n'
            "II — This Saga gains \"{2}, {T}: Create a 0/0 colorless Construct artifact creature token with 'This token gets +1/+1 for each artifact you control.'\"\n"
            "III — Search your library for an artifact card with mana cost {0} or {1}, put it onto the battlefield, then shuffle.")
SOL_RING = Card(name="Sol Ring", mana_cost="{1}", cmc=1.0, type_line="Artifact", oracle_text="{T}: Add {C}{C}.")
MOX = Card(name="Mox Pearl", mana_cost="{0}", cmc=0.0, type_line="Artifact", oracle_text="{T}: Add {W}.")
BIG_ROCK = Card(name="Big Rock", mana_cost="{2}", cmc=2.0, type_line="Artifact", oracle_text="{T}: Add {C}{C}{C}.")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


def start(*library):
    game, _ = table3(script(*(["Sol Ring"] if not library else [library[0]])))
    a = game.seats[0]
    a.library = [SOL_RING, BIG_ROCK, MOX, FOREST] + [FOREST] * 5
    saga = Permanent(SAGA)
    game._enter(a, saga)
    run_stack(game)
    return game, a, saga


def next_turn(game, a):
    game.step = "main1"
    game._turn_based_actions(a)
    run_stack(game)


class SagaTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(SAGA), [])

    def test_chapter_one_gives_it_a_mana_ability(self):
        game, a, saga = start()
        self.assertEqual(saga.counters["lore"], 1)
        self.assertEqual(sorted("".join(sorted(s.types)) for s in game._mana_sources(a) if s.permanent is saga), ["C"])

    def test_the_mana_pays_for_a_spell_and_taps_it(self):
        game, a, saga = start()
        a.hand = [real("Colorless Thing", "{C}", "Artifact", "")]
        self.assertIn(CAST + "Colorless Thing", game.legal_actions(a))
        game._perform(a, CAST + "Colorless Thing")
        self.assertTrue(saga.tapped)

    def test_a_saga_that_left_before_the_chapter_resolved_gains_nothing(self):
        game, _ = table3()
        a = game.seats[0]
        saga = Permanent(SAGA)
        game._enter(a, saga)
        a.battlefield.remove(saga)  # sacrificed or destroyed with chapter I on the stack
        run_stack(game)
        self.assertEqual((saga.card, saga.real_card), (SAGA, None))

    def test_gaining_the_same_mana_twice_does_not_list_it_twice(self):
        game, _ = table3()
        a = game.seats[0]
        land = Permanent(dataclasses.replace(SAGA, produced_mana=("C",)))
        a.battlefield = [land]
        game.resolving_source = land
        GainsAbility("{T}: Add {C}.").resolve(game, a, None)
        self.assertEqual(land.card.produced_mana, ("C",))

    def test_without_chapter_one_it_makes_no_mana(self):
        game, _ = table3()
        a = game.seats[0]
        saga = Permanent(SAGA)
        a.battlefield = [saga]
        self.assertEqual([s for s in game._mana_sources(a) if s.permanent is saga], [])

    def test_chapter_two_lets_it_make_constructs_that_grow_with_artifacts(self):
        game, a, saga = start()
        next_turn(game, a)
        self.assertEqual(saga.counters["lore"], 2)
        a.battlefield += lands(2) + [Permanent(SOL_RING)]
        saga.tapped = False
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith("Activate") and "Construct" in x))
        run_stack(game)
        construct = next(p for p in a.battlefield if p.card.name == "Construct")
        self.assertEqual((game.power(construct), game.toughness(construct)), (2, 2))  # itself and the Sol Ring
        a.battlefield.append(Permanent(MOX))
        self.assertEqual(game.power(construct), 3)

    def test_chapter_three_fetches_a_cheap_artifact_and_the_saga_is_sacrificed(self):
        game, a, saga = start("Sol Ring")
        next_turn(game, a)
        next_turn(game, a)
        game._check_state()
        self.assertIn("Sol Ring", [p.card.name for p in a.battlefield])
        self.assertNotIn(saga, a.battlefield)
        self.assertEqual([c.name for c in a.graveyard], ["Urza's Saga"])
        self.assertEqual(a.graveyard[0].oracle_text, SAGA.oracle_text)  # the card is back as printed, not with the lines it gained

    def test_an_artifact_that_costs_two_cannot_be_found(self):
        game, a, saga = start("Mox Pearl")
        a.library = [BIG_ROCK, FOREST]
        next_turn(game, a)
        next_turn(game, a)
        self.assertEqual([p.card.name for p in a.battlefield if "Artifact" in p.card.type_line], [])

    def test_a_zero_cost_artifact_can_be_found(self):
        game, a, saga = start("Mox Pearl")
        next_turn(game, a)
        next_turn(game, a)
        self.assertIn("Mox Pearl", [p.card.name for p in a.battlefield])


if __name__ == "__main__":
    unittest.main()
