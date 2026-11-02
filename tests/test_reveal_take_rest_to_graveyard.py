""""Reveal the top four cards of your library. You may put a permanent card from among them into your hand. Put the rest into your
graveyard." (Malevolent Rumble; Grisly Salvage's "creature or land card")."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, FOREST, OGRE, RELIC, lands, pick, real, run_stack, table3

RUMBLE = real("Malevolent Rumble", "{1}{G}", "Sorcery", "Reveal the top four cards of your library. You may put a permanent card from among "
              "them into your hand. Put the rest into your graveyard. Create a 0/1 colorless Eldrazi Spawn creature token with \"Sacrifice "
              "this token: Add {C}.\"")
SALVAGE = real("Grisly Salvage", "{B}{G}", "Instant", "Reveal the top five cards of your library. You may put a creature or land card from "
               "among them into your hand. Put the rest into your graveyard.")
SHOCK = Card(name="Shock", mana_cost="{R}", type_line="Instant", oracle_text="Shock deals 2 damage to any target.")


def rumble(library, take="Relic"):
    game, _ = table3(pick(take))
    a = game.seats[0]
    a.hand, a.graveyard, a.library = [RUMBLE], [], list(library)
    a.battlefield = lands(2)
    game._perform(a, CAST + RUMBLE.name)
    run_stack(game)
    return a


class MalevolentRumbleTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (RUMBLE, SALVAGE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_permanent_to_hand_the_rest_to_the_graveyard_and_a_spawn(self):
        a = rumble([SHOCK, RELIC, BEAR, SHOCK, OGRE])
        self.assertEqual(a.hand, [RELIC])
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Malevolent Rumble", "Shock", "Shock"])
        self.assertEqual(a.library, [OGRE])
        self.assertEqual([p.card.name for p in a.battlefield if p.card.name == "Eldrazi Spawn"], ["Eldrazi Spawn"])

    def test_an_instant_cannot_be_taken(self):
        a = rumble([SHOCK, SHOCK, SHOCK, SHOCK, FOREST], take="Shock")
        self.assertEqual(a.hand, [])
        self.assertEqual(a.library, [FOREST])


if __name__ == "__main__":
    unittest.main()
