"""Cards the earlier passes left over: Victimize, Malakir Rebirth, Traverse the Outlands."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR, OGRE
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import real
from tests.test_x_targets import script

FOREST = Card(name="Forest", type_line="Basic Land — Forest", produced_mana=("G",))
ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
SWAMP = Card(name="Swamp", type_line="Basic Land — Swamp", produced_mana=("B",))
VICTIMIZE = real("Victimize", "{2}{B}", "Sorcery", "Choose two target creature cards in your graveyard. Sacrifice a creature. If you do, "
                 "return the chosen cards to the battlefield tapped.")
REBIRTH = real("Malakir Rebirth", "{B}", "Instant", "Choose target creature. You lose 2 life. Until end of turn, that creature gains "
               "\"When this creature dies, return it to the battlefield tapped under its owner's control.\"")
TRAVERSE = real("Traverse the Outlands", "{3}{G}", "Sorcery", "Search your library for up to X basic land cards, where X is the greatest power "
                "among creatures you control. Put those cards onto the battlefield tapped, then shuffle.")
IMP = real("Imp", "{B}", "Creature — Imp", "", "1", "1")


def names(seat):
    return sorted(p.card.name for p in seat.battlefield if p.card.name != "City of Brass")


def cast(card, *answers, mine=(), graveyard=(), library=(), n=6):
    game, _ = table3(script(*answers))
    a, b, c = game.seats
    a.hand, a.battlefield, a.graveyard, a.library = [card], lands(n) + [Permanent(x) for x in mine], list(graveyard), list(library)
    game._perform(a, CAST + card.name)
    run_stack(game)
    game._check_state()
    return game, a


class ParseTests(unittest.TestCase):
    def test_the_three_cards_are_understood(self):
        for card in (VICTIMIZE, REBIRTH, TRAVERSE):
            self.assertEqual(unsupported_lines(card), [], card.name)


class VictimizeTests(unittest.TestCase):
    def test_sacrifice_a_creature_and_two_creature_cards_return_tapped(self):
        game, a = cast(VICTIMIZE, "Bear", "Ogre", "Imp", mine=[IMP], graveyard=[BEAR, OGRE, FOREST])
        self.assertEqual(names(a), ["Bear", "Ogre"])
        self.assertTrue(all(p.tapped for p in a.battlefield if p.card.name in ("Bear", "Ogre")))
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Forest", "Imp", "Victimize"])

    def test_without_a_creature_to_sacrifice_nothing_returns(self):
        game, a = cast(VICTIMIZE, "Bear", "Ogre", graveyard=[BEAR, OGRE])
        self.assertEqual(names(a), [])
        self.assertEqual(sorted(c.name for c in a.graveyard), ["Bear", "Ogre", "Victimize"])

    def test_the_creature_cards_may_not_be_other_cards_and_must_be_two(self):
        asked = []

        def record(prompt, options):
            asked.append(list(options))
            return 0
        game, _ = table3(record)
        a = game.seats[0]
        a.hand, a.battlefield, a.graveyard = [VICTIMIZE], lands(3) + [Permanent(IMP)], [BEAR, FOREST, OGRE]
        game._perform(a, CAST + "Victimize")
        self.assertEqual(len(asked[0]), 2)  # first of two: only the creature cards
        self.assertTrue(all("Forest" not in label for label in asked[0]))
        self.assertNotIn("No target", asked[1])  # the second is not optional


class MalakirRebirthTests(unittest.TestCase):
    def test_you_lose_two_life_and_the_creature_comes_back_tapped_if_it_dies_this_turn(self):
        game, a = cast(REBIRTH, "Bear", mine=[BEAR])
        self.assertEqual(a.life, 38)
        [bear] = [p for p in a.battlefield if p.card.name == "Bear"]
        game.destroy(bear)
        run_stack(game)
        game._check_state()
        [again] = [p for p in a.battlefield if p.card.name == "Bear"]
        self.assertIsNot(again, bear)
        self.assertTrue(again.tapped)
        self.assertEqual(again.counters, {})
        self.assertEqual(a.graveyard[-1].name, "Malakir Rebirth")  # the Bear itself is back, not in the graveyard
        self.assertNotIn("Bear", [c.name for c in a.graveyard])

    def test_it_does_not_come_back_the_next_turn(self):
        game, a = cast(REBIRTH, "Bear", mine=[BEAR])
        [bear] = [p for p in a.battlefield if p.card.name == "Bear"]
        game.turn += 1
        game.destroy(bear)
        run_stack(game)
        game._check_state()
        self.assertEqual(names(a), [])
        self.assertIn("Bear", [c.name for c in a.graveyard])

    def test_only_the_chosen_creature_gets_it(self):
        game, a = cast(REBIRTH, "Ogre", mine=[BEAR, OGRE])
        [bear] = [p for p in a.battlefield if p.card.name == "Bear"]
        game.destroy(bear)
        run_stack(game)
        self.assertEqual(names(a), ["Ogre"])

    def test_persist_and_undying_still_put_their_counter_on_the_creature(self):
        game, _ = table3()
        a = game.seats[0]
        dead = Permanent(BEAR)
        a.battlefield = [dead]
        game.destroy(dead)
        game.return_with_counter(dead, "+1/+1")
        self.assertEqual([p.counters for p in a.battlefield], [{"+1/+1": 1}])


class TraverseTests(unittest.TestCase):
    def test_up_to_x_basic_lands_where_x_is_the_greatest_power(self):
        game, a = cast(TRAVERSE, "Forest", "Island", "Swamp", mine=[OGRE, BEAR], library=[FOREST, ISLAND, SWAMP, FOREST])
        lands_in_play = [p for p in a.battlefield if p.card.name in ("Forest", "Island", "Swamp")]
        self.assertEqual(sorted(p.card.name for p in lands_in_play), ["Forest", "Island", "Swamp"])
        self.assertTrue(all(p.tapped for p in lands_in_play))
        self.assertEqual([c.name for c in a.library], ["Forest"])

    def test_with_no_creature_it_finds_nothing(self):
        game, a = cast(TRAVERSE, library=[FOREST, ISLAND])
        self.assertEqual(len(a.library), 2)

    def test_fewer_lands_than_x_are_all_it_can_find(self):
        game, a = cast(TRAVERSE, "Forest", mine=[OGRE], library=[FOREST, real("Plains Gate", "", "Land", "")])
        self.assertEqual(sorted(p.card.name for p in a.battlefield if p.card.name == "Forest"), ["Forest"])
        self.assertEqual(len(a.library), 1)


if __name__ == "__main__":
    unittest.main()
