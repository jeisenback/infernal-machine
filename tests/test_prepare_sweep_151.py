"""The nine prepare creatures of the precon decks that no test named (issue #151), each played from its real Oracle text and
its real spell half. Triggers run through the real turn (upkeep, combat, end step) where they can; each has cases where the
creature must stay unprepared."""

import unittest

from infernal_machine.cards import Card, _mana_value
from infernal_machine.game import CAST, CAST_PREPARED, GraveyardTarget, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import (
    attack_all,
    BEAR,
    BIG,
    FOREST,
    lands,
    OGRE,
    pick,
    RELIC,
    run_stack,
    script,
    SHRINE,
    SPIRIT,
    table,
    table3,
    take_turn_attacking,
)


def prep(name, cost, type_line, power, toughness, text, half_name, half_cost, half_type, half_text):
    spell = Card(name=half_name, mana_cost=half_cost, cmc=_mana_value(half_cost), type_line=half_type, oracle_text=half_text)
    return Card(name=f"{name} // {half_name}", mana_cost=cost, cmc=_mana_value(cost), type_line=type_line, power=power,
                toughness=toughness, oracle_text=text, prepare=spell)


def cast_prepared(game, seat, spell_name):
    game._perform(seat, CAST_PREPARED + spell_name)
    run_stack(game)


def fight(game, seat):
    """One combat for `seat`: its creatures that are not summoning sick attack the first opponent; the defender's policy blocks."""
    game.active = seat.index
    game.combat.declare_attackers(seat)
    run_stack(game)
    game.combat.declare_blockers()
    run_stack(game)
    game.combat.deal_damage(first_strike_step=False)
    run_stack(game)


def two_player(policy=attack_all):
    game, _, _ = table(policy)
    a, b = game.seats
    for seat in (a, b):
        seat.library = [FOREST] * 20
    return game, a, b


PREP_REMINDER = " (While it's prepared, you may cast a copy of its spell. Doing so unprepares it.)"

ARCHIVIST = prep("Lorehold Archivist", "{1}{R}{W}", "Creature — Dwarf Artificer", "3", "2",
                 "First strike\nAt the beginning of your upkeep, if there are three or more artifact and/or creature cards in your "
                 "graveyard, this creature becomes prepared." + PREP_REMINDER,
                 "Restore Relic", "{2}{R}{W}", "Sorcery", "Exile target artifact or creature card from your graveyard. Create a token "
                                                          "that's a copy of it.")


class LoreholdArchivistTests(unittest.TestCase):
    def upkeep(self, graveyard):
        game, a, b = two_player()
        self.archivist = Permanent(ARCHIVIST)
        a.battlefield = [self.archivist]
        a.graveyard = list(graveyard)
        take_turn_attacking(game, a)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(ARCHIVIST), [])

    def test_prepared_with_three_artifact_and_or_creature_cards(self):
        self.upkeep([RELIC, BEAR, OGRE])
        self.assertTrue(self.archivist.prepared)

    def test_not_prepared_with_two(self):
        self.upkeep([RELIC, BEAR])
        self.assertFalse(self.archivist.prepared)

    def test_other_cards_in_the_graveyard_do_not_count(self):
        self.upkeep([RELIC, BEAR, SHRINE, FOREST])
        self.assertFalse(self.archivist.prepared)

    def test_it_only_looks_at_your_upkeep(self):
        game, a, b = two_player()
        self.archivist = Permanent(ARCHIVIST)
        a.battlefield = [self.archivist]
        a.graveyard = [RELIC, BEAR, OGRE]
        take_turn_attacking(game, b)
        self.assertFalse(self.archivist.prepared)

    def test_restore_relic_exiles_a_card_and_makes_a_token_copy(self):
        game, a, b = two_player(pick("Ogre"))
        a.battlefield = [Permanent(ARCHIVIST, prepared=True), *lands(4)]
        a.graveyard = [BEAR, OGRE]
        cast_prepared(game, a, "Restore Relic")
        ogres = [p for p in a.battlefield if p.card.name == "Ogre"]
        self.assertEqual(len(ogres), 1)
        self.assertTrue(ogres[0].card.type_line.startswith("Token"))
        self.assertEqual([c.name for c in a.graveyard], ["Bear"])
        self.assertFalse(next(p for p in a.battlefield if p.card.name.startswith("Lorehold Archivist")).prepared)


LORESPINNER = prep("Naktamun Lorespinner", "{2}{R}", "Creature — Jackal Wizard", "3", "3",
                   "At the beginning of your upkeep, if a player has one or fewer cards in hand, this creature becomes prepared."
                   + PREP_REMINDER, "Wheel of Fortune", "{2}{R}", "Sorcery", "Each player discards their hand, then draws seven cards.")


