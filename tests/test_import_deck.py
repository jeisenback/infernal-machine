"""Turning a Moxfield or Archidekt export into a decklist (#395)."""

import importlib.util
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from infernal_machine.cards import BulkSource, Card, parse_decklist

spec = importlib.util.spec_from_file_location("import_deck", Path(__file__).parent.parent / "tools" / "import_deck.py")
assert spec is not None and spec.loader is not None
importer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(importer)

ARCHIDEKT = """\
1x Atraxa, Praetors' Voice (c16) 28 [Commander{top}]
1x Sol Ring (c21) 263 [Ramp] ^Staples,Mana^ *F*
2x Island (m21) 262 [Land]
1x Swords to Plowshares (cmm) 17 [Removal,Sideboard]
1x Counterspell (cmm) 81 [Maybeboard]
"""

MOXFIELD = """\
1 Atraxa, Praetors' Voice *CMDR*
1 Sol Ring (C21) 263 *F*
1 Command Tower (C21) 276
2 Island

SIDEBOARD:
1 Swords to Plowshares

Maybeboard:
1 Counterspell
"""


class TextTests(unittest.TestCase):
    def test_an_archidekt_export(self):
        deck = importer.parse(ARCHIDEKT)
        self.assertEqual(deck.commanders, {"Atraxa, Praetors' Voice": 1})
        self.assertEqual(deck.main, {"Sol Ring": 1, "Island": 2})
        self.assertEqual(deck.side, {"Swords to Plowshares": 1})
        self.assertEqual(deck.dropped, ["1x Counterspell (cmm) 81 [Maybeboard]"])

    def test_a_moxfield_export(self):
        deck = importer.parse(MOXFIELD)
        self.assertEqual(deck.commanders, {"Atraxa, Praetors' Voice": 1})
        self.assertEqual(deck.main, {"Sol Ring": 1, "Command Tower": 1, "Island": 2})
        self.assertEqual(deck.side, {"Swords to Plowshares": 1})
        self.assertEqual(deck.dropped, ["1 Counterspell"])

    def test_a_commander_section_and_sb_lines(self):
        deck = importer.parse("Commander\n1 Atraxa, Praetors' Voice\n\nDeck\n3 Island\nSB: 1 Counterspell\n")
        self.assertEqual((deck.commanders, deck.main, deck.side), ({"Atraxa, Praetors' Voice": 1}, {"Island": 3}, {"Counterspell": 1}))

    def test_a_blank_line_after_the_main_deck_starts_the_sideboard(self):
        deck = importer.parse("4 Lightning Bolt\n2 Mountain\n\n1 Pyroblast\n")
        self.assertEqual((deck.main, deck.side), ({"Lightning Bolt": 4, "Mountain": 2}, {"Pyroblast": 1}))

    def test_repeated_cards_add_up_and_foils_are_not_different_cards(self):
        deck = importer.parse("1 Island *F*\n1 Island (M21) 262\n2x Island\n")
        self.assertEqual(deck.main, {"Island": 4})

    def test_a_line_that_is_not_a_card_is_dropped_and_said_so(self):
        deck = importer.parse("1 Island\nTotal: 100 cards\n")
        self.assertEqual(deck.dropped, ["Total: 100 cards"])
        self.assertIn("Left out 1 line", importer.warnings(deck)[-1])

    def test_a_split_card_keeps_both_names(self):
        self.assertEqual(importer.parse("1 Fire // Ice (mh2) 290\n").main, {"Fire // Ice": 1})


def moxfield_export(main=99, side="SIDEBOARD:\n1 Snuff Out\n1 Shadowspear\n", tail="\n1 Toshiro Umezawa\n"):
    return f"{main - 1} Swamp\n1 Sol Ring\n\n{side}{tail}"


