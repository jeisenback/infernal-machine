"""The combo lines tool (#534): a combo's loop is run as the actions Spellbook's steps name and the result is read off the table.
The cards are from their real Oracle text."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import combo_lines  # noqa: E402
from tools.combo_lines import Line, answer, board, goblins, mana_yield, run  # noqa: E402

from tests.helpers import real  # noqa: E402

BOND = real("Sanguine Bond", "{3}{B}{B}", "Enchantment", "Whenever you gain life, target opponent loses that much life.")
BLOOD = real("Exquisite Blood", "{4}{B}", "Enchantment", "Whenever an opponent loses life, you gain that much life.")
PROSPECTOR = real("Skirk Prospector", "{R}", "Creature — Goblin", "Sacrifice a Goblin: Add {R}.", "1", "1")
BASALT = real("Basalt Monolith", "{3}", "Artifact", "This artifact doesn't untap during your untap step.\n{T}: Add {C}{C}{C}.\n{3}: Untap this artifact.")
CARDS = {card.name: card for card in (BOND, BLOOD, PROSPECTOR, BASALT)}


class RunnerTests(unittest.TestCase):
    def test_a_loop_the_triggers_run_ends_the_game(self):
        line = Line("Sanguine Bond + Exquisite Blood", "infinite life loss", ("Sanguine Bond", "Exquisite Blood"), start=combo_lines.lose_a_life)
        self.assertEqual(run(line, CARDS, 12), "wins once started")

    def test_without_the_second_piece_only_the_starting_life_is_lost(self):
        line = Line("Sanguine Bond", "-", ("Sanguine Bond",), start=combo_lines.lose_a_life, measure=combo_lines.opponent_life, unit="opponent life")
        self.assertEqual(run(line, CARDS, 12), "ends on its own, opponent life 40 to 39")

    def test_an_action_that_is_not_offered_stops_the_round_and_names_it(self):
        line = Line("Basalt Monolith", "-", ("Basalt Monolith",), loop=("{3}: Untap this artifact", "Cast: Nothing"))
        self.assertEqual(run(line, CARDS, 12), 'stops in round 1: "Cast: Nothing" is not offered')

    def test_a_mana_loop_reports_what_one_tap_yields_against_what_a_round_pays(self):
        line = Line("Basalt Monolith", "-", ("Basalt Monolith",), loop=("{3}: Untap this artifact",), measure=mana_yield, cost=3)
        self.assertEqual(run(line, CARDS, 5), "runs 5 rounds; one tap yields 3 mana, a round pays 3 (+0); 0 in the pool")

    def test_a_step_with_until_takes_no_action_when_what_it_waits_for_is_offered(self):
        line = Line("Skirk Prospector", "-", ("Skirk Prospector",), setup=goblins(2), loop=("Skirk Prospector until Skirk Prospector",),
                    measure=board, unit="permanents")
        self.assertEqual(run(line, CARDS, 3), "runs 3 rounds, permanents 3 to 3")

    def test_a_step_with_until_repeats_until_it_is_offered(self):
        line = Line("Skirk Prospector", "-", ("Skirk Prospector",), setup=goblins(2), loop=("Skirk Prospector until Cast: Nothing",))
        self.assertEqual(run(line, CARDS, 1), 'stops in round 1: "Skirk Prospector" is not offered before "Cast: Nothing"')


class AnswerTests(unittest.TestCase):
    def test_an_answer_for_a_named_question_does_not_apply_to_another(self):
        policy = answer(("Choose X~1", "Ogre"))
        self.assertEqual(policy("Choose X for Chatterfang", ["0", "1", "2"]), 1)
        self.assertEqual(policy("Choose a target for Chatterfang", ["Bear", "Ogre"]), 1)
        self.assertEqual(policy("Choose a target for Chatterfang", ["Bear", "1"]), 0)  # "Choose X~1" is for the X question only

    def test_a_question_nothing_answers_takes_the_first_option(self):
        self.assertEqual(answer(("Nothing",))("Choose", ["a", "b"]), 0)


class LinesTests(unittest.TestCase):
    def test_every_combo_has_one_line(self):
        names = [line.combo for line in combo_lines.LINES]
        self.assertEqual(len(names), len(set(names)))


if __name__ == "__main__":
    unittest.main()
