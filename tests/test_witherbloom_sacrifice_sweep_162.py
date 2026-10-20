"""The six Witherbloom sacrifice and death-trigger creatures of the precon decks that no test named (issue #162), each played from
their real Oracle text, with cases where the effect must not apply."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import attack_all, battlefield_names, BEAR, FOREST, lands, OGRE, pick, PLAINS, real, RELIC, run_stack, SHRINE, table, table3

SPIRIT = Card(name="Spirit", type_line="Token Creature — Spirit", power="1", toughness="1")
FOOD = Card(name="Food", type_line="Token Artifact — Food")


def activate(game, seat, fragment):
    action = next(a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a)
    game._perform(seat, action)
    run_stack(game)


def activations(game, seat, fragment):
    return [a for a in game.legal_actions(seat) if a.startswith(ACTIVATE) and fragment in a]


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


def counters(permanent):
    return permanent.counters.get("+1/+1", 0)


YAHENNI = real("Yahenni, Undying Partisan", "{2}{B}", "Legendary Creature — Aetherborn Vampire",
               "Haste\nWhenever a creature an opponent controls dies, put a +1/+1 counter on Yahenni.\nSacrifice another creature: Yahenni gains "
               "indestructible until end of turn.", "2", "2")


class YahenniTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick("Bear"))
        a, b, c = game.seats
        self.yahenni, self.mine = Permanent(YAHENNI), Permanent(BEAR)
        a.battlefield = [self.yahenni, self.mine]
        return game, a, b, c

    def test_parse(self):
        self.assertEqual(unsupported_lines(YAHENNI), [])

    def test_it_has_haste(self):
        game, a, b, c = self.table()
        self.assertTrue(game.has_keyword(self.yahenni, "haste"))

    def test_each_opposing_creature_that_dies_gives_it_a_counter(self):
        game, a, b, c = self.table()
        ogre, bear = Permanent(OGRE), Permanent(BEAR)
        b.battlefield, c.battlefield = [ogre], [bear]
        game.destroy(ogre)
        game.destroy(bear)
        run_stack(game)
        self.assertEqual(counters(self.yahenni), 2)

    def test_your_own_creatures_dying_gives_nothing(self):
        game, a, b, c = self.table()
        game.destroy(self.mine)
        run_stack(game)
        self.assertEqual(counters(self.yahenni), 0)

    def test_an_opposing_noncreature_dying_gives_nothing(self):
        game, a, b, c = self.table()
        relic = Permanent(RELIC)
        b.battlefield = [relic]
        game.destroy(relic)
        run_stack(game)
        self.assertEqual(counters(self.yahenni), 0)

    def test_sacrificing_another_creature_makes_it_indestructible_until_end_of_turn(self):
        game, a, b, c = self.table()
        activate(game, a, "Sacrifice another creature")
        self.assertNotIn(self.mine, a.battlefield)
        game.destroy(self.yahenni)
        self.assertIn(self.yahenni, a.battlefield)
        end_turn(game, a)
        game.destroy(self.yahenni)
        self.assertNotIn(self.yahenni, a.battlefield)

    def test_it_cannot_sacrifice_itself_for_the_ability(self):
        game, _ = table3(pick())
        a = game.seats[0]
        a.battlefield = [Permanent(YAHENNI)]
        self.assertEqual(activations(game, a, "Sacrifice another creature"), [])


OHRAN = real("Ohran Frostfang", "{3}{G}{G}", "Snow Creature — Snake",
             "Attacking creatures you control have deathtouch.\nWhenever a creature you control deals combat damage to a player, draw a card.", "2", "6")


class OhranFrostfangTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(OHRAN), [])

    def attack(self, blockers=()):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        self.ohran, self.bear = Permanent(OHRAN, sick=True), Permanent(BEAR, sick=False)
        a.battlefield = [self.ohran, self.bear]
        b.battlefield = [Permanent(c, sick=False) for c in blockers]
        a.library = [FOREST] * 5
        game.active = 0
        game.combat.declare_attackers(a)
        run_stack(game)
        return game, a, b

    def test_attacking_creatures_have_deathtouch_and_others_do_not(self):
        game, a, b = self.attack()
        self.assertTrue(game.has_keyword(self.bear, "deathtouch"))
        self.assertFalse(game.has_keyword(self.ohran, "deathtouch"))  # it is not attacking

    def test_an_attacking_bear_kills_a_big_blocker(self):
        game, a, b = self.attack(blockers=[real("Wall", "{3}", "Creature — Wall", "", "0", "9")])
        game.combat.declare_blockers()
        game.combat.deal_damage(first_strike_step=False)
        game._check_state()
        self.assertEqual(battlefield_names(b), [])

    def test_opposing_attackers_do_not_get_deathtouch(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(OHRAN)]
        enemy = Permanent(OGRE, sick=False)
        b.battlefield = [enemy]
        game.active = 1
        game.combat.declare_attackers(b)
        self.assertFalse(game.has_keyword(enemy, "deathtouch"))

    def test_a_creature_that_connects_draws_a_card(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(OHRAN, sick=True), Permanent(BEAR, sick=False), Permanent(OGRE, sick=False)]
        a.library = [FOREST] * 5
        fight(game, a)
        self.assertEqual(len(a.hand), 2)  # once for each creature

    def test_a_blocked_creature_draws_nothing(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(OHRAN, sick=True), Permanent(BEAR, sick=False)]
        b.battlefield = [Permanent(OGRE, sick=False)]
        a.library = [FOREST] * 5
        fight(game, a)
        self.assertEqual(len(a.hand), 0)

    def test_an_opponents_creature_connecting_draws_you_nothing(self):
        game, _, _ = table(attack_all, attack_all)
        a, b = game.seats
        a.battlefield = [Permanent(OHRAN, sick=True)]
        b.battlefield = [Permanent(OGRE, sick=False)]
        a.library = [FOREST] * 5
        fight(game, b)
        self.assertEqual(len(a.hand), 0)


MAZIREK = real("Mazirek, Kraul Death Priest", "{3}{B}{G}", "Legendary Creature — Insect Shaman",
               "Flying\nWhenever a player sacrifices another permanent, put a +1/+1 counter on each creature you control.", "2", "2")


class MazirekTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, c = game.seats
        self.mazirek, self.bear = Permanent(MAZIREK), Permanent(BEAR)
        a.battlefield = [self.mazirek, self.bear, Permanent(RELIC)]
        return game, a, b, c

    def test_parse(self):
        self.assertEqual(unsupported_lines(MAZIREK), [])

    def test_you_sacrificing_another_permanent_puts_a_counter_on_each_of_your_creatures(self):
        game, a, b, c = self.table()
        game.sacrifice(a, "artifact")
        run_stack(game)
        self.assertEqual((counters(self.mazirek), counters(self.bear)), (1, 1))

    def test_an_opponent_sacrificing_a_permanent_also_counts_and_only_your_creatures_grow(self):
        game, a, b, c = self.table()
        theirs = Permanent(OGRE)
        b.battlefield = [theirs]
        game.sacrifice(b, "creature")
        run_stack(game)
        self.assertEqual((counters(self.mazirek), counters(self.bear)), (1, 1))

    def test_it_sacrificing_itself_does_not_count(self):
        game, _ = table3(pick())
        a = game.seats[0]
        mazirek = Permanent(MAZIREK)
        a.battlefield = [mazirek, Permanent(BEAR)]
        game.sacrifice(a, "creature")  # the choice is the first creature: Mazirek itself
        run_stack(game)
        self.assertEqual(sum(counters(p) for p in a.battlefield), 0)

    def test_a_permanent_dying_without_being_sacrificed_gives_nothing(self):
        game, a, b, c = self.table()
        game.destroy(self.bear)
        run_stack(game)
        self.assertEqual(counters(self.mazirek), 0)

    def test_it_has_flying(self):
        game, a, b, c = self.table()
        self.assertTrue(game.has_keyword(self.mazirek, "flying"))


OPPORTUNIST = real("Morbid Opportunist", "{2}{B}", "Creature — Human Rogue",
                   "Whenever one or more other creatures die, draw a card. This ability triggers only once each turn.", "1", "3")


class MorbidOpportunistTests(unittest.TestCase):
    def table(self):
        game, _ = table3(pick())
        a, b, _ = game.seats
        self.opportunist = Permanent(OPPORTUNIST)
        a.battlefield = [self.opportunist]
        a.library = [FOREST] * 10
        return game, a, b

    def test_parse(self):
        self.assertEqual(unsupported_lines(OPPORTUNIST), [])

    def test_another_creature_dying_draws_a_card_whoever_controls_it(self):
        game, a, b = self.table()
        mine, theirs = Permanent(BEAR), Permanent(OGRE)
        a.battlefield.append(mine)
        b.battlefield = [theirs]
        game.destroy(theirs)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_several_creatures_dying_together_draw_one_card(self):
        game, a, b = self.table()
        creatures = [Permanent(BEAR), Permanent(OGRE)]
        b.battlefield = list(creatures)
        game.destroy_all(creatures)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)

    def test_only_once_each_turn_and_again_the_next(self):
        game, a, b = self.table()
        first, second, third = Permanent(BEAR), Permanent(OGRE), Permanent(BEAR)
        b.battlefield = [first, second, third]
        game.destroy(first)
        run_stack(game)
        game.destroy(second)
        run_stack(game)
        self.assertEqual(len(a.hand), 1)
        game.turn += 1
        game.destroy(third)
        run_stack(game)
        self.assertEqual(len(a.hand), 2)

    def test_it_dying_itself_does_not_draw(self):
        game, a, b = self.table()
        game.destroy(self.opportunist)
        run_stack(game)
        self.assertEqual(len(a.hand), 0)

    def test_a_noncreature_dying_does_not_draw(self):
        game, a, b = self.table()
        relic = Permanent(RELIC)
        a.battlefield.append(relic)
        game.destroy(relic)
        run_stack(game)
        self.assertEqual(len(a.hand), 0)


ZEALOT = real("Umbral Collar Zealot", "{1}{B}", "Creature — Human Cleric", "Sacrifice another creature or artifact: Surveil 1. (Look at the top card of your "
                                                                         "library. You may put it into your graveyard.)", "3", "2")
SEER = real("Viscera Seer", "{B}", "Creature — Vampire Wizard", "Sacrifice a creature: Scry 1. (Look at the top card of your library. You may put that "
                                                                  "card on the bottom.)", "1", "1")


class SurveilAndScryTests(unittest.TestCase):
    def table(self, card, fodder, policy):
        game, _ = table3(policy)
        a = game.seats[0]
        self.source = Permanent(card)
        a.battlefield = [self.source] + [Permanent(c) for c in fodder]
        a.library = [PLAINS, FOREST, FOREST, FOREST]
        return game, a

    def test_parse(self):
        self.assertEqual(unsupported_lines(ZEALOT), [])
        self.assertEqual(unsupported_lines(SEER), [])

    def test_the_zealot_sacrifices_another_creature_or_an_artifact_to_surveil_one(self):
        for fodder in (BEAR, RELIC):
            game, a = self.table(ZEALOT, [fodder], pick("Put into", fodder.name))
            activate(game, a, "Sacrifice another creature or artifact")
            self.assertEqual([c.name for c in a.graveyard if c.name == "Plains"], ["Plains"], fodder.name)
            self.assertEqual(battlefield_names(a), ["Umbral Collar Zealot"], fodder.name)

    def test_surveil_may_keep_the_card_on_top(self):
        game, a = self.table(ZEALOT, [BEAR], pick("Keep on top"))
        activate(game, a, "Sacrifice another creature or artifact")
        self.assertEqual((a.library[0].name, [c.name for c in a.graveyard]), ("Plains", ["Bear"]))

    def test_the_zealot_cannot_sacrifice_itself_or_a_land_or_an_enchantment(self):
        game, a = self.table(ZEALOT, [SHRINE, FOREST], pick())
        self.assertEqual(activations(game, a, "Sacrifice another creature or artifact"), [])

    def test_the_seer_sacrifices_a_creature_to_scry_one(self):
        game, a = self.table(SEER, [BEAR], pick("Bottom", "Put", "Bear"))
        activate(game, a, "Sacrifice a creature")
        self.assertEqual(a.library[-1].name, "Plains")
        self.assertEqual([c.name for c in a.graveyard], ["Bear"])

    def test_the_seer_may_keep_the_card_on_top(self):
        game, a = self.table(SEER, [BEAR], pick("Keep", "Top", "Bear"))
        activate(game, a, "Sacrifice a creature")
        self.assertEqual(a.library[0].name, "Plains")

    def test_the_seer_may_sacrifice_itself(self):
        game, a = self.table(SEER, [], pick())
        activate(game, a, "Sacrifice a creature")
        self.assertEqual(battlefield_names(a), [])
        self.assertEqual([c.name for c in a.graveyard], ["Viscera Seer"])

    def test_the_seer_cannot_sacrifice_an_artifact_that_is_not_a_creature(self):
        game, a = self.table(SEER, [RELIC], pick("Relic"))
        activate(game, a, "Sacrifice a creature")
        self.assertEqual(battlefield_names(a), ["Relic"])  # the Seer itself was the only creature to sacrifice