class TrailingCommanderTests(unittest.TestCase):
    def test_the_card_alone_after_the_sideboard_is_the_commander(self):
        deck = importer.parse(moxfield_export())
        self.assertEqual(deck.commanders, {"Toshiro Umezawa": 1})
        self.assertEqual(deck.side, {"Snuff Out": 1, "Shadowspear": 1})
        self.assertEqual(deck.total, 100)
        self.assertIn("Took Toshiro Umezawa for the commander", importer.warnings(deck)[0])

    def test_it_is_written_as_a_commander(self):
        decklist = parse_decklist(importer.render(importer.parse(moxfield_export())))
        self.assertEqual(decklist.commanders, {"Toshiro Umezawa": 1})
        self.assertNotIn("Toshiro Umezawa", decklist.sideboard)

    def test_not_when_the_main_deck_is_not_99_cards(self):
        for main in (98, 100):
            deck = importer.parse(moxfield_export(main=main))
            self.assertEqual(deck.commanders, {}, main)
            self.assertIn("Toshiro Umezawa", deck.side)

    def test_not_when_the_last_paragraph_is_more_than_one_card(self):
        deck = importer.parse(moxfield_export(tail="\n1 Toshiro Umezawa\n1 Another Card\n"))
        self.assertEqual(deck.commanders, {})

    def test_not_when_the_card_has_a_count_above_one(self):
        self.assertEqual(importer.parse(moxfield_export(tail="\n2 Toshiro Umezawa\n")).commanders, {})

    def test_not_when_a_commander_is_already_marked(self):
        deck = importer.parse("1 Boss *CMDR*\n" + moxfield_export(main=99))
        self.assertEqual(deck.commanders, {"Boss": 1})
        self.assertIn("Toshiro Umezawa", deck.side)

    def test_not_when_the_sideboard_is_one_paragraph(self):
        deck = importer.parse(moxfield_export(side="SIDEBOARD:\n1 Toshiro Umezawa\n", tail=""))
        self.assertEqual(deck.commanders, {})
        self.assertEqual(deck.side, {"Toshiro Umezawa": 1})


class CompanionTests(unittest.TestCase):
    def test_a_companion_section_is_kept_apart_from_the_deck_and_not_counted(self):
        deck = importer.parse("Companion\n1 Lurrus of the Dream-Den\n\nCommander\n1 Boss\n\nDeck\n99 Island\n\nSideboard\n1 Snuff Out\n")
        self.assertEqual(deck.companion, {"Lurrus of the Dream-Den": 1})
        self.assertEqual((deck.commanders, deck.main, deck.side), ({"Boss": 1}, {"Island": 99}, {"Snuff Out": 1}))
        self.assertEqual(deck.total, 100)
        self.assertEqual(importer.warnings(deck), [])

    def test_the_category_marks_a_companion_too(self):
        deck = importer.parse("1x Lurrus of the Dream-Den (iko) 226 [Companion]\n2x Island (m21) 262 [Land]\n")
        self.assertEqual((deck.companion, deck.main), ({"Lurrus of the Dream-Den": 1}, {"Island": 2}))

    def test_it_is_written_as_a_companion_section_the_decklist_reads(self):
        text = importer.render(importer.parse("Companion\n1 Lurrus of the Dream-Den\n\nDeck\n4 Island\n"))
        self.assertIn("Companion\n1 Lurrus of the Dream-Den", text)
        self.assertEqual(parse_decklist(text).companion, {"Lurrus of the Dream-Den": 1})

    def test_two_companions_are_warned_about(self):
        deck = importer.parse("Companion\n1 Lurrus of the Dream-Den\n1 Zirda, the Dawnwaker\n\nDeck\n4 Island\n")
        self.assertIn("at most one companion; this has 2", " ".join(importer.warnings(deck)))


class SignatureSpellTests(unittest.TestCase):
    TEXT = "Oathbreaker\n1 Oath Walker\n\nSignature Spell\n1 Sig Spell\n\nDeck\n58 Island\n"

    def test_the_oathbreaker_and_its_signature_spell_are_kept_apart(self):
        deck = importer.parse(self.TEXT)
        self.assertEqual((deck.commanders, deck.signature, deck.main), ({"Oath Walker": 1}, {"Sig Spell": 1}, {"Island": 58}))
        self.assertEqual(deck.total, 60, "the signature spell is one of the sixty")
        self.assertEqual(importer.warnings(deck), [])

    def test_the_category_marks_a_signature_spell_too(self):
        deck = importer.parse("1x Sig Spell (xxx) 1 [Signature Spell]\n2x Island (m21) 262 [Land]\n")
        self.assertEqual((deck.signature, deck.main), ({"Sig Spell": 1}, {"Island": 2}))

    def test_it_is_written_as_a_signature_spell_section_the_decklist_reads(self):
        text = importer.render(importer.parse(self.TEXT))
        self.assertIn("Signature Spell\n1 Sig Spell", text)
        parsed = parse_decklist(text)
        self.assertEqual((parsed.commanders, parsed.signature), ({"Oath Walker": 1}, {"Sig Spell": 1}))

    def test_two_signature_spells_are_warned_about_and_sixty_is_not_a_wrong_size(self):
        deck = importer.parse("Oathbreaker\n1 Oath Walker\n\nSignature Spell\n1 Sig Spell\n1 Sig Kill\n\nDeck\n57 Island\n")
        self.assertIn("at most one signature spell; this has 2", " ".join(importer.warnings(deck)))
        self.assertFalse(any("has 60" in w for w in importer.warnings(importer.parse(self.TEXT))))


