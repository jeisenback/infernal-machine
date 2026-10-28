"""Speed (CR 702.178, 702.179) with Howlsquad Heavy: "Start your engines!" gives speed 1 when a player controls the permanent, speed goes up
once each turn when an opponent loses life on your turn, and "Max speed" abilities work at speed 4. Howlsquad Heavy's own token
attacks the turn it is made."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, real, table, table3

HOWLSQUAD = real("Howlsquad Heavy", "{2}{R}", "Creature — Goblin Mercenary",
                 "Start your engines! (If you have no speed, it starts at 1. It increases once on each of your turns when an opponent loses life. Max speed is 4.)\n"
                 "Other Goblins you control have haste.\n"
                 "At the beginning of combat on your turn, create a 1/1 red Goblin creature token. That token attacks this combat if able.\n"
                 "Max speed — {T}: Add {R} for each Goblin you control.", "2", "3", colors=("R",))
ONE = real("Probe Spell", "{R}", "Sorcery", "")
THREE = real("Probe Spell Three", "{R}{R}{R}", "Sorcery", "")


def seat_with(*permanents):
    game, _ = table3(pick("Probe Spell"))
    a = game.seats[0]
    a.battlefield = list(permanents)
    return game, a


class SpeedTests(unittest.TestCase):
    def test_speed_starts_at_one_with_the_permanent(self):
        game, a = seat_with(Permanent(HOWLSQUAD, sick=False))
        self.assertEqual(a.speed, 0)
        game._check_state()
        self.assertEqual(a.speed, 1)

    def test_a_player_without_the_ability_has_no_speed(self):
        game, a = seat_with(Permanent(BEAR))
        game._check_state()
        self.assertEqual(a.speed, 0)

    def test_it_goes_up_once_each_turn_when_an_opponent_loses_life_on_your_turn(self):
        game, a = seat_with(Permanent(HOWLSQUAD, sick=False))
        game._check_state()
        opponent = game.seats[1]
        game.change_life(opponent, -1)
        game.change_life(opponent, -1)
        self.assertEqual(a.speed, 2)
        game.turn += 1
        game.change_life(opponent, -1)
        self.assertEqual(a.speed, 3)

    def test_it_stops_at_four(self):
        game, a = seat_with(Permanent(HOWLSQUAD, sick=False))
        game._check_state()
        for _ in range(6):
            game.turn += 1
            game.change_life(game.seats[1], -1)
        self.assertEqual(a.speed, 4)

    def test_not_for_life_you_lose_or_life_lost_on_another_turn_or_with_no_speed(self):
        game, a = seat_with(Permanent(HOWLSQUAD, sick=False))
        game._check_state()
        game.change_life(a, -1)  # your own life
        game.active = 1
        game.change_life(a, -1)  # during an opponent's turn
        game.change_life(game.seats[2], -1)  # (they have no speed, and it is not your turn)
        self.assertEqual((a.speed, game.seats[1].speed), (1, 0))
        game.active = 0
        game.seats[1].battlefield = []
        game.change_life(game.seats[2], -1)
        self.assertEqual(a.speed, 2)


class MaxSpeedTests(unittest.TestCase):
    def test_the_mana_ability_works_only_at_speed_four(self):
        game, a = seat_with(Permanent(HOWLSQUAD, sick=False))
        game._check_state()
        a.speed = 3
        self.assertIsNone(game._payment(a, ONE))
        a.speed = 4
        self.assertIsNotNone(game._payment(a, ONE))

    def test_it_makes_a_mana_for_each_goblin_you_control(self):
        token = real("Goblin", "", "Token Creature — Goblin", "", "1", "1", colors=("R",))
        game, a = seat_with(Permanent(HOWLSQUAD, sick=False), Permanent(token, sick=False), Permanent(token, sick=False))
        game._check_state()
        a.speed = 4
        self.assertIsNotNone(game._payment(a, THREE))  # three Goblins: {R}{R}{R}
        a.battlefield.pop()
        self.assertIsNone(game._payment(a, THREE))


SURVEYOR = real("Goblin Surveyor", "{2}{R}", "Creature \u2014 Goblin Scout",
                "Start your engines! (If you have no speed, it starts at 1. It increases once on each of your turns when an opponent loses life. Max speed is 4.)\n"
                "Max speed \u2014 {3}, Exile this card from your graveyard: Draw a card.", "3", "1", colors=("R",))
COLUMN = real("Starting Column", "{3}", "Artifact",
              "Start your engines! (If you have no speed, it starts at 1. It increases once on each of your turns when an opponent loses life. Max speed is 4.)\n"
              "Max speed \u2014 {T}, Sacrifice this artifact: Draw two cards, then discard a card.")
ASCENDANT = real("Embalmed Ascendant", "{3}{B}", "Creature \u2014 Zombie Wizard",
                 "Start your engines! (If you have no speed, it starts at 1. It increases once on each of your turns when an opponent loses life. Max speed is 4.)\n"
                 "When this creature enters, create a 2/2 black Zombie creature token.\n"
                 "Max speed \u2014 Whenever a creature you control dies, each opponent loses 1 life and you gain 1 life.", "2", "2", colors=("B",))


def offered(game, seat, needle):
    return [o for o in game.legal_actions(seat) if needle in o]


class MaxSpeedAbilityTests(unittest.TestCase):
    def test_an_ability_from_the_graveyard_waits_for_max_speed(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = lands(4)
        a.graveyard = [SURVEYOR]
        a.speed = 3
        self.assertEqual(offered(game, a, "Goblin Surveyor"), [])
        a.speed = 4
        self.assertEqual(len(offered(game, a, "Goblin Surveyor")), 1)

    def test_a_tap_and_sacrifice_ability_waits_for_max_speed(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(COLUMN, sick=False)]
        a.speed = 3
        self.assertEqual(offered(game, a, "Starting Column"), [])
        a.speed = 4
        self.assertEqual(len(offered(game, a, "Starting Column")), 1)

    def test_a_max_speed_trigger_is_not_read_so_the_card_is_not_reported_playable(self):
        self.assertEqual(len(unsupported_lines(ASCENDANT)), 1)
        self.assertEqual(unsupported_lines(SURVEYOR), [])


class HowlsquadTokenTests(unittest.TestCase):
    def test_it_makes_a_goblin_that_attacks_this_combat(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(HOWLSQUAD, sick=False)]
        game.turn, game.active = 3, 0
        game.step = "beginning_of_combat"
        game._turn_based_actions(a)
        game._priority_round(a)
        token = next(p for p in a.battlefield if p.card.name == "Goblin")
        game.step = "declare_attackers"
        game._turn_based_actions(a)  # the player's policy would decline every attack
        self.assertTrue(any(attack.attacker is token for attack in game.combat.attacks))
        self.assertFalse(any(attack.attacker.card.name == "Howlsquad Heavy" for attack in game.combat.attacks))


if __name__ == "__main__":
    unittest.main()
