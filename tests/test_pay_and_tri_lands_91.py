"""More lands from issue #91, each played from its real Oracle text: "When this land enters, sacrifice it unless you pay {1}"
(Gateway Plaza and the other Guildgate-style lands) and the tri-lands that make one mana of one of three colors."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, PLAY_LAND, UNLESS_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, pick, real, run_stack, Table, table3

ANY = ("B", "G", "R", "U", "W")

PLAZA = Card(name="Gateway Plaza", type_line="Land", produced_mana=ANY,
             oracle_text="This land enters tapped.\nWhen this land enters, sacrifice it unless you pay {1}.\n{T}: Add one mana of any color.")
SANCTUM = Card(name="Arcane Sanctum", type_line="Land", produced_mana=("B", "U", "W"), oracle_text="This land enters tapped.\n{T}: Add {W}, {U}, or {B}.")
NECROPOLIS = Card(name="Crumbling Necropolis", type_line="Land", produced_mana=("B", "R", "U"), oracle_text="This land enters tapped.\n{T}: Add {U}, {B}, or {R}.")
CITADEL = Card(name="Seaside Citadel", type_line="Land", produced_mana=("G", "U", "W"), oracle_text="This land enters tapped.\n{T}: Add {G}, {W}, or {U}.")
TRI_LANDS = [(SANCTUM, "BUW"), (NECROPOLIS, "BRU"), (CITADEL, "GUW")]
SPELLS = {c: real(f"{c} Draw", f"{{{c}}}", "Instant", "Draw a card.", colors=(c,)) for c in "WUBRG"}
UNITED = real("Blue Red", "{U}{R}", "Instant", "Draw a card.", colors=("U", "R"))


def play(policy, card, n):
    """Seat 0 plays `card` with `n` untapped lands already in play; returns (game, seat, prompts seen)."""
    seen = []

    def watching(prompt, options):
        seen.append((prompt, options))
        return policy(prompt, options)

    game, _ = table3(watching)
    a = game.seats[0]
    a.battlefield = lands(n)
    a.hand = [card]
    game._perform(a, PLAY_LAND + card.name)
    run_stack(game)
    return game, a, seen


def colors_it_pays(card):
    found = ""
    for color, spell in SPELLS.items():
        t = Table(spell, n=0, mine=[Permanent(card)])
        if any(a.startswith(CAST + spell.name) for a in t.game.legal_actions(t.a)):
            found += color
    return "".join(sorted(found))


class SacrificeUnlessPayTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(unsupported_lines(PLAZA), [])

    def test_paying_keeps_the_land_and_uses_a_land_for_the_mana(self):
        game, a, seen = play(pick("Pay"), PLAZA, 1)
        self.assertEqual([p.card.name for p in a.battlefield if p.card is PLAZA], ["Gateway Plaza"])
        self.assertEqual(sum(p.tapped for p in a.battlefield if p.card is not PLAZA), 1)
        self.assertEqual(seen, [(UNLESS_PROMPT + "Gateway Plaza", ["Pay {1}", "Don't pay"])])

    def test_the_land_enters_tapped_either_way(self):
        game, a, _ = play(pick("Pay"), PLAZA, 1)
        self.assertTrue(next(p for p in a.battlefield if p.card is PLAZA).tapped)

    def test_declining_sacrifices_it(self):
        game, a, _ = play(pick("Don't"), PLAZA, 3)
        self.assertEqual([p.card.name for p in a.battlefield if p.card is PLAZA], [])
        self.assertEqual([c.name for c in a.graveyard], ["Gateway Plaza"])
        self.assertEqual(sum(p.tapped for p in a.battlefield), 0, "nothing was spent")

    def test_with_nothing_to_pay_with_it_is_sacrificed_without_asking(self):
        # (it entered tapped, so it has no mana of its own for the cost)
        game, a, seen = play(pick("Pay"), PLAZA, 0)
        self.assertEqual(a.battlefield, [])
        self.assertEqual([c.name for c in a.graveyard], ["Gateway Plaza"])
        self.assertEqual(seen, [])

    def test_while_it_stays_it_makes_any_color(self):
        self.assertEqual(colors_it_pays(PLAZA), "BGRUW")


class TriLandTests(unittest.TestCase):
    def test_parse(self):
        for card, _ in TRI_LANDS:
            with self.subTest(card=card.name):
                self.assertEqual(unsupported_lines(card), [])

    def test_each_makes_one_mana_of_one_of_its_three_colors(self):
        for card, colors in TRI_LANDS:
            with self.subTest(card=card.name):
                self.assertEqual(colors_it_pays(card), colors)

    def test_it_makes_one_mana_not_two(self):
        for card, _ in TRI_LANDS:
            with self.subTest(card=card.name):
                t = Table(UNITED, n=0, mine=[Permanent(card)])
                self.assertFalse(any(a.startswith(CAST) for a in t.game.legal_actions(t.a)))

    def test_a_permanent_that_is_not_a_land_with_the_same_line_works_too(self):
        stone = Card(name="Tri Stone", type_line="Artifact", mana_cost="{3}", cmc=3.0, oracle_text="{T}: Add {W}, {U}, or {B}.")
        self.assertEqual(unsupported_lines(stone), [])
        self.assertEqual(colors_it_pays(stone), "BUW")
        t = Table(real("White Blue", "{W}{U}", "Instant", "Draw a card.", colors=("W", "U")), n=0, mine=[Permanent(stone)])
        self.assertFalse(any(a.startswith(CAST) for a in t.game.legal_actions(t.a)), "one mana, not two")

    def test_they_enter_tapped(self):
        for card, _ in TRI_LANDS:
            with self.subTest(card=card.name):
                game, a, _ = play(pick(), card, 0)
                self.assertTrue(a.battlefield[0].tapped)


if __name__ == "__main__":
    unittest.main()
