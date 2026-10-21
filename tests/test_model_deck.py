"""tools/model_deck.py: a typical Commander deck modelled from the card pool (#475), and the tracked decks it wrote."""

import importlib.util
import unittest
from pathlib import Path

from infernal_machine.cards import parse_decklist

ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location("model_deck", ROOT / "tools" / "model_deck.py")
assert _spec is not None and _spec.loader is not None
model_deck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(model_deck)


def card(name, colors="", rank=None, type_line="Creature — Test", cost="", legal="legal", layout="normal"):
    return {"name": name, "color_identity": list(colors), "edhrec_rank": rank, "type_line": type_line, "mana_cost": cost,
            "legalities": {"commander": legal}, "layout": layout}


def pool_of(*cards):
    return {c["name"]: c for c in cards}


def many(prefix, count, colors, start=10):
    return [card(f"{prefix} {i}", colors, rank=start + i, cost="{G}") for i in range(count)]


GREEN = card("Gnarl", "G", rank=1, cost="{2}{G}{G}")
BASE = [card("Forest", "", None, "Basic Land — Forest"), card("Island", "", None, "Basic Land — Island"),
        card("Green Land", "G", rank=5, type_line="Land"), card("Blue Land", "U", rank=6, type_line="Land")]


class ModelTests(unittest.TestCase):
    def pool(self, extra=()):
        return pool_of(GREEN, *BASE, *many("Green Spell", 90, "G"), *many("Blue Spell", 20, "U", 200), *extra)

    def test_a_deck_is_one_hundred_cards_with_the_commander_apart(self):
        main, commanders, _ = model_deck.model(self.pool(), ["Gnarl"], [])
        self.assertEqual((len(main), commanders), (99, ["Gnarl"]))

    def test_a_partner_pair_leaves_ninety_eight(self):
        pool = self.pool([card("Pal", "G", rank=2)])
        main, commanders, _ = model_deck.model(pool, ["Gnarl", "Pal"], [])
        self.assertEqual((len(main), commanders), (98, ["Gnarl", "Pal"]))

    def test_only_cards_of_the_commanders_colors_are_chosen(self):
        main, _, _ = model_deck.model(self.pool(), ["Gnarl"], [])
        self.assertFalse([n for n in main if n.startswith("Blue") or n in ("Island", "Blue Land")])

    def test_the_named_core_cards_come_first_and_the_rest_by_rank(self):
        main, _, _ = model_deck.model(self.pool(), ["Gnarl"], ["Green Spell 40"])
        self.assertEqual(main[0], "Green Spell 40")
        self.assertEqual(main[1], "Green Spell 0", "then the most played")
        self.assertEqual(main.count("Green Spell 40"), 1, "once")

    def test_the_most_played_cards_are_taken_before_alphabetical_ones(self):
        pool = pool_of(GREEN, *BASE, *[card(f"Card {chr(97 + i)}", "G", rank=1000 - i, cost="{G}") for i in range(26)] * 1,
                       *[card(f"Card {chr(97 + i)}{chr(97 + j)}", "G", rank=2000 + i * 26 + j, cost="{G}") for i in range(3) for j in range(26)])
        main, _, _ = model_deck.model(pool, ["Gnarl"], [])
        spells = [n for n in main if n.startswith("Card ")]
        self.assertEqual(spells[0], "Card z", "rank 975 is the best, though it sorts last by name")
        self.assertLess(spells.index("Card z"), spells.index("Card a"))

    def test_a_core_card_that_cannot_be_used_is_reported_with_the_reason(self):
        pool = self.pool([card("Banned Thing", "G", rank=3, legal="banned")])
        main, _, left_out = model_deck.model(pool, ["Gnarl"], ["Banned Thing", "Blue Spell 3", "Nonesuch", "Green Spell 1"])
        self.assertNotIn("Banned Thing", main)
        self.assertNotIn("Blue Spell 3", main)
        self.assertEqual(len(left_out), 3)
        self.assertTrue(any("Banned Thing" in why and "not Commander-legal" in why for why in left_out))
        self.assertTrue(any("Blue Spell 3" in why and "colors" in why for why in left_out))
        self.assertIn("Green Spell 1", main)

    def test_lands_are_thirty_six_with_the_best_nonbasic_ones_and_basics_of_the_colors(self):
        main, _, _ = model_deck.model(self.pool(), ["Gnarl"], [])
        lands = [n for n in main if n in ("Forest", "Green Land", "Island", "Blue Land")]
        self.assertEqual(len(lands), model_deck.LANDS)
        self.assertEqual(main.count("Green Land"), 1)
        self.assertEqual(main.count("Forest"), model_deck.LANDS - 1)

    def test_basics_follow_the_colored_symbols(self):
        pool = pool_of(card("Duo", "GU", rank=1, cost="{G}{U}"), *BASE,
                       *[card(f"G{i}", "G", rank=10 + i, cost="{G}{G}") for i in range(40)],
                       *[card(f"U{i}", "U", rank=100 + i, cost="{U}") for i in range(40)])
        main, _, _ = model_deck.model(pool, ["Duo"], [])
        self.assertGreater(main.count("Forest"), main.count("Island"))
        self.assertGreater(main.count("Island"), 0)

    def test_a_banned_card_is_never_chosen_even_if_it_is_the_most_played(self):
        pool = self.pool([card("Crypt", "", rank=0, legal="banned")])
        main, _, _ = model_deck.model(pool, ["Gnarl"], [])
        self.assertNotIn("Crypt", main)

    def test_the_same_pool_gives_the_same_deck(self):
        self.assertEqual(model_deck.model(self.pool(), ["Gnarl"], ["Green Spell 7"]), model_deck.model(self.pool(), ["Gnarl"], ["Green Spell 7"]))

    def test_the_decklist_text_counts_repeats(self):
        text = model_deck.decklist(["Gnarl"], ["A", "Forest", "Forest"])
        self.assertEqual(text, "Commander\n1 Gnarl\n\nDeck\n1 A\n2 Forest\n")
        parsed = parse_decklist(text)
        self.assertEqual((parsed.commanders, parsed.main), ({"Gnarl": 1}, {"A": 1, "Forest": 2}))


class WrittenDecksTests(unittest.TestCase):
    def test_every_modelled_deck_in_the_spec_was_written_and_is_a_hundred_cards(self):
        import json
        specs = json.loads((ROOT / "examples" / "decks" / "modelled.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(specs), 9)  # ten at first; Edgar Markov's modelled deck gave way to his real EDHREC list (#475)
        for spec in specs:
            parsed = parse_decklist((ROOT / "examples" / "decks" / (spec["name"] + ".txt")).read_text(encoding="utf-8"))
            self.assertEqual(list(parsed.commanders), spec["commanders"], spec["name"])
            self.assertEqual(sum(parsed.commanders.values()) + sum(parsed.main.values()), 100, spec["name"])

    def test_every_core_card_that_was_kept_is_in_its_deck(self):
        import json
        specs = json.loads((ROOT / "examples" / "decks" / "modelled.json").read_text(encoding="utf-8"))
        gone = {"Dockside Extortionist", "Mana Crypt"}  # banned in Commander: not in the pool
        for spec in specs:
            parsed = parse_decklist((ROOT / "examples" / "decks" / (spec["name"] + ".txt")).read_text(encoding="utf-8"))
            for name in spec["core"]:
                if name not in gone:
                    self.assertIn(name, parsed.main, f"{spec['name']}: {name}")


if __name__ == "__main__":
    unittest.main()
