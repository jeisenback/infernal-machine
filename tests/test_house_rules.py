"""House rules: play cards a format does not allow, named or every banned one, and say so in the output (#528)."""

import argparse
import contextlib
import dataclasses
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from infernal_machine import analyze, compare, impact, matchup
from infernal_machine.cards import BulkSource, Card, Deck
from infernal_machine.formats import (COMMANDER, NO_HOUSE_RULES, OATHBREAKER, STANDARD, HouseRules, add_format_argument, deck_problems,
                                      house_rules)
from infernal_machine.server import DeckRejected, load_human_deck
from infernal_machine.tune import candidate_problem, main as tune_main
from tests.helpers import FakeSource

LEGALITIES = {"commander": "banned", "duel": "banned", "oathbreaker": "banned", "legacy": "banned", "vintage": "restricted",
              "standard": "not_legal", "modern": "not_legal"}  # Mana Crypt's, as Scryfall gives them
MANA_CRYPT = Card.from_scryfall({"name": "Mana Crypt", "mana_cost": "{0}", "cmc": 0, "type_line": "Artifact", "legalities": LEGALITIES,
                                 "oracle_text": "At the beginning of your upkeep, flip a coin. If you lose the flip, this artifact deals 3 damage "
                                                "to you.\n{T}: Add {C}{C}."})
SILVER = Card.from_scryfall({"name": "Silver Card", "mana_cost": "{1}", "cmc": 1, "type_line": "Artifact", "oracle_text": "",
                             "legalities": {"commander": "not_legal", "vintage": "not_legal"}})  # outside every pool, banned nowhere
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Cub", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))
RED = Card(name="Red Crypt", mana_cost="{R}", cmc=1, type_line="Artifact", color_identity=("R",), legal=(), banned=("commander",))
WALKER = Card(name="Walker", mana_cost="{2}{G}", cmc=3, type_line="Legendary Planeswalker — Test", loyalty="3", color_identity=("G",))
SPELL = Card(name="Sig", mana_cost="{G}", cmc=1, type_line="Instant", oracle_text="Draw a card.", color_identity=("G",))


def commander(*extras):
    return Deck([BOSS], [*extras, BEAR, *[FOREST] * (98 - len(extras))], [])


class CardTests(unittest.TestCase):
    def test_scryfalls_banned_formats_are_kept_apart_from_the_ones_a_card_is_outside(self):
        self.assertEqual(MANA_CRYPT.banned, ("commander", "duel", "legacy", "oathbreaker"))
        self.assertEqual(SILVER.banned, ())
        again = Card.from_dict(json.loads(json.dumps(MANA_CRYPT.to_dict())))
        self.assertEqual(again.banned, MANA_CRYPT.banned)


class DeckCheckTests(unittest.TestCase):
    def test_a_named_card_is_not_reported_for_its_legality(self):
        self.assertEqual(deck_problems(commander(MANA_CRYPT), COMMANDER), ["Mana Crypt is not legal in Commander"])
        self.assertEqual(deck_problems(commander(MANA_CRYPT), COMMANDER, HouseRules(frozenset({"Mana Crypt"}))), [])

    def test_allow_banned_lets_in_a_banned_card_and_not_one_outside_the_pool(self):
        rules = HouseRules(banned=True)
        self.assertEqual(deck_problems(commander(MANA_CRYPT), COMMANDER, rules), [])
        self.assertEqual(deck_problems(commander(SILVER), COMMANDER, rules), ["Silver Card is not legal in Commander"])
        self.assertEqual(deck_problems(commander(SILVER), COMMANDER, HouseRules(frozenset({"Silver Card"}))), [], "named, it plays")

    def test_the_other_rules_still_hold(self):
        rules = HouseRules(frozenset({"Mana Crypt", "Red Crypt"}))
        self.assertEqual(deck_problems(commander(MANA_CRYPT, MANA_CRYPT), COMMANDER, rules), ["Mana Crypt: 2 copies, limit is 1"])
        self.assertEqual(deck_problems(commander(RED), COMMANDER, rules), ["Red Crypt is outside the commander's color identity (R)"])

    def test_every_format_takes_them(self):
        rotated = dataclasses.replace(BEAR, name="Old Cub", legal=("commander",), banned=())
        standard = Deck([], [rotated, *[FOREST] * 59], [])
        self.assertEqual(deck_problems(standard, STANDARD), ["Old Cub is not legal in Standard"])
        self.assertEqual(deck_problems(standard, STANDARD, HouseRules(frozenset({"Old Cub"}))), [])
        oath = Deck([WALKER], [MANA_CRYPT, *[FOREST] * 57], [], signature_spell=SPELL)
        self.assertEqual(deck_problems(oath, OATHBREAKER), ["Mana Crypt is not legal in Oathbreaker"])
        self.assertEqual(deck_problems(oath, OATHBREAKER, HouseRules(banned=True)), [])

    def test_a_companion_is_let_in_the_same_way(self):
        lurrus = Card.from_scryfall({"name": "Lurrus of the Dream-Den", "mana_cost": "{1}{W/B}{W/B}", "cmc": 3,
                                     "type_line": "Legendary Creature — Cat Nightmare", "power": "3", "toughness": "2",
                                     "color_identity": ["W", "B"], "legalities": {"commander": "banned", "legacy": "banned"},
                                     "oracle_text": "Companion — Each permanent card in your starting deck has mana value 2 or less.\nLifelink"})
        small = Card(name="Small Boss", mana_cost="{W}{B}", cmc=2, type_line="Legendary Creature — Elf", power="2", toughness="2",
                     color_identity=("W", "B"))
        plains = Card(name="Plains", type_line="Basic Land — Plains", produced_mana=("W",))
        deck = Deck([small], [plains] * 99, [], companion=lurrus)  # the companion check is the only one that sees it here
        self.assertEqual(deck_problems(deck, COMMANDER), ["Lurrus of the Dream-Den is not legal in Commander"])
        self.assertEqual(deck_problems(deck, COMMANDER, HouseRules(banned=True)), [])


