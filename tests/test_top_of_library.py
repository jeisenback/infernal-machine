import dataclasses
import unittest

from infernal_machine.effects import top_of_library
from infernal_machine.game import CAST_TOP, PLAY_TOP, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, lands, pick, real, run_stack, table

COURSER = real("Courser of Kruphix", "{1}{G}{G}", "Enchantment Creature — Centaur",
               "Play with the top card of your library revealed.\nYou may play lands from the top of your library.\n"
               "Landfall — Whenever a land you control enters, you gain 1 life.", "2", "4")
FUTURE_SIGHT = real("Future Sight", "{2}{U}{U}{U}", "Enchantment",
                    "Play with the top card of your library revealed.\nYou may play lands and cast spells from the top of your library.")
FORGE = real("Mystic Forge", "{4}", "Artifact",
             "You may look at the top card of your library any time.\nYou may cast artifact spells and colorless spells from the top of your library.\n"
             "{T}, Pay 1 life: Exile the top card of your library.")
REALMWALKER = real("Realmwalker", "{2}{G}", "Creature — Shapeshifter",
                   "Changeling (This card is every creature type.)\nAs this creature enters, choose a creature type.\n"
                   "You may look at the top card of your library any time.\nYou may cast creature spells of the chosen type from the top of your library.",
                   "2", "3")
CHIP = real("The Reality Chip", "{1}{U}", "Legendary Artifact Creature — Equipment Jellyfish",
            "You may look at the top card of your library any time.\nAs long as The Reality Chip is attached to a creature, you may play lands "
            "and cast spells from the top of your library.\nReconfigure {2}{U} ({2}{U}: Attach to target creature you control; or unattach from a "
            "creature. Reconfigure only as a sorcery. While attached, this isn't a creature.)", "0", "4")
GLARB = real("Glarb, Calamity's Augur", "{B}{G}{U}", "Legendary Creature — Frog Wizard Noble",
             "Deathtouch\nYou may look at the top card of your library any time.\nYou may play lands and cast spells with mana value 4 or greater "
             "from the top of your library.\n{T}: Surveil 2.", "2", "4")
GOBLIN = real("Test Goblin", "{1}{R}", "Creature — Goblin", "", "1", "1")
ELF = real("Test Elf", "{1}{G}", "Creature — Elf", "", "1", "1")
RELIC = real("Test Relic", "{2}", "Artifact", "")
BIG = dataclasses.replace(BEAR, name="Big Bear", mana_cost="{3}{G}", cmc=4.0)
SMALL = dataclasses.replace(BEAR, name="Small Bear", mana_cost="{1}{G}", cmc=2.0)
GREEN_BEAR = dataclasses.replace(BEAR, name="Green Bear", mana_cost="{1}{G}", colors=("G",))


def actions(permanents, top, mana=6, lands_played=0):
    game, _, _ = table(pick("Pass"))
    a = game.seats[0]
    a.battlefield = lands(mana) + [Permanent(c) if not isinstance(c, Permanent) else c for c in permanents]
    a.library = [top, FOREST]
    a.lands_played = lands_played
    return game, a, [x for x in game.legal_actions(a) if x.startswith((PLAY_TOP, CAST_TOP))]


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (COURSER, FUTURE_SIGHT, FORGE, REALMWALKER, CHIP, GLARB):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_what_each_permits(self):
        self.assertEqual((top_of_library(COURSER).lands, top_of_library(COURSER).spells), ("any", ()))
        self.assertEqual(top_of_library(FORGE).spells, ("artifact", "colorless"))
        self.assertEqual(top_of_library(GLARB).spells, ("with mana value 4 or greater",))
        self.assertTrue(top_of_library(CHIP).attached)
        self.assertIsNone(top_of_library(BEAR))

    def test_a_line_naming_something_else_is_not_understood(self):
        odd = real("Odd Seer", "{2}", "Artifact", "You may play lands from the top of your library if you control a Wizard.")
        self.assertNotEqual(unsupported_lines(odd), [])


