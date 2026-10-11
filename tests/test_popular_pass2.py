"""The second popularity pass: the most played cards still missing a rules line, each from the card's own Oracle text."""

import dataclasses
import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import mana_bonus, mana_condition, mana_lines
from infernal_machine.game import ACTIVATE, ACTIVATE_HAND, CAST, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

VERGE = real("Blazemire Verge", "", "Land", "{T}: Add {B}.\n{T}: Add {R}. Activate only if you control a Swamp or a Mountain.")
SPIRE = real("Spire of Industry", "", "Land", "{T}: Add {C}.\n{T}, Pay 1 life: Add one mana of any color. Activate only if you control an artifact.")
TOWER = dataclasses.replace(real("Urza's Tower", "", "Land — Urza's Tower", "{T}: Add {C}. If you control an Urza's Mine and an Urza's Power-Plant, add {C}{C}{C} instead."), produced_mana=("C",))
MINE = dataclasses.replace(real("Urza's Mine", "", "Land — Urza's Mine", "{T}: Add {C}. If you control an Urza's Power-Plant and an Urza's Tower, add {C}{C} instead."), produced_mana=("C",))
PLANT = dataclasses.replace(real("Urza's Power-Plant", "", "Land — Urza's Power-Plant", "{T}: Add {C}. If you control an Urza's Mine and an Urza's Tower, add {C}{C} instead."), produced_mana=("C",))
SPIRIT_GUIDE = real("Simian Spirit Guide", "{2}{R}", "Creature — Ape Spirit", "Exile this card from your hand: Add {R}.", "2", "2")
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
ROCK = Card(name="Rock", mana_cost="{1}", type_line="Artifact")


def types_of(game, seat, permanent):
    """The mana types each of the permanent's sources can make."""
    return sorted("".join(sorted(s.types)) for s in game._mana_sources(seat) if s.permanent is permanent)


class ManaLandTests(unittest.TestCase):
    def table(self, *others):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = list(others)
        return game, a

    def test_the_verge_lands_read(self):
        self.assertEqual(unsupported_lines(VERGE), [])
        self.assertEqual([types for types, _ in mana_lines(VERGE)], [frozenset("B"), frozenset("R")])
        self.assertIsNone(mana_lines(SWAMP))
        two_plain = real("Odd Land", "", "Land", "{T}: Add {W}.\n{T}: Add {U}.")
        self.assertIsNone(mana_lines(two_plain))  # nothing is conditional: the land's own colors do
        double = real("Odd Land", "", "Land", "{T}: Add {B}{G}.\n{T}: Add {R}. Activate only if you control a Swamp.")
        self.assertIsNone(mana_lines(double))  # the double line is the land's own affair (land_mana_units), not one color

    def test_a_verge_makes_its_second_color_only_with_the_right_land(self):
        for others, expected in (([], ["B"]), ([Permanent(FOREST)], ["B"]), ([Permanent(SWAMP)], ["BR"]), ([Permanent(MOUNTAIN)], ["BR"])):
            verge = Permanent(VERGE)
            game, a = self.table(verge, *others)
            self.assertEqual(types_of(game, a, verge), expected, [p.card.name for p in others])

    def test_a_verge_that_cannot_make_its_second_color_cannot_pay_for_it(self):
        verge = Permanent(VERGE)
        game, a = self.table(verge)
        a.hand = [real("Burn", "{R}", "Instant", "Draw a card.")]
        self.assertNotIn(CAST + "Burn", game.legal_actions(a))
        a.battlefield.append(Permanent(MOUNTAIN))
        self.assertIn(CAST + "Burn", game.legal_actions(a))

    def test_the_condition_names_either_land(self):
        self.assertEqual(mana_condition(Card(name="x", type_line="Land", oracle_text="{T}: Add {R}. Activate only if you control a Swamp or a Mountain.")).what,
                         "Swamp or Mountain")

    def test_spire_of_industry(self):
        self.assertEqual(unsupported_lines(SPIRE), [])
        spire = Permanent(SPIRE)
        game, a = self.table(spire)
        self.assertEqual(types_of(game, a, spire), ["C"])
        a.battlefield.append(Permanent(ROCK))
        self.assertEqual(types_of(game, a, spire), ["BCGRUW"])
        game.legal_actions(a)

    def test_spires_colored_mana_costs_life_and_its_colorless_mana_does_not(self):
        spire = Permanent(SPIRE)
        game, a = self.table(spire, Permanent(ROCK))
        a.hand = [real("Burn", "{R}", "Instant", "Draw a card.")]
        game._perform(a, CAST + "Burn")
        self.assertEqual(a.life, 39)
        a.hand = [real("Gem", "{1}", "Instant", "Draw a card.")]
        spire.tapped = False
        game._perform(a, CAST + "Gem")
        self.assertEqual(a.life, 39)  # {1} is paid with the free {C}


class UrzaLandTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(mana_bonus(TOWER), (("Urza's Mine", "Urza's Power-Plant"), 3))
        self.assertEqual(mana_bonus(MINE), (("Urza's Power-Plant", "Urza's Tower"), 2))
        self.assertIsNone(mana_bonus(SWAMP))
        for card in (TOWER, MINE, PLANT):
            self.assertEqual(unsupported_lines(card), [])

    def count(self, *lands_):
        game, _ = table3()
        a = game.seats[0]
        permanents = [Permanent(c) for c in lands_]
        a.battlefield = permanents
        return {p.card.name: sum(1 for s in game._mana_sources(a) if s.permanent is p) for p in permanents}

    def test_alone_each_makes_one(self):
        self.assertEqual(self.count(TOWER), {"Urza's Tower": 1})

    def test_with_one_of_the_others_still_one(self):
        self.assertEqual(self.count(TOWER, MINE), {"Urza's Tower": 1, "Urza's Mine": 1})

    def test_with_all_three_they_make_three_two_and_two(self):
        self.assertEqual(self.count(TOWER, MINE, PLANT), {"Urza's Tower": 3, "Urza's Mine": 2, "Urza's Power-Plant": 2})


class SpiritGuideTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(SPIRIT_GUIDE), [])

    def test_exiling_it_from_the_hand_adds_its_mana(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [SPIRIT_GUIDE]
        self.assertIn(ACTIVATE_HAND + "Simian Spirit Guide", game.legal_actions(a))
        game._perform(a, ACTIVATE_HAND + "Simian Spirit Guide")
        self.assertEqual(([c.name for c in a.exile], a.hand, a.graveyard, list(a.mana_pool)), (["Simian Spirit Guide"], [], [], [frozenset("R")]))
        self.assertEqual(game.stack, [])  # a mana ability does not use the stack

    def test_the_mana_pays_for_a_spell(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [SPIRIT_GUIDE, real("Burn", "{R}", "Instant", "Draw a card.")]
        game._perform(a, ACTIVATE_HAND + "Simian Spirit Guide")
        self.assertIn(CAST + "Burn", game.legal_actions(a))


AUTHORITY = real("Authority of the Consuls", "{W}", "Enchantment", "Creatures your opponents control enter tapped.\n"
                 "Whenever a creature an opponent controls enters, you gain 1 life.")
OBEDIENCE = real("Blind Obedience", "{1}{W}", "Enchantment", "Extort\nArtifacts and creatures your opponents control enter tapped.")
CLOCK = real("Unwinding Clock", "{2}", "Artifact", "Untap all artifacts you control during each other player's untap step.")
WATERSKIN = real("Bender's Waterskin", "{3}", "Artifact", "Untap this artifact during each other player's untap step.\n{T}: Add one mana of any color.")


class EnterTappedTests(unittest.TestCase):
    def enter(self, watcher, card):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(watcher)]
        entering = Permanent(card)
        game._enter(b, entering)
        return game, entering

    def test_parse(self):
        for card in (AUTHORITY, OBEDIENCE, CLOCK, WATERSKIN):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_an_opponents_creature_enters_tapped(self):
        self.assertTrue(self.enter(AUTHORITY, BEAR)[1].tapped)

    def test_an_opponents_noncreature_permanent_does_not(self):
        self.assertFalse(self.enter(AUTHORITY, ROCK)[1].tapped)

    def test_obedience_taps_artifacts_too(self):
        self.assertTrue(self.enter(OBEDIENCE, ROCK)[1].tapped)
        self.assertTrue(self.enter(OBEDIENCE, BEAR)[1].tapped)
        self.assertFalse(self.enter(OBEDIENCE, SWAMP)[1].tapped)

    def test_your_own_creatures_enter_untapped(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(AUTHORITY)]
        mine = Permanent(BEAR)
        game._enter(a, mine)
        self.assertFalse(mine.tapped)

    def test_a_creature_that_loses_the_enchantment_is_not_held(self):
        game, entering = self.enter(AUTHORITY, BEAR)
        game.seats[0].battlefield.clear()
        later = Permanent(BEAR)
        game._enter(game.seats[1], later)
        self.assertFalse(later.tapped)


class UntapInOtherStepsTests(unittest.TestCase):
    def untap_step(self, card):
        game, _ = table3()
        a, b, _ = game.seats
        mine, rock, bear = Permanent(card), Permanent(ROCK), Permanent(BEAR)
        a.battlefield = [mine, rock, bear]
        for p in a.battlefield:
            p.tapped = True
        game.step = "untap"
        game._turn_based_actions(b)  # another player's untap step
        return mine, rock, bear

    def test_unwinding_clock_untaps_artifacts_only(self):
        clock, rock, bear = self.untap_step(CLOCK)
        self.assertEqual((clock.tapped, rock.tapped, bear.tapped), (False, False, True))

    def test_the_waterskin_untaps_itself_only(self):
        skin, rock, bear = self.untap_step(WATERSKIN)
        self.assertEqual((skin.tapped, rock.tapped, bear.tapped), (False, True, True))

    def test_nothing_untaps_in_your_own_step_that_would_not_anyway(self):
        game, _ = table3()
        a, b, _ = game.seats
        skin = Permanent(WATERSKIN)
        b.battlefield = [skin]
        skin.tapped = True
        game.step = "untap"
        game._turn_based_actions(a)  # its controller is not the one untapping, so the other player's step helps it
        self.assertFalse(skin.tapped)


EXPLORE = real("Explore", "{1}{G}", "Sorcery", "You may play an additional land this turn.\nDraw a card.")
SILENCE = real("Silence", "{W}", "Instant", "Your opponents can't cast spells this turn.")
CAPTAIN = real("Ranger-Captain of Eos", "{1}{W}{W}", "Creature \u2014 Human Soldier",
               "When this creature enters, you may search your library for a creature card with mana value 1 or less, reveal it, put it into your hand, "
               "then shuffle.\nSacrifice this creature: Your opponents can't cast noncreature spells this turn.", "3", "3")
BOLT = real("Bolt", "{R}", "Instant", "Bolt deals 3 damage to any target.")


class SpellEffectTests(unittest.TestCase):
    def test_parse(self):
        for card in (EXPLORE, SILENCE, CAPTAIN):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_explore_allows_a_second_land_this_turn_only(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [EXPLORE, FOREST, FOREST, FOREST], lands(2), [FOREST] * 5
        game._perform(a, CAST + "Explore")
        run_stack(game)
        game._perform(a, PLAY_LAND + "Forest")
        self.assertIn(PLAY_LAND + "Forest", game.legal_actions(a))
        game._perform(a, PLAY_LAND + "Forest")
        self.assertNotIn(PLAY_LAND + "Forest", game.legal_actions(a))
        a.lands_played = 0
        game.turn += 1
        self.assertEqual(game._land_drops(a), 1)

    def test_an_explore_from_an_earlier_turn_is_not_counted_again(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [EXPLORE, EXPLORE], lands(4), [FOREST] * 5
        game._perform(a, CAST + "Explore")
        run_stack(game)
        game.turn += 1
        game._perform(a, CAST + "Explore")
        run_stack(game)
        self.assertEqual(game._land_drops(a), 2)

    def test_two_explores_make_three_land_drops(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [EXPLORE, EXPLORE], lands(4), [FOREST] * 5
        for _ in range(2):
            game._perform(a, CAST + "Explore")
            run_stack(game)
        self.assertEqual(game._land_drops(a), 3)

    def test_silence_stops_opponents_casting_this_turn(self):
        game, _ = table3()
        a, b, c = game.seats
        a.hand, a.battlefield = [SILENCE], lands(1)
        b.hand, b.battlefield = [BOLT], lands(1)
        c.hand, c.battlefield = [BOLT], lands(1)
        self.assertIn(CAST + "Bolt", game.legal_actions(b))
        game._perform(a, CAST + "Silence")
        run_stack(game)
        self.assertNotIn(CAST + "Bolt", game.legal_actions(b))
        self.assertNotIn(CAST + "Bolt", game.legal_actions(c))
        game.turn += 1
        self.assertIn(CAST + "Bolt", game.legal_actions(b))

    def test_silence_does_not_stop_its_caster(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.hand, a.battlefield = [SILENCE, BOLT], lands(3)
        game._perform(a, CAST + "Silence")
        run_stack(game)
        self.assertIn(CAST + "Bolt", game.legal_actions(a))

    def test_the_captain_stops_only_noncreature_spells(self):
        game, _ = table3()
        a, b, _ = game.seats
        b.hand, b.battlefield = [BOLT, BEAR_SPELL], lands(5)
        a.battlefield = [Permanent(CAPTAIN, sick=False)]
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith(ACTIVATE)))
        run_stack(game)
        game.active, game.step = 1, "main1"  # their own turn, when a creature spell can be cast
        self.assertEqual([x for x in game.legal_actions(b) if x.startswith(CAST)], [CAST + "Grizzly"])


BEAR_SPELL = real("Grizzly", "{1}{G}", "Creature \u2014 Bear", "", "2", "2")
MISSTEP = real("Mental Misstep", "{1}{U/P}", "Instant", "Counter target spell with mana value 1.")
REPRIEVE = real("Reprieve", "{1}{W}", "Instant", "Return target spell to its owner's hand.\nDraw a card.")
SWAN_SONG = real("Swan Song", "{U}", "Instant", "Counter target enchantment, instant, or sorcery spell. Its controller creates a 2/2 blue Bird creature token with flying.")
ONE = real("One Drop", "{G}", "Sorcery", "Draw a card.")
TWO = real("Two Drop", "{1}{G}", "Sorcery", "Draw a card.")
ENCHANT = real("Cheap Aura", "{W}", "Enchantment", "Flying")


def stacked(spell, counter, *answers):
    """Seat 0 casts `spell`; seat 1 answers it with `counter`."""
    game, _ = table3(script(), script(*answers))
    a, b, _ = game.seats
    a.hand, a.battlefield, a.library = [spell], lands(2), [FOREST] * 5
    b.hand, b.battlefield, b.library = [counter], lands(3), [FOREST] * 5
    game._perform(a, CAST + spell.name)
    game._perform(b, CAST + counter.name)
    return game, a, b


class CounterVariantsTests(unittest.TestCase):
    def test_parse(self):
        for card in (MISSTEP, REPRIEVE, SWAN_SONG):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_mental_misstep_counters_a_one_drop(self):
        game, a, b = stacked(ONE, MISSTEP, "One Drop")
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], a.hand), (["One Drop"], []))

    def test_mental_misstep_cannot_target_a_two_drop(self):
        game, _ = table3(script(), script("One Drop"))
        a, b, _ = game.seats
        a.hand, a.battlefield = [TWO], lands(2)
        b.hand, b.battlefield = [MISSTEP], lands(2)
        game._perform(a, CAST + "Two Drop")
        self.assertNotIn(CAST + "Mental Misstep", game.legal_actions(b))

    def test_reprieve_returns_the_spell_to_its_owners_hand(self):
        game, a, b = stacked(TWO, REPRIEVE, "Two Drop")
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], a.graveyard, len(b.hand)), (["Two Drop"], [], 1))  # and Reprieve drew a card

    def test_swan_song_counters_and_gives_its_controller_a_bird(self):
        game, a, b = stacked(ENCHANT, SWAN_SONG, "Cheap Aura")
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], [p.card.name for p in a.battlefield if "Token" in p.card.type_line]), (["Cheap Aura"], ["Bird"]))

    def test_swan_song_cannot_target_a_creature_spell(self):
        game, _ = table3(script(), script())
        a, b, _ = game.seats
        a.hand, a.battlefield = [BEAR_SPELL], lands(2)
        b.hand, b.battlefield = [SWAN_SONG], lands(2)
        game._perform(a, CAST + "Grizzly")
        self.assertNotIn(CAST + "Swan Song", game.legal_actions(b))


