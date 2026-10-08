import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import OnPlayer, OnSubject, triggered_abilities
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, fight
from tests.test_effects import lands, pick, table
from tests.test_mass_effects import table3

MOUNTAIN = Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))


def watcher(name, text, kind="Enchantment"):
    return Card(name=name, mana_cost="{1}", type_line=kind, oracle_text=text)


def settle(game, seat=None):
    game._priority_round(seat or game.seats[0])


def attack_first_opponent(prompt, options):
    return 1 if options[0] == "Don't attack" else 0


class ItAboutAttackersTests(unittest.TestCase):
    def test_a_creature_you_control_attacks_puts_a_counter_on_it(self):
        card = watcher("Banner", "Whenever a creature you control attacks, put a +1/+1 counter on it.")
        game, _, _ = table(attack_first_opponent)
        a = game.seats[0]
        one, two = Permanent(BEAR), Permanent(BEAR)
        source = Permanent(card)
        a.battlefield = [source, one, two]
        game.combat.declare_attackers(a)
        settle(game)
        self.assertEqual((one.counters, two.counters, source.counters), ({"+1/+1": 1}, {"+1/+1": 1}, {}))

    def test_that_creature_in_a_damage_trigger(self):
        card = watcher("Lash", "Whenever a creature you control deals combat damage to a player, put a +1/+1 counter on that creature.")
        game, _, _ = table(attack_first_opponent)
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(card), bear]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        game.combat.deal_damage(first_strike_step=False)
        settle(game)
        self.assertEqual(bear.counters, {"+1/+1": 1})

    def test_an_attacker_pointed_at_you(self):
        card = watcher("Wall", "Whenever a creature attacks you, put a +1/+1 counter on it.")
        game, _, _ = table(attack_first_opponent)
        a, b = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        b.battlefield = [Permanent(card)]
        game.combat.declare_attackers(a)
        settle(game)
        self.assertEqual(bear.counters, {"+1/+1": 1})

    def test_it_with_other_effects_is_unsupported(self):
        card = watcher("Odd", "Whenever a creature you control attacks, draw a card. Put a +1/+1 counter on it.")
        self.assertEqual(len(unsupported_lines(card)), 1)


class ThatPlayerTests(unittest.TestCase):
    def test_parse(self):
        card = watcher("Sheoldred", "Whenever an opponent draws a card, they lose 2 life.", "Creature — Phyrexian")
        (ability,) = triggered_abilities(card)
        self.assertIsInstance(ability.effects[0], OnPlayer)
        self.assertEqual(unsupported_lines(card), [])

    def test_they_lose_life_when_an_opponent_draws(self):
        card = watcher("Sheoldred", "Whenever an opponent draws a card, they lose 2 life.", "Creature — Phyrexian")
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(card)]
        game.draw(b, 2)
        game.draw(a, 1)
        settle(game)
        self.assertEqual((a.life, b.life, c.life), (40, 36, 40))  # only the drawer, once per card

    def test_that_player_gains_life_when_an_opponent_gains(self):
        card = watcher("Mirror", "Whenever an opponent gains life, that player loses 1 life.")
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(card)]
        game.change_life(c, 3)
        settle(game)
        self.assertEqual((b.life, c.life), (40, 42))

    def test_damage_to_that_player(self):
        card = watcher("Eye", "Whenever an opponent loses life, Eye deals 1 damage to that player.")
        (ability,) = triggered_abilities(card)
        self.assertIsInstance(ability.effects[0], OnPlayer)

    def test_an_opponent_casts_a_spell_and_that_player_loses_life(self):
        card = watcher("Tax", "Whenever an opponent casts a spell, that player loses 1 life.")
        game, _, _ = table(None, pick(CAST))
        a, b = game.seats
        a.battlefield = [Permanent(card)]
        b.battlefield = lands(1, MOUNTAIN)
        b.hand = [Card(name="Opt", mana_cost="{R}", type_line="Instant", oracle_text="Draw a card.")]
        game.step = "end"
        settle(game)
        self.assertEqual((a.life, b.life), (40, 39))

    def test_they_in_an_unrelated_trigger_is_unsupported(self):
        card = watcher("Odd", "Whenever you gain life, they lose 1 life.")
        self.assertEqual(len(unsupported_lines(card)), 1)

    def test_a_player_effect_that_isnt_about_a_player_is_unsupported(self):
        card = watcher("Odd", "Whenever an opponent draws a card, that player puts a +1/+1 counter on it.")
        self.assertEqual(len(unsupported_lines(card)), 1)


class MoreEventTests(unittest.TestCase):
    def test_an_opponent_loses_life(self):
        card = watcher("Leech", "Whenever an opponent loses life, you gain 1 life.")
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(card)]
        game.change_life(b, -3)
        game.change_life(a, -2)  # your own loss doesn't count
        game.change_life(c, 4)  # a gain doesn't either
        settle(game)
        self.assertEqual(a.life, 39)

    def test_an_opponent_sacrifices_a_creature(self):
        card = watcher("Reaper", "Whenever an opponent sacrifices a creature, you gain 1 life.")
        game, _, _ = table()
        a, b = game.seats
        a.battlefield = [Permanent(card), Permanent(BEAR)]
        b.battlefield = [Permanent(BEAR)]
        game.sacrifice(a)  # your own doesn't count
        game.sacrifice(b)
        settle(game)
        self.assertEqual(a.life, 41)

    def test_the_second_card_each_turn(self):
        card = watcher("Looter", "Whenever you draw your second card each turn, you gain 3 life.")
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(card)]
        game.draw(a, 1)
        settle(game)
        self.assertEqual(a.life, 40)
        game.draw(a, 2)  # the second and third
        settle(game)
        self.assertEqual(a.life, 43)  # once
        game.turn += 1
        game.draw(a, 1)
        game.draw(a, 1)
        settle(game)
        self.assertEqual(a.life, 46)  # again on a new turn

    def test_the_opening_hand_does_not_count_toward_the_second_card(self):
        card = watcher("Looter", "Whenever you draw your second card each turn, you gain 3 life.")
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(card)]
        game.draw(a, 7, announce=False)
        game.draw(a, 1)
        settle(game)
        self.assertEqual(a.life, 40)


if __name__ == "__main__":
    unittest.main()
