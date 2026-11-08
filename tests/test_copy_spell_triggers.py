"""Copy a spell (#659): Jin-Gitaxias, Progress Tyrant ("an artifact, instant, or sorcery spell", copied or countered once each turn),
Kitsa, Otterball Elite ("Activate only if Kitsa's power is 3 or greater"), Storm of Saruman ("copy it, except the copy isn't
legendary"), Wild Ricochet (new targets for a spell, then a copy of it), Bonus Round (each caster copies their own spells this turn)
Sword of Wealth and Power (the next instant or sorcery spell this turn), Krark, the Thumbless (a coin flip with both results),
Zada, Hedron Grinder (a copy for each other creature), Expansion // Explosion (a spell with mana value 4 or less), Pyromancer's
Goggles ("When that mana is spent to cast a red instant or sorcery spell, copy that spell") and Primal Amulet // Primal Wellspring
(charge counters, then "you may remove those counters and transform it"), Nalfeshnee ("Whenever you cast a spell from exile",
and a permanent spell's copy gains haste and an end step sacrifice), Twinning Staff (one copy more for each copying), Chain of Smog
and Chain of Vapor (the player it hit may copy it, and the bot never does) and Wondrous Crucible (a random nonland card from the graveyard,
cast as a copy)."""

import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.game import CAST_EXILE, CHAIN_COPY_OPTIONS, CHAIN_COPY_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BOLT, FOREST, OGRE, lands, pick, real, run_stack, scryfall, table

JIN = real("Jin-Gitaxias, Progress Tyrant", "{5}{U}{U}", "Legendary Creature — Phyrexian Praetor",
           "Whenever you cast an artifact, instant, or sorcery spell, copy that spell. You may choose new targets for the copy. This ability "
           "triggers only once each turn. (A copy of a permanent spell becomes a token.)\nWhenever an opponent casts an artifact, instant, or "
           "sorcery spell, counter that spell. This ability triggers only once each turn.", "5", "5", colors=("U",))
KITSA = real("Kitsa, Otterball Elite", "{1}{U}", "Legendary Creature — Otter Wizard",
             "Vigilance\nProwess (Whenever you cast a noncreature spell, this creature gets +1/+1 until end of turn.)\n{T}: Draw a card, then "
             "discard a card.\n{2}, {T}: Copy target instant or sorcery spell you control. You may choose new targets for the copy. Activate "
             "only if Kitsa's power is 3 or greater.", "1", "3", colors=("U",))
SARUMAN = real("Storm of Saruman", "{4}{U}{U}", "Enchantment",
               "Ward {3}\nWhenever you cast your second spell each turn, copy it, except the copy isn't legendary. You may choose new targets "
               "for the copy. (A copy of a permanent spell becomes a token.)", colors=("U",))
RICOCHET = real("Wild Ricochet", "{2}{R}{R}", "Instant",
                "You may choose new targets for target instant or sorcery spell. Then copy that spell. You may choose new targets for the copy.",
                colors=("R",))
BONUS = real("Bonus Round", "{1}{R}{R}", "Sorcery",
             "Until end of turn, whenever a player casts an instant or sorcery spell, that player copies it and may choose new targets for "
             "the copy.", colors=("R",))
SWORD = real("Sword of Wealth and Power", "{3}", "Artifact — Equipment",
             "Equipped creature gets +2/+2 and has protection from instants and from sorceries.\nWhenever equipped creature deals combat "
             "damage to a player, create a Treasure token. When you next cast an instant or sorcery spell this turn, copy that spell. You may "
             "choose new targets for the copy.\nEquip {2}")
KRARK = real("Krark, the Thumbless", "{1}{R}", "Legendary Creature — Goblin Wizard",
             "Whenever you cast an instant or sorcery spell, flip a coin. If you lose the flip, return that spell to its owner's hand. If you "
             "win the flip, copy that spell, and you may choose new targets for the copy.\nPartner (You can have two commanders if both have "
             "partner.)", "2", "2", colors=("R",))
ZADA = real("Zada, Hedron Grinder", "{3}{R}", "Legendary Creature — Goblin Ally",
            "Whenever you cast an instant or sorcery spell that targets only Zada, copy that spell for each other creature you control that "
            "the spell could target. Each copy targets a different one of those creatures.", "3", "3", colors=("R",))
