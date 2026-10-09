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


DIVINATION = Card(name="Divination", mana_cost="{2}{U}", cmc=3, type_line="Sorcery", oracle_text="Draw two cards.")
BEAR = Card(name="Grizzly Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")


def surge_table(graveyard):
    game, a, b = table()
    seat = game.seats[0]
    seat.hand = [REAL["Surge to Victory"]]
    seat.battlefield = [Permanent(BEAR)] + lands(6)
    seat.graveyard = list(graveyard)
    seat.library = [Card(name=f"Card {i}", type_line="Sorcery") for i in range(6)]
    return game, seat


def cast_surge(game, seat):
    game._perform(seat, "Cast: Surge to Victory")
    run_stack(game)


class SurgeToVictoryTests(unittest.TestCase):
    def test_exiles_the_card_and_pumps_by_its_mana_value(self):
        game, seat = surge_table([DIVINATION])
        cast_surge(game, seat)
        self.assertEqual(([c.name for c in seat.exile], [c.name for c in seat.graveyard]), (["Divination"], ["Surge to Victory"]))
        self.assertEqual(game.power(seat.battlefield[0]), 2 + 3)

    def test_combat_damage_lets_you_cast_a_free_copy(self):
        game, seat = surge_table([DIVINATION])
        cast_surge(game, seat)
        hand = len(seat.hand)
        game.damage(game.seats[1], 5, source=seat.battlefield[0], combat=True)
        run_stack(game)
        self.assertEqual(len(seat.hand), hand + 2)  # the copy drew two cards
        self.assertEqual(len(seat.exile), 1)  # the exiled card itself stays exiled; the copy is gone

    def test_each_creature_that_connects_gives_another_copy(self):
        game, seat = surge_table([DIVINATION])
        seat.battlefield.append(Permanent(BEAR))
        cast_surge(game, seat)
        hand = len(seat.hand)
        for p in seat.battlefield[:2]:
            game.damage(game.seats[1], 5, source=p, combat=True)
        run_stack(game)
        self.assertEqual(len(seat.hand), hand + 4)

    def test_no_copy_without_combat_damage_to_a_player(self):
        game, seat = surge_table([DIVINATION])
        cast_surge(game, seat)
        hand = len(seat.hand)
        game.damage(game.seats[1], 5, source=seat.battlefield[0])  # not combat damage
        run_stack(game)
        self.assertEqual(len(seat.hand), hand)

    def test_the_permission_ends_with_the_turn(self):
        game, seat = surge_table([DIVINATION])
        cast_surge(game, seat)
        game.turn += 2
        hand = len(seat.hand)
        game.damage(game.seats[1], 5, source=seat.battlefield[0], combat=True)
        run_stack(game)
        self.assertEqual(len(seat.hand), hand)

    def test_needs_an_instant_or_sorcery_in_the_graveyard(self):
        game, seat = surge_table([BEAR])
        self.assertNotIn("Cast: Surge to Victory", game.legal_actions(seat))


def votes(word):
    return lambda prompt, options: options.index(word) if word in options else 0


def tempest_table(vote_a, vote_b):
    game, a, b = table(votes(vote_a), votes(vote_b))
    seat = game.seats[0]
    seat.hand = [REAL["Fateful Tempest"]]
    seat.battlefield = lands(3)
    seat.library = [Card(name=f"Spell {n}", mana_cost="{" + str(n) + "}", cmc=n, type_line="Sorcery") for n in (2, 3, 5, 1)]
    return game, seat


def cast_tempest(game, seat):
    game._perform(seat, "Cast: Fateful Tempest")
    run_stack(game)


class FatefulTempestTests(unittest.TestCase):
    def test_past_votes_mill_and_damage_each_opponent_by_the_milled_mana_value(self):
        game, seat = tempest_table("past", "past")
        life = game.seats[1].life
        cast_tempest(game, seat)
        self.assertEqual([c.name for c in seat.graveyard][:2], ["Spell 2", "Spell 3"])
        self.assertEqual(game.seats[1].life, life - 5)
        self.assertEqual(seat.exile, [])

    def test_present_votes_exile_cards_you_may_play_until_your_next_turn_ends(self):
        game, seat = tempest_table("present", "present")
        life = game.seats[1].life
        cast_tempest(game, seat)
        self.assertEqual([c.name for c in seat.exile], ["Spell 2", "Spell 3"])
        self.assertEqual(len(seat.exile_play), 2)
        self.assertEqual(game.seats[1].life, life)  # nothing was milled
        self.assertTrue(all(until >= game.turn + 2 for _, until in seat.exile_play))

    def test_a_split_vote_does_both(self):
        game, seat = tempest_table("past", "present")
        life = game.seats[1].life
        cast_tempest(game, seat)
        self.assertEqual(([c.name for c in seat.exile], game.seats[1].life), (["Spell 3"], life - 2))
        self.assertIn("Spell 2", [c.name for c in seat.graveyard])

    def test_the_damage_is_only_to_opponents(self):
        game, seat = tempest_table("past", "past")
        life = seat.life
        cast_tempest(game, seat)
        self.assertEqual(seat.life, life)
