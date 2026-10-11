"""The second popularity pass: the most played cards still missing a rules line, each from the card's own Oracle text."""

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
TOWER = real("Urza's Tower", "", "Land — Urza's Tower", "{T}: Add {C}. If you control an Urza's Mine and an Urza's Power-Plant, add {C}{C}{C} instead.")
MINE = real("Urza's Mine", "", "Land — Urza's Mine", "{T}: Add {C}. If you control an Urza's Power-Plant and an Urza's Tower, add {C}{C} instead.")
PLANT = real("Urza's Power-Plant", "", "Land — Urza's Power-Plant", "{T}: Add {C}. If you control an Urza's Mine and an Urza's Tower, add {C}{C} instead.")
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


if __name__ == "__main__":
    unittest.main()
