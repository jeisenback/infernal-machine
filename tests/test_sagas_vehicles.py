import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import BecomeCreature, activated_abilities, saga_chapters
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.helpers import BEAR, lands, OGRE, pick, table

CART = Card(name="Cart", mana_cost="{2}", type_line="Artifact — Vehicle", power="3", toughness="2",
            oracle_text="Crew 2")
WAGON = Card(name="Wagon", mana_cost="{2}", type_line="Artifact — Vehicle", power="4", toughness="4",
             oracle_text="Crew 3")
SAGA = Card(name="Tale", mana_cost="{2}", type_line="Enchantment — Saga",
            oracle_text="I — You gain 1 life.\nII — You gain 2 life.\nIII — You gain 3 life.")
LOOTING = REAL["Summon: G.F. Ifrit"]
BROKEN = Card(name="Odd", mana_cost="{1}", type_line="Enchantment — Saga",
              oracle_text="I — You gain 1 life.\nII — Exchange control of two target creatures.")


def settle(game, seat=None):
    game._priority_round(seat or game.seats[0])


class VehicleTests(unittest.TestCase):
    def test_parse(self):
        (ability,) = activated_abilities(CART)
        self.assertEqual((ability.text, ability.crew, ability.effects), ("Crew 2", 2, (BecomeCreature(),)))
        self.assertEqual(unsupported_lines(CART), [])

    def crew(self, vehicle, helpers):
        game, _, _ = table(pick(ACTIVATE))
        a = game.seats[0]
        cart = Permanent(vehicle)
        a.battlefield = [cart] + helpers
        settle(game)
        return game, a, cart

    def test_it_is_not_a_creature_until_crewed(self):
        game, _, _ = table()
        self.assertNotIn("Creature", CART.type_line)
        a = game.seats[0]
        a.battlefield = [Permanent(CART, sick=False)]
        game.combat.declare_attackers(a)
        self.assertEqual(game.combat.attacks, [])

    def test_crewing_taps_creatures_and_makes_it_a_creature(self):
        game, a, cart = self.crew(CART, [Permanent(BEAR)])
        self.assertIn("Artifact Creature", cart.card.type_line)
        self.assertEqual((game.power(cart), game.toughness(cart)), (3, 2))
        self.assertTrue(a.battlefield[1].tapped)

    def test_total_power_must_reach_the_crew_number(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(WAGON), Permanent(BEAR)]
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)], [])  # 2 power isn't 3
        a.battlefield.append(Permanent(BEAR))
        self.assertEqual(len([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)]), 1)

    def test_it_taps_creatures_until_the_power_is_enough(self):
        game, a, cart = self.crew(WAGON, [Permanent(BEAR), Permanent(BEAR), Permanent(OGRE)])
        self.assertEqual([p.tapped for p in a.battlefield[1:]], [True, True, False])  # 2 + 2 >= 3
        self.assertIn("Creature", cart.card.type_line)

    def test_a_summoning_sick_creature_can_crew(self):
        game, a, cart = self.crew(CART, [Permanent(BEAR, sick=True)])
        self.assertIn("Creature", cart.card.type_line)

    def test_a_tapped_creature_cannot_crew(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(CART), Permanent(BEAR, tapped=True)]
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)], [])

    def test_it_cannot_crew_itself(self):
        game, _, _ = table()
        a = game.seats[0]
        crewed = Permanent(CART)
        game.become_creature(crewed)
        a.battlefield = [crewed]
        self.assertEqual(game._crew_candidates(a, crewed), [])

    def test_an_already_crewed_vehicle_is_not_crewed_again(self):
        game, a, cart = self.crew(CART, [Permanent(BEAR), Permanent(BEAR)])
        self.assertEqual([p.tapped for p in a.battlefield[1:]], [True, False])
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE)], [])

    def test_a_crewed_vehicle_can_attack(self):
        game, _, _ = table(lambda prompt, options: 1 if options[0] == "Don't attack" else 0)
        a = game.seats[0]
        cart = Permanent(CART, sick=False)
        a.battlefield = [cart]
        game.become_creature(cart)
        game.combat.declare_attackers(a)
        self.assertEqual([x.attacker for x in game.combat.attacks], [cart])

    def test_a_vehicle_that_just_arrived_is_summoning_sick(self):
        game, _, _ = table(lambda prompt, options: 1 if options[0] == "Don't attack" else 0)
        a = game.seats[0]
        cart = Permanent(CART, sick=True)
        a.battlefield = [cart]
        game.become_creature(cart)
        game.combat.declare_attackers(a)
        self.assertEqual(game.combat.attacks, [])

    def test_it_stops_being_a_creature_at_end_of_turn(self):
        game, a, cart = self.crew(CART, [Permanent(BEAR)])
        game.step = "cleanup"
        game._turn_based_actions(a)
        self.assertEqual((cart.card, cart.original), (CART, None))

    def test_it_goes_to_the_graveyard_as_the_real_card(self):
        game, a, cart = self.crew(CART, [Permanent(BEAR)])
        game.destroy(cart)
        self.assertEqual(a.graveyard, [CART])

    def test_the_bot_crews(self):
        from infernal_machine.bot import _limited_cost
        self.assertTrue(_limited_cost(f"{ACTIVATE}Cart (seat 0, #1): Crew 2"))


