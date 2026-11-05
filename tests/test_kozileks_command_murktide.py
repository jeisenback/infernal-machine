"""Kozilek's Command ("Choose two — ... • Target player scries X, then draws a card. • Exile target creature with mana value X or less.
• Exile up to X target cards from graveyards.") and Murktide Regent ("This creature enters with a +1/+1 counter on it for each instant
and sorcery card exiled with it." and "Whenever an instant or sorcery card leaves your graveyard, put a +1/+1 counter on this creature.")."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, MODE_PROMPT, PUT_ON_BOTTOM, SCRY_PROMPT, X_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, BIG, BOLT, DIVINATION, FOREST, OGRE, lands, real, run_stack, table3

COMMAND = real("Kozilek's Command", "{X}{C}{C}", "Kindred Instant — Eldrazi", "Choose two —\n• Target player creates X 0/1 colorless Eldrazi "
               "Spawn creature tokens with \"Sacrifice this token: Add {C}.\"\n• Target player scries X, then draws a card.\n• Exile target "
               "creature with mana value X or less.\n• Exile up to X target cards from graveyards.")
MURKTIDE = real("Murktide Regent", "{5}{U}{U}", "Creature — Dragon", "Delve (Each card you exile from your graveyard while casting this spell "
                "pays for {1}.)\nFlying\nThis creature enters with a +1/+1 counter on it for each instant and sorcery card exiled with it.\n"
                "Whenever an instant or sorcery card leaves your graveyard, put a +1/+1 counter on this creature.", "3", "3", colors=("U",))
CRUISE = real("Treasure Cruise", "{7}{U}", "Sorcery", "Delve (Each card you exile from your graveyard while casting this spell pays for "
              "{1}.)\nDraw three cards.", colors=("U",))
CUNNING = real("Satyr's Cunning", "{R}", "Sorcery", "Create a 1/1 red Satyr creature token with \"This token can't block.\"\nEscape—{2}{R}, "
               "Exile two other cards from your graveyard. (You may cast this card from your graveyard for its escape cost.)", colors=("R",))
WASTES = Card(name="Wastes", type_line="Basic Land", produced_mana=("C",))
THINK_TWICE = real("Think Twice", "{1}{U}", "Instant", "Draw a card.\nFlashback {2}{U} (You may cast this card from your graveyard for its "
                   "flashback cost. Then exile it.)", colors=("U",))


def command(x, modes, battlefield=(), graveyard=()):
    """Seat 0 casts the Command with X and the two `modes` (their numbers, 0 to 3); seat 1 holds `battlefield` and `graveyard`."""
    wanted = iter(COMMAND_MODES[m] for m in modes)

    def policy(prompt, options):
        if X_PROMPT.matches(prompt):
            return options.index(str(x))
        if MODE_PROMPT.matches(prompt):
            return options.index(next(wanted))
        if SCRY_PROMPT.matches(prompt):
            return options.index(PUT_ON_BOTTOM)  # both scried cards go to the bottom
        return 0
    game, _ = table3(policy)
    a, b = game.seats[0], game.seats[1]
    a.hand, a.battlefield, a.library = [COMMAND], [Permanent(WASTES) for _ in range(x + 2)], [FOREST, OGRE, BEAR]
    b.battlefield, b.graveyard, b.exile = [Permanent(c) for c in battlefield], list(graveyard), []
    game.active, game.step = 0, "main1"
    game._perform(a, CAST + COMMAND.name)
    run_stack(game)
    return game, a, b


COMMAND_MODES = ("Target player creates X 0/1 colorless Eldrazi Spawn creature tokens with \"Sacrifice this token: Add {C}.\"",
                 "Target player scries X, then draws a card.", "Exile target creature with mana value X or less.",
                 "Exile up to X target cards from graveyards.")


class KozileksCommandTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(COMMAND), [])

    def test_scry_x_then_draw_and_exile_a_small_creature(self):
        _, a, b = command(2, (1, 2), battlefield=[BEAR])
        self.assertEqual(a.hand, [BEAR])  # the Forest and the Ogre went to the bottom; the Bear is drawn
        self.assertEqual(b.exile, [BEAR])

    def test_a_creature_above_any_x_it_can_pay_is_not_a_target(self):
        offered = []

        def policy(prompt, options):
            if MODE_PROMPT.matches(prompt):
                offered.append(list(options))
            return 0
        game, _ = table3(policy)
        a, b = game.seats[0], game.seats[1]
        a.hand, a.battlefield = [COMMAND], [Permanent(WASTES) for _ in range(4)]  # X can be at most 2
        b.battlefield = [Permanent(BIG)]  # mana value 5
        game.active, game.step = 0, "main1"
        game._perform(a, CAST + COMMAND.name)
        self.assertNotIn(COMMAND_MODES[2], offered[0])

    def test_exile_up_to_x_cards_from_graveyards(self):
        _, _, b = command(2, (3, 1), graveyard=[BEAR, OGRE, BOLT])
        self.assertEqual((len(b.exile), len(b.graveyard)), (2, 1))


class MurktideRegentTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(MURKTIDE), [])

    def test_it_enters_with_a_counter_for_each_instant_and_sorcery_delved(self):
        game, _ = table3(lambda prompt, options: 0)
        a = game.seats[0]
        a.hand, a.graveyard, a.battlefield = [MURKTIDE], [BOLT, DIVINATION, BEAR, OGRE, FOREST], lands(2)
        game.active, game.step = 0, "main1"
        game._perform(a, CAST + MURKTIDE.name)
        run_stack(game)
        regent = next(p for p in a.battlefield if p.card is MURKTIDE)
        self.assertEqual(regent.counters, {"+1/+1": 2})  # five cards delved, two of them an instant or a sorcery

    def test_an_instant_leaving_the_graveyard_adds_a_counter_and_a_creature_does_not(self):
        game, _ = table3(lambda prompt, options: 0)
        a = game.seats[0]
        regent = Permanent(MURKTIDE)
        a.battlefield, a.graveyard, a.hand = [regent] + lands(3), [THINK_TWICE, BEAR], []
        game.active, game.step = 0, "main1"
        game._perform(a, "Cast from graveyard: Think Twice")
        run_stack(game)
        self.assertEqual(regent.counters, {"+1/+1": 1})
        game.exile_own_graveyard(a, 1)  # the Bear
        run_stack(game)
        self.assertEqual(regent.counters, {"+1/+1": 1})

    def regent_watching(self, hand, graveyard, mana, action):
        game, _ = table3(lambda prompt, options: 0)
        a = game.seats[0]
        regent = Permanent(MURKTIDE)
        a.battlefield, a.graveyard, a.hand, a.library = [regent] + lands(mana), list(graveyard), list(hand), [FOREST] * 5
        game.active, game.step = 0, "main1"
        game._perform(a, action)
        run_stack(game)
        return regent.counters.get("+1/+1", 0)

    def test_an_instant_delved_by_another_spell_adds_a_counter(self):
        self.assertEqual(self.regent_watching([CRUISE], [BOLT, BEAR, OGRE, FOREST, BIG, BEAR, OGRE], 1, CAST + "Treasure Cruise"), 1)

    def test_instants_exiled_to_escape_add_counters(self):  # the two others exiled, and the escaping sorcery itself
        self.assertEqual(self.regent_watching([], [CUNNING, BOLT, DIVINATION], 3, "Cast from graveyard: Satyr's Cunning"), 3)


if __name__ == "__main__":
    unittest.main()
