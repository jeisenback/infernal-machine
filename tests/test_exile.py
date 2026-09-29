import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Destroy, Exile, ExileGraveyard, spell_effects
from infernal_machine.game import CAST, COMMAND_ZONE_PROMPT, Permanent
from tests.test_effects import BEAR, FOREST, lands, pick, table
from tests.test_triggers import MARTYR

SWORDS = Card(name="Swords to Plowshares", mana_cost="{W}", type_line="Instant",
              oracle_text="Exile target creature. Its controller gains life equal to its power.")
PATH = Card(name="Path to Exile", mana_cost="{W}", type_line="Instant",
            oracle_text="Exile target creature. Its controller may search their library for a basic land card, "
                        "put that card onto the battlefield tapped, then shuffle.")
CRYPT = Card(name="Tormod's Crypt", mana_cost="{0}", type_line="Artifact",
             oracle_text="{T}, Sacrifice Tormod's Crypt: Exile target player's graveyard.")
BANISHER = Card(name="Banisher", mana_cost="{2}{W}", type_line="Creature — Human", power="2", toughness="2",
                oracle_text="When this creature enters, exile target nonland permanent an opponent controls.")
EXORCIST = Card(name="Exorcist", mana_cost="{W}", type_line="Instant",
                oracle_text="Exile target artifact or enchantment you control.")
OGRE = Card(name="Ogre", mana_cost="{3}", type_line="Creature — Ogre", power="3", toughness="3")
COMMANDER = Card(name="Omnath", mana_cost="{G}", type_line="Legendary Creature — Elemental", power="4", toughness="4")


class ParseTests(unittest.TestCase):
    def test_templates(self):
        self.assertEqual(spell_effects(SWORDS)[0], Exile("creature"))
        self.assertEqual(len(spell_effects(PATH)), 2)
        self.assertEqual(spell_effects(Card(name="Wipe", oracle_text="Exile target player's graveyard.")), [ExileGraveyard()])
        murder = Card(name="Murder", oracle_text="Destroy target creature an opponent controls.")
        self.assertEqual(spell_effects(murder), [Destroy("creature an opponent controls")])

    def test_names_only_replaced_as_whole_words(self):
        # A card named "Ex" must not turn "Exile" into "CARDNAMEile".
        self.assertEqual(spell_effects(Card(name="Ex", oracle_text="Exile target creature.")), [Exile("creature")])


class ExileTests(unittest.TestCase):
    def test_swords_to_plowshares(self):
        game, _, _ = table(pick(CAST, "Ogre"))
        game.seats[0].hand = [SWORDS]
        game.seats[0].battlefield = lands(1)
        game.seats[1].battlefield = [Permanent(OGRE)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].battlefield, [])
        self.assertEqual(game.seats[1].exile, [OGRE])
        self.assertEqual(game.seats[1].graveyard, [])
        self.assertEqual(game.seats[1].life, 43)  # its controller gains life, not the caster

    def test_path_to_exile(self):
        game, _, _ = table(pick(CAST, "Ogre"), pick("Yes"))
        game.seats[0].hand = [PATH]
        game.seats[0].battlefield = lands(1)
        game.seats[1].battlefield = [Permanent(OGRE)]
        game.seats[1].library = [BEAR, FOREST]
        game._priority_round(game.seats[0])
        fetched = game.seats[1].battlefield[-1]
        self.assertEqual((fetched.card, fetched.tapped), (FOREST, True))

    def test_path_search_is_optional(self):
        game, _, _ = table(pick(CAST, "Ogre"), pick("No"))
        game.seats[0].hand = [PATH]
        game.seats[0].battlefield = lands(1)
        game.seats[1].battlefield = [Permanent(OGRE)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].battlefield, [])

    def test_exiled_creatures_do_not_die(self):
        game, _, _ = table(pick(CAST, "Martyr"))
        game.seats[0].hand = [SWORDS]
        game.seats[0].battlefield = lands(1) + [Permanent(MARTYR)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].life, 41)  # Swords' 1 life, but no "dies" trigger for 3

    def test_commander_can_go_to_command_zone_from_exile(self):
        game, _, b = table(pick(CAST, "Omnath"), pick("Command zone"))
        game.seats[0].hand = [SWORDS]
        game.seats[0].battlefield = lands(1)
        game.seats[1].commander_names = {"Omnath"}
        game.seats[1].battlefield = [Permanent(COMMANDER)]
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[1].command_zone, game.seats[1].exile), ([COMMANDER], []))
        self.assertIn((COMMAND_ZONE_PROMPT, ["Command zone", "Exile"]), b.prompts)

    def test_exile_graveyard_from_an_ability(self):
        game, _, _ = table(pick("Activate", "Player: B"))
        game.seats[0].battlefield = [Permanent(CRYPT)]
        game.seats[1].graveyard = [BEAR, OGRE]
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[1].graveyard, game.seats[1].exile), ([], [BEAR, OGRE]))
        self.assertEqual(game.seats[0].graveyard, [CRYPT])

    def test_exile_trigger_targets_only_opponents(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [BANISHER]
        game.seats[0].battlefield = lands(3) + [Permanent(OGRE)]
        game.seats[1].battlefield = [Permanent(OGRE), Permanent(FOREST)]
        options = [label for label, _ in game.target_options("nonland permanent an opponent controls", game.seats[0])]
        self.assertEqual(options, ["Ogre 3/3 (seat 1, #1)"])
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].exile, [OGRE])
        self.assertEqual([p.card for p in game.seats[1].battlefield], [FOREST])

    def test_you_control_qualifier(self):
        game, _, _ = table()
        mine, theirs = Permanent(Card(name="Relic", type_line="Artifact")), Permanent(Card(name="Relic", type_line="Artifact"))
        game.seats[0].battlefield = [mine] + lands(1)
        game.seats[1].battlefield = [theirs]
        game.seats[0].hand = [EXORCIST]
        self.assertEqual([t for _, t in game.target_options("artifact or enchantment you control", game.seats[0])], [mine])


if __name__ == "__main__":
    unittest.main()
