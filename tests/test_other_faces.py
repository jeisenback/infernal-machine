"""The other half of a card cast from the hand: an Adventure (then the creature from exile), a split card's halves and a modal
card's back spell."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, CAST_EXILE, FOREVER, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, LIBRARY, run_stack, script, scryfall, table3


GIANT = {"name": "Giant", "type_line": "Creature — Giant", "mana_cost": "{2}{R}", "oracle_text": "", "power": "3", "toughness": "3"}
STOMP = {"name": "Stomp", "type_line": "Instant — Adventure", "mana_cost": "{1}{R}", "oracle_text": "Stomp deals 2 damage to target creature."}
RITUAL = {"name": "Ritual", "type_line": "Sorcery — Adventure", "mana_cost": "{U}", "oracle_text": "Draw a card."}
FIRE = {"name": "Fire", "type_line": "Instant", "mana_cost": "{1}{R}", "oracle_text": "Fire deals 2 damage to target creature."}
ICE = {"name": "Ice", "type_line": "Instant", "mana_cost": "{1}{U}", "oracle_text": "Draw a card."}
DEMON = {"name": "Demon", "type_line": "Creature — Demon", "mana_cost": "{3}{B}", "oracle_text": "", "power": "4", "toughness": "4"}
BACK_SPELL = {"name": "Deadly Vanity", "type_line": "Sorcery", "mana_cost": "{1}{B}", "oracle_text": "Draw a card."}
ADVENTURER = Card.from_scryfall(scryfall("adventure", GIANT, STOMP, colors=["R"]))
SORCERY_ADVENTURER = Card.from_scryfall(scryfall("adventure", GIANT, RITUAL, colors=["R"]))
SPLIT = Card.from_scryfall(scryfall("split", FIRE, ICE, cmc=4.0))
MODAL = Card.from_scryfall(scryfall("modal_dfc", DEMON, BACK_SPELL, cmc=4.0))


def table(card, *answers, n=5):
    game, _ = table3(script(*answers))
    a, b, _ = game.seats
    a.hand, a.battlefield, a.library = [card], lands(n), list(LIBRARY)
    b.battlefield = [Permanent(BEAR)]
    return game, a, b


def cast(game, a, name):
    game._perform(a, CAST + name)
    run_stack(game)
    game._check_state()


class LoadingTests(unittest.TestCase):
    def test_the_adventure_is_a_card_of_its_own(self):
        other = ADVENTURER.alternate
        self.assertEqual((other.name, other.mana_cost, other.cmc, other.colors, other.type_line),
                         ("Stomp", "{1}{R}", 2.0, ("R",), "Instant — Adventure"))
        self.assertEqual((ADVENTURER.name, ADVENTURER.cmc, ADVENTURER.other_face), ("Giant // Stomp", 3.0, ""))

    def test_each_half_of_a_split_card_has_its_own_cost_and_colors(self):
        self.assertEqual((SPLIT.cmc, SPLIT.colors, SPLIT.alternate.cmc, SPLIT.alternate.colors), (2.0, ("R",), 2.0, ("U",)))

    def test_a_card_can_be_played_only_when_both_halves_are_understood(self):
        self.assertEqual([unsupported_lines(c) for c in (ADVENTURER, SPLIT, MODAL)], [[], [], []])
        odd = Card.from_scryfall(scryfall("adventure", GIANT, {**STOMP, "oracle_text": "Frobnicate the widgets."}))
        self.assertEqual(unsupported_lines(odd), ["Frobnicate the widgets."])

    def test_the_halves_survive_the_cache(self):
        self.assertEqual(Card.from_dict(ADVENTURER.to_dict()).alternate, ADVENTURER.alternate)


class AdventureTests(unittest.TestCase):
    def test_both_the_creature_and_the_adventure_can_be_cast_from_the_hand(self):
        game, a, _ = table(ADVENTURER)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [CAST + "Giant // Stomp", CAST + "Stomp"])

    def test_the_adventure_does_what_it_says_and_the_card_goes_on_an_adventure(self):
        game, a, b = table(ADVENTURER, "Bear", n=2)
        cast(game, a, "Stomp")
        self.assertEqual([p.card.name for p in b.battlefield], [])  # the 2/2 Bear died
        self.assertEqual(([c.name for c in a.exile], a.graveyard, a.hand), (["Giant // Stomp"], [], []))
        self.assertEqual(a.exile_play, [(ADVENTURER, FOREVER)])

    def test_the_creature_is_then_cast_from_exile_for_as_long_as_it_stays(self):
        game, a, b = table(ADVENTURER, "Bear", n=5)
        cast(game, a, "Stomp")
        game.turn += 5  # not just this turn
        self.assertIn(CAST_EXILE + "Giant // Stomp", game.legal_actions(a))
        game._perform(a, CAST_EXILE + "Giant // Stomp")
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], ["Giant // Stomp"])
        self.assertEqual((a.exile, a.exile_play), ([], []))

    def test_an_adventure_that_is_countered_goes_to_the_graveyard_not_on_an_adventure(self):
        game, a, b = table(ADVENTURER, "Bear", n=2)
        game._perform(a, CAST + "Stomp")
        game.counter(game.stack[-1])
        self.assertEqual(([c.name for c in a.graveyard], a.exile, a.exile_play), (["Giant // Stomp"], [], []))

    def test_an_adventure_whose_target_is_gone_goes_to_the_graveyard(self):
        game, a, b = table(ADVENTURER, "Bear", n=2)
        game._perform(a, CAST + "Stomp")
        b.battlefield.clear()  # the spell fizzles
        run_stack(game)
        self.assertEqual(([c.name for c in a.graveyard], a.exile), (["Giant // Stomp"], []))

    def test_an_instant_adventure_can_be_cast_when_the_creature_cannot(self):
        game, a, _ = table(ADVENTURER)
        game.step, game.active = "end", 1  # on someone else's turn, with nothing to do
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [CAST + "Stomp"])

    def test_a_sorcery_adventure_waits_for_the_main_phase(self):
        game, a, _ = table(SORCERY_ADVENTURER)
        game.step, game.active = "end", 1
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [])
        game.step, game.active = "main1", 0
        self.assertIn(CAST + "Ritual", game.legal_actions(a))

    def test_the_adventure_is_not_offered_without_the_mana_for_it(self):
        game, a, _ = table(ADVENTURER, n=1)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [])

    def test_the_adventure_is_cast_as_the_adventure_not_as_a_creature_spell(self):
        game, a, _ = table(ADVENTURER, "Bear", n=2)
        game._perform(a, CAST + "Stomp")
        item = game.stack[-1]
        self.assertEqual((item.card.name, item.physical.name, "Creature" in item.card.type_line), ("Stomp", "Giant // Stomp", False))

    def test_the_creature_cast_normally_is_unaffected(self):
        game, a, _ = table(ADVENTURER, n=3)
        cast(game, a, "Giant // Stomp")
        self.assertEqual([p.card.name for p in a.battlefield if "Land" not in p.card.type_line], ["Giant // Stomp"])
        self.assertEqual(a.exile, [])


class SplitTests(unittest.TestCase):
    def test_either_half_can_be_cast_and_the_card_goes_to_the_graveyard(self):
        game, a, b = table(SPLIT, "Bear", n=4)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [CAST + "Fire // Ice", CAST + "Ice"])
        cast(game, a, "Ice")
        self.assertEqual((len(a.hand), [c.name for c in a.graveyard]), (1, ["Fire // Ice"]))  # drew the filler

    def test_the_first_half_is_cast_under_its_own_cost(self):
        game, a, b = table(SPLIT, "Bear", n=2)
        cast(game, a, "Fire // Ice")
        self.assertEqual(([p.card.name for p in b.battlefield], [c.name for c in a.graveyard]), ([], ["Fire // Ice"]))

    def test_only_the_half_that_can_be_paid_for_is_offered(self):
        game, a, _ = table(SPLIT, n=2)
        a.battlefield = [Permanent(Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))) for _ in range(2)]
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [CAST + "Fire // Ice"])


class ModalBackTests(unittest.TestCase):
    def test_the_back_spell_is_cast_from_the_hand_and_the_card_goes_to_the_graveyard(self):
        game, a, _ = table(MODAL, n=4)
        self.assertEqual([x for x in game.legal_actions(a) if x.startswith(CAST)], [CAST + "Demon // Deadly Vanity", CAST + "Deadly Vanity"])
        cast(game, a, "Deadly Vanity")
        self.assertEqual((len(a.hand), [c.name for c in a.graveyard]), (1, ["Demon // Deadly Vanity"]))


if __name__ == "__main__":
    unittest.main()