AQUEOUS = real("Aqueous Form", "{2}{U}", "Enchantment \u2014 Aura", "Enchant creature\nEnchanted creature can't be blocked.\n"
               "Whenever enchanted creature attacks, scry 1.")
CLOAK = real("Whispersilk Cloak", "{3}", "Artifact \u2014 Equipment", "Equipped creature can't be blocked and has shroud.\nEquip {2}")
BLACKBLADE = real("Blackblade Reforged", "{1}", "Legendary Artifact \u2014 Equipment", "Equipped creature gets +1/+1 for each land you control.\nEquip legendary creature {3}\nEquip {7}")
GLITTERS = real("All That Glitters", "{1}{W}", "Enchantment \u2014 Aura", "Enchant creature\nEnchanted creature gets +1/+1 for each artifact and/or enchantment you control.")


class AttachedBuffTests(unittest.TestCase):
    def attach(self, card, *others):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR, sick=False)
        a.battlefield = [bear, Permanent(card), *others]
        a.battlefield[1].attached_to = bear
        return game, a, b, bear

    def test_parse(self):
        for card in (AQUEOUS, CLOAK, BLACKBLADE, GLITTERS):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_an_enchanted_creature_cannot_be_blocked(self):
        game, a, b, bear = self.attach(AQUEOUS)
        self.assertTrue(game.has_keyword(bear, "can't be blocked"))

    def test_the_cloak_also_gives_shroud(self):
        game, a, b, bear = self.attach(CLOAK)
        self.assertTrue(game.has_keyword(bear, "can't be blocked"))
        self.assertTrue(game.has_keyword(bear, "shroud"))
        self.assertNotIn(("Bear", True), [(p.card.name, game.has_keyword(p, "shroud")) for p in b.battlefield])

    def test_the_blade_counts_lands(self):
        game, a, b, bear = self.attach(BLACKBLADE, *lands(3))
        self.assertEqual((game.power(bear), game.toughness(bear)), (5, 5))
        a.battlefield.append(Permanent(FOREST))
        self.assertEqual(game.power(bear), 6)

    def test_all_that_glitters_counts_artifacts_and_enchantments(self):
        game, a, b, bear = self.attach(GLITTERS, Permanent(ROCK), Permanent(ROCK), Permanent(AUTHORITY))
        self.assertEqual(game.power(bear), 2 + 4)  # itself, two rocks and the Authority


