import io
import json
import os
import tempfile
import unittest
import urllib.error
from pathlib import Path

from infernal_machine.cards import (
    CARD_FORMAT,
    BulkSource,
    CachedSource,
    Card,
    CardNotFound,
    ScryfallSource,
    load_deck,
    parse_decklist,
)

BOLT = {
    "id": "bolt-id",
    "name": "Lightning Bolt",
    "mana_cost": "{R}",
    "cmc": 1.0,
    "type_line": "Instant",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
    "colors": ["R"],
    "color_identity": ["R"],
    "legalities": {"commander": "legal", "standard": "not_legal"},
}
BEAR = {
    "id": "bear-id",
    "name": "Grizzly Bears",
    "mana_cost": "{1}{G}",
    "cmc": 2.0,
    "type_line": "Creature — Bear",
    "oracle_text": "",
    "colors": ["G"],
    "power": "2",
    "toughness": "2",
}
FIRE_ICE = {
    "id": "fi-id",
    "name": "Fire // Ice",
    "cmc": 4.0,
    "card_faces": [
        {"name": "Fire", "mana_cost": "{1}{R}", "type_line": "Instant", "oracle_text": "Fire deals 2 damage.", "colors": ["R"]},
        {"name": "Ice", "mana_cost": "{1}{U}", "type_line": "Instant", "oracle_text": "Tap target permanent.", "colors": ["U"]},
    ],
}
DB = {c["name"].lower(): c for c in (BOLT, BEAR, FIRE_ICE)}


class FakeScryfall:
    """Stands in for the HTTP layer, answering like the real API."""

    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        if request.full_url.endswith("/cards/collection"):
            identifiers = json.loads(request.data)["identifiers"]
            found, missing = [], []
            for ident in identifiers:
                name = ident["name"].lower()
                # Like Scryfall, the collection endpoint finds a face by its own name but not by "A // B".
                card = None if " // " in name else (
                    DB.get(name) or next((c for n, c in DB.items() if name in n.split(" // ")), None))
                (found.append(card) if card else missing.append(ident))
            return {"data": found, "not_found": missing}
        name = request.full_url.split("exact=")[1].replace("+", " ").lower()
        if name not in DB:
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", {}, io.BytesIO())
        return DB[name]


class CardTests(unittest.TestCase):
    def test_from_scryfall_uses_front_face_for_split_cards(self):
        card = Card.from_scryfall(FIRE_ICE)
        self.assertEqual(card.name, "Fire // Ice")
        self.assertEqual(card.mana_cost, "{1}{R}")
        self.assertEqual(card.colors, ("R",))

    def test_from_scryfall_reads_commander_fields(self):
        card = Card.from_scryfall(BOLT)
        self.assertEqual(card.color_identity, ("R",))
        self.assertTrue(card.legal_in("commander"))
        self.assertFalse(Card.from_scryfall({**BOLT, "legalities": {"commander": "banned"}}).legal_in("commander"))

    def test_round_trips_through_dict(self):
        card = Card.from_scryfall(BOLT)
        self.assertEqual(Card.from_dict(json.loads(json.dumps(card.to_dict()))), card)


class ScryfallSourceTests(unittest.TestCase):
    def setUp(self):
        self.http = FakeScryfall()
        self.source = ScryfallSource(http=self.http, min_interval=0)

    def test_get_sends_required_headers(self):
        card = self.source.get("Lightning Bolt")
        self.assertEqual(card.oracle_text, BOLT["oracle_text"])
        headers = dict(self.http.requests[0].header_items())
        self.assertIn("User-agent", headers)
        self.assertEqual(headers["Accept"], "application/json")

    def test_get_unknown_card_raises(self):
        with self.assertRaises(CardNotFound):
            self.source.get("Not A Card")

    def test_get_many_keys_by_requested_name(self):
        cards = self.source.get_many(["lightning bolt", "Fire", "Grizzly Bears"])
        self.assertEqual(cards["lightning bolt"].name, "Lightning Bolt")
        self.assertEqual(cards["Fire"].name, "Fire // Ice")

    def test_get_many_finds_full_split_names(self):
        cards = self.source.get_many(["Fire // Ice"])
        self.assertEqual(cards["Fire // Ice"].name, "Fire // Ice")

    def test_get_many_batches_requests(self):
        self.source.COLLECTION_BATCH = 2
        self.source.get_many(["Lightning Bolt", "Grizzly Bears", "Fire // Ice"])
        self.assertEqual(len(self.http.requests), 2)

    def test_get_many_reports_missing(self):
        with self.assertRaisesRegex(CardNotFound, "Nope"):
            self.source.get_many(["Lightning Bolt", "Nope"])


