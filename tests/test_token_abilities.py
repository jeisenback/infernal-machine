import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (POPULATE_PROMPT, Amount, CopyToken, CreateTokens, Populate, spell_effects,
                                      triggered_abilities)
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, lands, pick, table

PEST_MAKER = Card(name="Pest Maker", mana_cost="{1}", type_line="Sorcery",
                  oracle_text='Create a 1/1 black and green Pest creature token with "When this creature dies, you gain 1 life."')
FLYING_PEST = Card(name="Flying Pest Maker", mana_cost="{1}", type_line="Sorcery",
                   oracle_text='Create a 1/1 black and green Pest creature token with flying and '
                               '"When this creature dies, you gain 1 life."')
SOLDIERS = Card(name="Soldiers", mana_cost="{1}", type_line="Sorcery",
                oracle_text="Create a 1/1 white Soldier creature token.")
MOUNTAIN = Card(name="Mountain", type_line="Basic Land", produced_mana=("R",))


def settle(game):
    game._priority_round(game.seats[0])


class QuotedTokenTests(unittest.TestCase):
    def test_the_token_carries_the_ability(self):
        (effect,) = spell_effects(PEST_MAKER)
        self.assertIsInstance(effect, CreateTokens)
        (ability,) = triggered_abilities(effect.token)
        self.assertEqual(ability.event, "dies")
        self.assertEqual(unsupported_lines(PEST_MAKER), [])

    def test_keywords_and_a_quoted_ability(self):
        (effect,) = spell_effects(FLYING_PEST)
        self.assertEqual(effect.token.oracle_text.splitlines()[0], "Flying")
        self.assertEqual(len(triggered_abilities(effect.token)), 1)

    def test_the_ability_works_when_the_token_dies(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [PEST_MAKER]
        seat.battlefield = lands(1, MOUNTAIN)
        settle(game)
        pest = next(p for p in seat.battlefield if p.card.name == "Pest")
        game._leave_battlefield(pest, "dies")
        settle(game)
        self.assertEqual(seat.life, 41)

    def test_an_ability_we_cant_play_makes_the_card_unsupported(self):
        card = Card(name="x", type_line="Sorcery",
                    oracle_text='Create a 1/1 green Saproling creature token with "When this creature dies, it explodes."')
        self.assertIsNone(spell_effects(card))


class CopyTokenTests(unittest.TestCase):
    def test_parse(self):
        card = Card(name="Copier", type_line="Sorcery", oracle_text="Create a token that's a copy of target creature you control.")
        self.assertEqual(spell_effects(card), [CopyToken("creature you control")])
        self.assertEqual(unsupported_lines(card), [])

    def test_a_copy_is_a_token_with_the_same_card(self):
        game, _, _ = table()
        a = game.seats[0]
        bear = Permanent(BEAR)
        a.battlefield = [bear]
        CopyToken("creature").resolve(game, a, bear)
        self.assertEqual(len(a.battlefield), 2)
        copy = a.battlefield[1]
        self.assertTrue(copy.card.type_line.startswith("Token"))
        self.assertEqual((copy.card.name, copy.card.power, copy.card.toughness), ("Bear", "2", "2"))
        self.assertFalse(bear.card.type_line.startswith("Token"))

    def test_a_copy_of_a_token_stays_one_token_type(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1"))]
        CopyToken("creature").resolve(game, a, a.battlefield[0])
        self.assertEqual([p.card.type_line for p in a.battlefield], ["Token Creature — Soldier"] * 2)

    def test_casting_it(self):
        card = Card(name="Copier", mana_cost="{1}", type_line="Sorcery",
                    oracle_text="Create a token that's a copy of target creature you control.")
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR)] + lands(1, MOUNTAIN)
        a.hand = [card]
        settle(game)
        self.assertEqual(sorted(p.card.name for p in a.battlefield if p.card.name == "Bear"), ["Bear", "Bear"])


class PopulateTests(unittest.TestCase):
    def test_parse(self):
        card = Card(name="Pop", type_line="Sorcery", oracle_text="Populate.")
        self.assertEqual(spell_effects(card), [Populate()])

    def test_it_copies_the_only_token(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR), Permanent(Card(name="Soldier", type_line="Token Creature — Soldier",
                                                          power="1", toughness="1"))]
        Populate().resolve(game, a, None)
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Bear", "Soldier", "Soldier"])

    def test_it_asks_when_there_is_a_choice(self):
        seen = []

        def policy(prompt, options):
            seen.append((prompt, options))
            return 1

        game, _, _ = table(policy)
        a = game.seats[0]
        soldier = Card(name="Soldier", type_line="Token Creature — Soldier", power="1", toughness="1")
        giant = Card(name="Giant", type_line="Token Creature — Giant", power="4", toughness="4")
        a.battlefield = [Permanent(soldier), Permanent(giant), Permanent(soldier)]
        Populate().resolve(game, a, None)
        self.assertEqual(seen, [(POPULATE_PROMPT, ["Soldier 1/1", "Giant 4/4"])])  # identical tokens count once
        self.assertEqual(sorted(p.card.name for p in a.battlefield), ["Giant", "Giant", "Soldier", "Soldier"])

    def test_nothing_happens_without_a_token(self):
        game, _, _ = table()
        a = game.seats[0]
        a.battlefield = [Permanent(BEAR)]
        Populate().resolve(game, a, None)
        self.assertEqual(len(a.battlefield), 1)


class HalfLifeTests(unittest.TestCase):
    def test_rounding(self):
        game, _, _ = table()
        a = game.seats[0]
        a.life = 7
        self.assertEqual(game.evaluate(Amount("half_life", "down"), a), 3)
        self.assertEqual(game.evaluate(Amount("half_life", "up"), a), 4)
        a.life = -3
        self.assertEqual(game.evaluate(Amount("half_life", "up"), a), 0)

    def test_as_a_token_count(self):
        card = Card(name="Halve", mana_cost="{1}", type_line="Sorcery",
                    oracle_text="Let X be half your life total, rounded down.\nCreate X 1/1 white Soldier creature tokens.")
        self.assertEqual(unsupported_lines(card), [])
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.life = 9
        a.hand = [card]
        a.battlefield = lands(1, MOUNTAIN)
        settle(game)
        self.assertEqual(len([p for p in a.battlefield if p.card.name == "Soldier"]), 4)


if __name__ == "__main__":
    unittest.main()