class NaktamunLorespinnerTests(unittest.TestCase):
    def upkeep(self, mine, theirs):
        game, a, b = two_player()
        self.spinner = Permanent(LORESPINNER)
        a.battlefield = [self.spinner]
        a.hand, b.hand = [FOREST] * mine, [FOREST] * theirs
        take_turn_attacking(game, a)
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(LORESPINNER), [])

    def test_prepared_when_an_opponent_has_one_card_or_none(self):
        self.upkeep(mine=4, theirs=1)
        self.assertTrue(self.spinner.prepared)
        self.upkeep(mine=4, theirs=0)
        self.assertTrue(self.spinner.prepared)

    def test_prepared_when_you_have_one_card_or_none_too(self):
        self.upkeep(mine=1, theirs=5)
        self.assertTrue(self.spinner.prepared)

    def test_not_prepared_when_everyone_has_two_or_more(self):
        self.upkeep(mine=2, theirs=2)
        self.assertFalse(self.spinner.prepared)

    def test_wheel_of_fortune_discards_each_hand_and_draws_seven(self):
        game, a, b = two_player()
        a.battlefield = [Permanent(LORESPINNER, prepared=True), *lands(3)]
        a.hand, b.hand = [BEAR, OGRE], [RELIC]
        cast_prepared(game, a, "Wheel of Fortune")
        self.assertEqual((len(a.hand), len(b.hand)), (7, 7))
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Ogre"])
        self.assertEqual([c.name for c in b.graveyard], ["Relic"])


KIROL = prep("Kirol, History Buff", "{R}{W}", "Legendary Creature — Vampire Cleric", "2", "3",
             "Whenever one or more cards leave your graveyard, Kirol becomes prepared." + PREP_REMINDER,
             "Pack a Punch", "{1}{R}{W}", "Sorcery", "Mill a card. Put two +1/+1 counters on target creature. It gains trample until "
                                                      "end of turn.")


class KirolTests(unittest.TestCase):
    def table(self, *choices):
        game, _ = table3(pick(*choices))
        a, b, _ = game.seats
        self.kirol = Permanent(KIROL)
        a.battlefield = [self.kirol]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(KIROL), [])

    def test_prepared_when_a_card_leaves_your_graveyard(self):
        game, a, b = self.table()
        a.graveyard = [BEAR]
        game.exile_from_graveyard(GraveyardTarget(BEAR, a))
        run_stack(game)
        self.assertTrue(self.kirol.prepared)

    def test_not_prepared_when_a_card_leaves_an_opponents_graveyard(self):
        game, a, b = self.table()
        b.graveyard = [BEAR]
        game.exile_from_graveyard(GraveyardTarget(BEAR, b))
        run_stack(game)
        self.assertFalse(self.kirol.prepared)

    def test_not_prepared_when_a_card_enters_your_graveyard(self):
        game, a, b = self.table()
        game._move_card(a, BEAR, "graveyard")
        run_stack(game)
        self.assertFalse(self.kirol.prepared)

    def test_pack_a_punch_mills_a_card_and_pumps_a_creature(self):
        game, a, b = self.table("Ogre")
        target = Permanent(OGRE)
        a.battlefield += [target, *lands(3)]
        self.kirol.prepared = True
        a.library = [RELIC, SHRINE, FOREST]
        cast_prepared(game, a, "Pack a Punch")
        self.assertEqual((target.counters.get("+1/+1"), game.power(target), game.has_keyword(target, "trample")), (2, 5, True))
        self.assertEqual((len(a.library), len(a.graveyard)), (2, 1))  # a card milled; the copy of the spell is not a card
        self.assertFalse(self.kirol.prepared)

    def test_the_trample_goes_to_the_creature_that_got_the_counters_and_not_to_kirol(self):
        game, a, b = self.table("Ogre")
        target = Permanent(OGRE)
        a.battlefield += [target, *lands(3)]
        self.kirol.prepared = True
        a.library = [RELIC, SHRINE, FOREST]
        cast_prepared(game, a, "Pack a Punch")
        self.assertFalse(game.has_keyword(self.kirol, "trample"))


