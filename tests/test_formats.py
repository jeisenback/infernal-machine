"""The commander formats beyond Commander: Brawl and Duel Commander (#365)."""

import contextlib
import dataclasses
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from infernal_machine import commander, matchup
from infernal_machine.bot import BotPlayer
from infernal_machine.cards import CARD_FORMAT, BulkSource, Card, Deck
from infernal_machine.combat import ATTACK_PROMPT
from infernal_machine.formats import BRAWL, COMMANDER, DUEL_COMMANDER, FORMATS, STANDARD, deck_problems, format_of, with_format
from infernal_machine.game import Game
from tests.helpers import ScriptedPlayer, real

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))
WALKER = Card(name="Gideon Lite", mana_cost="{2}{G}", cmc=3, type_line="Legendary Planeswalker — Gideon", loyalty="3", color_identity=("G",))
PLAIN_WALKER = Card(name="Plain Walker", mana_cost="{2}{G}", cmc=3, type_line="Planeswalker — Jace", loyalty="3", color_identity=("G",))
BEAR = real("Cub", "{1}{G}", "Creature — Bear", "", "2", "2")
GREEN_BEAR = dataclasses.replace(BEAR, color_identity=("G",))
RED_BEAR = dataclasses.replace(BEAR, name="Red Cub", color_identity=("R",))


def commander_deck(size, commander_card=BOSS, extra=(), fmt=""):
    spells = [GREEN_BEAR] + list(extra)
    return Deck([commander_card], spells + [FOREST] * (size - 1 - len(spells)), [], format=fmt)


class FormatTests(unittest.TestCase):
    def test_the_numbers_of_each_format(self):
        self.assertEqual((COMMANDER.life, COMMANDER.min_deck, COMMANDER.commander_damage), (40, 100, 21))
        self.assertEqual((STANDARD.life, STANDARD.min_deck, STANDARD.commander), (20, 60, False))
        self.assertEqual((BRAWL.life, BRAWL.min_deck, BRAWL.commander_damage, BRAWL.multiplayer_life), (25, 60, 21, 30))
        self.assertEqual((DUEL_COMMANDER.life, DUEL_COMMANDER.min_deck, DUEL_COMMANDER.commander_damage), (20, 100, 15))
        self.assertEqual(sorted(FORMATS), ["brawl", "commander", "duel", "oathbreaker", "standard"])

    def test_brawl_has_more_life_with_more_players(self):
        self.assertEqual([BRAWL.starting_life(n) for n in (2, 3, 4)], [25, 30, 30])
        self.assertEqual([COMMANDER.starting_life(n) for n in (2, 4)], [40, 40])
        self.assertEqual(DUEL_COMMANDER.starting_life(2), 20)

    def test_the_names_are_written_out(self):
        self.assertEqual([FORMATS[n].label for n in ("commander", "standard", "brawl", "duel")], ["Commander", "Standard", "Brawl", "Duel Commander"])


