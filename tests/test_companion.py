"""Companions: the deck rules, the Companion section of a decklist, and the {3} special action in the game (#365)."""

import dataclasses
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from infernal_machine import companion
from infernal_machine.bot import FEATURES, BotPlayer
from infernal_machine.cards import BulkSource, Card, Deck, load_deck, parse_decklist
from infernal_machine.formats import BRAWL, COMMANDER, DUEL_COMMANDER, STANDARD, deck_problems
from infernal_machine.game import CAST, COMPANION, PASS
from tests.helpers import lands, real, table

REMINDER = " (If this card is your chosen companion, you may put it into your hand from outside the game for {3} as a sorcery.)"


def companion_card(name, condition, cost="{2}", type_line="Legendary Creature — Bear", **more):
    return dataclasses.replace(real(name, cost, type_line, f"Companion — {condition}{REMINDER}", "2", "2"), **more)


LURRUS = companion_card("Lurrus of the Dream-Den", "Each permanent card in your starting deck has mana value 2 or less.", "{1}{W/B}{W/B}")
GYRUDA = companion_card("Gyruda, Doom of Depths", "Your starting deck contains only cards with even mana values.", "{2}{U}{B}")
OBOSH = companion_card("Obosh, the Preypiercer", "Your starting deck contains only cards with odd mana values and land cards.", "{4}{R}")
KERUGA = companion_card("Keruga, the Macrosage", "Your starting deck contains only cards with mana value 3 or greater and land cards.", "{3}{G/U}{G/U}")
LUTRI = companion_card("Lutri, the Spellchaser", "Each nonland card in your starting deck has a different name.", "{R/G}{R/G}")
UMORI = companion_card("Umori, the Collector", "Each nonland card in your starting deck shares a card type.", "{3}{G/U}{G/U}")
JEGANTHA = companion_card("Jegantha, the Wellspring", "No card in your starting deck has more than one of the same mana symbol in its mana cost.", "{2}{R/G}")
KAHEERA = companion_card("Kaheera, the Orphanguard", "Each creature card in your starting deck is a Cat, Elemental, Nightmare, Dinosaur, or Beast card.", "{2}{G}")
YORION = companion_card("Yorion, Sky Nomad", "Your starting deck contains at least twenty cards more than the minimum deck size.", "{3}{W/U}{W/U}")
ZIRDA = companion_card("Zirda, the Dawnwaker", "Each permanent card in your starting deck has an activated ability.", "{1}{R/W}{R/W}")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))


def spell(name, cost, type_line="Creature — Bear", text="", **more):
    return dataclasses.replace(real(name, cost, type_line, text, "1", "1"), **more)


def deck(cards, **more):
    return Deck([], list(cards), [], **more)


def problems(card, cards, **more):
    return companion.companion_problems(deck(cards, companion=card), 60, False, "standard", "Standard", **more)


