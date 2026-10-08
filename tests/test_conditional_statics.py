import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import Condition, spell_effects, static_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import creature
from tests.test_effects import FOREST, SOL_RING, table

TECH = creature("Tinkerer", 1, 1, "As long as you control an artifact, CARDNAME gets +2/+2.")
SPRINTER = creature("Sprinter", 2, 2, "As long as it's your turn, CARDNAME has haste.")
HELLBENT = creature("Hellbent", 2, 2, "CARDNAME gets +2/+2 as long as you have no cards in hand.")
HOARDER = creature("Hoarder", 1, 1, "As long as you have three or more cards in hand, CARDNAME has flying.")
FLOCK = creature("Flock Leader", 1, 1, "As long as you control three or more creatures, creatures you control get +1/+1.")
KING = creature("King", 2, 2, "As long as you're the monarch, CARDNAME gets +1/+1 and has flying.")
BEAR = creature("Cub", 2, 2)
SPELL = Card(name="Spell", type_line="Instant", oracle_text="Draw a card.")


class ParseTests(unittest.TestCase):
    def test_a_conditional_self_buff(self):
        (buff,) = static_abilities(TECH)
        self.assertTrue(buff.self_only)
        self.assertEqual(buff.condition, Condition("control_at_least", 1, "artifact"))
        self.assertEqual((buff.modifier.power, buff.modifier.toughness), (2, 2))

    def test_the_condition_can_come_last(self):
        (buff,) = static_abilities(HELLBENT)
        self.assertEqual(buff.condition, Condition("hand_none"))

    def test_a_conditional_anthem(self):
        (buff,) = static_abilities(FLOCK)
        self.assertEqual((buff.self_only, buff.condition), (False, Condition("control_at_least", 3, "creature")))

    def test_the_report_counts_them_as_playable(self):
        for card in (TECH, SPRINTER, HELLBENT, HOARDER, FLOCK, KING):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_unknown_conditions_and_bare_self_buffs_are_unsupported(self):
        for text in ("As long as the moon is full, CARDNAME gets +1/+1.", "CARDNAME gets +1/+1."):
            self.assertEqual(len(unsupported_lines(creature("x", 1, 1, text))), 1, text)

    def test_an_intervening_if_can_use_the_new_conditions(self):
        card = creature("Maker", 1, 1, "When CARDNAME enters, if you control an artifact, draw a card.")
        self.assertEqual(unsupported_lines(card), [])


class EffectTests(unittest.TestCase):
    def setUp(self):
        self.game, _, _ = table()
        self.a, self.b = self.game.seats

    def test_the_buff_applies_only_while_the_condition_holds(self):
        tech = Permanent(TECH)
        self.a.battlefield = [tech]
        self.assertEqual((self.game.power(tech), self.game.toughness(tech)), (1, 1))
        self.a.battlefield.append(Permanent(SOL_RING))
        self.assertEqual((self.game.power(tech), self.game.toughness(tech)), (3, 3))
        self.a.battlefield.pop()
        self.assertEqual(self.game.power(tech), 1)

    def test_an_opponents_artifact_does_not_count(self):
        tech = Permanent(TECH)
        self.a.battlefield = [tech]
        self.b.battlefield = [Permanent(SOL_RING)]
        self.assertEqual(self.game.power(tech), 1)

    def test_a_self_buff_does_not_reach_other_creatures(self):
        tech, other = Permanent(TECH), Permanent(BEAR)
        self.a.battlefield = [tech, other, Permanent(SOL_RING)]
        self.assertEqual(self.game.power(other), 2)

    def test_haste_only_on_your_turn(self):
        sprinter = Permanent(SPRINTER, sick=True)
        self.a.battlefield = [sprinter]
        self.game.active = 0
        self.assertTrue(self.game.has_keyword(sprinter, "haste"))
        self.game.active = 1
        self.assertFalse(self.game.has_keyword(sprinter, "haste"))

    def test_an_empty_hand(self):
        hellbent = Permanent(HELLBENT)
        self.a.battlefield = [hellbent]
        self.a.hand = [SPELL]
        self.assertEqual(self.game.power(hellbent), 2)
        self.a.hand = []
        self.assertEqual(self.game.power(hellbent), 4)

    def test_cards_in_hand(self):
        hoarder = Permanent(HOARDER)
        self.a.battlefield = [hoarder]
        self.a.hand = [SPELL, SPELL]
        self.assertFalse(self.game.has_keyword(hoarder, "flying"))
        self.a.hand = [SPELL] * 3
        self.assertTrue(self.game.has_keyword(hoarder, "flying"))

    def test_a_conditional_anthem_counts_the_source(self):
        flock, one, two = Permanent(FLOCK), Permanent(BEAR), Permanent(BEAR)
        self.a.battlefield = [flock, one]
        self.assertEqual((self.game.power(flock), self.game.power(one)), (1, 2))  # two creatures: not enough
        self.a.battlefield.append(two)
        self.assertEqual((self.game.power(flock), self.game.power(one), self.game.power(two)), (2, 3, 3))

    def test_monarch(self):
        king = Permanent(KING)
        self.a.battlefield = [king]
        self.assertEqual(self.game.power(king), 2)
        self.game.become_monarch(self.a)
        self.assertEqual(self.game.power(king), 3)
        self.assertTrue(self.game.has_keyword(king, "flying"))
        self.game.become_monarch(self.b)
        self.assertFalse(self.game.has_keyword(king, "flying"))

    def test_a_token_with_a_conditional_ability(self):
        card = Card(name="Grow", type_line="Sorcery", oracle_text=
                    'Create a 3/3 green Elephant creature token with "This creature gets +1/+1 as long as you control a land."')
        (effect,) = spell_effects(card)
        self.assertEqual(unsupported_lines(card), [])
        game, _, _ = table()
        seat = game.seats[0]
        token = Permanent(effect.token)
        seat.battlefield = [token]
        self.assertEqual(game.power(token), 3)
        seat.battlefield.append(Permanent(FOREST))
        self.assertEqual(game.power(token), 4)


if __name__ == "__main__":
    unittest.main()
