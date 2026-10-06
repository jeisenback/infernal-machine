import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
from infernal_machine.effects import (CannotRegenerate, Destroy, DestroyAll, Regenerate, RegenerateEach, RegenerateSource,
                                      activated_abilities, spell_effects)
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, creature
from tests.test_effects import lands, pick, table

SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
SKELETON = creature("Skeleton", 1, 1, "{B}: Regenerate CARDNAME.")
SHIELD = Card(name="Shield", mana_cost="{G}", type_line="Instant", oracle_text="Regenerate target creature.")
BLESS = Card(name="Bless", mana_cost="{G}", type_line="Instant", oracle_text="Regenerate each creature you control.")
DOJ = Card(name="Judgment", mana_cost="{2}{W}{W}", type_line="Sorcery", oracle_text="Destroy all creatures.")
WRATH = Card(name="Wrath", mana_cost="{2}{W}{W}", type_line="Sorcery",
             oracle_text="Destroy all creatures. They can't be regenerated.")
MURDER = Card(name="Murder", mana_cost="{1}{B}{B}", type_line="Instant", oracle_text="Destroy target creature.")
TERMINATE = Card(name="Terminate", mana_cost="{B}{R}", type_line="Instant",
                 oracle_text="Destroy target creature. It can't be regenerated.")


def shielded(card=BEAR, shields=1):
    p = Permanent(card)
    p.regeneration = shields
    return p


