"""Land-count comparisons (issue #80): Claim Jumper and Archaeomancer's Map. Lines are the cards' own Oracle text from
Scryfall (the Map's first line is not written here)."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.game import Permanent
from infernal_machine.report import unsupported_lines
from tests.helpers import card, fire, FOREST, lands, pick, PLAINS, run_stack, table3, triggers_80_supported as supported

JUMPER = card("Vigilance\nWhen this creature enters, if an opponent controls more lands than you, you may search your library "
              "for a Plains card and put it onto the battlefield tapped. Then if an opponent controls more lands than you, "
              "repeat this process once. If you search your library this way, shuffle.", "Jumper")
MAP = card("Whenever a land an opponent controls enters, if that player controls more lands than you, you may put a land card "
           "from your hand onto the battlefield.", "Map", "Artifact")


class ClaimJumperTests(unittest.TestCase):
    def enter(self, mine, theirs, plains=3, answer="Yes"):
        game, _ = table3(pick(answer, "Plains", "Plains", "Plains"))
        a, b, _ = game.seats
        jumper = Permanent(JUMPER)
        a.battlefield = [jumper] + lands(mine, FOREST)
        b.battlefield = lands(theirs, FOREST)
        a.library = [PLAINS] * plains + [FOREST] * 5
        fire(game, a, jumper, "enters")
        return a

    def plains(self, seat):
        return [p for p in seat.battlefield if p.card.name == "Plains"]

    def test_parse(self):
        supported(self, JUMPER)

    def test_it_repeats_once_while_an_opponent_still_has_more(self):
        a = self.enter(mine=1, theirs=5)
        self.assertEqual(len(self.plains(a)), 2)
        self.assertTrue(all(p.tapped for p in self.plains(a)))

    def test_it_stops_after_one_when_that_evens_the_lands(self):
        a = self.enter(mine=1, theirs=2)
        self.assertEqual(len(self.plains(a)), 1)

    def test_nothing_when_no_opponent_has_more_lands(self):
        a = self.enter(mine=2, theirs=2)
        self.assertEqual(self.plains(a), [])

    def test_declining_fetches_nothing(self):
        a = self.enter(mine=1, theirs=5, answer="No")
        self.assertEqual(self.plains(a), [])

    def test_with_one_plains_left_it_fetches_that_one(self):
        a = self.enter(mine=1, theirs=5, plains=1)
        self.assertEqual(len(self.plains(a)), 1)


class ArchaeomancersMapTests(unittest.TestCase):
    def table(self, mine, theirs):
        game, _ = table3(pick("Yes", "Forest"))
        a, b, _ = game.seats
        a.battlefield = [Permanent(MAP)] + lands(mine, PLAINS)
        b.battlefield = lands(theirs, PLAINS)
        a.hand = [FOREST]
        return game, a, b

    def test_parse(self):
        supported(self, MAP)

    def test_an_opponent_land_that_puts_them_ahead_lets_you_play_one(self):
        game, a, b = self.table(mine=1, theirs=1)
        game._enter(b, Permanent(PLAINS))
        run_stack(game)
        self.assertEqual((a.hand, sum(p.card.name == "Forest" for p in a.battlefield)), ([], 1))

    def test_not_when_they_only_draw_level(self):
        game, a, b = self.table(mine=2, theirs=1)
        game._enter(b, Permanent(PLAINS))
        run_stack(game)
        self.assertEqual(a.hand, [FOREST])

    def test_your_own_land_does_not_trigger_it(self):
        game, a, b = self.table(mine=0, theirs=3)
        game._enter(a, Permanent(PLAINS))
        run_stack(game)
        self.assertEqual(a.hand, [FOREST])

    def test_a_permanent_that_is_not_a_land_does_not_trigger_it(self):
        game, a, b = self.table(mine=0, theirs=3)
        game._enter(b, Permanent(Card(name="Bear", type_line="Creature — Bear", power="2", toughness="2")))
        run_stack(game)
        self.assertEqual(a.hand, [FOREST])
