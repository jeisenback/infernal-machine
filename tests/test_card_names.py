"""A card is found by the name deck sites write: without accents, or a split card with one slash (MTGGoldfish's lists, #590)."""

import json
import os
import tempfile
import unittest

from infernal_machine.cards import BulkSource, Card, CardNotFound, load_deck


def card(name, type_line="Instant"):
    return Card(name=name, mana_cost="{1}", cmc=1, type_line=type_line, oracle_text="Draw a card.")


LORIEN = card("Lórien Revealed", "Sorcery")
TROLL = card("Troll of Khazad-dûm", "Creature — Troll")
WEAR = card("Wear // Tear")
ANNEX = card("Unholy Annex // Ritual Chamber", "Enchantment — Room")
CAFE, CAFE_ACCENT = card("Cafe"), card("Café")
EX_GRAVE, EX_ACUTE = card("Èx"), card("Éx")
FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))


class CardNameTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = os.path.join(self.tmp.name, "bulk.json")
        cards = (LORIEN, TROLL, WEAR, ANNEX, CAFE, CAFE_ACCENT, EX_GRAVE, EX_ACUTE, FOREST)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"format": BulkSource.FORMAT, "cards": {c.name: c.to_dict() for c in cards}}, f)
        self.source = BulkSource(path)

    def name(self, written):
        return self.source.get(written).name

    def test_a_name_without_its_accents_finds_the_card(self):
        self.assertEqual(self.name("Lorien Revealed"), "Lórien Revealed")
        self.assertEqual(self.name("Troll of Khazad-dum"), "Troll of Khazad-dûm")
        self.assertEqual(self.name("LORIEN REVEALED"), "Lórien Revealed")

    def test_a_split_or_room_card_with_one_slash_finds_the_card(self):
        self.assertEqual(self.name("Wear/Tear"), "Wear // Tear")
        self.assertEqual(self.name("wear//tear"), "Wear // Tear")
        self.assertEqual(self.name("Unholy Annex/Ritual Chamber"), "Unholy Annex // Ritual Chamber")

    def test_the_exact_names_still_win(self):
        self.assertEqual(self.name("Lórien Revealed"), "Lórien Revealed")
        self.assertEqual(self.name("Wear // Tear"), "Wear // Tear")
        self.assertEqual(self.name("Wear"), "Wear // Tear", "a face finds its card, as before")
        self.assertEqual((self.name("Cafe"), self.name("Café")), ("Cafe", "Café"), "each spelling is a card of its own")

    def test_a_form_two_cards_share_is_not_guessed(self):
        with self.assertRaises(CardNotFound):
            self.source.get("Ex")
        self.assertEqual((self.name("Èx"), self.name("Éx")), ("Èx", "Éx"))

    def test_an_unknown_name_is_still_not_found(self):
        with self.assertRaises(CardNotFound):
            self.source.get("Lorien Revealing")

    def test_a_list_as_mtggoldfish_writes_it_loads(self):
        deck = load_deck("4 Lorien Revealed\n2 Wear/Tear\n1 Troll of Khazad-dum\n53 Forest\n\n2 Unholy Annex/Ritual Chamber\n", self.source)
        self.assertEqual(sorted({c.name for c in deck.main}), ["Forest", "Lórien Revealed", "Troll of Khazad-dûm", "Wear // Tear"])
        self.assertEqual([c.name for c in deck.sideboard], ["Unholy Annex // Ritual Chamber"] * 2)


if __name__ == "__main__":
    unittest.main()
