"""Damage modifiers that name their source (CR 614.1): Torbran (a red source you control), Embermaw Hellion (another red source), Mechanized
Warfare (a red or artifact source), Calamity Bearer (a Giant), Valley Flamecaller (a Lizard, Mouse, Otter, or Raccoon), Pyromancer's Swath
(an instant or sorcery source), Fire Servant (a red instant or sorcery spell), Sulfuric Vapors (a red spell) and Thor (another source)."""

import unittest

from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import Table, pick, real, table3

TORBRAN = real("Torbran, Thane of Red Fell", "{1}{R}{R}{R}", "Legendary Creature — Dwarf Noble", "If a red source you control would deal "
               "damage to an opponent or a permanent an opponent controls, it deals that much damage plus 2 instead.", "2", "4", colors=("R",))
HELLION = real("Embermaw Hellion", "{3}{R}{R}", "Creature — Hellion", "Trample\nIf another red source you control would deal damage to a "
               "permanent or player, it deals that much damage plus 1 to that permanent or player instead.", "4", "5", colors=("R",))
WARFARE = real("Mechanized Warfare", "{1}{R}{R}", "Enchantment", "If a red or artifact source you control would deal damage to an opponent "
               "or a permanent an opponent controls, it deals that much damage plus 1 instead.", colors=("R",))
BEARER = real("Calamity Bearer", "{2}{R}{R}", "Creature — Giant Berserker", "If a Giant source you control would deal damage to a "
              "permanent or player, it deals double that damage to that permanent or player instead.", "3", "4", colors=("R",))
FLAMECALLER = real("Valley Flamecaller", "{2}{R}", "Creature — Lizard Warlock", "If a Lizard, Mouse, Otter, or Raccoon you control would "
                   "deal damage to a permanent or player, it deals that much damage plus 1 instead.", "3", "3", colors=("R",))
SWATH = real("Pyromancer's Swath", "{2}{R}", "Enchantment", "If an instant or sorcery source you control would deal damage to a permanent or "
             "player, it deals that much damage plus 2 to that permanent or player instead.\nAt the beginning of each end step, discard your hand.",
             colors=("R",))
SERVANT = real("Fire Servant", "{3}{R}{R}", "Creature — Elemental", "If a red instant or sorcery spell you control would deal damage, it "
               "deals double that damage instead.", "4", "3", colors=("R",))
VAPORS = real("Sulfuric Vapors", "{3}{R}", "Enchantment", "If a red spell would deal damage to a permanent or player, it deals that much "
              "damage plus 1 to that permanent or player instead.", colors=("R",))
THOR = real("Thor, Asgard's Avenger", "{2}{R}{R}", "Legendary Creature — God Warrior Hero", "Flying\nIf another source you control would "
            "deal damage to an opponent or a permanent an opponent controls, it deals that much damage plus 1 instead.", "4", "4", colors=("R",))
RED_OGRE = real("Red Ogre", "{2}{R}", "Creature — Ogre", "", "3", "3", colors=("R",))
BLUE_OGRE = real("Blue Ogre", "{2}{U}", "Creature — Ogre", "", "3", "3", colors=("U",))
HILL_GIANT = real("Hill Giant", "{3}{R}", "Creature — Giant", "", "3", "3", colors=("R",))
GOLEM = real("Golem", "{3}", "Artifact Creature — Golem", "", "3", "3")
RACCOON = real("Raccoon", "{1}{G}", "Creature — Raccoon", "", "2", "2", colors=("G",))
RED_BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.", colors=("R",))
BLUE_ZAP = real("Zap", "{U}", "Instant", "Zap deals 3 damage to any target.", colors=("U",))
WOUND = real("Wound", "{R}", "Sorcery", "Wound deals 3 damage to any target.", colors=("R",))


def setup(*cards, theirs=()):
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield = [Permanent(c) for c in cards]
    b.battlefield = [Permanent(c) for c in theirs]
    return game, a, b


def hit(game, target, source, amount=3):
    before = target.life
    game.damage(target, amount, source)
    return before - target.life


def cast_bolt(spell, mine=(), theirs=(), policy=None):
    t = Table(spell, mine=[Permanent(c) for c in mine], theirs=[Permanent(c) for c in theirs], n=1, policy=policy or pick("Player: B"))
    t.cast()
    return 40 - t.b.life


class DamageSourceTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (TORBRAN, HELLION, WARFARE, BEARER, FLAMECALLER, SWATH, SERVANT, VAPORS, THOR):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_red_source_you_control_to_an_opponent(self):
        game, a, b = setup(TORBRAN)
        red, blue = Permanent(RED_OGRE), Permanent(BLUE_OGRE)
        a.battlefield += [red, blue]
        self.assertEqual((hit(game, b, red), hit(game, b, blue), hit(game, a, red)), (5, 3, 3))  # not blue, not to its own controller
        self.assertEqual(cast_bolt(RED_BOLT, mine=[TORBRAN]), 5)  # a red spell is a red source
        self.assertEqual(cast_bolt(BLUE_ZAP, mine=[TORBRAN]), 3)
        self.assertEqual(cast_bolt(RED_BOLT, theirs=[TORBRAN]), 3)  # their Torbran does not help my Bolt

    def test_another_red_source_leaves_out_the_creature_itself(self):
        game, a, b = setup(HELLION)
        red = Permanent(RED_OGRE)
        a.battlefield.append(red)
        self.assertEqual((hit(game, b, red), hit(game, b, a.battlefield[0]), hit(game, a, red)), (4, 3, 4))  # any player or permanent

    def test_a_red_or_an_artifact_source_to_an_opponent(self):
        game, a, b = setup(WARFARE)
        red, golem, blue = Permanent(RED_OGRE), Permanent(GOLEM), Permanent(BLUE_OGRE)
        a.battlefield += [red, golem, blue]
        self.assertEqual((hit(game, b, red), hit(game, b, golem), hit(game, b, blue), hit(game, a, red)), (4, 4, 3, 3))

    def test_a_source_of_a_creature_type(self):
        game, a, b = setup(BEARER)
        giant, red = Permanent(HILL_GIANT), Permanent(RED_OGRE)
        a.battlefield += [giant, red]
        self.assertEqual((hit(game, b, giant), hit(game, b, red), hit(game, b, a.battlefield[0])), (6, 3, 6))  # Calamity Bearer is a Giant too

    def test_a_list_of_creature_types(self):
        game, a, b = setup(FLAMECALLER)
        raccoon, ogre = Permanent(RACCOON), Permanent(RED_OGRE)
        a.battlefield += [raccoon, ogre]
        self.assertEqual((hit(game, b, raccoon), hit(game, b, ogre), hit(game, b, a.battlefield[0])), (4, 3, 4))
        self.assertEqual(cast_bolt(RED_BOLT, mine=[FLAMECALLER]), 3)  # a spell is not a creature

    def test_an_instant_or_sorcery_source(self):
        game, a, b = setup(SWATH)
        ogre = Permanent(RED_OGRE)
        a.battlefield.append(ogre)
        self.assertEqual(hit(game, b, ogre), 3)
        self.assertEqual((cast_bolt(RED_BOLT, mine=[SWATH]), cast_bolt(WOUND, mine=[SWATH]), cast_bolt(BLUE_ZAP, mine=[SWATH])), (5, 5, 5))
        self.assertEqual(cast_bolt(RED_BOLT, theirs=[SWATH]), 3)

    def test_a_red_instant_or_sorcery_spell_you_control(self):
        game, a, b = setup(SERVANT)
        ogre = Permanent(RED_OGRE)
        a.battlefield.append(ogre)
        self.assertEqual(hit(game, b, ogre), 3)  # a creature is not a spell
        self.assertEqual((cast_bolt(RED_BOLT, mine=[SERVANT]), cast_bolt(WOUND, mine=[SERVANT]), cast_bolt(BLUE_ZAP, mine=[SERVANT])), (6, 6, 3))
        self.assertEqual(cast_bolt(RED_BOLT, theirs=[SERVANT]), 3)

    def test_a_red_spell_whoever_controls_it(self):
        self.assertEqual((cast_bolt(RED_BOLT, mine=[VAPORS]), cast_bolt(RED_BOLT, theirs=[VAPORS]), cast_bolt(BLUE_ZAP, mine=[VAPORS])), (4, 4, 3))
        game, a, b = setup(VAPORS)
        ogre = Permanent(RED_OGRE)
        a.battlefield.append(ogre)
        self.assertEqual(hit(game, b, ogre), 3)  # a creature is not a spell

    def test_another_source_you_control(self):
        game, a, b = setup(THOR)
        ogre = Permanent(BLUE_OGRE)
        a.battlefield.append(ogre)
        self.assertEqual((hit(game, b, ogre), hit(game, b, a.battlefield[0]), hit(game, a, ogre)), (4, 3, 3))
        self.assertEqual(cast_bolt(BLUE_ZAP, mine=[THOR]), 4)


if __name__ == "__main__":
    unittest.main()
