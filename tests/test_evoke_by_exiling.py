"""Evoke paid by exiling a card of a color from the hand ("Evoke—Exile a white card from your hand.": Solitude, Grief), and
Solitude's "exile up to one other target creature. That creature's controller gains life equal to its power." """

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import AlternativeCost, alternative_costs
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import OGRE, lands, pick, real, run_stack, table3

SOLITUDE = real("Solitude", "{3}{W}{W}", "Creature — Elemental Incarnation", "Flash\nLifelink\nWhen this creature enters, exile up to "
                "one other target creature. That creature's controller gains life equal to its power.\nEvoke—Exile a white card from "
                "your hand.", "3", "2")
GRIEF = real("Grief", "{2}{B}{B}", "Creature — Elemental Incarnation", "Menace\nWhen this creature enters, target opponent reveals their "
             "hand. You choose a nonland card from it. That player discards that card.\nEvoke—Exile a black card from your hand.", "3", "2")
WHITE = Card(name="White Card", mana_cost="{W}", type_line="Instant", colors=("W",), oracle_text="You gain 1 life.")
BLUE = Card(name="Blue Card", mana_cost="{U}", type_line="Instant", colors=("U",), oracle_text="Draw a card.")


def table(hand, mana=0, theirs=(OGRE,)):
    game, _ = table3(pick("Ogre"))
    a, b = game.seats[0], game.seats[1]
    a.hand, a.battlefield = list(hand), lands(mana)
    b.battlefield = [Permanent(card) for card in theirs]
    return game, a, b


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (SOLITUDE, GRIEF):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_cost_is_read(self):
        self.assertEqual(alternative_costs(SOLITUDE), [AlternativeCost("Evoke: exile a white card", evoke=True, exile_color="W")])


class SolitudeTests(unittest.TestCase):
    def test_evoked_it_exiles_a_creature_and_is_sacrificed(self):
        game, a, b = table([SOLITUDE, WHITE])
        game._perform(a, CAST + SOLITUDE.name)
        run_stack(game)
        self.assertEqual((a.exile, b.exile), ([WHITE], [OGRE]))
        self.assertEqual(b.life, 43)  # the Ogre's power
        self.assertEqual(a.graveyard, [SOLITUDE])
        self.assertEqual(a.hand, [])

    def test_evoke_needs_another_white_card(self):
        game, a, _ = table([SOLITUDE, BLUE])
        self.assertNotIn(CAST + SOLITUDE.name, game.legal_actions(a))
        game, a, _ = table([SOLITUDE])
        self.assertNotIn(CAST + SOLITUDE.name, game.legal_actions(a))

    def test_cast_for_its_mana_it_stays_and_cannot_exile_itself(self):
        game, a, b = table([SOLITUDE], mana=5, theirs=())
        game._perform(a, CAST + SOLITUDE.name)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield if p.card is SOLITUDE], ["Solitude"])
        self.assertEqual(a.exile, [])
        self.assertEqual(a.life, 40)


if __name__ == "__main__":
    unittest.main()
