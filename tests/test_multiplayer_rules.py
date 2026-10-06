import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import BecomeMonarch, ExtraTurn, Goad, spell_effects
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, creature
from tests.test_effects import FOREST, lands, pick, table
from tests.test_mass_effects import table3

TIME_WALK = Card(name="Time Walk", mana_cost="{1}{U}", type_line="Sorcery", oracle_text="Take an extra turn after this one.")
ISLAND = Card(name="Island", type_line="Basic Land", produced_mana=("U",))
PALACE = creature("Palace Jailer", 2, 2, "When CARDNAME enters, you become the monarch.")
ROPE = Card(name="Rope", mana_cost="{1}{R}", type_line="Sorcery", oracle_text="Goad target creature.")
ARCHERS = Card(name="Archers", mana_cost="{2}", type_line="Enchantment",
               oracle_text="Whenever a creature attacks you or a planeswalker you control, you gain 1 life.")


class ExtraTurnTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(TIME_WALK), [ExtraTurn()])
        self.assertEqual(unsupported_lines(TIME_WALK), [])

    def test_casting_it_queues_a_turn_for_the_caster(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [TIME_WALK]
        seat.battlefield = lands(2, ISLAND)
        game._priority_round(seat)
        self.assertEqual(game.extra_turns, [0])

    def test_the_extra_turn_comes_next_and_regular_order_resumes(self):
        game, _, _ = table()
        game.regular = 0
        game.extra_turns = [0]
        self.assertEqual(game._next_turn_seat(), 0)  # the extra turn
        self.assertEqual(game._next_turn_seat(), 1)  # then the next player in order
        self.assertEqual(game.regular, 1)

    def test_the_latest_extra_turn_goes_first(self):
        game, _, _ = table()
        game.extra_turns = [0, 1]
        self.assertEqual(game._next_turn_seat(), 1)
        self.assertEqual(game._next_turn_seat(), 0)

    def test_a_player_who_lost_is_skipped(self):
        game, players = table3()
        game.regular = 0
        game.extra_turns = [1]
        game.seats[1].lost = True
        self.assertEqual(game._next_turn_seat(), 2)


class MonarchTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(PALACE), [])
        self.assertEqual(BecomeMonarch(), BecomeMonarch())

    def test_entering_makes_you_monarch(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [PALACE]
        seat.battlefield = lands(2, FOREST)
        game._priority_round(seat)
        self.assertIs(game.monarch, seat)

    def test_the_monarch_draws_at_their_end_step_only(self):
        game, _, _ = table()
        a, b = game.seats
        game.monarch = a
        game.step = "end"
        game._turn_based_actions(b)
        self.assertEqual(len(a.hand), 0)
        game._turn_based_actions(a)
        self.assertEqual(len(a.hand), 1)

    def test_combat_damage_to_the_monarch_steals_it(self):
        game, _, _ = table()
        a, b = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        game.monarch = b
        game.damage(b, 2, source=bear, combat=False)
        self.assertIs(game.monarch, b)  # only combat damage counts
        game.damage(b, 2, source=bear, combat=True)
        self.assertIs(game.monarch, a)

    def test_the_active_player_takes_it_when_the_monarch_loses(self):
        game, _ = table3()
        a, b, c = game.seats
        game.monarch = b
        b.life = 0
        game._check_state()
        self.assertIs(game.monarch, a)


class GoadTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(ROPE), [Goad("creature")])

    def test_a_goaded_creature_attacks_even_if_its_controller_would_not(self):
        game, _, _ = table()
        a, b = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        bear.goaded_by = b
        game.combat.declare_attackers(a)  # policy says "don't attack"
        self.assertEqual([x.defender for x in game.combat.attacks], [b])

    def test_it_attacks_someone_other_than_the_goader(self):
        game, _ = table3()
        a, b, c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        bear.goaded_by = b
        game.combat.declare_attackers(a)
        self.assertEqual([x.defender for x in game.combat.attacks], [c])

    def test_it_can_choose_among_other_opponents(self):
        game, _ = table3(lambda prompt, options: len(options) - 1)
        a, b, c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        bear.goaded_by = a
        game.combat.declare_attackers(a)
        self.assertEqual([x.defender for x in game.combat.attacks], [c])

    def test_goad_wears_off_at_the_goaders_next_turn(self):
        game, _ = table3()
        a, b, c = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        bear.goaded_by = b
        game.step = "untap"
        game._turn_based_actions(c)
        self.assertIs(bear.goaded_by, b)
        game._turn_based_actions(b)
        self.assertIsNone(bear.goaded_by)

    def test_casting_goad(self):
        game, _ = table3(pick(CAST))
        a, b, c = game.seats
        target = Permanent(BEAR)
        b.battlefield = [target]
        a.hand = [ROPE]
        a.battlefield = lands(2, Card(name="Mountain", type_line="Basic Land", produced_mana=("R",)))
        game._priority_round(a)
        self.assertIs(target.goaded_by, a)


class AttackedTriggerTests(unittest.TestCase):
    def test_you_are_attacked(self):
        game, _ = table3(lambda prompt, options: 0 if options[0] != "Don't attack" else 2)
        a, b, c = game.seats
        a.battlefield = [Permanent(BEAR), Permanent(BEAR)]
        b.battlefield = [Permanent(ARCHERS)]
        game.combat.declare_attackers(a)  # option 2 is the second opponent, seat 2
        game._priority_round(a)
        self.assertEqual(b.life, 40)  # they were not attacked, so nothing

    def test_attackers_pointing_at_you_trigger_once_each(self):
        game, _ = table3(lambda prompt, options: 1 if options[0] == "Don't attack" else 0)
        a, b, c = game.seats
        a.battlefield = [Permanent(BEAR), Permanent(BEAR)]
        b.battlefield = [Permanent(ARCHERS)]
        game.combat.declare_attackers(a)  # option 1 is the first opponent, seat 1
        game._priority_round(a)
        self.assertEqual(b.life, 42)

    def test_it_means_the_attacker_which_is_not_supported(self):
        card = Card(name="W", type_line="Enchantment",
                    oracle_text="Whenever a creature attacks you, put a +1/+1 counter on it.")
        self.assertEqual(len(unsupported_lines(card)), 1)


if __name__ == "__main__":
    unittest.main()
