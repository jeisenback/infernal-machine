"""The fourth batch of cards whose every effect the engine already had, read from new wordings (each picked with Forge's card scripts),
from their real Oracle text: "Destroy all nonartifact creatures" and "with no counters on them", land cards returned tapped, thirteen
tokens, a sentence that opens with "Until end of turn,", "Exile each opponent's graveyard", life for each colorless creature or each
creature with power 4 or greater (Ferocious), mana for each counter, for each point of power, for each basic Swamp and for each black
creature card, "Other enchantments you control" and "Enchanted creatures you control", "All Zombies gain ...", Shriekmaw's target,
Murderous Rider's trip to the bottom of the library, winning with 40 life or thirteen cards in hand, statics while you have 25 or 30
life, "Activate only if you control a legendary creature", mana granted to tokens and Foods, and artifact creatures' combat damage."""

import dataclasses
import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import (BEAR, BIG, FOREST, OGRE, RELIC, SPIRIT, SWAMP, activate, attack_all, end_turn, lands, real, run_stack, table,
                           table3, take_turn_attacking)

EXTINCTION = real("Their Name Is Death", "{3}{B}{B}{B}", "Sorcery", "Destroy all nonartifact creatures.", colors=("B",))
ORGANIC = real("Organic Extinction", "{8}{W}{W}", "Sorcery", "Improvise (Your artifacts can help cast this spell. Each artifact you "
               "tap after you're done activating mana abilities pays for {1}.)\nDestroy all nonartifact creatures.", colors=("W",))
VERDICT = real("Damning Verdict", "{3}{W}{W}", "Sorcery", "Destroy all creatures with no counters on them.", colors=("W",))
RECLAMATION = real("Splendid Reclamation", "{3}{G}", "Sorcery", "Return all land cards from your graveyard to the battlefield tapped.",
                   colors=("G",))
ANALYST = real("Aftermath Analyst", "{1}{G}", "Creature — Elf Detective", "When this creature enters, mill three cards. (Put the top "
               "three cards of your library into your graveyard.)\n{3}{G}, Sacrifice this creature: Return all land cards from your "
               "graveyard to the battlefield tapped.", "1", "3", colors=("G",))
WORLD_SHAPER = real("World Shaper", "{3}{G}", "Creature — Merfolk Shaman", "Whenever this creature attacks, you may mill three "
                    "cards.\nWhen this creature dies, return all land cards from your graveyard to the battlefield tapped.", "3", "3",
                    colors=("G",))
ARMY = real("Army of the Damned", "{5}{B}{B}{B}", "Sorcery", "Create thirteen tapped 2/2 black Zombie creature tokens.\nFlashback "
            "{7}{B}{B}{B} (You may cast this card from your graveyard for its flashback cost. Then exile it.)", colors=("B",))
TRIUMPH = real("Triumph of the Hordes", "{2}{G}{G}", "Sorcery", "Until end of turn, creatures you control get +1/+1 and gain trample "
               "and infect. (Creatures with infect deal damage to creatures in the form of -1/-1 counters and to players in the form "
               "of poison counters.)", colors=("G",))
RESPLENDENT = real("Resplendent Angel", "{1}{W}{W}", "Creature — Angel", "Flying\nAt the beginning of each end step, if you gained 5 "
                   "or more life this turn, create a 4/4 white Angel creature token with flying and vigilance.\n{3}{W}{W}{W}: Until end "
                   "of turn, this creature gets +2/+2 and gains lifelink.", "3", "3", colors=("W",))
LANTERN = real("Soul-Guide Lantern", "{1}", "Artifact", "When this artifact enters, exile target card from a graveyard.\n{T}, "
               "Sacrifice this artifact: Exile each opponent's graveyard.\n{1}, {T}, Sacrifice this artifact: Draw a card.")
TOMB = real("Tomb of the Spirit Dragon", "", "Land", "{T}: Add {C}.\n{2}, {T}: You gain 1 life for each colorless creature you "
            "control.")