PYROBLAST = real("Pyroblast", "{R}", "Instant", "Choose one \u2014\n\u2022 Counter target spell if it's blue.\n\u2022 Destroy target permanent if it's blue.")
RED_BLAST = real("Red Elemental Blast", "{R}", "Instant", "Choose one \u2014\n\u2022 Counter target blue spell.\n\u2022 Destroy target blue permanent.")
BLUE_SPELL = real("Blue Spell", "{U}", "Sorcery", "Draw a card.", colors=("U",))
RED_SPELL = real("Red Spell", "{R}", "Sorcery", "Draw a card.", colors=("R",))
BLUE_BEAR = real("Blue Bear", "{1}{U}", "Creature \u2014 Bear", "", "2", "2", colors=("U",))


class ElementalBlastTests(unittest.TestCase):
    def test_parse(self):
        for card in (PYROBLAST, RED_BLAST):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def answer(self, blast, spell, mode):
        game, _ = table3(script(), script(mode, spell.name))
        a, b, _ = game.seats
        a.hand, a.battlefield, a.library = [spell], lands(2), [FOREST] * 5
        b.hand, b.battlefield = [blast], lands(2)
        game._perform(a, CAST + spell.name)
        game._perform(b, CAST + blast.name)
        run_stack(game)
        return a

    def test_red_blast_counters_a_blue_spell(self):
        self.assertEqual([c.name for c in self.answer(RED_BLAST, BLUE_SPELL, "Counter").graveyard], ["Blue Spell"])
        self.assertEqual(self.answer(RED_BLAST, BLUE_SPELL, "Counter").hand, [])  # it never drew

    def test_red_blast_cannot_be_cast_when_only_a_red_spell_is_there(self):
        game, _ = table3(script(), script("Counter"))
        a, b, _ = game.seats
        a.hand, a.battlefield = [RED_SPELL], lands(2)
        b.hand, b.battlefield = [RED_BLAST], lands(2)
        game._perform(a, CAST + "Red Spell")
        self.assertNotIn(CAST + "Red Elemental Blast", game.legal_actions(b))

    def test_pyroblast_does_nothing_to_a_red_spell_it_targets(self):
        a = self.answer(PYROBLAST, RED_SPELL, "Counter")
        self.assertEqual(len(a.hand), 1)  # the red spell resolved and drew

    def test_pyroblast_counters_a_blue_one(self):
        self.assertEqual(len(self.answer(PYROBLAST, BLUE_SPELL, "Counter").hand), 0)

    def destroy(self, name):
        game, _ = table3(script("Destroy", name))
        a, b, _ = game.seats
        a.hand, a.battlefield = [PYROBLAST], lands(1)
        b.battlefield = [Permanent(BLUE_BEAR), Permanent(BEAR)]
        game._perform(a, CAST + "Pyroblast")
        run_stack(game)
        return sorted(p.card.name for p in b.battlefield)

    def test_pyroblast_destroys_a_blue_permanent(self):
        self.assertEqual(self.destroy("Blue Bear"), ["Bear"])

    def test_pyroblast_leaves_a_permanent_that_is_not_blue(self):
        self.assertEqual(self.destroy("Bear"), ["Bear", "Blue Bear"])


