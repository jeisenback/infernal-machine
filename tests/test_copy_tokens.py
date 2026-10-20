"""Token copies as one sentence shape: "Create a token that's a copy of <what>(, except <changes>)." followed by its riders
("It gains haste.", "Sacrifice it / Exile it at the beginning of the next end step."), for any <what> the engine can find
(a target, the permanent that set a trigger off, the source, the equipped or enchanted permanent, a card in a graveyard, each
permanent of a kind). Lines are the cards' own Oracle text."""

import dataclasses
import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, Table, lands, pick, real, run_stack, table, table3

KIKI = real("Kiki-Jiki, Mirror Breaker", "{2}{R}{R}{R}", "Legendary Creature — Goblin Shaman",
            "Haste\n{T}: Create a token that's a copy of target nonlegendary creature you control, except it has haste. Sacrifice it at "
            "the beginning of the next end step.", "2", "2")
FIRE_CRYSTAL = real("The Fire Crystal", "{2}{R}{R}", "Legendary Artifact",
                    "Red spells you cast cost {1} less to cast.\nCreatures you control have haste.\n{4}{R}{R}, {T}: Create a token that's a "
                    "copy of target creature you control. Sacrifice it at the beginning of the next end step.")
SECOND_HARVEST = real("Second Harvest", "{2}{G}{G}", "Instant", "For each token you control, create a token that's a copy of that permanent.")
FLAMESHADOW = real("Flameshadow Conjuring", "{3}{R}", "Enchantment",
                   "Whenever a nontoken creature you control enters, you may pay {R}. If you do, create a token that's a copy of that "
                   "creature. That token gains haste. Exile it at the beginning of the next end step.")
MIRRORWORKS = real("Mirrorworks", "{5}", "Artifact",
                   "Whenever another nontoken artifact you control enters, you may pay {2}. If you do, create a token that's a copy of "
                   "that artifact.")
RIKU = real("Riku of Two Reflections", "{2}{G}{U}{R}", "Legendary Creature — Human Wizard",
            "Whenever you cast an instant or sorcery spell, you may pay {U}{R}. If you do, copy that spell. You may choose new targets "
            "for the copy.\nWhenever another nontoken creature you control enters, you may pay {G}{U}. If you do, create a token that's "
            "a copy of that creature.", "2", "2")
SPLINTER_TWIN = real("Splinter Twin", "{2}{R}{R}", "Enchantment — Aura",
                     "Enchant creature\nEnchanted creature has \"{T}: Create a token that's a copy of this creature, except it has haste. "
                     "Exile that token at the beginning of the next end step.\"")
FELDON = real("Feldon of the Third Path", "{1}{R}{R}", "Legendary Creature — Human Artificer",
              "{2}{R}, {T}: Create a token that's a copy of target creature card in your graveyard, except it's an artifact in addition "
              "to its other types. It gains haste. Sacrifice it at the beginning of the next end step.", "2", "3")
MOLTEN_DUPLICATION = real("Molten Duplication", "{1}{R}", "Sorcery",
                          "Create a token that's a copy of target artifact or creature you control, except it's an artifact in addition "
                          "to its other types. It gains haste until end of turn. Sacrifice it at the beginning of the next end step.")
SHEPHERD = real("Nightmare Shepherd", "{2}{B}{B}", "Enchantment Creature — Demon",
                "Flying\nWhenever another nontoken creature you control dies, you may exile it. If you do, create a token that's a copy "
                "of that creature, except it's 1/1 and it's a Nightmare in addition to its other types.", "4", "4")
HELM = real("Helm of the Host", "{4}", "Legendary Artifact — Equipment",
            "At the beginning of combat on your turn, create a token that's a copy of equipped creature, except the token isn't "
            "legendary if equipped creature is legendary. That token gains haste.\nEquip {5}")
MIIRYM = real("Miirym, Sentinel Wyrm", "{3}{G}{U}{R}", "Legendary Creature — Dragon Spirit",
              "Flying, ward {2}\nWhenever another nontoken Dragon you control enters, create a token that's a copy of it, except the "
              "token isn't legendary if that Dragon is legendary.", "6", "6")
