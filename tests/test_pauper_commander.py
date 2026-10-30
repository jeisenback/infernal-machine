"""Pauper Commander (#527): PDH Home Base's rules. An uncommon creature, vehicle or spacecraft leads, legendary or not; the 99 are
commons; 30 life; 16 commander damage."""

import dataclasses
import json
import os
import tempfile
import unittest
from unittest import mock

from infernal_machine import formats
from infernal_machine.cards import Card, Deck
from infernal_machine.formats import PAUPER_COMMANDER, HouseRules, deck_problems
from infernal_machine.game import Game
from infernal_machine.pauper_commander import SEARCH, can_lead, uncommon_commanders
from infernal_machine.tune import candidate_problem
from tests.helpers import ScriptedPlayer

COMMON = ("paupercommander", "commander")  # Scryfall's legalities of a card printed at common


def card(name, type_line, identity=("G",), legal=COMMON, banned=()):
    return Card(name=name, mana_cost="{1}{G}", cmc=2, type_line=type_line, power="2", toughness="2", color_identity=identity,
                legal=legal, banned=banned)


FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
LEADER = card("Uncommon Elf", "Creature — Elf", legal=("commander",))  # printed at uncommon only, not legendary
WAGON = card("Uncommon Wagon", "Artifact — Vehicle", identity=(), legal=("commander",))
SHIP = card("Uncommon Ship", "Artifact — Spacecraft", identity=(), legal=("commander",))
AURA = card("Uncommon Aura", "Enchantment — Aura", legal=("commander",))
LEGEND = card("Rare Legend", "Legendary Creature — Elf", legal=("commander",))  # a rare: never printed at uncommon
BANNED = card("Banned Elf", "Creature — Elf", legal=(), banned=("paupercommander",))
RARE_SPELL = card("Rare Spell", "Instant", legal=("commander",))
RED_COMMON = card("Red Common", "Instant", identity=("R",))
UNCOMMON = frozenset({"Uncommon Elf", "Uncommon Wagon", "Uncommon Ship", "Uncommon Aura", "Banned Elf"})


def pdh(commander=LEADER, extra=()):
    return Deck([commander], [*extra, *[FOREST] * (99 - len(extra))], [], format="paupercommander")


class FormatTests(unittest.TestCase):
    def test_the_numbers_are_pdh_home_bases(self):
        fmt = PAUPER_COMMANDER
        self.assertEqual((fmt.life, fmt.min_deck, fmt.copy_limit, fmt.commander, fmt.commander_damage), (30, 100, 1, True, 16))
        self.assertEqual((fmt.legality, fmt.label), ("paupercommander", "Pauper Commander"))
        self.assertIs(formats.FORMATS["paupercommander"], fmt)

    def test_a_game_starts_at_30_life_and_knows_the_16_damage(self):
        deck = Deck([LEADER], [FOREST] * 20, [], format="paupercommander")
        game = Game([(ScriptedPlayer(name), deck) for name in "ABC"], seed=1, format=PAUPER_COMMANDER)
        self.assertEqual([s.life for s in game.seats], [30, 30, 30])
        self.assertEqual(game.format.commander_damage, 16)


class LeadTests(unittest.TestCase):
    def test_an_uncommon_creature_vehicle_or_spacecraft_leads(self):
        self.assertEqual([can_lead(c, UNCOMMON) for c in (LEADER, WAGON, SHIP)], [True, True, True])

    def test_not_another_card_type_and_not_a_card_never_printed_at_uncommon(self):
        self.assertFalse(can_lead(AURA, UNCOMMON), "an uncommon, but not a creature, vehicle or spacecraft")
        self.assertFalse(can_lead(LEGEND, UNCOMMON), "a legendary creature, but rare")

    def test_an_uncommon_background_joins_a_pair_and_does_not_lead_alone(self):
        background = card("Uncommon Background", "Legendary Enchantment — Background")
        self.assertTrue(can_lead(background, UNCOMMON | {"Uncommon Background"}, paired=True))
        self.assertFalse(can_lead(background, UNCOMMON | {"Uncommon Background"}), "alone it can't lead")
        self.assertFalse(can_lead(background, UNCOMMON, paired=True), "a Background never printed at uncommon")
        self.assertFalse(can_lead(AURA, UNCOMMON, paired=True), "only a Background joins that way")


