"""Trigger lines from the five precon decks that #80 listed and the report still marked unsupported (real Oracle text from
Scryfall). Each has cases where the trigger must not fire.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import fire

PAY = lambda prompt, options: 0
DECLINE = lambda prompt, options: len(options) - 1

TOMIK = Card(name="Tomik, Wielder of Law", mana_cost="{3}{W}{U}", type_line="Legendary Creature — Human Advisor", power="4",
             toughness="3", oracle_text="Flying\nWhenever an opponent attacks with creatures, if two or more of those creatures "
                                        "are attacking you and/or planeswalkers you control, that opponent loses 3 life and you "
                                        "draw a card.")
TRAITOR = Card(name="Nether Traitor", mana_cost="{B}{B}", type_line="Creature — Spirit", power="1", toughness="1",
               oracle_text="Haste\nWhenever another creature is put into your graveyard from the battlefield, you may pay {B}. If "
                           "you do, return this card from your graveyard to the battlefield.")


class TomikTests(unittest.TestCase):
    def attack(self, count):
        game, _ = table3()
        a, b, c = game.seats
        tomik = Permanent(TOMIK)
        a.battlefield = [tomik]
        a.library = [BEAR] * 5
        game.trigger("opponent_attacks", tomik, a, player=b, x=count)
        run_stack(game)
        return a, b, c

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(TOMIK), [])

    def test_two_attackers_at_you_costs_that_opponent_three_life_and_draws_you_a_card(self):
        a, b, c = self.attack(2)
        self.assertEqual((b.life, c.life, a.life, len(a.hand)), (37, 40, 40, 1))

    def test_one_attacker_at_you_does_nothing(self):
        a, b, c = self.attack(1)
        self.assertEqual((b.life, len(a.hand)), (40, 0))

    def combat(self, targets):
        """Player B declares two attackers; `targets` are the options picked for them (1 is seat 0, 2 is seat 2)."""
        picks = iter(targets)
        policy = lambda prompt, options: next(picks) if prompt.startswith("Attack") and len(options) > 1 else 0
        game, _ = table3(None, policy)
        a, b, c = game.seats
        tomik = Permanent(TOMIK)
        a.battlefield = [tomik]
        a.library = [BEAR] * 5
        b.battlefield = [Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)]
        game.active = 1
        game.combat.declare_attackers(b)
        run_stack(game)
        return a, b

    def test_in_real_combat_two_attackers_aimed_at_you_trigger_it(self):
        a, b = self.combat([1, 1])
        self.assertEqual((b.life, len(a.hand)), (37, 1))

    def test_in_real_combat_attackers_split_between_players_do_not(self):
        a, b = self.combat([1, 2])  # one at you, one at the third player
        self.assertEqual((b.life, len(a.hand)), (40, 0))


class NetherTraitorTests(unittest.TestCase):
    def die(self, owner_index, policy=PAY, mana=1, token=False):
        game, _ = table3(policy)
        a, b, c = game.seats
        a.graveyard, a.battlefield = [TRAITOR], lands(mana)
        card = Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1") if token else BEAR
        victim = Permanent(card)
        game.seats[owner_index].battlefield.append(victim)
        game._leave_together([(victim, "destroyed")])
        run_stack(game)
        return a

    def graveyard(self, seat):
        return [c.name for c in seat.graveyard]

    def creatures(self, seat):
        return [p.card.name for p in seat.battlefield if "Creature" in p.card.type_line]

    def test_it_is_supported(self):
        self.assertEqual(unsupported_lines(TRAITOR), [])

    def test_another_creature_of_yours_dying_and_paying_b_brings_it_back(self):
        a = self.die(0)
        self.assertEqual((self.creatures(a), self.graveyard(a)), (["Nether Traitor"], ["Bear"]))
        self.assertEqual(sum(p.tapped for p in a.battlefield if "Land" in p.card.type_line), 1)  # {B} was paid

    def test_a_token_of_yours_counts_too(self):
        a = self.die(0, token=True)
        self.assertEqual(self.creatures(a), ["Nether Traitor"])

    def test_declining_to_pay_leaves_it_in_the_graveyard(self):
        a = self.die(0, policy=DECLINE)
        self.assertEqual((self.creatures(a), "Nether Traitor" in self.graveyard(a)), ([], True))

    def test_without_mana_it_stays(self):
        a = self.die(0, mana=0)
        self.assertEqual((self.creatures(a), "Nether Traitor" in self.graveyard(a)), ([], True))

    def test_an_opponents_creature_dying_does_nothing(self):
        a = self.die(1)
        self.assertEqual((self.creatures(a), "Nether Traitor" in self.graveyard(a)), ([], True))
