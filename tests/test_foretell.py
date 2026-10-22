"""Foretell: pay {2} on your turn to exile a card face down, then cast it from exile on a later turn for its foretell cost."""

import unittest

from infernal_machine.effects import foretell_of
from infernal_machine.game import CAST, CAST_FORETOLD, FORETELL, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, OGRE, real, run_stack, script, table3

CUP = real("Poison the Cup", "{1}{B}{B}", "Instant", "Destroy target creature. If this spell was foretold, scry 2.\nForetell {1}{B} (During your "
           "turn, you may pay {2} and exile this card from your hand face down. Cast it on a later turn for its foretell cost.)")
DOOMSKAR = real("Doomskar", "{3}{W}{W}", "Sorcery", "Destroy all creatures.\nForetell {1}{W}{W}")
STARNHEIM = real("Starnheim Unleashed", "{2}{W}{W}{W}", "Sorcery", "Create a 4/4 white Angel Warrior creature token with flying and vigilance. "
                 "If this spell was foretold, create X of those tokens instead.\nForetell {X}{X}{W}")
CHEAP = real("Cheap One", "{G}", "Instant", "You gain 1 life.\nForetell {0}")
PLAIN = real("Plain Sorcery", "{2}{R}", "Sorcery", "You gain 1 life.")


def table(*hand, mana=3, turn=2, step="main1"):
    game, _ = table3(script("Pass"))
    a = game.seats[0]
    a.hand, a.graveyard, a.exile, a.foretold = list(hand), [], [], []
    a.library = [BEAR, OGRE, BEAR, OGRE]
    a.battlefield = lands(mana)
    game.turn, game.step = turn, step
    return game, a


def foretell(game, seat, card):
    game._perform(seat, FORETELL + card.name)


def next_turn(game, seat):
    game.turn += 1
    for permanent in seat.battlefield:
        permanent.tapped = False


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (CUP, DOOMSKAR, STARNHEIM, CHEAP):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_cost_is_read(self):
        self.assertEqual(foretell_of(CUP), "{1}{B}")
        self.assertEqual(foretell_of(STARNHEIM), "{X}{X}{W}")
        self.assertIsNone(foretell_of(PLAIN))


class ForetellTests(unittest.TestCase):
    def test_it_goes_to_exile_for_two_mana(self):
        game, a = table(CUP, mana=3)
        self.assertIn(FORETELL + CUP.name, game.legal_actions(a))
        foretell(game, a, CUP)
        self.assertEqual(a.hand, [])
        self.assertEqual(a.exile, [CUP])
        self.assertEqual(a.foretold, [(2, CUP)])
        self.assertEqual(len(game._mana_sources(a)), 1)

    def test_it_needs_two_mana(self):
        game, a = table(CUP, mana=1)
        self.assertNotIn(FORETELL + CUP.name, game.legal_actions(a))

    def test_a_card_without_foretell_cannot_be(self):
        game, a = table(PLAIN)
        self.assertFalse([x for x in game.legal_actions(a) if x.startswith(FORETELL)])

    def test_not_on_another_players_turn(self):
        game, a = table(CUP)
        game.active = 1
        self.assertNotIn(FORETELL + CUP.name, game.legal_actions(a))

    def test_it_can_be_done_at_instant_speed_on_your_turn(self):
        game, a = table(CUP, step="declare_blockers")
        self.assertIn(FORETELL + CUP.name, game.legal_actions(a))

    def test_it_does_not_use_the_stack_or_a_land_drop(self):
        game, a = table(CUP)
        foretell(game, a, CUP)
        self.assertEqual(game.stack, [])
        self.assertEqual(a.lands_played, 0)


class WatcherTests(unittest.TestCase):
    def test_whenever_you_foretell_a_card_triggers(self):
        watcher = real("Foretell Fan", "{1}{U}", "Creature — Wizard", "Whenever you foretell a card, you gain 1 life.", "1", "1")
        self.assertEqual(unsupported_lines(watcher), [])
        game, a = table(CUP, mana=3)
        a.battlefield.append(Permanent(watcher, sick=False))
        foretell(game, a, CUP)
        run_stack(game)
        self.assertEqual(a.life, 41)


