"""The pyright ratchet (tools/pyright_ratchet.py): the count may fall but not rise."""

import importlib.util
import os
import tempfile
import unittest

_spec = importlib.util.spec_from_file_location("pyright_ratchet", os.path.join(os.path.dirname(__file__), "..", "tools", "pyright_ratchet.py"))
ratchet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ratchet)


class CountTests(unittest.TestCase):
    def test_the_summary_line_gives_the_count(self):
        self.assertEqual(ratchet.count_errors("/x/game.py:1:1 - error: nope\n398 errors, 0 warnings, 0 informations \n"), 398)

    def test_one_error_and_none(self):
        self.assertEqual(ratchet.count_errors("1 error, 2 warnings, 0 informations"), 1)
        self.assertEqual(ratchet.count_errors("0 errors, 0 warnings, 0 informations"), 0)

    def test_output_without_a_summary_has_no_count(self):
        self.assertIsNone(ratchet.count_errors("Traceback (most recent call last):\nOSError: node not found\n"))

    def test_the_last_summary_line_wins(self):
        self.assertEqual(ratchet.count_errors("5 errors, 0 warnings, 0 informations\n3 errors, 0 warnings, 0 informations\n"), 3)


class CheckTests(unittest.TestCase):
    def test_a_rise_fails(self):
        ok, line = ratchet.check(11, 10)
        self.assertFalse(ok)
        self.assertIn("1 more than the baseline of 10", line)

    def test_the_baseline_passes(self):
        self.assertTrue(ratchet.check(10, 10)[0])

    def test_a_fall_passes_and_says_to_lower_the_baseline(self):
        ok, line = ratchet.check(7, 10)
        self.assertTrue(ok)
        self.assertIn("lower .github/pyright-baseline to 7", line)

    def test_an_unknown_count_fails(self):
        self.assertFalse(ratchet.check(None, 10)[0])

    def test_at_zero_any_error_fails(self):
        self.assertFalse(ratchet.check(1, 0)[0])
        self.assertTrue(ratchet.check(0, 0)[0])


class MainTests(unittest.TestCase):
    def run_main(self, output, baseline):
        with tempfile.TemporaryDirectory() as directory:
            out, base = os.path.join(directory, "pyright.txt"), os.path.join(directory, "baseline")
            with open(out, "w") as f:
                f.write(output)
            with open(base, "w") as f:
                f.write(f"{baseline}\n")
            return ratchet.main([out, "--baseline", base])

    def test_exit_status_follows_the_check(self):
        self.assertEqual(self.run_main("5 errors, 0 warnings, 0 informations", 5), 0)
        self.assertEqual(self.run_main("6 errors, 0 warnings, 0 informations", 5), 1)
        self.assertEqual(self.run_main("crash", 5), 1)


if __name__ == "__main__":
    unittest.main()
