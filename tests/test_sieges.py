"""Fate Reforged's Sieges (#658): "As this enchantment enters, choose Khans or Dragons." and the permanent has only the chosen ability
(Outpost Siege, Palace Siege, Citadel Siege, Frontier Siege). It leaves the battlefield as the printed card."""

import unittest

from infernal_machine.game import Permanent
from tests.helpers import BEAR, FOREST, OGRE, enter, fire, pick, real, run_stack, table

OUTPOST = real("Outpost Siege", "{3}{R}", "Enchantment",
               "As this enchantment enters, choose Khans or Dragons.\n• Khans — At the beginning of your upkeep, exile the top card of your "
               "library. Until end of turn, you may play that card.\n• Dragons — Whenever a creature you control leaves the battlefield, this "
               "enchantment deals 1 damage to any target.", colors=("R",))
PALACE = real("Palace Siege", "{3}{B}{B}", "Enchantment",
              "As this enchantment enters, choose Khans or Dragons.\n• Khans — At the beginning of your upkeep, return target creature card "
              "from your graveyard to your hand.\n• Dragons — At the beginning of your upkeep, each opponent loses 2 life and you gain 2 life.",
              colors=("B",))
CITADEL = real("Citadel Siege", "{2}{W}{W}", "Enchantment",
               "As this enchantment enters, choose Khans or Dragons.\n• Khans — At the beginning of combat on your turn, put two +1/+1 counters "
               "on target creature you control.\n• Dragons — At the beginning of combat on each opponent's turn, tap target creature that player "
               "controls.", colors=("W",))
FRONTIER = real("Frontier Siege", "{3}{G}", "Enchantment",
                "As this enchantment enters, choose Khans or Dragons.\n• Khans — At the beginning of each of your main phases, add {G}{G}.\n"
                "• Dragons — Whenever a creature you control with flying enters, you may have it fight target creature you don't control.",
                colors=("G",))
FLYER = real("Wind Drake", "{2}{U}", "Creature — Drake", "Flying", "2", "2", colors=("U",))
TOP = real("Top Card", "{1}", "Sorcery", "")


def siege(card, choice, *labels):
    game, _, _ = table(pick(choice, *labels), pick(*labels))
    mine, theirs = game.seats
    mine.library = [TOP, FOREST]
    permanent = enter(game, mine, card)
    run_stack(game)
    return game, mine, theirs, permanent


class OutpostSiegeTests(unittest.TestCase):
    def test_khans_exiles_the_top_card_at_upkeep_to_play_this_turn(self):
        game, mine, theirs, outpost = siege(OUTPOST, "Khans")
        fire(game, mine, outpost, "upkeep")
        self.assertEqual([(c.name, until) for c, until in mine.exile_play], [("Top Card", game.turn)])

    def test_khans_has_no_dragons_ability(self):
        game, mine, theirs, outpost = siege(OUTPOST, "Khans", "Player: B")
        bear = Permanent(BEAR, sick=False)
        mine.battlefield.append(bear)
        game.destroy(bear)
        run_stack(game)
        self.assertEqual(theirs.life, 40)

    def test_dragons_deals_1_damage_when_a_creature_leaves(self):
        game, mine, theirs, outpost = siege(OUTPOST, "Dragons", "Player: B")
        bear = Permanent(BEAR, sick=False)
        mine.battlefield.append(bear)
        game.destroy(bear)
        run_stack(game)
        self.assertEqual(theirs.life, 39)

    def test_dragons_has_no_khans_ability(self):
        game, mine, theirs, outpost = siege(OUTPOST, "Dragons")
        fire(game, mine, outpost, "upkeep")
        self.assertEqual(mine.exile_play, [])

    def test_it_leaves_the_battlefield_as_the_printed_card(self):
        game, mine, theirs, outpost = siege(OUTPOST, "Dragons")
        game.destroy(outpost)
        run_stack(game)
        self.assertEqual(mine.graveyard, [OUTPOST])


class PalaceSiegeTests(unittest.TestCase):
    def test_khans_returns_a_creature_card_at_upkeep(self):
        game, mine, theirs, palace = siege(PALACE, "Khans", "Bear")
        mine.graveyard = [BEAR]
        fire(game, mine, palace, "upkeep")
        self.assertEqual(mine.hand, [BEAR])

    def test_dragons_drains_2_at_upkeep(self):
        game, mine, theirs, palace = siege(PALACE, "Dragons")
        fire(game, mine, palace, "upkeep")
        self.assertEqual((mine.life, theirs.life), (42, 38))


class CitadelSiegeTests(unittest.TestCase):
    def test_khans_puts_two_counters_on_a_creature_at_your_combat(self):
        game, mine, theirs, citadel = siege(CITADEL, "Khans", "Bear")
        bear = Permanent(BEAR, sick=False)
        mine.battlefield.append(bear)
        fire(game, mine, citadel, "combat")
        self.assertEqual(bear.counters.get("+1/+1"), 2)

    def test_dragons_taps_a_creature_of_the_player_whose_combat_it_is(self):
        game, mine, theirs, citadel = siege(CITADEL, "Dragons", "Ogre")
        ogre = Permanent(OGRE, sick=False)
        theirs.battlefield = [ogre]
        game.active, game.step = 1, "beginning_of_combat"
        game._turn_based_actions(theirs)
        run_stack(game)
        self.assertTrue(ogre.tapped)

    def test_dragons_does_nothing_at_your_own_combat(self):
        game, mine, theirs, citadel = siege(CITADEL, "Dragons", "Bear")
        bear = Permanent(BEAR, sick=False)
        mine.battlefield.append(bear)
        game.step = "beginning_of_combat"
        game._turn_based_actions(mine)
        run_stack(game)
        self.assertFalse(bear.tapped)


class FrontierSiegeTests(unittest.TestCase):
    def test_khans_adds_gg_in_each_main_phase(self):
        game, mine, theirs, frontier = siege(FRONTIER, "Khans")
        for step in ("main1", "main2"):
            game.step = step
            mine.mana_pool = []
            game._turn_based_actions(mine)
            run_stack(game)
            self.assertEqual(mine.mana_pool, [frozenset("G")] * 2, step)

    def test_dragons_has_a_flyer_that_enters_fight(self):
        game, mine, theirs, frontier = siege(FRONTIER, "Dragons", "Yes", "Bear")
        bear = Permanent(BEAR, sick=False)
        theirs.battlefield = [bear]
        drake = enter(game, mine, FLYER)
        run_stack(game)
        self.assertEqual((bear.damage, drake.damage), (2, 2))  # the drake and the bear deal 2 to each other

    def test_dragons_ignores_a_creature_without_flying(self):
        game, mine, theirs, frontier = siege(FRONTIER, "Dragons", "Yes", "Bear")
        bear = Permanent(BEAR, sick=False)
        theirs.battlefield = [bear]
        enter(game, mine, OGRE)
        run_stack(game)
        self.assertEqual(bear.damage, 0)


if __name__ == "__main__":
    unittest.main()
