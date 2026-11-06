"""Casting without paying the mana cost (#655), from the cards' real Oracle text: Buster Sword (a spell from the hand up to the combat
damage), Etali, Primal Conqueror (each player exiles until a nonland card; cast any number of them) and its back face (poison equal to the
damage), Isochron Scepter (imprint an instant, then cast copies of it), Mizzix's Mastery (copies of a graveyard spell, or of all of them
when overloaded), Beseech the Mirror (cast the card found if bargained and cheap enough, else take it) and Dauthi Voidwalker (an
opponent's cards are exiled with void counters; play one for free). Batch 2: Omniscience and One with the Multiverse (a free way to cast),
Electrodominance (a spell up to X), Malcolm, Alluring Scoundrel (the discarded card, with four chorus counters), Gix, Yawgmoth Praetor
(pay 1 life to draw; play the cards exiled with Discard X) and Fallen Shinobi (play the damaged player's top two cards free). Batch 3:
Dracogenesis (Dragon spells free), Descendants' Path (a creature sharing a type, or the bottom), Improvisation Capstone (exile to a total
mana value; Paradigm), Arcane Bombardment (copies of every card exiled with it), Aminatou's Augury (a land, then one spell of each type)
and Mind's Dilation (the opponent's top card, if nonland)."""

import unittest
from dataclasses import replace

from infernal_machine.effects import FREE_WAY
from infernal_machine.game import CAST, CAST_COMMANDER, COST_PROMPT, KICKER_PROMPT, PARADIGM_PROMPT, X_PROMPT, Permanent
from infernal_machine.zones import CAST_EXILE, CAST_TOP, PLAY_EXILE
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, COMMANDER, ELF, MOUNTAIN, OGRE, RAINBOW, RELIC, activate, enter, fire, lands, pick, real, run_stack, table3

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


if __name__ == "__main__":
    unittest.main()
