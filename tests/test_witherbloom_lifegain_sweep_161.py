"""The seven Witherbloom lifegain and token creatures of the precon decks that no test named (issue #161), each played from its real
Oracle text, with cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE, attack_all
from tests.test_effects import lands, pick, table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import Table, battlefield_names, real
from tests.test_triggers_80 import FOREST, RELIC, SHRINE
from tests.test_x_targets import script

SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
BLACK_BEAR = real("Black Bear", "{1}{B}", "Creature — Bear", "", "2", "2", colors=("B",))
GREEN_BEAR = real("Green Bear", "{1}{G}", "Creature — Bear", "", "2", "2", colors=("G",))
RED_BEAR = real("Red Bear", "{1}{R}", "Creature — Bear", "", "2", "2", colors=("R",))
GRAVE_CREATURE = real("Fallen Hero", "{2}", "Creature — Human", "", "2", "2")


def step(game, seat, name):
    game.active = seat.index
    game.step = name
    game._turn_based_actions(seat)
    run_stack(game)


def fight(game, seat):
    game.active = seat.index
    game.combat.declare_attackers(seat)
    run_stack(game)
    game.combat.declare_blockers()
    run_stack(game)
    game.combat.deal_damage(first_strike_step=False)
    run_stack(game)


def end_turn(game, seat):
    game.step = "cleanup"
    game._turn_based_actions(seat)


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


def activations(game, seat, fragment):
    return [a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a]


DAEMOGOTH = real("Defiling Daemogoth", "{3}{B}{B}", "Creature — Demon",
                 "Menace\nWhenever a creature you control deals combat damage to a player, you gain 1 life.\nAt the beginning of your end step, each "
                 "opponent loses X life, where X is the amount of life you gained this turn.", "5", "4")


class DefilingDaemogothTests(unittest.TestCase):
    def attack(self, attackers, blockers=()):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(DAEMOGOTH, sick=True)] + [Permanent(c, sick=False) for c in attackers]
        b.battlefield = [Permanent(c, sick=False) for c in blockers]
        fight(game, a)
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(DAEMOGOTH), [])

    def test_each_creature_that_connects_gains_you_a_life(self):
        game, a, b = self.attack([BEAR, OGRE])
        self.assertEqual(a.life, 42)

    def test_a_blocked_creature_gains_nothing(self):
        game, a, b = self.attack([BEAR], blockers=[OGRE])
        self.assertEqual(a.life, 40)

    def test_the_end_step_drains_opponents_by_the_life_you_gained_this_turn(self):
        game, a, b = self.attack([BEAR, OGRE])
        step(game, a, "end")
        self.assertEqual((a.life, b.life), (42, 33))  # 5 combat damage from Bear and Ogre, then 2 for the life gained

    def test_life_from_other_sources_counts(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        a.battlefield = [Permanent(DAEMOGOTH)]
        game.change_life(a, 5)
        step(game, a, "end")
        self.assertEqual((b.life, c.life), (35, 35))

    def test_no_life_gained_no_drain_and_only_at_your_own_end_step(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        a.battlefield = [Permanent(DAEMOGOTH)]
        step(game, a, "end")
        self.assertEqual((b.life, c.life), (40, 40))
        game.change_life(a, 4)
        step(game, b, "end")
        self.assertEqual((b.life, c.life), (40, 40))

    def test_life_gained_in_an_earlier_turn_does_not_count(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        a.battlefield = [Permanent(DAEMOGOTH)]
        game.change_life(a, 6)
        game.turn += 3  # my next turn
        step(game, a, "end")
        self.assertEqual((b.life, c.life), (40, 40))

    def test_life_lost_does_not_count(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        a.battlefield = [Permanent(DAEMOGOTH)]
        game.change_life(a, -3)
        step(game, a, "end")
        self.assertEqual(b.life, 40)

    def test_it_has_menace(self):
        game, _ = table3(pick())
        self.assertTrue(game.has_keyword(Permanent(DAEMOGOTH), "menace"))


DRYAD = real("Tendershoot Dryad", "{4}{G}", "Creature — Dryad",
             "Ascend (If you control ten or more permanents, you get the city's blessing for the rest of the game.)\nAt the beginning of each "
             "upkeep, create a 1/1 green Saproling creature token.\nSaprolings you control get +2/+2 as long as you have the city's blessing.", "2", "2")


class TendershootDryadTests(unittest.TestCase):
    def table(self, extra=0):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(DRYAD)] + [Permanent(RELIC) for _ in range(extra)]
        return game, a, b

    def saprolings(self, seat):
        return [p for p in seat.battlefield if p.card.name == "Saproling"]

    def test_parse(self):
        self.assertEqual(unsupported_lines(DRYAD), [])

    def test_each_upkeep_makes_a_saproling_including_an_opponents(self):
        game, a, b = self.table()
        step(game, a, "upkeep")
        step(game, b, "upkeep")
        self.assertEqual(len(self.saprolings(a)), 2)

    def upkeep(self, game, seat):
        step(game, seat, "upkeep")
        game._check_state()
        return self.saprolings(seat)[0]

    def test_without_the_citys_blessing_a_saproling_is_a_one_one(self):
        game, a, b = self.table(extra=3)
        sap = self.upkeep(game, a)
        self.assertEqual((game.power(sap), game.toughness(sap)), (1, 1))

    def test_ten_permanents_give_the_blessing_and_the_saprolings_get_plus_two_plus_two(self):
        game, a, b = self.table(extra=8)  # nine, and the Saproling makes ten
        sap = self.upkeep(game, a)
        self.assertEqual(len(a.battlefield), 10)
        self.assertEqual((game.power(sap), game.toughness(sap)), (3, 3))

    def test_nine_permanents_are_not_enough(self):
        game, a, b = self.table(extra=7)  # eight, and the Saproling makes nine
        sap = self.upkeep(game, a)
        self.assertEqual(len(a.battlefield), 9)
        self.assertEqual(game.power(sap), 1)

    def test_the_blessing_lasts_for_the_rest_of_the_game(self):
        game, a, b = self.table(extra=9)  # ten permanents
        game._check_state()
        for permanent in [p for p in a.battlefield if p.card.name == "Relic"][:6]:
            a.battlefield.remove(permanent)
        sap = self.upkeep(game, a)
        self.assertLess(len(a.battlefield), 10)
        self.assertEqual(game.power(sap), 3)

    def test_it_boosts_only_saprolings_you_control(self):
        game, a, b = self.table(extra=9)
        other = Permanent(Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1"))
        theirs = Permanent(Card(name="Saproling", type_line="Token Creature — Saproling", power="1", toughness="1"))
        a.battlefield.append(other)
        b.battlefield = [theirs]
        game._check_state()
        self.assertEqual((game.power(other), game.power(theirs)), (1, 1))


JADAR = real("Jadar, Ghoulcaller of Nephalia", "{1}{B}", "Legendary Creature — Human Wizard",
             "At the beginning of your end step, if you control no creatures with decayed, create a 2/2 black Zombie creature token with decayed. "
             "(It can't block. When it attacks, sacrifice it at end of combat.)", "1", "1")


class JadarTests(unittest.TestCase):
    def zombies(self, seat):
        return [p for p in seat.battlefield if p.card.name == "Zombie"]

    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(JADAR)]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(JADAR), [])

    def test_at_your_end_step_it_makes_a_two_two_zombie_with_decayed(self):
        game, a, b = self.table()
        step(game, a, "end")
        [zombie] = self.zombies(a)
        self.assertEqual((game.power(zombie), game.toughness(zombie)), (2, 2))
        self.assertTrue(game.has_keyword(zombie, "decayed"))

    def test_not_while_you_already_control_a_creature_with_decayed(self):
        game, a, b = self.table()
        step(game, a, "end")
        step(game, a, "end")
        self.assertEqual(len(self.zombies(a)), 1)

    def test_an_opponents_decayed_creature_does_not_stop_it(self):
        game, a, b = self.table()
        b.battlefield = [Permanent(Card(name="Their Zombie", type_line="Token Creature — Zombie", oracle_text="Decayed", power="2", toughness="2"))]
        step(game, a, "end")
        self.assertEqual(len(self.zombies(a)), 1)

    def test_only_at_your_own_end_step(self):
        game, a, b = self.table()
        step(game, b, "end")
        self.assertEqual(len(self.zombies(a)), 0)

    def test_the_zombie_cannot_block_and_is_sacrificed_after_it_attacks(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(JADAR, sick=True)]
        step(game, a, "end")
        game.turn += 2
        for p in a.battlefield:
            p.sick = False
        fight(game, a)
        game.step = "main2"
        game._turn_based_actions(a)
        self.assertEqual(self.zombies(a), [])

    def test_a_new_zombie_arrives_once_the_old_one_is_gone(self):
        game, a, b = self.table()
        step(game, a, "end")
        game.destroy(self.zombies(a)[0])
        step(game, a, "end")
        self.assertEqual(len(self.zombies(a)), 1)


COVEN = real("Veinwitch Coven", "{2}{B}", "Creature — Vampire Warlock",
             "Menace\nWhenever you gain life, you may pay {B}. If you do, return target creature card from your graveyard to your hand.", "3", "3")


class VeinwitchCovenTests(unittest.TestCase):
    def gain(self, *answers, graveyard=(GRAVE_CREATURE,), n=1, seat_gains=0):
        t = Table(CANTRIP_CARD, *answers, n=n, graveyard=list(graveyard), mine=[Permanent(COVEN)])
        t.game.change_life(t.game.seats[seat_gains], 2)
        run_stack(t.game)
        return t

    def test_parse(self):
        self.assertEqual(unsupported_lines(COVEN), [])

    def test_paying_b_returns_a_creature_card_to_hand(self):
        t = self.gain("Fallen Hero", "Pay")
        self.assertEqual(([c.name for c in t.a.hand if c.name != "Cantrip"], t.a.graveyard), (["Fallen Hero"], []))
        self.assertEqual(sum(p.tapped for p in t.a.battlefield), 1)

    def test_it_may_decline(self):
        t = self.gain("Fallen Hero", "Don't")
        self.assertEqual(([c.name for c in t.a.graveyard], sum(p.tapped for p in t.a.battlefield)), (["Fallen Hero"], 0))

    def test_without_the_mana_it_does_nothing(self):
        t = self.gain("Fallen Hero", "Pay", n=0)
        self.assertEqual([c.name for c in t.a.graveyard], ["Fallen Hero"])

    def test_a_noncreature_card_is_not_a_choice(self):
        t = self.gain("Relic", "Pay", graveyard=(RELIC,))
        self.assertEqual([c.name for c in t.a.graveyard], ["Relic"])

    def test_an_opponent_gaining_life_does_nothing(self):
        t = self.gain("Fallen Hero", "Pay", seat_gains=1)
        self.assertEqual([c.name for c in t.a.graveyard], ["Fallen Hero"])

    def test_losing_life_does_nothing(self):
        t = Table(CANTRIP_CARD, "Fallen Hero", "Pay", n=1, graveyard=[GRAVE_CREATURE], mine=[Permanent(COVEN)])
        t.game.change_life(t.a, -2)
        run_stack(t.game)
        self.assertEqual([c.name for c in t.a.graveyard], ["Fallen Hero"])


CANTRIP_CARD = real("Cantrip", "{W}", "Instant", "Draw a card.")
GARDEN = real("Trudge Garden", "{2}{G}", "Enchantment", "Whenever you gain life, you may pay {2}. If you do, create a 4/4 green Fungus Beast creature "
                                                        "token with trample.")


class TrudgeGardenTests(unittest.TestCase):
    def gain(self, *answers, n=2, seat_gains=0, amount=2):
        t = Table(CANTRIP_CARD, *answers, n=n, mine=[Permanent(GARDEN)])
        t.game.change_life(t.game.seats[seat_gains], amount)
        run_stack(t.game)
        return t

    def test_parse(self):
        self.assertEqual(unsupported_lines(GARDEN), [])

    def test_paying_two_makes_a_four_four_trampling_fungus_beast(self):
        t = self.gain("Pay")
        [beast] = [p for p in t.a.battlefield if p.card.name == "Fungus Beast"]
        self.assertEqual((t.game.power(beast), t.game.toughness(beast), t.game.has_keyword(beast, "trample")), (4, 4, True))
        self.assertEqual(sum(p.tapped for p in t.a.battlefield), 2)

    def test_it_may_decline(self):
        t = self.gain("Don't")
        self.assertFalse(any(p.card.name == "Fungus Beast" for p in t.a.battlefield))

    def test_without_two_mana_it_cannot_pay(self):
        t = self.gain("Pay", n=1)
        self.assertFalse(any(p.card.name == "Fungus Beast" for p in t.a.battlefield))

    def test_an_opponent_gaining_life_does_nothing(self):
        t = self.gain("Pay", seat_gains=1)
        self.assertFalse(any(p.card.name == "Fungus Beast" for p in t.a.battlefield))

    def test_each_instance_of_life_gain_is_its_own_trigger(self):
        t = Table(CANTRIP_CARD, "Pay", "Pay", n=4, mine=[Permanent(GARDEN)])
        t.game.change_life(t.a, 1)
        run_stack(t.game)
        t.game.change_life(t.a, 1)
        run_stack(t.game)
        self.assertEqual(sum(p.card.name == "Fungus Beast" for p in t.a.battlefield), 2)


BELEDROS = real("Beledros Witherbloom", "{5}{B}{G}", "Legendary Creature — Elder Dragon",
                "Flying\nAt the beginning of each upkeep, create a 1/1 black and green Pest creature token with \"When this token dies, you gain 1 "
                "life.\"\nPay 10 life: Untap all lands you control. Activate only once each turn.", "4", "4")


class BeledrosWitherbloomTests(unittest.TestCase):
    def table(self, life=40):
        game, _ = table3(pick())
        a, b, _ = game.seats
        a.battlefield = [Permanent(BELEDROS)] + [Permanent(FOREST, tapped=True) for _ in range(3)]
        a.life = life
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(BELEDROS), [])

    def test_each_upkeep_makes_a_black_and_green_pest(self):
        game, a, b = self.table()
        step(game, a, "upkeep")
        step(game, b, "upkeep")
        pests = [p for p in a.battlefield if p.card.name == "Pest"]
        self.assertEqual(len(pests), 2)
        self.assertEqual((game.power(pests[0]), game.toughness(pests[0])), (1, 1))

    def test_a_pest_dying_gains_you_a_life(self):
        game, a, b = self.table()
        step(game, a, "upkeep")
        pest = next(p for p in a.battlefield if p.card.name == "Pest")
        game.destroy(pest)
        run_stack(game)
        self.assertEqual(a.life, 41)

    def test_ten_life_untaps_all_your_lands(self):
        game, a, b = self.table()
        activate(game, a, "Untap all lands")
        self.assertEqual((a.life, [p.tapped for p in a.battlefield if p.card.name == "Forest"]), (30, [False, False, False]))

    def test_only_once_each_turn_and_again_the_next(self):
        game, a, b = self.table()
        activate(game, a, "Untap all lands")
        self.assertEqual(activations(game, a, "Untap all lands"), [])
        game.turn += 1
        self.assertEqual(len(activations(game, a, "Untap all lands")), 1)

    def test_it_cannot_be_paid_without_ten_life(self):
        game, a, b = self.table(life=9)
        self.assertEqual(activations(game, a, "Untap all lands"), [])

    def test_it_untaps_only_your_lands(self):
        game, a, b = self.table()
        theirs = Permanent(FOREST, tapped=True)
        b.battlefield = [theirs]
        activate(game, a, "Untap all lands")
        self.assertTrue(theirs.tapped)


LIEGE = real("Creakwood Liege", "{1}{B/G}{B/G}{B/G}", "Creature — Horror",
             "Other black creatures you control get +1/+1.\nOther green creatures you control get +1/+1.\nAt the beginning of your upkeep, you may "
             "create a 1/1 black and green Worm creature token.", "2", "2")


class CreakwoodLiegeTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick("Yes"))
        a, b, _ = game.seats
        self.liege = Permanent(LIEGE)
        a.battlefield = [self.liege]
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(LIEGE), [])

    def test_other_black_and_green_creatures_get_plus_one_plus_one(self):
        game, a, b = self.table()
        black, green, red, colorless = Permanent(BLACK_BEAR), Permanent(GREEN_BEAR), Permanent(RED_BEAR), Permanent(BEAR)
        a.battlefield += [black, green, red, colorless]
        self.assertEqual([game.power(p) for p in (black, green, red, colorless)], [3, 3, 2, 2])

    def test_it_does_not_boost_itself(self):
        game, a, b = self.table()
        self.assertEqual((game.power(self.liege), game.toughness(self.liege)), (2, 2))

    def test_it_does_not_boost_an_opponents_creatures(self):
        game, a, b = self.table()
        theirs = Permanent(BLACK_BEAR)
        b.battlefield = [theirs]
        self.assertEqual(game.power(theirs), 2)

    def test_a_black_and_green_creature_gets_both_bonuses(self):
        game, a, b = self.table()
        both = Permanent(real("Both Bear", "{B}{G}", "Creature — Bear", "", "2", "2", colors=("B", "G")))
        a.battlefield.append(both)
        self.assertEqual((game.power(both), game.toughness(both)), (4, 4))

    def test_upkeep_it_may_make_a_worm_that_it_pumps(self):
        game, a, b = self.table()
        step(game, a, "upkeep")
        [worm] = [p for p in a.battlefield if p.card.name == "Worm"]
        self.assertEqual((game.power(worm), game.toughness(worm)), (3, 3))  # a 1/1 that is black and green

    def test_the_worm_may_be_declined(self):
        game, _ = table3(pick("No"))
        a = game.seats[0]
        a.battlefield = [Permanent(LIEGE)]
        step(game, a, "upkeep")
        self.assertFalse(any(p.card.name == "Worm" for p in a.battlefield))

    def test_only_at_your_own_upkeep(self):
        game, a, b = self.table()
        step(game, b, "upkeep")
        self.assertFalse(any(p.card.name == "Worm" for p in a.battlefield))
