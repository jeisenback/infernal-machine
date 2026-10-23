"""tools/ability_smoke.py: for each activated ability of the fully playable cards, a table that can pay its cost, the activation performed, and
a check that the cost was paid. The cards are real: Goblin Warrens (a plural sacrifice cost that once matched no creature), Amugaba (a
discard), Cabal Patriarch (an exile from the graveyard), Spike Feeder (a counter), Aetherflux Reservoir (life), Cauldron Familiar (a
graveyard ability that sacrifices a Food)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import ability_smoke  # noqa: E402

from infernal_machine.effects import activated_abilities  # noqa: E402
from tests.helpers import real  # noqa: E402

WARRENS = real("Goblin Warrens", "{3}{R}", "Enchantment", "{2}{R}, Sacrifice two Goblins: Create three 1/1 red Goblin creature tokens.", colors=("R",))
AMUGABA = real("Amugaba", "{3}{U}{U}", "Creature — Eldrazi Horror", "{2}{U}, Discard a card: Return this creature to its owner's hand.", "5", "5",
               colors=("U",))
PATRIARCH = real("Cabal Patriarch", "{2}{B}{B}", "Creature — Human Wizard",
                 "{2}{B}, Sacrifice a creature: Target creature gets -2/-2 until end of turn.\n{2}{B}, Exile a creature card from your graveyard: "
                 "Target creature gets -2/-2 until end of turn.", "4", "4", colors=("B",))
SPIKE = real("Spike Feeder", "{3}{G}", "Creature — Spike", "This creature enters with two +1/+1 counters on it.\n{2}, Remove a +1/+1 counter "
             "from this creature: Put a +1/+1 counter on target creature.\nRemove a +1/+1 counter from this creature: You gain 2 life.", "0", "0",
             colors=("G",))
RESERVOIR = real("Aetherflux Reservoir", "{4}", "Artifact", "Pay 50 life: Aetherflux Reservoir deals 50 damage to any target.")
FAMILIAR = real("Cauldron Familiar", "{B}", "Creature — Cat", "When this creature enters, each opponent loses 1 life and you gain 1 life.\n"
                "Sacrifice a Food: Return this card from your graveyard to the battlefield.", "1", "1", colors=("B",))
ARMY_ANTS = real("Army Ants", "{2}{B}", "Creature \u2014 Insect", "{T}, Sacrifice a land: Destroy target land.", "2", "2", colors=("B",))
HIRELING = real("Grim Hireling", "{3}{B}", "Creature \u2014 Tiefling Rogue", "Whenever one or more creatures you control deal combat damage to a "
                "player, create two Treasure tokens.\n{B}, Sacrifice X Treasures: Target creature gets -X/-X until end of turn. Activate only as a sorcery.",
                "3", "3", colors=("B",))
MIND_STONE = real("Mind Stone", "{2}", "Artifact", "{T}: Add {C}.\n{1}, {T}, Sacrifice this artifact: Draw a card.")
SURGE_NODE = real("Surge Node", "{1}", "Artifact", "This artifact enters with six charge counters on it.\n{1}, {T}, Remove a charge counter from "
                  "this artifact: Put a charge counter on target artifact.")
TAPPER = real("Tapper Probe", "{1}", "Creature \u2014 Probe", "Tap an untapped creature you control: You gain 1 life.", "1", "1")
ELVES = real("Llanowar Elves", "{G}", "Creature — Elf Druid", "{T}: Add {G}.", "1", "1", colors=("G",))


def abilities(card):
    return activated_abilities(card)


class ProbeTests(unittest.TestCase):
    def test_a_card_is_found_for_each_kind_of_permanent(self):
        for kind in ("creature", "Goblin", "Squirrel", "artifact or creature", "white creature", "land", "Food", "enchantment"):
            card = ability_smoke.probe(kind, "Fodder")
            self.assertIsNotNone(card, kind)
            self.assertTrue(ability_smoke._permanent_matches(kind, card), kind)

    def test_a_color_word_gives_the_card_that_color(self):
        self.assertEqual(ability_smoke.probe("white creature", "Fodder").colors, ("W",))

    def test_a_kind_nothing_matches_gives_none(self):
        self.assertIsNone(ability_smoke.probe("creature with flying and defender and a name", "Fodder"))


class TryAbilityTests(unittest.TestCase):
    def outcome(self, card, index=0):
        return ability_smoke.try_ability(card, abilities(card)[index])

    def test_a_plural_sacrifice_cost_is_paid(self):
        self.assertEqual(self.outcome(WARRENS), ("paid", ""))

    def test_a_discard_cost_is_paid_even_when_the_ability_returns_a_card_to_the_hand(self):
        self.assertEqual(self.outcome(AMUGABA), ("paid", ""))

    def test_both_costs_of_one_card_are_tried_in_turn(self):
        self.assertEqual([self.outcome(PATRIARCH, i) for i in (0, 1)], [("paid", ""), ("paid", "")])

    def test_removing_a_counter_is_paid_even_when_the_ability_puts_one_back_on_a_creature(self):
        self.assertEqual(self.outcome(SPIKE, 0), ("paid", ""))
        self.assertEqual(self.outcome(SPIKE, 1), ("paid", ""))

    def test_a_land_to_sacrifice_comes_before_the_lands_that_pay(self):
        self.assertEqual(self.outcome(ARMY_ANTS), ("paid", ""))

    def test_an_x_sacrifice_is_x_of_two_spare_permanents(self):
        ability = abilities(HIRELING)[0]
        self.assertEqual(len(ability_smoke.build(HIRELING, ability).fodder), 2)
        self.assertEqual(self.outcome(HIRELING, 0), ("paid", ""))

    def test_sacrificing_the_card_itself_is_checked(self):
        self.assertEqual(self.outcome(MIND_STONE), ("paid", ""))

    def test_a_counter_removed_from_a_card_that_puts_one_on_a_target_artifact_is_not_put_back_on_itself(self):
        self.assertEqual(self.outcome(SURGE_NODE), ("paid", ""))

    def test_tapping_creatures_is_paid(self):
        self.assertEqual(self.outcome(TAPPER), ("paid", ""))

    def test_a_cost_the_game_does_not_take_is_reported_as_unpaid(self):
        original = ability_smoke.Game._perform
        ability_smoke.Game._perform = lambda self, seat, action: None  # the activation is offered and then does nothing
        self.addCleanup(setattr, ability_smoke.Game, "_perform", original)
        self.assertEqual(self.outcome(AMUGABA), ("unpaid", "discard"))

    def test_paying_life(self):
        self.assertEqual(self.outcome(RESERVOIR), ("paid", ""))

    def test_a_graveyard_ability_that_sacrifices_a_food_is_paid(self):
        self.assertEqual(self.outcome(FAMILIAR), ("paid", ""))

    def test_an_ability_the_game_does_not_offer_is_reported(self):
        original = ability_smoke.action_for
        ability_smoke.action_for = lambda setup, card, ability: None
        self.addCleanup(setattr, ability_smoke, "action_for", original)
        self.assertEqual(self.outcome(WARRENS), ("not offered", ""))


class UnpaidTests(unittest.TestCase):
    """The check that a cost was paid sees a cost that was not: the table, with nothing performed."""

    def unpaid(self, card, index=0):
        ability = abilities(card)[index]
        return ability_smoke.unpaid(ability_smoke.build(card, ability), ability)

    def test_each_kind_of_cost_left_alone_is_unpaid(self):
        self.assertIn("sacrifice (0 of 2 sacrificed)", self.unpaid(WARRENS))
        self.assertEqual(self.unpaid(AMUGABA), "discard")
        self.assertEqual(self.unpaid(PATRIARCH, 1), "exile from the graveyard")
        self.assertEqual(self.unpaid(SPIKE, 0), "remove counters")
        self.assertEqual(self.unpaid(RESERVOIR), "pay life")
        self.assertEqual(self.unpaid(MIND_STONE, 0), "sacrifice this")
        self.assertEqual(self.unpaid(TAPPER), "tap creatures")

    def test_a_mana_cost_left_alone_is_unpaid(self):
        ability = abilities(SPIKE)[0]
        setup = ability_smoke.build(SPIKE, ability)
        setup.source.counters.clear()  # (the counters are gone, so only the {2} is left unpaid)
        self.assertEqual(ability_smoke.unpaid(setup, ability), "pay mana")


class UntriedTests(unittest.TestCase):
    def reason(self, card, index=0):
        return ability_smoke.untried(abilities(card)[index])

    def test_a_cost_it_can_build_is_tried(self):
        self.assertIsNone(self.reason(WARRENS))

    def test_a_sacrifice_kind_no_card_matches_is_named(self):
        import dataclasses
        odd = dataclasses.replace(abilities(WARRENS)[0], sacrifice_other="creature with an impossible name")
        self.assertEqual(ability_smoke.untried(odd), "sacrifice kind creature with an impossible name")

    def test_costs_it_builds_no_table_for_are_named(self):
        crewed = real("Crew Probe", "{2}", "Artifact — Vehicle", "Crew 2", "3", "3")
        self.assertEqual(ability_smoke.untried(abilities(crewed)[0]), "crew")
        walker = real("Walker Probe", "{3}", "Planeswalker — Probe", "+1: You gain 1 life.")
        self.assertEqual(ability_smoke.untried(abilities(walker)[0]), "loyalty")

    def test_an_ability_that_needs_a_spell_or_a_creature_in_combat_is_named(self):
        shaman = real("Brine Shaman", "{3}{U}", "Creature — Merfolk Shaman", "{T}, Sacrifice a Merfolk: Target creature gets +1/+1 until end "
                      "of turn.\n{1}{U}{U}, Sacrifice a Merfolk: Counter target creature spell.", "1", "1")
        self.assertEqual(ability_smoke.untried(abilities(shaman)[1]), "a target on the stack or in combat")
        self.assertIsNone(ability_smoke.untried(abilities(shaman)[0]))


def data(card):
    return {"name": card.name, "layout": "normal", "mana_cost": card.mana_cost, "cmc": card.cmc, "type_line": card.type_line,
            "oracle_text": card.oracle_text, "power": card.power, "toughness": card.toughness, "legalities": {"commander": "legal"},
            "id": card.name, "color_identity": []}


class CheckTests(unittest.TestCase):
    def test_abilities_are_counted_paid_and_a_plain_one_is_left_to_play_smoke(self):
        tried, paid, problems, skipped = ability_smoke.check([data(WARRENS), data(AMUGABA), data(ELVES)])
        self.assertEqual((tried, paid, dict(problems), dict(skipped)), (2, 2, {}, {}))

    def test_a_card_with_an_unread_line_is_left_out(self):
        stuck = real("Stuck Probe", "{2}", "Creature — Frog", "Sacrifice a Goblin: Draw a card.\nFrobnicate the widget whenever the moon is full.",
                     "1", "1")
        self.assertEqual(ability_smoke.check([data(stuck)])[:2], (0, 0))

    def test_untried_costs_are_counted_by_name(self):
        crewed = real("Crew Probe", "{2}", "Artifact — Vehicle", "Crew 2", "3", "3")
        self.assertEqual(dict(ability_smoke.check([data(crewed), data(crewed)])[3]), {"crew": 2})

    def test_only_the_named_card_is_tried(self):
        self.assertEqual(ability_smoke.check([data(WARRENS), data(AMUGABA)], only="Amugaba")[:2], (1, 1))

    def test_the_limit_stops_it(self):
        self.assertEqual(ability_smoke.check([data(WARRENS), data(AMUGABA)], limit=1)[:2], (1, 1))

    def test_an_ability_that_raises_or_takes_too_long_is_listed(self):
        original, limit = ability_smoke.try_ability, ability_smoke.TIMEOUT_SECONDS
        self.addCleanup(setattr, ability_smoke, "try_ability", original)
        self.addCleanup(setattr, ability_smoke, "TIMEOUT_SECONDS", limit)
        ability_smoke.try_ability = lambda card, ability: (_ for _ in ()).throw(KeyError("boom"))
        problems = ability_smoke.check([data(WARRENS)])[2]
        self.assertEqual(dict(problems), {"KeyError: 'boom'": ["Goblin Warrens ({2}{R}, Sacrifice two Goblins: Create three 1/1 red Goblin c)"]})
        ability_smoke.TIMEOUT_SECONDS = 1
        ability_smoke.try_ability = lambda card, ability: [None for _ in iter(int, 1)]  # never ends
        self.assertEqual(list(ability_smoke.check([data(WARRENS)])[2]), ["took more than 1 seconds"])


if __name__ == "__main__":
    unittest.main()
