"""Damping Sphere: "If a land is tapped for two or more mana, it produces {C} instead of any other type and amount." and "Each spell a
player casts costs {1} more to cast for each other spell that player has cast this turn." Sunspine Lynx: "Players can't gain life." and
"When this creature enters, it deals damage to each player equal to the number of nonbasic lands that player controls." """

import dataclasses
import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, ELF, FOREST, OGRE, enter, real, run_stack, table3

SPHERE = real("Damping Sphere", "{2}", "Artifact", "If a land is tapped for two or more mana, it produces {C} instead of any other type and "
              "amount.\nEach spell a player casts costs {1} more to cast for each other spell that player has cast this turn.")
LYNX = real("Sunspine Lynx", "{2}{R}{R}", "Creature — Elemental Cat", "Players can't gain life.\nDamage can't be prevented.\nWhen this "
            "creature enters, it deals damage to each player equal to the number of nonbasic lands that player controls.", "5", "4",
            colors=("R",))


def land(name, type_line, text, mana):
    return dataclasses.replace(real(name, "", type_line, text), produced_mana=mana)


TOMB = land("Ancient Tomb", "Land", "{T}: Add {C}{C}. This land deals 2 damage to you.", ("C",))
CRADLE = land("Gaea's Cradle", "Legendary Land", "{T}: Add {G} for each creature you control.", ("G",))
TOWER = land("Urza's Tower", "Land — Urza's Tower", "{T}: Add {C}. If you control an Urza's Mine and an Urza's Power-Plant, add {C}{C}{C} "
             "instead.", ("C",))
MINE = land("Urza's Mine", "Land — Urza's Mine", "{T}: Add {C}. If you control an Urza's Power-Plant and an Urza's Tower, add {C}{C} "
            "instead.", ("C",))
PLANT = land("Urza's Power Plant", "Land — Urza's Power-Plant", "{T}: Add {C}. If you control an Urza's Mine and an Urza's Tower, add "
             "{C}{C} instead.", ("C",))
ARCHDRUID = dataclasses.replace(real("Elvish Archdruid", "{1}{G}{G}", "Creature — Elf Druid", "Other Elf creatures you control get "
                                     "+1/+1.\n{T}: Add {G} for each Elf you control.", "2", "2", colors=("G",)), produced_mana=("G",))
FIND_THE_PATH = real("Find the Path", "{2}{G}", "Enchantment — Aura", "Enchant land\nWhen this Aura enters, venture into the dungeon. (Enter "
                     "the first room or advance to the next room.)\nEnchanted land has \"{T}: Add {G}{G}.\"", colors=("G",))


def spell(cost):
    return Card(name="Thing", mana_cost="{%d}" % cost, cmc=float(cost), type_line="Artifact")


def most_mana(battlefield, damped):
    """The most generic mana seat 0 can pay with `battlefield`, with or without a Damping Sphere."""
    game, _ = table3()
    a = game.seats[0]
    a.battlefield = list(battlefield) + ([Permanent(SPHERE)] if damped else [])
    return max(n for n in range(8) if n == 0 or game._payment(a, spell(n)) is not None)


class DampingSphereTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        self.assertEqual([unsupported_lines(SPHERE), unsupported_lines(LYNX)], [[], []])

    def test_ancient_tomb_makes_one_colorless(self):
        self.assertEqual([most_mana([Permanent(TOMB)], d) for d in (False, True)], [2, 1])

    def test_gaeas_cradle_makes_one_colorless(self):
        board = [Permanent(CRADLE), Permanent(BEAR), Permanent(OGRE), Permanent(ELF)]
        self.assertEqual([most_mana(board, d) for d in (False, True)], [3, 1])

    def test_a_land_tapped_for_one_mana_keeps_its_color(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(CRADLE), Permanent(BEAR), Permanent(SPHERE)]
        self.assertIsNotNone(game._payment(a, Card(name="Green", mana_cost="{G}", cmc=1.0, type_line="Artifact")))

    def test_the_urza_lands_make_one_each(self):
        board = [Permanent(TOWER), Permanent(MINE), Permanent(PLANT)]
        self.assertEqual([most_mana(board, d) for d in (False, True)], [7, 3])

    def test_a_land_granted_two_mana_by_an_aura_makes_one(self):
        forest = Permanent(FOREST)
        path = Permanent(FIND_THE_PATH)
        path.attached_to = forest
        self.assertEqual([most_mana([forest, path], d) for d in (False, True)], [2, 1])

    def test_a_creature_that_makes_several_mana_is_not_a_land(self):
        board = [Permanent(ARCHDRUID), Permanent(ELF), Permanent(ELF)]
        self.assertEqual([most_mana(board, d) for d in (False, True)], [3, 3])

    def test_each_other_spell_this_turn_costs_one_more(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.battlefield = [Permanent(SPHERE)]
        a.cast_log = [(game.turn, BEAR), (game.turn, OGRE), (game.turn - 1, OGRE)]
        self.assertEqual((game.caster.cost_increase(a, BEAR), game.caster.cost_increase(b, BEAR)), (2, 0))


class SunspineLynxTests(unittest.TestCase):
    def test_it_deals_damage_for_each_nonbasic_land(self):
        game, _ = table3()
        a, b, c = game.seats
        b.battlefield = [Permanent(TOMB), Permanent(CRADLE), Permanent(FOREST)]
        c.battlefield = [Permanent(FOREST)]
        lives = (a.life, b.life, c.life)
        enter(game, a, LYNX)
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (lives[0], lives[1] - 2, lives[2]))

    def test_no_player_gains_life(self):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        life = b.life
        game.change_life(b, 3)
        self.assertEqual(b.life, life + 3)
        a.battlefield = [Permanent(LYNX)]
        game.change_life(b, 3)
        game.change_life(b, -1)
        self.assertEqual(b.life, life + 2)


if __name__ == "__main__":
    unittest.main()
