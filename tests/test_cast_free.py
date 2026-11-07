"""Casting without paying the mana cost (#655), from the cards' real Oracle text: Buster Sword (a spell from the hand up to the combat
damage), Etali, Primal Conqueror (each player exiles until a nonland card; cast any number of them) and its back face (poison equal to the
damage), Isochron Scepter (imprint an instant, then cast copies of it), Mizzix's Mastery (copies of a graveyard spell, or of all of them
when overloaded), Beseech the Mirror (cast the card found if bargained and cheap enough, else take it) and Dauthi Voidwalker (an
opponent's cards are exiled with void counters; play one for free). Batch 2: Omniscience and One with the Multiverse (a free way to cast),
Electrodominance (a spell up to X), Malcolm, Alluring Scoundrel (the discarded card, with four chorus counters), Gix, Yawgmoth Praetor
(pay 1 life to draw; play the cards exiled with Discard X) and Fallen Shinobi (play the damaged player's top two cards free). Batch 3:
Dracogenesis (Dragon spells free), Descendants' Path (a creature sharing a type, or the bottom), Improvisation Capstone (exile to a total
mana value; Paradigm), Arcane Bombardment (copies of every card exiled with it), Aminatou's Augury (a land, then one spell of each type)
and Mind's Dilation (the opponent's top card, if nonland). Batch 4: Jodah, the Unifier (a legendary anthem and a legendary cascade),
Cemetery Tampering (a Hideaway played at twenty cards in the graveyard), Gríma, Saruman's Footman (an instant or sorcery from the damaged
player's library), Geode Golem (the commander, free but for its tax), Planetarium of Wan Shi Tong (the top card, once a turn) and Ignite the
Future (free when flashed back). Batch 5: Mind's Desire, Breaching Dragonstorm, Mnemonic Deluge, Fight Rigging, Aetherworks Marvel and
Invoke Calamity. Batch 6: Kefka, Dancing Mad, Chaos Wand, Memory Plunder, Possibility Storm and Clive's Hideaway. Villainous choice:
Ensnared by the Mara. Court of Locthwain (a card played for as long as it stays exiled, with mana of any type; free while the monarch)."""

import unittest
from dataclasses import replace

from infernal_machine.effects import FREE_WAY
from infernal_machine.game import CAST, CAST_COMMANDER, COST_PROMPT, KICKER_PROMPT, PARADIGM_PROMPT, X_PROMPT, Permanent
from infernal_machine.analysis import is_land
from infernal_machine.zones import CAST_EXILE, CAST_TOP, PLAY_EXILE
from infernal_machine.report import unsupported_lines
from tests.helpers import ANTHEM, BEAR, BIG, COMMANDER, ELF, MOUNTAIN, OGRE, RAINBOW, RELIC, SWAMP, activate, enter, fire, lands, pick, real, run_stack, table3

SWORD = real("Buster Sword", "{3}", "Artifact — Equipment", "Equipped creature gets +3/+2.\nWhenever equipped creature deals combat "
             "damage to a player, draw a card, then you may cast a spell from your hand with mana value less than or equal to that damage "
             "without paying its mana cost.\nEquip {2}")
ETALI = real("Etali, Primal Conqueror", "{5}{R}{R}", "Legendary Creature — Elder Dinosaur", "Trample\nWhen Etali enters, each player "
             "exiles cards from the top of their library until they exile a nonland card. You may cast any number of spells from among the "
             "nonland cards exiled this way without paying their mana costs.\n{9}{G/P}: Transform Etali. Activate only as a sorcery.",
             "7", "7", colors=("R",))
SICKNESS = real("Etali, Primal Sickness", "", "Legendary Creature — Phyrexian Elder Dinosaur", "Trample, indestructible\nWhenever Etali "
                "deals combat damage to a player, they get that many poison counters. (A player with ten or more poison counters loses the "
                "game.)", "11", "11", colors=("G", "R"))
SCEPTER = real("Isochron Scepter", "{2}", "Artifact", "Imprint — When this artifact enters, you may exile an instant card with mana value 2 "
               "or less from your hand.\n{2}, {T}: You may copy the exiled card. If you do, you may cast the copy without paying its mana "
               "cost.")
MASTERY = real("Mizzix's Mastery", "{3}{R}", "Sorcery", "Exile target card that's an instant or sorcery from your graveyard. For each card "
               "exiled this way, copy it, and you may cast the copy without paying its mana cost. Exile Mizzix's Mastery.\nOverload "
               "{5}{R}{R}{R} (You may cast this spell for its overload cost. If you do, change \"target\" in its text to \"each.\")",
               colors=("R",))
BESEECH = real("Beseech the Mirror", "{1}{B}{B}{B}", "Sorcery", "Bargain (You may sacrifice an artifact, enchantment, or token as you cast "
               "this spell.)\nSearch your library for a card, exile it face down, then shuffle. If this spell was bargained, you may cast "
               "the exiled card without paying its mana cost if that spell's mana value is 4 or less. Put the exiled card into your hand "
               "if it wasn't cast this way.", colors=("B",))
DAUTHI = real("Dauthi Voidwalker", "{B}{B}", "Creature — Dauthi Rogue", "Shadow (This creature can block or be blocked by only creatures "
              "with shadow.)\nIf a card would be put into an opponent's graveyard from anywhere, instead exile it with a void counter on "
              "it.\n{T}, Sacrifice this creature: Choose an exiled card an opponent owns with a void counter on it. You may play it this "
              "turn without paying its mana cost.", "3", "2", colors=("B",))
OPT = real("Opt", "{U}", "Instant", "Scry 1.\nDraw a card.", colors=("U",))
THREE = real("Three Drop", "{2}{U}", "Sorcery", "Draw a card.", colors=("U",))
FOUR = real("Four Drop", "{3}{U}", "Instant", "Draw a card.", colors=("U",))
PONDER = real("Cheap Sorcery", "{U}", "Sorcery", "Draw a card.", colors=("U",))
LEYLINE = real("Leyline of the Void", "{2}{B}{B}", "Enchantment", "If Leyline of the Void is in your opening hand, you may begin the game "
                "with it on the battlefield.\nIf a card would be put into an opponent's graveyard from anywhere, exile it instead.",
                colors=("B",))
FOREST = real("Forest", "", "Basic Land — Forest", "({T}: Add {G}.)")

OMNISCIENCE = real("Omniscience", "{7}{U}{U}{U}", "Enchantment", "You may cast spells from your hand without paying their mana costs.",
                   colors=("U",))
MULTIVERSE = real("One with the Multiverse", "{6}{U}{U}", "Enchantment", "You may look at the top card of your library any time.\nYou may "
                  "play lands and cast spells from the top of your library.\nOnce during each of your turns, you may cast a spell from your "
                  "hand or the top of your library without paying its mana cost.", colors=("U",))
ELECTRO = real("Electrodominance", "{X}{R}{R}", "Instant", "Electrodominance deals X damage to any target. You may cast a spell with mana "
               "value X or less from your hand without paying its mana cost.", colors=("R",))