class ItGainsTests(unittest.TestCase):
    def test_a_trigger_that_says_it_still_means_the_source(self):
        card = Card(name="Charger", type_line="Creature — Test", power="2", toughness="2",
                    oracle_text="When this creature enters, it gains trample until end of turn.")
        self.assertEqual(unsupported_lines(card), [])
        game, _ = table3(pick())
        a = game.seats[0]
        charger = Permanent(card)
        a.battlefield = [charger]
        game.trigger("enters", charger, a)
        run_stack(game)
        self.assertTrue(game.has_keyword(charger, "trample"))


SKYPAINTER = prep("Inspired Skypainter", "{U}{R}", "Creature — Lizard Wizard", "2", "2",
                  "Flying\nWhen this creature enters and whenever one or more creature tokens you control deal combat damage to a "
                  "player, this creature becomes prepared." + PREP_REMINDER,
                  "Maestro's Gift", "{3}{U}{R}", "Sorcery", "Create a token that's a copy of target creature you control. That token "
                                                          "gains haste until end of turn.")


class InspiredSkypainterTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(SKYPAINTER), [])

    def test_prepared_on_entering(self):
        game, _ = table3(pick())
        a = game.seats[0]
        painter = Permanent(SKYPAINTER)
        a.battlefield = [painter]
        game.trigger("enters", painter, a)
        run_stack(game)
        self.assertTrue(painter.prepared)

    def attack(self, attacker):
        game, a, b = two_player()
        painter = Permanent(SKYPAINTER, sick=True)
        a.battlefield = [painter, Permanent(attacker, sick=False)]
        fight(game, a)
        return painter

    def test_prepared_when_a_creature_token_hits_a_player(self):
        self.assertTrue(self.attack(SPIRIT).prepared)

    def test_not_prepared_when_only_a_nontoken_creature_hits(self):
        self.assertFalse(self.attack(BEAR).prepared)

    def test_maestros_gift_makes_a_hasty_token_copy(self):
        game, _ = table3(pick("Ogre"))
        a = game.seats[0]
        ogre = Permanent(OGRE)
        a.battlefield = [Permanent(SKYPAINTER, prepared=True), ogre, *lands(5)]
        cast_prepared(game, a, "Maestro's Gift")
        copies = [p for p in a.battlefield if p.card.name == "Ogre" and p is not ogre]
        self.assertEqual(len(copies), 1)
        self.assertTrue(copies[0].card.type_line.startswith("Token"))
        self.assertTrue(game.has_keyword(copies[0], "haste"))
        self.assertFalse(game.has_keyword(ogre, "haste"))


FOCUSMAGE = prep("Dirgur Focusmage", "{2}{U}", "Creature — Djinn Monk", "1", "4",
                 "Instant and sorcery spells you cast cost {1} less to cast.\nWhenever you cast an instant or sorcery spell with "
                 "mana value 5 or greater from your hand, this creature becomes prepared.",
                 "Braingeyser", "{X}{U}{U}", "Sorcery", "Target player draws X cards.")
BIG_INSTANT = Card(name="Big Wave", mana_cost="{4}{U}", cmc=5.0, type_line="Instant", oracle_text="You gain 1 life.")
SMALL_INSTANT = Card(name="Small Wave", mana_cost="{3}{U}", cmc=4.0, type_line="Instant", oracle_text="You gain 1 life.")
BIG_CREATURE = Card(name="Big Ogre", mana_cost="{4}{U}", cmc=5.0, type_line="Creature — Ogre", power="5", toughness="5")


