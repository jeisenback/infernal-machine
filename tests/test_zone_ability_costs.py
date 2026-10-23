"""An ability that works from the graveyard and has no mana in its cost (#513): Cauldron Familiar's "Sacrifice a Food: Return this card
from your graveyard to the battlefield." was offered with no look at the Food, and listing the actions asserted on its empty mana cost.
And one that has a card cost other than a sacrifice (#529): Stitchwing Skaab's "Discard two cards: Return this card ..." and Purple
Pentapus's "Tap an untapped creature you control: Return this card ..." came back for free, because only the mana and the sacrifice
were paid. The cards are from their real Oracle text; the Food, the Treasure and the spare cards are probes."""

import unittest

from infernal_machine.game import ACTIVATE_GRAVEYARD, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, real, run_stack, table

FAMILIAR = real("Cauldron Familiar", "{B}", "Creature — Cat", "When this creature enters, each opponent loses 1 life and you gain 1 life.\n"
                "Sacrifice a Food: Return this card from your graveyard to the battlefield.", "1", "1")
FOOD = real("Food Probe", "{0}", "Artifact — Food", "")
TREASURE = real("Treasure Probe", "{0}", "Artifact — Treasure", "")
ACTION = ACTIVATE_GRAVEYARD + "Cauldron Familiar"


def seat_with(*permanents, mana=0):
    game, _, _ = table(pick(ACTION))
    a = game.seats[0]
    a.graveyard = [FAMILIAR]
    a.battlefield = [*(Permanent(c) for c in permanents), *lands(mana)]
    return game, a


class FromTheGraveyardWithAnotherCostTests(unittest.TestCase):
    def test_every_line_is_read(self):
        self.assertEqual(unsupported_lines(FAMILIAR), [])

    def test_with_no_food_it_is_not_offered_and_listing_does_not_raise(self):
        game, a = seat_with(TREASURE)
        self.assertNotIn(ACTION, game.legal_actions(a))

    def test_with_a_food_it_is_offered_without_any_mana(self):
        game, a = seat_with(FOOD)
        self.assertIn(ACTION, game.legal_actions(a))

    def test_it_sacrifices_the_food_and_comes_back(self):
        game, a = seat_with(FOOD, TREASURE)
        game._perform(a, ACTION)
        run_stack(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Cauldron Familiar", "Treasure Probe"])
        self.assertEqual(a.graveyard, [FOOD])

    def test_it_asks_nothing_of_the_lands(self):
        game, a = seat_with(FOOD, mana=2)
        game._perform(a, ACTION)
        run_stack(game)
        self.assertFalse(any(p.tapped for p in a.battlefield))

    def test_the_familiar_does_not_come_back_twice_from_one_food(self):
        game, a = seat_with(FOOD)
        game._perform(a, ACTION)
        run_stack(game)
        a.battlefield = [p for p in a.battlefield if p.card is not FAMILIAR]
        a.graveyard = [FAMILIAR]
        self.assertNotIn(ACTION, game.legal_actions(a))  # the Food went to the graveyard with the first return


SKAAB = real("Stitchwing Skaab", "{3}{U}", "Creature \u2014 Zombie Horror", "Flying\n{1}{U}, Discard two cards: Return this card from your graveyard to "
             "the battlefield tapped.", "3", "1", colors=("U",))
PENTAPUS = real("Purple Pentapus", "{B}", "Creature \u2014 Octopus Starfish", "When this creature enters, surveil 1. (Look at the top card of your "
                "library. You may put it into your graveyard.)\n{2}{B}, Tap an untapped creature you control: Return this card from your graveyard to "
                "the battlefield tapped.", "1", "1", colors=("B",))
SPARE = real("Spare Card", "{1}", "Instant", "")


def grave_with(card, hand=(), battlefield=(), mana=3):
    game, _, _ = table(pick("Activate from graveyard"))
    a = game.seats[0]
    a.graveyard = [card]
    a.hand = list(hand)
    a.battlefield = [*battlefield, *lands(mana)]
    return game, a, ACTIVATE_GRAVEYARD + card.name


class DiscardFromTheGraveyardTests(unittest.TestCase):
    def test_every_line_is_read(self):
        for card in (SKAAB, PENTAPUS):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_it_is_not_offered_with_fewer_cards_than_it_asks_to_discard(self):
        game, a, action = grave_with(SKAAB, hand=[SPARE])
        self.assertNotIn(action, game.legal_actions(a))

    def test_it_is_offered_with_enough_cards(self):
        game, a, action = grave_with(SKAAB, hand=[SPARE, SPARE])
        self.assertIn(action, game.legal_actions(a))

    def test_it_discards_two_cards_and_comes_back_tapped(self):
        game, a, action = grave_with(SKAAB, hand=[SPARE, SPARE, BEAR])
        game._perform(a, action)
        run_stack(game)
        self.assertEqual([c.name for c in a.graveyard], ["Spare Card", "Spare Card"])  # the first two cards of the hand
        self.assertEqual([c.name for c in a.hand], ["Bear"])
        skaab = next(p for p in a.battlefield if p.card is SKAAB)
        self.assertTrue(skaab.tapped)
        self.assertNotIn(SKAAB, a.graveyard)

    def test_it_needs_its_mana_as_well(self):
        game, a, action = grave_with(SKAAB, hand=[SPARE, SPARE], mana=1)
        self.assertNotIn(action, game.legal_actions(a))


class TapFromTheGraveyardTests(unittest.TestCase):
    def test_it_is_not_offered_with_no_untapped_creature(self):
        game, a, action = grave_with(PENTAPUS)
        self.assertNotIn(action, game.legal_actions(a))
        tapped = Permanent(BEAR, tapped=True)
        game, a, action = grave_with(PENTAPUS, battlefield=[tapped])
        self.assertNotIn(action, game.legal_actions(a))

    def test_it_taps_the_creature_and_comes_back_tapped(self):
        bear = Permanent(BEAR)
        game, a, action = grave_with(PENTAPUS, battlefield=[bear])
        self.assertIn(action, game.legal_actions(a))
        game._perform(a, action)
        run_stack(game)
        self.assertTrue(bear.tapped)
        self.assertTrue(next(p for p in a.battlefield if p.card is PENTAPUS).tapped)


if __name__ == "__main__":
    unittest.main()