PROBE = real("Gitaxian Probe", "{U/P}", "Sorcery", "Look at target player's hand.\nDraw a card.")
CABAL = real("Cabal Ritual", "{1}{B}", "Instant", "Add {B}{B}{B}.\nThreshold \u2014 Add {B}{B}{B}{B}{B} instead if there are seven or more cards in your graveyard.")
RITE = real("Rite of Flame", "{R}", "Sorcery", "Add {R}{R}, then add {R} for each card named Rite of Flame in each graveyard.")
ENTOMB = real("Entomb", "{B}", "Instant", "Search your library for a card, put that card into your graveyard, then shuffle.")
BURIED = real("Buried Alive", "{2}{B}", "Sorcery", "Search your library for up to three creature cards, put them into your graveyard, then shuffle.")
SANITARIUM = real("Geier Reach Sanitarium", "", "Legendary Land", "{T}: Add {C}.\n{2}, {T}: Each player draws a card, then discards a card.")
REVERSAL = real("Dramatic Reversal", "{1}{U}", "Instant", "Untap all nonland permanents you control.")


def hand_after(game, seat, name):
    game._perform(seat, CAST + name)
    run_stack(game)
    game._check_state()


class SmallSpellTests(unittest.TestCase):
    def test_parse(self):
        for card in (PROBE, CABAL, RITE, ENTOMB, BURIED, SANITARIUM, REVERSAL):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_gitaxian_probe_shows_its_controller_the_hand_and_draws(self):
        game, players = table3(script("Player: B"))
        a, b, _ = game.seats
        a.hand, a.battlefield, a.library = [PROBE], lands(1), [FOREST] * 3
        b.hand = [BEAR, OGRE]
        hand_after(game, a, "Gitaxian Probe")
        seen = [e for e in players[0].events if e.get("event") == "hand"]
        self.assertEqual([e["cards"] for e in seen], [["Bear", "Ogre"]])
        self.assertEqual(len(a.hand), 1)

    def mana_after(self, card, graveyard=()):
        game, _ = table3()
        a = game.seats[0]
        a.hand, a.battlefield = [card], lands(2)
        a.graveyard = list(graveyard)
        a.mana_pool = []
        game._perform(a, CAST + card.name)
        run_stack(game)
        return sorted("".join(sorted(unit)) for unit in a.mana_pool)

    def test_cabal_ritual_makes_three(self):
        self.assertEqual(self.mana_after(CABAL, [BEAR] * 3), ["B", "B", "B"])

    def test_cabal_ritual_with_threshold_makes_five(self):
        self.assertEqual(self.mana_after(CABAL, [BEAR] * 7), ["B"] * 5)

    def test_cabal_ritual_with_six_cards_is_still_three(self):
        self.assertEqual(self.mana_after(CABAL, [BEAR] * 6), ["B"] * 3)

    def test_rite_of_flame_counts_the_copies_in_every_graveyard(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.hand, a.battlefield = [RITE], lands(1)
        a.graveyard, b.graveyard = [RITE], [RITE, BEAR]
        a.mana_pool = []
        game._perform(a, CAST + "Rite of Flame")
        run_stack(game)
        self.assertEqual(len(a.mana_pool), 2 + 2)

    def test_entomb_puts_a_card_in_the_graveyard(self):
        game, _ = table3(script("Ogre"))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [ENTOMB], lands(1), [BEAR, OGRE]
        hand_after(game, a, "Entomb")
        self.assertEqual(([c.name for c in a.graveyard], len(a.library)), (["Ogre", "Entomb"], 1))

    def test_buried_alive_finds_up_to_three_creatures_and_may_stop(self):
        game, _ = table3(script("Ogre", "Bear", "Done"))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [BURIED], lands(3), [BEAR, OGRE, BEAR, FOREST]
        hand_after(game, a, "Buried Alive")
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Buried Alive", "Ogre"])
        self.assertEqual(len(a.library), 2)

    def test_buried_alive_with_fewer_creatures_takes_what_is_there(self):
        game, _ = table3(script("Bear", "Ogre", "Ogre"))
        a = game.seats[0]
        a.hand, a.battlefield, a.library = [BURIED], lands(3), [BEAR, FOREST]
        hand_after(game, a, "Buried Alive")
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Buried Alive"])

    def test_the_sanitarium_makes_everyone_draw_then_discard(self):
        game, _ = table3(script(), script("Pass"))
        a, b, c = game.seats
        for seat in (a, b, c):
            seat.library = [FOREST] * 5
            seat.hand = [BEAR]
        a.battlefield = [Permanent(SANITARIUM)] + lands(2)
        game._perform(a, next(x for x in game.legal_actions(a) if x.startswith("Activate")))
        run_stack(game)
        self.assertEqual([len(s.hand) for s in (a, b, c)], [1, 1, 1])
        self.assertEqual([len(s.graveyard) for s in (a, b, c)], [1, 1, 1])

    def test_dramatic_reversal_untaps_nonlands_only(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [REVERSAL]
        land, rock, bear = lands(3)[0], Permanent(ROCK), Permanent(BEAR)
        a.battlefield = [land, lands(1)[0], rock, bear]
        for p in a.battlefield[2:]:
            p.tapped = True
        a.battlefield[1].tapped = False
        game._perform(a, CAST + "Dramatic Reversal")
        run_stack(game)
        self.assertEqual((rock.tapped, bear.tapped), (False, False))


GREATER_GOOD = real("Greater Good", "{2}{G}{G}", "Enchantment", "Sacrifice a creature: Draw cards equal to the sacrificed creature's power, then discard three cards.")
ALTAR = real("Altar of Dementia", "{2}", "Artifact", "Sacrifice a creature: Target player mills cards equal to the sacrificed creature's power.")
GRAVE_PACT = real("Grave Pact", "{2}{B}{B}{B}", "Enchantment", "Whenever a creature you control dies, each other player sacrifices a creature of their choice.")
BITTERBLOSSOM = real("Bitterblossom", "{1}{B}", "Enchantment", "At the beginning of your upkeep, you lose 1 life and create a 1/1 black Faerie Rogue creature token with flying.")
BEACON = real("Command Beacon", "", "Land", "{T}: Add {C}.\n{T}, Sacrifice this land: Put your commander into your hand from the command zone.")
CLAW = real("Nature's Claim", "{G}", "Instant", "Destroy target artifact or enchantment. Its controller gains 4 life.")
BEDEVIL = real("Bedevil", "{B}{R}", "Instant", "Destroy target artifact, creature, or planeswalker.")
PRESSURE = real("Pressure Point", "{1}{W}", "Instant", "Tap target creature.\nDraw a card.")
RENUNCIATION = real("Djeru's Renunciation", "{2}{W}", "Instant", "Tap up to two target creatures. Draw a card.")
COMMANDER = real("Big Boss", "{3}{R}", "Legendary Creature \u2014 Boss", "", "4", "4")


def first_ability(game, seat):
    return next(x for x in game.legal_actions(seat) if x.startswith("Activate"))


class PermanentTests(unittest.TestCase):
    def test_parse(self):
        for card in (GREATER_GOOD, ALTAR, GRAVE_PACT, BITTERBLOSSOM, BEACON, CLAW, BEDEVIL, PRESSURE, RENUNCIATION):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_greater_good_draws_the_power_then_discards_three(self):
        game, _ = table3(script("Ogre", "Bear", "Bear", "Bear"))
        a = game.seats[0]
        a.battlefield = [Permanent(GREATER_GOOD), Permanent(OGRE)]
        a.hand, a.library = [BEAR, BEAR, BEAR], [FOREST] * 6
        game._perform(a, first_ability(game, a))
        run_stack(game)
        self.assertEqual(len(a.hand), 3 + 3 - 3)  # three drawn for the Ogre's power, three discarded
        self.assertEqual(len(a.graveyard), 3 + 1)  # and the Ogre

    def test_altar_of_dementia_mills_by_the_power(self):
        game, _ = table3(script("Player: B", "Ogre"))
        a, b, _ = game.seats
        a.battlefield = [Permanent(ALTAR), Permanent(OGRE)]
        b.library = [FOREST] * 10
        game._perform(a, first_ability(game, a))
        run_stack(game)
        self.assertEqual((len(b.library), len(b.graveyard)), (7, 3))

    def test_grave_pact_makes_each_other_player_sacrifice(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(GRAVE_PACT), Permanent(BEAR), Permanent(OGRE)]
        b.battlefield, c.battlefield = [Permanent(BEAR), Permanent(OGRE)], [Permanent(OGRE)]
        game.sacrifice(a)
        run_stack(game)
        game._check_state()
        self.assertEqual((len(b.battlefield), len(c.battlefield)), (1, 0))
        self.assertEqual(len([p for p in a.battlefield if "Creature" in p.card.type_line]), 1)  # only the one that died: not "each player"

    def test_bitterblossom_costs_a_life_and_makes_a_faerie_each_upkeep(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(BITTERBLOSSOM)]
        for _ in range(2):
            game.trigger("upkeep", a.battlefield[0], a)
            run_stack(game)
        self.assertEqual(a.life, 38)
        self.assertEqual([p.card.name for p in a.battlefield if "Token" in p.card.type_line], ["Faerie Rogue", "Faerie Rogue"])

    def test_command_beacon_returns_the_commander_to_hand(self):
        game, _ = table3()
        a = game.seats[0]
        a.command_zone, a.commander_names = [COMMANDER], {"Big Boss"}
        a.battlefield = [Permanent(BEACON)]
        game._perform(a, first_ability(game, a))
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], a.command_zone, a.battlefield), (["Big Boss"], [], []))

    def test_with_two_commanders_it_asks_which(self):
        game, _ = table3(script("Second Boss"))
        a = game.seats[0]
        second = real("Second Boss", "{3}{R}", "Legendary Creature \u2014 Boss", "", "4", "4")
        a.command_zone, a.commander_names = [COMMANDER, second], {"Big Boss", "Second Boss"}
        a.battlefield = [Permanent(BEACON)]
        game._perform(a, first_ability(game, a))
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.command_zone]), (["Second Boss"], ["Big Boss"]))

    def test_command_beacon_with_no_commander_there_just_goes(self):
        game, _ = table3()
        a = game.seats[0]
        a.command_zone, a.commander_names = [], {"Big Boss"}
        a.battlefield = [Permanent(BEACON)]
        game._perform(a, first_ability(game, a))
        run_stack(game)
        self.assertEqual((a.hand, [p.card.name for p in a.battlefield]), ([], []))