REVELATION = real("Shamanic Revelation", "{3}{G}{G}", "Sorcery", "Draw a card for each creature you control.\nFerocious — You gain 4 "
                  "life for each creature you control with power 4 or greater.", colors=("G",))
GYRE = real("Gyre Sage", "{1}{G}", "Creature — Elf Druid", "Evolve (Whenever a creature you control enters, if that creature has "
            "greater power or toughness than this creature, put a +1/+1 counter on this creature.)\n{T}: Add {G} for each +1/+1 "
            "counter on this creature.", "1", "2", colors=("G",))
MARWYN = real("Marwyn, the Nurturer", "{2}{G}", "Legendary Creature — Elf Druid", "Whenever another Elf you control enters, put a "
              "+1/+1 counter on Marwyn.\n{T}: Add an amount of {G} equal to Marwyn's power.", "1", "1", colors=("G",))
STRONGHOLD = dataclasses.replace(real("Cabal Stronghold", "", "Land", "{T}: Add {C}.\n{3}, {T}: Add {B} for each basic Swamp you "
                                        "control."), produced_mana=("B", "C"))  # as Scryfall gives it
CRYPT = dataclasses.replace(real("Crypt of Agadeem", "", "Land", "This land enters tapped.\n{T}: Add {B}.\n{2}, {T}: Add {B} for "
                                   "each black creature card in your graveyard."), produced_mana=("B",))
GROVE = real("Sterling Grove", "{G}{W}", "Enchantment", "Other enchantments you control have shroud. (They can't be the targets of "
             "spells or abilities.)\n{1}, Sacrifice this enchantment: Search your library for an enchantment card, reveal it, then "
             "shuffle and put that card on top.", colors=("G", "W"))
AURAMANCY = real("Greater Auramancy", "{1}{W}", "Enchantment", "Other enchantments you control have shroud. (A permanent with shroud "
                 "can't be the target of spells or abilities.)\nEnchanted creatures you control have shroud.", colors=("W",))
ACCURSED = real("Lord of the Accursed", "{2}{B}", "Creature — Zombie", "Other Zombies you control get +1/+1.\n{1}{B}, {T}: All Zombies "
                "gain menace until end of turn.", "2", "3", colors=("B",))
SHRIEKMAW = real("Shriekmaw", "{4}{B}", "Creature — Elemental", "Fear (This creature can't be blocked except by artifact creatures "
                 "and/or black creatures.)\nWhen this creature enters, destroy target nonartifact, nonblack creature.\nEvoke {1}{B} "
                 "(You may cast this spell for its evoke cost. If you do, it's sacrificed when it enters.)", "3", "2", colors=("B",))
RIDER = real("Murderous Rider", "{1}{B}{B}", "Creature — Zombie Knight", "Lifelink\nWhen this creature dies, put it on the bottom of "
             "its owner's library.", "2", "3", colors=("B",))
FELIDAR = real("Felidar Sovereign", "{4}{W}{W}", "Creature — Cat Beast", "Vigilance (Attacking doesn't cause this creature to "
               "tap.)\nLifelink (Damage dealt by this creature also causes you to gain that much life.)\nAt the beginning of your "
               "upkeep, if you have 40 or more life, you win the game.", "4", "6", colors=("W",))
ENDURANCE = real("Test of Endurance", "{2}{W}{W}", "Enchantment", "At the beginning of your upkeep, if you have 50 or more life, you "
                 "win the game.", colors=("W",))
TRISKAIDEKAPHILE = real("Triskaidekaphile", "{1}{U}", "Creature — Human Wizard", "You have no maximum hand size.\nAt the beginning "
                        "of your upkeep, if you have exactly thirteen cards in your hand, you win the game.\n{3}{U}: Draw a card.",
                        "1", "3", colors=("U",))
VITALITY = real("Angel of Vitality", "{2}{W}", "Creature — Angel", "Flying\nIf you would gain life, you gain that much life plus 1 "
                "instead.\nThis creature gets +2/+2 as long as you have 25 or more life.", "2", "2", colors=("W",))
