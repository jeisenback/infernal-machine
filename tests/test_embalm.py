"""Issue #797: Embalm {cost}, "({cost}, Exile this card from your graveyard: Create a token that's a copy of it, except it's a white Zombie
[types] with no mana cost. Embalm only as a sorcery.)" (CR 702.128a), from the cards' real Oracle text. All eleven cards whose only gap it
was are fully playable. On Sacred Cat, the most played: the token is a white Zombie Cat with the card's own power, toughness and
abilities and no mana cost, and the card is exiled; it is offered only from the graveyard, at sorcery speed, with the mana to pay."""

import unittest

from infernal_machine.game import EMBALM, Permanent
from tests.helpers import FOREST, lands, run_stack, table3, wording_unlocked
from tests.real import REAL

CARDS = ["Sacred Cat", "Angel of Sanctions", "Aven Wind Guide", "Anointer Priest", "Honored Hydra", "Heart-Piercer Manticore",
         "Oketra's Attendant", "Aven Initiate", "Unwavering Initiate", "Labyrinth Guardian", "Tah-Crop Skirmisher"]
CAT = REAL["Sacred Cat"]
HYDRA = REAL["Honored Hydra"]

# The guards these tests are there to catch (python tools/mutate.py tests.test_embalm).
MUTATIONS = [
    ("infernal_machine/game.py", "                if (cost := embalm_cost(card)) and self._payment(seat, dataclasses.replace(card, mana_cost=cost)) is not None:",
     "                if (cost := embalm_cost(card)):", "only with the mana to pay"),
    ("infernal_machine/game.py", 'self._zombie_copy(seat, card, "embalm", "W", card.power, card.toughness)',
     'self._zombie_copy(seat, card, "embalm", "B", "4", "4")', "a white token with the card's power and toughness"),
    ("infernal_machine/effects/costs.py", "_ENCORE, _ETERNALIZE, _EMBALM, _UNEARTH,", "_ENCORE, _ETERNALIZE, _UNEARTH,", "the line is read"),
]


def setup(card, mana):
    game, _ = table3()
    a = game.seats[0]
    a.graveyard, a.battlefield = [card], lands(mana)
    return game, a


class EmbalmTests(unittest.TestCase):
    def test_every_card_with_it_is_playable(self):
        wording_unlocked(self, CARDS)

    def test_makes_a_white_zombie_token_copy_and_exiles_the_card(self):
        for card, stats in ((CAT, ("1", "1")), (HYDRA, ("6", "6"))):
            game, a = setup(card, 4)
            game._perform(a, EMBALM + card.name)
            run_stack(game)
            (token,) = [p for p in a.battlefield if "Land" not in p.card.type_line]
            kind = card.type_line.partition(" — ")[2]
            self.assertEqual((token.card.type_line, token.card.colors, token.card.mana_cost, (token.card.power, token.card.toughness)),
                             (f"Token Creature — Zombie {kind}", ("W",), "", stats), card.name)
            self.assertEqual(token.card.oracle_text, card.oracle_text)
            self.assertEqual((a.graveyard, a.exile), ([], [card]))

    def test_only_with_the_mana_from_the_graveyard_at_sorcery_speed(self):
        game, a = setup(HYDRA, 3)
        self.assertNotIn(EMBALM + "Honored Hydra", game.legal_actions(a))
        a.battlefield = [Permanent(FOREST)] + lands(3)
        self.assertIn(EMBALM + "Honored Hydra", game.legal_actions(a))
        game.step = "combat"
        self.assertNotIn(EMBALM + "Honored Hydra", game.legal_actions(a))
        game.step, game.active = "main1", 1
        self.assertNotIn(EMBALM + "Honored Hydra", game.legal_actions(a))
        game.active, a.graveyard, a.hand = 0, [], [HYDRA]
        self.assertNotIn(EMBALM + "Honored Hydra", game.legal_actions(a))


if __name__ == "__main__":
    unittest.main()