class SagaTests(unittest.TestCase):
    def test_parse(self):
        chapters = saga_chapters(SAGA)
        self.assertEqual(sorted(chapters), [1, 2, 3])
        self.assertEqual(unsupported_lines(SAGA), [])
        self.assertEqual(sorted(saga_chapters(LOOTING)), [1, 2, 3, 4])

    def test_a_chapter_we_cannot_play_means_no_chapters(self):
        self.assertEqual(saga_chapters(BROKEN), {})
        self.assertNotEqual(unsupported_lines(BROKEN), [])

    def test_entering_adds_a_lore_counter_and_triggers_chapter_one(self):
        game, _, _ = table()
        a = game.seats[0]
        saga = Permanent(SAGA)
        game._enter(a, saga)
        settle(game)
        self.assertEqual((saga.counters["lore"], a.life), (1, 41))

    def test_each_turn_adds_a_lore_counter(self):
        game, _, _ = table()
        a = game.seats[0]
        saga = Permanent(SAGA)
        game._enter(a, saga)
        settle(game)
        game.step = "main1"
        game._turn_based_actions(a)
        settle(game)
        self.assertEqual((saga.counters["lore"], a.life), (2, 43))

    def test_it_is_sacrificed_after_the_last_chapter_resolves(self):
        game, _, _ = table()
        a = game.seats[0]
        saga = Permanent(SAGA)
        game._enter(a, saga)
        settle(game)
        for _ in range(2):
            game.step = "main1"
            game._turn_based_actions(a)
            if saga.counters["lore"] == 3:
                game._check_state()
                self.assertIn(saga, a.battlefield)  # chapter III is still waiting to resolve
            settle(game)
        self.assertEqual((a.battlefield, [c.name for c in a.graveyard], a.life), ([], ["Tale"], 46))

    def test_a_chapter_with_several_numbers(self):
        game, _, _ = table()
        a = game.seats[0]
        saga = Permanent(LOOTING)
        a.hand, a.library = [BEAR, BEAR, BEAR], [BEAR] * 3
        game._enter(a, saga)
        settle(game)
        self.assertEqual(len(a.graveyard), 1)  # chapter I: discard a card, then draw one
        game.step = "main1"
        game._turn_based_actions(a)
        settle(game)
        self.assertEqual(len(a.graveyard), 2)  # chapter II is the same ability

    def test_only_the_controllers_turn_adds_counters(self):
        game, _, _ = table()
        a, b = game.seats
        saga = Permanent(SAGA)
        game._enter(a, saga)
        settle(game)
        game.step = "main1"
        game._turn_based_actions(b)
        self.assertEqual(saga.counters["lore"], 1)

    def test_casting_one(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.hand = [SAGA]
        a.battlefield = lands(2)
        settle(game)
        self.assertEqual(a.life, 41)
        self.assertEqual(next(p for p in a.battlefield if p.card is SAGA).counters["lore"], 1)

    def test_a_card_that_is_not_a_saga_is_untouched(self):
        game, _, _ = table()
        a = game.seats[0]
        bear = Permanent(BEAR)
        game._enter(a, bear)
        self.assertEqual(bear.counters, {})


if __name__ == "__main__":
    unittest.main()