ASCENDANT = real("Serra Ascendant", "{W}", "Creature — Human Monk", "Lifelink (Damage dealt by this creature also causes you to gain "
                 "that much life.)\nAs long as you have 30 or more life, this creature gets +5/+5 and has flying.", "1", "1",
                 colors=("W",))
RIVENDELL = real("Rivendell", "", "Legendary Land", "Rivendell enters tapped unless you control a legendary creature.\n{T}: Add "
                 "{U}.\n{1}{U}, {T}: Scry 2. Activate only if you control a legendary creature.")
JAHEIRA = real("Jaheira, Friend of the Forest", "{2}{G}", "Legendary Creature — Human Elf Druid", 'Tokens you control have "{T}: Add '
               '{G}."\nChoose a Background (You can have a Background as a second commander.)', "2", "3", colors=("G",))
PARADE = real("Springleaf Parade", "{X}{G}{G}", "Enchantment", "When this enchantment enters, create X 1/1 colorless Shapeshifter "
              "creature tokens with changeling. (They're every creature type.)\nCreature tokens you control have \"{T}: Add one mana "
              "of any color.\"", colors=("G",))
SWEETS = real("Night of the Sweets' Revenge", "{3}{G}", "Enchantment", "When this enchantment enters, create a Food token. (It's an "
              "artifact with \"{2}, {T}, Sacrifice this token: You gain 3 life.\")\nFoods you control have \"{T}: Add {G}.\"\n{5}{G}{G}, "
              "Sacrifice this enchantment: Creatures you control get +X/+X until end of turn, where X is the number of Foods you "
              "control. Activate only as a sorcery.", colors=("G",))
SPY_NETWORK = real("Thopter Spy Network", "{2}{U}{U}", "Enchantment", "At the beginning of your upkeep, if you control an artifact, "
                   "create a 1/1 colorless Thopter artifact creature token with flying.\nWhenever one or more artifact creatures you "
                   "control deal combat damage to a player, draw a card.", colors=("U",))
CARDS = (EXTINCTION, ORGANIC, VERDICT, RECLAMATION, ANALYST, WORLD_SHAPER, ARMY, TRIUMPH, RESPLENDENT, LANTERN, TOMB, REVELATION,
         GYRE, MARWYN, STRONGHOLD, CRYPT, GROVE, AURAMANCY, ACCURSED, SHRIEKMAW, RIDER, FELIDAR, ENDURANCE, TRISKAIDEKAPHILE, VITALITY,
         ASCENDANT, RIVENDELL, JAHEIRA, PARADE, SWEETS, SPY_NETWORK)

