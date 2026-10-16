"""Reports say when a deck holds cards the engine can't fully play (#372). The unreadable text below is invented on purpose: these
tests are about the warning, not about any real card, and a real card that is unsupported today would be supported one day."""

import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.matchup import format_matchups, matchups
from infernal_machine.report import unplayable_cards, unplayable_note
from infernal_machine.simulate import format_simulation, simulate
from infernal_machine.tune import format_tuning, tune

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
BEAR = Card(name="Grizzly Bears", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2")
BOSS = Card(name="Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3", color_identity=("G",))
ODD_TEXT = "Exchange the frobnicator of each player with the quuxes."
ODD = Card(name="Odd Spell", mana_cost="{1}{G}", cmc=2, type_line="Sorcery", oracle_text=ODD_TEXT, color_identity=("G",))
ODDER = Card(name="Odder Creature", mana_cost="{2}{G}", cmc=3, type_line="Creature — Elf", power="2", toughness="2",
             oracle_text="When this creature enters, quux the frobnicator.", color_identity=("G",))
ODD_COMMANDER = Card(name="Odd Boss", mana_cost="{3}{G}", cmc=4, type_line="Legendary Creature — Elf", power="3", toughness="3",
                     oracle_text="Whenever you frobnicate, quux.", color_identity=("G",))


def deck(*extras, commander=BOSS):
    return Deck([commander], list(extras) + [FOREST] * 40 + [BEAR] * (99 - 40 - len(extras)), [])


class HelperTests(unittest.TestCase):
    def test_only_cards_with_unreadable_text_are_listed(self):
        found = unplayable_cards(deck(ODD, ODDER, ODDER))
        self.assertEqual([(name, copies) for name, copies, _ in found], [("Odder Creature", 2), ("Odd Spell", 1)])  # most copies first
        self.assertEqual(found[1][2], ODD_TEXT)
        self.assertEqual(unplayable_cards(deck()), [])

    def test_the_commander_counts(self):
        self.assertEqual([name for name, _, _ in unplayable_cards(deck(commander=ODD_COMMANDER))], ["Odd Boss"])

    def test_the_note_counts_and_shortens(self):
        one = unplayable_note([("Odd Spell", 1, ODD_TEXT)], "The deck")
        self.assertIn("The deck has 1 card (1 copy) the engine can't fully play: Odd Spell.", one)
        self.assertIn("a spell does nothing", one)
        many = unplayable_note([(f"Card {i}", 2, "x") for i in range(8)], "The deck")
        self.assertIn("8 cards (16 copies)", many)
        self.assertIn("Card 0, Card 1, Card 2, Card 3, Card 4 and 3 more", many)
        self.assertIn("so the numbers stand", unplayable_note([("A", 1, "x")], "The deck", "so the numbers stand."))


class MatchupTests(unittest.TestCase):
    def run_matchups(self, focus, **opponents):
        return matchups(focus, opponents, games=2, max_turns=6)

    def test_the_focus_deck_is_flagged(self):
        records = self.run_matchups(deck(ODD), clean=deck())
        self.assertEqual(records[0].focus_unplayable, (("Odd Spell", 1),))
        text = format_matchups(records, "focus")
        self.assertIn("The focus deck has 1 card (1 copy) the engine can't fully play: Odd Spell.", text)
        self.assertIn("Its win rates are unreliable.", text)
        self.assertNotIn("Opponent clean", text)

    def test_the_focus_deck_sentence_can_be_left_out(self):
        records = self.run_matchups(deck(ODD), odd=deck(ODDER))
        text = format_matchups(records, "focus", focus_warning=False)
        self.assertNotIn("The focus deck has", text)
        self.assertIn("Opponent odd has 1 card", text)  # (the opponents' sentences stay)

    def test_an_opponent_is_flagged_by_name(self):
        text = format_matchups(self.run_matchups(deck(), odd=deck(ODDER), clean=deck()), "focus")
        self.assertIn("Opponent odd has 1 card", text)
        self.assertIn("Results against it are unreliable.", text)
        self.assertNotIn("Opponent clean", text)
        self.assertNotIn("The focus deck has", text)

    def test_a_pod_lists_the_cards_of_every_opponent(self):
        records = matchups(deck(), {"a": deck(ODD), "b": deck(ODDER)}, games=2, pod=3, max_turns=6)
        self.assertEqual(records[0].opponent_unplayable, (("Odd Spell", 1), ("Odder Creature", 1)))

    def test_clean_decks_get_no_warning(self):
        text = format_matchups(self.run_matchups(deck(), same=deck()), "focus")
        self.assertNotIn("can't fully play", text)
        self.assertNotIn("unreliable", text)


class TuneTests(unittest.TestCase):
    def test_the_deck_and_its_cards_are_flagged(self):
        report = tune(deck(ODD), games=30, turns=4, seed=1)
        self.assertEqual([name for name, _, _ in report.unplayable], ["Odd Spell"])
        text = format_tuning(report)
        self.assertIn("The deck has 1 card (1 copy) the engine can't fully play: Odd Spell.", text)
        self.assertIn("The goldfish does not read card text, so these numbers do not change", text)

    def test_the_card_table_marks_unreadable_cards_whether_or_not_they_were_drawn(self):
        seen = tune(deck(*[ODD] * 8), games=40, turns=4, seed=1)
        row = next(line for line in format_tuning(seen).splitlines() if line.startswith("Odd Spell"))
        self.assertIn("text the engine can't read", row)
        self.assertNotIn("never drawn", row)  # (drawn in these games, so this is the other path)
        unseen = tune(deck(ODD), games=1, turns=1, seed=0)  # one copy, one game, one turn: not drawn
        row = next(line for line in format_tuning(unseen).splitlines() if line.startswith("Odd Spell"))
        self.assertIn("never drawn in these games; text the engine can't read", row)

    def test_a_clean_deck_is_not(self):
        text = format_tuning(tune(deck(), games=30, turns=4, seed=1))
        self.assertNotIn("can't fully play", text)
        self.assertNotIn("can't read", text)

    def test_a_candidate_with_unreadable_text_says_so(self):
        dud = Card(name="Aaa Dud", mana_cost="{U}{U}{U}{U}", cmc=4, type_line="Creature — Wizard", power="1", toughness="1", color_identity=("G",))
        fresh_odd = Card(name="Fresh Odd", mana_cost="{1}{G}", cmc=2, type_line="Sorcery", oracle_text=ODD_TEXT, color_identity=("G",))
        fresh_bear = Card(name="Fresh Bear", mana_cost="{1}{G}", cmc=2, type_line="Creature — Bear", power="2", toughness="2", color_identity=("G",))
        report = tune(deck(*[dud] * 8), games=30, turns=4, seed=1, candidates=[fresh_odd, fresh_bear])
        self.assertEqual(list(report.candidate_unplayable), ["Fresh Odd"])
        text = format_tuning(report)
        self.assertIn(f"[the engine can't read: {ODD_TEXT[:60]}]", text)
        self.assertEqual(sum("the engine can't read" in line for line in text.splitlines() if " for " in line), 1)


class WithBracketsTests(unittest.TestCase):
    """Both notes on one line when a candidate is a Game Changer whose text the engine can't read."""

    def test_a_swap_can_carry_both_notes(self):
        dud = Card(name="Aaa Dud", mana_cost="{U}{U}{U}{U}", cmc=4, type_line="Creature — Wizard", power="1", toughness="1", color_identity=("G",))
        odd_changer = Card(name="Odd Changer", mana_cost="{1}{G}", cmc=2, type_line="Sorcery", oracle_text=ODD_TEXT, color_identity=("G",), game_changer=True)
        text = format_tuning(tune(deck(*[dud] * 8), games=30, turns=4, seed=1, candidates=[odd_changer]))
        line = next(line for line in text.splitlines() if line.strip().startswith("Odd Changer for"))
        self.assertIn("a Game Changer: the deck would have 1", line)
        self.assertIn("the engine can't read:", line)
        self.assertIn("Bracket: no hard limit above Bracket 1", text)

    def test_the_deck_notes_come_together(self):
        text = format_tuning(tune(deck(ODD), games=20, turns=3, seed=1))
        lines = text.splitlines()
        self.assertTrue(lines[1].startswith("Bracket:") and lines[2].startswith("The deck has 1 card"), lines[:4])


class SimulateTests(unittest.TestCase):
    def test_the_simulation_says_what_it_does_not_read(self):
        text = format_simulation(simulate(deck(ODD), games=20, turns=4, seed=1))
        self.assertIn("Card text is not played here, only mana and creature bodies", text)


if __name__ == "__main__":
    unittest.main()