EXPANSION = real("Expansion", "{U/R}{U/R}", "Instant",
                 "Copy target instant or sorcery spell with mana value 4 or less. You may choose new targets for the copy.", colors=("U", "R"))
GROWTH = real("Giant Growth", "{G}", "Instant", "Target creature gets +3/+3 until end of turn.", colors=("G",))
BIG_STUDY = real("Deep Study", "{5}", "Sorcery", "Draw a card.")
GOGGLES = real("Pyromancer's Goggles", "{5}", "Legendary Artifact",
               "{T}: Add {R}. When that mana is spent to cast a red instant or sorcery spell, copy that spell and you may choose new targets "
               "for the copy.")
AMULET = Card.from_scryfall(scryfall(
    "transform",
    {"name": "Primal Amulet", "mana_cost": "{4}", "type_line": "Artifact",
     "oracle_text": "Instant and sorcery spells you cast cost {1} less to cast.\nWhenever you cast an instant or sorcery spell, put a "
                    "charge counter on this artifact. Then if there are four or more charge counters on it, you may remove those counters "
                    "and transform it."},
    {"name": "Primal Wellspring", "mana_cost": "", "type_line": "Land",
     "oracle_text": "(Transforms from Primal Amulet.)\n{T}: Add one mana of any color. When that mana is spent to cast an instant or "
                    "sorcery spell, copy that spell and you may choose new targets for the copy."}, cmc=4.0, colors=[]) | {"produced_mana": list("WUBRG")})
RED_STUDY = real("Red Study", "{R}", "Instant", "Draw a card.", colors=("R",))
BLUE_STUDY = real("Blue Study", "{1}", "Instant", "Draw a card.", colors=("U",))
MOUNTAIN = Card(name="Mountain", type_line="Basic Land — Mountain", produced_mana=("R",))
NALFESHNEE = real("Nalfeshnee", "{5}{R}", "Creature — Beast Demon",
                  "Flying\nWhenever you cast a spell from exile, copy it. You may choose new targets for the copy. If it's a permanent spell, "
                  "the copy gains haste and \"At the beginning of the end step, sacrifice this permanent.\" (A copy of a permanent spell "
                  "becomes a token.)", "4", "6", colors=("R",))
STAFF = real("Twinning Staff", "{3}", "Artifact",
             "If you would copy a spell one or more times, instead copy it that many times plus an additional time. You may choose new "
             "targets for the additional copy.\n{7}, {T}: Copy target instant or sorcery spell you control. You may choose new targets "
             "for the copy.")
STORM_STUDY = real("Storm Study", "{1}", "Sorcery", "Storm (When you cast this spell, copy it for each spell cast before it this turn.)\n"
                   "Draw a card.")
SMOG = real("Chain of Smog", "{1}{B}", "Sorcery",
            "Target player discards two cards. That player may copy this spell and may choose a new target for that copy.", colors=("B",))
VAPOR = real("Chain of Vapor", "{U}", "Instant",
             "Return target nonland permanent to its owner's hand. Then that permanent's controller may sacrifice a land of their choice. "
             "If the player does, they may copy this spell and may choose a new target for that copy.", colors=("U",))
CRUCIBLE = real("Wondrous Crucible", "{6}", "Artifact",
                "Permanents you control have ward {2}.\nAt the beginning of your end step, mill two cards, then exile a nonland card at random "
                "from your graveyard. Copy it. You may cast the copy without paying its mana cost. (A copy of a permanent spell becomes a "
                "token.)")
SHOCK = real("Shock", "{R}", "Instant", "Shock deals 2 damage to any target.", colors=("R",))
TRINKET = real("Trinket", "{1}", "Artifact", "")
CROWN = real("Crown of Ages", "{1}", "Legendary Artifact", "")
STUDY = real("Quick Study", "{1}", "Sorcery", "Draw a card.")


def cast(game, seat, card):
    seat.hand.append(card)
    game._perform(seat, f"Cast: {card.name}")
    run_stack(game)


def names(seat):
    return sorted(p.card.name for p in seat.battlefield)


