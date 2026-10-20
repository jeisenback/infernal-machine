import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (Damage, Destroy, Draw, Drain, EachMayWheel, EachPlayerLosesLife, MayDiscardThenDraw,
                                      TapOrUntap, TargetDrawLose, YouAndTargetDraw, spell_effects)
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.helpers import BEAR, pick, table3


def spell(name, text, kind="Sorcery"):
    return Card(name=name, mana_cost="{1}", type_line=kind, oracle_text=text)


CRAVING = spell("Ancestral Craving", "Target player draws three cards and loses 3 life.")
RENDEZVOUS = spell("Secret Rendezvous", "You and target opponent each draw three cards.")
EDIT = spell("Vandal's Edit", "Draw two cards. Each player loses 2 life.")
VERSE = REAL["Hallway Heckler // Vicious Verse"].prepare  # the spell half
VOLLEY = spell("Rocket Volley", "Destroy target nonbasic land.")
ACT = spell("Improvised Act", "You may discard a card. If you do, draw a card.")
REJOINDER = REAL["Elite Interceptor // Rejoinder"].prepare
FORTUNE = spell("Arc of Fortune", "Each player may discard their hand and draw seven cards.")
SANGUINE = spell("Exsanguinate", "Each opponent loses X life. You gain life equal to the life lost this way.")
STRAY = spell("Stray", "You gain life equal to the life lost this way.")
HALF_A_LOOT = spell("Half", "You may discard a card.")
TOWER = REAL["Reliquary Tower"]
BASIC = Card(name="Forest", type_line="Basic Land — Forest")
PORT = Card(name="Rugged Port", type_line="Land", oracle_text="{T}: Add {C}.")


class ParseTests(unittest.TestCase):
    def test_templates(self):
        self.assertEqual(spell_effects(CRAVING), [TargetDrawLose(3, 3, "player")])
        self.assertEqual(spell_effects(RENDEZVOUS), [YouAndTargetDraw(3)])
        self.assertEqual(spell_effects(VERSE), [Damage(1, "opponent")])
        self.assertEqual(spell_effects(VOLLEY), [Destroy("nonbasic land")])
        self.assertEqual(spell_effects(ACT), [MayDiscardThenDraw()])
        self.assertEqual(spell_effects(REJOINDER), [TapOrUntap(), Draw(1)])
        self.assertEqual(spell_effects(FORTUNE), [EachMayWheel(7)])
        self.assertEqual(spell_effects(SANGUINE), [Drain("X")])
        self.assertEqual(spell_effects(EDIT)[1], EachPlayerLosesLife(2))

    def test_half_of_a_two_sentence_effect_is_not_understood(self):
        self.assertIsNone(spell_effects(STRAY))
        self.assertIsNone(spell_effects(HALF_A_LOOT))

    def test_the_report_understands_them(self):
        for card in (CRAVING, RENDEZVOUS, EDIT, VERSE, VOLLEY, ACT, REJOINDER, FORTUNE, SANGUINE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class ResolveTests(unittest.TestCase):
    def test_draw_and_lose(self):
        game, _ = table3()
        a, b, _ = game.seats
        b.library = [BEAR] * 5
        TargetDrawLose(3, 3).resolve(game, a, b)
        self.assertEqual((len(b.hand), b.life), (3, 37))

    def test_you_and_target_opponent_draw(self):
        game, _ = table3()
        a, b, c = game.seats
        a.library, b.library = [BEAR] * 5, [BEAR] * 5
        YouAndTargetDraw(3).resolve(game, a, b)
        self.assertEqual((len(a.hand), len(b.hand), len(c.hand)), (3, 3, 0))

    def test_each_player_loses_life(self):
        game, _ = table3()
        EachPlayerLosesLife(2).resolve(game, game.seats[0], None)
        self.assertEqual([s.life for s in game.seats], [38, 38, 38])

    def test_drain_gains_what_the_opponents_lost(self):
        game, _ = table3()
        a, b, c = game.seats
        game.x_value = 3
        Drain("X").resolve(game, a, None)
        self.assertEqual((a.life, b.life, c.life), (46, 37, 37))

    def test_loot_discards_then_draws(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.library, a.hand = [PORT] * 3, [BEAR]
        MayDiscardThenDraw().resolve(game, a, None)
        self.assertEqual(([c.name for c in a.hand], [c.name for c in a.graveyard]), (["Rugged Port"], ["Bear"]))

    def test_declining_the_loot_does_nothing(self):
        game, _ = table3(pick("No"))
        a = game.seats[0]
        a.library, a.hand = [PORT] * 3, [BEAR]
        MayDiscardThenDraw().resolve(game, a, None)
        self.assertEqual(([c.name for c in a.hand], a.graveyard), (["Bear"], []))

    def test_no_loot_with_an_empty_hand(self):
        game, _ = table3(pick("Yes"))
        a = game.seats[0]
        a.library = [PORT] * 3
        MayDiscardThenDraw().resolve(game, a, None)
        self.assertEqual(a.hand, [])

    def test_each_player_may_wheel(self):
        game, _ = table3(pick("Yes"), pick("No"), pick("Yes"))
        a, b, c = game.seats
        for seat in game.seats:
            seat.library, seat.hand = [PORT] * 9, [BEAR]
        EachMayWheel(7).resolve(game, a, None)
        self.assertEqual((len(a.hand), len(b.hand), len(c.hand)), (7, 1, 7))
        self.assertEqual(b.hand[0].name, "Bear")

    def test_tap_or_untap(self):
        for choice, before, after in (("Tap", False, True), ("Untap", True, False), ("Neither", True, True)):
            game, _ = table3(pick(choice))
            a = game.seats[0]
            bear = Permanent(BEAR, tapped=before)
            a.battlefield = [bear]
            TapOrUntap().resolve(game, a, bear)
            self.assertEqual(bear.tapped, after, choice)

    def test_nonbasic_land_is_a_legal_target_only_for_nonbasic_lands(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(BASIC), Permanent(TOWER)]
        options = [option.card.name for _, option in game.target_options("nonbasic land", a)]
        self.assertEqual(options, ["Reliquary Tower"])


if __name__ == "__main__":
    unittest.main()
