"""Popular creatures, second batch (Elesh Norn, Avacyn, Ragavan with Dash, Etali, Esper Sentinel, Ledger Shredder, Phyrexian
Metamorph ...), each from its own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, CAST_EXILE, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_triggers_80 import FOREST, PLAINS
from tests.test_x_targets import script

NORN = real("Elesh Norn, Grand Cenobite", "{5}{W}{W}", "Legendary Creature — Praetor",
            "Vigilance\nOther creatures you control get +2/+2.\nCreatures your opponents control get -2/-2.", "4", "7")
AVACYN = real("Avacyn, Angel of Hope", "{3}{W}{W}{W}", "Legendary Creature — Angel",
              "Flash\nFlying, vigilance, indestructible\nOther permanents you control have indestructible.", "8", "8")
BLOODLETTER = real("Bloodletter of Aclazotz", "{1}{B}{B}", "Creature — Vampire Demon",
                   "Flying\nIf an opponent would lose life during your turn, they lose twice that much life instead.", "2", "4")
OVERSEER = real("Steel Overseer", "{2}", "Artifact Creature — Construct", "{T}: Put a +1/+1 counter on each artifact creature you control.", "1", "1")
DANITHA = real("Danitha Capashen, Paragon", "{2}{W}", "Legendary Creature — Human Knight",
               "First strike, vigilance, lifelink\nAura and Equipment spells you cast cost {1} less to cast.", "2", "2")
ATTENDANT = real("Soul's Attendant", "{W}", "Creature — Human Cleric", "Whenever another creature enters, you may gain 1 life.", "1", "1")
AYARA = real("Ayara, First of Locthwain", "{B}{B}{B}", "Legendary Creature — Elf Noble",
             "Whenever Ayara or another black creature you control enters, each opponent loses 1 life and you gain 1 life.\n"
             "{T}, Sacrifice another black creature: Draw a card.", "2", "3", colors=("B",))
RAGAVAN = real("Ragavan, Nimble Pilferer", "{R}", "Legendary Creature — Monkey Pirate",
               "Whenever Ragavan deals combat damage to a player, create a Treasure token and exile the top card of that player's library. "
               "Until end of turn, you may cast that card.\nDash {1}{R}", "2", "1", colors=("R",))
ETALI = real("Etali, Primal Storm", "{4}{R}{R}", "Legendary Creature — Elder Dinosaur",
             "Whenever Etali attacks, exile the top card of each player's library, then you may cast any number of spells from among those cards "
             "without paying their mana costs.", "6", "6")
SENTINEL = real("Esper Sentinel", "{W}", "Artifact Creature — Human Soldier",
                "Whenever an opponent casts their first noncreature spell each turn, draw a card unless that player pays {X}, where X is this "
                "creature's power.", "1", "1")
SHREDDER = real("Ledger Shredder", "{1}{U}", "Creature — Bird Advisor",
                "Flying\nWhenever a player casts their second spell each turn, Ledger Shredder connives.", "1", "3")
METAMORPH = real("Phyrexian Metamorph", "{3}{U/P}", "Artifact Creature — Phyrexian Shapeshifter",
                 "You may have this creature enter as a copy of any artifact or creature on the battlefield, except it's an artifact in "
                 "addition to its other types.", "0", "0")
RECRUITER = real("Imperial Recruiter", "{2}{R}", "Creature — Human Scout",
                 "When this creature enters, search your library for a creature card with power 2 or less, reveal it, put it into your hand, then "
                 "shuffle.", "1", "1")

BEAR = real("Bear", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
THREE_TWO = real("Three Two", "{2}{G}", "Creature — Beast", "", "3", "2", colors=("G",))
BLACK_ELF = real("Black Elf", "{B}", "Creature — Elf", "", "1", "1", colors=("B",))
RED_GOBLIN = real("Red Goblin", "{R}", "Creature — Goblin", "", "1", "1", colors=("R",))
ROCK = real("Rock", "{1}", "Artifact", "")
ARTIFACT_CREATURE = real("Gearbot", "{2}", "Artifact Creature — Construct", "", "1", "1")
BOLT = real("Bolt", "{R}", "Instant", "Bolt deals 1 damage to any target.")
CANTRIP = real("Opt", "{U}", "Instant", "You gain 1 life.")
CANTRIP2 = real("Opt Two", "{U}", "Instant", "You gain 1 life.")
AURA = real("Pacifism", "{1}{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature can't attack or block.")
SWORD = real("Sword", "{3}", "Artifact — Equipment", "Equipped creature gets +1/+1.\nEquip {2}")


def board(*answers, theirs=()):
    game, _ = table3(script(*answers), script(*theirs))
    return game, *game.seats


class StaticTests(unittest.TestCase):
    def test_elesh_norn_shrinks_the_opponents_creatures_only(self):
        game, a, b, c = board()
        mine, theirs = Permanent(BEAR), Permanent(THREE_TWO)
        a.battlefield = [Permanent(NORN), mine]
        b.battlefield = [theirs]
        self.assertEqual(((game.power(mine), game.toughness(mine)), (game.power(theirs), game.toughness(theirs))), ((4, 4), (1, 0)))

    def test_a_creature_with_no_toughness_left_dies(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(NORN)]
        b.battlefield = [Permanent(THREE_TWO)]
        game._check_state()
        self.assertEqual(b.battlefield, [])

    def test_avacyn_makes_other_permanents_indestructible(self):
        game, a, b, c = board()
        avacyn, rock, land, bear = Permanent(AVACYN), Permanent(ROCK), Permanent(FOREST), Permanent(BEAR)
        theirs = Permanent(ROCK)
        a.battlefield = [avacyn, rock, land, bear]
        b.battlefield = [theirs]
        self.assertEqual([game.has_keyword(p, "indestructible") for p in (rock, land, bear, theirs)], [True, True, True, False])

    def test_a_creature_only_ability_does_not_reach_other_permanents(self):
        game, a, b, c = board()
        anthem = real("Haste Lord", "{2}", "Creature \u2014 Goblin", "Other creatures you control have haste.", "1", "1")
        rock, bear = Permanent(ROCK), Permanent(BEAR)
        a.battlefield = [Permanent(anthem), rock, bear]
        self.assertEqual((game.has_keyword(rock, "haste"), game.has_keyword(bear, "haste")), (False, True))

    def test_other_permanents_does_not_include_the_source(self):
        game, a, b, c = board()
        warden = real("Warden", "{2}", "Creature \u2014 Spirit", "Other permanents you control have hexproof.", "1", "1")
        source, rock = Permanent(warden), Permanent(ROCK)
        a.battlefield = [source, rock]
        self.assertEqual((game.has_keyword(source, "hexproof"), game.has_keyword(rock, "hexproof")), (False, True))

    def test_avacyn_destroying_a_permanent_does_nothing(self):
        game, a, b, c = board()
        rock = Permanent(ROCK)
        a.battlefield = [Permanent(AVACYN), rock]
        game.destroy(rock)
        game._check_state()
        self.assertIn(rock, a.battlefield)

    def test_without_avacyn_it_is_destroyed(self):
        game, a, b, c = board()
        rock = Permanent(ROCK)
        a.battlefield = [rock]
        game.destroy(rock)
        self.assertNotIn(rock, a.battlefield)

    def test_bloodletter_doubles_loss_during_its_controllers_turn(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(BLOODLETTER)]
        game.change_life(b, -3)
        self.assertEqual(b.life, 34)

    def test_not_on_another_players_turn_or_for_its_own_controller(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(BLOODLETTER)]
        game.change_life(a, -3)
        game.active = 1
        game.change_life(c, -3)
        self.assertEqual((a.life, c.life), (37, 37))

    def test_two_bloodletters_quadruple_it(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(BLOODLETTER), Permanent(BLOODLETTER)]
        game.change_life(b, -2)
        self.assertEqual(b.life, 32)

    def test_gaining_life_is_not_changed(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(BLOODLETTER)]
        game.change_life(b, 3)
        self.assertEqual(b.life, 43)

    def test_danitha_makes_auras_and_equipment_cheaper(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(DANITHA)]
        self.assertEqual([game.cost_reduction(a, x) for x in (AURA, SWORD, BEAR, ROCK)], [1, 1, 0, 0])

    def test_steel_overseer_pumps_each_artifact_creature(self):
        game, a, b, c = board()
        overseer, gearbot, bear = Permanent(OVERSEER, sick=False), Permanent(ARTIFACT_CREATURE), Permanent(BEAR)
        a.battlefield = [overseer, gearbot, bear]
        [action] = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Steel Overseer" in x]
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((overseer.counters.get("+1/+1"), gearbot.counters.get("+1/+1"), bear.counters), (1, 1, {}))


class TriggerTests(unittest.TestCase):
    def test_soul_attendant_may_gain_life_for_any_creature_that_enters(self):
        game, a, b, c = board("Yes", "Yes")
        a.battlefield = [Permanent(ATTENDANT)]
        game._enter(a, Permanent(BEAR))
        game._enter(b, Permanent(BEAR))
        run_stack(game)
        self.assertEqual(a.life, 42)

    def test_a_land_entering_is_not_a_creature(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(ATTENDANT)]
        game._enter(a, Permanent(FOREST))
        run_stack(game)
        self.assertEqual(a.life, 40)

    def test_or_not(self):
        game, a, b, c = board("No")
        a.battlefield = [Permanent(ATTENDANT)]
        game._enter(a, Permanent(BEAR))
        run_stack(game)
        self.assertEqual(a.life, 40)

    def test_ayara_drains_for_a_black_creature(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(AYARA)]
        game._enter(a, Permanent(BLACK_ELF))
        game._enter(a, Permanent(RED_GOBLIN))
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (41, 39, 39))

    def test_ayara_drains_when_she_herself_enters(self):
        game, a, b, c = board()
        game._enter(a, Permanent(AYARA))
        run_stack(game)
        self.assertEqual((a.life, b.life), (41, 39))

    def test_ayara_sacrifices_a_black_creature_to_draw(self):
        game, a, b, c = board("Black Elf")
        a.library = [FOREST] * 3
        a.battlefield = [Permanent(AYARA, sick=False), Permanent(BLACK_ELF), Permanent(RED_GOBLIN)]
        [action] = [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Ayara" in x]
        game._perform(a, action)
        run_stack(game)
        self.assertEqual((len(a.hand), [p.card.name for p in a.battlefield]), (1, ["Ayara, First of Locthwain", "Red Goblin"]))

    def test_ayara_cannot_sacrifice_a_creature_that_is_not_black(self):
        game, a, b, c = board()
        a.battlefield = [Permanent(AYARA, sick=False), Permanent(RED_GOBLIN)]
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Ayara" in x], [])


class RagavanTests(unittest.TestCase):
    def hit(self):
        game, a, b, c = board()
        ragavan = Permanent(RAGAVAN, sick=False)
        a.battlefield = ragavan, *lands(3)
        a.battlefield = [ragavan, *lands(3)]
        b.library = [BOLT, FOREST, FOREST]
        game.damage(b, 2, ragavan, combat=True)
        run_stack(game)
        return game, a, b

    def test_it_makes_a_treasure_and_exiles_the_top_card(self):
        game, a, b = self.hit()
        self.assertEqual(([p.card.name for p in a.battlefield if "Token" in p.card.type_line], [c.name for c in a.exile], len(b.library)),
                         (["Treasure"], ["Bolt"], 2))

    def test_the_card_can_be_cast_this_turn(self):
        game, a, b = self.hit()
        self.assertIn(CAST_EXILE + "Bolt", game.legal_actions(a))

    def test_but_not_later(self):
        game, a, b = self.hit()
        game.turn += 1
        self.assertNotIn(CAST_EXILE + "Bolt", game.legal_actions(a))

    def test_damage_to_a_creature_does_nothing(self):
        game, a, b, c = board()
        ragavan = Permanent(RAGAVAN, sick=False)
        a.battlefield = [ragavan]
        b.battlefield = [Permanent(THREE_TWO)]
        b.library = [BOLT]
        game.damage(b.battlefield[0], 2, ragavan, combat=True)
        run_stack(game)
        self.assertEqual((a.exile, len(b.library)), ([], 1))

    def test_dash_gives_haste_and_returns_it_to_hand(self):
        game, a, b, c = board("Dash")
        a.battlefield = lands(2)
        a.hand = [RAGAVAN]
        game._perform(a, CAST + "Ragavan, Nimble Pilferer")
        run_stack(game)
        ragavan = next(p for p in a.battlefield if p.card.name.startswith("Ragavan"))
        self.assertEqual((sum(p.tapped for p in a.battlefield), game.has_keyword(ragavan, "haste")), (2, True))
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual(([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], [x.name for x in a.hand]),
                         ([], ["Ragavan, Nimble Pilferer"]))

    def test_cast_normally_it_stays(self):
        game, a, b, c = board("Pay")
        a.battlefield = lands(1)
        a.hand = [RAGAVAN]
        game._perform(a, CAST + "Ragavan, Nimble Pilferer")
        run_stack(game)
        game.step = "end"
        game._turn_based_actions(a)
        self.assertEqual([p.card.name for p in a.battlefield if "Creature" in p.card.type_line], ["Ragavan, Nimble Pilferer"])


class EtaliTests(unittest.TestCase):
    def test_it_casts_the_spells_it_exiles_for_free(self):
        game, a, b, c = board("Bolt", "Player: B", "Opt")
        etali = Permanent(ETALI)
        a.battlefield = [etali]
        a.library = [BOLT, FOREST]
        b.library = [FOREST, BOLT]
        c.library = [CANTRIP, FOREST]
        game.trigger("attacks", etali, a)
        run_stack(game)
        self.assertEqual(([x.name for x in a.library], [x.name for x in b.library], [x.name for x in c.library]),
                         (["Forest"], ["Bolt"], ["Forest"]))
        self.assertEqual(([x.name for x in b.exile], a.life, b.life, sorted(x.name for x in a.graveyard + c.graveyard)),
                         (["Forest"], 41, 39, ["Bolt", "Opt"]))

    def test_it_may_stop_and_lands_are_not_cast(self):
        game, a, b, c = board("Take none")
        a.library = [FOREST]
        b.library = [BOLT]
        game.exile_top_of_each_cast_free(a)
        self.assertEqual(([x.name for x in a.exile], [x.name for x in b.exile], len(game.stack)), (["Forest"], ["Bolt"], 0))

    def test_an_empty_library_is_skipped(self):
        game, a, b, c = board("Take none")
        a.library = []
        b.library = [BOLT]
        game.exile_top_of_each_cast_free(a)
        self.assertEqual([x.name for x in b.exile], ["Bolt"])


class SentinelTests(unittest.TestCase):
    def cast(self, spell, pays, *more):
        game, a, b, c = board(theirs=("Player: A", "Pay" if pays else "Don't", "Player: A"))
        a.battlefield = [Permanent(SENTINEL)]
        a.library = [FOREST] * 5
        b.battlefield = lands(4)
        b.hand = [spell, *more]
        game.active = 1
        for card in [spell, *more]:
            game._perform(b, CAST + card.name)
            run_stack(game)
        return a

    def test_an_opponents_first_noncreature_spell_draws_a_card(self):
        self.assertEqual(len(self.cast(BOLT, False).hand), 1)

    def test_unless_they_pay_its_power(self):
        a = self.cast(BOLT, True)
        self.assertEqual(a.hand, [])

    def test_the_price_is_its_power(self):
        big = real("Big Sentinel", "{W}", "Artifact Creature \u2014 Human Soldier", SENTINEL.oracle_text, "3", "3")
        for lands_left, draws in ((2, 1), (3, 0)):
            game, a, b, c = board(theirs=("Player: A", "Pay"))
            a.battlefield = [Permanent(big)]
            a.library = [FOREST] * 5
            b.battlefield = lands(1 + lands_left)
            b.hand = [BOLT]
            game.active = 1
            game._perform(b, CAST + "Bolt")
            run_stack(game)
            self.assertEqual(len(a.hand), draws, lands_left)

    def test_it_pays_with_mana_it_has(self):
        game, a, b, c = board(theirs=("Player: A", "Pay"))
        a.battlefield = [Permanent(SENTINEL)]
        a.library = [FOREST] * 5
        b.battlefield = lands(1)
        b.hand = [BOLT]
        game.active = 1
        game._perform(b, CAST + "Bolt")
        run_stack(game)
        self.assertEqual(len(a.hand), 1)  # the one land paid for the spell itself: nothing left for {1}

    def test_a_creature_spell_does_not_count(self):
        self.assertEqual(self.cast(real("Elf", "{R}", "Creature — Elf", "", "1", "1"), False).hand, [])

    def test_only_the_first_noncreature_spell_each_turn(self):
        self.assertEqual(len(self.cast(BOLT, False, real("Bolt Two", "{R}", "Instant", "Bolt Two deals 1 damage to any target.")).hand), 1)


class ConniveTests(unittest.TestCase):
    def two_spells(self, discard, library):
        game, a, b, c = board(discard)
        shredder = Permanent(SHREDDER)
        a.battlefield = [shredder] + lands(3)
        a.library = library
        a.hand = [CANTRIP, CANTRIP2]
        for card in (CANTRIP, CANTRIP2):
            game._perform(a, CAST + card.name)
            run_stack(game)
        return a, shredder

    def test_the_second_spell_connives(self):
        a, shredder = self.two_spells("Bolt", [BOLT, FOREST, FOREST])
        self.assertEqual((shredder.counters.get("+1/+1"), sorted(x.name for x in a.graveyard)), (1, ["Bolt", "Opt", "Opt Two"]))

    def test_discarding_a_land_gives_no_counter(self):
        a, shredder = self.two_spells("Forest", [FOREST, BOLT, FOREST])
        self.assertEqual((shredder.counters.get("+1/+1"), a.hand), (None, []))

    def test_the_first_spell_does_not(self):
        game, a, b, c = board()
        shredder = Permanent(SHREDDER)
        a.battlefield = [shredder] + lands(2)
        a.library = [BOLT, FOREST]
        a.hand = [CANTRIP]
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual((shredder.counters, len(a.library)), ({}, 2))

    def test_any_players_second_spell_counts(self):
        game, a, b, c = board("Bolt")
        shredder = Permanent(SHREDDER)
        a.battlefield = [shredder]
        a.library = [BOLT, FOREST]
        b.battlefield = lands(3)
        b.hand = [CANTRIP, CANTRIP2]
        game.active = 1
        for card in (CANTRIP, CANTRIP2):
            game._perform(b, CAST + card.name)
            run_stack(game)
        self.assertEqual(shredder.counters.get("+1/+1"), 1)


class CloneAndSearchTests(unittest.TestCase):
    def test_metamorph_copies_a_creature_and_is_an_artifact_too(self):
        game, a, b, c = board("Bear")
        a.battlefield = [Permanent(BEAR)]
        meta = Permanent(METAMORPH)
        game._enter(a, meta)
        self.assertEqual((meta.card.name, meta.card.type_line, game.power(meta)), ("Bear", "Artifact Creature — Bear", 2))

    def test_metamorph_copies_an_artifact(self):
        game, a, b, c = board("Rock")
        a.battlefield = [Permanent(ROCK)]
        meta = Permanent(METAMORPH)
        game._enter(a, meta)
        self.assertEqual((meta.card.name, meta.card.type_line), ("Rock", "Artifact"))

    def test_an_artifact_creature_does_not_get_artifact_twice(self):
        game, a, b, c = board("Gearbot")
        a.battlefield = [Permanent(ARTIFACT_CREATURE)]
        meta = Permanent(METAMORPH)
        game._enter(a, meta)
        self.assertEqual(meta.card.type_line, "Artifact Creature — Construct")

    def test_it_goes_to_the_graveyard_as_the_metamorph(self):
        game, a, b, c = board("Bear")
        a.battlefield = [Permanent(BEAR)]
        meta = Permanent(METAMORPH)
        game._enter(a, meta)
        game.destroy(meta)
        self.assertEqual([x.name for x in a.graveyard], ["Phyrexian Metamorph"])

    def test_the_recruiter_finds_only_a_creature_with_power_two_or_less(self):
        game, a, b, c = board("Bear")
        seen = []
        game.seats[0].player.policy = lambda prompt, options: (seen.append(list(options)), options.index("Bear"))[1]
        a.library = [THREE_TWO, BEAR, BOLT, FOREST]
        game._enter(a, Permanent(RECRUITER))
        run_stack(game)
        self.assertEqual(([x.name for x in a.hand], seen[0]), (["Bear"], ["Bear"]))


class CardsTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        cards = (NORN, AVACYN, BLOODLETTER, OVERSEER, DANITHA, ATTENDANT, AYARA, RAGAVAN, ETALI, SENTINEL, SHREDDER, METAMORPH, RECRUITER)
        self.assertEqual({c.name: unsupported_lines(c) for c in cards if unsupported_lines(c)}, {})


if __name__ == "__main__":
    unittest.main()