class FormatOfTests(unittest.TestCase):
    def test_a_deck_with_no_name_is_commander_or_standard_by_its_shape(self):
        self.assertIs(format_of([commander_deck(100), commander_deck(100)]), COMMANDER)
        self.assertIs(format_of([Deck([], [FOREST] * 60, [])]), STANDARD)
        self.assertIs(format_of([commander_deck(60)]), COMMANDER, "a 60-card commander deck is not taken for Brawl: it has to be asked for")

    def test_a_deck_names_its_format(self):
        for name, expected in (("brawl", BRAWL), ("duel", DUEL_COMMANDER), ("commander", COMMANDER)):
            self.assertIs(format_of([commander_deck(60, fmt=name), commander_deck(60, fmt=name)]), expected)
        self.assertIs(format_of([Deck([], [FOREST] * 60, [], format="standard")]), STANDARD)

    def test_one_named_deck_sets_the_table(self):
        self.assertIs(format_of([commander_deck(60, fmt="brawl"), commander_deck(60)]), BRAWL)

    def test_formats_cannot_be_mixed(self):
        with self.assertRaises(ValueError) as caught:
            format_of([commander_deck(60, fmt="brawl"), commander_deck(100, fmt="duel")])
        self.assertIn("can't mix formats", str(caught.exception))

    def test_a_deck_must_suit_its_format(self):
        with self.assertRaises(ValueError) as caught:
            format_of([Deck([], [FOREST] * 60, [], format="brawl")])
        self.assertIn("Brawl decks have a commander", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            format_of([commander_deck(60, fmt="standard")])
        self.assertIn("Standard decks have no commander", str(caught.exception))

    def test_an_unknown_format_is_an_error(self):
        with self.assertRaises(ValueError):
            format_of([commander_deck(60, fmt="pauper")])
        with self.assertRaises(ValueError):
            with_format(commander_deck(60), "pauper")

    def test_with_format(self):
        deck = commander_deck(60)
        self.assertIs(with_format(deck, None), deck)
        self.assertIs(with_format(deck, ""), deck)
        self.assertEqual(with_format(deck, "brawl").format, "brawl")
        self.assertEqual(deck.format, "", "the deck itself is not changed")


class DeckRulesTests(unittest.TestCase):
    def test_a_legal_brawl_deck(self):
        self.assertEqual(deck_problems(commander_deck(60), BRAWL), [])

    def test_brawl_needs_exactly_sixty_cards(self):
        self.assertIn("needs exactly 60", " ".join(deck_problems(commander_deck(59), BRAWL)))
        self.assertIn("needs exactly 60", " ".join(deck_problems(commander_deck(100), BRAWL)))

    def test_a_planeswalker_can_lead_a_brawl_deck_and_not_a_commander_deck(self):
        self.assertEqual(deck_problems(commander_deck(60, WALKER), BRAWL), [])
        self.assertIn("Gideon Lite can't be your commander", deck_problems(commander_deck(100, WALKER), COMMANDER))
        self.assertIn("Plain Walker can't be your commander", deck_problems(commander_deck(60, PLAIN_WALKER), BRAWL), "it must be legendary")

    def test_brawl_cards_must_be_standard_legal(self):
        old = dataclasses.replace(GREEN_BEAR, name="Old Cub", standard_legal=False)
        problems = deck_problems(commander_deck(60, extra=[old]), BRAWL)
        self.assertEqual(problems, ["Old Cub is not legal in Brawl"])
        self.assertEqual(deck_problems(commander_deck(100, extra=[old]), COMMANDER), [], "Commander does not care")

    def test_both_keep_singleton_and_color_identity(self):
        double = commander_deck(60, extra=[GREEN_BEAR])
        self.assertTrue(any("2 copies, limit is 1" in p for p in deck_problems(double, BRAWL)))
        off = commander_deck(60, extra=[RED_BEAR])
        self.assertTrue(any("outside the commander's color identity" in p for p in deck_problems(off, BRAWL)))
        self.assertTrue(any("outside the commander's color identity" in p for p in deck_problems(commander_deck(100, extra=[RED_BEAR]), DUEL_COMMANDER)))

    def test_duel_commander_is_a_hundred_cards_with_its_own_banned_list(self):
        banned = dataclasses.replace(GREEN_BEAR, name="Banned Cub", duel_legal=False)
        self.assertEqual(deck_problems(commander_deck(100), DUEL_COMMANDER), [])
        self.assertEqual(deck_problems(commander_deck(100, extra=[banned]), DUEL_COMMANDER), ["Banned Cub is not legal in Duel Commander"])
        self.assertEqual(deck_problems(commander_deck(100, extra=[banned]), COMMANDER), [], "legal in Commander, banned in Duel Commander")
        self.assertIn("needs exactly 100", " ".join(deck_problems(commander_deck(60), DUEL_COMMANDER)))

    def test_commander_proper_is_unchanged(self):
        self.assertEqual(deck_problems(commander_deck(100), COMMANDER), commander.deck_problems(commander_deck(100)))
        self.assertIn("is not legal in Commander", " ".join(deck_problems(
            commander_deck(100, extra=[dataclasses.replace(GREEN_BEAR, name="Bad", commander_legal=False)]), COMMANDER)))


class CardTests(unittest.TestCase):
    def test_duel_legality_is_read_from_scryfall(self):
        base = {"name": "Cub", "type_line": "Creature", "cmc": 0, "legalities": {"commander": "legal", "duel": "banned"}}
        self.assertFalse(Card.from_scryfall(base).duel_legal)
        self.assertTrue(Card.from_scryfall({**base, "legalities": {"duel": "legal"}}).duel_legal)
        self.assertFalse(Card.from_scryfall({**base, "legalities": {}}).duel_legal, "no legality given is not legal, as for the other formats")

    def test_every_face_a_card_can_be_played_as_carries_the_legality(self):
        banned = {"commander": "legal", "standard": "legal", "duel": "banned"}

        def faces(layout, back_type="Instant"):
            return {"name": "Front // Back", "layout": layout, "cmc": 1, "legalities": banned,
                    "card_faces": [{"name": "Front", "mana_cost": "{R}", "type_line": "Creature — Imp", "oracle_text": "", "power": "1", "toughness": "1"},
                                   {"name": "Back", "mana_cost": "{R}", "type_line": back_type, "oracle_text": "", "colors": ["R"]}]}
        self.assertFalse(Card.from_scryfall(faces("modal_dfc", "Land")).back.duel_legal, "a modal double-faced card's land back")
        self.assertFalse(Card.from_scryfall(faces("prepare")).prepare.duel_legal, "the spell half of a prepare card")
        self.assertFalse(Card.from_scryfall(faces("transform", "Creature — Imp")).flip.duel_legal, "the back of a transforming card")
        self.assertFalse(Card.from_scryfall(faces("adventure")).alternate.duel_legal, "the adventure of an adventure card")
        self.assertFalse(Card.from_scryfall(faces("split")).alternate.duel_legal, "the other half of a split card")
        ok = {**faces("adventure"), "legalities": {"duel": "legal"}}
        self.assertTrue(Card.from_scryfall(ok).alternate.duel_legal)

    def test_the_card_file_format_moved_with_the_new_field(self):
        self.assertGreaterEqual(CARD_FORMAT, 5)
        card = Card.from_dict(Card(name="X", duel_legal=False).to_dict())
        self.assertFalse(card.duel_legal)


class GameTests(unittest.TestCase):
    def game(self, fmt, players=2):
        deck = Deck([BOSS], [FOREST] * 20, [], format=fmt.name)
        game = Game([(ScriptedPlayer(name), deck) for name in "ABCD"[:players]], seed=1, format=fmt)
        game.turn, game.active, game.step = 2, 0, "main1"
        return game

    def test_each_format_starts_at_its_life(self):
        self.assertEqual([s.life for s in self.game(COMMANDER).seats], [40, 40])
        self.assertEqual([s.life for s in self.game(BRAWL).seats], [25, 25])
        self.assertEqual([s.life for s in self.game(BRAWL, players=3).seats], [30, 30, 30])
        self.assertEqual([s.life for s in self.game(DUEL_COMMANDER).seats], [20, 20])

    def test_fifteen_commander_damage_loses_duel_commander_and_not_commander(self):
        for fmt, loses in ((DUEL_COMMANDER, True), (COMMANDER, False), (BRAWL, False)):
            game = self.game(fmt)
            game.seats[1].commander_damage[(0, "Boss")] = 15
            game._check_state()
            self.assertEqual(game.seats[1].lost, loses, fmt.name)

    def test_fourteen_does_not_lose_duel_commander_and_twenty_one_loses_brawl(self):
        game = self.game(DUEL_COMMANDER)
        game.seats[1].commander_damage[(0, "Boss")] = 14
        game._check_state()
        self.assertFalse(game.seats[1].lost)
        game = self.game(BRAWL)
        game.seats[1].commander_damage[(0, "Boss")] = 21
        game._check_state()
        self.assertTrue(game.seats[1].lost)

    def test_the_seats_are_told_the_limit_in_a_commander_format_only(self):
        for fmt, expected in ((DUEL_COMMANDER, 15), (COMMANDER, 21), (BRAWL, 21)):
            events = []
            game = self.game(fmt)
            game.broadcast = lambda event, skip=None, sink=events: sink.append(event)  # type: ignore[method-assign]
            game.setup()
            self.assertEqual({e.get("damage_limit") for e in events if e.get("event") == "seat"}, {expected})
        standard = Game([(ScriptedPlayer("A"), Deck([], [FOREST] * 60, [])), (ScriptedPlayer("B"), Deck([], [FOREST] * 60, []))], seed=1, format=STANDARD)
        events = []
        standard.broadcast = lambda event, skip=None: events.append(event)  # type: ignore[method-assign]
        standard.setup()
        self.assertTrue(all("damage_limit" not in e for e in events if e.get("event") == "seat"))


class BotTests(unittest.TestCase):
    OPTIONS = ["Don't attack", "Attack Player: Foe (seat 1)", "Attack Player: Bar (seat 2)"]

    def pod(self, limit=None, dealt=10):
        deck = Deck([BOSS], [FOREST] * 5, [])
        b = BotPlayer("Bot", deck)
        b.notify({"event": "seat", "seat": 0, "name": "Bot", "life": 20, **({"damage_limit": limit} if limit else {})})
        b.notify({"event": "seat", "seat": 1, "name": "Foe", "life": 30})
        b.notify({"event": "seat", "seat": 2, "name": "Bar", "life": 12})
        boss = {"name": "Boss", "type": "Creature", "tapped": False, "sick": False, "power": 5, "toughness": 5}
        b.notify({"event": "state", "hand": [], "seats": [
            {"seat": 0, "lost": False, "life": 20, "mana_pool": [], "battlefield": [boss], "command_zone": [], "commander_damage": []},
            {"seat": 1, "lost": False, "life": 30, "mana_pool": [], "battlefield": [], "command_zone": [],
             "commander_damage": [{"from_seat": 0, "commander": "Boss", "damage": dealt}]},
            {"seat": 2, "lost": False, "life": 12, "mana_pool": [], "battlefield": [], "command_zone": [], "commander_damage": []}]})
        return b

    def test_the_commander_goes_for_the_player_it_can_finish_by_the_formats_limit(self):
        prompt = ATTACK_PROMPT + "Boss 5/5 (seat 0, #1)"
        self.assertEqual(self.pod(limit=15).choose(prompt, self.OPTIONS), 1, "10 + 5 = 15, enough in Duel Commander")
        self.assertEqual(self.pod(limit=21).choose(prompt, self.OPTIONS), 2, "not in Commander: the lowest life")
        self.assertEqual(self.pod(limit=None).choose(prompt, self.OPTIONS), 2, "no limit told: Commander's 21")
        self.assertEqual(self.pod(limit=None, dealt=16).choose(prompt, self.OPTIONS), 1, "16 + 5 = 21")

    def test_it_blocks_the_commander_that_would_reach_the_limit(self):
        def blocker(limit):
            b = self.pod(limit=limit)
            b.notify({"event": "state", "hand": [], "seats": [
                {"seat": 0, "lost": False, "life": 20, "mana_pool": [], "battlefield": [], "command_zone": [],
                 "commander_damage": [{"from_seat": 1, "commander": "Foe Boss", "damage": 10}]},
                {"seat": 1, "lost": False, "life": 30, "mana_pool": [], "battlefield": [], "command_zone": [], "commander_damage": []}]})
            return b.choose("Block with Wall 0/2 (seat 0, #3)", ["Don't block", "Foe Boss 5/5 (seat 1, #9)"])
        self.assertEqual(blocker(15), 1)
        self.assertEqual(blocker(21), 0)


class CommandLineTests(unittest.TestCase):
    def files(self, directory):
        bulk = os.path.join(directory, "bulk.json")
        with open(bulk, "w", encoding="utf-8") as f:
            json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in (FOREST, BOSS, GREEN_BEAR)}}, f)
        deck = os.path.join(directory, "deck.txt")
        Path(deck).write_text("Commander\n1 Boss\n\nDeck\n20 Forest\n39 Cub\n", encoding="utf-8")
        return bulk, deck

    def run_matchup(self, *options):
        with tempfile.TemporaryDirectory() as d:
            bulk, deck = self.files(d)
            out = io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                code = matchup.main(["tool", deck, deck, "--games", "2", "--workers", "1", "--max-turns", "20", "--bulk", bulk, *options])
            return code, out.getvalue()

    def test_a_brawl_matchup_plays_with_brawls_life_and_names_no_bracket(self):
        seen = []
        original = matchup.play_one

        def spying(decks, *rest):
            seen.append([d.format for d in decks])
            return original(decks, *rest)
        matchup.play_one = spying
        try:
            code, out = self.run_matchup("--format", "brawl")
        finally:
            matchup.play_one = original
        self.assertEqual(code, 0)
        self.assertEqual(seen[0], ["brawl", "brawl"])
        self.assertIn("against bots", out)

    def test_the_format_is_checked_against_the_decks(self):
        with self.assertRaises(ValueError):
            self.run_matchup("--format", "standard")

    def test_the_default_is_unchanged(self):
        code, out = self.run_matchup()
        self.assertEqual(code, 0)
        self.assertIn("against bots", out)


if __name__ == "__main__":
    unittest.main()
