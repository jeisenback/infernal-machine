import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import activated_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands, table
from tests.test_trigger_subjects import attack_first_opponent
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

HOUND = Card(name="Lizard Hound", mana_cost="{2}", type_line="Artifact Creature — Equipment Dog", power="2", toughness="2",
             oracle_text="Equipped creature gets +1/+1.\nReconfigure {2}")


def board(*extra):
    game, _ = table3()
    a = game.seats[0]
    hound = Permanent(HOUND)
    a.battlefield = [hound, *extra, *lands(4)]
    return game, a, hound


def reconfigure(game, a, unattach=False):
    [action] = [x for x in game._activations(a, True) if x.endswith("(unattach)") == unattach and "Reconfigure" in x]
    game._perform(a, action)
    run_stack(game)


class ReconfigureTests(unittest.TestCase):
    def test_parse(self):
        attach, unattach = activated_abilities(HOUND)
        self.assertEqual((attach.reconfigure, unattach.reconfigure, attach.sorcery_speed), ("attach", "unattach", True))
        self.assertEqual(unsupported_lines(HOUND), [])

    def test_attaching_makes_it_a_non_creature_that_buffs_the_host(self):
        bear = Permanent(BEAR)
        game, a, hound = board(bear)
        before = game.power(bear)
        reconfigure(game, a)
        self.assertIs(hound.attached_to, bear)
        self.assertNotIn("Creature", hound.card.type_line)
        self.assertIn("Equipment", hound.card.type_line)
        self.assertEqual(game.power(bear), before + 1)

    def test_not_offered_with_no_other_creature(self):
        game, a, hound = board()
        self.assertEqual([x for x in game._activations(a, True) if "Reconfigure" in x], [])

    def test_unattach_is_offered_only_while_attached(self):
        bear = Permanent(BEAR)
        game, a, hound = board(bear)
        self.assertEqual(len([x for x in game._activations(a, True) if "Reconfigure" in x]), 1)  # attach only
        reconfigure(game, a)
        self.assertEqual(len([x for x in game._activations(a, True) if "Reconfigure" in x]), 2)  # move or unattach

    def test_the_unattach_ability_frees_it(self):
        bear = Permanent(BEAR)
        game, a, hound = board(bear)
        reconfigure(game, a)
        reconfigure(game, a, unattach=True)
        self.assertEqual((hound.attached_to, hound.card), (None, HOUND))

    def test_unattaching_makes_it_a_creature_again(self):
        bear = Permanent(BEAR)
        game, a, hound = board(bear)
        reconfigure(game, a)
        game.detach(hound)
        self.assertIsNone(hound.attached_to)
        self.assertIn("Creature", hound.card.type_line)
        self.assertEqual(hound.card, HOUND)

    def test_the_host_dying_frees_it_as_a_creature(self):
        bear = Permanent(BEAR)
        game, a, hound = board(bear)
        reconfigure(game, a)
        game._leave_together([(bear, "destroyed")])
        game._check_state()
        self.assertEqual((hound.attached_to, hound.card), (None, HOUND))

    def test_leaving_the_battlefield_while_attached_is_the_real_card(self):
        bear = Permanent(BEAR)
        game, a, hound = board(bear)
        reconfigure(game, a)
        game._leave_together([(hound, "destroyed")])
        self.assertEqual(a.graveyard, [HOUND])


GROW = Card(name="Frost Blade", mana_cost="{1}", type_line="Artifact — Equipment",
            oracle_text="Equipped creature gets +1/+1.\nWhenever equipped creature attacks, put a +1/+1 counter on it.\nEquip {1}")
RETURN = Card(name="Lifeline", mana_cost="{1}", type_line="Artifact — Equipment",
              oracle_text="Whenever equipped creature dies, return it to its owner's hand.\nEquip {1}")


class HostSubjectTests(unittest.TestCase):
    def test_it_means_the_equipped_creature(self):
        game, _, _ = table(attack_first_opponent)
        a = game.seats[0]
        bear, blade = Permanent(BEAR), Permanent(GROW)
        blade.attached_to = bear
        a.battlefield = [bear, blade]
        self.assertEqual(unsupported_lines(GROW), [])
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual((bear.counters, blade.counters), ({"+1/+1": 1}, {}))

    def test_it_after_the_creature_died_is_not_understood(self):
        self.assertEqual(len(unsupported_lines(RETURN)), 1)


if __name__ == "__main__":
    unittest.main()
