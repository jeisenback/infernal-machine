import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import filter_mana_ability, spell_effects
from infernal_machine.game import CAST, PASS, X_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_effects import FOREST, lands, pick, table

ISLAND = Card(name="Island", type_line="Basic Land — Island", produced_mana=("U",))
SIGNET = Card(name="Azorius Signet", mana_cost="{2}", type_line="Artifact", oracle_text="{1}, {T}: Add {W}{U}.")
SWAN = Card(name="White Card", mana_cost="{W}{W}", type_line="Sorcery", oracle_text="You gain 2 life.")
FIREBALL = Card(name="Blaze", mana_cost="{X}{R}", type_line="Sorcery", oracle_text="Blaze deals X damage to any target.")
STROKE = Card(name="Stroke", mana_cost="{X}{U}", type_line="Instant", oracle_text="Draw X cards.")
HYDRA = Card(name="Hydra", mana_cost="{X}{G}", type_line="Creature — Hydra", power="0", toughness="0",
             oracle_text="This creature enters with X +1/+1 counters on it.")
RAINBOW = Card(name="City of Brass", type_line="Land", produced_mana=tuple("WUBRG"))


def x_policy(x, *then):
    base = pick(*then)
    return lambda prompt, options: min(x, len(options) - 1) if prompt.startswith(X_PROMPT) else base(prompt, options)


class SignetTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(filter_mana_ability(SIGNET), ("{1}", [frozenset("W"), frozenset("U")]))
        self.assertEqual(unsupported_lines(SIGNET), [])

    def test_signet_turns_one_land_into_two_colors(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [SWAN]
        seat.battlefield = [Permanent(SIGNET), Permanent(FOREST)]
        self.assertNotIn(CAST + "White Card", game.legal_actions(seat))  # {W}{W}: the Signet makes one W, one U
        seat.hand = [Card(name="Azorius Card", mana_cost="{W}{U}", type_line="Sorcery", oracle_text="Draw a card.")]
        self.assertIn(CAST + "Azorius Card", game.legal_actions(seat))
        game._priority_round(seat)
        self.assertTrue(all(p.tapped for p in seat.battlefield))

    def test_signet_cannot_pay_for_itself(self):
        game, _, _ = table()
        seat = game.seats[0]
        seat.hand = [Card(name="Blue Card", mana_cost="{U}", type_line="Sorcery", oracle_text="Draw a card.")]
        seat.battlefield = [Permanent(SIGNET)]
        self.assertEqual(game.legal_actions(seat), [PASS])

    def test_plain_sources_are_used_before_a_signet(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.hand = [Card(name="Blue Card", mana_cost="{U}", type_line="Sorcery", oracle_text="Draw a card.")]
        signet = Permanent(SIGNET)
        seat.battlefield = [signet, Permanent(ISLAND)]
        game._priority_round(seat)
        self.assertFalse(signet.tapped)


class XTests(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(spell_effects(STROKE)[0].count, "X")

    def test_choose_x_and_deal_x_damage(self):
        game, a, _ = table(x_policy(3, CAST, "Player: B"))
        game.seats[0].hand = [FIREBALL]
        game.seats[0].battlefield = lands(4, RAINBOW)
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[1].life, 37)
        x_prompt = next(options for prompt, options in a.prompts if prompt.startswith(X_PROMPT))
        self.assertEqual(x_prompt, ["0", "1", "2", "3"])  # four lands: {R} plus up to 3

    def test_x_counts_signet_mana(self):
        game, a, _ = table(x_policy(9, CAST))
        game.seats[0].hand = [STROKE]
        game.seats[0].battlefield = [Permanent(SIGNET), Permanent(ISLAND), Permanent(ISLAND)]
        game._priority_round(game.seats[0])
        self.assertEqual(len(game.seats[0].hand), 2)  # 3 mana worth: {U} + X=2

    def test_x_is_zero_outside_its_spell(self):
        game, _, _ = table(x_policy(0, CAST))
        game.seats[0].hand = [STROKE]
        game.seats[0].battlefield = lands(1, RAINBOW)
        game._priority_round(game.seats[0])
        self.assertEqual((game.seats[0].hand, game.x_value), ([], 0))

    def test_enters_with_x_counters(self):
        game, _, _ = table(x_policy(4, CAST))
        game.seats[0].hand = [HYDRA]
        game.seats[0].battlefield = lands(5, RAINBOW)
        game._priority_round(game.seats[0])
        hydra = game.seats[0].battlefield[-1]
        self.assertEqual((game.power(hydra), game.toughness(hydra)), (4, 4))

    def test_hydra_with_x_zero_dies(self):
        game, _, _ = table(x_policy(0, CAST))
        game.seats[0].hand = [HYDRA]
        game.seats[0].battlefield = lands(1, RAINBOW)
        game._priority_round(game.seats[0])
        self.assertEqual(game.seats[0].graveyard, [HYDRA])

    def test_report(self):
        for card in (FIREBALL, STROKE, HYDRA):
            self.assertEqual(unsupported_lines(card), [], card.name)


if __name__ == "__main__":
    unittest.main()
