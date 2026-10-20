import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import run_stack, table3, watcher

PEST = Card(name="Pest", type_line="Token Creature — Pest", power="1", toughness="1")
ELF = Card(name="Elf", type_line="Creature — Elf Druid", power="1", toughness="1")
BEAR = Card(name="Bear", type_line="Creature — Bear", power="2", toughness="2")


def board(text):
    game, _ = table3()
    a, b, _ = game.seats
    a.battlefield = [Permanent(watcher("Watch", text))]
    return game, a, b


class TribalTests(unittest.TestCase):
    def test_a_pest_you_control_dies(self):
        game, a, b = board("Whenever a Pest you control dies, you gain 1 life.")
        pest, other, theirs = Permanent(PEST), Permanent(BEAR), Permanent(PEST)
        a.battlefield += [pest, other]
        b.battlefield = [theirs]
        game._leave_together([(pest, "destroyed"), (other, "destroyed"), (theirs, "destroyed")])
        run_stack(game)
        self.assertEqual(a.life, 41)

    def test_another_elf_enters(self):
        game, a, b = board("Whenever another Elf you control enters, you gain 1 life.")
        game._enter(a, Permanent(ELF))
        game._enter(a, Permanent(BEAR))
        game._enter(b, Permanent(ELF))
        run_stack(game)
        self.assertEqual(a.life, 41)

    def test_this_or_another_pest_dies(self):
        card = Card(name="Pest Lord", type_line="Creature — Pest", power="1", toughness="1",
                    oracle_text="Whenever this creature or another Pest you control dies, you gain 1 life.")
        self.assertEqual(unsupported_lines(card), [])

    def test_a_token_you_control_dies(self):
        game, a, b = board("Whenever a token you control dies, each opponent loses 1 life.")
        token, card = Permanent(PEST), Permanent(BEAR)
        a.battlefield += [token, card]
        game._leave_together([(token, "destroyed"), (card, "destroyed")])
        run_stack(game)
        self.assertEqual((b.life, a.life), (39, 40))


class LeavesTests(unittest.TestCase):
    def test_a_creature_you_control_leaves_for_any_reason(self):
        game, a, b = board("Whenever a creature you control leaves the battlefield, you gain 1 life.")
        died, bounced, exiled, theirs = Permanent(BEAR), Permanent(BEAR), Permanent(BEAR), Permanent(BEAR)
        a.battlefield += [died, bounced, exiled]
        b.battlefield = [theirs]
        game._leave_together([(died, "destroyed")])
        game.return_to_hand(bounced)
        game._leave_together([(exiled, "exiled")], destination="exile")
        game._leave_together([(theirs, "destroyed")])
        run_stack(game)
        self.assertEqual(a.life, 43)

    def test_another_excludes_the_source(self):
        card = Card(name="Hound", type_line="Creature — Dog", power="1", toughness="1",
                    oracle_text="Whenever another creature you control leaves the battlefield, you gain 1 life.")
        game, _ = table3()
        a = game.seats[0]
        hound, bear = Permanent(card), Permanent(BEAR)
        a.battlefield = [hound, bear]
        game._leave_together([(hound, "destroyed"), (bear, "destroyed")])
        run_stack(game)
        self.assertEqual(a.life, 41)


class QuotedTokenAbilityTests(unittest.TestCase):
    def test_a_pest_gains_life_when_it_dies(self):
        text = ('Whenever a creature you control dies, create a 1/1 black and green Pest creature token with '
                '"When this token dies, you gain 1 life."')
        game, a, _ = board(text)
        self.assertEqual(unsupported_lines(watcher("Watch", text)), [])
        bear = Permanent(BEAR)
        a.battlefield.append(bear)
        game._leave_together([(bear, "destroyed")])
        run_stack(game)
        (pest,) = [p for p in a.battlefield if p.card.name == "Pest"]
        self.assertEqual(a.life, 40)
        game._leave_together([(pest, "destroyed")])
        run_stack(game)
        self.assertEqual(a.life, 41)


class TokenCounterTests(unittest.TestCase):
    def test_x_counters_go_on_the_new_token(self):
        game, _ = table3()
        a = game.seats[0]
        spell = Card(name="Growth", mana_cost="{X}{G}{U}", type_line="Sorcery",
                     oracle_text="Create a 0/0 green and blue Fractal creature token. Put X +1/+1 counters on it.")
        self.assertEqual(unsupported_lines(spell), [])
        from infernal_machine.effects import spell_effects
        game.x_value = 3
        for effect in spell_effects(spell):
            effect.resolve(game, a, None)
        (fractal,) = a.battlefield
        self.assertEqual((fractal.counters, game.power(fractal)), ({"+1/+1": 3}, 3))

    def test_then_put_counters_on_it(self):
        game, _ = table3()
        a = game.seats[0]
        spell = Card(name="Growth", mana_cost="{G}{U}", type_line="Sorcery",
                     oracle_text="Create a 0/0 green and blue Fractal creature token, then put three +1/+1 counters on it.")
        self.assertEqual(unsupported_lines(spell), [])
        from infernal_machine.effects import spell_effects
        for effect in spell_effects(spell):
            effect.resolve(game, a, None)
        (fractal,) = a.battlefield
        self.assertEqual(fractal.counters, {"+1/+1": 3})

    def test_a_trigger_that_makes_a_token_with_counters(self):
        game, a, _ = board("Whenever you gain life, create a 0/0 green Fractal creature token, then put two +1/+1 counters on it.")
        game.change_life(a, 1)
        run_stack(game)
        token = [p for p in a.battlefield if p.card.name == "Fractal"]
        self.assertEqual([p.counters for p in token], [{"+1/+1": 2}])
        self.assertEqual(a.battlefield[0].counters, {})


if __name__ == "__main__":
    unittest.main()
