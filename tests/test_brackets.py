"""Commander Brackets: Game Changers, mass land denial and extra turns read off a deck's cards (#362)."""

import unittest

from infernal_machine.brackets import analyze, bracket_floor, has_extra_turn, is_mass_land_denial
from infernal_machine.cards import Card, Deck
from infernal_machine.matchup import format_matchups, matchups, within_bracket
from infernal_machine.tune import Effect, _bracket_notes, format_tuning, tune
from tests.helpers import real

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))


def changer(name, power="1"):
    return Card(name=name, mana_cost="{1}{G}", cmc=2, type_line="Creature — Elf", power=power, toughness="1", color_identity=("G",), game_changer=True)


def commander_deck(*extras, filler=BEAR, commander=BOSS):
    main = list(extras)
    return Deck([commander], main + [FOREST] * 40 + [filler] * (99 - 40 - len(main)), [])


DUD = Card(name="Aaa Dud", mana_cost="{U}{U}{U}{U}", cmc=4, type_line="Creature — Wizard", power="1", toughness="1", color_identity=("G",))  # can never be cast: the weakest card
ARMAGEDDON = real("Armageddon", "{3}{W}", "Sorcery", "Destroy all lands.")
RUINATION = real("Ruination", "{3}{R}{R}", "Sorcery", "Destroy all nonbasic lands.")
JOKULHAUPS = real("Jokulhaups", "{4}{R}{R}", "Sorcery", "Destroy all artifacts, creatures, and lands. They can't be regenerated.")
CATASTROPHE = real("Catastrophe", "{4}{W}{W}", "Sorcery", "Destroy all lands or all creatures. Creatures destroyed this way can't be regenerated.")
WILDFIRE = real("Wildfire", "{4}{R}{R}", "Sorcery", "Each player sacrifices four lands of their choice. Wildfire deals 4 damage to each creature.")
SUNDER = real("Sunder", "{3}{U}{U}", "Instant", "Return all lands to their owners' hands.")
STONE_RAIN = real("Stone Rain", "{2}{R}", "Sorcery", "Destroy target land.")
WRATH = real("Wrath of God", "{2}{W}{W}", "Sorcery", "Destroy all creatures. They can't be regenerated.")
TIME_WARP = real("Time Warp", "{3}{U}{U}", "Sorcery", "Target player takes an extra turn after this one.")
TIME_STRETCH = real("Time Stretch", "{8}{U}{U}", "Sorcery", "Target player takes two extra turns after this one.")
SCRYFALL_RHYSTIC = {"name": "Rhystic Study", "mana_cost": "{2}{U}", "cmc": 3, "type_line": "Enchantment", "game_changer": True,
                    "oracle_text": "Whenever an opponent casts a spell, you may draw a card unless that player pays {1}.", "legalities": {"commander": "legal"}}


class CardTests(unittest.TestCase):
    def test_scryfall_flag_is_read_and_survives_the_cache(self):
        card = Card.from_scryfall(SCRYFALL_RHYSTIC)
        self.assertTrue(card.game_changer)
        self.assertTrue(Card.from_dict(card.to_dict()).game_changer)
        plain = Card.from_scryfall({**SCRYFALL_RHYSTIC, "game_changer": False})
        self.assertFalse(plain.game_changer)
        self.assertFalse(Card.from_scryfall({k: v for k, v in SCRYFALL_RHYSTIC.items() if k != "game_changer"}).game_changer)


class TextTests(unittest.TestCase):
    def test_mass_land_denial(self):
        for card in (ARMAGEDDON, RUINATION, JOKULHAUPS, CATASTROPHE, WILDFIRE, SUNDER):
            self.assertTrue(is_mass_land_denial(card), card.name)

    def test_ordinary_removal_is_not(self):
        for card in (STONE_RAIN, WRATH, TIME_WARP, BEAR):
            self.assertFalse(is_mass_land_denial(card), card.name)

    def test_a_land_that_mentions_lands_is_not_a_spell_that_destroys_them(self):
        land = real("Test Land", "", "Land", "{T}: Add {G}. Destroy all lands if you control no Forest.")
        self.assertFalse(is_mass_land_denial(land))

    def test_extra_turns(self):
        self.assertTrue(has_extra_turn(TIME_WARP))
        self.assertTrue(has_extra_turn(TIME_STRETCH))
        self.assertFalse(has_extra_turn(WRATH))


class FloorTests(unittest.TestCase):
    def test_the_floor(self):
        for changers, denial, floor in ((0, 0, 1), (1, 0, 3), (3, 0, 3), (4, 0, 4), (9, 0, 4), (0, 1, 4), (2, 2, 4)):
            self.assertEqual(bracket_floor(changers, denial), floor, (changers, denial))

    def test_a_deck_is_read_commander_and_all(self):
        plain = analyze(commander_deck())
        self.assertEqual((plain.floor, plain.game_changers, plain.mass_land_denial, plain.extra_turns), (1, [], [], []))
        three = analyze(commander_deck(changer("A"), changer("B"), changer("C")))
        self.assertEqual((three.floor, three.game_changers), (3, ["A", "B", "C"]))
        commander_counts = analyze(commander_deck(commander=changer("Flagged Boss")))
        self.assertEqual(commander_counts.game_changers, ["Flagged Boss"])
        self.assertEqual(analyze(commander_deck(changer("A"), changer("B"), changer("C"), changer("D"))).floor, 4)
        self.assertEqual(analyze(commander_deck(ARMAGEDDON)).floor, 4)

    def test_extra_turns_are_listed_but_do_not_raise_the_floor(self):
        report = analyze(commander_deck(TIME_WARP, TIME_STRETCH))
        self.assertEqual((report.floor, report.extra_turns), (1, ["Time Stretch", "Time Warp"]))

    def test_the_summary_reads_in_words(self):
        text = analyze(commander_deck(changer("A"), ARMAGEDDON, TIME_WARP)).summary()
        self.assertIn("Bracket 4 or higher", text)
        self.assertIn("1 Game Changer: A", text)
        self.assertIn("mass land denial: Armageddon", text)
        self.assertIn("extra turns: Time Warp", text)
        self.assertIn("no hard limit", analyze(commander_deck()).summary())