class DestroyAndTapTests(unittest.TestCase):
    def test_natures_claim_gives_the_controller_four_life(self):
        game, _ = table3(script("Rock"))
        a, b, _ = game.seats
        a.hand, a.battlefield = [CLAW], lands(1)
        b.battlefield = [Permanent(ROCK)]
        hand_after(game, a, "Nature's Claim")
        self.assertEqual(([p.card.name for p in b.battlefield], b.life), ([], 44))

    def test_bedevil_reaches_a_creature(self):
        game, _ = table3(script("Bear"))
        a, b, _ = game.seats
        a.hand, a.battlefield = [BEDEVIL], lands(2)
        b.battlefield = [Permanent(BEAR), Permanent(ROCK)]
        hand_after(game, a, "Bedevil")
        self.assertEqual([p.card.name for p in b.battlefield], ["Rock"])

    def test_bedevil_cannot_target_a_land(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.hand, a.battlefield = [BEDEVIL], lands(2)
        b.battlefield = [Permanent(FOREST)]
        self.assertNotIn(CAST + "Bedevil", game.legal_actions(a))

    def test_tap_target_creature(self):
        game, _ = table3(script("Bear"))
        a, b, _ = game.seats
        a.hand, a.battlefield, a.library = [PRESSURE], lands(2), [FOREST] * 3
        bear = Permanent(BEAR)
        b.battlefield = [bear, Permanent(OGRE)]
        hand_after(game, a, "Pressure Point")
        self.assertEqual([p.tapped for p in b.battlefield], [True, False])

    def test_tap_up_to_two_target_creatures(self):
        game, _ = table3(script("Bear", "Ogre"))
        a, b, _ = game.seats
        a.hand, a.battlefield, a.library = [RENUNCIATION], lands(3), [FOREST] * 3
        b.battlefield = [Permanent(BEAR), Permanent(OGRE), Permanent(BEAR)]
        hand_after(game, a, "Djeru's Renunciation")
        self.assertEqual(sum(p.tapped for p in b.battlefield), 2)


GRIP = real("Krosan Grip", "{2}{G}", "Instant", "Split second\nDestroy target artifact or enchantment.")
EPHEMERATE = real("Ephemerate", "{W}", "Instant", "Rebound\nExile target creature you control, then return it to the battlefield under its owner's control.")
FLICKER = real("Flicker", "{W}", "Instant", "Exile target creature you control, then return it to the battlefield under its owner's control.")


class SplitSecondTests(unittest.TestCase):
    def table(self):
        game, _ = table3(script("Rock"))
        a, b, _ = game.seats
        a.hand, a.battlefield = [GRIP], lands(3)
        b.hand, b.battlefield = [BOLT], lands(2) + [Permanent(ROCK)]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(GRIP), [])

    def test_nothing_can_be_cast_in_response(self):
        game, a, b = self.table()
        self.assertIn(CAST + "Bolt", game.legal_actions(b))
        game._perform(a, CAST + "Krosan Grip")
        self.assertEqual(game.legal_actions(b), ["Pass"])
        self.assertEqual(game.legal_actions(a), ["Pass"])

    def test_it_resolves_and_play_goes_on(self):
        game, a, b = self.table()
        game._perform(a, CAST + "Krosan Grip")
        run_stack(game)
        self.assertIn(CAST + "Bolt", game.legal_actions(b))
        self.assertEqual([p.card.name for p in b.battlefield if "Artifact" in p.card.type_line], [])

    def test_a_spell_without_it_can_be_answered(self):
        game, _ = table3(script("Rock"))
        a, b, _ = game.seats
        a.hand, a.battlefield = [CLAW], lands(1)
        b.hand, b.battlefield = [BOLT], lands(1) + [Permanent(ROCK)]
        game._perform(a, CAST + "Nature's Claim")
        self.assertIn(CAST + "Bolt", game.legal_actions(b))


