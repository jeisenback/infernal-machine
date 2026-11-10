"""The third batch of cards whose every effect the engine already had, read from new wordings (each picked with Forge's card scripts),
from their real Oracle text: "Each player may play an additional land", artifacts and "creatures and nonbasic lands" an opponent controls
entering tapped, Equipment and Auras whose buff holds only while the creature is legendary or of a color, "Each other Human you control",
"Other Merfolk you control", creatures' abilities locked, one noncreature spell a turn, "+1/+1 counters ... on it / on that creature
instead", first strike during your turn, cost reductions for creature spells with flying, searches for a permanent card, Alesha's
return, "create that many ... creature tokens", "Each creature gets", "Create A and B", "... and add {B}", "For each token you
control, create", hexproof while untapped, "if that player has no cards in hand", Sower of Temptation, Wall of Reverence, Field of Ruin,
Volatile Fault, "sacrifice a creature or land", "Whenever you sacrifice a permanent", Adaptive Omnitool, and charge counters."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import (BEAR, BIRD, BOLT, DIVINATION, FOREST, OGRE, RELIC, SPIRIT, activate, end_turn, enter, lands, pick, real,
                           run_stack, table3)

RITES = real("Rites of Flourishing", "{2}{G}", "Enchantment", "At the beginning of each player's draw step, that player draws an "
             "additional card.\nEach player may play an additional land on each of their turns.", colors=("G",))
MANGLEHORN = real("Manglehorn", "{2}{G}", "Creature — Beast", "When this creature enters, you may destroy target "
                  "artifact.\nArtifacts your opponents control enter tapped.", "2", "2", colors=("G",))
THALIA = real("Thalia, Heretic Cathar", "{2}{W}", "Legendary Creature — Human Soldier", "First strike\nCreatures and nonbasic "
              "lands your opponents control enter tapped.", "3", "2", colors=("W",))
HELM = real("Champion's Helm", "{3}", "Artifact — Equipment", "Equipped creature gets +2/+2.\nAs long as equipped creature is "
            "legendary, it has hexproof. (It can't be the target of spells or abilities your opponents control.)\nEquip {1}")
EDGE = real("Edge of the Divinity", "{W/B}", "Enchantment — Aura", "Enchant creature\nAs long as enchanted creature is white, it "
            "gets +1/+2.\nAs long as enchanted creature is black, it gets +2/+1.", colors=("B", "W"))
VANGUARD = real("Coppercoat Vanguard", "{1}{W}", "Creature — Human Soldier", "Each other Human you control gets +1/+0 and has ward "
                "{1}. (Whenever it becomes the target of a spell or ability an opponent controls, counter it unless that player "
                "pays {1}.)", "2", "2", colors=("W",))
TUNNEL = real("Aether Tunnel", "{1}{U}", "Enchantment — Aura", "Enchant creature\nEnchanted creature gets +1/+0 and can't be "
              "blocked.", colors=("U",))
SVYELUN = real("Svyelun of Sea and Sky", "{1}{U}{U}", "Legendary Creature — Merfolk God", "Svyelun has indestructible as long as "
               "you control at least two other Merfolk.\nWhenever Svyelun attacks, draw a card.\nOther Merfolk you control have "
               "ward {1}. (Whenever another Merfolk you control becomes the target of a spell or ability an opponent controls, "
               "counter it unless that player pays {1}.)", "3", "4", colors=("U",))
LINVALA = real("Linvala, Keeper of Silence", "{2}{W}{W}", "Legendary Creature — Angel", "Flying\nActivated abilities of creatures "
               "your opponents control can't be activated.", "3", "4", colors=("W",))
SILENCE = real("Deafening Silence", "{W}", "Enchantment", "Each player can't cast more than one noncreature spell each turn.",
               colors=("W",))
CORPSEJACK = real("Corpsejack Menace", "{2}{B}{G}", "Creature — Fungus", "If one or more +1/+1 counters would be put on a creature "
                  "you control, twice that many +1/+1 counters are put on it instead.", "4", "4", colors=("B", "G"))
MENTOR = real("Conclave Mentor", "{G}{W}", "Creature — Centaur Cleric", "If one or more +1/+1 counters would be put on a creature "
              "you control, that many plus one +1/+1 counters are put on that creature instead.\nWhen this creature dies, you gain "
              "life equal to its power.", "2", "2", colors=("G", "W"))
RAZORKIN = real("Razorkin Needlehead", "{R}{R}", "Creature — Human Assassin", "This creature has first strike during your "
                "turn.\nWhenever an opponent draws a card, this creature deals 1 damage to them.", "2", "2", colors=("R",))
WARDEN = real("Warden of Evos Isle", "{2}{U}", "Creature — Bird Wizard", "Flying\nCreature spells with flying you cast cost {1} "
              "less to cast.", "2", "2", colors=("U",))
WARGATE = real("Wargate", "{X}{G}{W}{U}", "Sorcery", "Search your library for a permanent card with mana value X or less, put it "
               "onto the battlefield, then shuffle.", colors=("G", "U", "W"))
ALESHA = real("Alesha, Who Laughs at Fate", "{1}{B}{R}", "Legendary Creature — Human Warrior", "First strike\nWhenever Alesha "
              "attacks, put a +1/+1 counter on it.\nRaid — At the beginning of your end step, if you attacked this turn, return "
              "target creature card with mana value less than or equal to Alesha's power from your graveyard to the battlefield.",
              "2", "2", colors=("B", "R"))
HELLION = real("Hellion Eruption", "{5}{R}", "Sorcery", "Sacrifice all creatures you control, then create that many 4/4 red "
               "Hellion creature tokens.", colors=("R",))
SHROOFUS = real("Shroofus Sproutsire", "{2}{G}", "Legendary Creature — Saproling", "Trample\nWhenever a Saproling you control "
                "deals combat damage to a player, create that many 1/1 green Saproling creature tokens.", "1", "1", colors=("G",))
PULSE = real("Essence Pulse", "{3}{B}", "Sorcery", "You gain 2 life. Each creature gets -X/-X until end of turn, where X is the "
             "amount of life you gained this turn.", colors=("B",))
COLLECTOR = real("Specimen Collector", "{4}{U}", "Creature — Vedalken Wizard", "When this creature enters, create a 1/1 green "
                 "Squirrel creature token and a 0/3 blue Crab creature token.\nWhen this creature dies, create a token that's a "
                 "copy of target token you control.", "2", "1", colors=("U",))
FLOW = real("Flow of Knowledge", "{4}{U}", "Instant", "Draw a card for each Island you control, then discard two cards.",
            colors=("U",))
CARNIVAL = real("Carnival of Souls", "{1}{B}", "Enchantment", "Whenever a creature enters, you lose 1 life and add {B}.",
                colors=("B",))
CADIRA = real("Cadira, Caller of the Small", "{1}{G}{W}", "Legendary Creature — Orc Ranger", "Trample\nWhenever Cadira deals "
              "combat damage to a player, for each token you control, create a 1/1 white Rabbit creature token.",
              "3", "3", colors=("G", "W"))
OJUTAI = real("Dragonlord Ojutai", "{3}{W}{U}", "Legendary Creature — Elder Dragon", "Flying\nDragonlord Ojutai has hexproof as "
              "long as it's untapped.\nWhenever Dragonlord Ojutai deals combat damage to a player, look at the top three cards of "
              "your library. Put one of them into your hand and the rest on the bottom of your library in any order.",
              "5", "4", colors=("U", "W"))
ORRERY = real("Ghirapur Orrery", "{4}", "Artifact", "Each player may play an additional land on each of their turns.\nAt the "
              "beginning of each player's upkeep, if that player has no cards in hand, that player draws three cards.")
SOWER = real("Sower of Temptation", "{2}{U}{U}", "Creature — Faerie Wizard", "Flying\nWhen this creature enters, gain control of "
             "target creature for as long as this creature remains on the battlefield.", "2", "2", colors=("U",))
REVERENCE = real("Wall of Reverence", "{3}{W}", "Creature — Spirit Wall", "Defender, flying\nAt the beginning of your end step, "
                 "you may gain life equal to the power of target creature you control.", "1", "6", colors=("W",))
RUIN = real("Field of Ruin", "", "Land", "{T}: Add {C}.\n{2}, {T}, Sacrifice this land: Destroy target nonbasic land an opponent "
            "controls. Each player searches their library for a basic land card, puts it onto the battlefield, then shuffles.")
DREDGE = real("Dredge", "{B}", "Instant", "Sacrifice a creature or land.\nDraw a card.", colors=("B",))
FAULT = real("Volatile Fault", "", "Land — Cave", "{T}: Add {C}.\n{1}, {T}, Sacrifice this land: Destroy target nonbasic land an "
             "opponent controls. That player may search their library for a basic land card, put it onto the battlefield, then "
             "shuffle. You create a Treasure token.")
JURI = real("Juri, Master of the Revue", "{B}{R}", "Legendary Creature — Human Shaman", "Whenever you sacrifice a permanent, put a "
            "+1/+1 counter on Juri.\nWhen Juri dies, it deals damage equal to its power to any target.", "1", "1", colors=("B", "R"))
OMNITOOL = real("Adaptive Omnitool", "{2}", "Artifact — Equipment", "Equipped creature gets +1/+1 for each artifact you "
                "control.\nWhenever equipped creature attacks, look at the top six cards of your library. You may reveal an "
                "artifact card from among them and put it into your hand. Put the rest on the bottom of your library in a random "
                "order.\nEquip {3}")
EXCALIBUR = real("Excalibur II", "{1}", "Legendary Artifact — Equipment", "Whenever you gain life, put a charge counter on "
                 "Excalibur II.\nEquipped creature gets +1/+1 for each charge counter on Excalibur II.\nEquip {3}")
HUMAN = real("Squire", "{1}{W}", "Creature — Human Soldier", "", "1", "2", colors=("W",))
MERFOLK = real("Silvergill Adept", "{1}{U}", "Creature — Merfolk Wizard", "", "2", "1", colors=("U",))
LEGEND = real("Isamaru, Hound of Konda", "{W}", "Legendary Creature — Dog", "", "2", "2", colors=("W",))
BLACK = real("Walking Corpse", "{1}{B}", "Creature — Zombie", "", "2", "2", colors=("B",))
TEMPLE = real("Temple", "", "Land", "{T}: Add {C}.")
CARDS = (RITES, MANGLEHORN, THALIA, HELM, EDGE, VANGUARD, TUNNEL, SVYELUN, LINVALA, SILENCE, CORPSEJACK, MENTOR, RAZORKIN, WARDEN,
         WARGATE, ALESHA, HELLION, SHROOFUS, PULSE, COLLECTOR, FLOW, CARNIVAL, CADIRA, OJUTAI, ORRERY, SOWER, REVERENCE, RUIN, DREDGE,
         FAULT, JURI, OMNITOOL, EXCALIBUR)


def step(game, seat, name):
    game.active, game.step = seat.index, name
    game._turn_based_actions(seat)
    run_stack(game)


class ParseOnlyBatch3Tests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in CARDS:
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_rites_of_flourishing_gives_every_player_a_land_drop(self):
        game, _ = table3()
        a, b, _ = game.seats
        self.assertEqual(game._land_drops(b), 1)
        b.battlefield = [Permanent(RITES)]
        self.assertEqual((game._land_drops(a), game._land_drops(b)), (2, 2))

    def test_manglehorn_taps_only_an_opponents_artifacts(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(MANGLEHORN)]
        theirs, mine, bear = enter(game, b, RELIC), enter(game, a, RELIC), enter(game, b, BEAR)
        self.assertEqual((theirs.tapped, mine.tapped, bear.tapped), (True, False, False))

    def test_thalia_taps_an_opponents_creatures_and_nonbasic_lands(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(THALIA)]
        bear, temple, forest, mine = enter(game, b, BEAR), enter(game, b, TEMPLE), enter(game, b, FOREST), enter(game, a, BEAR)
        self.assertEqual((bear.tapped, temple.tapped, forest.tapped, mine.tapped), (True, True, False, False))

    def test_champions_helm_gives_hexproof_only_to_a_legend(self):
        game, _ = table3()
        a = game.seats[0]
        legend, bear = Permanent(LEGEND), Permanent(BEAR)
        a.battlefield = [legend, bear, Permanent(HELM, attached_to=legend), Permanent(HELM, attached_to=bear)]
        self.assertEqual((game.has_keyword(legend, "hexproof"), game.has_keyword(bear, "hexproof")), (True, False))
        self.assertEqual((game.power(legend), game.power(bear)), (4, 4))

    def test_edge_of_the_divinity_reads_the_creatures_color(self):
        game, _ = table3()
        a = game.seats[0]
        white, black, bear = Permanent(LEGEND), Permanent(BLACK), Permanent(BEAR)
        a.battlefield = [white, black, bear] + [Permanent(EDGE, attached_to=p) for p in (white, black, bear)]
        self.assertEqual([(game.power(p), game.toughness(p)) for p in (white, black, bear)], [(3, 4), (4, 3), (2, 2)])

    def test_coppercoat_vanguard_pumps_your_other_humans(self):
        game, _ = table3()
        a, b, _ = game.seats
        vanguard, human, bear, theirs = Permanent(VANGUARD), Permanent(HUMAN), Permanent(BEAR), Permanent(HUMAN)
        a.battlefield, b.battlefield = [vanguard, human, bear], [theirs]
        self.assertEqual([game.power(p) for p in (vanguard, human, bear, theirs)], [2, 2, 2, 1])
        self.assertEqual((game.has_keyword(human, "ward {1}"), game.has_keyword(bear, "ward {1}")), (True, False))

    def test_aether_tunnel_makes_the_creature_unblockable(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear, Permanent(TUNNEL, attached_to=bear)]
        self.assertEqual((game.power(bear), game.has_keyword(bear, "can't be blocked")), (3, True))

    def test_svyelun_is_indestructible_with_two_other_merfolk_and_guards_only_yours(self):
        game, _ = table3()
        a, b, _ = game.seats
        svyelun, merfolk = Permanent(SVYELUN), Permanent(MERFOLK)
        a.battlefield, b.battlefield = [svyelun, merfolk], [Permanent(MERFOLK)]
        self.assertFalse(game.has_keyword(svyelun, "indestructible"))  # one other Merfolk of yours: an opponent's doesn't count
        a.battlefield.append(Permanent(MERFOLK))
        self.assertTrue(game.has_keyword(svyelun, "indestructible"))
        self.assertEqual((game.has_keyword(merfolk, "ward {1}"), game.has_keyword(b.battlefield[0], "ward {1}")), (True, False))

    def test_linvala_locks_only_an_opponents_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        mine, theirs, relic = Permanent(BEAR), Permanent(BEAR), Permanent(RELIC)
        a.battlefield, b.battlefield = [Permanent(LINVALA), mine], [theirs, relic]
        self.assertEqual((game._ability_barred(theirs), game._ability_barred(mine), game._ability_barred(relic)), (True, False, False))

    def test_deafening_silence_allows_one_noncreature_spell_a_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(SILENCE)]
        self.assertFalse(game._cast_barred(b, DIVINATION))
        b.cast_log = [(game.turn, BOLT)]
        self.assertEqual((game._cast_barred(b, DIVINATION), game._cast_barred(b, BEAR)), (True, False))

    def test_corpsejack_doubles_and_conclave_mentor_adds_one(self):
        for card, placed in ((CORPSEJACK, 4), (MENTOR, 3)):
            game, _ = table3()
            a, b, _ = game.seats
            bear, theirs = Permanent(BEAR), Permanent(BEAR)
            a.battlefield, b.battlefield = [Permanent(card), bear], [theirs]
            game.put_counters(bear, "+1/+1", 2, by=a)
            game.put_counters(theirs, "+1/+1", 2, by=b)
            self.assertEqual((bear.counters.get("+1/+1"), theirs.counters.get("+1/+1")), (placed, 2), card.name)

    def test_razorkin_has_first_strike_only_on_your_turn_and_pings_a_drawing_opponent(self):
        game, _ = table3()
        a, b, _ = game.seats
        razorkin = Permanent(RAZORKIN)
        a.battlefield, b.library = [razorkin], [FOREST] * 3
        self.assertTrue(game.has_keyword(razorkin, "first strike"))
        game.active = 1
        self.assertFalse(game.has_keyword(razorkin, "first strike"))
        life = b.life
        game.draw(b, 1)
        run_stack(game)
        self.assertEqual(b.life, life - 1)

    def test_warden_of_evos_isle_reduces_only_creature_spells_with_flying(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(WARDEN)]
        self.assertEqual((game.cost_reduction(a, BIRD), game.cost_reduction(a, BEAR)), (1, 0))

    def test_wargate_puts_a_permanent_card_of_mana_value_x_or_less_onto_the_battlefield(self):
        game, _ = table3(pick("1", "Relic"))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(4), [WARGATE], [DIVINATION, RELIC, OGRE]
        game._perform(a, CAST + "Wargate")
        run_stack(game)
        self.assertIn("Relic", [p.card.name for p in a.battlefield])
        self.assertIn("Divination", [c.name for c in a.library])

    def test_alesha_returns_a_creature_no_bigger_than_her_power(self):
        game, _ = table3(pick("Ogre"))
        a = game.seats[0]
        alesha = Permanent(ALESHA)
        alesha.counters["+1/+1"] = 1
        a.battlefield, a.graveyard = [alesha], [OGRE]
        step(game, a, "end")  # Raid: no attack this turn, nothing comes back
        self.assertEqual(a.graveyard, [OGRE])
        a.attackers_turn, a.most_attackers = game.turn, 1
        step(game, a, "end")
        self.assertIn("Ogre", [p.card.name for p in a.battlefield])

    def test_hellion_eruption_makes_one_hellion_for_each_creature_sacrificed(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand = [Permanent(BEAR), Permanent(OGRE), *lands(6)], [HELLION]
        game._perform(a, CAST + "Hellion Eruption")
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Creature" in p.card.type_line), ["Hellion", "Hellion"])

    def test_shroofus_makes_as_many_saprolings_as_the_damage(self):
        game, _ = table3()
        a, b, _ = game.seats
        shroofus = Permanent(SHROOFUS)
        a.battlefield = [shroofus]
        game.damage(b, 3, shroofus, combat=True)
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Saproling" for p in a.battlefield), 3)

    def test_essence_pulse_shrinks_every_players_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        mine, theirs = Permanent(OGRE), Permanent(OGRE)
        a.battlefield, a.hand, b.battlefield = [mine, *lands(4)], [PULSE], [theirs]
        game._perform(a, CAST + "Essence Pulse")
        run_stack(game)
        self.assertEqual((game.power(mine), game.power(theirs)), (1, 1))

    def test_specimen_collector_makes_a_squirrel_and_a_crab(self):
        game, _ = table3()
        a = game.seats[0]
        enter(game, a, COLLECTOR)
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Crab", "Specimen Collector", "Squirrel"])

    def test_flow_of_knowledge_draws_per_island_then_discards_two(self):
        island = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand, a.library = [Permanent(island) for _ in range(5)], [FLOW], [FOREST] * 6
        game._perform(a, CAST + "Flow of Knowledge")
        run_stack(game)
        self.assertEqual((len(a.hand), len(a.graveyard)), (3, 3))

    def test_carnival_of_souls_adds_black_and_costs_life(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(CARNIVAL)]
        life = a.life
        enter(game, b, BEAR)
        run_stack(game)
        self.assertEqual((a.life, a.mana_pool), (life - 1, [frozenset("B")]))

    def test_cadira_makes_a_rabbit_for_each_token(self):
        game, _ = table3()
        a, b, _ = game.seats
        cadira = Permanent(CADIRA)
        a.battlefield = [cadira, Permanent(SPIRIT), Permanent(SPIRIT), Permanent(BEAR)]
        game.damage(b, 3, cadira, combat=True)
        run_stack(game)
        self.assertEqual(sum(p.card.name == "Rabbit" for p in a.battlefield), 2)

    def test_dragonlord_ojutai_has_hexproof_while_untapped(self):
        game, _ = table3()
        a = game.seats[0]
        ojutai = Permanent(OJUTAI)
        a.battlefield = [ojutai]
        self.assertTrue(game.has_keyword(ojutai, "hexproof"))
        ojutai.tapped = True
        self.assertFalse(game.has_keyword(ojutai, "hexproof"))

    def test_ghirapur_orrery_refills_only_an_empty_hand(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(ORRERY)]
        b.library, c.library, c.hand = [FOREST] * 5, [FOREST] * 5, [FOREST]
        step(game, b, "upkeep")
        step(game, c, "upkeep")
        self.assertEqual((len(b.hand), len(c.hand)), (3, 1))

    def test_sower_of_temptation_keeps_the_creature_only_while_it_remains(self):
        game, _ = table3(pick("Ogre"))
        a, b, _ = game.seats
        ogre = Permanent(OGRE)
        b.battlefield = [ogre]
        sower = enter(game, a, SOWER)
        run_stack(game)
        game.active = 1
        end_turn(game, b)  # not "until end of turn"
        game.gain_control(sower, b)  # nor "for as long as you control" it
        game._check_state()
        self.assertIn(ogre, a.battlefield)
        game.destroy(sower)
        game._check_state()
        self.assertIn(ogre, b.battlefield)

    def test_wall_of_reverence_gains_life_equal_to_your_creatures_power(self):
        game, _ = table3(pick("Ogre", "Yes"))
        a = game.seats[0]
        a.battlefield = [Permanent(REVERENCE), Permanent(OGRE)]
        life = a.life
        step(game, a, "end")
        self.assertEqual(a.life, life + 3)

    def test_field_of_ruin_gives_every_player_a_basic(self):
        game, _ = table3(pick("Temple"))
        a, b, c = game.seats
        a.battlefield, b.battlefield = [Permanent(RUIN), *lands(2)], [Permanent(TEMPLE)]
        for seat in (a, b, c):
            seat.library = [FOREST, OGRE]
        activate(game, a, "Field of Ruin")
        self.assertEqual([[p.card.name for p in s.battlefield if p.card is FOREST] for s in (a, b, c)], [["Forest"]] * 3)
        self.assertNotIn("Temple", [p.card.name for p in b.battlefield])

    def test_volatile_fault_lets_only_the_land_lose_player_search_and_gives_a_treasure(self):
        game, _ = table3(pick("Temple", "Yes"), pick("Yes"))
        a, b, c = game.seats
        a.battlefield, b.battlefield = [Permanent(FAULT), *lands(1)], [Permanent(TEMPLE)]
        for seat in (a, b, c):
            seat.library = [FOREST, OGRE]
        activate(game, a, "Volatile Fault")
        self.assertEqual([[p.card.name for p in s.battlefield if p.card is FOREST] for s in (a, b, c)], [[], ["Forest"], []])
        self.assertIn("Treasure", [p.card.name for p in a.battlefield])

    def test_dredge_sacrifices_a_creature_or_land_then_draws(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = [Permanent(BEAR), Permanent(RELIC), *lands(1)], [DREDGE], [FOREST]
        game._perform(a, CAST + "Dredge")
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], len(a.hand), "Relic" in [p.card.name for p in a.battlefield]),
                         (["Bear", "Dredge"], 1, True))

    def test_juri_grows_whenever_you_sacrifice_a_permanent(self):
        game, _ = table3(pick("Bear"))
        a, b, _ = game.seats
        juri = Permanent(JURI)
        a.battlefield, b.battlefield = [juri, Permanent(BEAR)], [Permanent(BEAR)]
        game.sacrifice(b, "creature")  # an opponent's sacrifice doesn't count
        run_stack(game)
        self.assertEqual(juri.counters.get("+1/+1", 0), 0)
        game.sacrifice(a, "creature", exclude=juri)
        run_stack(game)
        self.assertEqual(juri.counters.get("+1/+1", 0), 1)

    def test_adaptive_omnitool_takes_an_artifact_from_the_top_six(self):
        game, _ = table3(pick("Relic", "Yes"))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield, a.library = [bear, Permanent(OMNITOOL, attached_to=bear)], [FOREST, OGRE, RELIC, FOREST, FOREST, FOREST, OGRE]
        game.trigger("host_attacks", a.battlefield[1], a, bear)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], len(a.library)), (["Relic"], 6))

    def test_excalibur_grows_with_charge_counters_from_life_gain(self):
        game, _ = table3()
        a = game.seats[0]
        bear = Permanent(BEAR)
        sword = Permanent(EXCALIBUR, attached_to=bear)
        a.battlefield = [bear, sword]
        game.change_life(a, 2)
        game.change_life(a, 1)
        run_stack(game)
        self.assertEqual((sword.counters.get("charge"), game.power(bear)), (2, 4))


if __name__ == "__main__":
    unittest.main()