MALCOLM = real("Malcolm, Alluring Scoundrel", "{1}{U}", "Legendary Creature — Siren Pirate", "Flash\nFlying\nWhenever Malcolm deals combat "
               "damage to a player, put a chorus counter on it. Draw a card, then discard a card. If there are four or more chorus counters "
               "on Malcolm, you may cast the discarded card without paying its mana cost.", "2", "1", colors=("U",))
GIX = real("Gix, Yawgmoth Praetor", "{1}{B}{B}", "Legendary Creature — Phyrexian Praetor", "Whenever a creature deals combat damage to one "
           "of your opponents, its controller may pay 1 life. If they do, they draw a card.\n{4}{B}{B}{B}, Discard X cards: Exile the top X "
           "cards of target opponent's library. You may play lands and cast spells from among cards exiled this way without paying their "
           "mana costs.", "3", "3", colors=("B",))
SHINOBI = real("Fallen Shinobi", "{3}{U}{B}", "Creature — Zombie Ninja", "Ninjutsu {2}{U}{B} ({2}{U}{B}, Return an unblocked attacker "
               "you control to hand: Put this card onto the battlefield from your hand tapped and attacking.)\nWhenever this creature deals "
               "combat damage to a player, that player exiles the top two cards of their library. Until end of turn, you may play those "
               "cards without paying their mana costs.", "5", "4", colors=("U", "B"))
TWO = real("Two Drop", "{1}{U}", "Sorcery", "Draw a card.", colors=("U",))

DRACOGENESIS = real("Dracogenesis", "{6}{R}{R}", "Enchantment", "You may cast Dragon spells without paying their mana costs.", colors=("R",))
PATH = real("Descendants' Path", "{2}{G}", "Enchantment", "At the beginning of your upkeep, reveal the top card of your library. If it's a "
            "creature card that shares a creature type with a creature you control, you may cast it without paying its mana cost. If you "
            "don't cast it, put it on the bottom of your library.", colors=("G",))
CAPSTONE = real("Improvisation Capstone", "{5}{R}{R}", "Sorcery — Lesson", "Exile cards from the top of your library until you exile cards "
                "with total mana value 4 or greater. You may cast any number of spells from among them without paying their mana costs.\n"
                "Paradigm (Then exile this spell. After you first resolve a spell with this name, you may cast a copy of it from exile "
                "without paying its mana cost at the beginning of each of your first main phases.)", colors=("R",))
BOMBARDMENT = real("Arcane Bombardment", "{4}{R}{R}", "Enchantment", "Whenever you cast your first instant or sorcery spell each turn, exile "
                   "an instant or sorcery card at random from your graveyard. Then copy each card exiled with this enchantment. You may cast "
                   "any number of the copies without paying their mana costs.", colors=("R",))
AUGURY = real("Aminatou's Augury", "{6}{U}{U}", "Sorcery", "Exile the top eight cards of your library. You may put a land card from among "
              "them onto the battlefield. Until end of turn, for each nonland card type, you may cast a spell of that type from among the "
              "exiled cards without paying its mana cost.", colors=("U",))
DILATION = real("Mind's Dilation", "{5}{U}{U}", "Enchantment", "Whenever an opponent casts their first spell each turn, that player exiles the "
                "top card of their library. If it's a nonland card, you may cast it without paying its mana cost.", colors=("U",))
DRAGON = real("Whelp", "{3}{R}{R}", "Creature — Dragon", "Flying", "4", "4", colors=("R",))
CUB = real("Cub", "{G}", "Creature — Cub", "", "1", "1", colors=("G",))
KINDRED = real("Elf Rite", "{1}{G}", "Kindred Sorcery — Elf", "Draw a card.", colors=("G",))
GOLEM = real("Golem", "{3}", "Artifact Creature — Golem", "", "3", "3")
ELF_DRUID = real("Druid", "{2}{G}", "Creature — Elf Druid", "", "2", "2", colors=("G",))

JODAH = real("Jodah, the Unifier", "{W}{U}{B}{R}{G}", "Legendary Creature — Human Wizard", "Legendary creatures you control get +X/+X, "
             "where X is the number of legendary creatures you control.\nWhenever you cast a legendary spell from your hand, exile cards from "
             "the top of your library until you exile a legendary nonland card with lesser mana value. You may cast that card without paying "
             "its mana cost. Put the rest on the bottom of your library in a random order.", "5", "5", colors=("W", "U", "B", "R", "G"))
TAMPERING = real("Cemetery Tampering", "{2}{B}", "Enchantment", "Hideaway 5 (When this enchantment enters, look at the top five cards of your "
                 "library, exile one face down, then put the rest on the bottom in a random order.)\nAt the beginning of your upkeep, you may "
                 "mill three cards. Then if there are twenty or more cards in your graveyard, you may play the exiled card without paying its "
                 "mana cost.", colors=("B",))
GRIMA = real("Gríma, Saruman's Footman", "{2}{U}{B}", "Legendary Creature — Human Advisor", "Gríma can't be blocked.\nWhenever Gríma deals "
             "combat damage to a player, that player exiles cards from the top of their library until they exile an instant or sorcery card. "
             "You may cast that card without paying its mana cost. Then that player puts the exiled cards that weren't cast this way on the "
             "bottom of their library in a random order.", "1", "4", colors=("U", "B"))
GEODE = real("Geode Golem", "{5}", "Artifact Creature — Golem", "Trample\nWhenever this creature deals combat damage to a player, you may "
             "cast your commander from the command zone without paying its mana cost. (You still pay any additional costs.)", "5", "3")
PLANETARIUM = real("Planetarium of Wan Shi Tong", "{6}", "Legendary Artifact", "{1}, {T}: Scry 2.\nWhenever you scry or surveil, look at "
                   "the top card of your library. You may cast that card without paying its mana cost. Do this only once each turn. (Look at "
                   "the card after you scry or surveil.)")
IGNITE = real("Ignite the Future", "{3}{R}", "Sorcery", "Exile the top three cards of your library. Until the end of your next turn, you may "
              "play those cards. If this spell was cast from a graveyard, you may play cards this way without paying their mana costs.\n"
              "Flashback {7}{R} (You may cast this card from your graveyard for its flashback cost. Then exile it.)", colors=("R",))
LEGEND2 = real("Small Legend", "{1}{G}", "Legendary Creature — Elf", "", "2", "2", colors=("G",))
LEGEND4 = real("Big Legend", "{3}{G}", "Legendary Creature — Elf", "", "4", "4", colors=("G",))

DESIRE = real("Mind's Desire", "{4}{U}{U}", "Sorcery", "Shuffle your library. Then exile the top card of your library. Until end of turn, "
              "you may play that card without paying its mana cost.\nStorm (When you cast this spell, copy it for each spell cast before it "
              "this turn.)", colors=("U",))
DRAGONSTORM = real("Breaching Dragonstorm", "{4}{R}", "Enchantment", "When this enchantment enters, exile cards from the top of your library "
                   "until you exile a nonland card. You may cast it without paying its mana cost if that spell's mana value is 8 or less. If "
                   "you don't, put that card into your hand.\nWhen a Dragon you control enters, return this enchantment to its owner's hand.",
                   colors=("R",))
