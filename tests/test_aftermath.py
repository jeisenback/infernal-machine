"""Aftermath: the second half of a split card is cast only from the graveyard, and exiled afterwards."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, CAST_GRAVEYARD, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, LIBRARY, run_stack, script, scryfall, table3

CUT = {"name": "Cut", "type_line": "Sorcery", "mana_cost": "{1}{R}", "oracle_text": "Cut deals 4 damage to target creature."}
SIP = {"name": "Sip", "type_line": "Sorcery", "mana_cost": "{2}{U}",
       "oracle_text": "Aftermath (Cast this spell only from your graveyard. Then exile it.)\nDraw two cards."}
SMITE = {"name": "Smite", "type_line": "Instant", "mana_cost": "{W}",
         "oracle_text": "Aftermath (Cast this spell only from your graveyard. Then exile it.)\nSmite deals 2 damage to target creature."}
CARD = Card.from_scryfall(scryfall("split", CUT, SIP, cmc=5.0))
INSTANT_BACK = Card.from_scryfall(scryfall("split", CUT, SMITE, cmc=3.0))


def table(card, *answers, n=5, graveyard=True):
    game, _ = table3(script(*answers))
    a, b, _ = game.seats
    a.hand, a.graveyard = ([], [card]) if graveyard else ([card], [])
    a.battlefield, a.library = lands(n), list(LIBRARY)
    b.battlefield = [Permanent(BEAR)]
    return game, a, b


def graveyard_casts(game, a):
    return [x for x in game.legal_actions(a) if x.startswith(CAST_GRAVEYARD)]


class LoadingTests(unittest.TestCase):
    def test_the_aftermath_half_is_a_card_of_its_own_and_the_card_is_playable(self):
        self.assertEqual((CARD.alternate.name, CARD.alternate.mana_cost, CARD.other_face), ("Sip", "{2}{U}", ""))
        self.assertEqual(unsupported_lines(CARD), [])

    def test_a_half_that_is_not_understood_still_keeps_the_card_out(self):
        odd = Card.from_scryfall(scryfall("split", CUT, {**SIP, "oracle_text": "Aftermath\nFrobnicate the widgets."}))
        self.assertEqual(unsupported_lines(odd), ["Frobnicate the widgets."])

    def test_it_survives_the_cache(self):
        self.assertEqual(Card.from_dict(CARD.to_dict()).alternate, CARD.alternate)


class CastingTests(unittest.TestCase):
    def test_the_front_half_is_cast_from_the_hand_and_the_back_half_only_from_the_graveyard(self):
        game, a, _ = table(CARD, graveyard=False)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [CAST + "Cut // Sip"])
        self.assertEqual(graveyard_casts(game, a), [])

    def test_in_the_graveyard_only_the_back_half_is_offered(self):
        game, a, _ = table(CARD)
        self.assertEqual(graveyard_casts(game, a), [CAST_GRAVEYARD + "Sip"])
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [])

    def test_it_needs_the_mana(self):
        game, a, _ = table(CARD, n=2)
        self.assertEqual(graveyard_casts(game, a), [])

    def test_a_sorcery_half_waits_for_the_main_phase_and_an_instant_half_does_not(self):
        sorcery, a, _ = table(CARD)
        sorcery.step, sorcery.active = "end", 1
        self.assertEqual(graveyard_casts(sorcery, a), [])
        instant, a, _ = table(INSTANT_BACK, "Bear")
        instant.step, instant.active = "end", 1
        self.assertEqual(graveyard_casts(instant, a), [CAST_GRAVEYARD + "Smite"])

    def test_the_card_is_exiled_after_it_resolves_not_put_back_in_the_graveyard(self):
        game, a, _ = table(CARD)
        game._perform(a, CAST_GRAVEYARD + "Sip")
        self.assertEqual((a.graveyard, len(a.hand)), ([], 0))  # on the stack
        run_stack(game)
        self.assertEqual((len(a.hand), a.graveyard, [c.name for c in a.exile], a.exile_play), (2, [], ["Cut // Sip"], []))

    def test_it_is_exiled_when_countered_or_fizzled_too(self):
        game, a, b = table(INSTANT_BACK, "Bear")
        game._perform(a, CAST_GRAVEYARD + "Smite")
        game.counter(game.stack[-1])
        self.assertEqual((a.graveyard, [c.name for c in a.exile]), ([], ["Cut // Smite"]))
        game, a, b = table(INSTANT_BACK, "Bear")
        game._perform(a, CAST_GRAVEYARD + "Smite")
        b.battlefield.clear()
        run_stack(game)
        self.assertEqual((a.graveyard, [c.name for c in a.exile]), ([], ["Cut // Smite"]))

    def test_the_back_half_does_what_it_says_to_its_target(self):
        game, a, b = table(INSTANT_BACK, "Bear")
        game._perform(a, CAST_GRAVEYARD + "Smite")
        run_stack(game)
        game._check_state()
        self.assertEqual(b.battlefield, [])

    def test_the_whole_cycle_front_from_hand_then_back_from_the_graveyard(self):
        game, a, b = table(CARD, "Bear", graveyard=False, n=5)
        game._perform(a, CAST + "Cut // Sip")
        run_stack(game)
        game._check_state()
        self.assertEqual(([c.name for c in a.graveyard], b.battlefield), (["Cut // Sip"], []))
        game._perform(a, CAST_GRAVEYARD + "Sip")
        run_stack(game)
        self.assertEqual((a.graveyard, [c.name for c in a.exile], len(a.hand)), ([], ["Cut // Sip"], 2))

    def test_it_is_not_offered_once_exiled(self):
        game, a, _ = table(CARD)
        a.graveyard, a.exile = [], [CARD]
        self.assertEqual(graveyard_casts(game, a), [])


if __name__ == "__main__":
    unittest.main()
