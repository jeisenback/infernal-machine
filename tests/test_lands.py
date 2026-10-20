import unittest

from infernal_machine.bot import BotPlayer
from infernal_machine.cards import Card, Deck
from infernal_machine.effects import (EntersTapped, cycling, enters_tapped_rule, is_identity_mana_land, mana_ability,
                                      mana_pain)
from infernal_machine.game import CAST, CYCLE, PASS, PLAY_LAND, SHOCK_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import FOREST, lands, pick, table
from tests.test_mass_effects import table3

TEMPLE = Card(name="Temple of Mystery", type_line="Land", produced_mana=("G", "U"),
              oracle_text="This land enters tapped.\nWhen this land enters, scry 1.\n{T}: Add {G} or {U}.")
CHECK = Card(name="Drowned Catacomb", type_line="Land", produced_mana=("U", "B"),
             oracle_text="This land enters tapped unless you control an Island or a Swamp.\n{T}: Add {U} or {B}.")
FAST = Card(name="Blooming Marsh", type_line="Land", produced_mana=("B", "G"),
            oracle_text="This land enters tapped unless you control two or fewer other lands.\n{T}: Add {B} or {G}.")
SLOW = Card(name="Deserted Beach", type_line="Land", produced_mana=("W", "U"),
            oracle_text="This land enters tapped unless you control two or more other lands.\n{T}: Add {W} or {U}.")
BOND = Card(name="Bountiful Promenade", type_line="Land", produced_mana=("G", "W"),
            oracle_text="This land enters tapped unless you have two or more opponents.\n{T}: Add {G} or {W}.")
SHOCK = Card(name="Breeding Pool", type_line="Land — Forest Island", produced_mana=("G", "U"),
             oracle_text="({T}: Add {G} or {U}.)\nAs this land enters, you may pay 2 life. If you don't, it enters tapped.")
PAIN = Card(name="Yavimaya Coast", type_line="Land", produced_mana=("C", "G", "U"),
            oracle_text="{T}: Add {C}.\n{T}: Add {G} or {U}. This land deals 1 damage to you.")
TALISMAN = Card(name="Talisman of Dominance", mana_cost="{2}", type_line="Artifact",
                oracle_text="{T}: Add {C}.\n{T}: Add {U} or {B}. This artifact deals 1 damage to you.")
TOWER = Card(name="Command Tower", type_line="Land", produced_mana=("W", "U", "B", "R", "G"),
             oracle_text="{T}: Add one mana of any color in your commander's color identity.")
TRIOME = Card(name="Indatha Triome", type_line="Land — Plains Swamp Forest", produced_mana=("W", "B", "G"),
              oracle_text="({T}: Add {W}, {B}, or {G}.)\nThis land enters tapped.\nCycling {3}")
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
DUAL = Card(name="Watery Grave", type_line="Land — Island Swamp", produced_mana=("U", "B"))


def spell(cost, name="Spell"):
    return Card(name=name, mana_cost=cost, type_line="Sorcery", oracle_text="Draw a card.")


def enter(game, seat, card):
    permanent = Permanent(card)
    game._enter(seat, permanent)
    return permanent


class ParseTests(unittest.TestCase):
    def test_rules(self):
        self.assertEqual(enters_tapped_rule(TEMPLE), EntersTapped("always"))
        self.assertEqual(enters_tapped_rule(CHECK), EntersTapped("unless_land_types", types=("Island", "Swamp")))
        self.assertEqual(enters_tapped_rule(FAST), EntersTapped("unless_lands_at_most", count=2))
        self.assertEqual(enters_tapped_rule(SLOW), EntersTapped("unless_lands_at_least", count=2))
        self.assertEqual(enters_tapped_rule(BOND), EntersTapped("unless_opponents", count=2))
        self.assertEqual(enters_tapped_rule(SHOCK), EntersTapped("shock", life=2))
        self.assertIsNone(enters_tapped_rule(FOREST))
        self.assertIsNone(enters_tapped_rule(Card(name="x", oracle_text="This land enters tapped unless you control an artifact.")))

    def test_mana_lines(self):
        self.assertEqual(mana_pain(PAIN), (frozenset("GU"), 1))
        self.assertEqual(mana_ability(TALISMAN, frozenset()), [frozenset("CUB")])
        self.assertTrue(is_identity_mana_land(TOWER))
        self.assertEqual((cycling(TRIOME)[1], cycling(FOREST)), ("{3}", None))
        self.assertEqual(cycling(Card(name="x", oracle_text="Cycling\u2014Pay 2 life."))[1:4:2], ("", 2))

    def test_report(self):
        for card in (TEMPLE, CHECK, FAST, SLOW, BOND, SHOCK, PAIN, TALISMAN, TOWER, TRIOME):
            self.assertEqual(unsupported_lines(card), [], card.name)