class DirgurFocusmageTests(unittest.TestCase):
    def cast(self, spell, n=4):
        game, _ = table3(pick())
        a = game.seats[0]
        self.focusmage = Permanent(FOCUSMAGE)
        a.battlefield = [self.focusmage, *lands(n)]
        a.hand = [spell]
        game._perform(a, CAST + spell.name)
        run_stack(game)
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(FOCUSMAGE), [])

    def test_a_five_mana_instant_from_hand_costs_one_less_and_prepares_it(self):
        game, a = self.cast(BIG_INSTANT, n=4)
        self.assertEqual(a.life, 41)  # four lands paid for a five mana instant
        self.assertTrue(self.focusmage.prepared)

    def test_a_four_mana_instant_does_not(self):
        self.cast(SMALL_INSTANT, n=3)
        self.assertFalse(self.focusmage.prepared)

    def test_a_five_mana_creature_spell_does_not(self):
        self.cast(BIG_CREATURE, n=5)
        self.assertFalse(self.focusmage.prepared)

    def test_a_five_mana_instant_from_elsewhere_does_not(self):
        game, _ = table3(pick())
        a = game.seats[0]
        focusmage = Permanent(FOCUSMAGE)
        a.battlefield = [focusmage]
        a.cast_log.append((game.turn, BIG_INSTANT))
        game._observe("cast", BIG_INSTANT, a, from_hand=False)
        run_stack(game)
        self.assertFalse(focusmage.prepared)

    def test_a_opponents_cast_does_not(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        focusmage = Permanent(FOCUSMAGE)
        a.battlefield = [focusmage]
        b.cast_log.append((game.turn, BIG_INSTANT))
        game._observe("cast", BIG_INSTANT, b, from_hand=True)
        run_stack(game)
        self.assertFalse(focusmage.prepared)

    def test_braingeyser_draws_x_cards_for_the_target_player(self):
        game, _ = table3(script("2", "Player: B"))
        a, b, _ = game.seats
        a.battlefield = [Permanent(FOCUSMAGE, prepared=True), *lands(6)]
        b.library = [FOREST] * 10
        cast_prepared(game, a, "Braingeyser")
        self.assertEqual((len(b.hand), len(a.hand)), (2, 0))
        self.assertFalse(a.battlefield[0].prepared)


SHOTCALLER = prep("Striding Shotcaller", "{G}{U}", "Creature — Troll Druid", "0", "4",
                  "Reach\nWhenever one or more creatures you control deal combat damage to a player, this creature becomes prepared."
                  + PREP_REMINDER, "Run the Play", "{X}{G}{U}", "Sorcery",
                  "Put a +1/+1 counter on each of up to X target creatures. Those creatures gain flying until end of turn. Draw a card.")


class StridingShotcallerTests(unittest.TestCase):
    def attack(self, attackers, blockers=(), shotcaller_attacks=False):
        game, a, b = two_player(attack_all)
        b.player.policy = attack_all
        self.shotcaller = Permanent(SHOTCALLER, sick=not shotcaller_attacks)
        a.battlefield = [self.shotcaller, *[Permanent(c, sick=False) for c in attackers]]
        b.battlefield = [Permanent(c, sick=False) for c in blockers]
        fight(game, a)
        return game

    def test_parse(self):
        self.assertEqual(unsupported_lines(SHOTCALLER), [])

    def test_prepared_when_a_creature_hits_a_player(self):
        self.attack([BEAR])
        self.assertTrue(self.shotcaller.prepared)

    def test_not_prepared_when_the_attacker_is_blocked(self):
        self.attack([BEAR], blockers=[OGRE])
        self.assertFalse(self.shotcaller.prepared)

    def test_not_prepared_when_nothing_attacks(self):
        self.attack([])
        self.assertFalse(self.shotcaller.prepared)

    def test_a_creature_with_no_power_deals_no_damage_and_does_not_prepare_it(self):
        self.attack([], shotcaller_attacks=True)  # the Shotcaller is a 0/4
        self.assertFalse(self.shotcaller.prepared)

    def test_run_the_play_puts_counters_on_up_to_x_creatures_who_fly_and_draws(self):
        game, _ = table3(script("2", "Bear", "Ogre"))
        a = game.seats[0]
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        a.battlefield = [Permanent(SHOTCALLER, prepared=True), bear, ogre, *lands(4)]
        a.library = [FOREST] * 5
        cast_prepared(game, a, "Run the Play")
        self.assertEqual((bear.counters.get("+1/+1"), ogre.counters.get("+1/+1")), (1, 1))
        self.assertTrue(game.has_keyword(bear, "flying") and game.has_keyword(ogre, "flying"))
        self.assertEqual(len(a.hand), 1)


DYNASTORIAN = prep("Eiganjo Dynastorian", "{2}{W}", "Creature — Fox Advisor", "2", "3",
                   "Vigilance\nWhenever you attack with two or more creatures, this creature becomes prepared." + PREP_REMINDER,
                   "Replenish", "{3}{W}", "Sorcery", "Return all enchantment cards from your graveyard to the battlefield.")


class EiganjoDynastorianTests(unittest.TestCase):
    def attack(self, attackers, dynastorian_attacks=False):
        game, a, b = two_player()
        self.dynastorian = Permanent(DYNASTORIAN, sick=not dynastorian_attacks)
        a.battlefield = [self.dynastorian, *[Permanent(c, sick=False) for c in attackers]]
        fight(game, a)

    def test_parse(self):
        self.assertEqual(unsupported_lines(DYNASTORIAN), [])

    def test_prepared_when_you_attack_with_two_creatures(self):
        self.attack([BEAR, OGRE])
        self.assertTrue(self.dynastorian.prepared)

    def test_not_prepared_when_you_attack_with_one(self):
        self.attack([BEAR])
        self.assertFalse(self.dynastorian.prepared)

    def test_the_dynastorian_itself_can_be_one_of_the_two(self):
        self.attack([BEAR], dynastorian_attacks=True)
        self.assertTrue(self.dynastorian.prepared)

    def test_the_dynastorian_attacking_alone_is_not_enough(self):
        self.attack([], dynastorian_attacks=True)
        self.assertFalse(self.dynastorian.prepared)

    def test_replenish_returns_every_enchantment_card_from_the_graveyard(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(DYNASTORIAN, prepared=True), *lands(4)]
        a.graveyard = [SHRINE, BEAR, SHRINE]
        cast_prepared(game, a, "Replenish")
        self.assertEqual(sorted(p.card.name for p in a.battlefield if p.card.name == "Shrine"), ["Shrine", "Shrine"])
        self.assertEqual([c.name for c in a.graveyard], ["Bear"])


DUSKMAGE = prep("Defacing Duskmage", "{W}{B}", "Creature — Dog Warlock", "2", "2",
                "Deathtouch\nWhenever an opponent draws their second card each turn, this creature becomes prepared." + PREP_REMINDER,
                "Vandal's Edit", "{1}{W}{B}", "Instant", "Draw two cards. Each player loses 2 life.")


class DefacingDuskmageTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        self.duskmage = Permanent(DUSKMAGE)
        a.battlefield = [self.duskmage]
        for seat in game.seats:
            seat.library = [FOREST] * 10
        return game, a, b, c

    def test_parse(self):
        self.assertEqual(unsupported_lines(DUSKMAGE), [])

    def test_the_first_card_does_not_prepare_it_and_the_second_does(self):
        game, a, b, c = self.table()
        game.draw(b, 1)
        run_stack(game)
        self.assertFalse(self.duskmage.prepared)
        game.draw(b, 1)
        run_stack(game)
        self.assertTrue(self.duskmage.prepared)

    def test_two_cards_at_once_count(self):
        game, a, b, c = self.table()
        game.draw(c, 2)
        run_stack(game)
        self.assertTrue(self.duskmage.prepared)

    def test_only_the_second_card_counts_not_the_third(self):
        game, a, b, c = self.table()
        game.draw(b, 2)
        run_stack(game)
        self.duskmage.prepared = False
        game.draw(b, 1)
        run_stack(game)
        self.assertFalse(self.duskmage.prepared)

    def test_your_own_second_card_does_not(self):
        game, a, b, c = self.table()
        game.draw(a, 3)
        run_stack(game)
        self.assertFalse(self.duskmage.prepared)

    def test_vandals_edit_draws_two_and_each_player_loses_two(self):
        game, a, b, c = self.table()
        a.battlefield += lands(3)
        self.duskmage.prepared = True
        cast_prepared(game, a, "Vandal's Edit")
        self.assertEqual((len(a.hand), [s.life for s in game.seats]), (2, [38, 38, 38]))


PESTFINDER = prep("Eccentric Pestfinder", "{2}{B}{G}", "Creature — Troll Druid", "5", "5",
                  "Trample\nAt the beginning of each end step, if you gained life this turn, this creature becomes prepared."
                  + PREP_REMINDER, "Turn Stones", "{B}{G}", "Sorcery",
                  'For each opponent, you create a 1/1 black and green Pest creature token with "When this token dies, you gain 1 '
                  'life."')


class EccentricPestfinderTests(unittest.TestCase):
    def end_step(self, change=0, event_seat=0):
        game, _ = table3(pick())
        a = game.seats[0]
        self.pestfinder = Permanent(PESTFINDER)
        a.battlefield = [self.pestfinder]
        if change:
            game.change_life(a, change)
        game.trigger("each_end_step", self.pestfinder, a)
        run_stack(game)

    def test_parse(self):
        self.assertEqual(unsupported_lines(PESTFINDER), [])

    def test_prepared_at_an_end_step_after_gaining_life(self):
        self.end_step(change=2)
        self.assertTrue(self.pestfinder.prepared)

    def test_not_prepared_without_gaining_life(self):
        self.end_step()
        self.assertFalse(self.pestfinder.prepared)

    def test_losing_life_is_not_gaining_it(self):
        self.end_step(change=-3)
        self.assertFalse(self.pestfinder.prepared)

    def test_turn_stones_makes_a_pest_for_each_opponent(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(PESTFINDER, prepared=True), *lands(2)]
        cast_prepared(game, a, "Turn Stones")
        self.assertEqual(sum(p.card.name == "Pest" for p in a.battlefield), 2)  # a three-player table