class JinGitaxiasTests(unittest.TestCase):
    def board(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mine.battlefield = [Permanent(JIN, sick=False)] + lands(6)
        mine.library = [BEAR] * 10
        return game, mine, theirs

    def test_an_artifact_spell_is_copied_as_a_token(self):
        game, mine, theirs = self.board()
        cast(game, mine, TRINKET)
        trinkets = [p for p in mine.battlefield if p.card.name == "Trinket"]
        self.assertEqual(len(trinkets), 2)
        self.assertEqual(sum(p.card.type_line.startswith("Token") for p in trinkets), 1)

    def test_only_the_first_spell_each_turn_is_copied(self):
        game, mine, theirs = self.board()
        cast(game, mine, STUDY)
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 3)  # 2 + 1: the first one was copied

    def test_a_creature_spell_is_not_copied(self):
        game, mine, theirs = self.board()
        cast(game, mine, BEAR)
        self.assertEqual(names(mine).count("Bear"), 1)

    def test_an_opponents_first_spell_each_turn_is_countered(self):
        game, mine, theirs = self.board()
        game.active = 1
        theirs.battlefield, theirs.library = lands(2), [BEAR] * 5
        cast(game, theirs, BOLT)
        self.assertEqual(theirs.hand, [])  # countered: no card drawn
        cast(game, theirs, BOLT)
        self.assertEqual(len(theirs.hand), 1)


class KitsaTests(unittest.TestCase):
    def offered(self, power_counters):
        game, _, _ = table(pick("Spell:"))
        mine = game.seats[0]
        kitsa = Permanent(KITSA, sick=False)
        kitsa.counters["+1/+1"] = power_counters
        mine.battlefield, mine.library = [kitsa] + lands(4), [BEAR] * 10
        mine.hand = [STUDY]
        game._perform(mine, "Cast: Quick Study")  # (it stays on the stack: Prowess makes Kitsa 1 bigger)
        game._put_triggers_on_stack()
        while len(game.stack) > 1:
            game._resolve(game.stack.pop())
        return game, mine, [a for a in game.legal_actions(mine) if "Copy target" in a]

    def test_at_power_3_the_spell_can_be_copied(self):
        game, mine, actions = self.offered(1)  # 1 + 1 counter + 1 from Prowess
        self.assertEqual(len(actions), 1)
        game._perform(mine, actions[0])
        run_stack(game)
        self.assertEqual(len(mine.hand), 2)

    def test_below_power_3_it_cannot(self):
        self.assertEqual(self.offered(0)[2], [])


class StormOfSarumanTests(unittest.TestCase):
    def board(self):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.library = [Permanent(SARUMAN)] + lands(4), [BEAR] * 10
        return game, mine

    def test_the_second_spell_is_copied_and_a_legendary_copy_is_not_legendary(self):
        game, mine = self.board()
        cast(game, mine, TRINKET)
        cast(game, mine, CROWN)
        crowns = [p for p in mine.battlefield if p.card.name == "Crown of Ages"]
        self.assertEqual(len(crowns), 2)  # (two legendary permanents of one name would leave one)
        copy = next(p for p in crowns if p.card.type_line.startswith("Token"))
        self.assertNotIn("Legendary", copy.card.type_line)

    def test_the_first_spell_is_not_copied(self):
        game, mine = self.board()
        cast(game, mine, CROWN)
        self.assertEqual(names(mine).count("Crown of Ages"), 1)


class WildRicochetTests(unittest.TestCase):
    def test_the_spell_is_turned_and_copied(self):
        game, _, _ = table(pick("Spell: Shock", "Player: B"), pick("Player: A"))
        mine, theirs = game.seats
        mine.battlefield, mine.hand = lands(4), [RICOCHET]
        theirs.battlefield, theirs.hand = lands(1), [SHOCK]
        game.active = 1
        game._perform(theirs, "Cast: Shock")  # at A
        game._perform(mine, "Cast: Wild Ricochet")
        run_stack(game)
        self.assertEqual((mine.life, theirs.life), (40, 36))  # the Shock and its copy both at B

    def test_with_no_spell_to_target_it_cannot_be_cast(self):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.hand = lands(4), [RICOCHET]
        self.assertNotIn("Cast: Wild Ricochet", game.legal_actions(mine))


