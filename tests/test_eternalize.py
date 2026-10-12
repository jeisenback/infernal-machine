"""Eternalize {cost}: "{cost}, Exile this card from your graveyard: Create a token that's a copy of it, except it's a 4/4 black Zombie
[types] with no mana cost. Eternalize only as a sorcery." (CR 702.129a). Fanatic of Rhonas, Adorned Pouncer, Steadfast Sentinel."""

import unittest

from infernal_machine.game import ETERNALIZE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, real, run_stack, table3

TEXT = " ({}, Exile this card from your graveyard: Create a token that's a copy of it, except it's a 4/4 black Zombie {} with no mana cost. Eternalize only as a sorcery.)"
FANATIC = real("Fanatic of Rhonas", "{1}{G}", "Creature — Snake Druid", "{T}: Add {G}.\nFerocious — {T}: Add {G}{G}{G}{G}. Activate only if you control a "
               "creature with power 4 or greater.\nEternalize {2}{G}{G}" + TEXT.format("{2}{G}{G}", "Snake Druid"), "1", "4", colors=("G",))
POUNCER = real("Adorned Pouncer", "{1}{W}", "Creature — Cat", "Double strike\nEternalize {3}{W}{W}" + TEXT.format("{3}{W}{W}", "Cat"), "2", "2", colors=("W",))
SENTINEL = real("Steadfast Sentinel", "{3}{W}", "Creature — Human Cleric", "Vigilance\nEternalize {4}{W}{W}" + TEXT.format("{4}{W}{W}", "Human Cleric"),
                "3", "3", colors=("W",))


def setup(card, n):
    game, _ = table3()
    a = game.seats[0]
    a.graveyard, a.battlefield = [card], lands(n)
    return game, a


class EternalizeTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (FANATIC, POUNCER, SENTINEL):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_makes_a_four_four_black_zombie_token_copy_and_exiles_the_card(self):
        game, a = setup(POUNCER, 5)
        self.assertIn(ETERNALIZE + "Adorned Pouncer", game.legal_actions(a))
        game._perform(a, ETERNALIZE + "Adorned Pouncer")
        run_stack(game)
        (token,) = [p for p in a.battlefield if "Land" not in p.card.type_line]
        card = token.card
        self.assertEqual((card.name, card.power, card.toughness, card.colors, card.mana_cost), ("Adorned Pouncer", "4", "4", ("B",), ""))
        self.assertEqual(card.type_line, "Token Creature — Zombie Cat")
        self.assertTrue(game.has_keyword(token, "double strike"))
        self.assertEqual((a.graveyard, a.exile), ([], [POUNCER]))
        self.assertEqual(sum(p.tapped for p in a.battlefield), 5)

    def test_the_token_keeps_the_original_creature_types(self):
        game, a = setup(SENTINEL, 6)
        game._perform(a, ETERNALIZE + "Steadfast Sentinel")
        (token,) = [p for p in a.battlefield if "Land" not in p.card.type_line]
        self.assertEqual(token.card.type_line, "Token Creature — Zombie Human Cleric")

    def test_needs_the_mana(self):
        game, a = setup(FANATIC, 3)
        self.assertNotIn(ETERNALIZE + "Fanatic of Rhonas", game.legal_actions(a))
        a.battlefield = lands(4)
        self.assertIn(ETERNALIZE + "Fanatic of Rhonas", game.legal_actions(a))

    def test_only_at_sorcery_speed(self):
        game, a = setup(POUNCER, 5)
        game.step = "combat"
        self.assertNotIn(ETERNALIZE + "Adorned Pouncer", game.legal_actions(a))
        game.step, game.active = "main1", 1
        self.assertNotIn(ETERNALIZE + "Adorned Pouncer", game.legal_actions(a))

    def test_not_from_the_battlefield_or_hand(self):
        game, a = setup(POUNCER, 5)
        a.graveyard, a.hand = [], [POUNCER]
        a.battlefield.append(Permanent(POUNCER))
        self.assertNotIn(ETERNALIZE + "Adorned Pouncer", game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