class CachedSourceTests(unittest.TestCase):
    def test_second_lookup_is_served_from_disk(self):
        http = FakeScryfall()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cards.json"
            CachedSource(ScryfallSource(http=http, min_interval=0), path).get("Lightning Bolt")
            fresh = CachedSource(ScryfallSource(http=http, min_interval=0), path)
            self.assertEqual(fresh.get("LIGHTNING BOLT").name, "Lightning Bolt")
        self.assertEqual(len(http.requests), 1)


class CachedSourceFormatTests(unittest.TestCase):
    """A cache file saved before Card gained a field must be fetched again, not read with that field's default (#373)."""

    OLD_BOLT = {key: value for key, value in Card.from_scryfall(BOLT).to_dict().items() if key != "legal"}  # as saved by an older version

    def fetch(self, contents):
        """Look up Lightning Bolt through a cache file holding `contents`; return the card, the number of requests, and the file afterwards."""
        http = FakeScryfall()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cards.json"
            path.write_text(json.dumps(contents))
            card = CachedSource(ScryfallSource(http=http, min_interval=0), path).get("Lightning Bolt")
            return card, len(http.requests), json.loads(path.read_text())

    def test_the_file_records_its_format(self):
        _, _, saved = self.fetch({})  # (an empty mapping is not a valid cache; it is read as empty and refilled)
        self.assertEqual(saved["format"], CARD_FORMAT)
        self.assertEqual(list(saved["cards"]), ["lightning bolt"])

    def test_a_current_file_is_used_without_the_network(self):
        card, requests, _ = self.fetch({"format": CARD_FORMAT, "cards": {"lightning bolt": Card.from_scryfall(BOLT).to_dict()}})
        self.assertEqual((card.name, requests), ("Lightning Bolt", 0))

    def test_the_old_bare_mapping_is_fetched_again(self):
        card, requests, saved = self.fetch({"lightning bolt": self.OLD_BOLT})
        self.assertEqual(requests, 1)
        self.assertFalse(card.legal_in("standard"))  # the old entry would have read as legal: its file never said
        self.assertEqual(saved["format"], CARD_FORMAT)

    def test_a_file_in_another_format_is_fetched_again(self):
        for other in (CARD_FORMAT - 1, CARD_FORMAT + 1, 0):
            card, requests, saved = self.fetch({"format": other, "cards": {"lightning bolt": self.OLD_BOLT}})
            self.assertEqual((requests, card.legal_in("standard"), saved["format"]), (1, False, CARD_FORMAT), other)

    def test_a_damaged_cards_entry_is_read_as_empty(self):
        _, requests, _ = self.fetch({"format": CARD_FORMAT, "cards": ["not", "a", "mapping"]})
        self.assertEqual(requests, 1)

    def test_the_demo_cards_are_in_the_current_format(self):
        # examples/demo_cards.json is hand-made and used offline (the tests forbid the network), so it is converted when the
        # format changes, not fetched again: check its cards have the new fields, then set "format" in the file to CARD_FORMAT.
        saved = json.loads((Path(__file__).parent.parent / "examples" / "demo_cards.json").read_text())
        self.assertEqual(saved["format"], CARD_FORMAT, "examples/demo_cards.json is in an older card format")


