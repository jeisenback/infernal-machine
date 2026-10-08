import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import CreateTokens, HEARTWOOD, ReturnToHand, Surveil, mana_ability, spell_effects
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import creature
from tests.test_mass_effects import table3


def spell(name, text):
    return Card(name=name, mana_cost="{1}", type_line="Sorcery", oracle_text=text)


PEER_REVIEW = spell("Peer Review", "Create a 2/2 colorless Wizard Soldier creature token named Cadet. Surveil 1.")
SOUL_TETHER = spell("Soul Tether", "Create a Heartwood token.")
SCROLLBOOST = spell("Test Scrollboost", "One or two target creatures each get +2/+2 until end of turn.")
UNWIND = spell("Test Unwind History", "Return target creature an opponent controls with mana value 3 or less to its owner's hand. "
                                 "Surveil 1.")


def sized(name, mana_value):
    return Card(name=name, cmc=float(mana_value), type_line="Creature — Bear", power="2", toughness="2")


class ParseTests(unittest.TestCase):
    def test_a_named_token(self):
        [create, surveil] = spell_effects(PEER_REVIEW)
        self.assertEqual(surveil, Surveil(1))
        token = create.token
        self.assertEqual((create.count, token.name, token.type_line, token.colors, token.power, token.toughness),
                         (1, "Cadet", "Token Creature — Wizard Soldier", (), "2", "2"))

    def test_heartwood(self):
        self.assertEqual(spell_effects(SOUL_TETHER), [CreateTokens(1, HEARTWOOD)])

    def test_one_or_two_targets(self):
        first, second = spell_effects(SCROLLBOOST)
        self.assertEqual((first.target, first.optional_target, second.optional_target, second.distinct),
                         ("creature", False, True, True))
        self.assertEqual(first.modifier, second.modifier)
        self.assertEqual((first.modifier.power, first.modifier.toughness), (2, 2))

    def test_a_mana_value_limit_on_the_target(self):
        [bounce, surveil] = spell_effects(UNWIND)
        self.assertEqual(bounce.target, "creature an opponent controls with mana value 3 or less")
        self.assertIsInstance(bounce, ReturnToHand)

    def test_the_report_understands_them(self):
        for card in (PEER_REVIEW, SOUL_TETHER, SCROLLBOOST, UNWIND):
            self.assertEqual(unsupported_lines(card), [], card.name)


class ResolveTests(unittest.TestCase):
    def test_cadet_is_created_with_its_name(self):
        game, _ = table3()
        a = game.seats[0]
        spell_effects(PEER_REVIEW)[0].resolve(game, a, None)
        [cadet] = a.battlefield
        self.assertEqual(cadet.card.name, "Cadet")

    def test_heartwood_taps_for_red_or_green(self):
        game, _ = table3()
        a = game.seats[0]
        spell_effects(SOUL_TETHER)[0].resolve(game, a, None)
        [heartwood] = a.battlefield
        self.assertEqual(heartwood.card.name, "Heartwood")
        self.assertEqual(mana_ability(heartwood.card, frozenset()), [frozenset({"R", "G"})])  # one mana: red or green

    def test_mana_value_limit_filters_targets(self):
        game, _ = table3()
        a, b, _ = game.seats
        small, edge, big = Permanent(sized("Small", 1)), Permanent(sized("Edge", 3)), Permanent(sized("Big", 4))
        b.battlefield = [small, edge, big]
        a.battlefield = [Permanent(sized("Mine", 1))]
        kind = "creature an opponent controls with mana value 3 or less"
        self.assertEqual(sorted(o.card.name for _, o in game.target_options(kind, a)), ["Edge", "Small"])
        kind = "creature with mana value 3 or greater"
        self.assertEqual(sorted(o.card.name for _, o in game.target_options(kind, a)), ["Big", "Edge"])

    def test_pumping_two_targets_and_leaving_one_out(self):
        game, _ = table3()
        a = game.seats[0]
        one, two = Permanent(creature("One", 1, 1)), Permanent(creature("Two", 1, 1))
        a.battlefield = [one, two]
        first, second = spell_effects(SCROLLBOOST)
        first.resolve(game, a, one)
        second.resolve(game, a, None)  # the second target was left out
        self.assertEqual((game.power(one), game.power(two)), (3, 1))
        second.resolve(game, a, two)
        self.assertEqual(game.power(two), 3)


if __name__ == "__main__":
    unittest.main()