@mock.patch.object(formats, "uncommon_commanders", lambda: UNCOMMON)
class DeckTests(unittest.TestCase):
    def test_a_non_legendary_uncommon_creature_leads_a_deck_of_commons(self):
        self.assertEqual(deck_problems(pdh(), PAUPER_COMMANDER), [])
        self.assertEqual(deck_problems(pdh(WAGON), PAUPER_COMMANDER), [])

    def test_a_rare_legend_cannot_lead_and_a_rare_cannot_be_in_the_99(self):
        self.assertEqual(deck_problems(pdh(LEGEND), PAUPER_COMMANDER), ["Rare Legend can't be your commander"])
        self.assertEqual(deck_problems(pdh(extra=[RARE_SPELL]), PAUPER_COMMANDER), ["Rare Spell is not legal in Pauper Commander"])

    def test_a_banned_creature_cannot_lead(self):
        self.assertEqual(deck_problems(pdh(BANNED), PAUPER_COMMANDER), ["Banned Elf can't be your commander"])

    def test_the_commander_rules_still_hold(self):
        self.assertEqual(deck_problems(pdh(extra=[RED_COMMON]), PAUPER_COMMANDER),
                         ["Red Common is outside the commander's color identity (R)"])
        self.assertIn("Red Common: 2 copies, limit is 1",
                      deck_problems(pdh(extra=[dataclasses.replace(RED_COMMON, color_identity=("G",))] * 2), PAUPER_COMMANDER))

    def test_two_uncommon_partners_lead_together_and_so_do_a_creature_and_an_uncommon_background(self):
        one = dataclasses.replace(LEADER, name="Uncommon Elf", oracle_text="Partner")
        two = dataclasses.replace(LEADER, name="Uncommon Ranger", oracle_text="Partner")
        deck = Deck([one, two], [FOREST] * 98, [], format="paupercommander")
        with mock.patch.object(formats, "uncommon_commanders", lambda: UNCOMMON | {"Uncommon Ranger"}):
            self.assertEqual(deck_problems(deck, PAUPER_COMMANDER), [])
        chooser = dataclasses.replace(LEADER, oracle_text="Choose a Background")
        background = card("Uncommon Background", "Legendary Enchantment — Background", legal=("commander",))
        deck = Deck([chooser, background], [FOREST] * 98, [], format="paupercommander")
        with mock.patch.object(formats, "uncommon_commanders", lambda: UNCOMMON | {"Uncommon Background"}):
            self.assertEqual(deck_problems(deck, PAUPER_COMMANDER), [], "Commander's pairs carry over, both uncommon")
        rare = card("Rare Background", "Legendary Enchantment — Background", legal=("commander",))
        deck = Deck([chooser, rare], [FOREST] * 98, [], format="paupercommander")
        self.assertEqual(deck_problems(deck, PAUPER_COMMANDER), ["Rare Background can't be your commander"])
        alone = Deck([background], [FOREST] * 99, [], format="paupercommander")
        with mock.patch.object(formats, "uncommon_commanders", lambda: UNCOMMON | {"Uncommon Background"}):
            self.assertEqual(deck_problems(alone, PAUPER_COMMANDER), ["Uncommon Background can't be your commander"])

    def test_house_rules_can_let_a_rare_lead(self):
        self.assertEqual(deck_problems(pdh(LEGEND), PAUPER_COMMANDER, HouseRules(frozenset({"Rare Legend"}))), [])

    def test_tune_offers_only_cards_the_99_may_hold(self):
        self.assertEqual(candidate_problem(pdh(), RARE_SPELL), "not legal in Pauper Commander")
        self.assertIsNone(candidate_problem(pdh(), card("Common Spell", "Instant")))


class UnreachableTests(unittest.TestCase):
    def test_when_the_list_cannot_be_fetched_the_deck_check_says_so(self):
        def unreachable():
            raise OSError("no route to host")
        with mock.patch.object(formats, "uncommon_commanders", unreachable):
            problems = deck_problems(pdh(), PAUPER_COMMANDER)
        self.assertEqual(len(problems), 1)
        self.assertIn("Can't check the commander", problems[0])


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "commanders.json")

    def test_the_names_are_fetched_page_by_page_saved_and_read_back(self):
        pages = [{"data": [{"name": "Uncommon Elf"}], "next_page": "https://api.scryfall.com/next"},
                 {"data": [{"name": "Uncommon Wagon"}], "next_page": None}]
        asked = []

        def http(request):
            asked.append(request.full_url)
            return pages[len(asked) - 1]
        with mock.patch("infernal_machine.pauper_commander.time.sleep"):
            names = uncommon_commanders(self.path, http=http)
        self.assertEqual(names, frozenset({"Uncommon Elf", "Uncommon Wagon"}))
        self.assertIn("r%3Auncommon", asked[0])
        self.assertIn("t%3Avehicle", asked[0])
        self.assertIn("t%3Abackground", asked[0])
        with open(self.path, encoding="utf-8") as f:
            self.assertEqual(json.load(f), {"search": SEARCH, "names": ["Uncommon Elf", "Uncommon Wagon"]})
        self.assertEqual(uncommon_commanders(self.path, http=lambda request: self.fail("a fresh file is read, not fetched")), names)

    def test_a_file_from_another_search_is_fetched_again(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(["Old Elf"], f)  # as the list was saved before Backgrounds joined the search
        page = {"data": [{"name": "Uncommon Elf"}], "next_page": None}
        with mock.patch("infernal_machine.pauper_commander.time.sleep"):
            self.assertEqual(uncommon_commanders(self.path, http=lambda request: page), frozenset({"Uncommon Elf"}))

    def test_a_search_scryfall_ignored_part_of_is_an_error_and_nothing_is_saved(self):
        page = {"data": [{"name": "Everything"}], "next_page": None, "warnings": ["Invalid expression ignored"]}
        with self.assertRaises(ValueError):
            uncommon_commanders(self.path, http=lambda request: page)
        self.assertFalse(os.path.exists(self.path))


if __name__ == "__main__":
    unittest.main()
