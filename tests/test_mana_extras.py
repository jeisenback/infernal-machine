import unittest

from infernal_machine.bot import _is_ritual
from infernal_machine.cards import Card
from infernal_machine.effects import AddMana, activated_abilities, spell_effects
from infernal_machine.game import ACTIVATE, CAST, X_PROMPT, Permanent
from infernal_machine.mana import Cost, SNOW, parse_cost, pay
from infernal_machine.report import unsupported_lines
from tests.test_combat import creature
from tests.test_effects import FOREST, lands, pick, table

W, B, G, R = (frozenset(c) for c in "WBGR")
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
SNOW_FOREST = Card(name="Snow-Covered Forest", type_line="Basic Snow Land — Forest", produced_mana=("G",))
DARK_RITUAL = Card(name="Dark Ritual", mana_cost="{B}", type_line="Instant", oracle_text="Add {B}{B}{B}.")
BIG = Card(name="Big Spell", mana_cost="{B}{B}{B}", type_line="Sorcery", oracle_text="You gain 5 life.")


def spell(cost, text="You gain 1 life.", name="Spell"):
    return Card(name=name, mana_cost=cost, type_line="Sorcery", oracle_text=text)


def settle(game):
    game._priority_round(game.seats[0])


class TwobridTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_cost("{2/W}{2/W}"), Cost(0, (), 0, (W, W)))

    def test_one_mana_of_the_color_is_enough(self):
        self.assertEqual(pay(parse_cost("{2/W}"), [W]), [0])

    def test_otherwise_two_of_any(self):
        self.assertEqual(sorted(pay(parse_cost("{2/W}"), [R, R])), [0, 1])
        self.assertIsNone(pay(parse_cost("{2/W}"), [R]))

    def test_each_symbol_picks_its_own_way(self):
        found = pay(parse_cost("{2/W}{2/W}{2/W}"), [W, W, R, R])
        self.assertEqual(sorted(found), [0, 1, 2, 3])
        self.assertIsNone(pay(parse_cost("{2/W}{2/W}{2/W}"), [W, W, R]))

    def test_casting_it(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [spell("{2/W}")]
        seat.battlefield = lands(2, MOUNTAIN)
        settle(game)
        self.assertEqual(seat.life, 41)


class SnowTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_cost("{S}"), Cost(0, (frozenset(SNOW),)))

    def test_only_a_snow_permanent_pays_for_it(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(FOREST)]
        self.assertIsNone(game._pay_cost(seat, parse_cost("{S}")))
        seat.battlefield = [Permanent(SNOW_FOREST)]
        self.assertEqual(len(game._pay_cost(seat, parse_cost("{S}"))), 1)

    def test_a_snow_land_still_makes_its_color(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(SNOW_FOREST), Permanent(FOREST)]
        self.assertEqual(len(game._pay_cost(seat, parse_cost("{S}{G}"))), 2)
        self.assertEqual(len(game._pay_cost(seat, parse_cost("{G}{G}"))), 2)
        self.assertIsNone(game._pay_cost(seat, parse_cost("{S}{S}")))


class PhyrexianTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_cost("{1}{B/P}{B/P}"), Cost(1, (), 0, (), (B, B)))
        self.assertEqual(parse_cost("{G/W/P}").phyrexian, (frozenset("GW"),))

    def test_mana_is_used_when_it_can_be(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(SWAMP), Permanent(SWAMP), Permanent(MOUNTAIN)]
        payment = game._pay_cost(seat, parse_cost("{1}{B/P}{B/P}"))
        self.assertEqual((len(payment), payment.life), (3, 0))

    def test_life_pays_for_what_mana_cannot(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(SWAMP), Permanent(MOUNTAIN)]
        payment = game._pay_cost(seat, parse_cost("{1}{B/P}{B/P}"))
        self.assertEqual((len(payment), payment.life), (2, 2))
        seat.battlefield = lands(3, MOUNTAIN)
        payment = game._pay_cost(seat, parse_cost("{1}{B/P}{B/P}"))
        self.assertEqual((len(payment), payment.life), (1, 4))

    def test_it_never_pays_itself_to_death(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(MOUNTAIN)]
        seat.life = 4
        self.assertIsNone(game._pay_cost(seat, parse_cost("{1}{B/P}{B/P}")))
        seat.life = 5
        self.assertEqual(game._pay_cost(seat, parse_cost("{1}{B/P}{B/P}")).life, 4)

    def test_casting_it_costs_the_life(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [spell("{1}{B/P}{B/P}")]
        seat.battlefield = [Permanent(MOUNTAIN), Permanent(SWAMP)]
        settle(game)
        self.assertEqual(seat.life, 40 - 2 + 1)  # paid 2 life, then the spell gains 1


class XAbilityTests(unittest.TestCase):
    def once(self, x):
        used = []

        def policy(prompt, options):
            if prompt.startswith(X_PROMPT):
                return x
            if not used:
                for i, option in enumerate(options):
                    if option.startswith(ACTIVATE):
                        used.append(True)
                        return i
            return options.index("Pass")
        return policy

    def test_parse(self):
        card = Card(name="Well", type_line="Artifact", oracle_text="{X}, {T}: Draw X cards.")
        (ability,) = activated_abilities(card)
        self.assertEqual(ability.mana_cost, "{X}")
        self.assertEqual(unsupported_lines(card), [])

    def test_x_is_chosen_and_paid(self):
        card = Card(name="Fountain", type_line="Artifact", oracle_text="{X}: You gain X life.")
        game, _, _ = table(self.once(2))
        seat = game.seats[0]
        seat.battlefield = [Permanent(card)] + lands(4, MOUNTAIN)
        settle(game)
        self.assertEqual(seat.life, 42)
        self.assertEqual(sum(p.tapped for p in seat.battlefield), 2)

    def test_x_with_a_tap_cost(self):
        card = Card(name="Well", type_line="Artifact", oracle_text="{X}, {T}: Draw X cards.")
        game, _, _ = table(self.once(3))
        seat = game.seats[0]
        seat.battlefield = [Permanent(card)] + lands(3, MOUNTAIN)
        settle(game)
        self.assertEqual(len(seat.hand), 3)

    def test_the_most_you_can_afford_is_offered(self):
        seen = []

        def policy(prompt, options):
            if prompt.startswith(X_PROMPT):
                seen.append(options)
                return 0
            for i, option in enumerate(options):
                if option.startswith(ACTIVATE) and not seen:
                    return i
            return options.index("Pass")
        card = Card(name="Fountain", type_line="Artifact", oracle_text="{X}: You gain X life.")
        game, _, _ = table(policy)
        seat = game.seats[0]
        seat.battlefield = [Permanent(card)] + lands(2, MOUNTAIN)
        settle(game)
        self.assertEqual(seen, [["0", "1", "2"]])


class RitualTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(DARK_RITUAL), [AddMana((B, B, B))])
        self.assertEqual(unsupported_lines(DARK_RITUAL), [])

    def test_mana_from_a_ritual_pays_for_the_next_spell(self):
        game, _, _ = table(pick(CAST + "Dark Ritual", CAST + "Big Spell"))
        seat = game.seats[0]
        seat.hand = [DARK_RITUAL, BIG]
        seat.battlefield = [Permanent(SWAMP)]
        settle(game)
        self.assertEqual(seat.life, 45)
        self.assertEqual([c.name for c in seat.graveyard], ["Dark Ritual", "Big Spell"])
        self.assertEqual(seat.mana_pool, [])

    def test_the_pool_is_spent_before_lands_are_tapped(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(SWAMP)]
        seat.mana_pool = [B, B]
        payment = game._pay_cost(seat, parse_cost("{B}{B}"))
        self.assertEqual((len(payment), payment.pool), (0, (B, B)))
        game._spend_mana(seat, payment)
        self.assertEqual(seat.mana_pool, [])
        self.assertFalse(seat.battlefield[0].tapped)

    def test_pool_and_lands_can_share_a_cost(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(SWAMP)]
        seat.mana_pool = [B, B]
        payment = game._pay_cost(seat, parse_cost("{B}{B}{B}"))
        self.assertEqual((len(payment), len(payment.pool)), (1, 2))

    def test_pool_mana_makes_a_spell_castable(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [BIG]
        self.assertNotIn(CAST + "Big Spell", game.legal_actions(seat))
        seat.mana_pool = [B, B, B]
        self.assertIn(CAST + "Big Spell", game.legal_actions(seat))

    def test_the_pool_empties_when_the_step_ends(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.mana_pool = [B, B]
        game.turn = 3
        game._take_turn(seat)
        self.assertEqual(seat.mana_pool, [])

    def test_the_pool_is_shown_to_clients(self):
        game, _, _ = table()
        game.seats[0].mana_pool = [B, B]
        self.assertEqual(game.snapshot(game.seats[0])["seats"][0]["mana_pool"], ["B", "B"])

    def test_the_bot_does_not_waste_a_ritual(self):
        self.assertTrue(_is_ritual(DARK_RITUAL))
        self.assertFalse(_is_ritual(BIG))
        self.assertFalse(_is_ritual(None))


if __name__ == "__main__":
    unittest.main()
