import unittest

from infernal_machine.cards import Card
from infernal_machine.game import CAST, PLAY_LAND, Permanent
from infernal_machine.report import unsupported_lines
from tests.test_combat import BEAR
from tests.test_effects import BOLT, DIVINATION, FOREST, MURDER, lands, pick, table
from tests.test_tokens import RAISE

SOUL_WARDEN = Card(name="Soul Warden", mana_cost="{W}", type_line="Creature — Human Cleric", power="1", toughness="1",
                   oracle_text="Whenever another creature enters, you gain 1 life.")
GUIDE = Card(name="Guide", mana_cost="{G}", type_line="Enchantment",
             oracle_text="Whenever a nontoken creature you control enters, draw a card.")
COURSER = Card(name="Courser", mana_cost="{G}", type_line="Enchantment",
               oracle_text="Landfall — Whenever a land you control enters, you gain 1 life.")
PAWN = Card(name="Pawn", mana_cost="{B}", type_line="Creature — Human", power="1", toughness="1",
            oracle_text="Whenever another creature you control dies, draw a card.")
ZULAPORT = Card(name="Zulaport", mana_cost="{B}", type_line="Creature — Human", power="1", toughness="1",
                oracle_text="Whenever Zulaport or another creature you control dies, each opponent loses 1 life.")
MONK = Card(name="Monk", mana_cost="{U}", type_line="Creature — Human Monk", power="1", toughness="1",
            oracle_text="Whenever you cast a noncreature spell, put a +1/+1 counter on each creature you control.")
CRUSADE = Card(name="Test Crusade", mana_cost="{W}", type_line="Enchantment",
               oracle_text="Whenever another creature you control enters, put a +1/+1 counter on it.")


class WatchTriggerTests(unittest.TestCase):
    def test_another_creature_enters_on_any_side(self):
        game, _, _ = table(pick(CAST), pick(CAST))
        game.seats[0].battlefield = [Permanent(SOUL_WARDEN)]
        game.seats[1].hand = [BEAR]
        game.seats[1].battlefield = lands(1, FOREST)
        game.active = 1
        game._priority_round(game.seats[1])
        self.assertEqual(game.seats[0].life, 41)  # an opponent's creature counts too

    def test_nontoken_creature_you_control(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.battlefield = [Permanent(GUIDE)] + lands(2, Card(name="Plains", type_line="Basic Land", produced_mana=("W", "G")))
        seat.hand = [RAISE]
        game._priority_round(seat)
        self.assertEqual(seat.hand, [])  # two tokens: no cards
        seat.hand = [BEAR]
        for land in seat.battlefield:
            land.tapped = False
        game._priority_round(seat)
        self.assertEqual(len(seat.hand), 1)

    def test_landfall(self):
        game, _, _ = table(pick(PLAY_LAND))
        seat = game.seats[0]
        seat.battlefield = [Permanent(COURSER)]
        seat.hand = [FOREST]
        game._priority_round(seat)
        self.assertEqual(seat.life, 41)

    def test_another_creature_dies(self):
        game, _, _ = table(pick(CAST, "Bear"))
        seat = game.seats[0]
        seat.battlefield = [Permanent(PAWN), Permanent(BEAR)] + lands(1, Card(name="Mountain", type_line="Basic Land", produced_mana=("R",)))
        seat.hand = [BOLT]
        game._priority_round(seat)
        self.assertEqual(len(seat.hand), 1)

    def test_self_or_another_dies_looks_back(self):
        game, _, _ = table(pick(CAST, "Zulaport"))
        seat = game.seats[0]
        seat.battlefield = [Permanent(ZULAPORT)] + lands(3, Card(name="Swamp", type_line="Basic Land", produced_mana=("B",)))
        seat.hand = [MURDER]
        game._priority_round(seat)
        self.assertEqual(game.seats[1].life, 39)  # it saw its own death

    def test_opponents_creatures_dying_do_not_count_for_you_control(self):
        game, _, _ = table(pick(CAST, "Bear"))
        seat = game.seats[0]
        seat.battlefield = [Permanent(PAWN)] + lands(1, Card(name="Mountain", type_line="Basic Land", produced_mana=("R",)))
        game.seats[1].battlefield = [Permanent(BEAR)]
        seat.hand = [BOLT]
        game._priority_round(seat)
        self.assertEqual(seat.hand, [])

    def test_cast_noncreature_spell(self):
        game, _, _ = table(pick(CAST))
        seat = game.seats[0]
        monk = Permanent(MONK)
        seat.battlefield = [monk] + lands(3, Card(name="Island", type_line="Basic Land", produced_mana=("U",)))
        seat.hand = [DIVINATION]
        game._priority_round(seat)
        self.assertEqual(monk.counters, {"+1/+1": 1})

    def test_casts_by_opponents_do_not_count(self):
        game, _, _ = table(None, pick(CAST))
        monk = Permanent(MONK)
        game.seats[0].battlefield = [monk]
        game.seats[1].battlefield = lands(3, Card(name="Island", type_line="Basic Land", produced_mana=("U",)))
        game.step = "end"
        game.seats[1].hand = [Card(name="Opt", mana_cost="{U}", type_line="Instant", oracle_text="Draw a card.")]
        game._priority_round(game.seats[0])
        self.assertEqual(monk.counters, {})

    def test_the_trigger_resolves_before_the_spell(self):
        game, a, _ = table(pick(CAST))
        seat = game.seats[0]
        seat.battlefield = [Permanent(MONK)] + lands(3, Card(name="Island", type_line="Basic Land", produced_mana=("U",)))
        seat.hand = [DIVINATION]
        game._priority_round(seat)
        order = [(e["event"], e["card"]) for e in a.events if e["event"] in ("cast", "trigger", "resolve")]
        self.assertEqual(order, [("cast", "Divination"), ("trigger", "Monk"), ("resolve", "Monk"), ("resolve", "Divination")])

    def test_report(self):
        for card in (SOUL_WARDEN, GUIDE, COURSER, PAWN, ZULAPORT, MONK, CRUSADE):
            self.assertEqual(unsupported_lines(card), [], card.name)
        tapper = Card(name="Tapper", type_line="Enchantment", oracle_text="Whenever another creature enters, tap it.")
        self.assertEqual(unsupported_lines(tapper), ["Whenever another creature enters, tap it."])


if __name__ == "__main__":
    unittest.main()
