"""Clarion Conqueror: "Activated abilities of artifacts, creatures, and planeswalkers can't be activated." (Stony Silence's artifacts-only
lock is the same rule.)"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects.outcomes import TREASURE
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, real, table3

CONQUEROR = real("Clarion Conqueror", "{2}{W}", "Creature — Dragon", "Flying\nActivated abilities of artifacts, creatures, and "
                 "planeswalkers can't be activated.", "3", "3")
LOOTER = Card(name="Looter", mana_cost="{U}", type_line="Creature — Wizard", power="1", toughness="1", oracle_text="{T}: Draw a card.")
SHRINE = Card(name="Shrine", mana_cost="{2}", type_line="Enchantment", oracle_text="{1}: You gain 1 life.")
BEAR_SPELL = Card(name="Cub", mana_cost="{1}", cmc=1.0, type_line="Creature — Bear", power="1", toughness="1")


def table(*permanents, conqueror=True, theirs=False):
    game, _ = table3()
    a, b = game.seats[0], game.seats[1]
    a.battlefield = [Permanent(card) for card in permanents]
    if conqueror:
        (b if theirs else a).battlefield.append(Permanent(CONQUEROR))
    return game, a


def activations(game, seat):
    return [x for x in game.legal_actions(seat) if x.startswith(ACTIVATE)]


class ClarionConquerorTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(CONQUEROR), [])

    def test_creature_abilities_cannot_be_activated(self):
        game, a = table(LOOTER)
        self.assertFalse(any("Looter" in x for x in activations(game, a)))
        game, a = table(LOOTER, conqueror=False)
        self.assertTrue(any("Looter" in x for x in activations(game, a)))

    def test_it_stops_an_opponents_abilities_too(self):
        game, a = table(LOOTER, theirs=True)
        self.assertFalse(any("Looter" in x for x in activations(game, a)))

    def test_an_enchantments_ability_still_can_be_activated(self):
        game, a = table(SHRINE, *[c.card for c in lands(1)])
        self.assertTrue(any("Shrine" in x for x in activations(game, a)))

    def test_a_treasure_cannot_pay_but_a_land_can(self):
        game, a = table(TREASURE)
        a.hand = [BEAR_SPELL]
        self.assertNotIn(CAST + BEAR_SPELL.name, game.legal_actions(a))
        a.battlefield += lands(1)
        self.assertIn(CAST + BEAR_SPELL.name, game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
