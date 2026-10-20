"""Study Hall and Path of Ancestry: mana abilities whose mana, when spent on the right spell, scries."""

import unittest

from infernal_machine.cards import Card
from infernal_machine.effects import ManaSpentTrigger, mana_spent_trigger
from infernal_machine.game import CAST, CAST_COMMANDER, SCRY_PROMPT, Permanent
from infernal_machine.report import unsupported_lines
from tests.real import REAL
from tests.test_effects import BEAR, COMMANDER, FOREST
from tests.test_mass_effects import table3
from tests.test_more_triggers import run_stack

STUDY_HALL = REAL["Study Hall"]
PATH = REAL["Path of Ancestry"]
# The table's commander is Omnath, a green Elemental.
ELEMENTAL = Card(name="Flamekin", mana_cost="{1}{G}", cmc=2, type_line="Creature — Elemental", power="2", toughness="2",
                 colors=("G",))
WHITE_COMMANDER = Card(name="Zada", mana_cost="{W}", cmc=1, type_line="Legendary Creature — Goblin", power="1", toughness="1",
                       colors=("W",))


def scries(player):
    return [prompt for prompt, _ in player.prompts if SCRY_PROMPT.matches(prompt)]


class ParseTests(unittest.TestCase):
    def test_study_hall(self):
        self.assertEqual(mana_spent_trigger(STUDY_HALL), ManaSpentTrigger(spell="commander", scry="commander_casts"))

    def test_path_of_ancestry(self):
        self.assertEqual(mana_spent_trigger(PATH), ManaSpentTrigger(spell="shares_type_with_commander", scry=1))

    def test_a_plain_mana_land_has_none(self):
        self.assertIsNone(mana_spent_trigger(FOREST))

    def test_the_report_understands_them(self):
        for card in (STUDY_HALL, PATH):
            self.assertEqual(unsupported_lines(card), [], card.name)


class PathOfAncestryTests(unittest.TestCase):
    def _table(self):
        game, (a, *_) = table3()
        seat = game.seats[0]
        seat.command_zone, seat.color_identity = [COMMANDER], frozenset("G")  # Omnath, a green Elemental
        seat.battlefield = [Permanent(PATH), Permanent(FOREST)]
        return game, a, seat

    def test_scries_when_its_mana_casts_a_creature_sharing_a_type_with_the_commander(self):
        game, a, seat = self._table()
        seat.hand = [ELEMENTAL]
        game._perform(seat, CAST + ELEMENTAL.name)
        run_stack(game)
        self.assertEqual(len(scries(a)), 1)
        self.assertEqual(seat.battlefield[-1].card, ELEMENTAL)

    def test_no_scry_for_a_creature_of_another_type(self):
        game, a, seat = self._table()
        seat.hand = [BEAR]
        game._perform(seat, CAST + BEAR.name)
        run_stack(game)
        self.assertEqual(scries(a), [])


class StudyHallTests(unittest.TestCase):
    def _table(self):
        game, (a, *_) = table3()
        seat = game.seats[0]
        seat.command_zone, seat.commander_names, seat.color_identity = [WHITE_COMMANDER], {WHITE_COMMANDER.name}, frozenset("W")
        # Only Study Hall's "{1}, {T}" ability can make the {W}; the Forest pays its {1}.
        seat.battlefield = [Permanent(STUDY_HALL), Permanent(FOREST), Permanent(FOREST), Permanent(FOREST)]
        return game, a, seat

    def test_scries_the_number_of_times_the_commander_was_cast(self):
        game, a, seat = self._table()
        seat.commander_casts[WHITE_COMMANDER.name] = 1  # the second cast: it costs {2}{W}
        game._perform(seat, CAST_COMMANDER + WHITE_COMMANDER.name)
        run_stack(game)
        self.assertEqual(len(scries(a)), 2)
        self.assertEqual(seat.battlefield[-1].card, WHITE_COMMANDER)

    def test_no_scry_when_the_colorless_mana_casts_a_spell(self):
        game, a, seat = self._table()
        seat.hand = [BEAR]
        game._perform(seat, CAST + BEAR.name)
        run_stack(game)
        self.assertEqual(scries(a), [])
        self.assertTrue(seat.battlefield[0].tapped)  # Study Hall paid the {1} with {C}


if __name__ == "__main__":
    unittest.main()
