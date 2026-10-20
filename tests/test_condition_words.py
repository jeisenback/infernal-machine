"""Ability words that are a condition in front of an effect the engine already has (issue #427): Raid (you attacked this turn),
Lieutenant (you control your commander) and Enrage (this creature is dealt damage), from the real cards."""

import unittest

from infernal_machine.effects import enters_with_counters, triggered_abilities
from infernal_machine.effects.outcomes import Condition
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, TABLE3_COMMANDER, FOREST, OGRE, real, run_stack, table3

SPY = real("Storm Fleet Spy", "{2}{U}", "Creature — Human Pirate", "Raid — When this creature enters, if you attacked this turn, draw a card.", "2", "2")
ASPIRANT = real("War-Name Aspirant", "{1}{R}", "Creature — Human Warrior",
                "Raid — This creature enters with a +1/+1 counter on it if you attacked this turn.\nThis creature can't be blocked by creatures with power 1 or less.",
                "2", "1")
CERATOPS = real("Imperial Ceratops", "{4}{W}", "Creature — Dinosaur", "Enrage — Whenever this creature is dealt damage, you gain 2 life.", "3", "5")
SUBORDINATE = real("Loyal Subordinate", "{2}{B}", "Creature — Zombie",
                   "Menace (This creature can't be blocked except by two or more creatures.)\nLieutenant — At the beginning of combat on your turn, if you "
                   "control your commander, each opponent loses 3 life.", "3", "1")


def attacked(game, seat, how_many=1, turn=None):
    """`seat` declared an attack with that many creatures this turn (or on `turn`)."""
    seat.attackers_turn = game.turn if turn is None else turn
    seat.most_attackers = how_many


def enter(game, seat, card):
    permanent = Permanent(card)
    game._enter(seat, permanent)
    run_stack(game)
    return permanent


class RaidTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SPY, ASPIRANT):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_enters_trigger_draws_only_after_an_attack_this_turn(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST] * 5
        enter(game, a, SPY)
        self.assertEqual(len(a.hand), 0)  # no attack yet
        attacked(game, a)
        enter(game, a, SPY)
        self.assertEqual(len(a.hand), 1)

    def test_an_attack_on_another_turn_or_by_another_player_does_not_count(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.library = [FOREST] * 5
        attacked(game, a, turn=game.turn - 1)
        attacked(game, b)
        enter(game, a, SPY)
        self.assertEqual(len(a.hand), 0)

    def test_an_attack_with_no_creatures_is_not_an_attack(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST] * 5
        attacked(game, a, how_many=0)
        enter(game, a, SPY)
        self.assertEqual(len(a.hand), 0)

    def test_the_condition_is_read_as_attacked_this_turn(self):
        ability = triggered_abilities(SPY)[0]
        self.assertEqual(ability.condition, Condition("attacked_this_turn"))

    def test_the_counter_line_is_conditional_on_the_attack(self):
        self.assertEqual(enters_with_counters(ASPIRANT), {})
        self.assertEqual(enters_with_counters(ASPIRANT, raided=True), {"+1/+1": 1})

    def test_the_game_gives_the_counter_only_after_an_attack(self):
        game, _ = table3()
        a = game.seats[0]
        calm = enter(game, a, ASPIRANT)
        self.assertEqual(calm.counters.get("+1/+1", 0), 0)
        attacked(game, a)
        raided = enter(game, a, ASPIRANT)
        self.assertEqual(raided.counters.get("+1/+1", 0), 1)


class LieutenantTests(unittest.TestCase):
    def test_the_card_is_understood_and_asks_for_the_commander(self):
        self.assertEqual(unsupported_lines(SUBORDINATE), [])
        conditions = [ability.condition for ability in triggered_abilities(SUBORDINATE)]
        self.assertIn(Condition("control_commander"), conditions)

    def test_it_holds_only_while_your_commander_is_on_the_battlefield(self):
        game, _ = table3()
        a, b, _ = game.seats
        condition = Condition("control_commander")
        self.assertFalse(game.condition_holds(condition, a))
        a.battlefield.append(Permanent(OGRE))
        self.assertFalse(game.condition_holds(condition, a))
        a.battlefield.append(Permanent(TABLE3_COMMANDER))
        self.assertTrue(game.condition_holds(condition, a))
        self.assertFalse(game.condition_holds(condition, b))  # it is a's commander, not b's

    def test_a_commander_in_the_command_zone_does_not_count(self):
        game, _ = table3()
        a = game.seats[0]
        a.command_zone = [TABLE3_COMMANDER]
        self.assertFalse(game.condition_holds(Condition("control_commander"), a))


class EnrageTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        self.assertEqual(unsupported_lines(CERATOPS), [])

    def test_being_dealt_damage_sets_it_off_each_time(self):
        game, _ = table3()
        a = game.seats[0]
        dino = Permanent(CERATOPS)
        a.battlefield = [dino]
        game.damage(dino, 1)
        run_stack(game)
        self.assertEqual(a.life, 42)
        game.damage(dino, 2)
        run_stack(game)
        self.assertEqual(a.life, 44)

    def test_no_damage_or_damage_to_something_else_does_not(self):
        game, _ = table3()
        a, b, _ = game.seats
        dino, bear = Permanent(CERATOPS), Permanent(BEAR)
        a.battlefield = [dino, bear]
        game.damage(dino, 0)
        game.damage(bear, 1)
        game.damage(a, 3)
        run_stack(game)
        self.assertEqual(a.life, 37)  # only the 3 to the player

    def test_it_fires_even_when_the_damage_kills_it(self):
        game, _ = table3()
        a = game.seats[0]
        dino = Permanent(CERATOPS)
        a.battlefield = [dino]
        game.damage(dino, 5)
        run_stack(game)
        self.assertEqual(a.life, 42)

    def test_a_fight_in_reply_to_damage_ends_when_the_creatures_die(self):
        """Apex Altisaur fights each time it is dealt damage, and a fight deals damage to it: the loop ends once the creatures it fights are dead."""
        altisaur = real("Apex Altisaur", "{6}{G}{G}", "Creature — Dinosaur",
                        "When this creature enters, it fights up to one target creature you don't control.\nEnrage — Whenever this creature is dealt damage, it fights up to one target creature you don't control.",
                        "10", "10")
        game, _ = table3(lambda prompt, options: 0)
        a, b, _ = game.seats
        dino, bear, ogre = Permanent(altisaur), Permanent(BEAR), Permanent(OGRE)
        a.battlefield = [dino]
        b.battlefield = [bear, ogre]
        game.damage(dino, 1)
        for _ in range(20):  # a loop that did not end would never leave this
            if not (game.pending or game.stack):
                break
            game._put_triggers_on_stack()
            while game.stack:
                game._resolve(game.stack.pop())
                game._check_state()
        else:
            self.fail("the fights never ended")
        self.assertEqual(b.battlefield, [])  # both fought and died
        self.assertIn(dino, a.battlefield)

    def test_the_event_is_declared(self):
        from infernal_machine.effects import EVENTS
        self.assertIn("damaged", EVENTS)


if __name__ == "__main__":
    unittest.main()
