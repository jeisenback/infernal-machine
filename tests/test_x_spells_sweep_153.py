"""The eight X spells of the precon decks that no test named (issue #153), each played from its real Oracle text through
casting with X chosen, including X of 0 and cases where the effect must not apply."""

import unittest

from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BARGAIN, battlefield_names, BEAR, BIG, FOREST, lands, OGRE, PLAINS, priority_cast, real, RELIC, SHRINE, Table


def end_turn(game, seat):
    game.step = "cleanup"
    game._turn_based_actions(seat)


def castable(table):
    return any(a.startswith(CAST + table.card.name) for a in table.game.legal_actions(table.a))


ALGORITHM = real("Expansion Algorithm", "{X}{U}{U}", "Sorcery",
                 "Proliferate X times. (To proliferate, choose any number of permanents and/or players, then give each another counter "
                 "of each kind already there.)")


class ExpansionAlgorithmTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(ALGORITHM), [])

    def test_it_proliferates_x_times(self):
        grown = Permanent(BEAR, counters={"+1/+1": 1})
        Table(ALGORITHM, "3", mine=[grown, Permanent(OGRE)]).cast()
        self.assertEqual(grown.counters, {"+1/+1": 4})

    def test_x_of_zero_does_nothing(self):
        grown = Permanent(BEAR, counters={"+1/+1": 1})
        Table(ALGORITHM, "0", mine=[grown]).cast()
        self.assertEqual(grown.counters, {"+1/+1": 1})

    def test_a_permanent_without_counters_gets_none(self):
        plain = Permanent(OGRE)
        Table(ALGORITHM, "2", mine=[plain, Permanent(BEAR, counters={"+1/+1": 1})]).cast()
        self.assertEqual(plain.counters, {})

    def test_every_kind_on_a_permanent_grows(self):
        mixed = Permanent(BEAR, counters={"+1/+1": 1, "story": 2})
        Table(ALGORITHM, "1", mine=[mixed]).cast()
        self.assertEqual(mixed.counters, {"+1/+1": 2, "story": 3})

    def test_plus_and_minus_counters_cancel_after_proliferating(self):
        mixed = Permanent(BEAR, counters={"+1/+1": 1, "-1/-1": 2})
        Table(ALGORITHM, "1", mine=[mixed]).cast()
        self.assertEqual({k: v for k, v in mixed.counters.items() if v}, {"-1/-1": 1})  # 2 and 3 cancel to 0 and 1

    def test_x_is_limited_by_the_mana(self):
        t = Table(ALGORITHM, n=4)
        asked = []
        t.game.seats[0].player.policy = lambda prompt, options: (asked.append(list(options)) or 0) if prompt.startswith("Choose X") else 0
        t.game._perform(t.a, CAST + "Expansion Algorithm")
        self.assertEqual(asked[0], ["0", "1", "2"])  # {X}{U}{U} with four lands


INSIGHT = real("Commander's Insight", "{X}{U}{U}{U}", "Instant",
               "Target player draws X cards plus an additional card for each time they've cast a commander from the command zone this game.")


class CommandersInsightTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(INSIGHT), [])

    def test_it_draws_x_plus_one_for_each_commander_cast(self):
        t = Table(INSIGHT, "2", "Player: A", n=8)
        t.a.commander_casts = {"Omnath": 2}
        t.cast()
        self.assertEqual(len(t.a.hand), 4)

    def test_without_commander_casts_it_draws_exactly_x(self):
        t = Table(INSIGHT, "2", "Player: A", n=8).cast()
        self.assertEqual(len(t.a.hand), 2)

    def test_x_of_zero_still_draws_for_the_commander_casts(self):
        t = Table(INSIGHT, "0", "Player: A", n=8)
        t.a.commander_casts = {"Omnath": 3}
        t.cast()
        self.assertEqual(len(t.a.hand), 3)

    def test_it_counts_the_targets_casts_and_not_the_casters(self):
        t = Table(INSIGHT, "1", "Player: B", n=8)
        t.b.commander_casts = {"Omnath": 3}
        t.b.library = [FOREST] * 10
        t.cast()
        self.assertEqual((len(t.b.hand), len(t.a.hand)), (4, 0))


PULL = real("Pull from Tomorrow", "{X}{U}{U}", "Instant", "Draw X cards, then discard a card.")


class PullFromTomorrowTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(PULL), [])

    def test_it_draws_x_then_discards_one(self):
        t = Table(PULL, "3", "Plains", library=[PLAINS, FOREST, FOREST, FOREST, FOREST]).cast()
        self.assertEqual(len(t.a.hand), 2)
        self.assertEqual(sorted(c.name for c in t.a.graveyard), ["Plains", "Pull from Tomorrow"])

    def test_the_discard_comes_after_the_draw(self):
        t = Table(PULL, "1", "Plains", library=[PLAINS, FOREST, FOREST]).cast()
        self.assertEqual(len(t.a.hand), 0)  # the drawn Plains was available to discard

    def test_x_of_zero_discards_a_card_from_hand_if_there_is_one(self):
        t = Table(PULL, "0", "Forest")
        t.a.hand.append(FOREST)
        t.cast()
        self.assertEqual([c.name for c in t.a.hand], [])

    def test_x_of_zero_with_an_empty_hand_discards_nothing(self):
        t = Table(PULL, "0").cast()
        self.assertEqual((t.a.hand, [c.name for c in t.a.graveyard]), ([], ["Pull from Tomorrow"]))


STROKE = real("Stroke of Genius", "{X}{2}{U}", "Instant", "Target player draws X cards.")


class StrokeOfGeniusTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(STROKE), [])

    def test_the_target_player_draws_x_cards(self):
        t = Table(STROKE, "4", "Player: B", n=8)
        t.b.library = [FOREST] * 10
        t.cast()
        self.assertEqual((len(t.b.hand), len(t.a.hand)), (4, 0))

    def test_you_may_target_yourself(self):
        t = Table(STROKE, "3", "Player: A", n=8).cast()
        self.assertEqual(len(t.a.hand), 3)

    def test_x_of_zero_draws_nothing(self):
        t = Table(STROKE, "0", "Player: A").cast()
        self.assertEqual(len(t.a.hand), 0)

    def test_it_costs_x_plus_three(self):
        self.assertFalse(castable(Table(STROKE, n=2)))
        self.assertTrue(castable(Table(STROKE, n=3)))


MIGHT = real("Primal Might", "{X}{G}", "Sorcery",
             "Target creature you control gets +X/+X until end of turn. Then it fights up to one target creature you don't control. (Each "
             "deals damage equal to its power to the other.)")


class PrimalMightTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(MIGHT), [])

    def test_the_pump_makes_it_win_the_fight(self):
        mine = Permanent(BEAR)
        t = Table(MIGHT, "2", "Bear", "Ogre", mine=[mine], theirs=[Permanent(OGRE)]).cast()
        self.assertEqual(battlefield_names(t.b), [])
        self.assertEqual((t.game.power(mine), t.game.toughness(mine), mine.damage), (4, 4, 3))

    def test_x_of_zero_fights_without_a_pump(self):
        mine = Permanent(BEAR)
        t = Table(MIGHT, "0", "Bear", "Ogre", mine=[mine], theirs=[Permanent(OGRE)]).cast()
        self.assertEqual((battlefield_names(t.a), battlefield_names(t.b)), ([], ["Ogre"]))  # a 2/2 loses to a 3/3

    def test_it_may_pump_without_fighting(self):
        mine = Permanent(BEAR)
        t = Table(MIGHT, "3", "Bear", "No target", mine=[mine], theirs=[Permanent(OGRE)]).cast()
        self.assertEqual((t.game.power(mine), mine.damage, battlefield_names(t.b)), (5, 0, ["Ogre"]))

    def test_the_pump_wears_off_at_end_of_turn(self):
        mine = Permanent(BEAR)
        t = Table(MIGHT, "3", "Bear", "No target", mine=[mine], theirs=[Permanent(OGRE)]).cast()
        end_turn(t.game, t.a)
        self.assertEqual(t.game.power(mine), 2)

    def test_it_cannot_fight_a_creature_you_control(self):
        mine, other = Permanent(BEAR), Permanent(OGRE)
        t = Table(MIGHT, "1", "Bear", mine=[mine, other])
        t.cast()
        fight_options = [options for prompt, options in t.a.player.prompts if prompt.startswith("Choose a target")][-1:]
        self.assertTrue(all("Ogre" not in o for opts in fight_options for o in opts))


BIOMASS = real("Biomass Mutation", "{X}{G/U}{G/U}", "Instant", "Creatures you control have base power and toughness X/X until end of turn.")


class BiomassMutationTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(BIOMASS), [])

    def test_every_creature_you_control_becomes_x_x_and_theirs_do_not(self):
        mine = [Permanent(BEAR), Permanent(BIG)]
        theirs = Permanent(OGRE)
        t = Table(BIOMASS, "4", mine=mine, theirs=[theirs]).cast()
        self.assertEqual([(t.game.power(p), t.game.toughness(p)) for p in mine], [(4, 4), (4, 4)])
        self.assertEqual(t.game.power(theirs), 3)

    def test_counters_still_apply_on_top_of_the_base(self):
        grown = Permanent(BEAR, counters={"+1/+1": 2})
        t = Table(BIOMASS, "1", mine=[grown]).cast()
        self.assertEqual(t.game.power(grown), 3)

    def test_x_of_zero_makes_them_zero_zero(self):
        t = Table(BIOMASS, "0", mine=[Permanent(BEAR)]).cast()
        self.assertEqual(battlefield_names(t.a), [])

    def test_it_wears_off_at_end_of_turn(self):
        bear = Permanent(BEAR)
        t = Table(BIOMASS, "4", mine=[bear]).cast()
        end_turn(t.game, t.a)
        self.assertEqual(t.game.power(bear), 2)

    def test_a_noncreature_permanent_is_not_changed(self):
        t = Table(BIOMASS, "4", mine=[Permanent(RELIC)]).cast()
        self.assertEqual(battlefield_names(t.a), ["Relic"])


STAND = real("Tyvar's Stand", "{X}{G}", "Instant",
             "Target creature you control gets +X/+X and gains hexproof and indestructible until end of turn. (It can't be the target of "
             "spells or abilities your opponents control. Damage and effects that say \"destroy\" don't destroy it.)")


class TyvarsStandTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(STAND), [])

    def test_it_pumps_and_protects(self):
        bear = Permanent(BEAR)
        t = Table(STAND, "3", "Bear", mine=[bear]).cast()
        self.assertEqual((t.game.power(bear), t.game.toughness(bear)), (5, 5))
        self.assertTrue(t.game.has_keyword(bear, "hexproof") and t.game.has_keyword(bear, "indestructible"))

    def test_x_of_zero_still_protects(self):
        bear = Permanent(BEAR)
        t = Table(STAND, "0", "Bear", mine=[bear]).cast()
        self.assertEqual(t.game.power(bear), 2)
        self.assertTrue(t.game.has_keyword(bear, "indestructible"))

    def test_it_ends_with_the_turn(self):
        bear = Permanent(BEAR)
        t = Table(STAND, "3", "Bear", mine=[bear]).cast()
        end_turn(t.game, t.a)
        self.assertEqual(t.game.power(bear), 2)
        self.assertFalse(t.game.has_keyword(bear, "hexproof") or t.game.has_keyword(bear, "indestructible"))

    def test_only_the_target_is_changed(self):
        bear, ogre = Permanent(BEAR), Permanent(OGRE)
        t = Table(STAND, "2", "Bear", mine=[bear, ogre]).cast()
        self.assertEqual((t.game.power(ogre), t.game.has_keyword(ogre, "indestructible")), (3, False))


class ImmoralBargainTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(BARGAIN), [])

    def test_it_sacrifices_x_creatures_and_destroys_x_permanents(self):
        mine = [Permanent(BEAR), Permanent(OGRE), Permanent(real("Bird", "{1}", "Creature — Bird", "", "1", "1"))]
        theirs = [Permanent(RELIC), Permanent(BIG), Permanent(SHRINE)]
        t = priority_cast(Table(BARGAIN, CAST, "2", "Relic", "Shrine", "Bear", "Ogre", mine=mine, theirs=theirs))
        self.assertEqual((battlefield_names(t.a), battlefield_names(t.b)), (["Bird"], ["Big"]))

    def test_x_of_zero_does_nothing(self):
        t = priority_cast(Table(BARGAIN, CAST, "0", mine=[Permanent(BEAR)], theirs=[Permanent(RELIC)]))
        self.assertEqual((battlefield_names(t.a), battlefield_names(t.b)), (["Bear"], ["Relic"]))

    def test_x_cannot_exceed_the_creatures_you_can_sacrifice(self):
        t = priority_cast(Table(BARGAIN, CAST, mine=[Permanent(BEAR)], theirs=[Permanent(RELIC), Permanent(SHRINE)]))
        asked = [options for prompt, options in t.a.player.prompts if prompt.startswith("Choose X")]
        self.assertEqual(asked[0], ["0", "1"])

    def test_lands_are_not_targets(self):
        t = priority_cast(Table(BARGAIN, CAST, "1", "Relic", "Bear", mine=[Permanent(BEAR)], theirs=[Permanent(FOREST), Permanent(RELIC)]))
        targets = [options for prompt, options in t.a.player.prompts if prompt.startswith("Choose a target")][0]
        self.assertFalse(any("Forest" in o for o in targets))
        self.assertEqual(battlefield_names(t.b), ["Forest"])
