"""The Lizards of Standard's Rakdos deck, from their real Oracle text: Hired Claw ("Whenever you attack with one or more Lizards" and an
ability activated only if an opponent lost life this turn, once each turn), Master of Barbs (once for each spell or ability that deals
noncombat damage to opponents), Gev, Scaled Scorch (creatures enter with a counter for each opponent who lost life), Ingris
Stingerquill (each attacker deals 1 damage to each opponent) and Rockface Village (a pump for a Lizard, Mouse, Otter, or Raccoon)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, attack_all, creature, lands, pick, real, run_stack, table, table3

HIRED_CLAW = real("Hired Claw", "{R}", "Creature — Lizard Mercenary", "Whenever you attack with one or more Lizards, this creature deals 1 "
                  "damage to target opponent.\n{1}{R}: Put a +1/+1 counter on this creature. Activate only if an opponent lost life this "
                  "turn and only once each turn.", "1", "2", ("R",))
MASTER_OF_BARBS = real("Master of Barbs", "{1}{R}", "Creature — Lizard Bard", "Menace\nWhenever one or more opponents are dealt noncombat "
                       "damage, creatures you control get +1/+0 until end of turn.", "2", "1", ("R",))
GEV = real("Gev, Scaled Scorch", "{B}{R}", "Legendary Creature — Lizard Mercenary", "Ward—Pay 2 life.\nOther creatures you control enter "
           "with an additional +1/+1 counter on them for each opponent who lost life this turn.\nWhenever you cast a Lizard spell, Gev deals "
           "1 damage to target opponent.", "3", "2", ("B", "R"))
INGRIS = real("Ingris Stingerquill", "{B}{R}{R}", "Legendary Creature — Elder Sphinx", "Flying\nWhenever a creature you control attacks, that "
              "creature deals 1 damage to each opponent.\n{4}: Create a 2/2 colorless Wizard Soldier creature token named Cadet. Then "
              "creatures you control gain haste until end of turn.", "1", "4", ("B", "R"))
ROCKFACE_VILLAGE = real("Rockface Village", "", "Land", "{T}: Add {C}.\n{T}: Add {R}. Spend this mana only to cast a creature spell.\n{R}, "
                        "{T}: Target Lizard, Mouse, Otter, or Raccoon you control gets +1/+0 and gains haste until end of turn. Activate "
                        "only as a sorcery.")
SIZZLE = real("Sizzle", "{2}{R}", "Sorcery", "Sizzle deals 3 damage to each opponent.", colors=("R",))
LEECH = creature("Leech", 1, 1, "Lifelink")
LIZARD = Card(name="Lizard", type_line="Creature — Lizard", power="1", toughness="1")


class LizardPayoffTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (HIRED_CLAW, MASTER_OF_BARBS, GEV, INGRIS, ROCKFACE_VILLAGE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_hired_claw_deals_1_damage_when_you_attack_with_a_lizard(self):
        game, _, _ = table(attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(HIRED_CLAW)]
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(b.life, 39)

    def test_hired_claw_does_not_trigger_on_an_attack_without_a_lizard(self):
        game, _, _ = table(attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(HIRED_CLAW, sick=True), Permanent(BEAR)]  # the Claw can't attack this turn
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual(b.life, 40)

    def test_hired_claw_grows_only_after_an_opponent_lost_life_and_once_a_turn(self):
        game, _, _ = table()
        a, b = game.seats
        claw = Permanent(HIRED_CLAW)
        a.battlefield = [claw] + lands(4)
        grow = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Hired Claw")]
        self.assertEqual(grow, [])
        b.life_lost_turn, b.life_lost_amount = game.turn, 1
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Hired Claw")))
        run_stack(game)
        self.assertEqual(claw.counters.get("+1/+1"), 1)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Hired Claw")], [])

    def test_master_of_barbs_pumps_once_for_a_spell_that_hits_each_opponent(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(MASTER_OF_BARBS), bear] + lands(3)
        a.hand = [SIZZLE]
        game._perform(a, CAST + "Sizzle")
        run_stack(game)
        self.assertEqual(game.power(bear), 3)  # two opponents were dealt damage: one trigger

    def test_master_of_barbs_ignores_combat_damage_and_damage_to_you(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(MASTER_OF_BARBS), bear]
        game.damage(b, 2, source=bear, combat=True)
        game.damage(a, 2)
        run_stack(game)
        self.assertEqual(game.power(bear), 2)

    def test_master_of_barbs_triggers_for_each_separate_damage_outside_a_spell(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(MASTER_OF_BARBS), bear]
        game.damage(b, 1)
        game.damage(b, 1)
        run_stack(game)
        self.assertEqual(game.power(bear), 4)

    def test_gev_gives_entering_creatures_a_counter_per_opponent_who_lost_life(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(GEV)]
        b.life_lost_turn = c.life_lost_turn = game.turn
        b.life_lost_amount = c.life_lost_amount = 1
        bear = Permanent(BEAR)
        game._enter(a, bear)
        self.assertEqual(bear.counters.get("+1/+1"), 2)

    def test_gev_gives_none_when_no_opponent_lost_life(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(GEV)]
        b.life_lost_turn = game.turn - 1  # last turn
        bear = Permanent(BEAR)
        game._enter(a, bear)
        self.assertEqual(bear.counters.get("+1/+1"), None)

    def test_ingris_each_attacker_deals_1_damage_to_each_opponent(self):
        game, _ = table3(attack_all)
        a, b, c = game.seats
        a.battlefield = [Permanent(INGRIS, sick=True), Permanent(LEECH)]  # only the Leech attacks
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual((b.life, c.life), (39, 39))
        self.assertEqual(a.life, 42)  # the Leech dealt it: its lifelink

    def test_rockface_village_pumps_a_lizard_but_not_a_bear(self):
        game, _ = table3(pick("Lizard"))
        a = game.seats[0]
        lizard, bear = Permanent(LIZARD), Permanent(BEAR)
        a.battlefield = [Permanent(ROCKFACE_VILLAGE), lizard, bear] + lands(1)
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Rockface Village")))
        run_stack(game)
        self.assertEqual((game.power(lizard), game.has_keyword(lizard, "haste"), game.power(bear)), (2, True, 2))
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        a.battlefield = [Permanent(ROCKFACE_VILLAGE), Permanent(BEAR)] + lands(1)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE + "Rockface Village")], [])


if __name__ == "__main__":
    unittest.main()
