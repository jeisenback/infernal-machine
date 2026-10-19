"""Pieces found by running the coverage audit over real decklists (issue #428): the cost reductions and counts of a creature type
(Goblins, Dragons), mana for each creature, damage equal to a count, and poison counters from spells."""

import dataclasses
import unittest

from infernal_machine.effects import cost_reductions
from infernal_machine.game import CAST, PASS, TARGET_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, real, run_stack, table

WARCHIEF = real("Goblin Warchief", "{1}{R}{R}", "Creature — Goblin Warrior", "Goblin spells you cast cost {1} less to cast.\nGoblins you control have haste.", "2", "2")
SHAMAN = real("Dragonspeaker Shaman", "{1}{R}{R}", "Creature — Human Barbarian Shaman", "Dragon spells you cast cost {2} less to cast.", "2", "2")
MONUMENT = real("Hazoret's Monument", "{3}", "Legendary Artifact",
                "Red creature spells you cast cost {1} less to cast.\nWhenever you cast a creature spell, you may discard a card. If you do, draw a card.")
RAID = real("Massive Raid", "{1}{R}{R}", "Instant", "Massive Raid deals damage to any target equal to the number of creatures you control.")
WAR_STRIKE = real("Goblin War Strike", "{R}", "Sorcery", "Goblin War Strike deals damage to target player or planeswalker equal to the number of Goblins you control.")
HYMN = real("Battle Hymn", "{1}{R}", "Instant", "Add {R} for each creature you control.")
RITUAL = real("Brightstone Ritual", "{R}", "Instant", "Add {R} for each Goblin on the battlefield.")
GRENADE = real("Goblin Grenade", "{R}", "Sorcery", "As an additional cost to cast this spell, sacrifice a Goblin.\nGoblin Grenade deals 5 damage to any target.")
PROLOGUE = real("Prologue to Phyresis", "{1}{U}", "Instant", "Each opponent gets a poison counter.\nDraw a card.")
RATS = real("Ichor Rats", "{1}{B}{B}", "Creature — Phyrexian Rat",
            "Infect (This creature deals damage to creatures in the form of -1/-1 counters and to players in the form of poison counters.)\n"
            "When this creature enters, each player gets a poison counter.", "2", "1")
OUTBREAK = real("Phyresis Outbreak", "{2}{B}", "Sorcery",
                "Each opponent gets a poison counter. Then each creature your opponents control gets -1/-1 until end of turn for each poison counter its controller has.")
FALL = real("Vraska's Fall", "{2}{B}", "Instant", "Each opponent sacrifices a creature or planeswalker of their choice and gets a poison counter.")
GOBLIN = real("Test Goblin", "{R}", "Creature — Goblin", "", "1", "1")
DRAGON = real("Test Dragon", "{4}{R}{R}", "Creature — Dragon", "Flying", "5", "5")
RED_BEAR = dataclasses.replace(BEAR, name="Red Bear", colors=("R",), mana_cost="{1}{R}")
GREEN_BEAR = dataclasses.replace(BEAR, name="Green Bear", colors=("G",), mana_cost="{1}{G}")


def policy(card_name):
    """Cast `card_name`; aim every target at the opponent (seat 1); pass otherwise."""
    def choose(prompt, options):
        if prompt.startswith(TARGET_PROMPT):
            return next((i for i, o in enumerate(options) if "seat 1" in o), 0)
        return next((i for i, o in enumerate(options) if o.startswith(CAST + card_name)), options.index(PASS) if PASS in options else 0)
    return choose


def play(card, mine=(), theirs=(), mana=6):
    game, _, _ = table(policy(card.name))
    a, b = game.seats
    a.hand = [card]
    a.battlefield = lands(mana) + [Permanent(c) for c in mine]
    b.battlefield = [Permanent(c) for c in theirs]
    game._priority_round(a)
    run_stack(game)
    return game, a, b


class ParseTests(unittest.TestCase):
    def test_the_cards_are_fully_playable(self):
        for card in (WARCHIEF, SHAMAN, MONUMENT, RAID, WAR_STRIKE, HYMN, RITUAL, GRENADE, PROLOGUE, RATS, OUTBREAK, FALL):
            self.assertEqual(unsupported_lines(card), [], card.name)


class CostReductionTests(unittest.TestCase):
    def test_what_each_reduces(self):
        self.assertEqual(cost_reductions(WARCHIEF), [("goblin", 1)])
        self.assertEqual(cost_reductions(SHAMAN), [("dragon", 2)])
        self.assertEqual(cost_reductions(MONUMENT), [("red creature", 1)])

    def cost(self, source, spell):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(source)]
        return game.cost_reduction(a, spell)

    def test_a_goblin_spell_costs_one_less_and_another_creature_does_not(self):
        self.assertEqual(self.cost(WARCHIEF, GOBLIN), 1)
        self.assertEqual(self.cost(WARCHIEF, BEAR), 0)

    def test_a_dragon_spell_costs_two_less(self):
        self.assertEqual(self.cost(SHAMAN, DRAGON), 2)
        self.assertEqual(self.cost(SHAMAN, GOBLIN), 0)

    def test_a_red_creature_spell_and_not_a_green_one_or_a_red_instant(self):
        self.assertEqual(self.cost(MONUMENT, RED_BEAR), 1)
        self.assertEqual(self.cost(MONUMENT, GREEN_BEAR), 0)
        self.assertEqual(self.cost(MONUMENT, RAID), 0)


