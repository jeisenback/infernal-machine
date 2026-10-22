import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (DamageEach, DestroyAll, EachSacrifices, ExileAll,
                                      TargetSacrifices, spell_effects)
from infernal_machine.game import CAST, COMMAND_ZONE_PROMPT, SACRIFICE_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import (
    COMMANDER,
    DARKSTEEL,
    EFFECTS_BEAR as BEAR,
    EXILE_OGRE as OGRE,
    lands,
    MARTYR,
    PAWN,
    pick,
    RAISE,
    SOL_RING,
    table,
    table3,
    ZULAPORT,
)
from tests.real import REAL

WRATH = Card(name="Wrath of God", mana_cost="{2}{W}{W}", type_line="Sorcery",
             oracle_text="Destroy all creatures. They can't be regenerated.")
PYROCLASM = Card(name="Pyroclasm", mana_cost="{1}{R}", type_line="Sorcery",
                 oracle_text="Pyroclasm deals 2 damage to each creature.")
VORTEX = Card(name="Vortex", mana_cost="{1}{R}", type_line="Sorcery", oracle_text="Vortex deals 3 damage to each opponent.")
FLARE = REAL["Steam Blast"]
ARMAGEDDON = Card(name="Armageddon", mana_cost="{3}{W}", type_line="Sorcery", oracle_text="Destroy all lands.")
PURGE = REAL["Plague Wind"]
BANISH = Card(name="Banish All", mana_cost="{4}{W}", type_line="Sorcery", oracle_text="Exile all creatures.")
EDICT = REAL["Cruel Edict"]
TRIBUTE = Card(name="Tribute", mana_cost="{1}{B}", type_line="Sorcery", oracle_text="Each opponent sacrifices a creature.")
SWEEP = Card(name="Fleshbag", mana_cost="{1}{B}", type_line="Sorcery", oracle_text="Each player sacrifices a creature.")


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class ParseTests(unittest.TestCase):
    def test_templates(self):
        self.assertEqual(spell_effects(WRATH), [DestroyAll("creature", no_regen=True)])
        self.assertEqual(spell_effects(ARMAGEDDON), [DestroyAll("land")])
        self.assertEqual(spell_effects(PURGE), [DestroyAll("creature you don't control", no_regen=True)])
        self.assertEqual(spell_effects(BANISH), [ExileAll("creature")])
        self.assertEqual(spell_effects(PYROCLASM), [DamageEach(2, "all", None)])
        self.assertEqual(spell_effects(VORTEX), [DamageEach(3, None, "opponents")])
        self.assertEqual(spell_effects(FLARE), [DamageEach(2, "all", "all")])
        self.assertEqual(spell_effects(TRIBUTE), [EachSacrifices("opponent")])
        self.assertEqual(spell_effects(EDICT), [TargetSacrifices("opponent")])

    def test_x_and_kinds(self):
        card = Card(name="Blast", oracle_text="Blast deals X damage to each creature you don't control.")
        self.assertEqual(spell_effects(card), [DamageEach("X", "opponents", None)])
        both = Card(name="Rust", oracle_text="Destroy all artifacts and enchantments.")
        self.assertEqual(spell_effects(both), [DestroyAll("artifact or enchantment")])

    def test_variants_that_need_more_are_unsupported(self):
        for text in ("Destroy all creatures with a +1/+1 counter on them.", "Each opponent sacrifices a creature with the greatest power.",
                     "Destroy all creatures. Draw a card for each creature destroyed this way."):
            self.assertIsNone(spell_effects(Card(name="x", oracle_text=text)), text)

    def test_report(self):
        for card in (WRATH, PYROCLASM, VORTEX, ARMAGEDDON, TRIBUTE, EDICT):
            self.assertEqual(unsupported_lines(card), [], card.name)


class DestroyAllTests(unittest.TestCase):
    def test_wrath_destroys_every_creature_but_not_indestructible_or_artifacts(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [WRATH]
        game.seats[0].battlefield = lands(4) + [Permanent(BEAR), Permanent(OGRE)]
        game.seats[1].battlefield = [Permanent(BEAR), Permanent(SOL_RING), Permanent(DARKSTEEL)]
        game._priority_round(game.seats[0])
        self.assertEqual(names(game.seats[0]), ["City of Brass"] * 4)
        self.assertEqual(names(game.seats[1]), ["Darksteel Myr", "Sol Ring"])
        self.assertEqual(sorted(c.name for c in game.seats[0].graveyard), ["Grizzly Bears", "Ogre", "Wrath of God"])

    def test_tokens_vanish_and_commanders_may_return(self):
        game, _, b = table(pick(CAST), pick("Command zone"))
        game.seats[0].hand = [WRATH]
        game.seats[0].battlefield = lands(4)
        game.create_tokens(game.seats[0], spell_effects(RAISE)[0].token, 2)
        game.seats[1].commander_names = {"Omnath"}
        game.seats[1].battlefield = [Permanent(COMMANDER)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].graveyard, [WRATH])  # the Soldier tokens are gone
        self.assertEqual(game.seats[1].command_zone, [COMMANDER])
        self.assertIn(COMMAND_ZONE_PROMPT, [prompt for prompt, _ in b.prompts])

    def test_qualifier_only_hits_the_other_players(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [PURGE]
        game.seats[0].battlefield = lands(9) + [Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(OGRE)]
        game._priority_round(game.seats[0])
        self.assertEqual((names(game.seats[0])[-1], game.seats[1].battlefield), ("Grizzly Bears", []))

    def test_armageddon(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [ARMAGEDDON]
        game.seats[0].battlefield = lands(4)
        game.seats[1].battlefield = lands(2) + [Permanent(BEAR)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].battlefield, [])
        self.assertEqual(names(game.seats[1]), ["Grizzly Bears"])

    def test_exile_all_does_not_trigger_dies(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [BANISH]
        game.seats[0].battlefield = lands(5)
        game.seats[1].battlefield = [Permanent(MARTYR)]
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[1].exile, game.seats[1].life), ([MARTYR], 40))


