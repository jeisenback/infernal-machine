"""The lines of issue #81 (rules text: sweepers, bounce, draw, damage, X spells and the like), each played from the card's own
Oracle text from Scryfall, with cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card, _mana_value
from infernal_machine.game import CAST, CAST_GRAVEYARD, DECLINE, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands, pick
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_triggers_80 import BIG, FOREST, PLAINS, RELIC, SHRINE
from tests.test_x_targets import script


def real(name, cost, type_line, text, power=None, toughness=None, colors=()):
    return Card(name=name, mana_cost=cost, cmc=_mana_value(cost), type_line=type_line, oracle_text=text, power=power,
                toughness=toughness, colors=colors)


class Table:
    """Seat 0 casts `card` with `n` lands against two opponents; `answers` are the replies to what the game asks."""

    def __init__(self, card, *answers, n=6, mine=(), theirs=(), graveyard=(), library=None, policy=None):
        self.game, _ = table3(policy or script(*answers))
        self.a, self.b, self.c = self.game.seats
        self.a.battlefield = list(mine) + lands(n)
        self.b.battlefield = list(theirs)
        self.a.hand = [card]
        self.a.graveyard = list(graveyard)
        self.a.library = list(library if library is not None else [FOREST] * 10)
        self.card = card

    def cast(self):
        self.game._perform(self.a, CAST + self.card.name)
        run_stack(self.game)
        self.game._check_state()
        return self


def battlefield_names(seat):
    return sorted(p.card.name for p in seat.battlefield if p.card.name != "City of Brass")


GALE = real("Aether Gale", "{3}{U}{U}", "Sorcery", "Return six target nonland permanents to their owners' hands.")


class AetherGaleTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(GALE), [])

    def test_six_nonland_permanents_go_back_to_their_owners(self):
        mine = [Permanent(RELIC), Permanent(SHRINE), Permanent(BEAR)]
        theirs = [Permanent(OGRE), Permanent(BIG), Permanent(real("Idol", "{3}", "Artifact", ""))]
        t = Table(GALE, mine=mine, theirs=theirs, policy=pick("Relic", "Shrine", "Bear", "Ogre", "Big", "Idol")).cast()
        self.assertEqual(battlefield_names(t.a), [])
        self.assertEqual(battlefield_names(t.b), [])
        self.assertEqual(sorted(c.name for c in t.a.hand), ["Bear", "Relic", "Shrine"])
        self.assertEqual(sorted(c.name for c in t.b.hand), ["Big", "Idol", "Ogre"])

    def test_lands_are_not_targets(self):
        t = Table(GALE, mine=[Permanent(RELIC)], theirs=[Permanent(FOREST)], policy=pick("Forest", "Relic")).cast()
        self.assertEqual(battlefield_names(t.b), ["Forest"])


EUREKA = real("Eureka Moment", "{2}{G}{U}", "Instant", "Draw two cards. You may put a land card from your hand onto the battlefield.")


class EurekaMomentTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(EUREKA), [])

    def test_it_draws_two_and_may_put_a_land_onto_the_battlefield(self):
        t = Table(EUREKA, library=[FOREST, PLAINS, RELIC], policy=pick("Forest", "Plains")).cast()
        lands_in_play = [p for p in t.a.battlefield if p.card.name in ("Forest", "Plains")]
        self.assertEqual([p.card.name for p in lands_in_play], ["Forest"])
        self.assertEqual(sorted(c.name for c in t.a.hand), ["Plains"])

    def test_it_may_keep_the_land_in_hand(self):
        t = Table(EUREKA, library=[FOREST, PLAINS, RELIC], policy=pick(DECLINE)).cast()
        self.assertEqual(sorted(c.name for c in t.a.hand), ["Forest", "Plains"])


HARVEST = real("Ominous Harvest", "{2}{B}", "Sorcery", "Gravestorm (When you cast this spell, copy it for each permanent put into a "
                                                    "graveyard from the battlefield this turn.)\nTarget player draws a card and loses 1 life.")


class OminousHarvestTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(HARVEST), [])

    def test_it_is_copied_for_each_permanent_that_went_to_a_graveyard_this_turn(self):
        t = Table(HARVEST, policy=pick("Bear", "Ogre", "Player A", "Player"), mine=[Permanent(BEAR), Permanent(OGRE)])
        t.game.sacrifice(t.a, "creature", 2)
        t.cast()
        self.assertEqual((len(t.a.hand), t.a.life), (3, 37))

    def test_one_draw_when_nothing_died(self):
        t = Table(HARVEST, policy=pick("Player A", "Player")).cast()
        self.assertEqual((len(t.a.hand), t.a.life), (1, 39))


DEEP = real("Deep Analysis", "{3}{U}", "Sorcery", "Target player draws two cards.\nFlashback—{1}{U}, Pay 3 life. (You may cast this card from "
                                                  "your graveyard for its flashback cost. Then exile it.)")


class DeepAnalysisTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(DEEP), [])

    def flashback(self, life=40, n=2):
        t = Table(DEEP, n=n, graveyard=[DEEP], policy=pick("Player A", "Player"))
        t.a.hand = []
        t.a.life = life
        return t

    def test_flashback_costs_two_mana_and_three_life_then_exiles_it(self):
        t = self.flashback()
        t.game._perform(t.a, CAST_GRAVEYARD + "Deep Analysis")
        run_stack(t.game)
        self.assertEqual((t.a.life, len(t.a.hand), t.a.graveyard, [c.name for c in t.a.exile]), (37, 2, [], ["Deep Analysis"]))

    def test_it_is_not_offered_without_the_mana_or_the_life(self):
        self.assertNotIn(CAST_GRAVEYARD + "Deep Analysis", (t := self.flashback(n=1)).game.legal_actions(t.a))
        self.assertNotIn(CAST_GRAVEYARD + "Deep Analysis", (t := self.flashback(life=2)).game.legal_actions(t.a))
        self.assertIn(CAST_GRAVEYARD + "Deep Analysis", (t := self.flashback(life=3)).game.legal_actions(t.a))


DIG = real("Dig Through Time", "{6}{U}{U}", "Instant", "Delve (Each card you exile from your graveyard while casting this spell pays for "
                                                     "{1}.)\nLook at the top seven cards of your library. Put two of them into your hand and "
                                                     "the rest on the bottom of your library in any order.")


class DigThroughTimeTests(unittest.TestCase):
    def library(self):
        return [real(f"Card {i}", "{1}", "Sorcery", "") for i in range(9)]

    def test_parse(self):
        self.assertEqual(unsupported_lines(DIG), [])

    def test_two_of_the_top_seven_go_to_hand_and_the_rest_to_the_bottom(self):
        t = Table(DIG, n=2, graveyard=[real(f"Gy {i}", "{1}", "Sorcery", "") for i in range(6)], library=self.library(),
                  policy=pick("Card 5", "Card 2")).cast()
        self.assertEqual(sorted(c.name for c in t.a.hand), ["Card 2", "Card 5"])
        self.assertEqual(len(t.a.library), 7)
        self.assertEqual({c.name for c in t.a.library[:2]}, {"Card 7", "Card 8"})  # the two below the seven looked at are now on top
        self.assertEqual(len(t.a.exile), 6)  # delve paid for six of the eight

    def test_cards_below_the_seventh_are_not_offered(self):
        t = Table(DIG, n=8, library=self.library(), policy=pick("Card 8", "Card 7")).cast()
        self.assertNotIn("Card 8", [c.name for c in t.a.hand])
        self.assertNotIn("Card 7", [c.name for c in t.a.hand])




AUGMENTER = real("Guardian Augmenter", "{2}{G}", "Creature — Troll Wizard",
                 "Flash\nCommander creatures you control get +2/+2.\nCommanders you control have hexproof.", "2", "2")


class GuardianAugmenterTests(unittest.TestCase):
    def table(self, commander_of=0):
        game, _ = table3(pick())
        a, b, _ = game.seats
        self.commander, self.other = Permanent(BEAR), Permanent(OGRE)
        a.battlefield = [self.commander, self.other, Permanent(AUGMENTER)]
        game.seats[commander_of].commander_names = {"Bear"}
        return game

    def test_parse(self):
        self.assertEqual(unsupported_lines(AUGMENTER), [])

    def test_your_commander_gets_plus_two_and_hexproof(self):
        game = self.table()
        self.assertEqual((game.power(self.commander), game.toughness(self.commander)), (4, 4))
        self.assertTrue(game.has_keyword(self.commander, "hexproof"))

    def test_other_creatures_are_unchanged(self):
        game = self.table()
        self.assertEqual(game.power(self.other), 3)
        self.assertFalse(game.has_keyword(self.other, "hexproof"))

    def test_the_augmenter_is_not_a_commander_itself(self):
        game = self.table()
        self.assertEqual(game.power(next(p for p in game.seats[0].battlefield if p.card.name == "Guardian Augmenter")), 2)

    def test_nothing_happens_without_a_commander_on_the_battlefield(self):
        game = self.table(commander_of=1)  # the Bear is an opponent's commander but is on my side of the table, still a commander
        self.assertEqual(game.power(self.commander), 4)
        game.seats[1].commander_names = set()
        self.assertEqual(game.power(self.commander), 2)

    def test_a_token_copy_of_the_commander_is_not_the_commander(self):
        game = self.table()
        copy = Permanent(Card(name="Bear", type_line="Token Creature — Bear", power="2", toughness="2"))
        game.seats[0].battlefield.append(copy)
        self.assertEqual(game.power(copy), 2)

    def test_an_opponents_commander_is_not_affected(self):
        game = self.table()
        theirs = Permanent(OGRE)
        game.seats[1].battlefield = [theirs]
        game.seats[1].commander_names = {"Ogre"}
        self.assertEqual(game.power(theirs), 3)


PRISMARI_CHARM = real("Prismari Charm", "{U}{R}", "Instant", "Choose one —\n• Surveil 2, then draw a card.\n• Prismari Charm deals 1 damage to each of "
                                                          "one or two targets.\n• Return target nonland permanent to its owner's hand.")


class PrismariCharmTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(PRISMARI_CHARM), [])

    def test_surveil_two_then_draw(self):
        top = [real("Keep", "{1}", "Sorcery", ""), real("Bin", "{1}", "Sorcery", ""), real("Next", "{1}", "Sorcery", ""), real("Last", "{1}", "Sorcery", "")]
        def policy(prompt, options):
            return pick("Put into")(prompt, options) if prompt == "Surveil: Bin" else pick("Surveil", "Keep on top")(prompt, options)
        t = Table(PRISMARI_CHARM, library=top, policy=policy).cast()
        self.assertEqual(sorted(c.name for c in t.a.graveyard), ["Bin", "Prismari Charm"])
        self.assertEqual([c.name for c in t.a.hand], ["Keep"])

    def test_return_a_nonland_permanent(self):
        t = Table(PRISMARI_CHARM, theirs=[Permanent(FOREST), Permanent(OGRE)], policy=pick("Return", "Ogre")).cast()
        self.assertEqual((battlefield_names(t.b), [c.name for c in t.b.hand]), (["Forest"], ["Ogre"]))


QUANDRIX_CHARM = real("Quandrix Charm", "{G}{U}", "Instant", "Choose one —\n• Counter target spell unless its controller pays {2}.\n• Destroy "
                                                         "target enchantment.\n• Target creature has base power and toughness 5/5 until end of turn.")


class QuandrixCharmTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(QUANDRIX_CHARM), [])

    def test_base_power_and_toughness_become_five_until_end_of_turn(self):
        bear = Permanent(BEAR, counters={"+1/+1": 1})
        t = Table(QUANDRIX_CHARM, mine=[bear], policy=pick("Target creature has", "Bear")).cast()
        self.assertEqual((t.game.power(bear), t.game.toughness(bear)), (6, 6))  # counters stay on top of the base 5/5

    def test_destroy_target_enchantment(self):
        t = Table(QUANDRIX_CHARM, theirs=[Permanent(SHRINE), Permanent(RELIC)], policy=pick("Destroy", "Shrine")).cast()
        self.assertEqual(battlefield_names(t.b), ["Relic"])


LOREHOLD_CHARM = real("Lorehold Charm", "{R}{W}", "Instant", "Choose one —\n• Each opponent sacrifices a nontoken artifact of their choice.\n• Return "
                                                        "target artifact or creature card with mana value 2 or less from your graveyard to the "
                                                        "battlefield.\n• Creatures you control get +1/+1 and gain trample until end of turn.")


class LoreholdCharmTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(LOREHOLD_CHARM), [])

    def test_it_returns_an_artifact_or_creature_with_mana_value_two_or_less(self):
        two = real("Cheap", "{1}{R}", "Creature — Test", "", "2", "2")
        t = Table(LOREHOLD_CHARM, graveyard=[BIG, two, SHRINE], policy=pick("Return", "Cheap")).cast()
        self.assertEqual(battlefield_names(t.a), ["Cheap"])

    def test_nothing_with_a_greater_mana_value_is_offered(self):
        t = Table(LOREHOLD_CHARM, graveyard=[BIG], policy=pick("Return", "Big")).cast()
        self.assertEqual(battlefield_names(t.a), [])

    def test_creatures_get_plus_one_and_trample(self):
        bear = Permanent(BEAR)
        t = Table(LOREHOLD_CHARM, mine=[bear], theirs=[Permanent(OGRE)], policy=pick("Creatures you control")).cast()
        self.assertEqual((t.game.power(bear), t.game.has_keyword(bear, "trample")), (3, True))
        self.assertEqual(t.game.power(t.b.battlefield[0]), 3)


WITHERBLOOM_CHARM = real("Witherbloom Charm", "{B}{G}", "Instant", "Choose one —\n• You may sacrifice a permanent. If you do, draw two cards.\n• You "
                                                                "gain 5 life.\n• Destroy target nonland permanent with mana value 2 or less.")


class WitherbloomCharmTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(WITHERBLOOM_CHARM), [])

    def test_destroy_a_nonland_permanent_with_mana_value_two_or_less(self):
        t = Table(WITHERBLOOM_CHARM, theirs=[Permanent(BIG), Permanent(SHRINE)], policy=pick("Destroy", "Shrine", "Big")).cast()
        self.assertEqual(battlefield_names(t.b), ["Big"])

    def test_a_permanent_with_a_greater_mana_value_is_not_a_target(self):
        t = Table(WITHERBLOOM_CHARM, theirs=[Permanent(BIG)], policy=pick("Destroy", "Big", "You gain")).cast()
        self.assertEqual(battlefield_names(t.b), ["Big"])

    def test_gain_five_life(self):
        t = Table(WITHERBLOOM_CHARM, policy=pick("You gain")).cast()
        self.assertEqual(t.a.life, 45)


WITHERBLOOM_COMMAND = real("Witherbloom Command", "{B}{G}", "Sorcery", "Choose two —\n• Target player mills three cards, then you return a land "
                                                                    "card from your graveyard to your hand.\n• Destroy target noncreature, "
                                                                    "nonland permanent with mana value 2 or less.\n• Target creature gets -3/-1 "
                                                                    "until end of turn.\n• Target opponent loses 2 life and you gain 2 life.")


class WitherbloomCommandTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(WITHERBLOOM_COMMAND), [])

    def test_destroy_only_a_cheap_noncreature_nonland_permanent(self):
        cheap_creature = real("Cheap", "{1}", "Creature — Test", "", "1", "1")
        t = Table(WITHERBLOOM_COMMAND, theirs=[Permanent(cheap_creature), Permanent(SHRINE), Permanent(BIG)],
                  policy=pick("Destroy", "Target opponent", "Shrine", "Cheap", "Big")).cast()
        self.assertEqual(battlefield_names(t.b), ["Big", "Cheap"])

    def test_minus_three_minus_one_and_the_drain(self):
        t = Table(WITHERBLOOM_COMMAND, theirs=[Permanent(OGRE)], policy=pick("Target creature gets", "Target opponent", "Ogre", "Player: B")).cast()
        self.assertEqual((t.a.life, t.b.life), (42, 38))
        self.assertEqual([battlefield_names(t.b)], [["Ogre"]])  # a 3/3 with -3/-1 is a 0/2 and survives
        self.assertEqual(t.game.power(t.b.battlefield[0]), 0)


PRISMARI_COMMAND = real("Prismari Command", "{1}{U}{R}", "Instant", "Choose two —\n• Prismari Command deals 2 damage to any target.\n• Target player "
                                                                  "draws two cards, then discards two cards.\n• Target player creates a "
                                                                  "Treasure token.\n• Destroy target artifact.")


class PrismariCommandTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(PRISMARI_COMMAND), [])

    def test_two_damage_and_a_treasure(self):
        t = Table(PRISMARI_COMMAND, "Prismari Command deals", "Target player creates", "Player: B", "Player: A").cast()
        self.assertEqual(t.b.life, 38)
        self.assertEqual([p.card.name for p in t.a.battlefield if p.card.name == "Treasure"], ["Treasure"])

    def test_destroy_target_artifact(self):
        t = Table(PRISMARI_COMMAND, theirs=[Permanent(RELIC), Permanent(SHRINE)],
                  policy=pick("Destroy target artifact", "Target player creates", "Relic", "Player: A")).cast()
        self.assertEqual(battlefield_names(t.b), ["Shrine"])


DECISIVE = real("Decisive Denial", "{G}{U}", "Instant", "Choose one —\n• Target creature you control fights target creature you don't control. (Each "
                                                         "deals damage equal to its power to the other.)\n• Counter target noncreature spell "
                                                         "unless its controller pays {3}.")


class DecisiveDenialTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(DECISIVE), [])

    def test_the_fight_mode_deals_damage_both_ways(self):
        ogre = Permanent(OGRE)
        t = Table(DECISIVE, mine=[ogre], theirs=[Permanent(BEAR)], policy=pick("Target creature you control", "Ogre", "Bear")).cast()
        self.assertEqual((battlefield_names(t.b), ogre.damage), ([], 2))


BLOODGHAST = real("Bloodghast", "{B}{B}", "Creature — Vampire Spirit",
                  "This creature can't block.\nThis creature has haste as long as an opponent has 10 or less life.\nLandfall — Whenever a land "
                  "you control enters, you may return this card from your graveyard to the battlefield.", "2", "1")


class BloodghastTests(unittest.TestCase):
    def play_land(self, *choices, in_graveyard=True, land_of=0):
        game, _ = table3(pick(*choices))
        a = game.seats[0]
        self.ghast = Permanent(BLOODGHAST)
        a.graveyard = [BLOODGHAST] if in_graveyard else []
        game._enter(game.seats[land_of], Permanent(FOREST))
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(BLOODGHAST), [])

    def test_a_land_entering_brings_it_back_from_the_graveyard(self):
        game, a = self.play_land("Yes")
        self.assertEqual((battlefield_names(a), a.graveyard), (["Bloodghast", "Forest"], []))

    def test_you_may_leave_it_there(self):
        game, a = self.play_land("No")
        self.assertEqual((battlefield_names(a), [c.name for c in a.graveyard]), (["Forest"], ["Bloodghast"]))

    def test_an_opponents_land_does_not_bring_it_back(self):
        game, a = self.play_land("Yes", land_of=1)
        self.assertEqual((battlefield_names(a), [c.name for c in a.graveyard]), ([], ["Bloodghast"]))

    def test_each_land_returns_it_only_once_from_the_graveyard(self):
        game, a = self.play_land("Yes")
        game._enter(a, Permanent(FOREST))
        run_stack(game)
        self.assertEqual(battlefield_names(a), ["Bloodghast", "Forest", "Forest"])


FINAL_ACT = real("Final Act", "{4}{B}{B}", "Sorcery", "Choose one or more —\n• Destroy all creatures.\n• Destroy all planeswalkers.\n• Destroy all "
                                                     "battles.\n• Exile all graveyards.\n• Each opponent loses all counters.")


class FinalActTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(FINAL_ACT), [])

    def test_destroy_all_creatures_and_exile_all_graveyards(self):
        t = Table(FINAL_ACT, mine=[Permanent(BEAR)], theirs=[Permanent(OGRE), Permanent(RELIC)], graveyard=[SHRINE],
                  policy=pick("Destroy all creatures", "Exile all graveyards", "Done")).cast()
        self.assertEqual((battlefield_names(t.a), battlefield_names(t.b)), ([], ["Relic"]))
        self.assertEqual(([c.name for c in t.a.graveyard], [c.name for c in t.a.exile if c.name == "Shrine"]), (["Final Act"], ["Shrine"]))

    def test_destroying_planeswalkers_leaves_creatures_alone(self):
        t = Table(FINAL_ACT, theirs=[Permanent(OGRE), Permanent(real("Walker", "{3}", "Legendary Planeswalker — Test", ""))],
                  policy=pick("Destroy all planeswalkers", "Done")).cast()
        self.assertEqual(battlefield_names(t.b), ["Ogre"])

    def test_each_opponent_loses_all_counters_on_them_and_you_keep_yours(self):
        t = Table(FINAL_ACT, policy=pick("Each opponent loses all counters", "Done"))
        t.a.player_counters, t.b.player_counters, t.c.player_counters = {"poison": 2}, {"poison": 4, "energy": 3}, {"experience": 1}
        t.cast()
        self.assertEqual((t.a.player_counters, t.b.player_counters, t.c.player_counters), ({"poison": 2}, {}, {}))


APPRENTICE = real("Quandrix Apprentice", "{G}{U}", "Creature — Human Wizard",
                  "Magecraft — Whenever you cast or copy an instant or sorcery spell, look at the top three cards of your library. You may reveal "
                  "a land card from among them and put that card into your hand. Put the rest on the bottom of your library in any order.",
                  "2", "2")
CANTRIP = real("Cantrip", "{U}", "Instant", "You gain 1 life.")


class QuandrixApprenticeTests(unittest.TestCase):
    def cast(self, library, *choices):
        t = Table(CANTRIP, mine=[Permanent(APPRENTICE)], library=library, policy=pick(*choices))
        return t.cast()

    def test_parse(self):
        self.assertEqual(unsupported_lines(APPRENTICE), [])

    def test_a_land_among_the_top_three_goes_to_hand_and_the_rest_to_the_bottom(self):
        spell = [real(f"Spell {i}", "{1}", "Sorcery", "") for i in range(5)]
        t = self.cast([spell[0], FOREST, spell[1], spell[2], spell[3]], "Forest")
        self.assertEqual([c.name for c in t.a.hand], ["Forest"])
        self.assertEqual({c.name for c in t.a.library[-2:]}, {"Spell 0", "Spell 1"})
        self.assertEqual(t.a.library[0].name, "Spell 2")

    def test_it_may_take_no_land(self):
        t = self.cast([FOREST, RELIC, SHRINE, PLAINS], "Take none")
        self.assertEqual(t.a.hand, [])
        self.assertEqual(len(t.a.library), 4)

    def test_without_a_land_in_the_top_three_nothing_goes_to_hand(self):
        t = self.cast([RELIC, SHRINE, BIG, FOREST])
        self.assertEqual(t.a.hand, [])

    def test_a_creature_spell_does_not_trigger_it(self):
        t = Table(real("Brute", "{1}", "Creature — Test", "", "1", "1"), mine=[Permanent(APPRENTICE)], library=[FOREST] * 5).cast()
        self.assertEqual(t.a.hand, [])


NEXUS = real("Nexus Mentality", "{3}{U}", "Instant", "Choose one. If you control a commander as you cast this spell, you may choose both "
                                                     "instead.\n• Move all counters from target nonland permanent you control onto another target "
                                                     "nonland permanent you control.\n• Remove all counters from target nonland permanent you "
                                                     "control. Draw a card for each counter removed this way.")


class NexusMentalityTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(NEXUS), [])

    def test_moving_all_counters_onto_another_permanent(self):
        src, dst = Permanent(BEAR, counters={"+1/+1": 3}), Permanent(OGRE)
        Table(NEXUS, mine=[src, dst], policy=pick("Move all counters", "Bear", "Ogre")).cast()
        self.assertEqual((src.counters, dst.counters), ({}, {"+1/+1": 3}))

    def test_removing_counters_draws_a_card_for_each(self):
        src = Permanent(BEAR, counters={"+1/+1": 3})
        t = Table(NEXUS, mine=[src], policy=pick("Remove all counters", "Bear")).cast()
        self.assertEqual((src.counters, len(t.a.hand)), ({}, 3))

    def mode_prompts(self, with_commander):
        t = Table(NEXUS, mine=[Permanent(BEAR, counters={"+1/+1": 3}), Permanent(OGRE)], policy=pick("Move all counters", "Bear", "Ogre", "Done"))
        if with_commander:
            t.a.commander_names = {"Ogre"}
        t.cast()
        return [options for prompt, options in t.a.player.prompts if prompt.startswith("Choose a mode")]

    def test_only_one_mode_without_a_commander(self):
        self.assertEqual(len(self.mode_prompts(False)), 1)

    def test_a_second_mode_is_offered_with_a_commander(self):
        self.assertEqual(len(self.mode_prompts(True)), 2)

    def test_both_modes_in_order_move_the_counters_and_then_draw_for_them(self):
        src, dst = Permanent(BEAR, counters={"+1/+1": 3}), Permanent(OGRE)
        t = Table(NEXUS, "Move all counters", "Remove all", "Bear", "Ogre", "Ogre", mine=[src, dst])
        t.a.commander_names = {"Ogre"}
        t.cast()
        self.assertEqual((src.counters, dst.counters, len(t.a.hand)), ({}, {}, 3))  # moved onto the Ogre, then removed from it
