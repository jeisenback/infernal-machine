"""Exile effects of issue #79: Serra Paragon (plays from the graveyard once a turn), Abstract Performance,
Fateful Tempest and Surge to Victory. Real Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST_PARAGON, PLAY_PARAGON, Permanent
from tests.real import REAL
from tests.test_effects import lands, table
from tests.test_more_triggers import run_stack

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
CHEAP = Card(name="Cheap Bear", mana_cost="{1}", cmc=1, type_line="Creature — Bear", power="2", toughness="2")
PRICEY = Card(name="Pricey Bear", mana_cost="{3}{G}", cmc=4, type_line="Creature — Bear", power="4", toughness="4")
BOLT = Card(name="Bolt", mana_cost="{R}", cmc=1, type_line="Instant", oracle_text="Bolt deals 3 damage to any target.")


def with_paragon(graveyard, mana=3):
    game, a, b = table()
    seat = game.seats[0]
    seat.battlefield = [Permanent(REAL["Serra Paragon"])] + lands(mana)
    seat.graveyard = list(graveyard)
    return game, seat


def paragon_actions(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith((CAST_PARAGON, PLAY_PARAGON))]


class SerraParagonTests(unittest.TestCase):
    def test_a_land_can_be_played_from_the_graveyard(self):
        game, seat = with_paragon([FOREST])
        game._perform(seat, PLAY_PARAGON + "Forest")
        self.assertEqual((seat.graveyard, seat.lands_played), ([], 1))
        self.assertIn("Forest", [p.card.name for p in seat.battlefield])

    def test_a_cheap_permanent_spell_can_be_cast_from_the_graveyard(self):
        game, seat = with_paragon([CHEAP])
        self.assertEqual(paragon_actions(game, seat), [CAST_PARAGON + "Cheap Bear"])
        game._perform(seat, CAST_PARAGON + "Cheap Bear")
        run_stack(game)
        self.assertIn("Cheap Bear", [p.card.name for p in seat.battlefield])

    def test_a_spell_costing_more_than_three_is_not_offered(self):
        game, seat = with_paragon([PRICEY], mana=5)
        self.assertEqual(paragon_actions(game, seat), [])

    def test_an_instant_is_not_offered(self):
        game, seat = with_paragon([BOLT])
        self.assertEqual(paragon_actions(game, seat), [])

    def test_only_once_each_turn(self):
        game, seat = with_paragon([CHEAP, FOREST])
        game._perform(seat, PLAY_PARAGON + "Forest")
        self.assertEqual(paragon_actions(game, seat), [])
        game.turn += 2  # back to this player's next turn
        self.assertEqual(paragon_actions(game, seat), [CAST_PARAGON + "Cheap Bear"])

    def test_without_the_paragon_nothing_is_offered(self):
        game, seat = with_paragon([CHEAP, FOREST])
        seat.battlefield = lands(3)
        self.assertEqual(paragon_actions(game, seat), [])

    def test_the_permanent_is_exiled_and_gains_2_life_when_it_goes_to_the_graveyard(self):
        game, seat = with_paragon([CHEAP])
        game._perform(seat, CAST_PARAGON + "Cheap Bear")
        run_stack(game)
        bear = next(p for p in seat.battlefield if p.card.name == "Cheap Bear")
        life = seat.life
        game._leave_battlefield(bear, "died")
        self.assertEqual(([c.name for c in seat.exile], seat.graveyard, seat.life), (["Cheap Bear"], [], life + 2))

    def test_a_permanent_not_cast_with_the_paragon_goes_to_the_graveyard_as_usual(self):
        game, seat = with_paragon([])
        bear = Permanent(CHEAP)
        seat.battlefield.append(bear)
        life = seat.life
        game._leave_battlefield(bear, "died")
        self.assertEqual(([c.name for c in seat.graveyard], seat.exile, seat.life), (["Cheap Bear"], [], life))


if __name__ == "__main__":
    unittest.main()
