"""Warp: cast a creature for its warp cost, and it is exiled at the next end step; it may be cast from exile on a later turn."""

import unittest

from infernal_machine.effects import alternative_costs
from infernal_machine.game import CAST, CAST_EXILE, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import lands, real, run_stack, script, table3

HOUND = real("Rayblade Trooper", "{3}{W}", "Creature — Human Soldier", "Warp {1}{W} (You may cast this card from your hand for its warp cost. "
             "Exile this creature at the beginning of the next end step, then you may cast it from exile on a later turn.)", "3", "3")
PLAIN = real("Plain Bear", "{1}{G}", "Creature — Bear", "", "2", "2")


def table(mana=2, hand=(HOUND,), policy=None):
    game, _ = table3(policy or script("Warp"))
    a = game.seats[0]
    a.hand, a.graveyard, a.exile, a.exile_play = list(hand), [], [], []
    a.battlefield = lands(mana)
    game.turn, game.step = 2, "main1"
    return game, a


def end_step(game, seat):
    game.step = "end"
    game._turn_based_actions(seat)
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_the_card_is_understood(self):
        self.assertEqual(unsupported_lines(HOUND), [])

    def test_warp_is_an_alternative_cost(self):
        [way] = [w for w in alternative_costs(HOUND) if w.warp]
        self.assertEqual((way.mana_cost, way.text), ("{1}{W}", "Warp {1}{W}"))


class CastTests(unittest.TestCase):
    def test_it_is_cast_for_the_warp_cost(self):
        game, a = table(mana=2)
        self.assertIn(CAST + HOUND.name, game.legal_actions(a))
        game._perform(a, CAST + HOUND.name)
        run_stack(game)
        self.assertEqual([p.card.name for p in a.battlefield[2:]], ["Rayblade Trooper"])
        self.assertEqual(game._mana_sources(a), [])

    def test_it_cannot_be_cast_for_less_without_warp(self):
        game, a = table(mana=1)
        self.assertNotIn(CAST + HOUND.name, game.legal_actions(a))

    def test_at_the_end_step_it_is_exiled(self):
        game, a = table(mana=2)
        game._perform(a, CAST + HOUND.name)
        run_stack(game)
        end_step(game, a)
        self.assertEqual(a.battlefield[2:], [])
        self.assertEqual(a.exile, [HOUND])
        self.assertEqual(a.graveyard, [])

    def test_it_stays_until_the_end_step(self):
        game, a = table(mana=2)
        game._perform(a, CAST + HOUND.name)
        run_stack(game)
        game.step = "combat"
        game._check_state()
        self.assertEqual(len(a.battlefield), 3)

    def test_it_can_be_cast_from_exile_on_a_later_turn(self):
        game, a = table(mana=4)
        game._perform(a, CAST + HOUND.name)
        run_stack(game)
        end_step(game, a)
        self.assertNotIn(CAST_EXILE + HOUND.name, [x for x in game.legal_actions(a) if game.step == "main1"])
        game.turn, game.step = 3, "main1"
        for permanent in a.battlefield:
            permanent.tapped = False
        self.assertIn(CAST_EXILE + HOUND.name, game.legal_actions(a))

    def test_the_cast_from_exile_costs_its_full_mana_cost_and_stays(self):
        game, a = table(mana=4, policy=script("Warp", "Pay"))
        game._perform(a, CAST + HOUND.name)
        run_stack(game)
        end_step(game, a)
        game.turn, game.step = 3, "main1"
        for permanent in a.battlefield:
            permanent.tapped = False
        a.battlefield = a.battlefield[:2]  # two lands are not enough for {3}{W}
        self.assertNotIn(CAST_EXILE + HOUND.name, game.legal_actions(a))
        a.battlefield = lands(4)
        game._perform(a, CAST_EXILE + HOUND.name)
        run_stack(game)
        self.assertEqual(len([p for p in a.battlefield if p.card is HOUND]), 1)
        end_step(game, a)
        self.assertEqual(len([p for p in a.battlefield if p.card is HOUND]), 1)

    def test_warp_is_not_offered_again_from_exile(self):
        seen = []

        def policy(prompt, options):
            seen.append(options)
            return next((i for i, o in enumerate(options) if o.startswith("Warp")), 0)
        game, a = table(mana=4, policy=policy)
        game._perform(a, CAST + HOUND.name)
        run_stack(game)
        end_step(game, a)
        game.turn, game.step = 3, "main1"
        for permanent in a.battlefield:
            permanent.tapped = False
        seen.clear()
        game._perform(a, CAST_EXILE + HOUND.name)
        self.assertEqual([options for options in seen if any(o.startswith("Warp") for o in options)], [])

    def test_a_hard_cast_creature_is_not_exiled(self):
        game, a = table(mana=4, policy=script("Pay"))
        game._perform(a, CAST + HOUND.name)
        run_stack(game)
        end_step(game, a)
        self.assertEqual(len([p for p in a.battlefield if p.card is HOUND]), 1)
        self.assertEqual(a.exile, [])

    def test_a_creature_that_died_first_stays_in_the_graveyard(self):
        game, a = table(mana=2)
        game._perform(a, CAST + HOUND.name)
        run_stack(game)
        game.destroy(a.battlefield[-1])
        end_step(game, a)
        self.assertEqual(a.graveyard, [HOUND])
        self.assertEqual(a.exile_play, [])

    def test_a_card_without_warp_is_unaffected(self):
        game, a = table(mana=2, hand=(PLAIN,))
        game._perform(a, CAST + PLAIN.name)
        run_stack(game)
        end_step(game, a)
        self.assertEqual(len(a.battlefield), 3)