class BulkSourceTests(unittest.TestCase):
    TOKEN = {"id": "t", "name": "Grizzly Bears", "layout": "token", "type_line": "Token Creature"}

    def setUp(self):
        self.requests = []
        fire_ice = {"id": "fi", "name": "Fire // Ice", "layout": "split", "cmc": 4.0,
                    "card_faces": [{"name": "Fire", "mana_cost": "{1}{R}", "type_line": "Instant", "oracle_text": "x"},
                                   {"name": "Ice", "mana_cost": "{1}{U}", "type_line": "Instant", "oracle_text": "y"}]}

        def http(request):
            self.requests.append(request.full_url)
            return {"data": [{"type": "default_cards", "jsonl_download_uri": "https://x/default"},
                             {"type": "oracle_cards", "jsonl_download_uri": "https://x/oracle"}]}

        def download(request):
            self.requests.append(request.full_url)
            start_fire = {"id": "sf", "name": "Start // Fire", "layout": "split",
                          "card_faces": [{"name": "Start", "type_line": "Sorcery"}, {"name": "Fire", "type_line": "Sorcery"}]}
            return [BOLT, self.TOKEN, start_fire, fire_ice]

        self.http = http
        self.download = download

    def test_downloads_once_then_serves_from_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bulk.json"
            first = BulkSource(path, http=self.http, download=self.download)
            self.assertEqual(first.get("lightning bolt").name, "Lightning Bolt")
            self.assertEqual(self.requests, ["https://api.scryfall.com/bulk-data", "https://x/oracle"])
            second = BulkSource(path, http=self.http, download=self.download)
            self.assertEqual(second.get("Lightning Bolt").mana_cost, "{R}")
            self.assertEqual(len(self.requests), 2)

    def test_finds_faces_and_skips_tokens(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = BulkSource(Path(tmp) / "bulk.json", http=self.http, download=self.download)
            self.assertEqual(source.get("Fire").name, "Fire // Ice")
            with self.assertRaises(CardNotFound):
                source.get("Grizzly Bears")

    def test_a_copy_saved_before_the_format_marker_is_downloaded_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bulk.json"
            path.write_text(json.dumps({"Lightning Bolt": Card.from_scryfall(BOLT).to_dict()}))
            BulkSource(path, http=self.http, download=self.download).get("Lightning Bolt")
            self.assertEqual(len(self.requests), 2)
            self.assertEqual(json.loads(path.read_text())["format"], BulkSource.FORMAT)

    def test_stale_file_is_refreshed_and_kept_if_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bulk.json"
            BulkSource(path, http=self.http, download=self.download).get("Lightning Bolt")
            old = path.stat().st_mtime - 30 * 86400
            os.utime(path, (old, old))
            BulkSource(path, http=self.http, download=self.download).get("Lightning Bolt")
            self.assertEqual(len(self.requests), 4)
            os.utime(path, (old, old))

            def offline(request):
                raise urllib.error.URLError("down")

            self.assertEqual(BulkSource(path, http=offline, download=offline).get("Lightning Bolt").name, "Lightning Bolt")


class DecklistTests(unittest.TestCase):
    def test_parses_arena_format(self):
        deck = parse_decklist(
            "Commander\n1 Grizzly Bears\n\nDeck\n4 Lightning Bolt (M11) 146\n\nSideboard\n1 Fire // Ice\n"
        )
        self.assertEqual(deck.commanders, {"Grizzly Bears": 1})
        self.assertEqual(deck.main, {"Lightning Bolt": 4})
        self.assertEqual(deck.sideboard, {"Fire // Ice": 1})

    def test_parses_moxfield_markers(self):
        deck = parse_decklist("1 Grizzly Bears (LEA) 190 *CMDR*\n2x Lightning Bolt (2X2) 117 *F*\n")
        self.assertEqual(deck.commanders, {"Grizzly Bears": 1})
        self.assertEqual(deck.main, {"Lightning Bolt": 2})

    def test_blank_line_after_main_starts_sideboard(self):
        deck = parse_decklist("4 Lightning Bolt\n\n1 Fire // Ice")
        self.assertEqual(deck.sideboard, {"Fire // Ice": 1})

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            parse_decklist("Lightning Bolt")

    def test_load_deck_expands_counts(self):
        source = ScryfallSource(http=FakeScryfall(), min_interval=0)
        deck = load_deck("Commander\n1 Grizzly Bears\nDeck\n3 Lightning Bolt", source)
        self.assertEqual([c.name for c in deck.commanders], ["Grizzly Bears"])
        self.assertEqual([c.name for c in deck.main], ["Lightning Bolt"] * 3)


if __name__ == "__main__":
    unittest.main()