class CsvTests(unittest.TestCase):
    def test_a_csv_with_count_and_name(self):
        deck = importer.parse('Count,Name,Edition,Board\n1,"Atraxa, Praetors\' Voice",c16,commander\n2,Island,m21,mainboard\n1,Counterspell,cmm,maybeboard\n'
                              '1,Swords to Plowshares,cmm,sideboard\n')
        self.assertEqual((deck.commanders, deck.main, deck.side), ({"Atraxa, Praetors' Voice": 1}, {"Island": 2}, {"Swords to Plowshares": 1}))
        self.assertEqual(deck.dropped, ["1 Counterspell"])

    def test_text_that_only_mentions_count_is_not_a_csv(self):
        self.assertEqual(importer.parse("1 Name Count\n").main, {"Name Count": 1})


class OutputTests(unittest.TestCase):
    def test_what_it_writes_is_what_load_deck_reads(self):
        decklist = parse_decklist(importer.render(importer.parse(MOXFIELD)))
        self.assertEqual(decklist.commanders, {"Atraxa, Praetors' Voice": 1})
        self.assertEqual(decklist.main, {"Sol Ring": 1, "Command Tower": 1, "Island": 2})
        self.assertEqual(decklist.sideboard, {"Swords to Plowshares": 1})

    def test_a_hundred_cards_and_no_commander_is_warned_about(self):
        deck = importer.parse("100 Island\n")
        self.assertIn("no commander", importer.warnings(deck)[0])
        self.assertEqual(importer.warnings(importer.parse("60 Island\n")), [], "a 60-card deck needs none")

    def test_a_commander_deck_of_the_wrong_size_is_warned_about(self):
        self.assertIn("this one has 61", importer.warnings(importer.parse("Commander\n1 Boss\n\nDeck\n60 Island\n"))[0])

    def test_the_command_line_reads_a_file_and_writes_one(self):
        with tempfile.TemporaryDirectory() as d:
            source, target = os.path.join(d, "export.txt"), os.path.join(d, "deck.txt")
            Path(source).write_text(ARCHIDEKT, encoding="utf-8")
            with redirect_stderr(io.StringIO()) as err:
                self.assertEqual(importer.main([source, "-o", target]), 0)
            self.assertTrue(Path(target).read_text(encoding="utf-8").startswith("Commander\n1 Atraxa, Praetors' Voice\n\nDeck\n"))
            self.assertIn("Wrote", err.getvalue())
            self.assertIn("Left out 1 line", err.getvalue())

    def test_an_export_with_no_cards_is_an_error(self):
        with tempfile.TemporaryDirectory() as d, redirect_stderr(io.StringIO()):
            empty = os.path.join(d, "empty.txt")
            Path(empty).write_text("nothing here\n", encoding="utf-8")
            self.assertEqual(importer.main([empty]), 2)


class CheckTests(unittest.TestCase):
    def bulk(self, directory, cards):
        path = os.path.join(directory, "bulk.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in cards}}, f)
        return path

    def test_check_reports_a_missing_card_and_a_complete_deck(self):
        boss = Card(name="Boss", type_line="Legendary Creature — Elf", color_identity=("G",))
        island = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
        with tempfile.TemporaryDirectory() as d:
            bulk = self.bulk(d, [boss, island])
            ok = importer.check("Commander\n1 Boss\n\nDeck\n2 Island\n", bulk)
            self.assertIn("1 commander(s) and 2 other card(s) all found", ok[0])
            self.assertIn("Bracket 1 or higher", ok[1])
            bad = importer.check("Commander\n1 Boss\n\nDeck\n1 Nonesuch\n", bulk)
            self.assertTrue(bad[0].startswith("Check failed"))
            self.assertIn("Nonesuch", bad[0])


if __name__ == "__main__":
    unittest.main()
