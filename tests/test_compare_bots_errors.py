"""tools/compare_bots.py says which game crashed or timed out, so it can be replayed (#535): the count, the first error, its seed and seat."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import compare_bots  # noqa: E402

from infernal_machine.matchup import Record  # noqa: E402


class ErrorNoteTests(unittest.TestCase):
    def test_it_names_the_count_the_error_and_the_game(self):
        record = Record("x", 0, errors=1, first_error="ValueError: max() iterable argument is empty", first_error_at="seed 507654502, focus seat 1")
        self.assertEqual(compare_bots.error_note(record),
                         "  [1 errors: ValueError: max() iterable argument is empty (seed 507654502, focus seat 1)]")

    def test_without_a_game_to_name_it_is_the_count_and_the_error(self):
        record = Record("x", 0, errors=2, first_error="timeout")
        self.assertEqual(compare_bots.error_note(record), "  [2 errors: timeout]")


if __name__ == "__main__":
    unittest.main()
