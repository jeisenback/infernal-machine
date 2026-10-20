import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import (Draw, EachSacrifices, GainLife, LoseLife, OpponentsLoseLife, SacrificeCreature,
                                      TargetLoseLife, line_effects, spell_effects, triggered_abilities)
from infernal_machine.game import CAST, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.helpers import BEAR, creature, lands, pick, table

BLOOD_ARTIST = creature("Blood Artist", 0, 1, "Whenever this creature or another creature dies, target player loses 1 "
                                              "life and you gain 1 life.")
ZULAPORT = creature("Zulaport Cutthroat", 1, 1, "Whenever this creature or another creature you control dies, each "
                                                "opponent loses 1 life and you gain 1 life.")
MOLDERVINE = Card(name="Moldervine Reclamation", mana_cost="{3}{B}{G}", type_line="Enchantment",
                  oracle_text="Whenever a creature you control dies, you gain 1 life and draw a card.")
NIGHTS_WHISPER = Card(name="Night's Whisper", mana_cost="{1}{B}", type_line="Sorcery", colors=("B",),
                      oracle_text="You draw two cards and lose 2 life.")
MERCHANT = REAL["Merchant of Venom"]
ABOMINATION = REAL["Smothering Abomination"]
TAX = REAL["Monologue Tax"]
class ParseTests(unittest.TestCase):
    def test_and_you_gain_life(self):
        self.assertEqual(triggered_abilities(BLOOD_ARTIST)[0].effects, (TargetLoseLife(1, "player"), GainLife(1)))
        self.assertEqual(triggered_abilities(ZULAPORT)[0].effects, (OpponentsLoseLife(1), GainLife(1)))

    def test_gain_life_and_draw(self):
        self.assertEqual(triggered_abilities(MOLDERVINE)[0].effects, (GainLife(1), Draw(1)))

    def test_you_draw_and_lose_life(self):
        self.assertEqual(spell_effects(NIGHTS_WHISPER), [Draw(2), LoseLife(2)])
        self.assertEqual(line_effects("You draw a card and lose 1 life."), [Draw(1), LoseLife(1)])
        self.assertEqual(line_effects("You draw two cards and you lose 2 life."), [Draw(2), LoseLife(2)])

    def test_of_their_choice(self):
        self.assertEqual(triggered_abilities(MERCHANT)[0].effects, (EachSacrifices("player"),))

    def test_sacrifice_a_creature(self):
        self.assertEqual(triggered_abilities(ABOMINATION)[0].effects, (SacrificeCreature(),))

    def test_you_create(self):
        self.assertEqual(triggered_abilities(TAX)[0].effects, tuple(line_effects("Create a Treasure token.")))

    def test_unrelated_and_is_left_alone(self):
        self.assertIsNone(line_effects("Destroy target creature and draw a card if it was green."))

    def test_report_accepts_them(self):
        for card in (BLOOD_ARTIST, ZULAPORT, MOLDERVINE, NIGHTS_WHISPER, MERCHANT, TAX):
            self.assertEqual(unsupported_lines(card), [], card.name)


class PlayTests(unittest.TestCase):
    def test_nights_whisper(self):
        game, _, _ = table(pick(CAST))
        a = game.seats[0]
        a.hand = [NIGHTS_WHISPER]
        a.library = [BEAR, BEAR]
        a.battlefield = lands(2)
        game._priority_round(a)
        self.assertEqual((a.hand, a.life), ([BEAR, BEAR], 38))

    def test_blood_artist_drains(self):
        game, _, _ = table(pick("Player: B"))
        a, b = game.seats
        bear = Permanent(BEAR)
        a.battlefield = [Permanent(BLOOD_ARTIST), bear]
        game.destroy(bear)
        game._priority_round(a)
        self.assertEqual((a.life, b.life), (41, 39))

    def test_sacrifice_a_creature_on_upkeep(self):
        game, _, _ = table()
        a = game.seats[0]
        abomination = Permanent(ABOMINATION)
        a.battlefield = [Permanent(BEAR), abomination]
        game.step = "upkeep"
        game._turn_based_actions(a)
        game._priority_round(a)
        self.assertEqual(a.battlefield, [abomination])
        self.assertEqual(a.graveyard, [BEAR])


if __name__ == "__main__":
    unittest.main()