class ConditionTests(unittest.TestCase):
    def test_the_condition_is_the_companion_line_without_its_reminder(self):
        self.assertEqual(companion.companion_condition(LURRUS), "Each permanent card in your starting deck has mana value 2 or less.")
        self.assertIsNone(companion.companion_condition(spell("Plain", "{1}")))

    def test_all_ten_companions_are_known(self):
        for card in (LURRUS, GYRUDA, OBOSH, KERUGA, LUTRI, UMORI, JEGANTHA, KAHEERA, YORION, ZIRDA):
            self.assertIn(companion.companion_condition(card), companion.CONDITIONS, card.name)

    def test_lurrus_wants_cheap_permanents_and_allows_any_spell(self):
        ok = [spell("One", "{1}"), spell("Bolt", "{4}", "Instant"), FOREST]
        self.assertEqual(problems(LURRUS, ok), [])
        bad = problems(LURRUS, ok + [spell("Big Bear", "{2}{G}", cmc=3.0)])
        self.assertIn("Big Bear", bad[0])

    def test_gyruda_wants_even_mana_values_lands_included(self):
        self.assertEqual(problems(GYRUDA, [spell("Two", "{2}", cmc=2.0), spell("Four", "{4}", cmc=4.0), FOREST]), [])
        self.assertIn("Three", problems(GYRUDA, [spell("Three", "{3}", cmc=3.0)])[0])

    def test_obosh_wants_odd_nonland_cards(self):
        self.assertEqual(problems(OBOSH, [spell("One", "{1}", cmc=1.0), spell("Three", "{3}", cmc=3.0), FOREST]), [])
        bad = problems(OBOSH, [spell("Two", "{2}", cmc=2.0), FOREST])
        self.assertIn("Two", bad[0])
        self.assertNotIn("Forest", bad[0])

    def test_keruga_wants_three_or_more_and_lands(self):
        self.assertEqual(problems(KERUGA, [spell("Three", "{3}", cmc=3.0), FOREST]), [])
        self.assertIn("Two", problems(KERUGA, [spell("Two", "{2}", cmc=2.0)])[0])

    def test_lutri_wants_different_nonland_names(self):
        self.assertEqual(problems(LUTRI, [FOREST, FOREST, spell("A", "{1}"), spell("B", "{1}")]), [])
        self.assertIn("Twin", problems(LUTRI, [spell("Twin", "{1}"), spell("Twin", "{1}")])[0])

    def test_umori_wants_a_card_type_every_nonland_card_shares(self):
        self.assertEqual(problems(UMORI, [spell("A", "{1}", "Artifact Creature — Golem"), spell("B", "{1}", "Creature — Bear"), FOREST]), [])
        self.assertIn("shared", problems(UMORI, [spell("A", "{1}", "Artifact"), spell("B", "{1}", "Creature — Bear")])[0])

    def test_jegantha_wants_no_repeated_mana_symbol(self):
        self.assertEqual(problems(JEGANTHA, [spell("A", "{1}{R}{G}"), spell("B", "{2}{W}")]), [])
        self.assertIn("Double", problems(JEGANTHA, [spell("Double", "{R}{R}")])[0])
        self.assertIn("Doubled Generic", problems(JEGANTHA, [spell("Doubled Generic", "{1}{1}")])[0])

    def test_kaheera_wants_listed_creature_types(self):
        self.assertEqual(problems(KAHEERA, [spell("Cat", "{1}", "Creature — Cat"), spell("Dino", "{1}", "Creature — Dinosaur Beast"), spell("Bolt", "{1}", "Instant")]), [])
        self.assertIn("Bear", problems(KAHEERA, [spell("Bear", "{1}", "Creature — Bear")])[0])

    def test_yorion_wants_twenty_more_than_the_minimum(self):
        self.assertEqual(problems(YORION, [FOREST] * 80), [])
        self.assertIn("79 cards, needs 80", problems(YORION, [FOREST] * 79)[0])

    def test_zirda_wants_activated_abilities_on_permanents(self):
        tap = spell("Tapper", "{1}", text="{T}: Draw a card.")
        quoted = spell("Gives", "{1}", text='Creatures you control have "{T}: Add {G}."')
        self.assertEqual(problems(ZIRDA, [tap, FOREST, spell("Bolt", "{1}", "Instant")]), [])
        self.assertIn("Gives", problems(ZIRDA, [quoted])[0], "an ability in quotation marks is the creature's it gives, not this card's")
        self.assertIn("Vanilla", problems(ZIRDA, [spell("Vanilla", "{1}")])[0])

    def test_a_card_without_the_ability_and_a_condition_not_known(self):
        self.assertEqual(problems(spell("Plain", "{1}"), [FOREST]), ["Plain doesn't have the companion ability"])
        odd = companion_card("Odd Companion", "Your starting deck contains only blue cards.")
        self.assertIn("does not check its companion condition", problems(odd, [FOREST])[0])

    def test_no_companion_no_problem(self):
        self.assertEqual(companion.companion_problems(deck([FOREST]), 60, False, "standard", "Standard"), [])

    def test_the_commanders_are_part_of_the_starting_deck(self):
        d = Deck([spell("Heavy Boss", "{5}", "Legendary Creature — Elf", cmc=5.0)], [FOREST] * 99, [], companion=LURRUS)
        self.assertIn("Heavy Boss", companion.companion_problems(d, 100, True, "commander", "Commander")[0])