HOFRI = real("Hofri Ghostforge", "{3}{R}{W}", "Legendary Creature — Dwarf Cleric",
             "Spirits you control get +1/+1 and have trample and haste.\nWhenever another nontoken creature you control dies, exile it. "
             "If you do, create a token that's a copy of that creature, except it's a Spirit in addition to its other types and it has "
             "\"When this creature leaves the battlefield, return the exiled card to its owner's graveyard.\"", "4", "5")
SCARAB_GOD_LINE = ("{2}{U}{B}: Exile target creature card from a graveyard. Create a token that's a copy of it, except it's a 4/4 black "
                   "Zombie.")
SCARAB_GOD = real("The Scarab God", "{3}{U}{B}", "Legendary Creature — God",
                  "At the beginning of your upkeep, each opponent loses X life and you scry X, where X is the number of Zombies you "
                  f"control.\n{SCARAB_GOD_LINE}\nWhen The Scarab God dies, return it to its owner's hand at the beginning of the next "
                  "end step.", "5", "5")
ORTHION = real("Orthion, Hero of Lavabrink", "{3}{R}", "Legendary Creature — Human Soldier",
               "{1}{R}, {T}: Create a token that's a copy of another target creature you control. It gains haste. Sacrifice it at the "
               "beginning of the next end step. Activate only as a sorcery.\n{6}{R}{R}{R}, {T}: Create five tokens that are copies of "
               "another target creature you control. They gain haste. Sacrifice them at the beginning of the next end step. Activate "
               "only as a sorcery.", "3", "3")
DACKS_DUPLICATE = real("Dack's Duplicate", "{2}{U}{R}", "Creature — Shapeshifter",
                       "You may have Dack's Duplicate enter as a copy of any creature on the battlefield, except it has haste and "
                       "dethrone.", "0", "0")
HERO = real("Test Hero", "{1}{W}", "Legendary Creature — Human Knight", "Vigilance", "2", "2")
WHELP = real("Whelp Dragon", "{1}{R}", "Creature — Dragon", "", "2", "2")
RELIC = real("Relic", "{1}", "Artifact", "")


def tokens(seat, name=None):
    return [p for p in seat.battlefield if p.card.type_line.startswith("Token") and (name is None or p.card.name == name)]


def end_step(game, seat):
    game.step = "end"
    game._turn_based_actions(seat)
    run_stack(game)


def activate(game, seat, text):
    [action] = [x for x in game._activations(seat, True) if text in x]
    game._perform(seat, action)
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (KIKI, FIRE_CRYSTAL, SECOND_HARVEST, FLAMESHADOW, MIRRORWORKS, RIKU, SPLINTER_TWIN, FELDON, MOLTEN_DUPLICATION,
                     SHEPHERD, HELM, MIIRYM, HOFRI, ORTHION):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_scarab_god_copy_line_is_understood(self):
        self.assertNotIn(SCARAB_GOD_LINE, unsupported_lines(SCARAB_GOD))

    def test_a_change_the_engine_does_not_apply_leaves_the_line_unsupported(self):
        self.assertEqual(len(unsupported_lines(DACKS_DUPLICATE)), 1)  # dethrone
        odd = real("Odd Copier", "{2}", "Sorcery", "Create a token that's a copy of target creature you control, except it can't block.")
        self.assertEqual(len(unsupported_lines(odd)), 1)

    def test_a_rider_with_no_copy_before_it_is_not_understood(self):
        lone = real("Lone Rider", "{2}", "Sorcery", "Draw a card. Sacrifice it at the beginning of the next end step.")
        self.assertEqual(len(unsupported_lines(lone)), 1)


