import unittest

from infernal_machine.cards import Card
from infernal_machine.game import PLAY_LAND, Permanent
from tests.helpers import spell, table

PATHWAY = {
    "name": "Riverglade Pathway // Lavaglen Pathway", "layout": "modal_dfc", "cmc": 0.0, "id": "abc",
    "color_identity": ["G", "R"], "produced_mana": ["G", "R"],
    "legalities": {"commander": "legal"},
    "card_faces": [
        {"name": "Riverglade Pathway", "type_line": "Land", "oracle_text": "{T}: Add {G}."},
        {"name": "Lavaglen Pathway", "type_line": "Land", "oracle_text": "{T}: Add {R}."},
    ],
}


class PathwayCardTests(unittest.TestCase):
    def test_each_face_makes_only_its_own_mana(self):
        card = Card.from_scryfall(PATHWAY)
        self.assertEqual((card.produced_mana, card.back.produced_mana), (("G",), ("R",)))
        self.assertEqual((card.back.name, card.back.type_line), ("Lavaglen Pathway", "Land"))

    def test_the_cache_round_trip_keeps_the_back(self):
        card = Card.from_scryfall(PATHWAY)
        self.assertEqual(Card.from_dict(card.to_dict()), card)

    def test_other_double_faced_cards_have_no_back(self):
        data = {**PATHWAY, "layout": "transform"}
        self.assertIsNone(Card.from_scryfall(data).back)

    def test_a_back_face_that_is_not_a_land_is_ignored(self):
        data = {**PATHWAY, "card_faces": [PATHWAY["card_faces"][0],
                                          {"name": "Spell", "type_line": "Sorcery", "oracle_text": "Draw a card."}]}
        self.assertIsNone(Card.from_scryfall(data).back)


class PathwayPlayTests(unittest.TestCase):
    def play(self):
        game, _, _ = table(None)
        a = game.seats[0]
        a.hand = [Card.from_scryfall(PATHWAY)]
        return game, a

    def test_both_faces_are_offered(self):
        game, a = self.play()
        actions = [x for x in game.legal_actions(a) if x.startswith(PLAY_LAND)]
        self.assertEqual(actions, [PLAY_LAND + "Riverglade Pathway // Lavaglen Pathway", PLAY_LAND + "Lavaglen Pathway"])

    def test_playing_the_back_face_puts_that_face_on_the_battlefield(self):
        game, a = self.play()
        game._perform(a, PLAY_LAND + "Lavaglen Pathway")
        self.assertEqual(([p.card.name for p in a.battlefield], a.hand, a.lands_played), (["Lavaglen Pathway"], [], 1))
        self.assertIsNotNone(game._payment(a, spell("{R}")))
        self.assertIsNone(game._payment(a, spell("{G}")))

    def test_playing_the_front_face(self):
        game, a = self.play()
        game._perform(a, PLAY_LAND + "Riverglade Pathway // Lavaglen Pathway")
        self.assertIsNotNone(game._payment(a, spell("{G}")))
        self.assertIsNone(game._payment(a, spell("{R}")))


if __name__ == "__main__":
    unittest.main()