class EntersTappedTests(unittest.TestCase):
    def test_tapped_land_cannot_pay_until_it_untaps(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [spell("{G}")]
        land = enter(game, seat, TEMPLE)
        self.assertTrue(land.tapped)
        self.assertEqual(game.legal_actions(seat), [PASS])
        game.step = "untap"
        game._turn_based_actions(seat)
        game.step = "main1"
        self.assertIn(CAST + "Spell", game.legal_actions(seat))

    def test_playing_a_temple_enters_tapped_and_scries(self):
        game, players = table3(pick(PLAY_LAND))
        seat = game.seats[0]
        seat.hand = [TEMPLE]
        seat.library = [FOREST] * 5
        game._priority_round(seat)
        self.assertTrue(seat.battlefield[-1].tapped)
        self.assertTrue(any(e["event"] == "scry" for e in players[0].events))

    def test_untapped_basic_lands_are_unaffected(self):
        game, _, _ = table()
        self.assertFalse(enter(game, game.seats[0], FOREST).tapped)

    def test_checkland(self):
        game, _, _ = table()
        seat = game.seats[0]
        self.assertTrue(enter(game, seat, CHECK).tapped)
        seat.battlefield = [Permanent(SWAMP)]
        self.assertFalse(enter(game, seat, CHECK).tapped)
        seat.battlefield = [Permanent(DUAL)]  # a nonbasic Island Swamp counts too
        self.assertFalse(enter(game, seat, CHECK).tapped)
        seat.battlefield = [Permanent(FOREST)]
        self.assertTrue(enter(game, seat, CHECK).tapped)

    def test_fastland_and_slowland_count_other_lands(self):
        for others, fast_tapped, slow_tapped in ((0, False, True), (1, False, True), (2, False, False), (3, True, False)):
            game, _, _ = table()
            seat = game.seats[0]
            seat.battlefield = lands(others)
            self.assertEqual(enter(game, seat, FAST).tapped, fast_tapped, f"fastland with {others} other lands")
            seat.battlefield = lands(others)
            self.assertEqual(enter(game, seat, SLOW).tapped, slow_tapped, f"slowland with {others} other lands")

    def test_bond_land_needs_two_opponents(self):
        game, _, _ = table()
        self.assertTrue(enter(game, game.seats[0], BOND).tapped)  # two players: one opponent
        game, _ = table3()
        self.assertFalse(enter(game, game.seats[0], BOND).tapped)

    def test_shockland_choices(self):
        game, _, _ = table(pick("Pay"))
        self.assertFalse(enter(game, game.seats[0], SHOCK).tapped)
        self.assertEqual(game.seats[0].life, 38)
        game, _, _ = table(pick("Enter"))
        self.assertTrue(enter(game, game.seats[0], SHOCK).tapped)
        self.assertEqual(game.seats[0].life, 40)

    def test_shockland_when_you_cannot_afford_the_life(self):
        game, a, _ = table(pick("Pay"))
        game.seats[0].life = 2
        self.assertTrue(enter(game, game.seats[0], SHOCK).tapped)
        self.assertEqual(game.seats[0].life, 2)
        self.assertFalse(any(SHOCK_PROMPT.matches(prompt) for prompt, _ in a.prompts))

    def test_bot_pays_life_only_while_healthy(self):
        bot = BotPlayer("A", Deck([FOREST], [SHOCK], []))
        bot.notify({"event": "seat", "seat": 0, "name": "A", "life": 40})
        options = ["Pay 2 life", "Enter tapped"]
        self.assertEqual(bot.choose(SHOCK_PROMPT + "Breeding Pool", options), 0)
        bot.notify({"event": "life", "seat": 0, "change": -32, "life": 8})
        self.assertEqual(bot.choose(SHOCK_PROMPT + "Breeding Pool", options), 1)


class CommandTowerTests(unittest.TestCase):
    def test_only_the_commanders_colors(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.color_identity = frozenset("GU")
        seat.battlefield = [Permanent(TOWER)]
        seat.hand = [spell("{U}", "Blue"), spell("{R}", "Red")]
        self.assertEqual(game.legal_actions(seat), [PASS, CAST + "Blue"])

    def test_colorless_commander_means_no_mana(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.battlefield = [Permanent(TOWER)]
        seat.hand = [spell("{1}")]
        self.assertEqual(game.legal_actions(seat), [PASS])


class PainTests(unittest.TestCase):
    def cast(self, battlefield, cost):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.battlefield = battlefield
        seat.hand = [spell(cost)]
        game._priority_round(seat)
        return seat

    def test_painland_hurts_for_colored_mana_only(self):
        self.assertEqual(self.cast([Permanent(PAIN)], "{G}").life, 39)
        self.assertEqual(self.cast([Permanent(PAIN)], "{1}").life, 40)  # pays generic with its colorless mana
        self.assertEqual(self.cast([Permanent(PAIN)], "{C}").life, 40)

    def test_a_painless_source_is_used_first(self):
        self.assertEqual(self.cast([Permanent(PAIN), Permanent(FOREST)], "{G}").life, 40)

    def test_talisman_makes_colored_mana_now_and_hurts_for_it(self):
        self.assertEqual(self.cast([Permanent(TALISMAN)], "{U}").life, 39)
        self.assertEqual(self.cast([Permanent(TALISMAN)], "{1}").life, 40)
        game, _, _ = table()
        game.seats[0].battlefield = [Permanent(TALISMAN)]
        game.seats[0].hand = [spell("{B}")]
        self.assertIn(CAST + "Spell", game.legal_actions(game.seats[0]))

    def test_two_painlands_hurt_twice(self):
        self.assertEqual(self.cast([Permanent(PAIN), Permanent(PAIN)], "{G}{U}").life, 38)


class CyclingTests(unittest.TestCase):
    def test_needs_the_mana(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [TRIOME]
        seat.battlefield = lands(2)
        self.assertEqual(game.legal_actions(seat), [PASS, PLAY_LAND + "Indatha Triome"])
        seat.battlefield = lands(3)
        self.assertIn(CYCLE + "Indatha Triome", game.legal_actions(seat))

    def test_cycling_discards_and_draws_through_the_stack(self):
        game, a, _ = table(pick(CYCLE))
        seat = game.seats[0]
        seat.hand = [TRIOME]
        seat.battlefield = lands(3)
        seat.library = [FOREST, SWAMP]
        game._priority_round(seat)
        self.assertEqual((seat.graveyard, seat.hand), ([TRIOME], [FOREST]))
        events = [e["event"] for e in a.events if e["event"] in ("discard", "activate", "resolve")]
        self.assertEqual(events, ["discard", "activate", "resolve"])

    def test_cycling_works_at_instant_speed_on_another_players_turn(self):
        game, _, _ = table(None, pick(CYCLE))
        game.seats[1].hand = [TRIOME]
        game.seats[1].battlefield = lands(3)
        game.seats[1].library = [FOREST]
        game.step = "end"
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].hand, [FOREST])

    def test_a_cycled_spell_can_be_cycled_too(self):
        card = Card(name="Decree", mana_cost="{4}", type_line="Sorcery", oracle_text="Draw two cards.\nCycling {2}")
        game, _, _ = table(pick(CYCLE))
        game.seats[0].hand = [card]
        game.seats[0].battlefield = lands(2)
        game.seats[0].library = [FOREST, SWAMP]
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].hand, [FOREST])
        self.assertEqual(unsupported_lines(card), [])


if __name__ == "__main__":
    unittest.main()
