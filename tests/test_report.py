import unittest

from infernal_machine.cards import Card, Deck
from infernal_machine.report import category, deck_report, format_report, unsupported_lines

FOREST = Card(name="Forest", type_line="Basic Land — Forest", oracle_text="({T}: Add {G}.)", produced_mana=("G",))
SOL_RING = Card(name="Sol Ring", mana_cost="{1}", type_line="Artifact", oracle_text="{T}: Add {C}{C}.")
MULLDRIFTER = Card(name="Mulldrifter", mana_cost="{4}{U}", type_line="Creature — Elemental",
                   oracle_text="Flying\nWhen Mulldrifter enters, draw two cards.\nEvoke {2}{U} (You may cast this spell for its evoke cost.)")
BOLT = Card(name="Lightning Bolt", mana_cost="{R}", type_line="Instant", oracle_text="Lightning Bolt deals 3 damage to any target.")
SWORDS = Card(name="Swords to Plowshares", mana_cost="{W}", type_line="Instant",
              oracle_text="Exile target creature. Its controller gains life equal to its power.")
MIND_STONE = Card(name="Mind Stone", mana_cost="{2}", type_line="Artifact",
                  oracle_text="{T}: Add {C}.\n{1}, {T}, Sacrifice this artifact: Draw a card.")
THRASIOS = Card(name="Thrasios, Triton Hero", mana_cost="{G}{U}", type_line="Legendary Creature — Merfolk Wizard",
                oracle_text="{4}: Proliferate.\nPartner (You can have two commanders if both have partner.)")


class UnsupportedLinesTests(unittest.TestCase):
    def test_fully_playable(self):
        for card in (FOREST, SOL_RING, BOLT, MIND_STONE):
            self.assertEqual(unsupported_lines(card), [], card.name)

    def test_lists_only_what_is_missing(self):
        self.assertEqual(unsupported_lines(MULLDRIFTER), ["Evoke {2}{U}"])
        self.assertEqual(unsupported_lines(THRASIOS), ["{4}: Proliferate."])  # partner is a deckbuilding line
        self.assertEqual(unsupported_lines(Card(name="x", mana_cost="{Q}", type_line="Creature")), ["mana cost {Q}"])

    def test_categories(self):
        self.assertEqual(category("{4}: Proliferate."), "activated abilities")
        self.assertEqual(category("+1: Draw a card."), "activated abilities")
        self.assertEqual(category("When CARDNAME enters, proliferate."), "triggers (the trigger or its effect)")
        self.assertEqual(category("Create a 1/1 white Soldier creature token."), "tokens")
        self.assertEqual(category("Exile target creature. Its controller gains life equal to its power."), "exile")
        self.assertEqual(category("Creatures you control get +1/+1."), "pump and static buffs")
        self.assertEqual(category("Ward {2}"), "other keywords")
        self.assertEqual(category("Protection from red"), "other keywords")
        self.assertEqual(category("This land enters tapped."), "enters tapped")
        self.assertEqual(category("mana cost {S}"), "mana costs")


class ReportTests(unittest.TestCase):
    def test_format(self):
        deck = Deck([THRASIOS], [FOREST] * 3 + [BOLT, SWORDS, MIND_STONE], [])
        text = format_report(deck_report(deck))
        self.assertIn("Fully playable: 6/7 cards", text)  # Swords to Plowshares is playable now
        self.assertIn("activated abilities (1): Thrasios, Triton Hero", text)
        self.assertIn("Thrasios, Triton Hero: {4}: Proliferate.", text)


if __name__ == "__main__":
    unittest.main()
