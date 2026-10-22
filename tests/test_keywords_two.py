import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (affinity_for, devour, replicate_cost, static_abilities, storm_kind)
from infernal_machine.game import CAST, DEVOUR_PROMPT, Permanent, REPLICATE_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, table3

PLANESWALKER = Card(name="Jace", type_line="Legendary Planeswalker — Jace", loyalty="3")
SAPROLING = Card(name="Saproling", type_line="Token Creature — Saproling", colors=("G",), power="1", toughness="1")


def spell(name, cost, text, type_line="Sorcery", cmc=1):
    return Card(name=name, mana_cost=cost, cmc=float(cmc), type_line=type_line, oracle_text=text)


def resolve_everything(game):
    game._put_triggers_on_stack()
    while game.stack:
        game._resolve(game.stack.pop())
        game._put_triggers_on_stack()
    game._check_state()


class ParseTests(unittest.TestCase):
    def test_keywords(self):
        eater = Card(name="Eater", type_line="Creature — Beast", power="4", toughness="4", oracle_text="Devour 2 (...)")
        self.assertEqual(devour(eater), 2)
        self.assertEqual(replicate_cost(spell("Copy", "{R}", "Replicate {1}\nYou gain 1 life.")), "{1}")
        self.assertEqual(storm_kind(spell("S", "{R}", "Storm")), "storm")
        self.assertEqual(storm_kind(spell("G", "{B}", "Gravestorm")), "gravestorm")
        self.assertEqual(affinity_for(spell("A", "{5}", "Affinity for planeswalkers")), "planeswalker")

    def test_the_report_accepts_them(self):
        for text in ("Devour 1", "Ascend", "Affinity for artifacts"):
            card = Card(name="Test", mana_cost="{1}", type_line="Creature — Bear", power="1", toughness="1", oracle_text=text)
            self.assertEqual(unsupported_lines(card), [], text)
        for text in ("Replicate {1}\nYou gain 1 life.", "Storm\nYou gain 1 life.", "Gravestorm\nYou gain 1 life."):
            self.assertEqual(unsupported_lines(spell("Test", "{R}", text)), [], text)


class DevourTests(unittest.TestCase):
    EATER = Card(name="Eater", mana_cost="{3}", type_line="Creature — Beast", power="4", toughness="4", oracle_text="Devour 2")

    def enter(self, sacrifices, creatures=3):
        eaten = [0]

        def policy(prompt, options):
            if DEVOUR_PROMPT.matches(prompt):
                if eaten[0] < sacrifices:
                    eaten[0] += 1
                    return 0
                return len(options) - 1  # Done
            return 0

        game, _ = table3(policy)
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR) for _ in range(creatures)]
        eater = Permanent(self.EATER)
        game._enter(a, eater)
        return a, eater

    def test_each_creature_gives_n_counters(self):
        a, eater = self.enter(2)
        self.assertEqual(eater.counters["+1/+1"], 4)
        self.assertEqual(len(a.battlefield), 2)  # one Bear and the Eater
        self.assertEqual(len(a.graveyard), 2)

    def test_it_can_eat_nothing(self):
        a, eater = self.enter(0)
        self.assertEqual(eater.counters, {})
        self.assertEqual(len(a.battlefield), 4)

    def test_no_prompt_without_other_creatures(self):
        a, eater = self.enter(2, creatures=0)
        self.assertEqual(eater.counters, {})


class ReplicateTests(unittest.TestCase):
    PYRO = spell("Pyromatics", "{R}", "Replicate {1}\nYou gain 3 life.")

    def cast(self, times, lands_count=4):
        game, _ = table3(pick(str(times)))
        a = game.seats[0]
        a.hand = [self.PYRO]
        a.battlefield = lands(lands_count)
        game._perform(a, CAST + "Pyromatics")
        resolve_everything(game)
        return game, a

    def test_each_payment_makes_a_copy(self):
        game, a = self.cast(3)
        self.assertEqual(a.life, 40 + 3 * 4)  # the spell and three copies
        self.assertEqual(sum(p.tapped for p in a.battlefield), 4)
        self.assertEqual([c.name for c in a.graveyard], ["Pyromatics"])  # copies do not go to the graveyard

    def test_none_is_fine(self):
        game, a = self.cast(0)
        self.assertEqual(a.life, 43)

    def test_the_options_stop_at_what_you_can_afford(self):
        seen = []

        def policy(prompt, options):
            if REPLICATE_PROMPT.matches(prompt):
                seen.append(options)
            return 0

        game, _ = table3(policy)
        a = game.seats[0]
        a.hand = [self.PYRO]
        a.battlefield = lands(3)
        game._perform(a, CAST + "Pyromatics")
        self.assertEqual(seen, [["0", "1", "2"]])  # {R} plus up to two {1}

    def test_a_copy_of_an_aura_becomes_a_token_aura(self):
        aura = Card(name="Loyal Aura", mana_cost="{3}{U}", type_line="Enchantment — Aura",
                    oracle_text="Flash\nReplicate {2}\nEnchant creature\nEnchanted creature gets +1/+1.")
        game, _ = table3(pick("1"))
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.hand = [aura]
        a.battlefield = [*lands(6), bear]
        game._perform(a, CAST + "Loyal Aura")
        resolve_everything(game)
        attached = sorted(p.card.type_line for p in a.battlefield if p.attached_to is bear)
        self.assertEqual(attached, ["Enchantment — Aura", "Token Enchantment — Aura"])
        self.assertEqual(game.power(bear), 4)


