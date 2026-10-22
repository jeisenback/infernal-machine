"""Mana abilities given to your artifacts (issue #80): Goldspan Dragon's Treasures and Galazeth Prismari's artifacts.

Lines are the cards' own Oracle text from Scryfall (their other lines are not written here).
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import COURSEWORK, RELIC, table3

GOLDSPAN = Card(name="Goldspan Dragon", mana_cost="{3}{R}{R}", type_line="Creature — Dragon", power="4", toughness="4",
                oracle_text="Flying, haste\nTreasures you control have \"{T}, Sacrifice this artifact: Add two mana of any one "
                            "color.\"")
GALAZETH = Card(name="Galazeth Prismari", mana_cost="{2}{U}{R}", type_line="Legendary Creature — Elder Dragon", power="3",
                toughness="4", oracle_text="Flying\nArtifacts you control have \"{T}: Add one mana of any color. Spend this mana "
                                           "only to cast an instant or sorcery spell.\"")
TREASURE = Card(name="Treasure", type_line="Token Artifact — Treasure",
                oracle_text="{T}, Sacrifice this artifact: Add one mana of any color.")
SOL = Card(name="Sol Ring", mana_cost="{1}", type_line="Artifact", oracle_text="{T}: Add {C}{C}.")
SORCERY = Card(name="Ritual", mana_cost="{1}{R}", cmc=2.0, type_line="Sorcery")
CREATURE = Card(name="Bear", mana_cost="{1}{G}", cmc=2.0, type_line="Creature — Bear", power="2", toughness="2")


def table(*mine, theirs=()):
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield = [Permanent(c) for c in mine]
    b.battlefield = [Permanent(c) for c in theirs]
    return game, a


class ParseTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        self.assertEqual(unsupported_lines(GOLDSPAN), [])
        self.assertEqual(unsupported_lines(GALAZETH), [])


class GoldspanTests(unittest.TestCase):
    def test_one_treasure_pays_two_mana(self):
        game, a = table(GOLDSPAN, TREASURE)
        self.assertIsNotNone(game._payment(a, SORCERY))

    def test_without_the_dragon_one_treasure_is_one_mana(self):
        game, a = table(TREASURE)
        self.assertIsNone(game._payment(a, SORCERY))

    def test_the_treasure_is_sacrificed_when_used(self):
        game, a = table(GOLDSPAN, TREASURE)
        game._spend_mana(a, game._payment(a, SORCERY))
        self.assertEqual([p.card.name for p in a.battlefield], ["Goldspan Dragon"])

    def test_other_artifacts_are_not_treasures(self):
        game, a = table(GOLDSPAN, RELIC)
        self.assertIsNone(game._payment(a, SORCERY))

    def test_a_dragon_that_lost_its_abilities_gives_nothing(self):
        game, a = table(GOLDSPAN, TREASURE)
        a.battlefield.append(Permanent(COURSEWORK, attached_to=a.battlefield[0]))
        self.assertIsNone(game._payment(a, SORCERY))

    def test_an_opponents_dragon_does_not_help(self):
        game, a = table(TREASURE, theirs=[GOLDSPAN])
        self.assertIsNone(game._payment(a, SORCERY))


class GalazethTests(unittest.TestCase):
    def test_an_artifact_pays_for_an_instant_or_sorcery(self):
        game, a = table(GALAZETH, RELIC, Card(name="Idol", type_line="Artifact"))
        self.assertIsNotNone(game._payment(a, SORCERY))

    def test_but_not_for_a_creature_spell(self):
        game, a = table(GALAZETH, RELIC, Card(name="Idol", type_line="Artifact"))
        self.assertIsNone(game._payment(a, CREATURE))

    def test_without_galazeth_the_artifacts_make_nothing(self):
        game, a = table(RELIC, Card(name="Idol", type_line="Artifact"))
        self.assertIsNone(game._payment(a, SORCERY))

    def test_an_opponents_galazeth_does_not_help(self):
        game, a = table(RELIC, Card(name="Idol", type_line="Artifact"), theirs=[GALAZETH])
        self.assertIsNone(game._payment(a, SORCERY))

    def test_an_artifact_with_its_own_mana_ability_keeps_it(self):
        game, a = table(GALAZETH, SOL)
        self.assertIsNotNone(game._payment(a, Card(name="Golem", mana_cost="{2}", cmc=2.0, type_line="Artifact Creature — Golem",
                                                   power="2", toughness="2")))  # Sol Ring's {C}{C}, for any spell