class CommandLineTests(unittest.TestCase):
    def test_the_flags_ride_on_format_and_take_repeats_and_comma_lists(self):
        parser = argparse.ArgumentParser()
        add_format_argument(parser)
        args = parser.parse_args(["--allow", "Mana Crypt, Black Lotus", "--allow", "Dockside Extortionist", "--allow-banned"])
        self.assertEqual(house_rules(args), HouseRules(frozenset({"Mana Crypt", "Black Lotus", "Dockside Extortionist"}), True))
        self.assertEqual(house_rules(parser.parse_args([])), NO_HOUSE_RULES)

    def test_the_note_names_the_cards_it_let_in(self):
        rules = HouseRules(frozenset({"Mana Crypt", "Cub"}))  # (a legal card named is not one it let in)
        self.assertEqual(rules.note([commander(MANA_CRYPT)], COMMANDER),
                         "Includes cards not legal in Commander, played under house rules: Mana Crypt.")
        self.assertEqual(rules.note([commander()], COMMANDER), "")
        self.assertEqual(NO_HOUSE_RULES.note([commander(MANA_CRYPT)], COMMANDER), "", "no house rules, nothing let in")

    def test_every_tool_that_takes_format_says_so(self):
        quick = ["--games", "2", "--workers", "1", "--max-turns", "10"]
        tools = {
            "matchup": lambda deck, bulk: matchup.main(["tool", deck, deck, *quick, "--bulk", bulk, "--allow", "Mana Crypt"]),
            "compare": lambda deck, bulk: compare.main(["tool", deck, deck, deck, *quick, "--goldfish-games", "0", "--bulk", bulk,
                                                        "--allow", "Mana Crypt"]),
            "impact": lambda deck, bulk: impact.main([deck, deck, *quick, "--cards", "Cub", "--goldfish-games", "4", "--bulk", bulk,
                                                      "--allow-banned"]),
            "analyze": lambda deck, bulk: analyze.main([deck, deck, "--games", "2", "--sim-games", "4", "--turns", "2", "--workers", "1",
                                                        "--skip", "bracket,combos,goldfish,tuning,matchups", "--bulk", bulk,
                                                        "--allow", "Mana Crypt"]),
        }
        with tempfile.TemporaryDirectory() as d:
            bulk = os.path.join(d, "bulk.json")
            with open(bulk, "w", encoding="utf-8") as f:
                json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in (FOREST, BOSS, BEAR, MANA_CRYPT)}}, f)
            deck = os.path.join(d, "deck.txt")
            Path(deck).write_text("Commander\n1 Boss\n\nDeck\n1 Mana Crypt\n1 Cub\n97 Forest\n", encoding="utf-8")
            for name, run in tools.items():
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(run(deck, bulk), 0, name)
                self.assertIn("Includes cards not legal in Commander, played under house rules: Mana Crypt.", out.getvalue(), name)


class ServerTests(unittest.TestCase):
    def test_a_human_deck_is_checked_with_the_house_rules(self):
        source = FakeSource(BOSS, FOREST, BEAR, MANA_CRYPT)
        hello = {"deck": "Commander\n1 Boss\n\nDeck\n1 Mana Crypt\n1 Cub\n97 Forest\n"}
        with self.assertRaises(DeckRejected):
            load_human_deck(hello, source, True, COMMANDER)
        self.assertEqual(len(load_human_deck(hello, source, True, COMMANDER, HouseRules(banned=True)).main), 99)


class TuneTests(unittest.TestCase):
    def test_a_candidate_the_house_rules_let_in_is_tried(self):
        deck = commander()
        self.assertEqual(candidate_problem(deck, MANA_CRYPT), "not legal in Commander")
        self.assertIsNone(candidate_problem(deck, MANA_CRYPT, HouseRules(frozenset({"Mana Crypt"}))))
        self.assertIsNone(candidate_problem(deck, MANA_CRYPT, HouseRules(banned=True)))
        self.assertEqual(candidate_problem(deck, SILVER, HouseRules(banned=True)), "not legal in Commander")
        self.assertIn("outside the commander's color identity", candidate_problem(deck, RED, HouseRules(frozenset({"Red Crypt"}))) or "")
        rotated = dataclasses.replace(BEAR, name="Old Cub", legal=("commander",))
        self.assertEqual(candidate_problem(Deck([], [FOREST] * 60, []), rotated), "not legal in Standard")
        self.assertIsNone(candidate_problem(Deck([], [FOREST] * 60, []), rotated, HouseRules(frozenset({"Old Cub"}))))

    def test_the_command_line_says_so(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "deck.txt")
            Path(path).write_text("Commander\n1 Boss\n\nDeck\n1 Cub\n98 Forest\n", encoding="utf-8")
            for options, expected in ((["--try", "Mana Crypt"], False), (["--try", "Mana Crypt", "--allow-banned"], True)):
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(tune_main(["tune", path, "--games", "4", "--turns", "2", *options],
                                               source=FakeSource(BOSS, FOREST, BEAR, MANA_CRYPT)), 0)
                self.assertEqual("played under house rules: Mana Crypt." in out.getvalue(), expected, options)


if __name__ == "__main__":
    unittest.main()