class TuneTests(unittest.TestCase):
    def run_tune(self, deck, *candidates):
        return tune(deck, games=30, turns=4, seed=1, candidates=list(candidates))

    def test_the_report_says_what_the_deck_needs(self):
        text = format_tuning(self.run_tune(commander_deck(changer("A"))))
        self.assertIn("Bracket: plays at Bracket 3 or higher; 1 Game Changer: A.", text)

    def test_a_deck_without_a_commander_has_no_bracket(self):
        report = self.run_tune(Deck([], [FOREST] * 24 + [BEAR] * 36, []))
        self.assertIsNone(report.bracket)
        self.assertNotIn("Bracket", format_tuning(report))

    def test_a_game_changer_candidate_says_what_it_does_to_the_bracket(self):
        report = self.run_tune(commander_deck(changer("A", "6"), changer("B", "6"), changer("C", "6"), *[DUD] * 8), changer("Fourth"))
        self.assertEqual(report.swaps[0][1], "Aaa Dud")  # (ties at zero are broken by name)
        self.assertIn("a Game Changer: the deck would have 4, and play at Bracket 4 or higher", report.swap_notes["Fourth"])
        self.assertIn("Fourth for", format_tuning(report))

    def test_mass_land_denial_candidate(self):
        green_armageddon = Card(**{**ARMAGEDDON.__dict__, "color_identity": ("G",)})
        report = self.run_tune(commander_deck(*[DUD] * 8), green_armageddon)
        self.assertIn("mass land denial", report.swap_notes["Armageddon"])

    def test_an_ordinary_candidate_has_no_note(self):
        self.assertEqual(self.run_tune(commander_deck(), Card(name="Other Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))).swap_notes, {})

    def test_replacing_a_game_changer_with_an_ordinary_card_lowers_the_count(self):
        stuck = Card(name="Stuck Changer", mana_cost="{U}{U}{U}{U}", cmc=4, type_line="Creature — Wizard", power="1", toughness="1", color_identity=("G",), game_changer=True)
        fresh = Card(name="Fresh Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))
        deck = commander_deck(stuck)
        notes = _bracket_notes(deck, [("Fresh Bear", "Stuck Changer", Effect(0.0, 0.0))], [fresh])
        self.assertEqual(notes, {"Fresh Bear": "drops a Game Changer: the deck could play at Bracket 1"})
        # four Game Changers is Bracket 4, and three is Bracket 3: that is worth saying; but one of five going leaves the floor where it is
        four = commander_deck(stuck, changer("A"), changer("B"), changer("C"))
        self.assertEqual(_bracket_notes(four, [("Fresh Bear", "Stuck Changer", Effect(0.0, 0.0))], [fresh]),
                         {"Fresh Bear": "drops a Game Changer: the deck could play at Bracket 3"})
        five = commander_deck(stuck, changer("A"), changer("B"), changer("C"), changer("D"))
        self.assertEqual(_bracket_notes(five, [("Fresh Bear", "Stuck Changer", Effect(0.0, 0.0))], [fresh]), {})


class MatchupTests(unittest.TestCase):
    def test_records_carry_the_brackets_and_a_mismatch_is_flagged(self):
        focus = commander_deck(changer("A"))
        strong = commander_deck(changer("A"), changer("B"), changer("C"), changer("D"))
        records = matchups(focus, {"even": commander_deck(changer("X")), "stronger": strong}, games=2, max_turns=6)
        self.assertEqual([(r.focus_bracket, r.bracket) for r in records], [(3, (3,)), (3, (4,))])
        text = format_matchups(records, "focus")
        self.assertIn("plays at Bracket 3 or higher", text)
        self.assertIn("Warning: stronger can only be played at a higher Bracket", text)
        self.assertNotIn("Warning: even", text)

    def test_matching_brackets_get_no_warning(self):
        records = matchups(commander_deck(), {"same": commander_deck()}, games=2, max_turns=6)
        self.assertNotIn("Warning", format_matchups(records, "focus"))

    def test_a_pod_lists_every_opponent_bracket(self):
        pod = matchups(commander_deck(), {"a": commander_deck(), "b": commander_deck(ARMAGEDDON)}, games=2, pod=3, max_turns=6)
        self.assertEqual(pod[0].bracket, (1, 4))

    def test_decks_without_commanders_have_no_brackets(self):
        deck = Deck([], [FOREST] * 24 + [BEAR] * 36, [])
        records = matchups(deck, {"mirror": deck}, games=2, max_turns=6)
        self.assertEqual((records[0].focus_bracket, records[0].bracket), (None, ()))
        self.assertNotIn("Bracket", format_matchups(records, "focus"))

    def test_leaving_out_opponents_above_a_bracket(self):
        opponents = {"low": commander_deck(), "mid": commander_deck(changer("A")), "high": commander_deck(ARMAGEDDON)}
        kept, left_out = within_bracket(opponents, 3)
        self.assertEqual((sorted(kept), left_out), (["low", "mid"], {"high": 4}))
        self.assertEqual(sorted(within_bracket(opponents, 1)[0]), ["low"])


if __name__ == "__main__":
    unittest.main()
