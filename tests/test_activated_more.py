import unittest

from infernal_machine.cards import Card
from infernal_machine.characteristics import Modifier
from infernal_machine.effects import (CANT_BE_BLOCKED, Condition, FOOD, PutCounters, TapThat, activated_abilities)
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import lands
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

PASSAGE = Card(name="Rogue's Passage", type_line="Land",
               oracle_text="{T}: Add {C}.\n{4}, {T}: Target creature can't be blocked this turn.")
STEELBANE = Card(name="Steelbane Hydra", mana_cost="{X}{G}", type_line="Creature — Hydra", power="0", toughness="0",
                 oracle_text="This creature enters with X +1/+1 counters on it.\n{2}{G}, Remove a +1/+1 counter from this "
                             "creature: Destroy target artifact or enchantment.")
BENEVOLENT = Card(name="Benevolent Hydra", mana_cost="{X}{G}", type_line="Creature — Hydra", power="0", toughness="0",
                  oracle_text="{T}, Remove a +1/+1 counter from this creature: Put a +1/+1 counter on another target "
                              "creature you control.")
STAFF = Card(name="Staff of the Storyteller", mana_cost="{3}", type_line="Artifact",
             oracle_text="{W}, {T}, Remove a story counter from this artifact: Draw a card.")
GYOME = Card(name="Gyome, Master Chef", mana_cost="{3}{G}", type_line="Legendary Creature — Troll Warlock", power="3", toughness="3",
             oracle_text="{1}, Sacrifice a Food: Target creature gains indestructible until end of turn. Tap it.")
HALL = Card(name="Hall of Oracles", type_line="Land",
            oracle_text="{T}: Put a +1/+1 counter on target creature. Activate only as a sorcery and only if you've cast "
                        "an instant or sorcery spell this turn.")
MISTVEIL = Card(name="Mistveil Plains", type_line="Land",
                oracle_text="{W}, {T}: Draw a card. Activate only if you control two or more white permanents.")
RELIC = Card(name="Relic", type_line="Artifact", oracle_text="")
IDOL = Card(name="Idol", type_line="Artifact", oracle_text="")
SHRINE = Card(name="Shrine", type_line="Enchantment", oracle_text="")
WHITE_BEAR = Card(name="White Bear", type_line="Creature — Bear", colors=("W",), power="2", toughness="2")
BOLT = Card(name="Bolt", mana_cost="{R}", type_line="Instant", oracle_text="Draw a card.")


def activation(game, seat, text):
    options = [a for a in game._activations(seat, True) if text in a]
    return options


def activate(game, seat, text):
    [action] = activation(game, seat, text)
    game._perform(seat, action)
    run_stack(game)


class ParseTests(unittest.TestCase):
    def test_cant_be_blocked(self):
        [ability] = activated_abilities(PASSAGE)
        self.assertEqual((ability.mana_cost, ability.tap), ("{4}", True))
        [effect] = ability.effects
        self.assertEqual((effect.target, effect.modifier), ("creature", Modifier(keywords=frozenset({CANT_BE_BLOCKED}))))

    def test_remove_a_counter(self):
        [ability] = activated_abilities(STEELBANE)
        self.assertEqual((ability.remove_counter, ability.mana_cost), ("+1/+1", "{2}{G}"))
        [ability] = activated_abilities(STAFF)
        self.assertEqual(ability.remove_counter, "story")

    def test_put_a_counter_on_another_creature(self):
        [ability] = activated_abilities(BENEVOLENT)
        self.assertEqual(ability.effects, (PutCounters(1, "+1/+1", "creature you control", another=True),))

    def test_sacrifice_a_food_and_tap_it(self):
        [ability] = activated_abilities(GYOME)
        self.assertEqual((ability.sacrifice_other, ability.sacrifice_another), ("Food", False))
        self.assertIsInstance(ability.effects[-1], TapThat)

    def test_activation_conditions(self):
        [ability] = activated_abilities(HALL)
        self.assertEqual((ability.sorcery_speed, ability.condition), (True, Condition("cast_this_turn", what="instant or sorcery spell")))
        [ability] = activated_abilities(MISTVEIL)
        self.assertEqual((ability.sorcery_speed, ability.condition), (False, Condition("control_color_at_least", 2, "white")))

    def test_the_report_understands_them(self):
        for card in (PASSAGE, STEELBANE, STAFF, GYOME, HALL, MISTVEIL):
            self.assertEqual([l for l in unsupported_lines(card) if "enters with" not in l], [], card.name)


