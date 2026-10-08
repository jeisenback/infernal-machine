import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import OnPlayer, triggered_abilities
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.test_mass_effects import table3
from tests.test_trigger_subjects import MOUNTAIN, settle, watcher

MEGRIM = "Whenever an opponent discards a card, Megrim deals 2 damage to that player."
SPY = "Whenever an opponent searches their library, they lose 3 life."


def hand_of(game, seat, count):
    seat.hand = [Card(name=f"Card {n}", type_line="Sorcery") for n in range(count)]


class DiscardTriggerTests(unittest.TestCase):
    def test_parse(self):
        card = watcher("Megrim", MEGRIM)
        (ability,) = triggered_abilities(card)
        self.assertEqual(ability.event, "opponent_discard")
        self.assertIsInstance(ability.effects[0], OnPlayer)
        self.assertEqual(unsupported_lines(card), [])

    def test_each_card_an_opponent_discards_hurts_only_that_player(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(watcher("Megrim", MEGRIM))]
        hand_of(game, b, 3)
        hand_of(game, a, 2)
        game.discard(b, 2)
        game.discard(a, 1)  # its own controller discarding is not an opponent
        settle(game)
        self.assertEqual((a.life, b.life, c.life), (40, 36, 40))

    def test_discarding_the_whole_hand_triggers_per_card(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(watcher("Megrim", MEGRIM))]
        hand_of(game, b, 3)
        game.discard(b, None)
        settle(game)
        self.assertEqual(b.life, 34)

    def test_you_discard_a_card(self):
        card = watcher("Madness", "Whenever you discard a card, you gain 1 life.")
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(card)]
        hand_of(game, a, 2)
        hand_of(game, b, 2)
        game.discard(a, 2)
        game.discard(b, 1)
        settle(game)
        self.assertEqual(a.life, 42)


class SearchTriggerTests(unittest.TestCase):
    def test_parse(self):
        card = watcher("Spy", SPY)
        (ability,) = triggered_abilities(card)
        self.assertEqual(ability.event, "opponent_search")
        self.assertEqual(unsupported_lines(card), [])

    def test_an_opponent_fetching_a_land_triggers_once(self):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(watcher("Spy", SPY))]
        b.library = [MOUNTAIN, MOUNTAIN]
        game.fetch_basic_land(b)
        game.fetch_basic_land(a)  # not an opponent
        settle(game)
        self.assertEqual((a.life, b.life, c.life), (40, 37, 40))

    def test_a_search_that_finds_nothing_still_triggers(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(watcher("Spy", SPY))]
        b.library = []
        game.search_for_lands(b, 1, (), 1, True, False)
        settle(game)
        self.assertEqual(b.life, 37)

    def test_a_tutor_triggers(self):
        game, _ = table3()
        a, b, _ = game.seats
        a.battlefield = [Permanent(watcher("Spy", SPY))]
        b.library = [Card(name="Bear", type_line="Creature — Bear")]
        game.tutor(b, "creature", "hand", False)
        settle(game)
        self.assertEqual(b.life, 37)


class ItsControllerTests(unittest.TestCase):
    def enter(self, text, creature_type="Creature — Bear"):
        game, _ = table3()
        a, b, c = game.seats
        a.battlefield = [Permanent(watcher("Watch", text))]
        b.battlefield = [Permanent(Card(name="Bear", type_line=creature_type, power="2", toughness="2"))]
        return game, a, b, c

    def test_parse(self):
        card = watcher("Watch", "Whenever another creature enters, its controller loses 1 life.")
        (ability,) = triggered_abilities(card)
        self.assertIsInstance(ability.effects[0], OnPlayer)
        self.assertEqual(unsupported_lines(card), [])

    def test_its_controller_loses_life_when_a_creature_enters(self):
        game, a, b, c = self.enter("Whenever another creature enters, its controller loses 1 life.")
        game._enter(b, Permanent(Card(name="Cub", type_line="Creature — Bear", power="1", toughness="1")))
        game._enter(c, Permanent(Card(name="Cub", type_line="Creature — Bear", power="1", toughness="1")))
        settle(game)
        self.assertEqual((a.life, b.life, c.life), (40, 39, 39))

    def test_that_creatures_controller_when_it_dies(self):
        game, a, b, c = self.enter("Whenever a creature dies, Watch deals 2 damage to that creature's controller.")
        game._leave_together([(b.battlefield[0], "destroyed")])
        settle(game)
        self.assertEqual((a.life, b.life, c.life), (40, 38, 40))


if __name__ == "__main__":
    unittest.main()
