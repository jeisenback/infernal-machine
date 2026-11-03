""""At the beginning of your upkeep, look at the top card of your library. You may reveal that card. If an instant or sorcery card is
revealed this way, transform this creature." (Delver of Secrets)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import FOREST, fire, real, scryfall, table3

DELVER = Card.from_scryfall(scryfall(
    "transform",
    {"name": "Delver of Secrets", "mana_cost": "{U}", "type_line": "Creature — Human Wizard", "power": "1", "toughness": "1",
     "oracle_text": "At the beginning of your upkeep, look at the top card of your library. You may reveal that card. If an instant or "
                    "sorcery card is revealed this way, transform this creature."},
    {"name": "Insectile Aberration", "mana_cost": "", "type_line": "Creature — Human Insect", "power": "3", "toughness": "2",
     "oracle_text": "Flying"}, cmc=1.0))
BOLT = real("Lightning Bolt", "{R}", "Instant", "Lightning Bolt deals 3 damage to any target.")


def upkeep(top):
    game, _ = table3()
    a = game.seats[0]
    delver = Permanent(DELVER)
    a.battlefield, a.library, a.hand = [delver], [top, FOREST], []
    fire(game, a, delver, "upkeep")
    return game, a, delver


class DelverTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(DELVER), [])

    def test_an_instant_on_top_transforms_it(self):
        game, a, delver = upkeep(BOLT)
        self.assertEqual(delver.card.name, "Insectile Aberration")
        self.assertTrue(game.has_keyword(delver, "flying"))
        self.assertEqual(a.library[0], BOLT)  # revealed, not moved

    def test_a_land_on_top_does_not(self):
        game, a, delver = upkeep(FOREST)
        self.assertIs(delver.card, DELVER)


if __name__ == "__main__":
    unittest.main()