class BonusRoundTests(unittest.TestCase):
    def test_each_player_copies_their_own_spells_this_turn(self):
        game, _, _ = table()
        mine, theirs = game.seats
        mine.battlefield, mine.library = lands(5), [BEAR] * 10
        theirs.battlefield, theirs.library = lands(2), [BEAR] * 10
        cast(game, mine, BONUS)
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 2)
        cast(game, theirs, BOLT)  # (an instant, on A's turn)
        self.assertEqual(len(theirs.hand), 2)  # B's copy, for B

    def test_it_ends_with_the_turn(self):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.library = lands(5), [BEAR] * 10
        cast(game, mine, BONUS)
        game.step = "cleanup"
        game._turn_based_actions(mine)
        game.turn += 2
        game.step = "main1"
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 1)


class SwordOfWealthAndPowerTests(unittest.TestCase):
    def hit(self):
        game, _, _ = table()
        mine, theirs = game.seats
        bear, sword = Permanent(BEAR, sick=False), Permanent(SWORD)
        sword.attached_to = bear
        mine.battlefield, mine.library = [bear, sword] + lands(3), [BEAR] * 10
        game.damage(theirs, 4, source=bear, combat=True)
        run_stack(game)
        return game, mine

    def test_a_treasure_and_the_next_instant_or_sorcery_is_copied(self):
        game, mine = self.hit()
        self.assertIn("Treasure", names(mine))
        cast(game, mine, BEAR)  # a creature spell: not the one it waits for
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 2)
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 3)  # only the next one


class KrarkTests(unittest.TestCase):
    def flip(self, won):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.library = [Permanent(KRARK)] + lands(2), [BEAR] * 10
        game.flip_coin = lambda seat: won
        cast(game, mine, STUDY)
        return mine

    def test_a_won_flip_copies_the_spell(self):
        mine = self.flip(True)
        self.assertEqual(len(mine.hand), 2)
        self.assertEqual([c.name for c in mine.graveyard], ["Quick Study"])

    def test_a_lost_flip_returns_it_to_the_hand(self):
        mine = self.flip(False)
        self.assertEqual([c.name for c in mine.hand], ["Quick Study"])
        self.assertEqual(mine.graveyard, [])


class ZadaTests(unittest.TestCase):
    def board(self, target):
        game, _, _ = table(pick(target))
        mine = game.seats[0]
        zada, bear, ogre = Permanent(ZADA, sick=False), Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)
        mine.battlefield = [zada, bear, ogre] + lands(1)
        cast(game, mine, GROWTH)
        return game, zada, bear, ogre

    def test_a_spell_at_zada_is_copied_for_each_other_creature(self):
        game, zada, bear, ogre = self.board("Zada")
        self.assertEqual([game.power(p) for p in (zada, bear, ogre)], [6, 5, 6])

    def test_a_spell_at_another_creature_is_not(self):
        game, zada, bear, ogre = self.board("Bear")
        self.assertEqual([game.power(p) for p in (zada, bear, ogre)], [3, 5, 3])


class ExpansionTests(unittest.TestCase):
    def offered(self, spell):
        game, _, _ = table(pick("Spell:"))
        mine = game.seats[0]
        mine.battlefield, mine.library = lands(8), [BEAR] * 10
        mine.hand = [spell, EXPANSION]
        game._perform(mine, f"Cast: {spell.name}")
        return game, mine, "Cast: Expansion" in game.legal_actions(mine)

    def test_a_spell_of_mana_value_4_or_less_is_copied(self):
        game, mine, castable = self.offered(STUDY)
        self.assertTrue(castable)
        game._perform(mine, "Cast: Expansion")
        run_stack(game)
        self.assertEqual(len(mine.hand), 2)

    def test_a_bigger_spell_is_not_a_target(self):
        self.assertFalse(self.offered(BIG_STUDY)[2])