class StormTests(unittest.TestCase):
    STORM = spell("Tendrils", "{R}", "Storm\nYou gain 1 life.")
    GRAVE = spell("Harvest", "{B}", "Gravestorm\nYou gain 1 life.")

    def test_a_copy_for_each_spell_cast_before_it(self):
        game, _ = table3(pick("Yes"))
        a, b, _ = game.seats
        a.cast_log += [(game.turn, BEAR), (game.turn - 1, BEAR)]  # only this turn's count
        b.cast_log.append((game.turn, BEAR))
        a.hand = [self.STORM]
        a.battlefield = lands(1)
        game._perform(a, CAST + "Tendrils")
        resolve_everything(game)
        self.assertEqual(a.life, 43)  # the spell and two copies

    def test_the_first_spell_has_no_copies(self):
        game, _ = table3()
        a = game.seats[0]
        a.hand = [self.STORM]
        a.battlefield = lands(1)
        game._perform(a, CAST + "Tendrils")
        resolve_everything(game)
        self.assertEqual(a.life, 41)

    def test_gravestorm_counts_permanents_put_into_a_graveyard_this_turn(self):
        game, _ = table3()
        a, b, _ = game.seats
        victims = [Permanent(BEAR), Permanent(BEAR), Permanent(BEAR)]
        a.battlefield = [*lands(1), victims[0], victims[1]]
        b.battlefield = [victims[2]]
        for victim in victims:
            game._leave_battlefield(victim, "destroyed")
        a.hand = [self.GRAVE]
        game._perform(a, CAST + "Harvest")
        resolve_everything(game)
        self.assertEqual(a.life, 44)  # three copies and the spell

    def test_gravestorm_starts_over_each_turn(self):
        game, _ = table3()
        a = game.seats[0]
        victim = Permanent(BEAR)
        a.battlefield = [*lands(1), victim]
        game._leave_battlefield(victim, "destroyed")
        game.turn += 1
        a.hand = [self.GRAVE]
        game._perform(a, CAST + "Harvest")
        resolve_everything(game)
        self.assertEqual(a.life, 41)


class AscendTests(unittest.TestCase):
    DRYAD = Card(name="Dryad", mana_cost="{1}{G}", type_line="Creature — Dryad", power="2", toughness="2",
                 oracle_text="Ascend\nSaprolings you control get +2/+2 as long as you have the city's blessing.")

    def test_ten_permanents_give_the_blessing_for_good(self):
        game, _ = table3()
        a = game.seats[0]
        saproling = Permanent(SAPROLING)
        a.battlefield = [Permanent(self.DRYAD), saproling, *lands(7)]
        game._check_state()
        self.assertFalse(a.citys_blessing)  # nine permanents
        self.assertEqual(game.power(saproling), 1)
        a.battlefield.append(Permanent(BEAR))
        game._check_state()
        self.assertTrue(a.citys_blessing)
        self.assertEqual(game.power(saproling), 3)
        a.battlefield.pop()
        game._check_state()
        self.assertTrue(a.citys_blessing)  # it never goes away

    def test_the_buff_line_is_understood(self):
        [buff] = static_abilities(self.DRYAD)
        self.assertEqual((buff.subtype, buff.modifier.power), ("Saproling", 2))

    def test_without_an_ascend_permanent_there_is_no_blessing(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = lands(12)
        game._check_state()
        self.assertFalse(a.citys_blessing)


class AffinityTests(unittest.TestCase):
    TOMIK = Card(name="Tomik", mana_cost="{4}{U}", type_line="Creature — Bird", power="2", toughness="2",
                 oracle_text="Affinity for planeswalkers\nFlying")

    def test_each_planeswalker_takes_one_off(self):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = lands(3)
        self.assertIsNone(game._payment(a, self.TOMIK))  # {4}{U} needs five
        a.battlefield += [Permanent(PLANESWALKER), Permanent(PLANESWALKER)]
        self.assertIsNotNone(game._payment(a, self.TOMIK))
        self.assertEqual(game.cost_reduction(a, self.TOMIK), 2)


if __name__ == "__main__":
    unittest.main()
