import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Untap, UntapAll, UntapSource, spell_effects
from infernal_machine.game import ACTIVATE, CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import attack_first_opponent, BEAR, FOREST, lands, pick, run_stack, table, table3


def spell(text, kind="Instant"):
    return Card(name="Spell", mana_cost="{U}", type_line=kind, oracle_text=text)


class UntapParseTests(unittest.TestCase):
    def test_forms(self):
        self.assertEqual(spell_effects(spell("Untap target permanent."))[0], Untap("permanent"))
        self.assertEqual(spell_effects(spell("Untap another target creature."))[0], Untap("creature", True))
        self.assertEqual(spell_effects(spell("Untap all lands you control.")), [UntapAll("land")])
        a, b = spell_effects(spell("Untap up to two target lands."))
        self.assertEqual((a.target, a.optional_target, a.distinct, b.distinct), ("land", True, False, True))
        self.assertEqual(spell_effects(spell("Untap up to one target land."))[0].optional_target, True)

    def test_reported_playable(self):
        for text in ("Untap target permanent.", "Untap all lands you control.", "Untap up to two target lands."):
            self.assertEqual(unsupported_lines(spell(text)), [], text)


class UntapPlayTests(unittest.TestCase):
    def test_untap_target_land(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        tapped = Permanent(FOREST, tapped=True)
        a.battlefield = [tapped, *lands(1)]
        a.hand = [Card(name="Spell", mana_cost="{G}", type_line="Instant", oracle_text="Untap target land.")]
        game._priority_round(a)
        self.assertFalse(tapped.tapped)

    def test_untap_all_lands_leaves_other_permanents(self):
        game, _ = table3()
        a = game.seats[0]
        forest, bear = Permanent(FOREST, tapped=True), Permanent(BEAR, tapped=True)
        opponent_forest = Permanent(FOREST, tapped=True)
        a.battlefield, game.seats[1].battlefield = [forest, bear], [opponent_forest]
        UntapAll("land").resolve(game, a, None)
        self.assertEqual((forest.tapped, bear.tapped, opponent_forest.tapped), (False, True, True))

    def test_a_creature_that_untaps_itself_when_it_attacks(self):
        card = Card(name="Vigilant", mana_cost="{1}", type_line="Creature — Bear", power="2", toughness="2",
                    oracle_text="Whenever this creature attacks, untap it.")
        self.assertEqual(unsupported_lines(card), [])
        game, _, _ = table(attack_first_opponent)
        a = game.seats[0]
        bear = Permanent(card)
        a.battlefield = [bear]
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertFalse(bear.tapped)

    def test_the_equipped_creature_untaps(self):
        blade = Card(name="Frost Blade", mana_cost="{1}", type_line="Artifact — Equipment",
                     oracle_text="Equipped creature gets +1/+1.\nWhenever equipped creature attacks, untap it.\nEquip {1}")
        self.assertEqual(unsupported_lines(blade), [])
        game, _, _ = table(attack_first_opponent)
        a = game.seats[0]
        bear, equipment = Permanent(BEAR), Permanent(blade)
        equipment.attached_to = bear
        a.battlefield = [bear, equipment]
        game.combat.declare_attackers(a)
        run_stack(game)
        self.assertEqual((bear.tapped, equipment.tapped), (False, False))


if __name__ == "__main__":
    unittest.main()
