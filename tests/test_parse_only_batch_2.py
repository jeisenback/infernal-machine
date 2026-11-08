"""The second batch of cards whose every effect the engine already had, read from new wordings (each picked with Forge's card scripts),
from their real Oracle text: power and toughness thresholds on targets (Valorous Stance, Warping Wail), "multicolored", damage to
"creature you don't control" (Mizzium Mortars), Crux of Fate; "Other Elf creatures", "Other Merfolk", "All Slivers", "Zombie tokens
you control", "with +1/+1 counters on them", "nontoken" lords; "each player" and "that player ... and ..." sentences (Stormfist
Crusader, Burning Inquiry, Seizan, Sword of Body and Mind); one-word variants of graveyard returns, untaps, fights and searches; and
"Untap those creatures.", "That creature gains ..." after an Equipment attaches, "put that many +1/+1 counters", named modes."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent, StackItem
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, activate, enter, lands, pick, real, run_stack, table3

STANCE = real("Valorous Stance", "{1}{W}", "Instant", "Choose one —\n• Target creature gains indestructible until end of turn. "
              "(Damage and effects that say \"destroy\" don't destroy it.)\n• Destroy target creature with toughness 4 or greater.",
              colors=("W",))
WAIL = real("Warping Wail", "{1}{C}", "Instant", "({C} represents colorless mana.)\nChoose one —\n• Exile target creature with "
            "power or toughness 1 or less.\n• Counter target sorcery spell.\n• Create a 1/1 colorless Eldrazi Scion creature "
            "token. It has \"Sacrifice this token: Add {C}.\"")
BLAST = real("Null Elemental Blast", "{C}", "Instant", "Choose one —\n• Counter target multicolored spell.\n• Destroy target "
             "multicolored permanent.")
MORTARS = real("Mizzium Mortars", "{1}{R}", "Sorcery", "Mizzium Mortars deals 4 damage to target creature you don't control.\nOverload "
               "{3}{R}{R}{R} (You may cast this spell for its overload cost. If you do, change \"target\" in its text to \"each.\")",
               colors=("R",))
CRUX = real("Crux of Fate", "{3}{B}{B}", "Sorcery", "Choose one —\n• Destroy all Dragon creatures.\n• Destroy all non-Dragon "
            "creatures.", colors=("B",))
CHAMPION = real("Elvish Champion", "{1}{G}{G}", "Creature — Elf", "Other Elf creatures get +1/+1 and have forestwalk. (They can't be "
                "blocked as long as defending player controls a Forest.)", "2", "2", colors=("G",))
ATLANTIS = real("Lord of Atlantis", "{U}{U}", "Creature — Merfolk", "Other Merfolk get +1/+1 and have islandwalk. (They can't be "
                "blocked as long as defending player controls an Island.)", "2", "2", colors=("U",))
CRYSTALLINE = real("Crystalline Sliver", "{W}{U}", "Creature — Sliver", "All Slivers have shroud. (They can't be the targets of "
                   "spells or abilities.)", "2", "2", colors=("W", "U"))
SKYLORD = real("Eternal Skylord", "{4}{U}", "Creature — Zombie Wizard", "When this creature enters, amass Zombies 2. (Put two +1/+1 "
               "counters on an Army you control. It's also a Zombie. If you don't control an Army, create a 0/0 black Zombie Army creature "
               "token first.)\nZombie tokens you control have flying.", "3", "3", colors=("U",))
BADGERMOLE = real("Badgermole", "{4}{G}", "Creature — Badger Mole", "When this creature enters, earthbend 2. (Target land you control "
                  "becomes a 0/0 creature with haste that's still a land. Put two +1/+1 counters on it. When it dies or is exiled, return it "
                  "to the battlefield tapped.)\nCreatures you control with +1/+1 counters on them have trample.", "4", "4", colors=("G",))
WATCHER = real("Thraben Watcher", "{2}{W}{W}", "Creature — Angel", "Flying, vigilance\nOther nontoken creatures you control get +1/+1 "
               "and have vigilance.", "2", "2", colors=("W",))
STORMFIST = real("Stormfist Crusader", "{B}{R}", "Creature — Human Knight", "Menace\nAt the beginning of your upkeep, each player "
                 "draws a card and loses 1 life.", "2", "2", colors=("B", "R"))
INQUIRY = real("Burning Inquiry", "{R}", "Sorcery", "Each player draws three cards, then discards three cards at random.", colors=("R",))
SEIZAN = real("Seizan, Perverter of Truth", "{3}{B}{B}", "Legendary Creature — Demon Spirit", "At the beginning of each player's "
              "upkeep, that player loses 2 life and draws two cards.", "6", "5", colors=("B",))
BODY_MIND = real("Sword of Body and Mind", "{3}", "Artifact — Equipment", "Equipped creature gets +2/+2 and has protection from green "
                 "and from blue.\nWhenever equipped creature deals combat damage to a player, you create a 2/2 green Wolf creature token "
                 "and that player mills ten cards.\nEquip {2}")
PUPPETEER = real("Gixian Puppeteer", "{3}{B}", "Creature — Phyrexian Warlock", "Whenever you draw your second card each turn, each "
                 "opponent loses 2 life and you gain 2 life.\nWhen this creature dies, return another target creature card with mana value "
                 "3 or less from your graveyard to the battlefield.", "4", "3", colors=("B",))
NAYA = real("Naya Charm", "{R}{G}{W}", "Instant", "Choose one —\n• Naya Charm deals 3 damage to target creature.\n• Return "
            "target card from a graveyard to its owner's hand.\n• Tap all creatures target player controls.", colors=("R", "G", "W"))
LION = real("Whitemane Lion", "{1}{W}", "Creature — Cat", "Flash\nWhen this creature enters, return a creature you control to its "
            "owner's hand.", "2", "2", colors=("W",))
RESHAPE = real("Reshape the Earth", "{6}{G}{G}{G}", "Sorcery", "Search your library for up to ten land cards, put them onto the "
               "battlefield tapped, then shuffle.", colors=("G",))
IORETH = real("Ioreth of the Healing House", "{2}{U}", "Legendary Creature — Human Cleric", "{T}: Untap another target permanent.\n"
              "{T}: Untap two other target legendary creatures.", "1", "4", colors=("U",))
PESTILENCE = real("Pestilence", "{2}{B}{B}", "Enchantment", "At the beginning of the end step, if no creatures are on the battlefield, "
                  "sacrifice this enchantment.\n{B}: This enchantment deals 1 damage to each creature and each player.", colors=("B",))
SNUFFERS = real("Soul Snuffers", "{2}{B}{B}", "Creature — Elemental Shaman", "When this creature enters, put a -1/-1 counter on each "
                "creature.", "3", "3", colors=("B",))
GHOUL = real("Noxious Ghoul", "{3}{B}{B}", "Creature — Zombie", "Whenever this creature or another Zombie enters, all non-Zombie "
             "creatures get -1/-1 until end of turn.", "3", "3", colors=("B",))
STRETCH = real("Time Stretch", "{8}{U}{U}", "Sorcery", "Target player takes two extra turns after this one.", colors=("U",))
COSTUME = real("Silver Shroud Costume", "{2}", "Artifact — Equipment", "Flash\nWhen this Equipment enters, attach it to target "
               "creature you control. That creature gains shroud until end of turn. (It can't be the target of spells or abilities.)\n"
               "Equipped creature can't be blocked.\nEquip {3}")
ASCENDANCY = real("Jeskai Ascendancy", "{U}{R}{W}", "Enchantment", "Whenever you cast a noncreature spell, creatures you control get "
                  "+1/+1 until end of turn. Untap those creatures.\nWhenever you cast a noncreature spell, you may draw a card. If you do, "
                  "discard a card.", colors=("U", "R", "W"))
HYDRA = real("Hungering Hydra", "{X}{G}", "Creature — Hydra", "This creature enters with X +1/+1 counters on it.\nThis creature "
             "can't be blocked by more than one creature.\nWhenever this creature is dealt damage, put that many +1/+1 counters on it. (It "
             "must survive the damage to get the counters.)", "0", "0", colors=("G",))
MAKO = real("Marauding Mako", "{U}{R}", "Creature — Shark", "Whenever you discard one or more cards, put that many +1/+1 counters on "
            "this creature.\nCycling {2} ({2}, Discard this card: Draw a card.)", "1", "1", colors=("U", "R"))
WOODLAND = real("Woodland Champion", "{1}{G}", "Creature — Elf Scout", "Whenever one or more tokens you control enter, put that many "
                "+1/+1 counters on this creature.", "2", "2", colors=("G",))
TEMPLE = real("Your Temple Is Under Attack", "{2}{W}", "Instant", "Choose one —\n• Pray for Protection — Creatures you "
              "control gain indestructible until end of turn.\n• Strike a Deal — You and target opponent each draw two cards.",
              colors=("W",))
BUGLE = real("Daily Bugle Building", "", "Land", "{T}: Add {C}.\n{1}, {T}: Add one mana of any color.\nSmear Campaign — {1}, {T}: "
             "Target legendary creature gains menace until end of turn. Activate only as a sorcery.")

ELF = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))
MERFOLK = real("Merfolk Looter", "{1}{U}", "Creature — Merfolk Rogue", "", "1", "1", colors=("U",))
SLIVER = real("Muscle Sliver", "{1}{G}", "Creature — Sliver", "", "2", "2", colors=("G",))
DRAGON = real("Shivan Dragon", "{4}{R}{R}", "Creature — Dragon", "Flying", "5", "5", colors=("R",))
GOLD = real("Gold Bear", "{G}{W}", "Creature — Bear", "", "2", "2", colors=("G", "W"))
ZOMBIE = real("Walking Corpse", "{1}{B}", "Creature — Zombie", "", "2", "2", colors=("B",))
TAPLAND = real("Ancient Den", "", "Artifact Land", "{T}: Add {W}.")
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))


def names(seat):
    return [p.card.name for p in seat.battlefield]


class TargetKindTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (STANCE, WAIL, BLAST, MORTARS, CRUX, CHAMPION, ATLANTIS, CRYSTALLINE, SKYLORD, BADGERMOLE, WATCHER, STORMFIST,
                     INQUIRY, SEIZAN, BODY_MIND, PUPPETEER, NAYA, LION, RESHAPE, IORETH, PESTILENCE, SNUFFERS, GHOUL, STRETCH, COSTUME,
                     ASCENDANCY, HYDRA, MAKO, TEMPLE, BUGLE):
            self.assertEqual(unsupported_lines(card), [], card.name)
        self.assertTrue(unsupported_lines(WOODLAND))  # a batch of tokens carries no count: "that many" stays unread
        pillage = real("Heartless Pillage", "{2}{B}", "Sorcery", "Target opponent discards two cards.\nRaid \u2014 If you attacked this "
                       "turn, create a Treasure token. (It's an artifact with \"{T}, Sacrifice this token: Add one mana of any color.\")",
                       colors=("B",))
        self.assertTrue(unsupported_lines(pillage))  # an ability word on a spell's line is no mode name: still not read

    def test_valorous_stance_destroys_only_a_creature_with_toughness_4_or_greater_now(self):
        asked = []
        game, _ = table3(lambda prompt, options: asked.append(list(options)) or pick("Destroy", "Ogre")(prompt, options))
        a, b, _ = game.seats
        ogre, bear = Permanent(OGRE), Permanent(BEAR)
        ogre.counters["+1/+1"] = 1  # 4/4 now: its toughness as it is, counters included
        a.battlefield, a.hand, b.battlefield = lands(2), [STANCE], [ogre, bear]
        game._perform(a, CAST + "Valorous Stance")
        run_stack(game)
        self.assertNotIn("Bear", " ".join(o for options in asked for o in options))
        self.assertEqual(names(b), ["Bear"])

    def test_warping_wail_takes_power_or_toughness_1_or_less(self):
        asked = []
        game, _ = table3(lambda prompt, options: asked.append(list(options)) or pick("Exile", "Llanowar")(prompt, options))
        a, b, _ = game.seats
        a.battlefield, a.hand, b.battlefield = lands(2, WASTES), [WAIL], [Permanent(ELF), Permanent(BEAR)]
        game._perform(a, CAST + "Warping Wail")
        run_stack(game)
        self.assertNotIn("Bear", " ".join(o for options in asked for o in options))
        self.assertEqual(names(b), ["Bear"])

    def test_null_elemental_blast_counters_only_a_multicolored_spell(self):
        for spell, countered in ((GOLD, True), (BEAR, False)):
            game, _ = table3(pick("Counter", "Spell"))
            a, b, _ = game.seats
            a.battlefield, a.hand = lands(1, WASTES), [BLAST]
            game.stack.append(StackItem(spell, b))
            game._perform(a, CAST + "Null Elemental Blast")
            if countered:
                game._resolve(game.stack.pop())
            self.assertEqual(len(b.graveyard), int(countered), spell.name)

    def test_mizzium_mortars_cannot_hit_your_own_creature(self):
        asked = []
        game, _ = table3(lambda prompt, options: asked.append(list(options)) or pick("Ogre")(prompt, options))
        a, b, _ = game.seats
        a.battlefield, a.hand, b.battlefield = [Permanent(BEAR), *lands(2)], [MORTARS], [Permanent(OGRE)]
        game._perform(a, CAST + "Mizzium Mortars")
        run_stack(game)
        game._check_state()
        self.assertNotIn("Bear", " ".join(o for options in asked for o in options if "Bear" in o and "seat 0" in o))
        self.assertEqual((names(b), "Bear" in names(a)), ([], True))

    def test_crux_of_fate_spares_dragons_in_its_non_dragon_mode(self):
        game, _ = table3(pick("Destroy all non-Dragon"))
        a, b, _ = game.seats
        a.battlefield, a.hand, b.battlefield = lands(5), [CRUX], [Permanent(DRAGON), Permanent(BEAR)]
        game._perform(a, CAST + "Crux of Fate")
        run_stack(game)
        self.assertEqual(names(b), ["Shivan Dragon"])


class LordTests(unittest.TestCase):
    def test_elvish_champion_and_lord_of_atlantis_pump_every_players_creatures_of_the_type_but_themselves(self):
        game, _ = table3()
        a, b, _ = game.seats
        champion, atlantis, elf, merfolk = Permanent(CHAMPION), Permanent(ATLANTIS), Permanent(ELF), Permanent(MERFOLK)
        a.battlefield, b.battlefield = [champion, atlantis], [elf, merfolk, Permanent(BEAR)]
        self.assertEqual((game.power(elf), game.power(merfolk), game.power(champion), game.power(atlantis)), (2, 2, 2, 2))
        self.assertTrue(game.has_keyword(elf, "forestwalk") and game.has_keyword(merfolk, "islandwalk"))

    def test_crystalline_sliver_gives_every_sliver_shroud(self):
        game, _ = table3()
        a, b, _ = game.seats
        theirs = Permanent(SLIVER)
        a.battlefield, b.battlefield = [Permanent(CRYSTALLINE)], [theirs, Permanent(BEAR)]
        self.assertEqual((game.has_keyword(theirs, "shroud"), game.has_keyword(b.battlefield[1], "shroud")), (True, False))

    def test_eternal_skylord_flies_zombie_tokens_only(self):
        game, _ = table3()
        a = game.seats[0]
        token = Permanent(real("Zombie", "", "Token Creature — Zombie", "", "2", "2"))
        card = Permanent(ZOMBIE)
        a.battlefield = [Permanent(SKYLORD), token, card]
        self.assertEqual((game.has_keyword(token, "flying"), game.has_keyword(card, "flying")), (True, False))

    def test_badgermole_gives_trample_to_creatures_with_counters_and_thraben_watcher_skips_tokens(self):
        game, _ = table3()
        a = game.seats[0]
        countered, plain = Permanent(BEAR), Permanent(OGRE)
        countered.counters["+1/+1"] = 1
        token = Permanent(real("Soldier", "", "Token Creature — Soldier", "", "1", "1"))
        a.battlefield = [Permanent(BADGERMOLE), Permanent(WATCHER), countered, plain, token]
        self.assertEqual((game.has_keyword(countered, "trample"), game.has_keyword(plain, "trample")), (True, False))
        self.assertEqual((game.power(plain), game.power(token)), (4, 1))


class PlayerTests(unittest.TestCase):
    def test_stormfist_crusader_makes_each_player_draw_and_lose_life(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(STORMFIST)]
        for seat in game.seats:
            seat.library = [FOREST] * 2
        game.trigger("upkeep", a.battlefield[0], a)
        run_stack(game)
        self.assertEqual([(len(s.hand), s.life) for s in game.seats], [(1, 39)] * 3)

    def test_burning_inquiry_draws_three_then_discards_three_at_random(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield, a.hand = lands(1), [INQUIRY]
        for seat in game.seats:
            seat.library = [FOREST] * 4
        game._perform(a, CAST + "Burning Inquiry")
        run_stack(game)
        self.assertEqual([(len(s.hand), len(s.graveyard)) for s in game.seats], [(0, 4), (0, 3), (0, 3)])  # (a's spell too)

    def test_seizan_makes_the_player_whose_upkeep_it_is_lose_and_draw(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield, b.library = [Permanent(SEIZAN)], [FOREST] * 3
        game.step = "upkeep"
        game._turn_based_actions(b)  # b's upkeep begins
        run_stack(game)
        self.assertEqual((b.life, len(b.hand), a.life, c.life), (38, 2, 40, 40))

    def test_sword_of_body_and_mind_makes_a_wolf_and_mills_the_player_it_hit(self):
        game, _ = table3()
        a, b, _ = game.seats
        bear = Permanent(BEAR)
        a.battlefield, b.library = [bear, Permanent(BODY_MIND, attached_to=bear)], [FOREST] * 12
        game.damage(b, 4, bear, combat=True)
        run_stack(game)
        self.assertEqual(("Wolf" in names(a), len(b.graveyard), len(b.library)), (True, 10, 2))


class VariantTests(unittest.TestCase):
    def test_gixian_puppeteer_returns_another_creature_card_not_itself(self):
        asked = []
        game, _ = table3(lambda prompt, options: asked.append(list(options)) or pick("Bear")(prompt, options))
        a = game.seats[0]
        puppeteer = Permanent(PUPPETEER)
        a.battlefield, a.graveyard = [puppeteer], [BEAR]
        game._leave_battlefield(puppeteer, "destroyed")
        run_stack(game)
        self.assertNotIn("Gixian Puppeteer", " ".join(o for options in asked for o in options))
        self.assertIn("Bear", names(a))

    def test_naya_charm_taps_all_creatures_of_the_target_player_only(self):
        game, _ = table3(pick("Tap all", "Player: B"))
        a, b, c = game.seats
        theirs, others = Permanent(BEAR), Permanent(OGRE)
        a.battlefield, a.hand, b.battlefield, c.battlefield = lands(3), [NAYA], [theirs], [others]
        game._perform(a, CAST + "Naya Charm")
        run_stack(game)
        self.assertEqual((theirs.tapped, others.tapped), (True, False))

    def test_whitemane_lion_returns_a_creature_you_control(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR), Permanent(FOREST)]
        enter(game, a, LION)
        run_stack(game)
        self.assertEqual(([c.name for c in a.hand], "Forest" in names(a)), (["Bear"], True))

    def test_reshape_the_earth_finds_nonbasic_lands_too(self):
        game, _ = table3(pick("Ancient Den", "Forest"))
        a = game.seats[0]
        a.battlefield, a.hand, a.library = lands(9), [RESHAPE], [TAPLAND, FOREST, BEAR]
        game._perform(a, CAST + "Reshape the Earth")
        run_stack(game)
        self.assertEqual(sorted(n for n in names(a) if n != "City of Brass"), ["Ancient Den", "Forest"])

    def test_ioreth_untaps_two_other_legendary_creatures(self):
        game, _ = table3(pick("Seizan", "Kami"))
        a = game.seats[0]
        kami = Permanent(real("Kami", "{U}", "Legendary Creature — Spirit", "", "1", "1"), tapped=True)
        seizan, bear = Permanent(SEIZAN, tapped=True), Permanent(BEAR, tapped=True)
        a.battlefield = [Permanent(IORETH), seizan, kami, bear]
        activate(game, a, "two other target")
        run_stack(game)
        self.assertEqual((seizan.tapped, kami.tapped, bear.tapped), (False, False, True))


class EffectTests(unittest.TestCase):
    def test_pestilence_is_sacrificed_only_when_no_creature_is_left(self):
        for creatures, kept in (([], False), ([Permanent(BEAR)], True)):
            game, _ = table3()
            a, b, _ = game.seats
            a.battlefield, b.battlefield = [Permanent(PESTILENCE)], creatures
            game.trigger("each_end_step", a.battlefield[0], a)
            run_stack(game)
            self.assertEqual("Pestilence" in names(a), kept)

    def test_soul_snuffers_and_noxious_ghoul_reach_every_players_creatures(self):
        game, _ = table3()
        a, b, _ = game.seats
        ogre, zombie = Permanent(OGRE), Permanent(ZOMBIE)
        b.battlefield = [ogre, zombie]
        enter(game, a, SNUFFERS)
        run_stack(game)
        self.assertEqual((ogre.counters.get("-1/-1"), zombie.counters.get("-1/-1")), (1, 1))
        enter(game, a, GHOUL)
        run_stack(game)
        self.assertEqual((game.power(ogre), game.power(zombie)), (1, 1))  # 3/3 with a counter, -1/-1: the Zombie is spared

    def test_time_stretch_gives_two_extra_turns(self):
        game, _ = table3(pick("Player: A"))
        a = game.seats[0]
        a.battlefield, a.hand = lands(10), [STRETCH]
        game._perform(a, CAST + "Time Stretch")
        run_stack(game)
        self.assertEqual(game.extra_turns, [0, 0])

    def test_silver_shroud_costume_gives_the_creature_shroud_as_it_attaches(self):
        game, _ = table3(pick("Bear"))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        costume = enter(game, a, COSTUME)
        run_stack(game)
        self.assertEqual((costume.attached_to, game.has_keyword(bear, "shroud")), (bear, True))

    def test_jeskai_ascendancy_pumps_and_untaps(self):
        game, _ = table3(pick("No"))
        a = game.seats[0]
        bear = Permanent(BEAR, tapped=True)
        a.battlefield, a.hand = [Permanent(ASCENDANCY), bear, *lands(1)], [real("Opt", "{U}", "Instant", "Draw a card.")]
        a.library = [FOREST] * 2
        game._perform(a, CAST + "Opt")
        run_stack(game)
        self.assertEqual((bear.tapped, game.power(bear)), (False, 3))

    def test_hungering_hydra_and_marauding_mako_count_what_happened(self):
        game, _ = table3()
        a = game.seats[0]
        hydra, mako = Permanent(HYDRA), Permanent(MAKO)
        hydra.counters["+1/+1"] = 5
        a.battlefield, a.hand = [hydra, mako], [FOREST] * 3
        game.damage(hydra, 2, Permanent(OGRE))
        game.discard(a, 2)
        run_stack(game)
        self.assertEqual((hydra.counters["+1/+1"], mako.counters.get("+1/+1")), (7, 2))

    def test_a_named_mode_and_a_named_activated_ability(self):
        game, _ = table3(pick("Creatures you control"))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield, a.hand = [bear, *lands(3)], [TEMPLE]
        game._perform(a, CAST + "Your Temple Is Under Attack")
        run_stack(game)
        self.assertTrue(game.has_keyword(bear, "indestructible"))


if __name__ == "__main__":
    unittest.main()
