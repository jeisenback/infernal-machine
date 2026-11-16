"""Issue #810: tools/mutate.py, the mutation checks. A mutation a test catches, one none does, and the ones refused because they would
not apply; the file is put back every time. Run against a small module in a temporary directory, never the repository's files."""

import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import mutate  # noqa: E402

GUARDED = "def bigger(a, b):\n    if a > b:\n        return a\n    return b\n\n\ndef unused():\n    return 1\n"
TEST = ("import unittest\nfrom guarded import bigger\n\n\nclass T(unittest.TestCase):\n    def test_bigger(self):\n"
        "        self.assertEqual((bigger(3, 2), bigger(2, 3)), (3, 3))\n")


class MutateTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "guarded.py").write_text(GUARDED)
        (self.root / "test_guarded.py").write_text(TEST)

    def caught(self, old, new):
        return mutate.caught(mutate.Mutation("guarded.py", old, new), ["test_guarded"], self.root)

    def assert_untouched(self):
        self.assertEqual((self.root / "guarded.py").read_text(), GUARDED)

    def test_a_guard_the_tests_check_is_caught_and_the_file_put_back(self):
        self.assertTrue(self.caught("if a > b:", "if a < b:"))
        self.assert_untouched()

    def test_a_change_no_test_notices_survives(self):
        self.assertFalse(self.caught("return 1", "return 2"))
        self.assert_untouched()

    def test_a_mutation_that_would_not_apply_is_refused_and_writes_nothing(self):
        for old, new in (("if a >= b:", "if a < b:"), ("return", "return None or"), ("if a > b:", "if a > b:")):
            with self.assertRaises(mutate.Refused, msg=old):
                self.caught(old, new)
            self.assert_untouched()

    def test_the_file_is_put_back_even_if_running_the_tests_fails(self):
        original = mutate.subprocess.run
        def broken(*args, **kwargs):
            raise OSError("no python")
        mutate.subprocess.run = broken
        try:
            with self.assertRaises(OSError):
                self.caught("if a > b:", "if a < b:")
        finally:
            mutate.subprocess.run = original
        self.assert_untouched()

    def test_the_report_and_exit_code(self):
        plan = [(mutate.Mutation("guarded.py", "if a > b:", "if a < b:", "the comparison"), ["test_guarded"]),
                (mutate.Mutation("guarded.py", "return 1", "return 2"), ["test_guarded"])]
        out = io.StringIO()
        self.assertEqual(mutate.run(plan, self.root, out), 1)
        self.assertIn("caught    the comparison", out.getvalue())
        self.assertIn("SURVIVED", out.getvalue())
        out = io.StringIO()
        self.assertEqual(mutate.run([(mutate.Mutation("guarded.py", "nowhere", "x"), ["test_guarded"])], self.root, out), 2)
        self.assertIn("refused", out.getvalue())


if __name__ == "__main__":
    unittest.main()