class PyromancersGogglesTests(unittest.TestCase):
    def cast_with(self, spell, *others, goggles_tapped=False):
        game, _, _ = table()
        mine = game.seats[0]
        goggles = Permanent(GOGGLES)
        goggles.tapped = goggles_tapped
        mine.battlefield, mine.library = [goggles, *others], [BEAR] * 10
        cast(game, mine, spell)
        return mine

    def test_a_red_instant_paid_with_its_mana_is_copied(self):
        self.assertEqual(len(self.cast_with(RED_STUDY).hand), 2)

    def test_a_spell_that_is_not_red_is_not(self):
        self.assertEqual(len(self.cast_with(BLUE_STUDY).hand), 1)

    def test_a_red_instant_paid_with_other_mana_is_not(self):
        mine = self.cast_with(RED_STUDY, Permanent(MOUNTAIN), goggles_tapped=True)
        self.assertEqual(len(mine.hand), 1)


class PrimalAmuletTests(unittest.TestCase):
    def board(self, charge):
        game, _, _ = table()
        mine = game.seats[0]
        amulet = Permanent(AMULET)
        amulet.counters["charge"] = charge
        mine.battlefield, mine.library = [amulet] + lands(3), [BEAR] * 10
        return game, mine, amulet

    def test_the_fourth_counter_turns_it_into_primal_wellspring(self):
        game, mine, amulet = self.board(3)
        cast(game, mine, STUDY)
        self.assertEqual(amulet.card.name, "Primal Wellspring")  # (its back face)
        self.assertEqual(amulet.counters.get("charge", 0), 0)

    def test_with_fewer_counters_it_stays(self):
        game, mine, amulet = self.board(2)
        cast(game, mine, STUDY)
        self.assertEqual((amulet.card.type_line, amulet.counters.get("charge")), ("Artifact", 3))

    def test_a_line_about_the_attacker_and_the_sources_counters_is_not_read(self):  # Grasping Shadows: "it" is two things
        shadows = real("Grasping Shadows", "{2}{B}", "Enchantment",
                       "Whenever a creature you control attacks alone, it gains deathtouch and lifelink until end of turn. Put a dread counter "
                       "on this enchantment. Then if there are three or more dread counters on it, transform it.")
        self.assertTrue(unsupported_lines(shadows))

    def test_primal_wellsprings_mana_copies_an_instant(self):
        game, mine, amulet = self.board(3)
        cast(game, mine, STUDY)  # (it transforms)
        mine.battlefield = [amulet]
        hand = len(mine.hand)
        cast(game, mine, BLUE_STUDY)
        self.assertEqual(len(mine.hand), hand + 2)


class NalfeshneeTests(unittest.TestCase):
    def board(self, card, exiled=True):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.library = [Permanent(NALFESHNEE)] + lands(3), [BEAR] * 10
        if exiled:
            mine.exile, mine.exile_play = [card], [(card, game.turn)]
            game._perform(mine, CAST_EXILE + card.name)
        else:
            mine.hand.append(card)
            game._perform(mine, f"Cast: {card.name}")
        run_stack(game)
        return game, mine

    def test_a_spell_cast_from_exile_is_copied(self):
        game, mine = self.board(STUDY)
        self.assertEqual(len(mine.hand), 2)

    def test_a_spell_cast_from_the_hand_is_not(self):
        game, mine = self.board(STUDY, exiled=False)
        self.assertEqual(len(mine.hand), 1)

    def test_a_permanent_spells_copy_has_haste_and_is_sacrificed_at_the_end_step(self):
        game, mine = self.board(BEAR)
        token = next(p for p in mine.battlefield if p.card.name == "Bear" and p.card.type_line.startswith("Token"))
        self.assertTrue(game.has_keyword(token, "haste"))
        game.step = "end"
        game._turn_based_actions(mine)
        run_stack(game)
        self.assertEqual(names(mine).count("Bear"), 1)  # the card stays, the token is gone


class TwinningStaffTests(unittest.TestCase):
    def board(self, *others):
        game, _, _ = table()
        mine = game.seats[0]
        mine.battlefield, mine.library = [Permanent(STAFF), *others] + lands(3), [BEAR] * 10
        return game, mine

    def test_a_copy_becomes_two(self):
        game, mine = self.board(Permanent(JIN))
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 3)

    def test_several_copies_at_once_get_one_more_not_one_each(self):
        game, mine = self.board()
        cast(game, mine, STUDY)
        cast(game, mine, STUDY)
        cast(game, mine, STORM_STUDY)  # storm 2, plus one
        self.assertEqual(len(mine.hand), 2 + 4)

    def test_without_a_copy_nothing_is_added(self):
        game, mine = self.board()
        cast(game, mine, STUDY)
        self.assertEqual(len(mine.hand), 1)