class CountTests(unittest.TestCase):
    def test_damage_equal_to_the_creatures_you_control(self):
        _, _, b = play(RAID, mine=[BEAR, BEAR, GOBLIN])
        self.assertEqual(b.life, 37)

    def test_the_damage_goes_to_what_the_card_says(self):
        from infernal_machine.effects import spell_effects

        self.assertEqual([getattr(e, "target", None) for e in spell_effects(RAID)], [None, "any"])
        self.assertEqual([getattr(e, "target", None) for e in spell_effects(WAR_STRIKE)], [None, "player or planeswalker"])

    def test_damage_equal_to_the_goblins_you_control_and_only_goblins(self):
        _, _, b = play(WAR_STRIKE, mine=[GOBLIN, GOBLIN, BEAR])
        self.assertEqual(b.life, 38)

    def test_mana_for_each_creature_you_control(self):
        game, a, _ = play(HYMN, mine=[BEAR, BEAR, GOBLIN])
        self.assertEqual(len(a.mana_pool), 3)

    def test_mana_for_each_goblin_on_the_battlefield_including_the_opponents(self):
        game, a, _ = play(RITUAL, mine=[GOBLIN, BEAR], theirs=[GOBLIN, GOBLIN])
        self.assertEqual(len(a.mana_pool), 3)


class AdditionalCostTests(unittest.TestCase):
    def test_a_goblin_is_sacrificed_and_nothing_else(self):
        _, a, b = play(GRENADE, mine=[GOBLIN, BEAR])
        self.assertEqual(b.life, 35)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if "Creature" in p.card.type_line), ["Bear"])

    def test_without_a_goblin_it_cannot_be_cast(self):
        _, a, b = play(GRENADE, mine=[BEAR])
        self.assertEqual((b.life, len(a.hand)), (40, 1))


class PoisonTests(unittest.TestCase):
    def test_each_opponent_gets_a_poison_counter(self):
        _, a, b = play(PROLOGUE)
        self.assertEqual((b.player_counters.get("poison", 0), a.player_counters.get("poison", 0)), (1, 0))

    def test_each_player_gets_one_when_the_rats_enter(self):
        _, a, b = play(RATS)
        self.assertEqual((a.player_counters.get("poison"), b.player_counters.get("poison")), (1, 1))

    def test_ten_counters_lose_the_game(self):
        game, a, b = play(PROLOGUE)
        game.give_poison(b, 9)
        game._check_state()
        self.assertTrue(b.lost)

    def test_the_outbreak_shrinks_each_opponents_creature_by_their_poison(self):
        game, a, b = play(OUTBREAK, theirs=[BEAR, dataclasses.replace(BEAR, name="Big Bear", power="4", toughness="4")])
        self.assertEqual(b.player_counters.get("poison"), 1)
        self.assertEqual(sorted((p.card.name, game.power(p)) for p in b.battlefield), [("Bear", 1), ("Big Bear", 3)])

    def test_the_outbreak_with_more_poison_shrinks_more_and_my_creatures_not_at_all(self):
        game, _, _ = table(policy("Phyresis Outbreak"))
        a, b = game.seats
        a.hand = [OUTBREAK]
        a.battlefield = lands(4) + [Permanent(BEAR)]
        b.battlefield = [Permanent(dataclasses.replace(BEAR, name="Big Bear", power="4", toughness="4"))]
        b.player_counters["poison"] = 2
        a.player_counters["poison"] = 5  # (the caster's own poison does not shrink the caster's creatures)
        game._priority_round(a)
        run_stack(game)
        self.assertEqual(game.power(b.battlefield[0]), 1)  # 4 - 3 poison
        self.assertEqual(game.power(a.battlefield[-1]), 2)

    def test_vraskas_fall_makes_the_opponent_sacrifice_and_poisons_them(self):
        _, a, b = play(FALL, theirs=[BEAR])
        self.assertEqual((b.battlefield, b.player_counters.get("poison")), ([], 1))

    def test_vraskas_fall_with_nothing_to_sacrifice_still_poisons(self):
        _, a, b = play(FALL)
        self.assertEqual(b.player_counters.get("poison"), 1)


class PluralTests(unittest.TestCase):
    def test_elves_count_as_elf(self):
        from infernal_machine.effects import outcomes

        self.assertEqual(outcomes._amount("the number of Elves on the battlefield").what, "Elf")
        self.assertEqual(outcomes._amount("the number of Wolves you control").what, "Wolf")


if __name__ == "__main__":
    unittest.main()
