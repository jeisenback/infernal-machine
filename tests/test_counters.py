import unittest

from infernal_machine.cards import Card
from infernal_machine.characteristics import power, toughness
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR, attack_all
from tests.test_effects import BOLT, lands, pick, table

GROWTH = REAL["Soldier On"]
WITHER = Card(name="Wither", mana_cost="{B}", type_line="Instant",
              oracle_text="Put two −1/−1 counters on target creature an opponent controls.")
RALLY = REAL["Basri's Solidarity"]
HYDRA = REAL["Faithful Watchdog"]
BRUTE = Card(name="Brute", mana_cost="{1}", type_line="Creature — Ogre", power="2", toughness="2",
             oracle_text="Whenever this creature attacks, put a +1/+1 counter on it.")


class CharacteristicsTests(unittest.TestCase):
    def test_counters_change_power_and_toughness(self):
        bear = Permanent(BEAR, counters={"+1/+1": 2, "-1/-1": 1})
        self.assertEqual((power(bear), toughness(bear)), (3, 3))
        self.assertIsNone(toughness(Permanent(Card(name="Relic", type_line="Artifact"))))


class CounterTests(unittest.TestCase):
    def test_put_counters_on_target(self):
        game, _, _ = table(pick(CAST, "Bear"))
        game.seats[0].hand = [GROWTH]
        game.seats[0].battlefield = lands(3) + [Permanent(BEAR)]
        game._priority_round(game.seats[0])
        bear = game.seats[0].battlefield[-1]
        self.assertEqual(bear.counters, {"+1/+1": 2})
        self.assertEqual(game.label(bear), "Bear 4/4 (seat 0, #4)")

    def test_minus_counters_kill_and_restrict_targets(self):
        game, _, _ = table(pick(CAST, "Bear"))
        game.seats[0].hand = [WITHER]
        game.seats[0].battlefield = lands(1) + [Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(BEAR)]
        options = [label for label, _ in game.target_options("creature an opponent controls", game.seats[0])]
        self.assertEqual(options, ["Bear 2/2 (seat 1, #1)"])
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].battlefield, [])  # 0/0 dies
        self.assertEqual(len(game.seats[0].battlefield), 2)

    def test_plus_and_minus_counters_cancel(self):
        game, _, _ = table()
        bear = Permanent(BEAR, counters={"+1/+1": 3, "-1/-1": 1})
        game.seats[0].battlefield = [bear]
        game._check_state()
        self.assertEqual(bear.counters, {"+1/+1": 2, "-1/-1": 0})

    def test_counters_on_each_creature_you_control(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [RALLY]
        game.seats[0].battlefield = lands(2) + [Permanent(BEAR), Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(BEAR)]
        game._priority_round(game.seats[0])
        self.assertEqual([p.counters for p in game.seats[0].battlefield[2:]], [{"+1/+1": 1}] * 2)
        self.assertEqual(game.seats[1].battlefield[0].counters, {})

    def test_enters_with_counters(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [HYDRA]
        game.seats[0].battlefield = lands(2)
        game._priority_round(game.seats[0])
        hydra = game.seats[0].battlefield[-1]
        self.assertEqual((power(hydra), toughness(hydra)), (3, 3))  # a 0/0 that survives

    def test_counters_matter_for_damage_and_combat(self):
        game, _, _ = table(pick(CAST, "Bear"))
        game.seats[0].hand = [BOLT]
        game.seats[0].battlefield = lands(1)
        big = Permanent(BEAR, counters={"+1/+1": 2})
        game.seats[1].battlefield = [big]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].battlefield, [big])  # 4/4 survives 3 damage

        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(BEAR, counters={"+1/+1": 1})]
        b.battlefield = [Permanent(BEAR)]
        game.combat.declare_attackers(a)
        game.combat.declare_blockers()
        game.combat.deal_damage(first_strike_step=False)
        game._check_state()
        self.assertEqual((len(a.battlefield), len(b.battlefield)), (1, 0))  # 3/3 beats 2/2

    def test_attack_trigger_puts_a_counter_on_itself(self):
        game, _, _ = table(attack_all)
        a = game.seats[0]
        a.battlefield = [Permanent(BRUTE)]
        game.turn = 3
        game._take_turn(a)
        self.assertEqual(a.battlefield[0].counters, {"+1/+1": 1})
        self.assertEqual(game.seats[1].life, 37)  # the counter lands before damage

    def test_report(self):
        for card in (GROWTH, WITHER, RALLY, HYDRA, BRUTE):
            self.assertEqual(unsupported_lines(card), [], card.name)


if __name__ == "__main__":
    unittest.main()
