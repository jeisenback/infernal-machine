"""Doubling and replacement effects (#203), played from the cards' own Oracle text: twice the life, tokens and +1/+1 counters,
one Clue, Food and Treasure at once, and exiled instead of dying."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import CLUE, FOOD, TREASURE
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack
from tests.test_rules_text_81 import Table, real
from tests.test_triggers_80 import BIG


def static(name, text, type_line="Artifact"):
    return Card(name=name, mana_cost="{3}", cmc=3, type_line=type_line, oracle_text=text)


WIND = static("The Wind Crystal", "If you would gain life, you gain twice that much life instead.")
BRANCHING = static("Branching Evolution", "If one or more +1/+1 counters would be put on a creature you control, twice that many "
                   "+1/+1 counters are put on that creature instead.", "Enchantment")
MONDRAK = static("Mondrak, Glory Dominus", "If one or more tokens would be created under your control, twice that many of those "
                 "tokens are created instead.", "Legendary Creature — Phyrexian Horror")
SEASON = static("Doubling Season", "If an effect would create one or more tokens under your control, it creates twice that many of "
                "those tokens instead.", "Enchantment")
SCALES = static("Hardened Scales", "If one or more +1/+1 counters would be put on a creature you control, that many plus one +1/+1 "
                "counters are put on it instead.", "Enchantment")
RESCUER = Card(name="Pest Rescuer", type_line="Creature — Pest", power="1", toughness="1",
               oracle_text="If you would gain life, you gain that much life plus 1 instead.")
MANUFACTOR = Card(name="Academy Manufactor", mana_cost="{3}", cmc=3, type_line="Artifact Creature — Assembly-Worker", power="1",
                  toughness="3", oracle_text="If you would create a Clue, Food, or Treasure token, instead create one of each.")
LIESA = Card(name="Liesa", mana_cost="{2}{W}{W}", cmc=4, type_line="Legendary Creature — Angel", power="4", toughness="3",
             oracle_text="If a creature an opponent controls would die, exile it instead.")
GLOOM = Card(name="Gloomshrieker", mana_cost="{2}{B}", cmc=3, type_line="Creature — Spirit", power="3", toughness="2",
             oracle_text="If this creature would die, exile it instead.")
BEAR = Card(name="Bear", mana_cost="{1}", cmc=1, type_line="Creature — Bear", power="2", toughness="2")
MARTYR = Card(name="Martyr", mana_cost="{1}", cmc=1, type_line="Creature — Cleric", power="1", toughness="1",
              oracle_text="When this creature dies, you gain 1 life.")
GOBLIN = Card(name="Goblin Token", type_line="Token Creature — Goblin", power="1", toughness="1")
LAVA_COIL = real("Lava Coil", "{1}{R}", "Sorcery", "Lava Coil deals 4 damage to target creature. If that creature would die this turn, "
                 "exile it instead.")
FIRE = real("Annihilating Fire", "{1}{R}", "Instant", "Annihilating Fire deals 3 damage to any target. If a creature dealt damage this "
            "way would die this turn, exile it instead.")
ANGER = real("Anger of the Gods", "{1}{R}{R}", "Sorcery", "Anger of the Gods deals 3 damage to each creature. If a creature dealt "
             "damage this way would die this turn, exile it instead.")


def one(card, seat, holder="battlefield"):
    return next(p for p in getattr(seat, holder) if p.card.name == card.name)


class LifeTests(unittest.TestCase):
    def gain(self, mine, amount=3, theirs=()):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.battlefield = [Permanent(c) for c in mine]
        b.battlefield = [Permanent(c) for c in theirs]
        life = a.life
        game.change_life(a, amount)
        return a.life - life

    def test_twice_that_much(self):
        self.assertEqual(self.gain([WIND]), 6)

    def test_two_of_them_stack(self):
        self.assertEqual(self.gain([WIND, static("Boon Reflection", WIND.oracle_text, "Enchantment")]), 12)

    def test_with_pest_rescuer_the_extra_one_comes_first(self):
        self.assertEqual(self.gain([WIND, RESCUER]), 8)  # (3 + 1) * 2

    def test_an_opponents_does_not_apply(self):
        self.assertEqual(self.gain([], theirs=[WIND]), 3)

    def test_losing_life_is_not_doubled(self):
        self.assertEqual(self.gain([WIND], amount=-3), -3)


class TokenTests(unittest.TestCase):
    def make(self, mine, count=2):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(c) for c in mine]
        return len(game.create_tokens(a, GOBLIN, count))

    def test_the_current_wording_doubles(self):
        self.assertEqual(self.make([MONDRAK]), 4)

    def test_it_stacks_with_the_older_wording(self):
        self.assertEqual(self.make([MONDRAK, SEASON]), 8)

    def test_without_one_nothing_changes(self):
        self.assertEqual(self.make([]), 2)

    def test_an_opponents_does_not_apply(self):
        game, _ = table3()
        game.seats[1].battlefield = [Permanent(MONDRAK)]
        self.assertEqual(len(game.create_tokens(game.seats[0], GOBLIN, 2)), 2)


class CounterTests(unittest.TestCase):
    def put(self, mine, counter="+1/+1", target=BEAR, count=2):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(c) for c in mine] + [Permanent(target)]
        creature = a.battlefield[-1]
        game.put_counters(creature, counter, count)
        return creature.counters.get(counter, 0)

    def test_twice_that_many_on_a_creature(self):
        self.assertEqual(self.put([BRANCHING]), 4)

    def test_hardened_scales_adds_first(self):
        self.assertEqual(self.put([BRANCHING, SCALES]), 6)  # (2 + 1) * 2

    def test_other_counters_are_not_doubled(self):
        self.assertEqual(self.put([BRANCHING], counter="-1/-1"), 2)

    def test_a_noncreature_is_not(self):
        self.assertEqual(self.put([BRANCHING], target=static("Relic", "")), 2)


class ManufactorTests(unittest.TestCase):
    def create(self, mine, token=TREASURE, count=1):
        game, _ = table3()
        a = game.seats[0]
        a.battlefield = [Permanent(c) for c in mine]
        game.create_tokens(a, token, count)
        return sorted(p.card.name for p in a.battlefield if p.card.type_line.startswith("Token"))

    def test_a_treasure_becomes_a_clue_a_food_and_a_treasure(self):
        self.assertEqual(self.create([MANUFACTOR]), ["Clue", "Food", "Treasure"])

    def test_two_make_two_of_each(self):
        self.assertEqual(self.create([MANUFACTOR], FOOD, 2), ["Clue", "Clue", "Food", "Food", "Treasure", "Treasure"])

    def test_other_tokens_are_untouched(self):
        self.assertEqual(self.create([MANUFACTOR], GOBLIN, 2), ["Goblin Token", "Goblin Token"])

    def test_without_it_only_what_was_asked(self):
        self.assertEqual(self.create([], CLUE), ["Clue"])

    def test_with_a_token_doubler_each_one_is_doubled(self):
        self.assertEqual(self.create([MANUFACTOR, MONDRAK]), ["Clue", "Clue", "Food", "Food", "Treasure", "Treasure"])


class ExileInsteadOfDyingTests(unittest.TestCase):
    def table(self, mine=(), theirs=()):
        game, _ = table3()
        a, b = game.seats[0], game.seats[1]
        a.battlefield = [Permanent(c) for c in mine]
        b.battlefield = [Permanent(c) for c in theirs]
        return game, a, b

    def test_an_opponents_creature_is_exiled(self):
        game, a, b = self.table([LIESA], [BEAR])
        game.destroy(b.battlefield[0])
        self.assertEqual(([c.name for c in b.exile], b.graveyard), (["Bear"], []))

    def test_your_own_creature_still_dies(self):
        game, a, b = self.table([LIESA, BEAR])
        game.destroy(one(BEAR, a))
        self.assertEqual(([c.name for c in a.graveyard], a.exile), (["Bear"], []))

    def test_it_is_the_controllers_opponents_creatures_that_are_exiled_whoever_has_it(self):
        game, a, b = self.table([BEAR], [LIESA])  # b has the Liesa, so a's creature is the opponent's
        game.destroy(one(BEAR, a))
        self.assertEqual(([c.name for c in a.exile], a.graveyard), (["Bear"], []))

    def test_a_creature_that_exiles_itself(self):
        game, a, b = self.table([GLOOM, BEAR])
        game.destroy(one(GLOOM, a))
        game.destroy(one(BEAR, a))
        self.assertEqual(([c.name for c in a.exile], [c.name for c in a.graveyard]), (["Gloomshrieker"], ["Bear"]))

    def test_exiled_creatures_do_not_die(self):
        game, a, b = self.table([LIESA], [MARTYR])
        life = b.life
        game.destroy(b.battlefield[0])
        run_stack(game)
        self.assertEqual(b.life, life)  # "when this creature dies" never happened

    def test_a_damage_spell_exiles_what_it_kills(self):
        t = Table(LAVA_COIL, "Bear", theirs=[Permanent(BEAR)], n=2, policy=lambda prompt, options: next(
            (i for i, o in enumerate(options) if o.startswith("Bear")), 0))
        t.cast()
        self.assertEqual(([c.name for c in t.b.exile], t.b.graveyard), (["Bear"], []))

    def test_what_survives_is_exiled_if_it_dies_later_this_turn_only(self):
        t = Table(LAVA_COIL, theirs=[Permanent(BIG)], n=2, policy=lambda prompt, options: next(
            (i for i, o in enumerate(options) if o.startswith("Big")), 0))
        t.cast()
        big = t.b.battlefield[0]
        self.assertEqual(big.exile_if_dies, t.game.turn)
        t.game.turn += 1  # the next turn
        t.game.destroy(big)
        self.assertEqual(([c.name for c in t.b.graveyard], t.b.exile), (["Big"], []))
        t2 = Table(LAVA_COIL, theirs=[Permanent(BIG)], n=2, policy=lambda prompt, options: next(
            (i for i, o in enumerate(options) if o.startswith("Big")), 0))
        t2.cast()
        t2.game.destroy(t2.b.battlefield[0])
        self.assertEqual(([c.name for c in t2.b.exile], t2.b.graveyard), (["Big"], []))

    def test_a_sweeper_exiles_only_what_it_damaged(self):
        t = Table(ANGER, mine=[Permanent(BIG), Permanent(BEAR)], n=3, theirs=[Permanent(BEAR)])
        t.cast()
        self.assertEqual(sorted(c.name for c in t.a.exile), ["Bear"])
        self.assertEqual(sorted(c.name for c in t.b.exile), ["Bear"])
        self.assertEqual([p.card.name for p in t.a.battlefield if "Creature" in p.card.type_line], ["Big"])  # survived with 3 damage
        t.game.destroy(one(BIG, t.a))
        self.assertEqual([c.name for c in t.a.exile if c.name == "Big"], ["Big"])

    def test_only_creatures_are_exiled_instead_of_dying(self):
        game, a, b = self.table([LIESA], [static("Relic", "")])
        game.destroy(b.battlefield[0])
        self.assertEqual(([c.name for c in b.graveyard], b.exile), (["Relic"], []))

    def test_a_spell_marks_only_what_it_damaged_not_what_an_earlier_one_did(self):
        t = Table(FIRE, theirs=[Permanent(BIG)], n=3, policy=lambda prompt, options: next(
            (i for i, o in enumerate(options) if o.startswith("Player")), 0))
        t.game.resolving_damaged = [t.b.battlefield[0]]  # left over from an earlier spell this turn
        t.cast()
        self.assertIsNone(t.b.battlefield[0].exile_if_dies)

    def test_an_ordinary_death_goes_to_the_graveyard(self):
        game, a, b = self.table([BEAR])
        game.destroy(a.battlefield[0])
        self.assertEqual(([c.name for c in a.graveyard], a.exile), (["Bear"], []))


class ReportTests(unittest.TestCase):
    def test_the_lines_are_supported(self):
        for card in (WIND, BRANCHING, MONDRAK, MANUFACTOR, LIESA, GLOOM, LAVA_COIL, ANGER):
            with self.subTest(card.name):
                self.assertEqual(unsupported_lines(card), [])


if __name__ == "__main__":
    unittest.main()
