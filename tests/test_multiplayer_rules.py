import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (BecomeMonarch, ExtraCombat, ExtraTurn, Goad, TargetExtraTurn, UntapCreatures,
                                      spell_effects)
from infernal_machine.game import CAST, STEPS, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, creature
from tests.test_effects import FOREST, lands, pick, table
from tests.test_mass_effects import table3

TIME_WALK = Card(name="Time Walk", mana_cost="{1}{U}", type_line="Sorcery", oracle_text="Take an extra turn after this one.")
ISLAND = Card(name="Island", type_line="Basic Land", produced_mana=("U",))
PALACE = creature("Palace Jailer", 2, 2, "When CARDNAME enters, you become the monarch.")
ROPE = Card(name="Rope", mana_cost="{1}{R}", type_line="Sorcery", oracle_text="Goad target creature.")
RELENTLESS = Card(name="Relentless Assault", mana_cost="{2}{R}{R}", type_line="Sorcery",
                  oracle_text="Untap all creatures that attacked this turn. After this main phase, there is an "
                              "additional combat phase followed by an additional main phase.")
TIME_WARP = Card(name="Time Warp", mana_cost="{3}{U}{U}", type_line="Sorcery",
                 oracle_text="Target player takes an extra turn after this one.")
AGGRAVATED = Card(name="Aggravated Assault", mana_cost="{2}{R}", type_line="Enchantment",
                  oracle_text="{3}{R}{R}: Untap all creatures you control. After this main phase, there is an "
                              "additional combat phase followed by an additional main phase. "
                              "Activate only once each turn.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))
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



def cast_then_attack(prompt, options):
    """In the second main phase, cast whatever it can; attack the first opponent with everything; otherwise pass."""
    for i, option in enumerate(options):
        if option.startswith("Cast:") and "main2" in prompt:
            return i
    if options[0] == "Don't attack":
        return 1
    return options.index("Pass") if "Pass" in options else 0


class ExtraCombatTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(RELENTLESS), [UntapCreatures("attacked"), ExtraCombat(True)])
        self.assertEqual(spell_effects(TIME_WARP), [TargetExtraTurn()])
        for card in (RELENTLESS, TIME_WARP, AGGRAVATED):
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertEqual(spell_effects(Card(name="Seize", type_line="Sorcery", oracle_text=
                         "After this phase, there is an additional combat phase.")), [ExtraCombat(False)])

    def test_the_phases_go_after_the_current_one(self):
        game, _, _ = table()
        game.step, game._plan, game._plan_index = "main1", list(STEPS), STEPS.index("main1")
        game.add_combat(True)
        combat = STEPS[STEPS.index("beginning_of_combat"):STEPS.index("end_of_combat") + 1]
        self.assertEqual(game._plan, STEPS[:STEPS.index("main1") + 1] + combat + ["main2"] + STEPS[STEPS.index("beginning_of_combat"):])

    def test_from_inside_combat_it_waits_for_combat_to_end(self):
        game, _, _ = table()
        game.step, game._plan, game._plan_index = "declare_attackers", list(STEPS), STEPS.index("declare_attackers")
        game.add_combat(False)
        end = STEPS.index("end_of_combat")
        self.assertEqual(game._plan[end + 1:end + 6], STEPS[STEPS.index("beginning_of_combat"):end + 1])
        self.assertEqual(game._plan[end + 6], "main2")

    def test_a_creature_attacks_again_in_the_extra_combat(self):
        game, a, _ = self._turn(RELENTLESS)
        attacks = [e for e in game.seats[0].player.events if e["event"] == "attack"]
        self.assertEqual(len(attacks), 2)

    def test_without_the_card_it_attacks_once(self):
        game, a, _ = self._turn(None)
        self.assertEqual(len([e for e in game.seats[0].player.events if e["event"] == "attack"]), 1)

    def _turn(self, card):
        game, _, _ = table(cast_then_attack)
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR)] + lands(4, MOUNTAIN)
        a.hand = [card] if card else []
        game.turn = 3
        game._take_turn(a)
        return game, a, game.seats[1]

    def test_untap_only_the_creatures_that_attacked(self):
        game, _, _ = table()
        a = game.seats[0]
        attacker, idle = Permanent(BEAR, tapped=True), Permanent(BEAR, tapped=True)
        attacker.attacked_turn = game.turn
        UntapCreatures("attacked").resolve(game, a, None)
        a.battlefield = [attacker, idle]
        UntapCreatures("attacked").resolve(game, a, None)
        self.assertEqual([p.tapped for p in a.battlefield], [False, True])
        UntapCreatures("yours").resolve(game, a, None)
        self.assertEqual([p.tapped for p in a.battlefield], [False, False])

    def test_time_warp_gives_the_target_an_extra_turn(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.hand = [TIME_WARP]
        a.battlefield = lands(5, ISLAND)
        game._priority_round(a)
        self.assertEqual(len(game.extra_turns), 1)


if __name__ == "__main__":
    unittest.main()
