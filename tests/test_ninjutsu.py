"""Ninjutsu and Commander ninjutsu: after blockers are declared, return an unblocked attacker and the ninja comes in attacking."""

import unittest

from infernal_machine.effects import ninjutsu_of
from infernal_machine.game import NINJUTSU, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, attack_all
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

NINJA = real("Ninja of the Deep Hours", "{3}{U}", "Creature — Human Ninja", "Ninjutsu {1}{U} ({1}{U}, Return an unblocked attacker you control "
             "to hand: Put this card onto the battlefield from your hand tapped and attacking.)\nWhenever this creature deals combat damage to a "
             "player, you may draw a card.", "2", "2")
YURIKO = real("Yuriko, the Tiger's Shadow", "{U}{B}", "Legendary Creature — Human Ninja", "Commander ninjutsu {U}{B}", "1", "3")
OTHER = real("Other Ninja", "{1}{U}", "Creature — Ninja", "Ninjutsu {U}", "1", "1")


def combat(attackers, blockers=(), hand=(), command=(), mana=2, policy=None, step="declare_blockers"):
    """Seat A attacks with `attackers`, seat B has `blockers` (which block if the policy lets them); the step is `step`."""
    game, _ = table3(policy or attack_all)
    a, b = game.seats[:2]
    a.hand, a.command_zone, a.graveyard = list(hand), list(command), []
    a.battlefield = lands(mana) + [Permanent(c, sick=False) for c in attackers]
    b.battlefield = [Permanent(c, sick=False) for c in blockers]
    game.combat.declare_attackers(a)
    game.combat.declare_blockers()
    game.step = step
    return game, a, b


def ninjutsu(game, seat, name):
    game._perform(seat, NINJUTSU + name)
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (NINJA, YURIKO):
            self.assertEqual([l for l in unsupported_lines(card) if "injutsu" in l], [], card.name)

    def test_the_cost_is_read(self):
        self.assertEqual(ninjutsu_of(NINJA), ("{1}{U}", False))
        self.assertEqual(ninjutsu_of(YURIKO), ("{U}{B}", True))
        self.assertIsNone(ninjutsu_of(BEAR))


class TimingTests(unittest.TestCase):
    def offered(self, **kwargs):
        game, a, b = combat([BEAR], hand=[NINJA], **kwargs)
        return NINJUTSU + "Ninja of the Deep Hours" in game.legal_actions(a)

    def test_it_is_offered_once_blockers_are_declared(self):
        self.assertTrue(self.offered())

    def test_not_before_blockers(self):
        self.assertFalse(self.offered(step="declare_attackers"))

    def test_not_after_combat_damage(self):
        self.assertFalse(self.offered(step="combat_damage"))

    def test_not_in_a_main_phase(self):
        self.assertFalse(self.offered(step="main2"))

    def test_not_without_the_mana(self):
        self.assertFalse(self.offered(mana=1))

    def test_not_for_a_blocked_attacker(self):
        game, a, b = combat([BEAR], [OGRE], hand=[NINJA])
        game.combat.attacks[0].blockers = [b.battlefield[0]]
        self.assertNotIn(NINJUTSU + "Ninja of the Deep Hours", game.legal_actions(a))

    def test_not_for_an_attacker_that_stays_blocked_after_its_blockers_leave(self):
        game, a, b = combat([BEAR], hand=[NINJA])
        game.combat.attacks[0].blocked = True
        self.assertNotIn(NINJUTSU + "Ninja of the Deep Hours", game.legal_actions(a))

    def test_not_for_a_card_with_no_ninjutsu(self):
        game, a, b = combat([BEAR], hand=[OGRE])
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(NINJUTSU)])

    def test_not_when_nothing_attacks(self):
        game, a, b = combat([], hand=[NINJA])
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(NINJUTSU)])

    def test_the_defending_player_cannot_use_it(self):
        game, a, b = combat([BEAR], hand=[NINJA])
        b.hand, b.battlefield = [NINJA], lands(2)
        self.assertFalse([x for x in game.legal_actions(b) if x.startswith(NINJUTSU)])


