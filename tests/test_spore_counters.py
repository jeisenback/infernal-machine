"""Remove N counters from this creature as a cost: the Thallids (Magic's Fallen Empires and later) put a spore counter on themselves at
each upkeep and trade three of them for a Saproling, a point of damage, a regeneration or a fog."""

import unittest

from infernal_machine.effects import activated_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import pick, real, run_stack, table3
from tests.test_activated import activation

THALLID = real("Thallid", "{G}", "Creature — Fungus", "At the beginning of your upkeep, put a spore counter on this creature.\n"
               "Remove three spore counters from this creature: Create a 1/1 green Saproling creature token.", "1", "1")
THORN = real("Thorn Thallid", "{3}{G}", "Creature — Fungus", "At the beginning of your upkeep, put a spore counter on this creature.\n"
             "Remove three spore counters from this creature: It deals 1 damage to any target.", "3", "2")
FERAL = real("Feral Thallid", "{2}{G}", "Creature — Fungus", "At the beginning of your upkeep, put a spore counter on this creature.\n"
             "Remove three spore counters from this creature: Regenerate this creature.", "2", "2")
MYCON = real("Utopia Mycon", "{3}{G}", "Creature — Fungus", "At the beginning of your upkeep, put a spore counter on this creature.\n"
             "Remove three spore counters from this creature: Create a 1/1 green Saproling creature token.\n"
             "Sacrifice a Saproling: Add one mana of any color.", "1", "1")
FARMER = real("Elvish Farmer", "{1}{G}{G}", "Creature — Elf Druid", "At the beginning of your upkeep, put a spore counter on this creature.\n"
              "Remove three spore counters from this creature: Create a 1/1 green Saproling creature token.\n"
              "Sacrifice a Saproling: You gain 2 life.", "1", "1")
OLD = real("Old Growth", "{2}{G}", "Creature — Treefolk", "{2}{G}, Remove a +1/+1 counter from this creature: Draw a card.", "2", "2")


def with_spores(card, spores, policy=None):
    game, _ = table3(policy)
    a = game.seats[0]
    thallid = Permanent(card, sick=False)
    thallid.counters["spore"] = spores
    a.battlefield = [thallid]
    return game, a, thallid


class ParseTests(unittest.TestCase):
    def test_the_cards_are_understood(self):
        for card in (THALLID, THORN, FERAL, MYCON, FARMER):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_the_count_is_kept(self):
        [ability] = activated_abilities(THALLID)
        self.assertEqual((ability.remove_counter, ability.remove_count), ("spore", 3))

    def test_a_single_counter_cost_still_counts_one(self):
        [ability] = activated_abilities(OLD)
        self.assertEqual((ability.remove_counter, ability.remove_count), ("+1/+1", 1))


class CostTests(unittest.TestCase):
    def test_it_needs_all_the_counters(self):
        for spores, offered in ((2, 0), (3, 1), (5, 1)):
            game, a, _ = with_spores(THALLID, spores)
            self.assertEqual(len(activation(game, a, "Remove three")), offered, spores)

    def test_it_removes_that_many_and_makes_a_saproling(self):
        game, a, thallid = with_spores(THALLID, 4)
        game._perform(a, activation(game, a, "Remove three")[0])
        run_stack(game)
        self.assertEqual(thallid.counters["spore"], 1)
        self.assertEqual([p.card.name for p in a.battlefield], ["Thallid", "Saproling"])

    def test_the_counters_are_gone_before_the_ability_resolves(self):
        game, a, thallid = with_spores(THALLID, 3)
        game._perform(a, activation(game, a, "Remove three")[0])
        self.assertEqual(thallid.counters.get("spore", 0), 0)
        self.assertEqual(len(game.stack), 1)

    def test_a_saproling_can_be_sacrificed_for_mana(self):
        game, a, _ = with_spores(MYCON, 3)
        game._perform(a, activation(game, a, "Remove three")[0])
        run_stack(game)
        self.assertEqual(len(activation(game, a, "Sacrifice a Saproling")), 1)


class EffectTests(unittest.TestCase):
    def test_one_damage_to_any_target(self):
        game, a, _ = with_spores(THORN, 3, pick("Player: B"))
        game._perform(a, activation(game, a, "Remove three")[0])
        run_stack(game)
        self.assertEqual([s.life for s in game.seats], [40, 39, 40])

    def test_regenerate_this_creature(self):
        game, a, feral = with_spores(FERAL, 3)
        game._perform(a, activation(game, a, "Remove three")[0])
        run_stack(game)
        self.assertEqual(feral.regeneration, 1)


if __name__ == "__main__":
    unittest.main()
