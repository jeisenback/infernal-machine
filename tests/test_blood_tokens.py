"""Blood tokens: "{1}, {T}, Discard a card, Sacrifice this token: Draw a card." (CR 111.10g; Voldaren Epicure, Blood Fountain; #527)."""

import unittest

from infernal_machine.effects import activated_abilities, triggered_abilities
from infernal_machine.effects.families.life_and_damage import DamageEach
from infernal_machine.effects.families.tokens import CreateTokens
from infernal_machine.effects.outcomes import BLOOD
from infernal_machine.game import ACTIVATE
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, OGRE, activate, enter, lands, real, run_stack, table3

EPICURE = real("Voldaren Epicure", "{R}", "Creature — Vampire",
               "When this creature enters, it deals 1 damage to each opponent. Create a Blood token. (It's an artifact with "
               "\"{1}, {T}, Discard a card, Sacrifice this token: Draw a card.\")", "1", "1")
FOUNTAIN = real("Blood Fountain", "{B}", "Artifact",
                "When this artifact enters, create a Blood token. (It's an artifact with \"{1}, {T}, Discard a card, Sacrifice this token: "
                "Draw a card.\")\n{3}{B}, {T}, Sacrifice this artifact: Return up to two target creature cards from your graveyard to your hand.")


def bloods(seat):
    return [p for p in seat.battlefield if p.card.name == "Blood"]


class ParseTests(unittest.TestCase):
    def test_the_cards_are_read(self):
        self.assertEqual(unsupported_lines(EPICURE), [])
        self.assertEqual(unsupported_lines(FOUNTAIN), [])
        effects = list(triggered_abilities(EPICURE)[0].effects)
        self.assertIsInstance(effects[0], DamageEach)
        self.assertEqual(effects[1], CreateTokens(1, BLOOD))
        self.assertEqual(list(triggered_abilities(FOUNTAIN)[0].effects), [CreateTokens(1, BLOOD)])

    def test_the_token_is_an_artifact_with_its_one_ability(self):
        self.assertEqual((BLOOD.name, BLOOD.type_line), ("Blood", "Token Artifact — Blood"))
        self.assertEqual(unsupported_lines(BLOOD), [])
        self.assertEqual(len(activated_abilities(BLOOD)), 1)


class GameTests(unittest.TestCase):
    def test_the_epicure_pings_each_opponent_and_makes_a_blood(self):
        game, _ = table3()
        a, b, c = game.seats
        life = (a.life, b.life, c.life)
        enter(game, a, EPICURE)
        run_stack(game)
        self.assertEqual((a.life, b.life, c.life), (life[0], life[1] - 1, life[2] - 1))
        self.assertEqual(len(bloods(a)), 1)
        self.assertEqual((bloods(b), bloods(c)), ([], []))

    def test_blood_rummages_for_one_mana(self):
        game, _ = table3()
        a = game.seats[0]
        enter(game, a, EPICURE)
        run_stack(game)
        a.battlefield += lands(1)
        a.hand = [OGRE]
        a.library = [BEAR] + a.library
        activate(game, a, "Discard a card")
        self.assertEqual(bloods(a), [], "the token is sacrificed")
        self.assertEqual([c.name for c in a.hand], ["Bear"], "the Ogre is discarded and the Bear drawn")
        self.assertIn("Ogre", [c.name for c in a.graveyard])
        self.assertTrue(all(p.tapped for p in a.battlefield if "Land" in p.card.type_line), "the {1} is paid")

    def test_blood_is_not_offered_with_no_card_to_discard_or_no_mana(self):
        game, _ = table3()
        a = game.seats[0]
        enter(game, a, EPICURE)
        run_stack(game)
        offered = lambda: [x for x in game.legal_actions(a) if x.startswith(ACTIVATE) and "Discard a card" in x]  # noqa: E731
        a.hand = []
        a.battlefield += lands(1)
        self.assertEqual(offered(), [], "no card to discard")
        a.hand = [OGRE]
        self.assertTrue(offered())
        a.battlefield = [p for p in a.battlefield if "Land" not in p.card.type_line]
        self.assertEqual(offered(), [], "no mana for its {1}")


if __name__ == "__main__":
    unittest.main()
