import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Attack
from infernal_machine.effects import attached_abilities, static_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_combat import BEAR
from tests.test_mass_effects import table3


def creature(name, text="", types="Creature — Bear", colors=(), power="2", toughness="2"):
    return Card(name=name, type_line=types, oracle_text=text, colors=colors, power=power, toughness=toughness)


LIEGE = REAL["Balefire Liege"]
RED_BEAR = creature("Red Bear", colors=("R",))
GREEN_BEAR = creature("Green Bear", colors=("G",))
SHAMAN = REAL["Rageblood Shaman"]
MINOTAUR = creature("Minotaur", types="Token Creature — Minotaur", colors=("R",), power="1", toughness="1")
MOUND = REAL["Blight Mound"]
PEST = creature("Pest", types="Token Creature — Pest", colors=("B", "G"), power="1", toughness="1")
STORM_KILN = REAL["Storm-Kiln Artist"]
WIGHT = REAL["Wight of the Reliquary"]
SPIRITDANCER = REAL["Kor Spiritdancer"]
REVERIE = REAL["Sage's Reverie"]
BLESSING = REAL["Pacifism"]
IMPETUS = REAL["Ghoulish Impetus"]
MARTIAL = REAL["Martial Impetus"]
TRINKET = Card(name="Trinket", type_line="Artifact")
GRAVE_BEAR = creature("Grave Bear")


class ParseTests(unittest.TestCase):
    def test_color_and_tribe_filters(self):
        red, white = static_abilities(LIEGE)
        self.assertEqual((red.color, red.other, red.modifier.power), ("R", True, 1))
        self.assertEqual(white.color, "W")
        [minotaurs] = static_abilities(SHAMAN)
        self.assertEqual((minotaurs.subtype, minotaurs.other, minotaurs.modifier.keywords), ("Minotaur", True, frozenset({"trample"})))
        [pests] = static_abilities(MOUND)
        self.assertEqual((pests.subtype, pests.attacking, pests.modifier.keywords), ("Pest", True, frozenset({"menace"})))

    def test_scaling(self):
        self.assertEqual(static_abilities(STORM_KILN)[0].per, ("permanent", "artifact"))
        self.assertEqual(static_abilities(WIGHT)[0].per, ("graveyard", "creature"))
        self.assertEqual(static_abilities(SPIRITDANCER)[0].per, ("auras_on_it", ""))
        self.assertEqual(attached_abilities(REVERIE)[0].per, ("auras_on_creatures", ""))

    def test_goaded(self):
        [buff] = attached_abilities(IMPETUS)
        self.assertEqual((buff.goaded, buff.modifier.keywords, buff.modifier.power), (True, frozenset({"deathtouch"}), 1))
        self.assertTrue(attached_abilities(MARTIAL)[0].goaded)

    def test_the_report_no_longer_lists_these_lines(self):
        for card in (LIEGE, SHAMAN, MOUND, STORM_KILN, WIGHT, SPIRITDANCER, REVERIE, IMPETUS, MARTIAL):
            self.assertEqual(unsupported_lines(card), [], card.name)


class FilterTests(unittest.TestCase):
    def test_other_red_creatures_only(self):
        game, _ = table3()
        a = game.seats[0]
        liege, red, green = Permanent(LIEGE), Permanent(RED_BEAR), Permanent(GREEN_BEAR)
        a.battlefield = [liege, red, green]
        self.assertEqual((game.power(liege), game.power(red), game.power(green)), (2, 3, 2))

    def test_only_your_own_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(LIEGE)]
        theirs = Permanent(RED_BEAR)
        b.battlefield = [theirs]
        self.assertEqual(game.power(theirs), 2)

    def test_a_tribe_gets_the_bonus_and_keywords(self):
        game, _ = table3()
        a = game.seats[0]
        minotaur, bear = Permanent(MINOTAUR), Permanent(BEAR)
        a.battlefield = [Permanent(SHAMAN), minotaur, bear]
        self.assertEqual((game.power(minotaur), game.power(bear)), (2, 2))
        self.assertTrue(game.has_keyword(minotaur, "trample"))
        self.assertFalse(game.has_keyword(bear, "trample"))

    def test_attacking_pests_only_while_attacking(self):
        game, _ = table3()
        a, b, _ = game.seats
        pest = Permanent(PEST)
        a.battlefield = [Permanent(MOUND), pest]
        self.assertEqual(game.power(pest), 1)
        game.combat.attacks.append(Attack(pest, a, b))
        self.assertEqual(game.power(pest), 2)
        self.assertTrue(game.has_keyword(pest, "menace"))


class ScalingTests(unittest.TestCase):
    def test_per_artifact(self):
        game, _ = table3()
        a = game.seats[0]
        artist = Permanent(STORM_KILN)
        a.battlefield = [artist]
        self.assertEqual(game.power(artist), 2)
        a.battlefield += [Permanent(TRINKET), Permanent(TRINKET)]
        self.assertEqual((game.power(artist), game.toughness(artist)), (4, 2))

    def test_per_creature_card_in_your_graveyard(self):
        game, _ = table3()
        a = game.seats[0]
        wight = Permanent(WIGHT)
        a.battlefield = [wight]
        a.graveyard = [GRAVE_BEAR, GRAVE_BEAR, TRINKET]
        self.assertEqual((game.power(wight), game.toughness(wight)), (4, 4))  # a 2/2 with two creature cards

    def test_per_aura_attached_to_it(self):
        game, _ = table3()
        a, b, _ = game.seats
        dancer = Permanent(SPIRITDANCER)
        a.battlefield = [dancer, Permanent(BLESSING, attached_to=dancer)]
        b.battlefield = [Permanent(BLESSING, attached_to=dancer)]  # an opponent's Aura counts too
        self.assertEqual((game.power(dancer), game.toughness(dancer)), (4, 6))

    def test_auras_you_control_on_creatures(self):
        game, _ = table3()
        a = game.seats[0]
        bear, other = Permanent(BEAR), Permanent(BEAR)
        reverie = Permanent(REVERIE, attached_to=bear)
        a.battlefield = [bear, other, reverie, Permanent(BLESSING, attached_to=other)]
        self.assertEqual(game.power(bear), 4)  # itself and the other Aura: +2


class GoadTests(unittest.TestCase):
    def test_an_aura_goads_for_its_controller(self):
        game, _ = table3()
        a, b, _ = game.seats
        victim = Permanent(BEAR)
        b.battlefield = [victim]
        self.assertIsNone(game.goader_of(victim))
        a.battlefield = [Permanent(MARTIAL, attached_to=victim)]
        self.assertIs(game.goader_of(victim), a)
        self.assertEqual(game.power(victim), 3)

    def test_a_goaded_creature_attacks_someone_other_than_the_goader(self):
        game, _ = table3()
        a, b, c = game.seats
        victim = Permanent(BEAR)
        b.battlefield = [victim]
        a.battlefield = [Permanent(MARTIAL, attached_to=victim)]
        game.combat.declare_attackers(b)
        [attack] = game.combat.attacks
        self.assertIs(attack.defender, c)

    def test_the_effect_of_goad_still_works(self):
        game, _ = table3()
        a, b, _ = game.seats
        victim = Permanent(BEAR, goaded_by=a)
        b.battlefield = [victim]
        self.assertIs(game.goader_of(victim), a)


if __name__ == "__main__":
    unittest.main()
