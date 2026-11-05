"""Looking at an opponent's hand and taking a card, from the real Oracle text: Stinging Vitriol ("That player reveals their hand. ...
They discard that card.", the player its damage targeted), Intimidation Tactics ("You choose an artifact or creature card from it. Exile
that card.") and Thought-Stalker Warlock (your choice if they lost life this turn, theirs otherwise)."""

import unittest

from infernal_machine.effects.spells import line_effects
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BOLT, FOREST, RELIC, lands, pick, real, run_stack, table3

STINGING_VITRIOL = real("Stinging Vitriol", "{B}{R}", "Sorcery", "Stinging Vitriol deals 2 damage to target opponent. That player reveals "
                        "their hand. You choose a nonland card from it. They discard that card.", colors=("B", "R"))
INTIMIDATION_TACTICS = real("Intimidation Tactics", "{B}", "Sorcery", "Target opponent reveals their hand. You choose an artifact or "
                            "creature card from it. Exile that card.\nCycling {3} ({3}, Discard this card: Draw a card.)", colors=("B",))
WARLOCK = real("Thought-Stalker Warlock", "{2}{B}", "Creature — Lizard Warlock", "Menace (This creature can't be blocked except by two or "
               "more creatures.)\nWhen this creature enters, choose target opponent. If they lost life this turn, they reveal their hand, "
               "you choose a nonland card from it, and they discard that card. Otherwise, they discard a card.", "2", "2", ("B",))


def table(card, *mine):
    game, _ = table3(pick(*mine))
    a, b, _ = game.seats
    a.battlefield, a.hand = lands(4), [card]
    return game, a, b


class RevealAndChooseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (STINGING_VITRIOL, INTIMIDATION_TACTICS, WARLOCK):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_that_player_needs_a_player_the_effect_before_targeted(self):
        self.assertIsNone(line_effects("You draw a card. That player reveals their hand. You choose a nonland card from it. "
                                       "They discard that card."))

    def test_stinging_vitriol_damages_then_takes_a_nonland_card(self):
        game, a, b = table(STINGING_VITRIOL, "Seat 1", "Bear")
        b.hand = [FOREST, BEAR]
        game._perform(a, CAST + "Stinging Vitriol")
        run_stack(game)
        self.assertEqual((b.life, b.hand, b.graveyard), (38, [FOREST], [BEAR]))

    def test_intimidation_tactics_exiles_an_artifact_or_creature_only(self):
        game, a, b = table(INTIMIDATION_TACTICS, "Seat 1", "Bolt", "Relic")
        b.hand = [BOLT, RELIC, BEAR]
        game._perform(a, CAST + "Intimidation Tactics")
        run_stack(game)
        self.assertEqual((b.hand, b.exile), ([BOLT, BEAR], [RELIC]))  # the instant was not offered

    def test_warlock_takes_your_choice_after_they_lost_life(self):
        game, a, b = table(WARLOCK, "Seat 1", "Bear")
        b.hand = [FOREST, BEAR]
        b.life_lost_turn, b.life_lost_amount = game.turn, 1
        game._perform(a, CAST + "Thought-Stalker Warlock")
        run_stack(game)
        self.assertEqual(b.graveyard, [BEAR])

    def test_warlock_lets_them_choose_otherwise(self):
        game, a, b = table(WARLOCK, "Seat 1", "Bear")
        b.hand = [FOREST, BEAR]  # their policy discards the first card offered
        game._perform(a, CAST + "Thought-Stalker Warlock")
        run_stack(game)
        self.assertEqual(b.graveyard, [FOREST])


if __name__ == "__main__":
    unittest.main()