ARDENT = real("Weftstalker Ardent", "{1}{R}", "Creature — Human Artificer", "Whenever another creature or artifact you control enters, this "
              "creature deals 1 damage to each opponent.\nWarp {R}", "2", "2")
VOIDBORN = real("Susurian Voidborn", "{2}{B}", "Creature — Vampire", "Whenever this creature or another creature or artifact you control dies, "
                "target opponent loses 1 life and you gain 1 life.\nWarp {B}", "2", "2")
HALIYA = real("Haliya, Guided by Light", "{1}{W}", "Legendary Creature — Human", "At the beginning of your end step, draw a card if you've "
              "gained 3 or more life this turn.\nWarp {W}", "3", "3")
TREASURE = real("Trinket", "{1}", "Artifact", "")


class CreatureOrArtifactTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (ARDENT, VOIDBORN, HALIYA):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_a_creature_or_an_artifact_entering_pings_each_opponent(self):
        for entering in (PLAIN, TREASURE):
            game, a = table(mana=0, hand=())
            a.battlefield = [Permanent(ARDENT, sick=False)]
            game._enter(a, Permanent(entering))
            run_stack(game)
            self.assertEqual(game.seats[1].life, 39, entering.name)

    def test_a_land_does_not(self):
        game, a = table(mana=0, hand=())
        a.battlefield = [Permanent(ARDENT, sick=False)]
        game._enter(a, Permanent(real("Plains", "", "Basic Land — Plains", "")))
        run_stack(game)
        self.assertEqual(game.seats[1].life, 40)

    def test_an_artifact_that_is_destroyed_drains(self):
        game, a = table(mana=0, hand=())
        trinket = Permanent(TREASURE)
        a.battlefield = [Permanent(VOIDBORN, sick=False), trinket]
        game.destroy(trinket)
        run_stack(game)
        self.assertEqual((game.seats[1].life, a.life), (39, 41))

    def test_drawing_at_the_end_step_only_after_gaining_three_life(self):
        for gained, drawn in ((3, 1), (2, 0)):
            game, a = table(mana=0, hand=())
            a.battlefield = [Permanent(HALIYA, sick=False)]
            a.library = [PLAIN] * 3
            game.change_life(a, gained)
            end_step(game, a)
            self.assertEqual(len(a.hand), drawn, gained)


if __name__ == "__main__":
    unittest.main()