class ChainTests(unittest.TestCase):
    def test_the_player_hit_may_copy_chain_of_smog_back(self):
        game, _, _ = table(pick("Player: B", "No"), pick("Yes", "Player: A"))
        mine, theirs = game.seats
        mine.battlefield, mine.hand = lands(2), [SMOG, BEAR, BEAR, BEAR]
        theirs.hand = [OGRE, OGRE, OGRE]
        game._perform(mine, "Cast: Chain of Smog")
        run_stack(game)
        self.assertEqual((len(mine.hand), len(theirs.hand)), (1, 1))  # B discarded two, copied it at A, and A stopped

    def test_declining_ends_the_chain(self):
        game, _, _ = table(pick("Player: B"), pick("No"))
        mine, theirs = game.seats
        mine.battlefield, mine.hand = lands(2), [SMOG, BEAR, BEAR]
        theirs.hand = [OGRE, OGRE, OGRE]
        game._perform(mine, "Cast: Chain of Smog")
        run_stack(game)
        self.assertEqual((len(mine.hand), len(theirs.hand)), (2, 1))

    def test_chain_of_vapor_costs_a_land_to_copy(self):
        game, _, _ = table(pick("Ogre", "No"), pick("Yes", "Forest", "Bear"))
        mine, theirs = game.seats
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        mine.battlefield, mine.hand = [bear] + lands(1), [VAPOR]
        theirs.battlefield = [ogre, Permanent(FOREST)]
        game._perform(mine, "Cast: Chain of Vapor")
        run_stack(game)
        self.assertEqual(([c.name for c in theirs.hand], [c.name for c in mine.hand]), (["Ogre"], ["Bear"]))
        self.assertEqual([p.card.name for p in theirs.battlefield], [])  # the Forest paid for the copy

    def test_the_bot_never_copies_back(self):
        bot = BotPlayer("A", Deck([FOREST], [], []))
        self.assertEqual(CHAIN_COPY_OPTIONS[bot.choose(CHAIN_COPY_PROMPT("Chain of Smog"), CHAIN_COPY_OPTIONS)], "No")

    def test_a_player_who_takes_the_first_option_ends_the_chain(self):  # (the smoke tests' player: it must not copy forever)
        game, _, _ = table(lambda prompt, options: next((i for i, o in enumerate(options) if o.startswith("Player: B")), 0),
                           lambda prompt, options: 0)
        mine, theirs = game.seats
        mine.battlefield, mine.hand = lands(2), [SMOG]
        theirs.hand = [OGRE, OGRE, OGRE]
        game._perform(mine, "Cast: Chain of Smog")
        run_stack(game)
        self.assertEqual(len(theirs.hand), 1)


class WondrousCrucibleTests(unittest.TestCase):
    def test_a_nonland_card_from_the_graveyard_is_cast_as_a_copy(self):
        game, _, _ = table(pick("Quick Study"))
        mine = game.seats[0]
        mine.battlefield, mine.library, mine.graveyard = [Permanent(CRUCIBLE)], [FOREST, FOREST, BEAR, BEAR], [STUDY]
        game.step = "end"
        game._turn_based_actions(mine)
        run_stack(game)
        self.assertEqual([c.name for c in mine.exile], ["Quick Study"])
        self.assertEqual(len(mine.hand), 1)  # the copy drew a card
        self.assertEqual(sorted(c.name for c in mine.graveyard), ["Forest", "Forest"])  # the two milled lands stay

    def test_with_only_lands_in_the_graveyard_nothing_is_exiled(self):
        game, _, _ = table(pick("Forest"))
        mine = game.seats[0]
        mine.battlefield, mine.library = [Permanent(CRUCIBLE)], [FOREST, FOREST, BEAR]
        game.step = "end"
        game._turn_based_actions(mine)
        run_stack(game)
        self.assertEqual((mine.exile, len(mine.graveyard)), ([], 2))


if __name__ == "__main__":
    unittest.main()
