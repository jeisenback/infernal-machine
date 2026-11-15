"""Tezzeret the Seeker, from its real Oracle text: "−X: Search your library for an artifact card with mana value X or less, put it onto
the battlefield, then shuffle." (X is chosen up to its loyalty and removed, CR 606.4) and "−5: Artifacts you control become artifact
creatures with base power and toughness 5/5 until end of turn." (artifacts only; an Equipment keeps its subtype)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent, X_PROMPT
from infernal_machine.report import unsupported_lines
from tests.helpers import BEAR, RELIC, activate, real, table3

TEZZERET = real("Tezzeret the Seeker", "{3}{U}{U}", "Legendary Planeswalker — Tezzeret", "+1: Untap up to two target artifacts.\n−X: Search "
                "your library for an artifact card with mana value X or less, put it onto the battlefield, then shuffle.\n−5: Artifacts you "
                "control become artifact creatures with base power and toughness 5/5 until end of turn.", colors=("U",))
ANVIL = Card(name="Anvil", type_line="Artifact", mana_cost="{3}", cmc=3.0)
SWORD = Card(name="Sword", type_line="Artifact — Equipment", mana_cost="{2}", cmc=2.0)


def with_tezzeret(loyalty, x=0):
    game, _ = table3(lambda prompt, options: options.index(str(x)) if X_PROMPT.matches(prompt) else 0)
    a = game.seats[0]
    tezzeret = Permanent(TEZZERET, loyalty=loyalty)
    a.battlefield = [tezzeret]
    return game, a, tezzeret


class TezzeretTests(unittest.TestCase):
    def test_it_is_understood(self):
        self.assertEqual(unsupported_lines(TEZZERET), [])

    def test_minus_x_finds_an_artifact_of_mana_value_x_or_less_and_removes_x_loyalty(self):
        game, a, tezzeret = with_tezzeret(4, x=2)
        a.library = [ANVIL, RELIC]
        activate(game, a, "−X")
        self.assertEqual(([p.card.name for p in a.battlefield], tezzeret.loyalty, [c.name for c in a.library]),
                         (["Tezzeret the Seeker", "Relic"], 2, ["Anvil"]))  # the 3-drop Anvil is above X

    def test_minus_five_makes_your_artifacts_5_5_creatures(self):
        game, a, _ = with_tezzeret(6)
        relic, sword, bear = Permanent(RELIC), Permanent(SWORD), Permanent(BEAR)
        a.battlefield += [relic, sword, bear]
        activate(game, a, "−5")
        self.assertEqual(([(game.power(p), game.toughness(p)) for p in (relic, sword, bear)], "Equipment" in sword.card.type_line,
                          "Creature" in relic.card.type_line), ([(5, 5), (5, 5), (2, 2)], True, True))


if __name__ == "__main__":
    unittest.main()