class ReboundTests(unittest.TestCase):
    def table(self, *answers):
        game, _ = table3(script(*answers))
        a = game.seats[0]
        a.hand, a.battlefield = [EPHEMERATE], lands(2) + [Permanent(BEAR)]
        a.library = [FOREST] * 5
        return game, a

    def upkeep(self, game, a):
        game.turn += 1
        game.step = "upkeep"
        game._turn_based_actions(a)
        run_stack(game)

    def test_parse(self):
        self.assertEqual(unsupported_lines(EPHEMERATE), [])

    def test_cast_from_the_hand_it_is_exiled_as_it_resolves(self):
        game, a = self.table("Bear")
        hand_after(game, a, "Ephemerate")
        self.assertEqual(([c.name for c in a.exile], a.graveyard), (["Ephemerate"], []))

    def test_at_the_next_upkeep_it_is_cast_again_for_free_and_goes_to_the_graveyard(self):
        game, a = self.table("Bear", "Yes", "Bear")
        hand_after(game, a, "Ephemerate")
        self.upkeep(game, a)
        self.assertEqual(([c.name for c in a.exile], [c.name for c in a.graveyard]), ([], ["Ephemerate"]))
        self.assertEqual(a.rebounding, [])

    def test_it_waits_for_the_next_upkeep_not_this_turn(self):
        game, a = self.table("Bear")
        hand_after(game, a, "Ephemerate")
        game.step = "upkeep"
        game._turn_based_actions(a)  # the same turn
        self.assertEqual([c.name for c in a.exile], ["Ephemerate"])

    def test_declining_leaves_it_in_exile_for_good(self):
        game, a = self.table("Bear", "No")
        hand_after(game, a, "Ephemerate")
        self.upkeep(game, a)
        self.assertEqual(([c.name for c in a.exile], a.graveyard), (["Ephemerate"], []))
        self.upkeep(game, a)
        self.assertEqual(a.rebounding, [])

    def test_a_spell_that_fizzles_does_not_rebound(self):
        game, a = self.table("Bear")
        game._perform(a, CAST + "Ephemerate")
        a.battlefield = [p for p in a.battlefield if p.card.name != "Bear"]  # the target is gone
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], a.exile, a.rebounding), (["Ephemerate"], [], []))

    def test_a_spell_cast_from_elsewhere_does_not_rebound(self):
        game, a = self.table("Bear")
        a.hand, a.graveyard = [], [EPHEMERATE]
        game._cast(a, EPHEMERATE, a.graveyard, free=True)  # as if cast from the graveyard (not from the hand)
        run_stack(game)
        self.assertEqual(a.rebounding, [])
        self.assertEqual([c.name for c in a.graveyard], ["Ephemerate"])


if __name__ == "__main__":
    unittest.main()
