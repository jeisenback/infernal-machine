"""Unearth (#216), played from the cards' own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import UNEARTH, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import run_stack, table3

REMINDER = ("({cost}: Return this card from your graveyard to the battlefield. It gains haste. Exile it at the beginning of the "
            "next end step or if it would leave the battlefield. Unearth only as a sorcery.)")
ZOMBIE = Card(name="Dregscape Zombie", mana_cost="{1}{B}", type_line="Creature — Zombie", power="2", toughness="1",
              oracle_text="Unearth {B} " + REMINDER.format(cost="{B}"))
RATS = Card(name="Rotting Rats", mana_cost="{1}{B}", type_line="Creature — Zombie Rat", power="1", toughness="1",
            oracle_text="When this creature enters, each player discards a card.\nUnearth {1}{B} " + REMINDER.format(cost="{1}{B}"))
BEAR = Card(name="Bear", mana_cost="{1}{G}", type_line="Creature — Bear", power="2", toughness="2")
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
CARD = Card(name="Spare", mana_cost="{1}", type_line="Artifact")


def setup(card=ZOMBIE, swamps=1):
    game, _ = table3()
    a = game.seats[0]
    a.graveyard = [card]
    a.battlefield = [Permanent(SWAMP) for _ in range(swamps)]
    return game, a


def on_battlefield(seat, name):
    return next((p for p in seat.battlefield if p.card.name == name), None)


def end_step(game):
    due, game.at_end_step = game.at_end_step, []
    for _, what in due:
        what()


class UnearthTests(unittest.TestCase):
    def test_the_line_is_supported(self):
        self.assertEqual(unsupported_lines(ZOMBIE), [])
        self.assertEqual(unsupported_lines(RATS), [])

    def test_it_is_offered_when_the_cost_can_be_paid_at_sorcery_speed(self):
        game, a = setup()
        self.assertIn(UNEARTH + "Dregscape Zombie", game.legal_actions(a))
        game.step = "combat"
        self.assertNotIn(UNEARTH + "Dregscape Zombie", game.legal_actions(a))
        game.step = "main1"
        game.active = 1
        self.assertNotIn(UNEARTH + "Dregscape Zombie", game.legal_actions(a))

    def test_it_is_not_offered_without_the_mana_or_the_keyword(self):
        game, a = setup(swamps=0)
        self.assertNotIn(UNEARTH + "Dregscape Zombie", game.legal_actions(a))
        game, a = setup(BEAR)
        self.assertNotIn(UNEARTH + "Bear", game.legal_actions(a))

    def test_it_returns_with_haste_and_costs_the_unearth_cost_not_the_mana_cost(self):
        game, a = setup()
        game._perform(a, UNEARTH + "Dregscape Zombie")
        zombie = on_battlefield(a, "Dregscape Zombie")
        self.assertIsNotNone(zombie)
        self.assertEqual(a.graveyard, [])
        self.assertTrue(a.battlefield[0].tapped)  # the one Swamp paid {B}
        self.assertTrue(game.has_keyword(zombie, "haste"))

    def test_leaving_the_graveyard_is_noticed(self):
        game, a = setup()
        game._perform(a, UNEARTH + "Dregscape Zombie")
        self.assertEqual(a.graveyard_left_turn, game.turn)

    def test_it_is_not_cast(self):
        game, a = setup()
        game._perform(a, UNEARTH + "Dregscape Zombie")
        self.assertEqual(a.cast_log, [])
        self.assertEqual(game.stack, [])

    def test_enters_triggers_still_happen(self):
        game, a = setup(RATS, swamps=2)
        b = game.seats[1]
        a.hand, b.hand = [CARD], [CARD]
        game._perform(a, UNEARTH + "Rotting Rats")
        run_stack(game)
        self.assertEqual((len(a.hand), len(b.hand)), (0, 0))

    def test_it_is_exiled_at_the_next_end_step(self):
        game, a = setup()
        game._perform(a, UNEARTH + "Dregscape Zombie")
        end_step(game)
        self.assertIsNone(on_battlefield(a, "Dregscape Zombie"))
        self.assertEqual([c.name for c in a.exile], ["Dregscape Zombie"])
        self.assertEqual(a.graveyard, [])

    def test_it_is_exiled_instead_of_dying(self):
        game, a = setup()
        game._perform(a, UNEARTH + "Dregscape Zombie")
        game.destroy(on_battlefield(a, "Dregscape Zombie"))
        self.assertEqual(a.graveyard, [])
        self.assertEqual([c.name for c in a.exile], ["Dregscape Zombie"])

    def test_it_is_exiled_instead_of_returning_to_a_hand(self):
        game, a = setup()
        game._perform(a, UNEARTH + "Dregscape Zombie")
        game._leave_battlefield(on_battlefield(a, "Dregscape Zombie"), "returned", destination="hand")
        self.assertEqual(a.hand, [])
        self.assertEqual([c.name for c in a.exile], ["Dregscape Zombie"])

    def test_the_end_step_does_nothing_if_it_already_left(self):
        game, a = setup()
        game._perform(a, UNEARTH + "Dregscape Zombie")
        game.destroy(on_battlefield(a, "Dregscape Zombie"))
        end_step(game)
        self.assertEqual([c.name for c in a.exile], ["Dregscape Zombie"])  # once, not twice

    def test_a_creature_that_was_cast_normally_still_dies_to_the_graveyard(self):
        game, a = setup(swamps=0)
        a.graveyard = []
        a.battlefield = [Permanent(ZOMBIE)]
        game.destroy(a.battlefield[0])
        self.assertEqual([c.name for c in a.graveyard], ["Dregscape Zombie"])
        self.assertEqual(a.exile, [])


if __name__ == "__main__":
    unittest.main()
