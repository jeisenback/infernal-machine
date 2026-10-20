"""Madness (#216), played from the cards' own Oracle text."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import ACTIVATE, CAST, MADNESS_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_ability_costs import LOOTER, MOUNTAIN, settle
from tests.test_effects import lands, pick, table
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_triggers_80 import BIG, FOREST

REMINDER = ("(If you discard this card, discard it into exile. When you do, cast it for its madness cost or put it into your "
            "graveyard.)")
SEARCH = Card(name="Obsessive Search", mana_cost="{U}", cmc=1, type_line="Instant",
              oracle_text="Draw a card.\nMadness {U} " + REMINDER)
AGONY = Card(name="Terminal Agony", mana_cost="{2}{B}{R}", cmc=4, type_line="Instant",
             oracle_text="Destroy target creature.\nMadness {B}{R} " + REMINDER)
ROOTWALLA = Card(name="Basking Rootwalla", mana_cost="{1}{G}", cmc=2, type_line="Creature — Lizard", power="1", toughness="1",
                 oracle_text="{1}{G}: Basking Rootwalla gets +2/+2 until end of turn. Activate only once each turn.\nMadness {0} " + REMINDER)
SPARE = Card(name="Spare", mana_cost="{1}", cmc=1, type_line="Sorcery", oracle_text="Draw a card.")
WATCHER = Card(name="Watcher", mana_cost="{1}", cmc=1, type_line="Creature — Bear", power="1", toughness="1",
               oracle_text="Whenever you discard a card, you gain 1 life.")
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))


class Asked:
    """Answers the madness question with `answer` and records it; everything else gets the first option."""

    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def __call__(self, prompt, options):
        if MADNESS_PROMPT.matches(prompt):
            self.prompts.append(prompt)
            return options.index(self.answer)
        return 0


def setup(card, policy, lands_=(), battlefield=()):
    game, _ = table3(policy)
    a = game.seats[0]
    a.hand = [card]
    a.library = [FOREST] * 5
    a.battlefield = list(battlefield) + [Permanent(land) for land in lands_]
    return game, a


def tapped(seat):
    return sum(p.tapped for p in seat.battlefield)


class MadnessTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for card in (SEARCH, AGONY, ROOTWALLA):
            with self.subTest(card.name):
                self.assertFalse([line for line in unsupported_lines(card) if line.startswith("Madness")])
        self.assertEqual(unsupported_lines(SEARCH), [])
        self.assertEqual(unsupported_lines(AGONY), [])

    def test_a_discarded_card_may_be_cast_for_its_madness_cost(self):
        asked = Asked("Yes")
        game, a = setup(SEARCH, asked, [ISLAND, ISLAND])
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual(len(asked.prompts), 1)
        self.assertEqual(tapped(a), 1)  # {U}, not the {U} mana cost plus anything
        self.assertEqual(len(a.hand), 1)  # Obsessive Search drew a card
        self.assertEqual([c.name for c in a.graveyard], ["Obsessive Search"])
        self.assertEqual(a.exile, [])

    def test_declining_puts_it_into_the_graveyard_and_spends_nothing(self):
        asked = Asked("No")
        game, a = setup(SEARCH, asked, [ISLAND])
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual(len(asked.prompts), 1)
        self.assertEqual([c.name for c in a.graveyard], ["Obsessive Search"])
        self.assertEqual((tapped(a), a.hand, a.exile), (0, [], []))

    def test_it_is_not_offered_when_the_cost_cannot_be_paid(self):
        asked = Asked("Yes")
        game, a = setup(SEARCH, asked)
        game.discard(a, 1)
        self.assertEqual(asked.prompts, [])
        self.assertEqual(([c.name for c in a.graveyard], a.exile), (["Obsessive Search"], []))

    def test_a_card_without_madness_goes_straight_to_the_graveyard(self):
        asked = Asked("Yes")
        game, a = setup(SPARE, asked, [ISLAND])
        game.discard(a, 1)
        self.assertEqual((asked.prompts, [c.name for c in a.graveyard]), ([], ["Spare"]))

    def test_the_madness_cost_replaces_the_mana_cost(self):
        game, a = setup(AGONY, Asked("Yes"), [SWAMP, MOUNTAIN], [Permanent(BIG)])
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual(tapped(a), 2)  # {B}{R}, not {2}{B}{R}
        self.assertEqual([c.name for c in a.graveyard][-1:], ["Terminal Agony"])

    def test_a_card_with_no_legal_target_goes_to_the_graveyard_not_stuck_in_exile(self):
        game, a = setup(AGONY, Asked("Yes"), [SWAMP, MOUNTAIN])
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], a.exile), (["Terminal Agony"], []))

    def test_a_madness_creature_enters_the_battlefield(self):
        game, a = setup(ROOTWALLA, Asked("Yes"))
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield], ["Basking Rootwalla"])  # madness {0}: nothing to pay
        self.assertEqual((a.graveyard, a.exile), ([], []))

    def test_discard_triggers_still_happen(self):
        game, a = setup(SEARCH, Asked("Yes"), [ISLAND], [Permanent(WATCHER)])
        life = a.life
        game.discard(a, 1)
        run_stack(game)
        self.assertEqual(a.life, life + 1)

    def test_discarding_as_a_cost_works_too(self):
        asked = Asked("Yes")
        game, _, _ = table(lambda prompt, options: asked(prompt, options) if MADNESS_PROMPT.matches(prompt) else pick(ACTIVATE)(prompt, options))
        a = game.seats[0]
        a.battlefield = [Permanent(LOOTER)] + [Permanent(MOUNTAIN)] + [Permanent(ISLAND)] + [Permanent(ISLAND)]
        a.hand = [SEARCH]
        a.library = [FOREST] * 5
        settle(game)
        self.assertEqual(len(asked.prompts), 1)
        self.assertEqual(a.exile, [])

    def test_a_card_discarded_to_hand_size_at_cleanup_may_be_cast(self):
        asked = Asked("Yes")
        game, a = setup(SEARCH, asked, [ISLAND])
        a.hand = [SEARCH] + [SPARE] * 7  # eight cards: one too many
        game.step = "cleanup"
        game._turn_based_actions(a)
        run_stack(game)
        self.assertEqual(len(asked.prompts), 1)
        self.assertEqual([c.name for c in a.graveyard], ["Obsessive Search"])

    def test_a_card_taken_by_a_discard_effect_that_picks_it_may_be_cast_by_its_owner(self):
        asked = Asked("Yes")
        game, _ = table3(lambda prompt, options: 0, asked)
        a, b = game.seats[0], game.seats[1]
        b.hand, b.library = [SEARCH], [FOREST] * 5
        b.battlefield = [Permanent(ISLAND)]
        game.reveal_and_discard(a, b, (), None)
        run_stack(game)
        self.assertEqual(len(asked.prompts), 1)
        self.assertEqual((tapped(b), len(b.hand)), (1, 1))

    def test_a_card_discarded_as_an_additional_cost_may_be_cast(self):
        asked = Asked("Yes")
        pitcher = Card(name="Pitcher", mana_cost="{1}", cmc=1, type_line="Sorcery",
                       oracle_text="As an additional cost to cast this spell, discard a card.\nYou gain 3 life.")
        game, a = setup(pitcher, asked, [ISLAND, ISLAND, ISLAND])
        a.hand = [pitcher, SEARCH]
        game._perform(a, CAST + "Pitcher")
        run_stack(game)
        self.assertEqual(len(asked.prompts), 1)
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Obsessive Search", "Pitcher"])
        self.assertEqual(a.life, 43)


if __name__ == "__main__":
    unittest.main()