DELUGE = real("Mnemonic Deluge", "{6}{U}{U}{U}", "Sorcery", "Exile target instant or sorcery card from a graveyard. Copy that card three "
              "times. You may cast the copies without paying their mana costs. Exile Mnemonic Deluge.", colors=("U",))
RIGGING = real("Fight Rigging", "{2}{G}", "Enchantment", "Hideaway 5 (When this enchantment enters, look at the top five cards of your "
               "library, exile one face down, then put the rest on the bottom in a random order.)\nAt the beginning of combat on your turn, "
               "put a +1/+1 counter on target creature you control. Then if you control a creature with power 7 or greater, you may play the "
               "exiled card without paying its mana cost.", colors=("G",))
MARVEL = real("Aetherworks Marvel", "{4}", "Legendary Artifact", "Whenever a permanent you control is put into a graveyard, you get {E} (an "
              "energy counter).\n{T}, Pay six {E}: Look at the top six cards of your library. You may cast a spell from among them without "
              "paying its mana cost. Put the rest on the bottom of your library in a random order.")
CALAMITY = real("Invoke Calamity", "{1}{R}{R}{R}{R}", "Instant", "You may cast up to two instant and/or sorcery spells with total mana value 6 "
                "or less from your graveyard and/or hand without paying their mana costs. If those spells would be put into your graveyard, "
                "exile them instead. Exile Invoke Calamity.", colors=("R",))
NINE = real("Nine Drop", "{9}", "Artifact", "")
SIX = real("Giant", "{6}", "Creature — Giant", "", "6", "6")

KEFKA = real("Kefka, Dancing Mad", "{5}{B}{R}", "Legendary Creature — Human Wizard", "During your turn, Kefka has indestructible.\nAt the "
             "beginning of your end step, exile a card at random from each opponent's graveyard. You may cast any number of spells from "
             "among cards exiled this way without paying their mana costs. Then each player who owns a spell you cast this way loses life "
             "equal to its mana value.", "6", "6", colors=("B", "R"))
WAND = real("Chaos Wand", "{3}", "Artifact", "{4}, {T}: Target opponent exiles cards from the top of their library until they exile an "
            "instant or sorcery card. You may cast that card without paying its mana cost. Then put the exiled cards that weren't cast this "
            "way on the bottom of that library in a random order.")
PLUNDER = real("Memory Plunder", "{U/B}{U/B}{U/B}{U/B}", "Instant", "You may cast target instant or sorcery card from an opponent's "
               "graveyard without paying its mana cost.", colors=("U", "B"))
POSSIBILITY = real("Possibility Storm", "{3}{R}{R}", "Enchantment", "Whenever a player casts a spell from their hand, that player exiles it, "
                   "then exiles cards from the top of their library until they exile a card that shares a card type with it. That player "
                   "may cast that card without paying its mana cost. Then they put all cards exiled with this enchantment on the bottom of "
                   "their library in a random order.", colors=("R",))
CHARGE = real("Sokka's Charge", "{3}{W}", "Enchantment", "During your turn, Allies you control have double strike and lifelink.",
              colors=("W",))
ZAMRIEL = real("Zamriel, Seraph of Steel", "{2}{W}{W}", "Legendary Creature — Angel", "Flying\nDuring your turn, equipped creatures you "
               "control have indestructible.", "3", "4", colors=("W",))
ALLY = real("Ally", "{1}{W}", "Creature — Human Soldier Ally", "", "2", "2", colors=("W",))
SYNOD = real("Seat of the Synod", "", "Artifact Land", "{T}: Add {U}.")
CLIVE = real("Clive's Hideaway", "", "Land — Town", "Hideaway 4 (When this land enters, look at the top four cards of your library, exile one "
             "face down, then put the rest on the bottom in a random order.)\n{T}: Add {C}.\n{2}, {T}: You may play the exiled card "
             "without paying its mana cost if you control four or more legendary creatures.")

ENSNARED = real("Ensnared by the Mara", "{2}{R}{R}", "Sorcery", "Each opponent faces a villainous choice — They exile cards from the top of "
                "their library until they exile a nonland card, then you may cast that card without paying its mana cost, or that player "
                "exiles the top four cards of their library and Ensnared by the Mara deals damage equal to the total mana value of those "
                "exiled cards to that player.", colors=("R",))

GUFF = real("Guff Rewrites History", "{2}{R}", "Instant", "For each player, choose target nonenchantment, nonland permanent that player "
            "controls. Those permanents' owners shuffle them into their libraries. Each player who controlled one of those permanents exiles "
            "cards from the top of their library until they exile a nonland card, then puts the rest on the bottom of their library in a "
            "random order. Each player may cast the nonland card they exiled without paying its mana cost.", colors=("R",))
COURT = real("Court of Locthwain", "{2}{B}{B}", "Enchantment", "When this enchantment enters, you become the monarch.\nAt the beginning of "
             "your upkeep, exile the top card of target opponent's library. You may play that card for as long as it remains exiled, and "
             "mana of any type can be spent to cast it. If you're the monarch, until end of turn, you may cast a spell from among cards "
             "exiled with this enchantment without paying its mana cost.", colors=("B",))
RED_BEAR = real("Red Bear", "{1}{R}", "Creature — Bear", "", "2", "2", colors=("R",))


def asking(policy, asked):
    """`policy`, noting every list of options it is shown."""
    return lambda prompt, options: asked.append(list(options)) or policy(prompt, options)


class CastFreeTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SWORD, ETALI, SICKNESS, SCEPTER, MASTERY, BESEECH, DAUTHI):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_buster_sword_casts_a_spell_up_to_the_damage_dealt(self):
        for damage, cast in ((3, True), (2, False)):
            asked = []
            game, _ = table3(asking(pick("Three Drop"), asked))
            a, b, _ = game.seats
            bear = Permanent(BEAR)
            a.battlefield, a.hand, a.library = [bear, Permanent(SWORD, attached_to=bear)], [THREE, BIG], [FOREST] * 3
            game.damage(b, damage, bear, combat=True)
            run_stack(game)
            self.assertNotIn("Big", [o for options in asked for o in options], damage)  # mana value 5: more than the damage
            self.assertEqual(("Three Drop" in [c.name for c in a.graveyard], "Big" in [c.name for c in a.hand]), (cast, True), damage)

    def test_etali_casts_every_nonland_card_the_players_exile(self):
        game, _ = table3()
        a, b, c = game.seats
        a.library, b.library, c.library = [FOREST, replace(BEAR)], [replace(BEAR), FOREST], [FOREST, FOREST, replace(BEAR)]
        enter(game, a, ETALI)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield].count("Bear"), 3)  # nobody sets one aside, and all may be cast
        self.assertEqual(([c.name for c in a.exile], [c.name for c in b.library], len(c.exile)), (["Forest"], ["Forest"], 2))

    def test_etali_primal_sickness_poisons_the_player_it_damages(self):
        game, _ = table3()
        a, b, c = game.seats
        etali = Permanent(SICKNESS)
        a.battlefield = [etali]
        game.damage(b, 3, etali, combat=True)
        game.damage(c, 3, etali)  # not combat damage
        run_stack(game)
        self.assertEqual((b.player_counters.get("poison"), c.player_counters.get("poison")), (3, None))

    def test_isochron_scepter_imprints_a_cheap_instant_and_casts_copies_of_it(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(6), [FOUR, OPT, THREE], [FOREST] * 5
        scepter = enter(game, a, SCEPTER)
        run_stack(game)
        self.assertEqual(([c.name for c in a.exile], [c.name for c in a.hand]), (["Opt"], ["Four Drop", "Three Drop"]))
        for times in (1, 2):
            activate(game, a, "Isochron Scepter")
            scepter.tapped = False
            self.assertEqual((len(a.hand), [c.name for c in a.exile], a.graveyard), (2 + times, ["Opt"], []), times)
        a.exile.clear()  # the imprinted card is gone: there is nothing to copy
        activate(game, a, "Isochron Scepter")
        self.assertEqual(len(a.hand), 4)

    def test_isochron_scepter_exiles_nothing_without_a_cheap_instant(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [FOUR, PONDER]  # an instant that costs too much, and a cheap sorcery
        enter(game, a, SCEPTER)
        run_stack(game)
        self.assertEqual((a.exile, len(a.hand)), ([], 2))

    def test_mizzixs_mastery_casts_a_copy_of_its_target(self):
        game, _ = table3(pick("Pay"))
        a = game.seats[0]
        a.battlefield, a.hand, a.graveyard, a.library = lands(8), [MASTERY], [OPT, BEAR, replace(OPT)], [FOREST] * 5
        game._perform(a, CAST + "Mizzix's Mastery")
        run_stack(game)
        self.assertEqual((len(a.hand), sorted(c.name for c in a.exile), [c.name for c in a.graveyard]),
                         (1, ["Mizzix's Mastery", "Opt"], ["Bear", "Opt"]))

    def test_mizzixs_mastery_needs_a_target_unless_overloaded(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.graveyard = lands(4), [MASTERY], [BEAR]
        self.assertNotIn(CAST + "Mizzix's Mastery", game.legal_actions(a))

    def test_overloaded_mizzixs_mastery_casts_copies_of_every_instant_and_sorcery(self):
        game, _ = table3(pick("Overload"))
        a = game.seats[0]
        a.battlefield, a.hand, a.graveyard, a.library = lands(8), [MASTERY], [OPT, BEAR, replace(OPT), THREE], [FOREST] * 5
        game._perform(a, CAST + "Mizzix's Mastery")
        run_stack(game)
        self.assertEqual((len(a.hand), [c.name for c in a.graveyard]), (3, ["Bear"]))

    def test_beseech_the_mirror_casts_the_card_only_if_bargained_and_cheap_enough(self):
        for bargain, found, cast in (("Yes", "Three Drop", True), ("No", "Three Drop", False), ("Yes", "Big", False),
                                     ("Yes", "Forest", False)):
            game, _ = table3(lambda prompt, options, bargain=bargain, found=found:
                             options.index(bargain) if KICKER_PROMPT.matches(prompt) else pick(found)(prompt, options))
            a = game.seats[0]
            a.battlefield, a.hand, a.library = [*lands(4), Permanent(RELIC)], [BESEECH], [BIG, FOREST, THREE, FOREST]
            game._perform(a, CAST + "Beseech the Mirror")
            run_stack(game)
            self.assertEqual("Relic" in [p.card.name for p in a.battlefield], bargain == "No")
            self.assertEqual((found in [c.name for c in a.graveyard], found in [c.name for c in a.hand], a.exile), (cast, not cast, []),
                             (bargain, found))

    def test_dauthi_voidwalker_exiles_opponents_cards_and_plays_one_for_free(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(DAUTHI)]
        game._move_card(b, BIG, "graveyard")
        game._move_card(a, BEAR, "graveyard")  # yours go to your graveyard
        b.exile.append(OPT)  # exiled some other way: no void counter
        self.assertEqual(([c.name for c in b.exile], b.graveyard, [c.name for c in a.graveyard]), (["Big", "Opt"], [], ["Bear"]))
        activate(game, a, "Dauthi Voidwalker")
        self.assertEqual(([p.card.name for p in a.battlefield], [c.name for c in b.exile]), (["Big"], ["Opt"]))

    def test_only_an_opponents_voidwalker_puts_a_void_counter(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(DAUTHI)]
        b.battlefield = [Permanent(LEYLINE)]
        game._move_card(a, BEAR, "graveyard")  # exiled by the Leyline, not by your own Voidwalker
        self.assertEqual(([c.name for c in a.exile], game.void_exiled), (["Bear"], []))

    def test_dauthi_voidwalker_plays_a_land_with_a_land_drop_left(self):
        for played, entered in ((0, True), (1, False)):
            game, _ = table3()
            a, b, _ = game.seats
            a.battlefield, a.lands_played = [Permanent(DAUTHI)], played
            game._move_card(b, RAINBOW, "graveyard")
            activate(game, a, "Dauthi Voidwalker")
            self.assertEqual("City of Brass" in [p.card.name for p in a.battlefield], entered, played)


class CastFreeBatchTwoTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (OMNISCIENCE, MULTIVERSE, ELECTRO, MALCOLM, GIX, SHINOBI):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_omniscience_casts_spells_from_the_hand_for_free(self):
        game, _ = table3(pick(FREE_WAY))
        a, b, _ = game.seats
        a.battlefield, a.hand, a.command_zone = [Permanent(OMNISCIENCE)], [BIG], [COMMANDER]
        b.hand = [OPT]
        self.assertNotIn(CAST_COMMANDER + "Omnath", game.legal_actions(a))  # not from the command zone
        self.assertNotIn(CAST + "Opt", game.legal_actions(b))  # only its controller's spells
        game._perform(a, CAST + "Big")
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Omniscience", "Big"])

    def test_one_with_the_multiverse_casts_one_spell_free_on_each_of_your_turns(self):
        game, _ = table3(pick(FREE_WAY))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = [Permanent(MULTIVERSE)], [BIG], [OPT, BEAR]
        a.exile, a.exile_play = [OGRE], [(OGRE, game.turn)]
        self.assertIn(CAST_TOP + "Opt", game.legal_actions(a))  # from the top of the library too
        self.assertNotIn(CAST_EXILE + "Ogre", game.legal_actions(a))  # but not from anywhere else
        game._perform(a, CAST + "Big")
        run_stack(game)
        self.assertNotIn(CAST_TOP + "Opt", game.legal_actions(a))  # once a turn
        game.turn += 3
        self.assertIn(CAST_TOP + "Opt", game.legal_actions(a))
        game.active = 1
        self.assertNotIn(CAST_TOP + "Opt", game.legal_actions(a))  # during your turns only

    def test_electrodominance_casts_a_spell_up_to_x(self):
        asked = []
        policy = lambda prompt, options: (options.index("2") if X_PROMPT.matches(prompt) else options.index("Player: B (seat 1)")
                                          if "Player: B (seat 1)" in options else pick("Two Drop")(prompt, options))
        game, _ = table3(asking(policy, asked))
        a, b, _ = game.seats
        a.battlefield, a.hand, a.library = lands(4), [ELECTRO, THREE, TWO], [FOREST] * 3
        life = b.life
        game._perform(a, CAST + "Electrodominance")
        run_stack(game)
        self.assertEqual((b.life, sorted(c.name for c in a.graveyard)), (life - 2, ["Electrodominance", "Two Drop"]))
        self.assertIn(["Two Drop", "Don't cast"], asked)  # Three Drop costs more than X

    def test_malcolm_casts_the_discarded_card_with_four_chorus_counters(self):
        for counters, cast in ((3, True), (2, False)):
            game, _ = table3(pick("Three Drop"))
            a, b, _ = game.seats
            malcolm = Permanent(MALCOLM, counters={"chorus": counters})
            a.battlefield, a.hand, a.library = [malcolm], [THREE], [FOREST] * 3
            game.damage(b, 2, malcolm, combat=True)
            run_stack(game)
            self.assertEqual((malcolm.counters["chorus"], len(a.hand)), (counters + 1, 1 + cast), counters)

    def test_malcolm_casts_no_land_and_nothing_that_left_the_graveyard(self):
        for discard, theirs in (("Mountain", []), ("Three Drop", [Permanent(LEYLINE)])):
            game, _ = table3(pick(discard))
            a, b, _ = game.seats
            malcolm = Permanent(MALCOLM, counters={"chorus": 3})
            a.battlefield, a.hand, a.library, b.battlefield = [malcolm], [replace(MOUNTAIN), THREE], [FOREST] * 3, theirs
            game.damage(b, 2, malcolm, combat=True)
            run_stack(game)
            self.assertEqual((len(a.hand), [c.name for c in a.graveyard + a.exile]), (2, [discard]), discard)  # nothing cast

    def test_gix_lets_the_controller_of_a_creature_that_hits_your_opponent_pay_to_draw(self):
        game, _ = table3()
        a, b, c = game.seats
        theirs = Permanent(BEAR)
        a.battlefield, b.battlefield = [Permanent(GIX)], [theirs]
        for seat in game.seats:
            seat.library = [FOREST] * 3
        life = b.life
        game.damage(c, 2, theirs, combat=True)  # c is one of a's opponents: b pays and draws
        game.damage(a, 2, theirs, combat=True)  # a is not their own opponent
        game.damage(c, 2, theirs)  # not combat damage
        run_stack(game)
        self.assertEqual((b.life, len(b.hand), len(a.hand)), (life - 1, 1, 0))
        b.life = 0  # no life to pay
        game.damage(c, 2, theirs, combat=True)
        run_stack(game)
        self.assertEqual(len(b.hand), 1)

    def test_gixs_ability_plays_the_exiled_cards_for_free(self):
        for played, forest in ((0, True), (1, False)):
            game, _ = table3(lambda prompt, options: options.index("2") if X_PROMPT.matches(prompt)
                             else options.index("Player: B (seat 1)") if "Player: B (seat 1)" in options else 0)
            a, b, _ = game.seats
            a.battlefield, a.hand, a.lands_played = [Permanent(GIX), *lands(7)], [BEAR, OGRE, TWO], played
            b.library = [BIG, MOUNTAIN, OPT]
            activate(game, a, "Gix")
            mine = [p.card.name for p in a.battlefield]
            self.assertEqual(("Big" in mine, "Mountain" in mine, [c.name for c in a.hand], [c.name for c in b.library]),
                             (True, forest, ["Two Drop"], ["Opt"]), played)

    def test_fallen_shinobi_plays_the_damaged_players_top_two_cards_free_this_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        shinobi = Permanent(SHINOBI)
        a.battlefield, b.library = [shinobi], [BIG, MOUNTAIN, BEAR]
        game.damage(b, 5, shinobi, combat=True)
        run_stack(game)
        actions = game.legal_actions(a)
        self.assertTrue({CAST_EXILE + "Big", PLAY_EXILE + "Mountain"} <= set(actions))  # no lands needed for Big
        self.assertEqual([c.name for c in b.library], ["Bear"])
        game._perform(a, CAST_EXILE + "Big")  # free: no lands to pay with
        run_stack(game)
        self.assertIn("Big", [p.card.name for p in a.battlefield])
        game.turn += 1
        self.assertNotIn(PLAY_EXILE + "Mountain", game.legal_actions(a))


class CastFreeBatchThreeTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (DRACOGENESIS, PATH, CAPSTONE, BOMBARDMENT, AUGURY, DILATION):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_dracogenesis_casts_its_controllers_dragons_free(self):
        game, _ = table3(pick(FREE_WAY))
        a, b, _ = game.seats
        a.battlefield, a.hand, b.hand = [Permanent(DRACOGENESIS)], [DRAGON, BEAR], [DRAGON]
        game.active = 1
        self.assertNotIn(CAST + "Whelp", game.legal_actions(b))  # not its owner's
        game.active = 0
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [CAST + "Whelp"])  # not the Bear
        game._perform(a, CAST + "Whelp")
        run_stack(game)
        self.assertIn("Whelp", [p.card.name for p in a.battlefield])

    def test_descendants_path_casts_a_creature_sharing_a_type_or_puts_it_on_the_bottom(self):
        for top, cast in ((ELF_DRUID, True), (DRAGON, False), (KINDRED, False)):  # a Kindred Elf is no creature card
            game, _ = table3()
            a = game.seats[0]
            path = Permanent(PATH)
            a.battlefield, a.library = [path, Permanent(ELF)], [top, FOREST]
            fire(game, a, path, "upkeep")
            self.assertEqual((top.name in [p.card.name for p in a.battlefield], [c.name for c in a.library]),
                             (cast, ["Forest"] if cast else ["Forest", top.name]), top.name)

    def test_improvisation_capstone_exiles_up_to_four_mana_value_and_comes_back_by_paradigm(self):
        asked = []
        game, _ = table3(asking(lambda prompt, options: 0, asked))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(9), [CAPSTONE, replace(CAPSTONE)], [FOREST, CUB, FOREST, ELF_DRUID, OGRE, OGRE, OGRE]
        game._perform(a, CAST + "Improvisation Capstone")
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.exile), ["Forest", "Forest", "Improvisation Capstone"])  # Cub, Druid cast: 1 + 3 = 4
        self.assertEqual([c.name for c in a.library[:1]], ["Ogre"])
        game.step = "main1"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertIn("Ogre", [p.card.name for p in a.battlefield])  # the copy exiled the Ogres and cast them
        self.assertEqual([c.name for c in a.exile].count("Improvisation Capstone"), 1)
        a.library = [OGRE, BEAR]
        for p in a.battlefield:
            p.tapped = False
        game._perform(a, CAST + "Improvisation Capstone")  # another of the same name: exiled, but no second paradigm
        run_stack(game)
        self.assertEqual(len(a.paradigms), 1)
        a.exile.clear()  # the first left exile: nothing to copy
        a.library = [BEAR]
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual([c.name for c in a.library], ["Bear"])

    def test_arcane_bombardment_copies_every_card_exiled_with_it(self):
        game, _ = table3()
        a = game.seats[0]
        bombardment = Permanent(BOMBARDMENT)
        a.battlefield, a.hand, a.graveyard, a.library = [bombardment, *lands(4)], [OPT, replace(OPT)], [BEAR, THREE], [FOREST] * 6
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual(([c.name for c in a.exile], len(a.hand)), (["Three Drop"], 3))  # Opt and the Three Drop copy drew; the Bear stays
        game._perform(a, CAST + "Opt")  # the second instant this turn: nothing
        run_stack(game)
        self.assertEqual(len(a.hand), 3)
        a.exile.clear()  # the card exiled with it left exile: no copy of it
        a.graveyard, a.hand = [], [OPT]
        game.turn += 3
        for p in a.battlefield:
            p.tapped = False
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_aminatous_augury_puts_a_land_and_casts_one_spell_of_each_type(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand = lands(8), [AUGURY]
        a.library = [FOREST, GOLEM, BEAR, replace(BEAR), OPT, MOUNTAIN, THREE, OGRE, FOREST]
        game._perform(a, CAST + "Aminatou's Augury")
        run_stack(game)
        names = [p.card.name for p in a.battlefield]  # the Golem used up artifact, so a creature could still be cast
        self.assertEqual((names.count("Forest"), names.count("Golem"), names.count("Bear"), names.count("Ogre")), (1, 1, 1, 0))
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Aminatou's Augury", "Opt", "Three Drop"])

    def test_minds_dilation_casts_the_opponents_top_card_only_if_nonland(self):
        for top, cast in ((BEAR, True), (FOREST, False)):
            game, _ = table3()
            a, b, _ = game.seats
            a.battlefield, b.battlefield, b.hand, b.library = [Permanent(DILATION)], lands(1), [OPT], [top, OPT]
            game.active = 1
            game._perform(b, CAST + "Opt")
            run_stack(game)
            self.assertEqual(("Bear" in [p.card.name for p in a.battlefield], [c.name for c in b.exile]), (cast, [] if cast else [top.name]), top.name)


class CastFreeBatchFourTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (JODAH, TAMPERING, GRIMA, GEODE, PLANETARIUM, IGNITE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_jodah_pumps_legendary_creatures_by_their_number(self):
        game, _ = table3()
        a = game.seats[0]
        jodah, legend, bear = Permanent(JODAH), Permanent(LEGEND2), Permanent(BEAR)
        a.battlefield = [jodah, legend, bear]
        self.assertEqual((game.power(jodah), game.power(legend), game.power(bear)), (7, 4, 2))

    def test_jodah_casts_a_cheaper_legend_when_a_legend_is_cast_from_hand(self):
        for cast, legend in ((LEGEND4, True), (BIG, False)):
            game, _ = table3()
            a = game.seats[0]
            a.battlefield, a.hand = [Permanent(JODAH), *lands(5)], [cast]
            a.library = [replace(LEGEND4), BEAR, LEGEND2, FOREST]  # an equal mana value is passed over
            game._perform(a, CAST + cast.name)
            run_stack(game)
            names = [p.card.name for p in a.battlefield]
            self.assertEqual(("Small Legend" in names, sorted(c.name for c in a.library)[:2]),
                             (legend, ["Bear", "Big Legend"] if legend else ["Bear", "Big Legend"]), cast.name)
            self.assertEqual(len(a.library), 3 if legend else 4, cast.name)

    def test_grima_casts_an_instant_or_sorcery_from_the_damaged_players_library(self):
        for library, cast in (([FOREST, BEAR, OPT, MOUNTAIN], True), ([FOREST, BEAR], False)):
            game, _ = table3()
            a, b, _ = game.seats
            grima = Permanent(GRIMA)
            a.battlefield, a.library, b.library = [grima], [FOREST] * 3, list(library)
            game.damage(b, 1, grima, combat=True)
            run_stack(game)
            self.assertEqual((len(a.hand), [c.name for c in b.graveyard], b.exile), (1 if cast else 0, ["Opt"] if cast else [], []))
            self.assertEqual(sorted(c.name for c in b.library), sorted(c.name for c in library if c is not OPT))

    def test_geode_golem_casts_the_commander_free_but_for_its_tax(self):
        for casts, cast in ((0, True), (1, False)):
            game, _ = table3()
            a, b, _ = game.seats
            golem = Permanent(GEODE)
            a.battlefield, a.command_zone, a.commander_casts = [golem], [COMMANDER], {"Omnath": casts}
            game.damage(b, 5, golem, combat=True)
            run_stack(game)
            self.assertEqual(("Omnath" in [p.card.name for p in a.battlefield], a.commander_casts["Omnath"]), (cast, casts + cast), casts)

    def test_cemetery_tampering_plays_the_hidden_card_at_twenty_cards_in_the_graveyard(self):
        for graveyard, mill, played in ((17, "Yes", True), (16, "Yes", False), (20, "No", True)):
            game, _ = table3(lambda prompt, options, mill=mill: options.index(mill) if "Yes" in options and "Play it" not in options else 0)
            a = game.seats[0]
            tampering = Permanent(TAMPERING)
            a.battlefield, a.graveyard, a.library, a.exile = [tampering], [replace(FOREST) for _ in range(graveyard)], [FOREST] * 5, [BIG]
            tampering.exiled_with.append((a, BIG))
            fire(game, a, tampering, "upkeep")
            self.assertEqual(("Big" in [p.card.name for p in a.battlefield], len(a.library)), (played, 2 if mill == "Yes" else 5),
                             (graveyard, mill))

    def test_planetarium_casts_the_top_card_free_once_each_turn(self):
        game, _ = table3()
        a = game.seats[0]
        planetarium = Permanent(PLANETARIUM)
        a.battlefield, a.library = [planetarium], [BEAR, OGRE, MOUNTAIN]
        fire(game, a, planetarium, "scry_or_surveil")
        fire(game, a, planetarium, "scry_or_surveil")
        self.assertEqual([p.card.name for p in a.battlefield], ["Planetarium of Wan Shi Tong", "Bear"])
        game.turn += 1
        fire(game, a, planetarium, "scry_or_surveil")
        self.assertIn("Ogre", [p.card.name for p in a.battlefield])
        game.turn += 1
        fire(game, a, planetarium, "scry_or_surveil")  # a land is not cast
        self.assertEqual([c.name for c in a.library], ["Mountain"])

    def test_ignite_the_future_plays_free_only_when_flashed_back(self):
        for zone, free in (("hand", False), ("graveyard", True)):
            game, _ = table3(pick("Flashback", "Pay"))
            a = game.seats[0]
            a.battlefield, a.library = lands(8), [BIG, OPT, FOREST]
            if zone == "hand":
                a.hand = [IGNITE]
                game._perform(a, CAST + "Ignite the Future")
            else:
                a.graveyard = [IGNITE]
                game._perform(a, "Cast from graveyard: Ignite the Future")
            run_stack(game)
            for p in a.battlefield:
                p.tapped = True  # no mana left
            self.assertEqual(CAST_EXILE + "Big" in game.legal_actions(a), free, zone)


class CastFreeBatchFiveTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (DESIRE, DRAGONSTORM, DELUGE, RIGGING, MARVEL, CALAMITY):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_minds_desire_plays_the_exiled_card_free_this_turn(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(6), [DESIRE], [BIG]
        game._perform(a, CAST + "Mind's Desire")
        run_stack(game)
        self.assertIn(CAST_EXILE + "Big", game.legal_actions(a))  # free: no mana left
        game.turn += 1
        self.assertNotIn(CAST_EXILE + "Big", game.legal_actions(a))

    def test_minds_desire_shuffles_first(self):
        game, _ = table3()
        a = game.seats[0]
        cards = [replace(FOREST, name=f"Card {i}") for i in range(20)]
        a.battlefield, a.hand, a.library = lands(6), [DESIRE], list(cards)
        game._perform(a, CAST + "Mind's Desire")
        run_stack(game)
        self.assertNotEqual([c.name for c in a.library], [c.name for c in cards[1:]])  # 19 cards left in their first order: not shuffled

    def test_breaching_dragonstorm_casts_up_to_eight_or_takes_the_card(self):
        for card, cast in ((BIG, True), (NINE, False)):
            game, _ = table3()
            a = game.seats[0]
            a.library = [FOREST, card, OPT]
            enter(game, a, DRAGONSTORM)
            run_stack(game)
            self.assertEqual((card.name in [p.card.name for p in a.battlefield], [c.name for c in a.hand], [c.name for c in a.exile]),
                             (cast, [] if cast else [card.name], ["Forest"]), card.name)

    def test_breaching_dragonstorm_returns_when_a_dragon_enters(self):
        for creature, back in ((DRAGON, True), (BEAR, False)):
            game, _ = table3()
            a = game.seats[0]
            a.battlefield = [Permanent(DRAGONSTORM)]
            enter(game, a, creature)
            run_stack(game)
            self.assertEqual([c.name for c in a.hand], ["Breaching Dragonstorm"] if back else [], creature.name)

    def test_mnemonic_deluge_casts_three_copies_of_a_card_from_any_graveyard(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield, a.hand, a.library, b.graveyard = lands(9), [DELUGE], [FOREST] * 6, [OPT]
        game._perform(a, CAST + "Mnemonic Deluge")
        run_stack(game)
        self.assertEqual((len(a.hand), [c.name for c in b.exile], [c.name for c in a.exile]), (3, ["Opt"], ["Mnemonic Deluge"]))

    def test_fight_rigging_plays_the_hidden_card_with_a_creature_of_power_seven(self):
        for creature, played in ((SIX, True), (OGRE, False)):
            game, _ = table3()
            a = game.seats[0]
            rigging = Permanent(RIGGING)
            a.battlefield, a.exile = [rigging, Permanent(creature)], [BIG]
            rigging.exiled_with.append((a, BIG))
            fire(game, a, rigging, "combat")
            self.assertEqual("Big" in [p.card.name for p in a.battlefield], played, creature.name)

    def test_aetherworks_marvel_gets_energy_and_casts_one_of_six_free(self):
        game, _ = table3()
        a = game.seats[0]
        marvel, bear = Permanent(MARVEL), Permanent(BEAR)
        a.battlefield = [marvel, bear]
        a.player_counters["energy"] = 5
        game.destroy(bear)
        run_stack(game)
        self.assertEqual(a.player_counters["energy"], 6)  # the Bear went to the graveyard
        a.library = [FOREST, BIG, OPT, replace(FOREST), OGRE, replace(BEAR), MOUNTAIN]
        activate(game, a, "Aetherworks Marvel")
        self.assertEqual(("Big" in [p.card.name for p in a.battlefield], a.player_counters["energy"]), (True, 0))
        self.assertEqual(([c.name for c in a.library[:1]], len(a.library)), (["Mountain"], 6))

    def test_invoke_calamity_casts_two_spells_up_to_six_and_exiles_them(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.graveyard, a.library = lands(5), [CALAMITY, THREE, FOUR], [OPT, replace(OPT)], [FOREST] * 5
        game._perform(a, CAST + "Invoke Calamity")
        run_stack(game)
        self.assertEqual(sorted(c.name for c in a.exile), ["Invoke Calamity", "Opt", "Three Drop"])  # 3 + 1; the Four Drop would pass 6
        self.assertEqual(([c.name for c in a.graveyard], "Four Drop" in [c.name for c in a.hand]), (["Opt"], True))  # two spells only


class CastFreeBatchSixTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (KEFKA, WAND, PLUNDER, POSSIBILITY, CLIVE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_kefka_is_indestructible_during_its_controllers_turn(self):
        game, _ = table3()
        kefka = Permanent(KEFKA)
        game.seats[0].battlefield = [kefka]
        self.assertTrue(game.has_keyword(kefka, "indestructible"))
        game.active = 1
        self.assertFalse(game.has_keyword(kefka, "indestructible"))

    def test_during_your_turn_groups_are_the_right_creatures(self):
        game, _ = table3()
        a = game.seats[0]
        ally, other, equipped, bare = Permanent(ALLY), Permanent(BEAR), Permanent(OGRE), Permanent(replace(OGRE))
        a.battlefield = [Permanent(CHARGE), Permanent(ZAMRIEL), ally, other, equipped, bare, Permanent(SWORD, attached_to=equipped)]
        self.assertEqual((game.has_keyword(ally, "double strike"), game.has_keyword(other, "double strike")), (True, False))
        self.assertEqual((game.has_keyword(equipped, "indestructible"), game.has_keyword(bare, "indestructible")), (True, False))
        game.active = 1
        self.assertEqual((game.has_keyword(ally, "double strike"), game.has_keyword(equipped, "indestructible")), (False, False))

    def test_kefka_casts_cards_from_opponents_graveyards_and_drains_their_owners(self):
        game, _ = table3()
        a, b, c = game.seats
        kefka = Permanent(KEFKA)
        a.battlefield, a.library, b.graveyard, c.graveyard = [kefka], [FOREST] * 3, [OPT], [MOUNTAIN]
        life_b, life_c = b.life, c.life
        fire(game, a, kefka, "end_step")
        self.assertEqual((len(a.hand), b.life, c.life, [x.name for x in c.exile]), (1, life_b - 1, life_c, ["Mountain"]))

    def test_chaos_wand_casts_an_instant_or_sorcery_from_the_opponents_library(self):
        game, _ = table3(lambda prompt, options: options.index("Player: B (seat 1)") if "Player: B (seat 1)" in options else 0)
        a, b, _ = game.seats
        a.battlefield, a.library, b.library = [Permanent(WAND), *lands(4)], [FOREST] * 3, [FOREST, BEAR, OPT, MOUNTAIN]
        activate(game, a, "Chaos Wand")
        self.assertEqual((len(a.hand), [x.name for x in b.graveyard], sorted(x.name for x in b.library)),
                         (1, ["Opt"], ["Bear", "Forest", "Mountain"]))

    def test_memory_plunder_casts_from_an_opponents_graveyard_only(self):
        asked = []
        game, _ = table3(asking(lambda prompt, options: 0, asked))
        a, b, _ = game.seats
        a.battlefield, a.hand, a.graveyard, a.library, b.graveyard = lands(4), [PLUNDER], [replace(OPT)], [FOREST] * 3, [OPT]
        game._perform(a, CAST + "Memory Plunder")
        run_stack(game)
        self.assertNotIn("Opt (seat 0 graveyard)", [o for options in asked for o in options])
        self.assertEqual((len(a.hand), [x.name for x in b.graveyard], len(a.graveyard)), (1, ["Opt"], 2))
        a.hand = [replace(PLUNDER)]
        for p in a.battlefield:
            p.tapped = False
        game._perform(a, CAST + "Memory Plunder")
        b.graveyard.clear()  # the target left the graveyard before it resolved: the spell fizzles (CR 608.2b)
        run_stack(game)
        self.assertEqual(len(a.hand), 0)  # nothing cast, nothing drawn

    def test_possibility_storm_swaps_a_spell_cast_from_hand_for_one_of_its_type(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.library = [Permanent(POSSIBILITY), *lands(2)], [BEAR], [OPT, OGRE, FOREST]
        game._perform(a, CAST + "Bear")
        run_stack(game)
        names = [p.card.name for p in a.battlefield]
        self.assertEqual(("Ogre" in names, "Bear" in names, sorted(x.name for x in a.library)), (True, False, ["Bear", "Forest", "Opt"]))

    def test_possibility_storm_does_not_cast_an_artifact_land(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.library = [Permanent(POSSIBILITY), *lands(1)], [RELIC], [SYNOD, FOREST]
        game._perform(a, CAST + "Relic")
        run_stack(game)
        self.assertEqual((sorted(x.name for x in a.library), "Seat of the Synod" in [p.card.name for p in a.battlefield]),
                         (["Forest", "Relic", "Seat of the Synod"], False))

    def test_possibility_storm_ignores_spells_not_cast_from_hand(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.library = [Permanent(POSSIBILITY)], [OGRE, FOREST]
        game.cast_copy_free(a, BEAR)  # a copy, cast from no hand
        run_stack(game)
        self.assertEqual(([x.name for x in a.library], "Ogre" in [p.card.name for p in a.battlefield]), (["Ogre", "Forest"], False))

    def test_clives_hideaway_plays_the_card_with_four_legendary_creatures(self):
        for legends, played in ((4, True), (3, False)):
            game, _ = table3()
            a = game.seats[0]
            hideaway = Permanent(CLIVE)
            a.battlefield = [hideaway, *lands(2), Permanent(BEAR), *[Permanent(replace(LEGEND2, name=f"Legend {i}")) for i in range(legends)]]
            a.exile = [BIG]
            hideaway.exiled_with.append((a, BIG))
            activate(game, a, "{2}")
            self.assertEqual("Big" in [p.card.name for p in a.battlefield], played, legends)


class VillainousChoiceTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(ENSNARED), [])

    def test_each_opponent_chooses_for_themselves(self):
        game, _ = table3(lambda prompt, options: 0, lambda prompt, options: 0, lambda prompt, options: 1)
        a, b, c = game.seats
        a.battlefield, a.hand = lands(4), [ENSNARED]
        b.library, c.library = [FOREST, BEAR, OPT], [BIG, OPT, FOREST, MOUNTAIN, OGRE]
        life_b, life_c = b.life, c.life
        game._perform(a, CAST + "Ensnared by the Mara")
        run_stack(game)
        self.assertEqual(("Bear" in [p.card.name for p in a.battlefield], [x.name for x in b.exile], b.life), (True, ["Forest"], life_b))
        self.assertEqual((sorted(x.name for x in c.exile), c.life, [x.name for x in c.library]),
                         (["Big", "Forest", "Mountain", "Opt"], life_c - 6, ["Ogre"]))  # 5 + 1 damage


class GuffRewritesHistoryTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(GUFF), [])

    def test_each_player_shuffles_one_permanent_away_and_casts_what_they_find(self):
        asked = []
        game, _ = table3(asking(lambda prompt, options: 0, asked))
        a, b, c = game.seats
        a.battlefield, a.hand, a.library = [*lands(3), Permanent(OGRE)], [GUFF], [FOREST] * 10
        b.battlefield, b.library = [Permanent(BEAR)], [FOREST] * 10
        c.battlefield, c.library = [Permanent(ANTHEM)], [BIG, FOREST]  # nothing c controls can be chosen
        game._perform(a, CAST + "Guff Rewrites History")
        run_stack(game)
        self.assertFalse(any("No target" in o for options in asked for o in options))  # "choose target": one for each player who can
        self.assertEqual(([p.card.name for p in a.battlefield if not is_land(p.card)], [p.card.name for p in b.battlefield]),
                         (["Ogre"], ["Bear"]))  # shuffled in, found again, cast free
        self.assertEqual(([x.name for x in c.library], len(a.library), len(b.library)), (["Big", "Forest"], 10, 10))  # lands to the bottom


class CourtOfLocthwainTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(COURT), [])

    def test_the_exiled_card_is_played_later_with_mana_of_any_type(self):
        game, _ = table3(pick("Player: B", "Pay"))
        a, b, _ = game.seats
        court = Permanent(COURT)
        a.battlefield, b.library = [court, *lands(2, SWAMP)], [RED_BEAR, OPT]
        game.monarch = b
        fire(game, a, court, "upkeep")
        self.assertEqual(([c.name for c in a.exile], [p.card.name for p in a.battlefield].count("Red Bear")), (["Red Bear"], 0))
        game.turn += 3  # a later turn of yours: for as long as it remains exiled
        self.assertIn(CAST_EXILE + "Red Bear", game.legal_actions(a))  # two Swamps pay {1}{R}
        game._perform(a, CAST_EXILE + "Red Bear")
        run_stack(game)
        self.assertIn("Red Bear", [p.card.name for p in a.battlefield])

    def test_other_exiled_cards_still_need_their_colors(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.exile, a.exile_play = lands(2, SWAMP), [RED_BEAR], [(RED_BEAR, game.turn)]
        self.assertNotIn(CAST_EXILE + "Red Bear", game.legal_actions(a))

    def test_the_monarch_casts_one_for_free(self):
        for monarch, cast in ((0, True), (1, False)):
            game, _ = table3(pick("Player: B"))
            a, b, _ = game.seats
            court = Permanent(COURT)
            a.battlefield, b.library = [court], [BIG, OPT]
            game.monarch = game.seats[monarch]
            fire(game, a, court, "upkeep")
            self.assertEqual("Big" in [p.card.name for p in a.battlefield], cast, monarch)


if __name__ == "__main__":
    unittest.main()