class SimultaneousTests(unittest.TestCase):
    def test_watchers_see_every_creature_that_dies_with_them(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [WRATH]
        seat.battlefield = lands(4) + [Permanent(PAWN), Permanent(BEAR), Permanent(BEAR)]
        game._priority_round(seat)
        self.assertEqual(len(seat.hand), 2)  # "another creature you control dies": both Bears, not Pawn itself

    def test_self_or_another_counts_itself_too(self):
        game, _, _ = table(pick(CAST))
        game.seats[0].hand = [WRATH]
        game.seats[0].battlefield = lands(4) + [Permanent(ZULAPORT), Permanent(BEAR)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].life, 38)

    def test_lethal_damage_kills_creatures_together(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [PYROCLASM]
        seat.battlefield = lands(2) + [Permanent(PAWN), Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(BEAR), Permanent(OGRE)]
        game._priority_round(seat)
        self.assertEqual(names(game.seats[1]), ["Ogre"])
        self.assertEqual(game.seats[1].battlefield[0].damage, 2)
        self.assertEqual(len(seat.hand), 1)  # Pawn saw the Bear die, though Pawn died in the same moment


class DamageEachTests(unittest.TestCase):
    def test_each_opponent(self):
        game, _ = table3(pick(CAST))
        game.seats[0].hand = [VORTEX]
        game.seats[0].battlefield = lands(2)
        game._priority_round(game.seats[0])
        self.assertEqual([s.life for s in game.seats], [40, 37, 37])

    def test_each_creature_and_each_player(self):
        game, _ = table3(pick(CAST))
        game.seats[0].hand = [FLARE]
        game.seats[0].battlefield = lands(3) + [Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(OGRE)]
        game._priority_round(game.seats[0])
        self.assertEqual([s.life for s in game.seats], [38, 38, 38])
        self.assertEqual(names(game.seats[0]), ["City of Brass"] * 3)  # the 2/2 Bear died
        self.assertEqual(names(game.seats[1]), ["Ogre"])  # the 3/3 survived with damage


class SacrificeTests(unittest.TestCase):
    def test_each_opponent_chooses_and_the_caster_keeps_theirs(self):
        game, players = table3(pick(CAST), pick("Grizzly", "Ogre"), pick("Ogre"))
        game.seats[0].hand = [TRIBUTE]
        game.seats[0].battlefield = lands(2) + [Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(BEAR), Permanent(OGRE)]
        game.seats[2].battlefield = [Permanent(OGRE)]
        game._priority_round(game.seats[0])
        self.assertEqual((names(game.seats[1]), game.seats[2].battlefield), (["Ogre"], []))
        self.assertIn("Grizzly Bears", names(game.seats[0]))
        prompts = [options for prompt, options in players[1].prompts if prompt == SACRIFICE_PROMPT]
        self.assertEqual(prompts, [["Grizzly Bears 2/2 (seat 1, #1)", "Ogre 3/3 (seat 1, #2)"]])

    def test_each_player_includes_the_caster(self):
        game, _ = table3(pick(CAST), pick("Ogre"), pick("Ogre"))
        game.seats[0].hand = [SWEEP]
        game.seats[0].battlefield = lands(2) + [Permanent(BEAR)]
        game.seats[1].battlefield = [Permanent(OGRE)]
        game._priority_round(game.seats[0])
        self.assertEqual([len([p for p in s.battlefield if "Creature" in p.card.type_line]) for s in game.seats], [0, 0, 0])

    def test_target_opponent_cannot_be_the_caster(self):
        game, _ = table3()
        self.assertEqual([label for label, _ in game.target_options("opponent", game.seats[0])],
                         ["Player: B (seat 1)", "Player: C (seat 2)"])

    def test_edict_and_dies_triggers(self):
        game, _, _ = table(pick(CAST, "Player: B"))
        game.seats[0].hand = [EDICT]
        game.seats[0].battlefield = lands(2)
        game.seats[1].battlefield = [Permanent(MARTYR)]
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[1].battlefield, game.seats[1].life), ([], 43))  # sacrifice is dying

    def test_sacrificed_commander_may_go_to_the_command_zone(self):
        game, _, _ = table(pick(CAST, "Player: B"), pick("Command zone", "Omnath"))
        game.seats[0].hand = [EDICT]
        game.seats[0].battlefield = lands(2)
        game.seats[1].commander_names = {"Omnath"}
        game.seats[1].battlefield = [Permanent(COMMANDER)]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].command_zone, [COMMANDER])

    def test_no_creatures_means_nothing_happens(self):
        game, players = table3(pick(CAST))
        game.seats[0].hand = [TRIBUTE]
        game.seats[0].battlefield = lands(2)
        game._priority_round(game.seats[0])
        self.assertFalse(any(prompt == SACRIFICE_PROMPT for p in players for prompt, _ in p.prompts))


if __name__ == "__main__":
    unittest.main()
