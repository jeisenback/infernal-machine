"""Mana that may be spent only on some spells (#214): "{T}: Add MANA. Spend this mana only to cast KIND spell(s)." for any kind the
filters read and any amount, with an "Activate only if" condition where the card has one. Each land or creature from its real Oracle
text; the spells they are asked to pay for are probes."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, real, table3

ALL = ("C", "W", "U", "B", "R", "G")
MAELSTROM = Card(name="Maelstrom of the Spirit Dragon", type_line="Land", produced_mana=ALL,
                 oracle_text="{T}: Add {C}.\n{T}: Add one mana of any color. Spend this mana only to cast a Dragon spell or an Omen spell.\n"
                             "{4}, {T}, Sacrifice this land: Search your library for a Dragon card, reveal it, put it into your hand, then shuffle.")
HAVEN = Card(name="Haven of the Spirit Dragon", type_line="Land", produced_mana=ALL,
             oracle_text="{T}: Add {C}.\n{T}: Add one mana of any color. Spend this mana only to cast a Dragon creature spell.\n"
                         "{2}, {T}, Sacrifice this land: Return target Dragon creature card or Ugin planeswalker card from your graveyard to your hand.")
TEMPLE = Card(name="Eldrazi Temple", type_line="Land", produced_mana=("C",),
              oracle_text="{T}: Add {C}.\n{T}: Add {C}{C}. Spend this mana only to cast colorless Eldrazi spells or activate abilities of "
                          "colorless Eldrazi.")
SHRINE = Card(name="Shrine of the Forsaken Gods", type_line="Land", produced_mana=("C",),
              oracle_text="{T}: Add {C}.\n{T}: Add {C}{C}. Spend this mana only to cast colorless spells. Activate only if you control seven "
                          "or more lands.")
COURTYARD = Card(name="Secluded Courtyard", type_line="Land", produced_mana=ALL,
                 oracle_text="As this land enters, choose a creature type.\n{T}: Add {C}.\n{T}: Add one mana of any color. Spend this mana "
                             "only to cast a creature spell of the chosen type or activate an ability of a creature source of the chosen type.")
RIVAZ = real("Rivaz of the Claw", "{1}{B}{R}", "Legendary Creature — Lizard Warlock",
             "Menace\n{T}: Add two mana in any combination of colors. Spend this mana only to cast Dragon creature spells.\n"
             "Once during each of your turns, you may cast a Dragon creature spell from your graveyard.\n"
             "Whenever you cast a Dragon creature spell from your graveyard, it gains \"When this creature dies, exile it.\"", "3", "3",
             colors=("B", "R"))

DRAGON = real("Dragon Whelp", "{R}", "Creature — Dragon", "", "2", "2", colors=("R",))
BIG_DRAGON = real("Big Dragon", "{R}{G}", "Creature — Dragon", "", "4", "4", colors=("R", "G"))
DRAGON_RITE = Card(name="Dragon Rite", mana_cost="{R}", cmc=1, type_line="Kindred Sorcery — Dragon", colors=("R",))
GOBLIN = real("Goblin", "{R}", "Creature — Goblin", "", "1", "1", colors=("R",))
BIG_GOBLIN = real("Big Goblin", "{R}{G}", "Creature — Goblin", "", "3", "3", colors=("R", "G"))
ELF = real("Elf", "{G}", "Creature — Elf", "", "1", "1", colors=("G",))
DRONE = Card(name="Eldrazi Drone", mana_cost="{2}", cmc=2, type_line="Creature — Eldrazi Drone", power="2", toughness="2")
GREEN_ELDRAZI = Card(name="Verdant Eldrazi", mana_cost="{2}", cmc=2, type_line="Creature — Eldrazi", power="2", toughness="2", colors=("G",))
ROCK = Card(name="Rock", mana_cost="{2}", cmc=2, type_line="Artifact")
SEVEN_ROCK = Card(name="Big Rock", mana_cost="{7}", cmc=7, type_line="Artifact")
EIGHT_ROCK = Card(name="Bigger Rock", mana_cost="{8}", cmc=8, type_line="Artifact")


def seat_with(*permanents):
    game, _ = table3(None)
    a = game.seats[0]
    a.battlefield = list(permanents)
    return game, a


def payable(game, a, card):
    return game._payment(a, card) is not None


class ParseTests(unittest.TestCase):
    def test_the_restricted_lines_are_read(self):
        for card in (MAELSTROM, TEMPLE, SHRINE, COURTYARD):
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertNotIn("{T}: Add one mana of any color. Spend this mana only to cast a Dragon creature spell.", unsupported_lines(HAVEN))
        self.assertNotIn("{T}: Add two mana in any combination of colors. Spend this mana only to cast Dragon creature spells.", unsupported_lines(RIVAZ))

    def test_a_restriction_the_filters_cannot_read_stays_unread(self):
        odd = Card(name="Odd Land", type_line="Land", produced_mana=ALL,
                   oracle_text="{T}: Add one mana of any color. Spend this mana only to cast kicked spells.")  # Castle Embereth's cousin
        self.assertEqual(len(unsupported_lines(odd)), 1)


class AnyColorForAKindTests(unittest.TestCase):
    def test_maelstrom_pays_for_a_dragon_spell_of_any_kind(self):
        game, a = seat_with(Permanent(MAELSTROM))
        self.assertTrue(payable(game, a, DRAGON))
        self.assertTrue(payable(game, a, DRAGON_RITE))

    def test_maelstrom_does_not_pay_for_a_goblin(self):
        game, a = seat_with(Permanent(MAELSTROM))
        self.assertFalse(payable(game, a, GOBLIN))

    def test_haven_pays_for_a_dragon_creature_only(self):
        game, a = seat_with(Permanent(HAVEN))
        self.assertTrue(payable(game, a, DRAGON))
        self.assertFalse(payable(game, a, DRAGON_RITE))

    def test_the_colorless_mana_still_pays_generic_costs(self):
        game, a = seat_with(Permanent(MAELSTROM))
        self.assertTrue(payable(game, a, Card(name="Pebble", mana_cost="{1}", cmc=1, type_line="Artifact")))


class TwoManaTests(unittest.TestCase):
    def test_eldrazi_temple_makes_two_for_a_colorless_eldrazi(self):
        game, a = seat_with(Permanent(TEMPLE))
        self.assertTrue(payable(game, a, DRONE))

    def test_not_for_a_colored_eldrazi_or_a_colorless_rock(self):
        game, a = seat_with(Permanent(TEMPLE))
        self.assertFalse(payable(game, a, GREEN_ELDRAZI))
        self.assertFalse(payable(game, a, ROCK))

    def test_rivaz_makes_two_of_any_colors_for_a_dragon_creature(self):
        game, a = seat_with(Permanent(RIVAZ))
        self.assertTrue(payable(game, a, BIG_DRAGON))
        self.assertFalse(payable(game, a, BIG_GOBLIN))
        self.assertFalse(payable(game, a, DRAGON_RITE))


class ConditionTests(unittest.TestCase):
    def test_the_shrine_makes_two_only_with_seven_lands(self):
        game, a = seat_with(Permanent(SHRINE), *(Permanent(FOREST) for _ in range(6)))  # seven lands: 6 + 2 = 8
        self.assertTrue(payable(game, a, EIGHT_ROCK))
        game, a = seat_with(Permanent(SHRINE), *(Permanent(FOREST) for _ in range(5)))  # six lands: 5 + 1 = 6, even though 5 + 2 would do
        self.assertFalse(payable(game, a, SEVEN_ROCK))


class ChosenTypeTests(unittest.TestCase):
    def test_the_courtyard_pays_for_a_creature_of_the_chosen_type(self):
        game, a = seat_with(Permanent(COURTYARD, chosen_type="Elf"))
        self.assertTrue(payable(game, a, ELF))
        self.assertFalse(payable(game, a, GOBLIN))


if __name__ == "__main__":
    unittest.main()
