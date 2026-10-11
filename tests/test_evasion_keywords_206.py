"""Evasion keywords (#206, #207): fear, intimidate, horsemanship, the five landwalks and a printed "can't be blocked"."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Combat
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_mass_effects import table3


def creature(name, text="", colors=(), types="Creature — Bear", power=2):
    return Card(name=name, mana_cost="{1}", type_line=types, oracle_text=text, power=str(power), toughness="2", colors=colors)


def land(name, types):
    return Card(name=name, type_line=types, produced_mana=("C",))


class EvasionTests(unittest.TestCase):
    def can_block(self, attacker, blocker, defender_lands=()):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(attacker)]
        b.battlefield = [Permanent(blocker)] + [Permanent(c) for c in defender_lands]
        game.combat = Combat(game)
        return game.combat._can_block(b.battlefield[0], a.battlefield[0])

    def test_fear_is_blocked_only_by_artifact_and_black_creatures(self):
        fear = creature("Shade", "Fear", ("B",))
        self.assertFalse(self.can_block(fear, creature("Elf", colors=("G",))))
        self.assertFalse(self.can_block(fear, creature("Colorless")))
        self.assertTrue(self.can_block(fear, creature("Zombie", colors=("B",))))
        self.assertTrue(self.can_block(fear, creature("Golem", types="Artifact Creature — Golem")))

    def test_intimidate_is_blocked_by_artifacts_and_creatures_sharing_a_color(self):
        intimidate = creature("Rogue", "Intimidate", ("B", "R"))
        self.assertFalse(self.can_block(intimidate, creature("Elf", colors=("G",))))
        self.assertTrue(self.can_block(intimidate, creature("Imp", colors=("R",))))
        self.assertTrue(self.can_block(intimidate, creature("Golem", types="Artifact Creature — Golem")))
        self.assertFalse(self.can_block(creature("Ghost", "Intimidate"), creature("Colorless")))  # no color to share

    def test_horsemanship_is_blocked_only_by_horsemanship(self):
        rider = creature("Rider", "Horsemanship")
        self.assertFalse(self.can_block(rider, creature("Elf")))
        self.assertTrue(self.can_block(rider, creature("Other Rider", "Horsemanship")))

    def test_landwalk_cannot_be_blocked_while_the_defender_has_that_land_type(self):
        for word, kind in (("Islandwalk", "Island"), ("Swampwalk", "Swamp"), ("Mountainwalk", "Mountain"),
                           ("Forestwalk", "Forest"), ("Plainswalk", "Plains")):
            with self.subTest(word):
                walker, elf = creature("Walker", word), creature("Elf")
                self.assertFalse(self.can_block(walker, elf, [land(kind, f"Basic Land — {kind}")]))
                self.assertTrue(self.can_block(walker, elf))
                other = "Forest" if kind != "Forest" else "Island"
                self.assertTrue(self.can_block(walker, elf, [land(other, f"Basic Land — {other}")]))

    def test_landwalk_counts_a_dual_land_of_that_type(self):
        self.assertFalse(self.can_block(creature("Walker", "Swampwalk"), creature("Elf"),
                                        [land("Watery Grave", "Land — Island Swamp")]))

    def test_landwalk_needs_a_land_not_just_the_word(self):
        self.assertTrue(self.can_block(creature("Walker", "Swampwalk"), creature("Elf"),
                                       [creature("Swamp Thing", types="Creature — Swamp Thing")]))

    def test_a_printed_cant_be_blocked_line(self):
        self.assertFalse(self.can_block(creature("Blade", "This creature can't be blocked."), creature("Elf")))
        self.assertTrue(self.can_block(creature("Plain"), creature("Elf")))


class ReportTests(unittest.TestCase):
    def test_the_keywords_and_the_line_are_supported(self):
        for text in ("Fear", "Intimidate", "Horsemanship", "Swampwalk", "Plainswalk", "Flying, islandwalk",
                     "Fear (This creature can't be blocked except by artifact creatures and/or black creatures.)",
                     "This creature can't be blocked."):
            with self.subTest(text):
                self.assertEqual(unsupported_lines(creature("Test", text)), [])

    def test_other_landwalks_are_still_reported(self):
        self.assertEqual(unsupported_lines(creature("Test", "Nonbasic landwalk")), ["Nonbasic landwalk"])


if __name__ == "__main__":
    unittest.main()