class LandsTests(unittest.TestCase):
    def test_a_land_on_top_may_be_played(self):
        self.assertEqual(actions([COURSER], FOREST)[2], [PLAY_TOP + "Forest"])

    def test_a_spell_on_top_is_not_offered_to_a_lands_only_permission(self):
        self.assertEqual(actions([COURSER], SMALL)[2], [])

    def test_no_land_drop_left_means_no_play(self):
        self.assertEqual(actions([COURSER], FOREST, lands_played=1)[2], [])


class SnowTests(unittest.TestCase):
    SEER = real("Snow Seer", "{2}{G}", "Snow Creature — Elf", "You may play snow lands and cast snow spells from the top of your library.", "1", "1")

    def test_only_snow_lands_and_spells(self):
        snow_land = real("Snow-Covered Forest", "", "Basic Snow Land — Forest", "{T}: Add {G}.")
        snow_spell = dataclasses.replace(SMALL, name="Snow Bear", type_line="Snow Creature — Bear")
        self.assertEqual(actions([self.SEER], snow_land)[2], [PLAY_TOP + "Snow-Covered Forest"])
        self.assertEqual(actions([self.SEER], FOREST)[2], [])
        self.assertEqual(actions([self.SEER], snow_spell)[2], [CAST_TOP + "Snow Bear"])
        self.assertEqual(actions([self.SEER], SMALL)[2], [])


class SpellsTests(unittest.TestCase):
    def test_any_spell_may_be_cast_if_it_can_be_paid(self):
        self.assertEqual(actions([FUTURE_SIGHT], SMALL)[2], [CAST_TOP + "Small Bear"])
        self.assertEqual(actions([FUTURE_SIGHT], SMALL, mana=1)[2], [], "can't pay for it")

    def test_it_is_not_offered_without_the_permanent(self):
        self.assertEqual(actions([], SMALL)[2], [])

    def test_artifact_and_colorless_spells_only(self):
        self.assertEqual(actions([FORGE], RELIC)[2], [CAST_TOP + "Test Relic"])
        self.assertEqual(actions([FORGE], BEAR)[2], [CAST_TOP + "Bear"], "Bear has no color")
        self.assertEqual(actions([FORGE], GREEN_BEAR)[2], [])

    def test_only_the_chosen_type(self):
        walker = Permanent(REALMWALKER, chosen_type="Goblin")
        self.assertEqual(actions([walker], GOBLIN)[2], [CAST_TOP + "Test Goblin"])
        self.assertEqual(actions([walker], ELF)[2], [])

    def test_only_while_attached(self):
        chip = Permanent(CHIP)
        self.assertEqual(actions([chip], SMALL)[2], [])
        host = Permanent(BEAR)
        self.assertEqual(actions([host, Permanent(CHIP, attached_to=host)], SMALL)[2], [CAST_TOP + "Small Bear"])

    def test_a_mana_value_floor(self):
        self.assertEqual(actions([GLARB], BIG)[2], [CAST_TOP + "Big Bear"])
        self.assertEqual(actions([GLARB], SMALL)[2], [])
        self.assertEqual(actions([GLARB], FOREST)[2], [PLAY_TOP + "Forest"], "lands have no floor")


class PlayingTests(unittest.TestCase):
    def play(self, permanents, top, choose):
        game, _, _ = table(pick(choose))
        a = game.seats[0]
        a.battlefield = lands(6) + [Permanent(c) for c in permanents]
        a.library = [top, FOREST, FOREST]
        game.step, game.active = "main1", 0
        game._priority_round(a)
        run_stack(game)
        return game, a

    def test_playing_the_land_takes_it_off_the_library_and_triggers_landfall(self):
        game, a = self.play([COURSER], FOREST, PLAY_TOP)
        self.assertEqual((len(a.library), a.lands_played, a.life), (2, 1, 41))
        self.assertEqual(sum(p.card.name == "Forest" for p in a.battlefield), 1)

    def test_casting_the_spell_takes_it_off_the_library_and_it_resolves(self):
        game, a = self.play([FUTURE_SIGHT], SMALL, CAST_TOP)
        self.assertEqual(len(a.library), 2)
        self.assertEqual(sum(p.card.name == "Small Bear" for p in a.battlefield), 1)
        self.assertEqual(len(a.cast_log), 1)


if __name__ == "__main__":
    unittest.main()