class ActivatedCopyTests(unittest.TestCase):
    def test_kiki_jiki_copies_a_nonlegendary_creature_with_haste_and_sacrifices_it(self):
        game, _ = table3(pick("Activate", "Bear"))
        a = game.seats[0]
        a.battlefield = [Permanent(KIKI), Permanent(BEAR), Permanent(HERO)]
        actions = [x for x in game._activations(a, True) if "Create a token that's a copy" in x]
        self.assertEqual(len(actions), 1)
        game._perform(a, actions[0])
        run_stack(game)
        [token] = tokens(a)
        self.assertEqual((token.card.name, game.has_keyword(token, "haste")), ("Bear", True))
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Test Hero"], ["Test Hero"])  # not a legal target
        end_step(game, a)
        self.assertEqual(tokens(a), [])
        self.assertEqual([c.name for c in a.graveyard], [])  # a token that is sacrificed leaves nothing in the graveyard

    def test_the_fire_crystal_copy_is_sacrificed_at_the_next_end_step(self):
        game, _ = table3(pick("Activate", "Bear"))
        a = game.seats[0]
        a.battlefield = [Permanent(FIRE_CRYSTAL), Permanent(BEAR), *lands(6)]
        activate(game, a, "Create a token that's a copy")
        self.assertEqual(len(tokens(a, "Bear")), 1)
        end_step(game, a)
        self.assertEqual(tokens(a), [])

    def test_feldon_copies_a_creature_card_in_the_graveyard_as_an_artifact(self):
        game, _ = table3(pick("Activate", "Bear"))
        a = game.seats[0]
        a.battlefield = [Permanent(FELDON), *lands(3)]
        a.graveyard = [BEAR]
        activate(game, a, "Create a token that's a copy")
        [token] = tokens(a, "Bear")
        self.assertEqual(token.card.type_line, "Token Artifact Creature — Test")
        self.assertTrue(game.has_keyword(token, "haste"))
        self.assertEqual([c.name for c in a.graveyard], ["Bear"])  # the card stays where it was
        end_step(game, a)
        self.assertEqual(tokens(a), [])

    def test_feldon_has_nothing_to_copy_without_a_creature_card_in_the_graveyard(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(FELDON), *lands(3)]
        a.graveyard = [RELIC]
        self.assertEqual([x for x in game._activations(a, True) if "Create a token that's a copy" in x], [])

    def test_splinter_twin_grants_the_ability_and_the_copy_is_exiled(self):
        game, _ = table3(pick("Activate"))
        a = game.seats[0]
        bear, twin = Permanent(BEAR), Permanent(SPLINTER_TWIN)
        twin.attached_to = bear
        a.battlefield = [bear, twin]
        activate(game, a, "Create a token that's a copy of this creature")
        [token] = tokens(a, "Bear")
        self.assertTrue(game.has_keyword(token, "haste"))
        end_step(game, a)
        self.assertEqual(tokens(a), [])
        self.assertEqual([c.name for c in a.graveyard], [])

    def test_the_scarab_god_makes_a_black_zombie_from_a_card_in_any_graveyard(self):
        game, _ = table3(pick("Activate", "Test Hero"))
        a, b, _ = game.seats
        a.battlefield = [Permanent(SCARAB_GOD), *lands(4)]
        b.graveyard = [HERO]
        activate(game, a, "Exile target creature card from a graveyard")
        [token] = tokens(a, "Test Hero")
        self.assertEqual((token.card.type_line, token.card.power, token.card.toughness, token.card.colors),
                         ("Token Legendary Creature — Zombie", "4", "4", ("B",)))
        self.assertEqual(b.graveyard, [])
        self.assertEqual([c.name for c in b.exile], ["Test Hero"])


class SpellCopyTests(unittest.TestCase):
    def test_second_harvest_copies_each_token_and_nothing_else(self):
        token = Permanent(dataclasses.replace(BEAR, type_line="Token Creature — Bear"))
        treasure = Permanent(real("Treasure", "", "Token Artifact — Treasure", "{T}, Sacrifice this artifact: Add one mana of any color."))
        t = Table(SECOND_HARVEST, mine=[token, treasure, Permanent(OGRE)]).cast()
        self.assertEqual(sorted(p.card.name for p in tokens(t.a)), ["Bear", "Bear", "Treasure", "Treasure"])
        self.assertEqual(len([p for p in t.a.battlefield if p.card.name == "Ogre"]), 1)

    def test_molten_duplication_copies_with_haste_this_turn_and_sacrifices_at_the_end_step(self):
        t = Table(MOLTEN_DUPLICATION, "Bear", mine=[Permanent(BEAR)]).cast()
        [token] = tokens(t.a, "Bear")
        self.assertIn("Artifact", token.card.type_line)
        self.assertTrue(t.game.has_keyword(token, "haste"))
        end_step(t.game, t.a)
        self.assertEqual(tokens(t.a), [])


