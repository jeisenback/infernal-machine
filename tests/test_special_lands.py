import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import cycling, land_mana_units, mana_life_cost, mana_pain
from infernal_machine.game import CAST, CYCLE, PLAY_LAND, Permanent
from infernal_machine.mana import parse_cost
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_effects import FOREST, lands, pick, table

TOMB = REAL["Ancient Tomb"]
AQUEDUCT = REAL["Dimir Aqueduct"]
CITY = REAL["City of Brass"]
CONFLUENCE = Card(name="Mana Confluence", type_line="Land", produced_mana=("W", "U", "B", "R", "G"),
                  oracle_text="{T}, Pay 1 life: Add one mana of any color.")
GARDEN = Card(name="Temple Garden", type_line="Land — Forest Plains", produced_mana=("G", "W"))
SPROUT = REAL["Generous Ent"]
SEEKER = REAL["Ash Barrens"]
SPELL = Card(name="Spell", mana_cost="{2}", type_line="Sorcery", oracle_text="Draw a card.")


def with_lands(*cards):
    game, _, _ = table(pick(CAST))
    seat = game.seats[0]
    seat.battlefield = [Permanent(c) for c in cards]
    return game, seat


class ParseTests(unittest.TestCase):
    def test_what_each_land_does(self):
        self.assertEqual(mana_pain(TOMB), (frozenset("C"), 2))
        self.assertEqual(land_mana_units(TOMB), [frozenset("C"), frozenset("C")])
        self.assertEqual(land_mana_units(AQUEDUCT), [frozenset("U"), frozenset("B")])
        self.assertIsNone(land_mana_units(FOREST))
        self.assertEqual(mana_pain(CITY), (frozenset("WUBRGC"), 1))
        self.assertEqual(mana_life_cost(CONFLUENCE), 1)
        self.assertEqual(mana_life_cost(CITY), 0)

    def test_the_report_counts_them_as_playable(self):
        for card in (TOMB, AQUEDUCT, CITY, CONFLUENCE, SPROUT, SEEKER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_cycling_kinds(self):
        self.assertEqual(cycling(SPROUT)[:2], ("Forestcycling", "{1}"))
        self.assertEqual(cycling(SEEKER)[:2], ("Basic landcycling", "{1}"))
        self.assertEqual(cycling(Card(name="x", oracle_text="Cycling {2}"))[:2], ("Cycling", "{2}"))
        self.assertIsNone(cycling(FOREST))


class ManaTests(unittest.TestCase):
    def test_ancient_tomb_makes_two_mana_and_hurts_once(self):
        game, seat = with_lands(TOMB)
        payment = game._pay_cost(seat, parse_cost("{2}"))
        self.assertEqual((len(payment), payment.pain, payment.life), (1, 2, 0))
        one = game._pay_cost(seat, parse_cost("{1}"))  # the second mana is wasted but the damage is the same
        self.assertEqual((len(one), one.pain), (1, 2))

    def test_casting_with_it(self):
        game, seat = with_lands(TOMB)
        seat.hand = [SPELL]
        game._priority_round(seat)
        self.assertEqual((seat.life, seat.hand and 1 or 0), (38, 1))  # 2 damage, one card drawn
        self.assertTrue(seat.battlefield[0].tapped)

    def test_a_bounceland_makes_two_colors_in_one_tap(self):
        game, seat = with_lands(AQUEDUCT)
        payment = game._pay_cost(seat, parse_cost("{U}{B}"))
        self.assertEqual((len(payment), payment.pain), (1, 0))
        self.assertIsNone(game._pay_cost(seat, parse_cost("{U}{U}")))

    def test_city_of_brass_hurts_once_per_land(self):
        game, seat = with_lands(CITY, CITY)
        one = game._pay_cost(seat, parse_cost("{W}"))
        self.assertEqual((len(one), one.pain), (1, 1))
        two = game._pay_cost(seat, parse_cost("{W}{U}"))
        self.assertEqual((len(two), two.pain), (2, 2))

    def test_mana_confluence_costs_life_not_damage(self):
        game, seat = with_lands(CONFLUENCE)
        payment = game._pay_cost(seat, parse_cost("{R}"))
        self.assertEqual((payment.pain, payment.life), (0, 1))
        game._spend_mana(seat, payment)
        self.assertEqual(seat.life, 39)

    def test_you_cant_pay_life_you_dont_have(self):
        game, seat = with_lands(CONFLUENCE)
        seat.life = 0
        self.assertIsNone(game._pay_cost(seat, parse_cost("{R}")))

    def test_a_plain_land_is_preferred_when_it_is_enough(self):
        game, seat = with_lands(CONFLUENCE, FOREST)
        payment = game._pay_cost(seat, parse_cost("{G}"))
        self.assertEqual(payment.life, 0)  # the painless land pays for it


class BounceTests(unittest.TestCase):
    def test_it_enters_tapped_and_returns_a_land(self):
        game, _, _ = table(pick(PLAY_LAND))
        seat = game.seats[0]
        seat.battlefield = lands(1, FOREST)
        seat.hand = [AQUEDUCT]
        game._priority_round(seat)
        self.assertEqual([p.card.name for p in seat.battlefield], ["Dimir Aqueduct"])
        self.assertTrue(seat.battlefield[0].tapped)
        self.assertEqual([c.name for c in seat.hand], ["Forest"])

    def test_it_can_return_itself(self):
        game, _, _ = table(lambda prompt, options: len(options) - 1 if "Return which" in prompt else
                           options.index(PLAY_LAND + "Dimir Aqueduct") if PLAY_LAND + "Dimir Aqueduct" in options else
                           options.index("Pass"))
        seat = game.seats[0]
        seat.battlefield = lands(1, FOREST)
        seat.hand = [AQUEDUCT]
        game._priority_round(seat)
        self.assertEqual([p.card.name for p in seat.battlefield], ["Forest"])
        self.assertEqual([c.name for c in seat.hand], ["Dimir Aqueduct"])


class LandcyclingTests(unittest.TestCase):
    def test_typecycling_fetches_a_land_with_that_type(self):
        game, _, _ = table(pick(CYCLE))
        seat = game.seats[0]
        seat.battlefield = lands(1, FOREST)
        seat.hand = [SPROUT]
        seat.library = [GARDEN, Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))]
        game._priority_round(seat)
        self.assertEqual([c.name for c in seat.hand], ["Temple Garden"])
        self.assertEqual([c.name for c in seat.graveyard], ["Generous Ent"])

    def test_basic_landcycling_wants_a_basic_land(self):
        game, _, _ = table(pick(CYCLE))
        seat = game.seats[0]
        seat.battlefield = lands(1, FOREST)
        seat.hand = [SEEKER]
        seat.library = [GARDEN]
        game._priority_round(seat)
        self.assertEqual(seat.hand, [])  # no basic land to find
        self.assertEqual([c.name for c in seat.graveyard], ["Ash Barrens"])

    def test_it_is_offered_only_when_affordable(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [SPROUT]
        self.assertNotIn(CYCLE + "Generous Ent", game.legal_actions(seat))
        seat.battlefield = lands(1, FOREST)
        self.assertIn(CYCLE + "Generous Ent", game.legal_actions(seat))


if __name__ == "__main__":
    unittest.main()
