"""The three prepare cards of issue #85 whose text the issue cut off, with their full Oracle text from Scryfall.

Emeritus of Truce, Stensian Sanguinist and Yavimaya Bloomsage. Each has a case where the condition is false and the
creature must stay unprepared. The spell halves are not written here.
"""

import unittest

from infernal_machine.cards import Card
from infernal_machine.combat import Combat
from infernal_machine.game import Permanent
from tests.test_combat import BEAR
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_prepare_85 import fire, prepper, supported
from tests.test_x_targets import script

BEHEMOTH = Card(name="Behemoth", type_line="Creature — Beast", power="6", toughness="6")

TRUCE = prepper("When this creature enters, target player creates a 1/1 white and black Inkling creature token with flying. "
                "Then if an opponent controls more creatures than you, this creature becomes prepared.", "Truce")


class EmeritusOfTruceTests(unittest.TestCase):
    def enter(self, target, mine, theirs):
        game, _ = table3(script(target))
        a, b, _ = game.seats
        truce = Permanent(TRUCE)
        a.battlefield = [truce] + [Permanent(BEAR) for _ in range(mine)]
        b.battlefield = [Permanent(BEAR) for _ in range(theirs)]
        fire(game, a, truce, "enters")
        return game, truce

    def test_parse(self):
        supported(self, TRUCE)

    def test_prepared_when_an_opponent_controls_more_creatures(self):
        game, truce = self.enter("Player: A", mine=0, theirs=3)  # Truce and the Inkling make two, against three
        self.assertEqual(sum("Inkling" in p.card.name for p in game.seats[0].battlefield), 1)
        self.assertTrue(truce.prepared)

    def test_not_prepared_when_the_opponent_has_the_same_number(self):
        game, truce = self.enter("Player: A", mine=0, theirs=2)  # two against two
        self.assertFalse(truce.prepared)

    def test_the_targeted_opponent_gets_the_token_and_is_counted_with_it(self):
        game, truce = self.enter("Player: B", mine=0, theirs=0)  # one for me, one for them: not more
        self.assertEqual(sum("Inkling" in p.card.name for p in game.seats[1].battlefield), 1)
        self.assertFalse(truce.prepared)

    def test_the_token_counts_when_an_opponent_gets_it(self):
        game, truce = self.enter("Player: B", mine=0, theirs=1)  # one for me, two for them
        self.assertTrue(truce.prepared)


SANGUINIST = prepper("Whenever you attack, target creature gains deathtouch until end of turn. Whenever that creature deals "
                     "combat damage to a player this combat, this creature becomes prepared.", "Sanguinist")


class StensianSanguinistTests(unittest.TestCase):
    def attack(self, target="Bear"):
        game, _ = table3(script(target))
        a, b, _ = game.seats
        sanguinist, bear, ogre = Permanent(SANGUINIST), Permanent(BEAR), Permanent(BEAR)
        a.battlefield = [sanguinist, bear, ogre]
        game.combat = Combat(game)
        fire(game, a, sanguinist, "creatures_attack")
        return game, b, sanguinist, bear, ogre

    def test_parse(self):
        supported(self, SANGUINIST)

    def test_the_target_gains_deathtouch(self):
        game, _, _, bear, ogre = self.attack()
        self.assertEqual((game.has_keyword(bear, "deathtouch"), game.has_keyword(ogre, "deathtouch")), (True, False))

    def test_prepared_when_the_target_hits_a_player(self):
        game, b, sanguinist, bear, _ = self.attack()
        game.damage(b, 2, source=bear, combat=True)
        run_stack(game)
        self.assertTrue(sanguinist.prepared)

    def test_not_prepared_when_another_creature_hits_a_player(self):
        game, b, sanguinist, bear, ogre = self.attack()
        game.damage(b, 2, source=ogre, combat=True)
        run_stack(game)
        self.assertFalse(sanguinist.prepared)

    def test_not_prepared_when_the_target_only_hits_a_creature(self):
        game, b, sanguinist, bear, _ = self.attack()
        victim = Permanent(BEAR)
        b.battlefield = [victim]
        game.damage(victim, 2, source=bear, combat=True)
        run_stack(game)
        self.assertFalse(sanguinist.prepared)

    def test_not_prepared_when_the_damage_is_not_combat_damage(self):
        game, b, sanguinist, bear, _ = self.attack()
        game.damage(b, 2, source=bear)
        run_stack(game)
        self.assertFalse(sanguinist.prepared)

    def test_not_prepared_by_damage_after_the_combat_ends(self):
        game, b, sanguinist, bear, _ = self.attack()
        game.combat = Combat(game)  # creatures leave combat; the watch ended with it
        game.damage(b, 2, source=bear, combat=True)
        run_stack(game)
        self.assertFalse(sanguinist.prepared)

    def test_prepared_only_once_for_two_hits(self):
        game, b, sanguinist, bear, _ = self.attack()
        game.damage(b, 1, source=bear, combat=True)  # first strike, then regular damage
        game.damage(b, 1, source=bear, combat=True)
        run_stack(game)
        self.assertTrue(sanguinist.prepared)


BLOOMSAGE = prepper("At the beginning of your end step, put a +1/+1 counter on target creature you control. Then if that "
                    "creature has power 7 or greater, this creature becomes prepared.", "Bloomsage")


class YavimayaBloomsageTests(unittest.TestCase):
    def end_step(self, target, power):
        game, _ = table3(script(target))
        a = game.seats[0]
        bloomsage = Permanent(BLOOMSAGE)
        big = Permanent(Card(name="Behemoth", type_line="Creature — Beast", power=str(power), toughness="6"))
        a.battlefield = [bloomsage, big, Permanent(BEAR)]
        fire(game, a, bloomsage, "end_step")
        return bloomsage, big

    def test_parse(self):
        supported(self, BLOOMSAGE)

    def test_prepared_when_the_counter_makes_the_power_seven(self):
        bloomsage, big = self.end_step("Behemoth", power=6)
        self.assertEqual((big.counters.get("+1/+1"), bloomsage.prepared), (1, True))

    def test_not_prepared_when_the_power_stays_below_seven(self):
        bloomsage, big = self.end_step("Behemoth", power=5)
        self.assertEqual((big.counters.get("+1/+1"), bloomsage.prepared), (1, False))

    def test_the_power_of_another_creature_does_not_count(self):
        bloomsage, big = self.end_step("Bear", power=9)  # the Bear gets the counter; the 9-power creature is not that creature
        self.assertFalse(bloomsage.prepared)