class ResolveTests(unittest.TestCase):
    def test_the_ninja_replaces_the_attacker(self):
        game, a, b = combat([BEAR], hand=[NINJA])
        ninjutsu(game, a, NINJA.name)
        [attack] = game.combat.attacks
        self.assertIs(attack.attacker.card, NINJA)
        self.assertTrue(attack.attacker.tapped)
        self.assertIs(attack.defender, b)
        self.assertEqual([c.name for c in a.hand], ["Bear"])
        self.assertNotIn(NINJA, a.hand)

    def test_it_costs_its_mana_cost_not_the_creatures(self):
        game, a, b = combat([BEAR], hand=[NINJA], mana=2)
        ninjutsu(game, a, NINJA.name)
        self.assertEqual(game._mana_sources(a), [])

    def test_the_ability_is_on_the_stack_until_it_resolves(self):
        game, a, b = combat([BEAR], hand=[NINJA])
        game._perform(a, NINJA_ACTION)
        self.assertEqual(len(game.stack), 1)
        self.assertIn(NINJA, a.hand)
        self.assertEqual(game.combat.attacks, [])

    def test_the_ninja_deals_combat_damage_and_its_trigger_works(self):
        game, a, b = combat([BEAR], hand=[NINJA])
        a.library = [BEAR] * 3
        ninjutsu(game, a, NINJA.name)
        game.combat.deal_damage(first_strike_step=False)
        game._check_state()
        self.assertEqual(b.damage_taken, 2)

    def test_with_two_attackers_the_player_chooses_which_returns(self):
        game, a, b = combat([BEAR, OGRE], hand=[NINJA])
        a.player.policy = script("Ogre")
        ninjutsu(game, a, NINJA.name)
        self.assertEqual(sorted(x.attacker.card.name for x in game.combat.attacks), ["Bear", "Ninja of the Deep Hours"])
        self.assertEqual([c.name for c in a.hand], ["Ogre"])

    def test_it_attacks_the_planeswalker_the_creature_attacked(self):
        game, a, b = combat([BEAR], hand=[NINJA])
        walker = Permanent(real("Walker", "{3}", "Planeswalker — Test", "", None, None), sick=False)
        walker.loyalty = 3
        b.battlefield.append(walker)
        game.combat.attacks[0].walker = walker
        ninjutsu(game, a, NINJA.name)
        self.assertIs(game.combat.attacks[0].walker, walker)

    def test_it_does_not_enter_if_the_card_left_the_hand(self):
        game, a, b = combat([BEAR], hand=[NINJA])
        game._perform(a, NINJA_ACTION)
        a.hand.remove(NINJA)
        run_stack(game)
        self.assertEqual([x.attacker.card for x in game.combat.attacks], [])
        self.assertNotIn(NINJA, [p.card for p in a.battlefield])

    def test_the_returned_creature_can_be_cast_again(self):
        game, a, b = combat([BEAR], hand=[NINJA])
        ninjutsu(game, a, NINJA.name)
        self.assertIn(BEAR, a.hand)


class CommanderNinjutsuTests(unittest.TestCase):
    def test_it_works_from_the_command_zone(self):
        game, a, b = combat([BEAR], command=[YURIKO], mana=0)
        a.battlefield += lands(2)
        self.assertIn(NINJUTSU + YURIKO.name, game.legal_actions(a))
        ninjutsu(game, a, YURIKO.name)
        self.assertEqual(a.command_zone, [])
        self.assertIs(game.combat.attacks[0].attacker.card, YURIKO)

    def test_it_works_from_the_hand_too(self):
        game, a, b = combat([BEAR], hand=[YURIKO], mana=2)
        self.assertIn(NINJUTSU + YURIKO.name, game.legal_actions(a))

    def test_plain_ninjutsu_does_not_work_from_the_command_zone(self):
        game, a, b = combat([BEAR], command=[NINJA], mana=2)
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(NINJUTSU)])


NINJA_ACTION = NINJUTSU + NINJA.name

if __name__ == "__main__":
    unittest.main()