THOPTER = real("Memnite", "{0}", "Artifact Creature — Construct", "", "1", "1")
GREEN = real("Grizzly Bears", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
ZOMBIE = real("Walking Corpse", "{1}{B}", "Creature — Zombie", "", "2", "2", colors=("B",))
LEGEND = real("Isamaru, Hound of Konda", "{W}", "Legendary Creature — Dog", "", "2", "2", colors=("W",))
SHRINE = real("Shrine", "{2}", "Enchantment", "")
AURA = real("Holy Strength", "{W}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +1/+2.", colors=("W",))
FOOD = Card(name="Food", type_line="Token Artifact — Food", oracle_text="{2}, {T}, Sacrifice this artifact: You gain 3 life.")
SNOW_SWAMP = Card(name="Snow Swamp", type_line="Land — Swamp", produced_mana=("B",))  # a Swamp, but not a basic one


def step(game, seat, name):
    game.active, game.step = seat.index, name
    game._turn_based_actions(seat)
    run_stack(game)


def cast(game, seat, card):
    seat.battlefield += lands(10)
    seat.hand.append(card)
    game._perform(seat, CAST + card.name)
    run_stack(game)


def made(game, seat, permanent):
    return sorted("".join(sorted(s.types)) for s in game._mana_sources(seat) if s.permanent is permanent)


def payable(game, seat, cost):
    return game._payment(seat, Card(name="Probe", mana_cost=cost, type_line="Sorcery")) is not None


class ParseOnlyBatch4Tests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_their_name_is_death_spares_artifact_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear, thopter, ogre = Permanent(BEAR), Permanent(THOPTER), Permanent(OGRE)
        b.battlefield = [bear, thopter, ogre]
        cast(game, a, EXTINCTION)
        self.assertEqual([p.card.name for p in b.battlefield], ["Memnite"])

    def test_damning_verdict_spares_creatures_with_counters(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        ogre.counters["-1/-1"] = 1
        b.battlefield = [bear, ogre]
        cast(game, a, VERDICT)
        self.assertEqual([p.card.name for p in b.battlefield], ["Ogre"])

    def test_splendid_reclamation_returns_only_the_lands_tapped(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard = [FOREST, SWAMP, BEAR]
        cast(game, a, RECLAMATION)
        back = [p for p in a.battlefield if p.card in (FOREST, SWAMP)]
        self.assertEqual(([p.card.name for p in back], [p.tapped for p in back]), (["Forest", "Swamp"], [True, True]))
        self.assertEqual([c.name for c in a.graveyard], ["Bear", "Splendid Reclamation"])

    def test_army_of_the_damned_makes_thirteen_tapped_zombies(self):
        game, _ = table3()
        a = game.seats[0]
        cast(game, a, ARMY)
        zombies = [p for p in a.battlefield if p.card.name == "Zombie"]
        self.assertEqual((len(zombies), all(p.tapped for p in zombies)), (13, True))

    def test_triumph_of_the_hordes_pumps_only_your_creatures_until_end_of_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear, theirs = Permanent(BEAR), Permanent(BEAR)
        a.battlefield, b.battlefield = [bear], [theirs]
        cast(game, a, TRIUMPH)
        self.assertEqual((game.power(bear), game.has_keyword(bear, "trample"), game.has_keyword(bear, "infect")), (3, True, True))
        self.assertEqual((game.power(theirs), game.has_keyword(theirs, "infect")), (2, False))
        end_turn(game, a)
        self.assertEqual((game.power(bear), game.has_keyword(bear, "infect")), (2, False))

    def test_resplendent_angel_pumps_itself_until_end_of_turn(self):
        game, _ = table3()
        a = game.seats[0]
        angel = Permanent(RESPLENDENT)
        a.battlefield = [angel] + lands(6)
        activate(game, a, "{3}{W}{W}{W}")
        self.assertEqual((game.power(angel), game.toughness(angel), game.has_keyword(angel, "lifelink")), (5, 5, True))

    def test_soul_guide_lantern_exiles_only_the_opponents_graveyards(self):
        game, _ = table3()
        a, b, c = game.seats
        a.graveyard, b.graveyard, c.graveyard = [BEAR], [OGRE], [FOREST]
        a.battlefield = [Permanent(LANTERN)]
        activate(game, a, "Exile each opponent's graveyard")
        self.assertEqual(([x.name for x in a.graveyard], b.graveyard, c.graveyard), (["Bear", "Soul-Guide Lantern"], [], []))

    def test_tomb_of_the_spirit_dragon_counts_colorless_creatures(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(TOMB), Permanent(THOPTER), Permanent(THOPTER), Permanent(GREEN)] + lands(2)
        life = a.life
        activate(game, a, "You gain 1 life")
        self.assertEqual(a.life, life + 2)

    def test_shamanic_revelation_gains_4_for_each_creature_with_power_4_or_greater(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [FOREST] * 5
        a.battlefield = [Permanent(BEAR), Permanent(OGRE), Permanent(BIG)]
        life = a.life
        cast(game, a, REVELATION)
        self.assertEqual((len(a.hand), a.life), (3, life + 4))  # three creatures; only the 5/5 has power 4 or greater

    def test_gyre_sage_makes_a_green_for_each_counter(self):
        game, _ = table3()
        a = game.seats[0]
        sage = Permanent(GYRE)
        a.battlefield = [sage]
        self.assertEqual(made(game, a, sage), [])
        sage.counters["+1/+1"] = 3
        self.assertEqual(made(game, a, sage), ["G", "G", "G"])
        sage.sick = True  # it came in this turn: no {T}
        self.assertEqual(made(game, a, sage), [])

    def test_marwyn_makes_green_equal_to_her_power(self):
        game, _ = table3()
        a = game.seats[0]
        marwyn = Permanent(MARWYN)
        marwyn.counters["+1/+1"] = 2
        a.battlefield = [marwyn]
        self.assertEqual(made(game, a, marwyn), ["G", "G", "G"])

    def test_cabal_stronghold_counts_only_basic_swamps(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(STRONGHOLD)] + [Permanent(FOREST)] * 3 + [Permanent(SWAMP), Permanent(SWAMP), Permanent(SNOW_SWAMP)]
        # The Forests pay the {3}; the Stronghold makes {B}{B}, for the two basic Swamps; the Swamps add {B}{B} and the Snow Swamp {B}.
        self.assertTrue(payable(game, a, "{B}{B}{B}{B}{B}"))
        self.assertFalse(payable(game, a, "{B}{B}{B}{B}{B}{B}"))

    def test_crypt_of_agadeem_counts_black_creature_cards_in_the_graveyard(self):
        game, _ = table3()
        a = game.seats[0]
        a.graveyard = [ZOMBIE, ZOMBIE, BEAR]
        a.battlefield = [Permanent(CRYPT)] + [Permanent(FOREST)] * 2
        self.assertTrue(payable(game, a, "{B}{B}"))
        self.assertFalse(payable(game, a, "{B}{B}{B}"))  # the colorless Bear doesn't count, and the Crypt taps once

    def test_sterling_grove_gives_shroud_to_your_other_enchantments(self):
        game, _ = table3()
        a, b, _ = game.seats
        grove, shrine, bear, theirs = Permanent(GROVE), Permanent(SHRINE), Permanent(BEAR), Permanent(SHRINE)
        a.battlefield, b.battlefield = [grove, shrine, bear], [theirs]
        self.assertEqual([game.has_keyword(p, "shroud") for p in (grove, shrine, bear, theirs)], [False, True, False, False])

    def test_greater_auramancy_gives_shroud_to_your_enchanted_creatures(self):
        game, _ = table3()
        a = game.seats[0]
        enchanted, bear = Permanent(OGRE), Permanent(BEAR)
        aura = Permanent(AURA, attached_to=enchanted)
        a.battlefield = [Permanent(AURAMANCY), enchanted, bear, aura]
        self.assertEqual([game.has_keyword(p, "shroud") for p in (enchanted, bear, aura)], [True, False, True])

    def test_lord_of_the_accursed_gives_every_zombie_menace(self):
        game, _ = table3()
        a, b, _ = game.seats
        lord, bear, theirs = Permanent(ACCURSED), Permanent(BEAR), Permanent(ZOMBIE)
        a.battlefield, b.battlefield = [lord, bear] + lands(2), [theirs]
        activate(game, a, "All Zombies gain menace")
        self.assertEqual([game.has_keyword(p, "menace") for p in (lord, bear, theirs)], [True, False, True])

    def test_shriekmaw_targets_neither_artifact_nor_black_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        b.battlefield = [Permanent(c) for c in (BEAR, THOPTER, ZOMBIE)]
        kind = "nonartifact, nonblack creature"
        self.assertEqual([game.is_legal_target(kind, p, a) for p in b.battlefield], [True, False, False])

    def test_murderous_rider_goes_to_the_bottom_of_its_library(self):
        game, _ = table3()
        a = game.seats[0]
        rider = Permanent(RIDER)
        a.battlefield, a.library = [rider], [FOREST, FOREST]
        game.destroy(rider)
        run_stack(game)
        self.assertEqual((a.library[-1].name, [c.name for c in a.graveyard]), ("Murderous Rider", []))

    def test_felidar_sovereign_wins_only_with_40_life(self):
        for life, wins in ((39, False), (40, True)):
            game, _ = table3()
            a = game.seats[0]
            a.battlefield, a.life = [Permanent(FELIDAR)], life
            step(game, a, "upkeep")
            self.assertEqual(a.wins_game, wins, life)

    def test_test_of_endurance_wins_only_with_50_life(self):
        for life, wins in ((49, False), (50, True)):
            game, _ = table3()
            a = game.seats[0]
            a.battlefield, a.life = [Permanent(ENDURANCE)], life
            step(game, a, "upkeep")
            self.assertEqual(a.wins_game, wins, life)

    def test_triskaidekaphile_wins_with_exactly_thirteen_cards(self):
        for count, wins in ((12, False), (13, True), (14, False)):
            game, _ = table3()
            a = game.seats[0]
            a.battlefield, a.hand = [Permanent(TRISKAIDEKAPHILE)], [FOREST] * count
            step(game, a, "upkeep")
            self.assertEqual(a.wins_game, wins, count)

    def test_angel_of_vitality_and_serra_ascendant_grow_with_enough_life(self):
        game, _ = table3()
        a = game.seats[0]
        angel, monk = Permanent(VITALITY), Permanent(ASCENDANT)
        a.battlefield, a.life = [angel, monk], 24
        self.assertEqual((game.power(angel), game.power(monk), game.has_keyword(monk, "flying")), (2, 1, False))
        a.life = 25
        self.assertEqual((game.power(angel), game.power(monk)), (4, 1))
        a.life = 30
        self.assertEqual((game.power(monk), game.toughness(monk), game.has_keyword(monk, "flying")), (6, 6, True))

    def test_rivendell_scries_only_with_a_legendary_creature(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(RIVENDELL), Permanent(BEAR)] + lands(2)
        self.assertFalse(any("Scry 2" in action for action in game.legal_actions(a)))
        a.battlefield.append(Permanent(LEGEND))
        self.assertTrue(any("Scry 2" in action for action in game.legal_actions(a)))

    def test_jaheira_gives_tokens_a_green_mana_ability(self):
        game, _ = table3()
        a = game.seats[0]
        spirit, bear = Permanent(SPIRIT), Permanent(BEAR)
        a.battlefield = [Permanent(JAHEIRA), spirit, bear]
        self.assertEqual((made(game, a, spirit), made(game, a, bear)), (["G"], []))

    def test_springleaf_parade_gives_creature_tokens_any_color_but_not_a_food(self):
        game, _ = table3()
        a = game.seats[0]
        spirit, food = Permanent(SPIRIT), Permanent(FOOD)
        a.battlefield = [Permanent(PARADE), spirit, food]
        self.assertEqual((made(game, a, spirit), made(game, a, food)), (["BGRUW"], []))

    def test_night_of_the_sweets_revenge_gives_foods_a_green_mana_ability(self):
        game, _ = table3()
        a = game.seats[0]
        food, relic = Permanent(FOOD), Permanent(RELIC)
        a.battlefield = [Permanent(SWEETS), food, relic]
        self.assertEqual((made(game, a, food), made(game, a, relic)), (["G"], []))

    def test_thopter_spy_network_draws_only_for_artifact_creatures(self):
        for attackers, drawn in (([BEAR], 0), ([BEAR, THOPTER], 1)):
            game, _, _ = table(attack_all)
            a = game.seats[0]
            a.battlefield = [Permanent(SPY_NETWORK)] + [Permanent(c) for c in attackers]
            a.library = [FOREST] * 5
            take_turn_attacking(game, a)
            self.assertEqual(len(a.hand), 1 + drawn, attackers)  # the draw step's card, and the Network's


if __name__ == "__main__":
    unittest.main()