class ParseTests(unittest.TestCase):
    def test_the_effects(self):
        self.assertEqual(spell_effects(SHIELD), [Regenerate("creature")])
        self.assertEqual(spell_effects(BLESS), [RegenerateEach()])
        (ability,) = activated_abilities(SKELETON)
        self.assertEqual((ability.mana_cost, ability.effects), ("{B}", (RegenerateSource(),)))

    def test_cant_be_regenerated_folds_into_the_destroy(self):
        self.assertEqual(spell_effects(WRATH), [DestroyAll("creature", no_regen=True)])
        self.assertEqual(spell_effects(TERMINATE), [Destroy("creature", no_regen=True)])
        self.assertEqual(spell_effects(DOJ), [DestroyAll("creature")])

    def test_on_its_own_it_stays_a_no_op(self):
        card = Card(name="x", oracle_text="You gain 1 life. It can't be regenerated.")
        self.assertEqual(spell_effects(card)[-1], CannotRegenerate())

    def test_the_report(self):
        for card in (SKELETON, SHIELD, BLESS, WRATH, TERMINATE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class ShieldTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a, self.b = self.game.seats

    def test_a_shield_replaces_destruction(self):
        bear = shielded()
        self.a.battlefield = [bear]
        self.game.destroy(bear)
        self.assertEqual(self.a.battlefield, [bear])
        self.assertEqual((bear.tapped, bear.regeneration), (True, 0))
        self.game.destroy(bear)  # the shield is used up
        self.assertEqual(self.a.battlefield, [])

    def test_two_shields_stop_two_destroys(self):
        bear = shielded(shields=2)
        self.a.battlefield = [bear]
        self.game.destroy(bear)
        self.game.destroy(bear)
        self.assertEqual(self.a.battlefield, [bear])
        self.game.destroy(bear)
        self.assertEqual(self.a.battlefield, [])

    def test_it_loses_its_damage(self):
        bear = shielded()
        bear.damage = 1
        self.a.battlefield = [bear]
        self.game.destroy(bear)
        self.assertEqual(bear.damage, 0)

    def test_cant_be_regenerated_gets_past_the_shield(self):
        bear = shielded()
        self.a.battlefield = [bear]
        self.game.destroy(bear, no_regen=True)
        self.assertEqual(self.a.battlefield, [])

    def test_exile_and_sacrifice_are_not_destruction(self):
        a_bear, b_bear = shielded(), shielded()
        self.a.battlefield, self.b.battlefield = [a_bear], [b_bear]
        self.game.exile(a_bear)
        self.game.sacrifice(self.b)
        self.assertEqual((self.a.battlefield, self.b.battlefield), ([], []))

    def test_a_wipe_leaves_the_shielded_ones(self):
        mine, theirs = shielded(), Permanent(OGRE)
        self.a.battlefield, self.b.battlefield = [mine, Permanent(BEAR)], [theirs]
        self.game.destroy_all([mine, self.a.battlefield[1], theirs])
        self.assertEqual(self.a.battlefield, [mine])
        self.assertEqual(self.b.battlefield, [])

    def test_a_wipe_that_cant_be_regenerated_takes_them_too(self):
        mine = shielded()
        self.a.battlefield = [mine]
        self.game.destroy_all([mine], no_regen=True)
        self.assertEqual(self.a.battlefield, [])

    def test_lethal_damage_is_regenerated(self):
        bear = shielded()
        bear.damage = 2
        self.a.battlefield = [bear]
        self.game._check_state()
        self.assertEqual((self.a.battlefield, bear.damage, bear.tapped), ([bear], 0, True))

    def test_deathtouch_is_regenerated(self):
        bear = shielded()
        bear.deathtouched = True
        self.a.battlefield = [bear]
        self.game._check_state()
        self.assertEqual((self.a.battlefield, bear.deathtouched), ([bear], False))

    def test_without_a_shield_lethal_damage_still_kills(self):
        bear = Permanent(BEAR)
        bear.damage = 2
        self.a.battlefield = [bear]
        self.game._check_state()
        self.assertEqual(self.a.battlefield, [])

    def test_it_leaves_combat(self):
        attacker, blocker = shielded(OGRE), Permanent(BEAR)
        self.a.battlefield, self.b.battlefield = [attacker], [blocker]
        self.game.combat.attacks = [Attack(attacker, self.a, self.b, [blocker], True)]
        self.game.destroy(attacker)
        self.assertEqual(self.game.combat.attacks, [])
        blocked = shielded(BEAR)
        self.b.battlefield = [blocked]
        other = Permanent(OGRE)
        self.a.battlefield = [other]
        self.game.combat.attacks = [Attack(other, self.a, self.b, [blocked], True)]
        self.game.destroy(blocked)
        self.assertEqual(self.game.combat.attacks[0].blockers, [])
        self.assertTrue(self.game.combat.attacks[0].blocked)  # it stays blocked

    def test_shields_end_with_the_turn(self):
        bear = shielded()
        self.a.battlefield = [bear]
        self.game.step = "cleanup"
        self.game._turn_based_actions(self.a)
        self.assertEqual(bear.regeneration, 0)

    def test_toughness_zero_is_not_regenerable(self):
        bear = shielded(creature("Tiny", 1, 1))
        bear.counters["-1/-1"] = 1
        self.a.battlefield = [bear]
        self.game._check_state()
        self.assertEqual(self.a.battlefield, [])


class CastingTests(unittest.TestCase):
    def test_the_ability_gives_a_shield(self):
        game, _, _ = table(pick(ACTIVATE))
        a = game.seats[0]
        skeleton = Permanent(SKELETON)
        a.battlefield = [skeleton, Permanent(SWAMP)]
        game._priority_round(a)
        self.assertEqual(skeleton.regeneration, 1)

    def test_the_spell_gives_a_shield(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear] + lands(1)
        a.hand = [SHIELD]
        game._priority_round(a)
        self.assertEqual(bear.regeneration, 1)

    def test_regenerate_each(self):
        game, _, _ = table(pick(CAST))
        a, b = game.seats
        mine, also, theirs = Permanent(BEAR), Permanent(OGRE), Permanent(BEAR)
        a.battlefield, b.battlefield = [mine, also] + lands(1), [theirs]
        a.hand = [BLESS]
        game._priority_round(a)
        self.assertEqual((mine.regeneration, also.regeneration, theirs.regeneration), (1, 1, 0))

    def test_regenerating_in_response_to_a_wrath(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        bear = shielded()
        a.battlefield = [bear] + lands(4)
        a.hand = [DOJ]
        game._priority_round(a)
        self.assertEqual(a.battlefield[0], bear)
        self.assertTrue(bear.tapped)


if __name__ == "__main__":
    unittest.main()