class TriggeredCopyTests(unittest.TestCase):
    def cast(self, card, battlefield, *answers):
        game, _, _ = table(pick(CAST, card.name, *answers))
        seat = game.seats[0]
        seat.hand = [card]
        seat.battlefield = lands(5) + battlefield
        game._priority_round(seat)
        run_stack(game)
        return game, seat

    def test_flameshadow_conjuring_copies_an_entering_creature_for_red_mana(self):
        game, seat = self.cast(BEAR, [Permanent(FLAMESHADOW)], "Pay")
        [token] = tokens(seat, "Bear")
        self.assertTrue(game.has_keyword(token, "haste"))
        end_step(game, seat)
        self.assertEqual(tokens(seat), [])
        self.assertEqual([c.name for c in seat.exile], ["Bear"][:0])  # a token exiled ceases to exist

    def test_flameshadow_conjuring_does_nothing_when_the_mana_is_not_paid(self):
        game, seat = self.cast(BEAR, [Permanent(FLAMESHADOW)], "Don't pay")
        self.assertEqual(tokens(seat), [])

    def test_mirrorworks_copies_an_entering_artifact(self):
        game, seat = self.cast(RELIC, [Permanent(MIRRORWORKS)], "Pay")
        self.assertEqual(len(tokens(seat, "Relic")), 1)

    def test_riku_copies_an_entering_nontoken_creature(self):
        game, seat = self.cast(BEAR, [Permanent(RIKU)], "Pay")
        self.assertEqual(len(tokens(seat, "Bear")), 1)
        end_step(game, seat)
        self.assertEqual(len(tokens(seat, "Bear")), 1)  # no rider: it stays

    def test_the_copies_miirym_and_helm_make_are_not_legendary(self):
        legend = dataclasses.replace(WHELP, name="Old Wyrm", type_line="Legendary Creature — Dragon")
        game, seat = self.cast(legend, [Permanent(MIIRYM)])
        [token] = tokens(seat, "Old Wyrm")
        self.assertNotIn("Legendary", token.card.type_line)
        game, _ = table3()
        a = game.seats[0]
        hero, helm = Permanent(HERO), Permanent(HELM)
        helm.attached_to = hero
        a.battlefield = [hero, helm]
        game.step = "beginning_of_combat"
        game._turn_based_actions(a)
        run_stack(game)
        [token] = tokens(a, "Test Hero")
        self.assertNotIn("Legendary", token.card.type_line)
        self.assertTrue(game.has_keyword(token, "haste"))

    def test_nightmare_shepherd_exiles_the_dead_creature_and_makes_a_one_one_nightmare(self):
        game, _, _ = table(pick("Yes"))
        seat = game.seats[0]
        bear = Permanent(BEAR)
        seat.battlefield = [Permanent(SHEPHERD), bear]
        game.destroy(bear)
        run_stack(game)
        [token] = tokens(seat, "Bear")
        self.assertEqual((token.card.power, token.card.toughness, token.card.type_line), ("1", "1", "Token Creature — Test Nightmare"))
        self.assertEqual(([c.name for c in seat.exile], seat.graveyard), (["Bear"], []))

    def test_nightmare_shepherd_may_be_declined(self):
        game, _, _ = table(pick("No"))
        seat = game.seats[0]
        bear = Permanent(BEAR)
        seat.battlefield = [Permanent(SHEPHERD), bear]
        game.destroy(bear)
        run_stack(game)
        self.assertEqual((tokens(seat), [c.name for c in seat.graveyard]), ([], ["Bear"]))

    def test_hofri_still_sends_the_exiled_card_back_when_the_copy_leaves(self):
        game, _, _ = table()
        seat = game.seats[0]
        bear = Permanent(BEAR)
        seat.battlefield = [Permanent(HOFRI), bear]
        game.destroy(bear)
        run_stack(game)
        [token] = tokens(seat, "Bear")
        self.assertIn("Spirit", token.card.type_line)
        game.destroy(token)
        run_stack(game)
        self.assertEqual(([c.name for c in seat.graveyard], seat.exile), (["Bear"], []))


if __name__ == "__main__":
    unittest.main()