class FormatRuleTests(unittest.TestCase):
    def commander_deck(self, card, size=100):
        return Deck([BOSS], [FOREST] * (size - 1), [], companion=card)

    def test_in_a_commander_format_it_must_fit_the_commanders_colors_and_not_be_in_the_deck(self):
        green = dataclasses.replace(KERUGA, color_identity=("G",))
        self.assertEqual(deck_problems(self.commander_deck(green), COMMANDER), [])
        red = dataclasses.replace(LUTRI, color_identity=("R",))
        self.assertTrue(any("outside the commander's color identity" in p for p in deck_problems(self.commander_deck(red), COMMANDER)))
        twice = Deck([BOSS], [dataclasses.replace(green)] + [FOREST] * 98, [], companion=green)
        self.assertTrue(any("singleton" in p for p in deck_problems(twice, COMMANDER)))

    def test_it_must_be_legal_in_the_format(self):
        banned = dataclasses.replace(KERUGA, color_identity=("G",), legal=("commander",))
        self.assertEqual(deck_problems(self.commander_deck(banned), COMMANDER), [])
        self.assertIn("Keruga, the Macrosage is not legal in Duel Commander", deck_problems(self.commander_deck(banned), DUEL_COMMANDER))

    def test_it_is_not_counted_in_the_hundred(self):
        green = dataclasses.replace(KERUGA, color_identity=("G",))
        self.assertEqual(deck_problems(self.commander_deck(green, 100), COMMANDER), [])
        self.assertTrue(any("needs exactly 100" in p for p in deck_problems(self.commander_deck(green, 101), COMMANDER)))
        brawl = self.commander_deck(dataclasses.replace(GYRUDA, color_identity=("G",)), 60)
        self.assertEqual([p for p in deck_problems(brawl, BRAWL) if "companion" in p], [], "a Brawl deck's 60 are not counting the companion either")

    def test_yorion_cannot_be_played_in_commander(self):
        problems_ = deck_problems(self.commander_deck(dataclasses.replace(YORION, color_identity=("G",))), COMMANDER)
        self.assertTrue(any("100 cards, needs 120" in p for p in problems_), problems_)

    def test_in_standard_it_is_one_of_the_sidebars_fifteen_and_counts_for_the_copies(self):
        d = Deck([], [FOREST] * 60, [FOREST] * 14, companion=GYRUDA)
        self.assertFalse(any("Sideboard" in p for p in deck_problems(d, STANDARD)), "fifteen with the companion")
        d = Deck([], [FOREST] * 60, [FOREST] * 15, companion=GYRUDA)
        self.assertTrue(any("Sideboard has 16 cards (with the companion)" in p for p in deck_problems(d, STANDARD)))
        d = Deck([], [FOREST] * 56 + [GYRUDA] * 4, [], companion=GYRUDA)
        self.assertTrue(any("5 copies, limit is 4" in p for p in deck_problems(d, STANDARD)))

    def test_the_standard_condition_is_checked_against_the_main_deck(self):
        d = Deck([], [FOREST] * 59 + [spell("Three", "{3}", cmc=3.0)], [], companion=GYRUDA)
        self.assertTrue(any("companion condition" in p for p in deck_problems(d, STANDARD)))