class BlockingTests(unittest.TestCase):
    def test_a_creature_that_cannot_be_blocked_this_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        attacker, blocker = Permanent(BEAR), Permanent(BEAR)
        a.battlefield, b.battlefield = [attacker], [blocker]
        self.assertTrue(game.combat._can_block(blocker, attacker))
        game.modify_until_end_of_turn(attacker, Modifier(keywords=frozenset({CANT_BE_BLOCKED})))
        self.assertFalse(game.combat._can_block(blocker, attacker))

    def test_the_ability_wears_off_at_end_of_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        passage, attacker = Permanent(PASSAGE), Permanent(BEAR)
        a.battlefield = [passage, attacker, *lands(4)]
        activate(game, a, "can't be blocked")
        self.assertTrue(game.has_keyword(attacker, CANT_BE_BLOCKED))
        self.assertTrue(passage.tapped)


class RemoveCounterTests(unittest.TestCase):
    def test_pay_by_removing_a_counter(self):
        game, _ = table3()
        a, b, _ = game.seats
        hydra = Permanent(STEELBANE, counters={"+1/+1": 3})
        relic = Permanent(RELIC)
        a.battlefield = [hydra, *lands(3)]
        b.battlefield = [relic]
        activate(game, a, "Destroy target")
        self.assertEqual(hydra.counters["+1/+1"], 2)
        self.assertEqual(b.battlefield, [])

    def test_not_offered_without_a_counter(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(STEELBANE), *lands(3)]
        b.battlefield = [Permanent(RELIC)]
        self.assertEqual(activation(game, a, "Destroy target"), [])

    def test_a_named_counter(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 3
        staff = Permanent(STAFF, counters={"story": 1})
        a.battlefield = [staff, *lands(1)]
        activate(game, a, "Draw a card")
        self.assertEqual((len(a.hand), staff.counters.get("story", 0)), (1, 0))
        staff.tapped = False
        self.assertEqual(activation(game, a, "Draw a card"), [])  # no counters left

    def test_another_target_creature_excludes_the_source(self):
        game, _ = table3()
        a = game.seats[0]
        hydra, other = Permanent(BENEVOLENT, counters={"+1/+1": 1}), Permanent(BEAR)
        a.battlefield = [hydra, other]
        activate(game, a, "Put a +1/+1 counter")
        self.assertEqual((hydra.counters.get("+1/+1", 0), other.counters["+1/+1"]), (0, 1))


class SacrificeFoodTests(unittest.TestCase):
    def test_sacrifice_a_food_to_protect_and_tap(self):
        game, _ = table3()
        a = game.seats[0]
        bear, food = Permanent(BEAR), Permanent(FOOD)
        a.battlefield = [Permanent(GYOME), bear, food, *lands(1)]
        activate(game, a, "Sacrifice a Food")
        self.assertNotIn(food, a.battlefield)
        [protected] = [p for p in a.battlefield if game.has_keyword(p, "indestructible")]
        self.assertTrue(protected.tapped)  # "Tap it."

    def test_not_offered_without_a_food(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(GYOME), Permanent(BEAR), *lands(1)]
        self.assertEqual(activation(game, a, "Sacrifice a Food"), [])


class ActivationConditionTests(unittest.TestCase):
    def test_only_after_casting_an_instant_or_sorcery(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(HALL), Permanent(BEAR)]
        self.assertEqual(activation(game, a, "Put a +1/+1 counter"), [])
        a.cast_log.append((game.turn, BOLT))
        self.assertEqual(len(activation(game, a, "Put a +1/+1 counter")), 1)

    def test_white_permanents(self):
        game, _ = table3()
        a = game.seats[0]
        a.library = [BEAR] * 3
        a.battlefield = [Permanent(MISTVEIL), Permanent(WHITE_BEAR), *lands(1)]
        self.assertEqual(activation(game, a, "Draw a card"), [])
        a.battlefield.append(Permanent(WHITE_BEAR))
        self.assertEqual(len(activation(game, a, "Draw a card")), 1)


if __name__ == "__main__":
    unittest.main()
