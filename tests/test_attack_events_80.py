"""Triggers about another player's attack (issue #80): Firemane Commando, Breena the Demagogue and Combat Calligrapher.

Lines are the cards' own Oracle text from Scryfall. Each is played through a real declare-attackers step: player B (seat 1)
declares attackers at A (seat 0, who owns the watcher) and/or C (seat 2). Each has cases where it must not fire.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, run_stack, table3

FIREMANE = Card(name="Firemane Commando", mana_cost="{3}{W}", type_line="Creature — Angel Soldier", power="3", toughness="3",
                oracle_text="Flying\nWhenever you attack with two or more creatures, draw a card.\nWhenever another player "
                            "attacks with two or more creatures, they draw a card if none of those creatures attacked you.")
BREENA = Card(name="Breena, the Demagogue", mana_cost="{1}{W}{B}", type_line="Legendary Creature — Bird Warlock", power="1",
              toughness="3", oracle_text="Flying\nWhenever a player attacks one of your opponents, if that opponent has more "
                                         "life than another of your opponents, that attacking player draws a card and you put "
                                         "two +1/+1 counters on a creature you control.")
CALLIGRAPHER = Card(name="Combat Calligrapher", mana_cost="{3}{W}{B}", type_line="Creature — Bird Cleric", power="3",
                    toughness="3", oracle_text="Flying\nInklings can't attack you or planeswalkers you control.\nWhenever a "
                                               "player attacks one of your opponents, that attacking player creates a tapped "
                                               "2/1 white and black Inkling creature token with flying that's attacking that "
                                               "opponent.")


def declare(card, targets, attackers=2, lives=None, watcher=0, attacker=1):
    """`attacker` declares `attackers` creatures; `targets` are the options picked for them (1 is seat 0, 2 is seat 2 when
    seat 1 attacks). Returns (game, the watcher's permanent)."""
    picks = iter(targets)
    policy = lambda prompt, options: next(picks) if prompt.startswith("Attack") and len(options) > 1 else 0
    game, _ = table3(*[policy if i == attacker else None for i in range(3)])
    seats = game.seats
    watching = Permanent(card, sick=True)
    seats[watcher].battlefield = [watching]
    for seat in seats:
        seat.library = [BEAR] * 5
    seats[attacker].battlefield += [Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)][:attackers]
    for seat, life in zip(seats, lives or (40, 40, 40)):
        seat.life = life
    game.active = attacker
    game.combat.declare_attackers(seats[attacker])
    run_stack(game)
    return game, watching


class FiremaneCommandoTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(FIREMANE), [])

    def test_two_attackers_none_at_you_draws_them_a_card(self):
        game, _ = declare(FIREMANE, [2, 2])
        self.assertEqual(len(game.seats[1].hand), 1)
        self.assertEqual(len(game.seats[0].hand), 0)

    def test_one_attacker_at_you_stops_it(self):
        game, _ = declare(FIREMANE, [1, 2])
        self.assertEqual(len(game.seats[1].hand), 0)

    def test_a_single_attacker_is_not_two_or_more(self):
        game, _ = declare(FIREMANE, [2], attackers=1)
        self.assertEqual(len(game.seats[1].hand), 0)

    def test_your_own_attack_is_not_another_players(self):
        game, _ = declare(FIREMANE, [2, 2], watcher=1)  # the attacker owns the Commando: only its own line applies
        self.assertEqual(len(game.seats[1].hand), 1)  # from "Whenever you attack with two or more creatures"


class BreenaTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(BREENA), [])

    def test_attacking_the_opponent_with_more_life_draws_the_attacker_and_grows_breena(self):
        game, breena = declare(BREENA, [2, 2], lives=(40, 30, 40))  # B attacks C, who has more life than B
        self.assertEqual(len(game.seats[1].hand), 1)
        self.assertEqual(breena.counters.get("+1/+1"), 2)

    def test_equal_life_does_nothing(self):
        game, breena = declare(BREENA, [2, 2], lives=(40, 40, 40))
        self.assertEqual((len(game.seats[1].hand), breena.counters.get("+1/+1")), (0, None))

    def test_attacking_the_opponent_with_less_life_does_nothing(self):
        game, breena = declare(BREENA, [2, 2], lives=(40, 30, 20))
        self.assertEqual((len(game.seats[1].hand), breena.counters.get("+1/+1")), (0, None))

    def test_an_attack_on_breenas_controller_does_nothing(self):
        game, breena = declare(BREENA, [1, 1], lives=(50, 30, 40))
        self.assertEqual((len(game.seats[1].hand), breena.counters.get("+1/+1")), (0, None))

    def test_it_triggers_once_per_opponent_attacked(self):
        game, breena = declare(BREENA, [2, 2], lives=(40, 30, 40))
        self.assertEqual(breena.counters.get("+1/+1"), 2)  # two attackers at C, one trigger

    def test_the_controllers_own_attack_counts(self):
        game, breena = declare(BREENA, [1, 1], lives=(40, 50, 30), watcher=0, attacker=0)
        self.assertEqual(len(game.seats[0].hand), 1)  # A attacks B, who has more life than C
        self.assertEqual(breena.counters.get("+1/+1"), 2)


WALKER = Card(name="Walker", mana_cost="{3}", type_line="Legendary Planeswalker — Test", loyalty="4")


class PlaneswalkerAttackTests(unittest.TestCase):
    def test_attacking_an_opponents_planeswalker_is_not_attacking_the_opponent(self):
        def at_walker(prompt, options):
            return next((i for i, o in enumerate(options) if o.startswith("Attack Planeswalker")), 0)
        game, _ = table3(None, at_walker)
        a, b, c = game.seats
        breena = Permanent(BREENA, sick=True)
        a.battlefield = [breena]
        c.battlefield = [Permanent(WALKER, loyalty=4)]
        b.battlefield = [Permanent(BEAR, sick=False)]
        b.life, c.life = 30, 40
        game.active = 1
        game.combat.declare_attackers(b)
        run_stack(game)
        self.assertTrue(any(at.walker is not None for at in game.combat.attacks))  # it did attack the planeswalker
        self.assertEqual((len(b.hand), breena.counters.get("+1/+1")), (0, None))


class CombatCalligrapherTests(unittest.TestCase):
    def inklings(self, game, seat):
        return [p for p in game.seats[seat].battlefield if p.card.name == "Inkling"]

    def test_parse(self):
        self.assertEqual(unsupported_lines(CALLIGRAPHER), [])

    def test_the_attacker_gets_a_tapped_inkling_attacking_the_same_opponent(self):
        game, _ = declare(CALLIGRAPHER, [2, 2])
        [inkling] = self.inklings(game, 1)
        self.assertTrue(inkling.tapped)
        self.assertEqual((inkling.card.power, inkling.card.toughness, inkling.card.colors), ("2", "1", ("W", "B")))
        attack = next(a for a in game.combat.attacks if a.attacker is inkling)
        self.assertIs(attack.defender, game.seats[2])

    def test_one_token_for_the_attack_however_many_attackers(self):
        game, _ = declare(CALLIGRAPHER, [2, 2])
        self.assertEqual(len(self.inklings(game, 1)), 1)

    def test_attacking_its_controller_gives_nothing(self):
        game, _ = declare(CALLIGRAPHER, [1, 1])
        self.assertEqual(self.inklings(game, 1), [])

    def test_an_attack_split_between_its_controller_and_another_opponent_gives_one_token(self):
        game, _ = declare(CALLIGRAPHER, [1, 2])  # one at A (the controller), one at C
        self.assertEqual(len(self.inklings(game, 1)), 1)
