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

    def test_an_opponents_commander_is_not_affected(self):
        game = self.table()
        theirs = Permanent(OGRE)
        game.seats[1].battlefield = [theirs]
        game.seats[1].commander_names = {"Ogre"}
        self.assertEqual(game.power(theirs), 3)