class CastTests(unittest.TestCase):
    def test_not_the_turn_it_was_foretold(self):
        game, a = table(CUP, mana=5)
        game.seats[1].battlefield = [Permanent(OGRE)]
        foretell(game, a, CUP)
        self.assertNotIn(CAST_FORETOLD + CUP.name, game.legal_actions(a))

    def test_on_a_later_turn_for_the_foretell_cost(self):
        game, a = table(CUP, mana=5)
        b = game.seats[1]
        b.battlefield = [Permanent(OGRE)]
        foretell(game, a, CUP)
        next_turn(game, a)
        self.assertIn(CAST_FORETOLD + CUP.name, game.legal_actions(a))
        game._perform(a, CAST_FORETOLD + CUP.name)
        run_stack(game)
        self.assertEqual(b.battlefield, [])
        self.assertEqual(a.exile, [])
        self.assertEqual(a.foretold, [])
        self.assertEqual([c.name for c in a.graveyard], ["Poison the Cup"])
        self.assertEqual(len(game._mana_sources(a)), 5 - 2)  # {1}{B}: not the card's {1}{B}{B}

    def test_not_without_the_foretell_cost(self):
        game, a = table(CUP, mana=2)
        foretell(game, a, CUP)
        next_turn(game, a)
        a.battlefield = []
        self.assertNotIn(CAST_FORETOLD + CUP.name, game.legal_actions(a))

    def test_a_sorcery_waits_for_a_main_phase(self):
        game, a = table(DOOMSKAR, mana=5)
        foretell(game, a, DOOMSKAR)
        next_turn(game, a)
        game.step = "combat"
        self.assertNotIn(CAST_FORETOLD + DOOMSKAR.name, game.legal_actions(a))
        game.step = "main2"
        self.assertIn(CAST_FORETOLD + DOOMSKAR.name, game.legal_actions(a))

    def test_an_instant_can_be_cast_during_combat(self):
        game, a = table(CUP, mana=5)
        game.seats[1].battlefield = [Permanent(OGRE)]
        foretell(game, a, CUP)
        next_turn(game, a)
        game.step = "declare_blockers"
        self.assertIn(CAST_FORETOLD + CUP.name, game.legal_actions(a))

    def test_it_is_not_cast_from_exile_the_normal_way(self):
        game, a = table(CUP, mana=5)
        foretell(game, a, CUP)
        next_turn(game, a)
        self.assertNotIn(CAST + CUP.name, game.legal_actions(a))

    def test_a_zero_foretell_cost(self):
        game, a = table(CHEAP, mana=2)
        foretell(game, a, CHEAP)
        next_turn(game, a)
        a.battlefield = []
        self.assertIn(CAST_FORETOLD + CHEAP.name, game.legal_actions(a))

    def test_a_cast_that_does_not_happen_leaves_it_foretold(self):
        game, a = table(CUP, mana=5)
        game.seats[1].battlefield = [Permanent(OGRE)]
        foretell(game, a, CUP)
        next_turn(game, a)
        game._cast = lambda *args, **kwargs: None  # the player backed out (no target, no X ...)
        game._perform(a, CAST_FORETOLD + CUP.name)
        self.assertEqual(a.foretold, [(2, CUP)])
        self.assertEqual(a.exile, [CUP])

    def test_an_uncastable_foretold_card_stays_foretold(self):
        game, a = table(CUP, mana=5)
        foretell(game, a, CUP)
        next_turn(game, a)  # no creature to destroy anywhere
        game.seats[0].battlefield = lands(5)
        self.assertNotIn(CAST_FORETOLD + CUP.name, game.legal_actions(a))
        self.assertEqual(a.foretold, [(2, CUP)])


class WasForetoldTests(unittest.TestCase):
    def prompts(self, foretold):
        seen = []

        def policy(prompt, options):
            seen.append(prompt)
            return 0
        game, _ = table3(policy)
        a, b = game.seats[:2]
        a.hand, a.exile, a.foretold, a.graveyard = [] if foretold else [CUP], [CUP] if foretold else [], [(1, CUP)] if foretold else [], []
        a.library = [BEAR, OGRE, BEAR]
        a.battlefield = lands(5)
        b.battlefield = [Permanent(OGRE)]
        game.turn, game.step = 2, "main1"
        game._perform(a, (CAST_FORETOLD if foretold else CAST) + CUP.name)
        run_stack(game)
        return [p for p in seen if p.startswith("Scry")]

    def test_scry_two_only_if_it_was_foretold(self):
        self.assertEqual(len(self.prompts(True)), 2)
        self.assertEqual(self.prompts(False), [])

    def test_x_tokens_if_it_was_foretold(self):
        game, _ = table3(script("Pass"))
        a = game.seats[0]
        a.hand, a.exile, a.foretold, a.graveyard = [], [STARNHEIM], [(1, STARNHEIM)], []
        a.battlefield = lands(7)
        game.turn, game.step = 2, "main1"
        game.seats[0].player.policy = lambda prompt, options: options.index("3") if "3" in options else 0
        game._perform(a, CAST_FORETOLD + STARNHEIM.name)
        run_stack(game)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Angel Warrior"]), 3)

    def test_one_token_if_it_was_not(self):
        game, _ = table3(script("Pass"))
        a = game.seats[0]
        a.hand, a.graveyard = [STARNHEIM], []
        a.battlefield = lands(5)
        game.turn, game.step = 2, "main1"
        game._perform(a, CAST + STARNHEIM.name)
        run_stack(game)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Angel Warrior"]), 1)


if __name__ == "__main__":
    unittest.main()