class DecklistTests(unittest.TestCase):
    def test_a_companion_section_is_kept_apart(self):
        parsed = parse_decklist("Companion\n1 Lurrus of the Dream-Den\n\nDeck\n4 Forest\n\nSideboard\n1 Forest\n")
        self.assertEqual(parsed.companion, {"Lurrus of the Dream-Den": 1})
        self.assertEqual((parsed.main, parsed.sideboard), ({"Forest": 4}, {"Forest": 1}))

    def test_load_deck_gives_the_card_and_refuses_two(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "bulk.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in (FOREST, LURRUS, GYRUDA)}}, f)
            source = BulkSource(path)
            loaded = load_deck("Companion\n1 Lurrus of the Dream-Den\n\nDeck\n4 Forest\n", source)
            self.assertEqual(loaded.companion.name, "Lurrus of the Dream-Den")
            self.assertEqual(len(loaded.main), 4)
            self.assertIsNone(load_deck("Deck\n4 Forest\n", source).companion)
            with self.assertRaises(ValueError):
                load_deck("Companion\n1 Lurrus of the Dream-Den\n1 Gyruda, Doom of Depths\n\nDeck\n4 Forest\n", source)


class GameTests(unittest.TestCase):
    def setup_game(self, mana=3, policy=None):
        game, a, b = table(policy)
        seat = game.seats[0]
        seat.companion = LURRUS
        seat.battlefield = lands(mana)
        return game, seat

    def test_it_is_offered_at_sorcery_timing_with_three_mana(self):
        game, seat = self.setup_game()
        self.assertIn(COMPANION + "Lurrus of the Dream-Den", game.legal_actions(seat))

    def test_not_without_three_mana(self):
        game, seat = self.setup_game(mana=2)
        self.assertFalse(any(a.startswith(COMPANION) for a in game.legal_actions(seat)))

    def test_not_on_the_other_players_turn_outside_a_main_phase_or_with_something_on_the_stack(self):
        game, seat = self.setup_game()
        game.active = 1
        self.assertFalse(any(a.startswith(COMPANION) for a in game.legal_actions(seat)))
        game.active, game.step = 0, "combat"
        self.assertFalse(any(a.startswith(COMPANION) for a in game.legal_actions(seat)))
        game.step = "main1"
        game.stack.append(SimpleNamespace(ability=object(), card=None))
        self.assertFalse(any(a.startswith(COMPANION) for a in game.legal_actions(seat)))

    def test_not_for_a_seat_with_no_companion(self):
        game, seat = self.setup_game()
        seat.companion = None
        self.assertFalse(any(a.startswith(COMPANION) for a in game.legal_actions(seat)))

    def test_taking_it_pays_three_puts_it_in_hand_and_cannot_be_done_twice(self):
        game, seat = self.setup_game(mana=6)
        events = []
        forward = game.broadcast
        game.broadcast = lambda event, skip=None: (events.append(event), forward(event, skip))[1]  # type: ignore[method-assign]
        game._perform(seat, COMPANION + "Lurrus of the Dream-Den")
        self.assertEqual([c.name for c in seat.hand], ["Lurrus of the Dream-Den"])
        self.assertTrue(seat.companion_used)
        self.assertEqual(sum(p.tapped for p in seat.battlefield), 3, "{3} was paid")
        self.assertIn({"event": "companion", "seat": 0, "card": "Lurrus of the Dream-Den"}, events)
        self.assertFalse(any(a.startswith(COMPANION) for a in game.legal_actions(seat)), "once per game")

    def test_once_in_hand_it_is_cast_like_any_card(self):
        game, seat = self.setup_game(mana=6)
        seat.companion = dataclasses.replace(LURRUS, mana_cost="{1}", cmc=1.0, oracle_text=LURRUS.oracle_text)
        game._perform(seat, COMPANION + "Lurrus of the Dream-Den")
        self.assertIn(CAST + "Lurrus of the Dream-Den", game.legal_actions(seat))

    def test_the_board_shows_whether_it_is_still_outside(self):
        game, seat = self.setup_game(mana=6)
        self.assertEqual(game.snapshot(seat)["seats"][0]["companion"], "Lurrus of the Dream-Den")
        game._perform(seat, COMPANION + "Lurrus of the Dream-Den")
        self.assertIsNone(game.snapshot(seat)["seats"][0]["companion"])

    def test_a_seat_starts_with_its_decks_companion(self):
        from infernal_machine.game import Game
        from tests.helpers import ScriptedPlayer
        d = Deck([BOSS], [FOREST] * 20, [], companion=LURRUS)
        game = Game([(ScriptedPlayer("A"), d), (ScriptedPlayer("B"), Deck([BOSS], [FOREST] * 20, []))], seed=1)
        self.assertEqual([s.companion.name if s.companion else None for s in game.seats], ["Lurrus of the Dream-Den", None])


class BotTests(unittest.TestCase):
    def bot(self):
        b = BotPlayer("Bot", Deck([], [FOREST, spell("Bear", "{1}")], []), features=FEATURES)
        b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 20})
        b.notify({"event": "state", "hand": [], "seats": [
            {"seat": 0, "lost": False, "life": 20, "mana_pool": [], "battlefield": [], "command_zone": []},
            {"seat": 1, "lost": False, "life": 20, "mana_pool": [], "battlefield": [], "command_zone": []}]})
        return b

    def test_with_nothing_else_to_do_it_takes_the_companion(self):
        options = [PASS, COMPANION + "Lurrus of the Dream-Den"]
        self.assertEqual(self.bot().choose("Priority: main1", options), 1)

    def test_it_casts_first_and_takes_the_companion_after(self):
        options = [PASS, COMPANION + "Lurrus of the Dream-Den", CAST + "Bear"]
        self.assertEqual(self.bot().choose("Priority: main1", options), 2)

    def test_no_companion_option_is_a_pass(self):
        self.assertEqual(self.bot().choose("Priority: main1", [PASS]), 0)


if __name__ == "__main__":
    unittest.main()
